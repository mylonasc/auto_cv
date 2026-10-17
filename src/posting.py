"""Structured posting extraction and explicitly labeled evidence-only fallback."""

import re
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate
from .outcomes import StageFailure, gather_owned


class BasicAnalysis(BaseModel):
    skills: str = Field(..., description="Semicolon separated list of required skills.")
    qualifications: str = Field(..., description="Semicolon separated list of required qualifications.")
    preferred_qualifications: str | None = Field(None, description="Semicolon separated list of preferred qualifications.")


class IndustryPositionAnalysis(BaseModel):
    company_name: str | None = Field(None, description="Name of the company.")
    industry: str | None = Field(None, description="Industry the company operates in.")
    job_title: str = Field(..., description="Title of the position.")
    business_skills: float = Field(..., description="Business skills required (0-10).")
    hands_on_skills: float = Field(..., description="Hands-on skills required (0-10).")


analyses_prompts = [
    {'prompt_txt': 'Analyze this job posting for required skills and qualifications: {job_posting_text}',
     'prompt_provides': 'basic_analysis', 'schema': BasicAnalysis},
    {'prompt_txt': 'Analyze this job posting for company, industry, title and skill balance: {job_posting_text}',
     'prompt_provides': 'industry_and_position_analysis', 'schema': IndustryPositionAnalysis},
]


class JobPostAnalysis:
    """Analyze explicit text (or a legacy text-file input) without import-time calls."""
    def __init__(self, post_txt_file=None, analysis_prompts=analyses_prompts, llm_model=None, *, post_text=None):
        self.post_txt_file = post_txt_file
        if post_text is not None:
            self.post_txt = post_text
        elif post_txt_file is not None:
            with open(post_txt_file, encoding='utf-8') as source:
                self.post_txt = source.read()
        else:
            raise ValueError('Provide posting text or a posting file')
        if llm_model is None:
            from .config import BackendConfig, build_model
            llm_model = build_model(BackendConfig().analysis_model)
        self.model = llm_model
        self.chains = [{'chain': ChatPromptTemplate.from_template(item['prompt_txt']) |
                        self.model.with_structured_output(item['schema']), 'provides': item['prompt_provides']}
                       for item in analysis_prompts]
        self.data = {}

    async def analyze(self):
        async def invoke(chain):
            try:
                return await chain['chain'].ainvoke({'job_posting_text': self.post_txt})
            except Exception as error:
                raise StageFailure('posting_analysis', chain['provides'], error) from error
        results = await gather_owned(*(invoke(chain) for chain in self.chains))
        for chain, result in zip(self.chains, results):
            self.data[chain['provides']] = result.model_dump()
        self._postprocess_analysis()

    def _postprocess_analysis(self):
        basic = self.data.get('basic_analysis') or {}
        if not isinstance(basic, dict):
            basic = {}
        provenance = {}
        normalized = {}
        for field, fallback in (('skills', self._fallback_extract_skills), ('qualifications', self._fallback_extract_qualifications)):
            text = str(basic.get(field) or '').strip()
            if text.lower() in {'', 'required skills', 'skills', 'required qualifications', 'qualifications', 'none', 'n/a'}:
                text = fallback()
                provenance[field] = {'status': 'fallback', 'method': 'posting_heuristic_v1',
                                     'reason': f'Model returned empty/placeholder {field}'}
            else:
                provenance[field] = {'status': 'success', 'method': 'model'}
            normalized[field] = text
        preferred = basic.get('preferred_qualifications')
        normalized['preferred_qualifications'] = None if isinstance(preferred, str) and preferred.strip().lower() in {'', 'none', 'n/a'} else preferred
        self.data['basic_analysis'], self.data['provenance'] = normalized, provenance

    def _extract_section_lines(self, headers):
        lines, capture = [], False
        for raw in self.post_txt.splitlines():
            line = raw.strip()
            if any(header in line.lower() for header in headers) and len(line) <= 90:
                capture = True
                continue
            if capture and not line:
                capture = False
                continue
            if capture:
                lines.append(line)
        return lines

    def _fallback_extract_skills(self):
        tokens = ['python', 'pytorch', 'tensorflow', 'machine learning', 'deep learning',
                  'nlp', 'llm', 'genai', 'rag', 'docker', 'kubernetes', 'sql', 'aws', 'gcp', 'azure',
                  'c++', 'java', 'javascript', 'graph neural networks', 'gnn', 'data science']
        candidates = [token for token in tokens if token in self.post_txt.lower()]
        for line in self._extract_section_lines(['skills', 'requirements', 'qualifications']):
            text = line.strip(' -•\t').strip()
            if 2 <= len(text) <= 90:
                candidates.append(text)
        seen, unique = set(), []
        for text in candidates:
            if text.lower() not in seen:
                seen.add(text.lower())
                unique.append(text)
        return '; '.join(unique[:12]) if unique else 'Not identified in posting'

    def _fallback_extract_qualifications(self):
        items = []
        for line in self._extract_section_lines(['requirements', 'qualifications']):
            text = line.strip(' -•\t').strip()
            if 8 <= len(text) <= 220:
                items.append(text)
        if not items:
            for sentence in re.split(r'(?<=[.!?])\s+', self.post_txt):
                text = sentence.strip()
                if any(token in text.lower() for token in ['experience', 'degree', 'years', 'required']):
                    items.append(text)
                if len(items) >= 6:
                    break
        return '; '.join(items[:8]) if items else 'Not identified in posting'
