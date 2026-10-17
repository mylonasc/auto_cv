"""Canonical CV content and template references, independent of storage/rendering."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


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
    template_id: str = "default_cv"
    template_path: str | None = None
    experience_section_title: str = "Work Experience"


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
    personal_statement: str = ""
    alternative_statements: list[str] = Field(default_factory=list)
    experience_sections: list[ExperienceSectionData] = Field(default_factory=list)
    cv_template: CVTemplateData = Field(default_factory=CVTemplateData)
    motivation_letter_template: MotivationLetterTemplateData = Field(default_factory=MotivationLetterTemplateData)
