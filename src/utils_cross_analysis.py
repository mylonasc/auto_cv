import json
import asyncio
import hashlib
import threading
from bs4 import BeautifulSoup
import numpy as np
import os
import pandas as pd
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from langchain_core.prompts import ChatPromptTemplate

class BulletAnalysis(BaseModel):
    experience_relevance_score: float = Field(..., description="Score from 0 to 10 based on relevance to the job posting.")
    explanation: str = Field(..., description="Short explanation (less than 20 words) of why the score was assigned.")
    posting_evidence: str = Field(..., description="Which parts of the job posting analysis are relevant to this bullet.")

class SectionAnalysis(BaseModel):
    experience_relevance_score: float = Field(..., description="Overall score from 0 to 10 for the entire role/experience.")
    explanation: str = Field(..., description="Concise summary justifying the overall score based on the individual items.")
    posting_evidence: str = Field(..., description="Key skills/requirements satisfied by this entire section.")

class PersonalStatementAnalysis(BaseModel):
    experience_relevance_score: float = Field(..., description="Score from 0 to 10 of how well the statement matches the job.")
    explanation: str = Field(..., description="Why this statement is or isn't a good fit.")

class PersonalStatementRewrite(BaseModel):
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

from .models import ModelFactory


class AnalysisResultCache:
    """Simple disk-backed cache for analysis calls."""

    def __init__(self, cache_path: Optional[str] = None):
        self._lock = threading.RLock()
        self.cache_path = cache_path or self._default_cache_path()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _default_cache_path(self) -> str:
        cv_root = os.getenv('CV_CUSTOMIZER_ROOT', os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
        cache_dir = os.path.join(cv_root, 'server_application', 'backend', 'cache')
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, 'analysis_results_cache.json')

    def _load(self):
        with self._lock:
            if not os.path.exists(self.cache_path):
                self._cache = {}
                return
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._cache = data
                    else:
                        self._cache = {}
            except Exception:
                self._cache = {}

    def _save(self):
        with self._lock:
            tmp_path = f"{self.cache_path}.tmp"
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    json.dump(self._cache, f)
                os.replace(tmp_path, self.cache_path)
            except PermissionError:
                pass

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            value = self._cache.get(key)
            return value.copy() if isinstance(value, dict) else None

    def set(self, key: str, value: Dict[str, Any], persist: bool = True):
        with self._lock:
            self._cache[key] = value
            if persist:
                self._save()

    def flush(self):
        self._save()


_analysis_cache = AnalysisResultCache()


