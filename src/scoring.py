"""Structured CV scoring and document selection over immutable analysis snapshots."""

import asyncio
from copy import deepcopy
import pandas as pd
from .cache import AnalysisResultCache, make_cache_key
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .analysis import Assessment, AnalyzedBullet, AnalyzedRole, AnalysisSnapshot, SelectionPolicy, select_bullets, aggregate_metrics, score_comment
from .documents import DocSection, DocSectionItem, FullCVDocument
from .outcomes import StageFailure, gather_owned


class BulletAnalysis(BaseModel):
    """BulletAnalysis model."""
    experience_relevance_score: float = Field(..., ge=0, le=10, allow_inf_nan=False, description="Score from 0 to 10 based on relevance to the job posting.")
    explanation: str = Field(..., description="Short explanation (less than 20 words) of why the score was assigned.")
    posting_evidence: str = Field(..., description="Which parts of the job posting analysis are relevant to this bullet.")

class SectionAnalysis(BaseModel):
    """SectionAnalysis model."""
    experience_relevance_score: float = Field(..., ge=0, le=10, allow_inf_nan=False, description="Overall score from 0 to 10 for the entire role/experience.")
    explanation: str = Field(..., description="Concise summary justifying the overall score based on the individual items.")
    posting_evidence: str = Field(..., description="Key skills/requirements satisfied by this entire section.")

class PersonalStatementAnalysis(BaseModel):
    """PersonalStatementAnalysis model."""
    experience_relevance_score: float = Field(..., description="Score from 0 to 10 of how well the statement matches the job.")
    explanation: str = Field(..., description="Why this statement is or isn't a good fit.")

class PersonalStatementRewrite(BaseModel):
    """PersonalStatementRewrite model."""
    edited_statement: str = Field(..., description="The new, concise personal statement using provided points.")
    analysis: str = Field(..., description="Detailed scoring and selection reasoning for the statements.")

personal_statement_analysis_prompt = '''
    You are a CV analyzer. Analyze the provided personal statement against the job posting data.
    Job posting information: {job_posting_data}
    Personal Statement: {personal_statement}
'''

personal_statement_list_analysis_prompt = '''
    You are provided with a job description and some alternative personal statements.
    Your goal is to create a calibrated personal statement using ONLY points from the examples.
    1. Score them (0 to 10) in relevance and candidate strength.
    2. Create a concise final statement that takes the strongest points.
    Avoid repetition. Do not make up statements.
    Job posting: {job_posting_raw}
    Alternative Personal statements: {personal_statements}
'''

section_experience_analysis_prompt = '''
    You are a CV analyzer. Assess how relevant this specific CV experience bullet point is to the job posting.
    Assign at least 5 if there is evidence of excellence or strong work ethic.
    Job posting information: {job_posting_data}
    CV Experience Bullet: {cv_experience}
'''

section_synthesis_analysis_prompt = '''
    You are evaluating the OVERALL relevance of a specific work experience section from a CV.
    Job posting requirements: {job_posting_data}
    CV Section context:
    Company: {company}
    Position: {position}
    Full text: {cv_experience}
    Detailed analysis of individual bullet points in this section: {item_analyses}
    Based on the above, provide an OVERALL relevance score (0-10) for this entire role.
    The section score must be logically grounded in the individual item scores.
'''

def _make_default_model():
    """Resolve the legacy ad hoc caller's analysis role only at construction."""
    from .config import BackendConfig, build_model
    return build_model(BackendConfig().analysis_model)

