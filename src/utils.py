"""Legacy import adapter. New code uses documents, posting, cover_letter or rendering.

These are aliases to the production implementations, not alternate workflows or
content stores. Private monkeypatch targets moved to src.rendering.
"""

from .documents import DocSection, DocSectionItem, SectionListItem, FullCVDocument
from .posting import BasicAnalysis, IndustryPositionAnalysis, JobPostAnalysis, analyses_prompts
from .cover_letter import CoverLetterModel
from .rendering import latex_to_pdf as _latex_to_pdf, latex_comment as _latex_comment
