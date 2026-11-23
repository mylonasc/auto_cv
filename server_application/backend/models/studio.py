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


class StudioDraft(StudioModel):
    cv: CVData
    package: TemplatePackage


class StudioSaveRequest(StudioModel):
    package: TemplatePackage
    expected_revision: RevisionID | None