class CVCrossAnalyzer:
    """Score immutable source content, select IDs, then build render-only documents."""
    def __init__(self, job_post_analyzer, full_cv_document, llm_model = None, llm_editor_model = None, max_section_parse_retries = 3, *, cache=None, model_identity=None):
        """Inject posting/document/model/cache dependencies; parsing retries remain reserved."""
        self.cv_model = full_cv_document
        self.cache = cache if cache is not None else AnalysisResultCache()
        # Ad hoc callers without declared model settings cannot safely reuse cache.
        self.model_identity = deepcopy(model_identity)
        self.source_cv = full_cv_document.copy()
        self.snapshot: AnalysisSnapshot | None = None
        self.selected_ids: frozenset[str] | None = None
        self.job_post_analyzer = job_post_analyzer
        self.model = llm_model or _make_default_model()
        self.llm_editor_model = llm_editor_model or self.model
        self.max_section_parse_retries = max_section_parse_retries
        self.personal_statements = None

        self.chains = {
            'personal_statement_analysis' : {
                'chain' : ChatPromptTemplate.from_template(personal_statement_analysis_prompt) | self.model.with_structured_output(PersonalStatementAnalysis),
                'provides' : 'personal_statement_analysis'
            },
            'personal_statement_rewrite' : {
                'chain' : ChatPromptTemplate.from_template(personal_statement_list_analysis_prompt) | self.llm_editor_model.with_structured_output(PersonalStatementRewrite),
                'provides' : ['analysis','edited_statement']
            },
            'experience_section_analysis' : {
                'chain' : ChatPromptTemplate.from_template(section_experience_analysis_prompt) | self.model.with_structured_output(BulletAnalysis),
                'provides' : 'experience_section_analysis'
            },
            'section_synthesis_analysis': {
                'chain': ChatPromptTemplate.from_template(section_synthesis_analysis_prompt) | self.model.with_structured_output(SectionAnalysis),
                'provides': 'section_synthesis_analysis'
            }
        }
        self.data = {}

    async def analyze_rewrite_personal_statement(self, statements_list = None):
        """Store a rewritten statement grounded in the supplied alternatives and posting."""
        post_txt = self.job_post_analyzer.post_txt
        statements_list = statements_list or self.personal_statements
        if not statements_list: raise Exception("No personal statements provided")
        statements_str = ''.join(['Personal Statement %i'%i+'-'*10+s+'\n\n' for i, s in enumerate(statements_list)])
        try:
            res = await self.chains['personal_statement_rewrite']['chain'].ainvoke({'job_posting_raw' : post_txt ,'personal_statements' : statements_str})
        except Exception as error:
            raise StageFailure("statement_rewrite", "personal_statement", error) from error
        self.data['edited_statement'] = res.edited_statement
        self.data['statement_list_analysis'] = res.analysis

    async def analyze_personal_statement(self):
        """Score the current statement without altering its text."""
        res = await self.chains['personal_statement_analysis']['chain'].ainvoke({
            'job_posting_data' : str(self.job_post_analyzer.data),
            'personal_statement' : self.cv_model.statement
        })
        self.data['personal_statement_analysis'] = res.model_dump()

    async def analyze_job_experience_section(self, concurrency_limit=5, progress_callback=None):
        """Analyze source content without mutating text, comments or selection."""
        if concurrency_limit < 1:
            raise ValueError("concurrency_limit must be positive")
        section = self.source_cv.experience_section
        context = str(self.job_post_analyzer.data)
        raw = self.job_post_analyzer.post_txt
        semaphore = asyncio.Semaphore(concurrency_limit)
        total = sum(len(s.section_item_list) + 1 for s in section.doc_section_items)
        completed_items = 0
        progress_lock = asyncio.Lock()

        async def progress(message):
            nonlocal completed_items
            async with progress_lock:
                completed_items += 1
                if progress_callback:
                    await progress_callback(f"[{completed_items}/{total}] {message}")

        async def assess(scope, context_id, chain_name, inputs):
            async with semaphore:
                try:
                    prompt, schema = ((section_experience_analysis_prompt, BulletAnalysis) if chain_name == 'experience_section_analysis'
                                      else (section_synthesis_analysis_prompt, SectionAnalysis))
                    key = make_cache_key(scope, {'inputs': inputs, 'posting_text': raw,
                        'model': self.model_identity, 'prompt': prompt, 'schema': schema.model_json_schema(),
                        'assessment_schema': Assessment.model_json_schema()})
                    data = self.cache.get(key) if self.model_identity is not None else None
                    if data is None:
                        output = await self.chains[chain_name]['chain'].ainvoke(inputs)
                        data = Assessment.model_validate(output.model_dump()).model_dump()
                        if self.model_identity is not None:
                            self.cache.set(key, data, persist=False)
                    return Assessment.model_validate(data)
                except Exception as error:
                    raise StageFailure(scope, context_id, error) from error

        async def analyze_bullet(bullet):
            assessment = await assess('experience_bullet', bullet.id,
                'experience_section_analysis', {'cv_experience': bullet.text, 'job_posting_data': context})
            await progress(f"{'Analyzed' if assessment else 'Failed'} bullet: {bullet.text[:30]}")
            return AnalyzedBullet(id=bullet.id, text=bullet.text, assessment=assessment)

        async def analyze_role(role):
            items = tuple(await gather_owned(*(analyze_bullet(item) for item in role.section_item_list)))
            details = '\n'.join(f"{item.text}: {item.assessment.experience_relevance_score if item.assessment else 'N/A'}"
                                for item in items)
            content = '\n'.join(item.text for item in items)
            assessment = await assess('experience_section_synthesis', role.id, 'section_synthesis_analysis', {
                'cv_experience': content, 'job_posting_data': context,
                'company': role.company, 'position': role.position, 'item_analyses': details,
            })
            await progress(f"Synthesized section: {role.company}")
            return AnalyzedRole(id=role.id, company=role.company, position=role.position,
                                duration=role.duration, items=items, assessment=assessment)

        self.snapshot = AnalysisSnapshot(roles=tuple(await gather_owned(
            *(analyze_role(role) for role in section.doc_section_items))))
        self.cache.flush()
        self.data['experience_section_analysis'] = self.snapshot.model_dump(mode='json')
        return self.snapshot

    def get_section_aggregate_metrics(self):
        """Compatibility presentation for CLI callers; calculation is pure."""
        if self.snapshot is None:
            raise ValueError("Analyze the CV before calculating metrics")
        records = [{'role_id': role.id, 'section_relevance': role.assessment.experience_relevance_score}
                   for role in self.snapshot.roles if role.assessment]
        return aggregate_metrics(self.snapshot, self.selected_ids), pd.DataFrame(records), []

    def rewrite_reviewed_experience_section(self, min_section_items_keep = 1, max_section_items_keep = 6, min_relevance_score = 3):
        """Select a new document without deleting anything from the analysis."""
        if self.snapshot is None:
            raise ValueError("Analyze the CV before selecting content")
        policy = SelectionPolicy(min_items=min_section_items_keep, max_items=max_section_items_keep,
                                 min_score=min_relevance_score)
        self.selected_ids = frozenset(item_id for role in self.snapshot.roles
                                      for item_id in select_bullets(role.items, policy))
        self.cv_model = self.render_document()
        return self.selected_ids

    def render_document(self, include_scoring_comments=False):
        """Build a rendering adapter from immutable analysis and explicit selection."""
        if self.snapshot is None:
            raise ValueError("Analyze the CV before rendering")
        roles = []
        for role in self.snapshot.roles:
            items = [item for item in role.items if self.selected_ids is None or item.id in self.selected_ids]
            if not items:
                continue
            rendered = DocSectionItem(role.company, role.duration, role.position,
                                      [item.text for item in items], id=role.id,
                                      item_ids=[item.id for item in items])
            if include_scoring_comments:
                def comment(assessment):
                    return score_comment(assessment.experience_relevance_score, assessment.explanation,
                                         assessment.posting_evidence) if assessment else None
                rendered.set_comment(comment(role.assessment))
                for bullet, item in zip(rendered.section_item_list, items):
                    bullet.set_comment(comment(item.assessment))
            roles.append(rendered)
        return FullCVDocument(self.cv_model.statement, DocSection(self.source_cv.experience_section.section_title, roles),
                              cv_template=self.source_cv.cv_template.model_copy(deep=True), content_format=self.source_cv.content_format)