def _make_cache_key(scope: str, payload: Dict[str, Any]) -> str:
    key_obj = {
        'scope': scope,
        'payload': payload,
    }
    key_json = json.dumps(key_obj, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(key_json.encode('utf-8')).hexdigest()

def _load_defaults():
    from pathlib import Path
    import yaml
    _here = Path(__file__).resolve().parent.parent
    with open(os.path.join(_here, 'config/llm_defaults.yaml'),'r') as f:
        res = yaml.safe_load(f)
    return res

def _make_default_model():
    default_model_options = _load_defaults()
    return ModelFactory(**default_model_options['cv_cross_analysis_llm_default']).get_llm_model()

class CoverLetterDrafter:
    draft_prompt = """ I want you to draft a short cover letter for a job candidate. I will add a job description, a personal statement from the candidate, and
        the different professional experiences of that candidate.
        Role Description: {job_post_text}
        Personal Statement: {pers_statement}
        Professional Experience: {exp_section}
        Return the cover letter enclosed in <COVERLETTER> tags.
        """
    def __init__(self, cvca, llm_editor_model = None):
        self.cvca = cvca
        self.llm_editor_model = llm_editor_model or cvca.llm_editor_model
        self._debug = {}
        
    async def get_cover_letter_text(self):
        chain = ChatPromptTemplate.from_template(self.draft_prompt) | self.llm_editor_model
        _inputs = {
            "exp_section" : self.cvca.cv_model.experience_section.get_markdown(),
            'pers_statement' : self.cvca.cv_model.statement,
            'job_post_text' : self.cvca.job_post_analyzer.post_txt
        }
        res = await chain.ainvoke(_inputs)
        self._debug['inputs'] = _inputs
        self._debug['raw_llm_output'] = res
        res_text = res.content if hasattr(res, 'content') else str(res)
        soup = BeautifulSoup(res_text, 'html.parser')
        return soup.coverletter.text if soup.coverletter else res_text

class CVCrossAnalyzer:
    def __init__(self, job_post_analyzer, full_cv_document, llm_model = None, llm_editor_model = None, max_section_parse_retries = 3):
        self.cv_model = full_cv_document
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
        post_txt = self.job_post_analyzer.post_txt
        statements_list = statements_list or self.personal_statements
        if not statements_list: raise Exception("No personal statements provided")
        statements_str = ''.join(['Personal Statement %i'%i+'-'*10+s+'\n\n' for i, s in enumerate(statements_list)])
        res = await self.chains['personal_statement_rewrite']['chain'].ainvoke({'job_posting_raw' : post_txt ,'personal_statements' : statements_str})
        self.data['edited_statement'] = res.edited_statement
        self.data['statement_list_analysis'] = res.analysis
        
    async def analyze_personal_statement(self):
        res = await self.chains['personal_statement_analysis']['chain'].ainvoke({
            'job_posting_data' : str(self.job_post_analyzer.data), 
            'personal_statement' : self.cv_model.statement
        })
        self.data['personal_statement_analysis'] = res.model_dump()
        
    async def analyze_job_experience_section(self, concurrency_limit=5, progress_callback=None):
        section = self.cv_model.experience_section
        _job_post_data = str(self.job_post_analyzer.data)
        _job_post_raw = getattr(self.job_post_analyzer, 'post_txt', _job_post_data)
        by_section_item_analysis = {}
        by_section_analysis = {}
        
        semaphore = asyncio.Semaphore(concurrency_limit)
        total_bullets = sum(len(s.section_item_list) for s in section.doc_section_items)
        total_sections = len(section.doc_section_items)
        completed_items = 0
        progress_lock = asyncio.Lock()

        async def update_progress(msg):
            nonlocal completed_items
            async with progress_lock:
                completed_items += 1
                if progress_callback: await progress_callback(f"[{completed_items}/{total_bullets+total_sections}] {msg}")

        async def analyze_bullet(s_item, bullet):
            async with semaphore:
                try:
                    cache_key = _make_cache_key('experience_bullet_v1', {
                        'job_posting_text': _job_post_raw,
                        'cv_experience': bullet.text,
                    })
                    jdata = _analysis_cache.get(cache_key)
                    if jdata is None:
                        res = await self.chains['experience_section_analysis']['chain'].ainvoke({'cv_experience' : bullet.text, 'job_posting_data' : _job_post_data})
                        jdata = res.model_dump()
                        _analysis_cache.set(cache_key, jdata, persist=False)
                    bullet.set_comment(str(jdata).replace(' & ',' and '))
                    await update_progress(f"Analyzed bullet: {bullet.text[:30]}...")
                    return s_item, bullet, jdata
                except Exception as e:
                    await update_progress(f"Failed bullet: {bullet.text[:30]}...")
                    return None

        bullet_tasks = [analyze_bullet(s, i) for s in section.doc_section_items for i in s.section_item_list]
        for res in await asyncio.gather(*bullet_tasks):
            if res:
                s_item, bullet, jdata = res
                if s_item not in by_section_item_analysis: by_section_item_analysis[s_item] = {}
                by_section_item_analysis[s_item][bullet] = jdata

        async def synthesize_section(s_item):
            async with semaphore:
                bullet_analyses = ""
                for i, bullet in enumerate(s_item.section_item_list):
                    analysis = by_section_item_analysis.get(s_item, {}).get(bullet, {})
                    bullet_analyses += f"Bullet {i+1}: {bullet.text}\n Score: {analysis.get('experience_relevance_score', 'N/A')}\n\n"
                try:
                    cv_experience = s_item.get_markdown()
                    cache_key = _make_cache_key('experience_section_synthesis_v1', {
                        'job_posting_text': _job_post_raw,
                        'company': s_item.company,
                        'position': s_item.position,
                        'cv_experience': cv_experience,
                        'item_analyses': bullet_analyses,
                    })
                    jdata = _analysis_cache.get(cache_key)
                    if jdata is None:
                        res = await self.chains['section_synthesis_analysis']['chain'].ainvoke({
                            'cv_experience' : cv_experience, 'job_posting_data' : _job_post_data,
                            'company': s_item.company, 'position': s_item.position, 'item_analyses': bullet_analyses
                        })
                        jdata = res.model_dump()
                        _analysis_cache.set(cache_key, jdata, persist=False)
                    s_item.set_comment(str(jdata))
                    await update_progress(f"Synthesized section: {s_item.company}")
                    return s_item, jdata
                except Exception as e:
                    return None

        section_tasks = [synthesize_section(s) for s in section.doc_section_items]
        for res in await asyncio.gather(*section_tasks):
            if res: by_section_analysis[res[0]] = res[1]

        _analysis_cache.flush()

        self.data['experience_section_analysis'] = {'full_section_analysis' : by_section_analysis,'by_section_item_analysis' : by_section_item_analysis}
        return self.data['experience_section_analysis']
        
    def get_section_aggregate_metrics(self):
        section_scoring = []
        section_weights = []
        for section, s in self.data['experience_section_analysis']['full_section_analysis'].items():
            weight = len(section.get_markdown().split(' '))
            score = s['experience_relevance_score']
            section_scoring.append(score)
            section_weights.append(weight)
        
        all_dat = pd.DataFrame({'section_relevance': section_scoring, 'section_weight': section_weights})
        mean_section_relevance = np.mean(all_dat['section_relevance'])
        weighted_mean_section_relevance = np.sum(all_dat['section_relevance'] * all_dat['section_weight'] / np.sum(all_dat['section_weight']))
        _res  = {
            'conciseness_relevance_metric' : weighted_mean_section_relevance - mean_section_relevance, 
            'mean_section_relevance' : mean_section_relevance,
            'weighted_mean_section_relevance' : weighted_mean_section_relevance
        }
        return _res, all_dat, []
    
    def rewrite_reviewed_experience_section(self, min_section_items_keep = 1, max_section_items_keep = 6, min_relevance_score = 3):
        bsa = self.data['experience_section_analysis']['by_section_item_analysis']
        fsa = self.data['experience_section_analysis']['full_section_analysis']
        for k in fsa.keys():
            temp_list = sorted(k.section_item_list, key = lambda x : -bsa[k].get(x, {}).get('experience_relevance_score', 0))
            new_list = []
            for item in temp_list:
                score = bsa[k].get(item, {}).get('experience_relevance_score', 0)
                if len(new_list) < min_section_items_keep or (len(new_list) < max_section_items_keep and score >= min_relevance_score):
                    new_list.append(item)
            k.section_item_list = new_list
