"""Legacy imports alias canonical scoring, cache and cover-letter implementations."""

from .scoring import (
    CVCrossAnalyzer, BulletAnalysis, SectionAnalysis, PersonalStatementAnalysis,
    PersonalStatementRewrite, personal_statement_analysis_prompt,
    personal_statement_list_analysis_prompt, section_experience_analysis_prompt,
    section_synthesis_analysis_prompt,
)
from .cache import AnalysisResultCache, make_cache_key as _make_cache_key
from .cover_letter import CoverLetterDrafter
