"""TRF-03: explicit authoring contracts; no filesystem paths from clients."""

from pydantic import BaseModel, ConfigDict, Field
from src.domain import CVData
from src.template_package import TemplatePackage, TemplateID, RevisionID


class StudioModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class StudioImportRequest(StudioModel):
    cv: CVData
    template_id: TemplateID
    name: str = Field(min_length=1, max_length=200)
    source_template: str | None = Field(default=None, max_length=200)


class StudioDraft(StudioModel):
    cv: CVData
    package: TemplatePackage


class StudioSaveRequest(StudioModel):
    package: TemplatePackage
    expected_revision: RevisionID | None


class StudioPreviewRequest(StudioDraft):
    """A CV/package pair; its effective revision is bound without saving."""


class StudioPreviewError(StudioModel):
    detail: str
    diagnostics: str = Field(default='', max_length=8192)


class OverfullWarning(StudioModel):
    kind: str
    amount_pt: float
    start_line: int
    end_line: int
    excerpt: str = Field(default='', max_length=200)


class OverlapSpot(StudioModel):
    page: int
    first: str = Field(default='', max_length=80)
    second: str = Field(default='', max_length=80)
    area: float


class OutsideWord(StudioModel):
    page: int
    text: str = Field(default='', max_length=80)
    edge: str
    amount_pt: float


class StudioPreviewReport(StudioModel):
    input_id: str
    pages: int
    words: int
    overfulls: list[OverfullWarning] = Field(default_factory=list)
    overfull_count: int = 0
    overlaps: list[OverlapSpot] = Field(default_factory=list)
    outside_page: list[OutsideWord] = Field(default_factory=list)
    missing_glyphs: list[str] = Field(default_factory=list)
    omitted: dict[str, int] = Field(default_factory=dict)
