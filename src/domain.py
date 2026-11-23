"""Canonical CV content and template references, independent of storage/rendering."""

from typing import Any, Literal
import re

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .composition import DocumentComposition

ContentFormat = Literal["latex", "plain_text"]
MANAGED_TEMPLATE_ID_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"
TEMPLATE_REVISION_PATTERN = r"^[0-9a-f]{64}$"


class ExperienceSectionData(BaseModel):
    """One role and its experience bullets."""
    model_config = ConfigDict(extra="forbid")
    company: str
    duration: str
    position: str
    text_items: list[str]


class CVTemplateData(BaseModel):
    """A portable template reference; an explicit path overrides its registry ID."""
    model_config = ConfigDict(extra="forbid")
    template_id: str = "template2"
    template_path: str | None = None
    revision: str | None = Field(default=None, pattern=TEMPLATE_REVISION_PATTERN)
    experience_section_title: str = "Work Experience"

    @model_validator(mode="after")
    def managed_reference(self):
        if self.revision is not None and self.template_path is not None:
            raise ValueError("Managed template revisions cannot also reference a legacy filesystem path")
        if self.revision is not None and not re.fullmatch(MANAGED_TEMPLATE_ID_PATTERN, self.template_id):
            raise ValueError("Invalid managed template ID")
        return self


class MotivationLetterTemplateData(BaseModel):
    """Motivation-letter template reference."""
    model_config = ConfigDict(extra="forbid")
    template_id: str = "default_motivation_letter"
    template_path: str | None = None


class CandidateMetadata(BaseModel):
    """Identity/profile only: CV content is never duplicated under candidate."""
    model_config = ConfigDict(extra="forbid")
    candidate_id: str
    full_name: str = ""
    profile: dict[str, Any] = Field(default_factory=dict)


class CVData(BaseModel):
    """Canonical persisted and editable CV. Paths resolve only when rendering."""
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    candidate: CandidateMetadata
    content_format: ContentFormat = "latex"
    document: DocumentComposition | None = None
    personal_statement: str = ""
    alternative_statements: list[str] = Field(default_factory=list)
    experience_sections: list[ExperienceSectionData] = Field(default_factory=list)
    cv_template: CVTemplateData = Field(default_factory=CVTemplateData)
    motivation_letter_template: MotivationLetterTemplateData = Field(default_factory=MotivationLetterTemplateData)

    @model_validator(mode="after")
    def composition_reference(self):
        if (self.document is None) != (self.cv_template.revision is None):
            raise ValueError("Document composition and a pinned managed-template revision must be supplied together")
        return self
