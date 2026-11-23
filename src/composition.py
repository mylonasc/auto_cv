"""TRF-01 / RFK-04: ordered CV content, independent of templates and analysis.

Statement/experience sections are bindings, not competing writable content.
Raw sections deliberately own complete LaTeX blocks; their title is an editor
label, while structured section titles are rendered by their template fragment.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")]


class CompositionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class SectionBase(CompositionModel):
    id: Identifier
    title: str = Field(min_length=1, max_length=200)
    enabled: bool = True
    page_break_before: bool = False


class StatementSection(SectionBase):
    kind: Literal["statement"]


class ExperienceSection(SectionBase):
    kind: Literal["experience"]


class ProjectEntry(CompositionModel):
    id: Identifier
    name: str = Field(min_length=1, max_length=300)
    description: str = Field(default="", max_length=10000)
    technologies: list[Annotated[str, Field(max_length=200)]] = Field(default_factory=list, max_length=100)
    url: str = Field(default="", max_length=2000)
    bullets: list[Annotated[str, Field(max_length=10000)]] = Field(default_factory=list, max_length=100)
    enabled: bool = True


class EntryListSection(SectionBase):
    kind: Literal["entries"]
    entries: list[ProjectEntry] = Field(default_factory=list, max_length=100)


class PublicationEntry(CompositionModel):
    id: Identifier
    authors: str = Field(default="", max_length=3000)
    title: str = Field(min_length=1, max_length=3000)
    venue: str = Field(default="", max_length=1000)
    year: str = Field(default="", max_length=50)
    url: str = Field(default="", max_length=2000)
    enabled: bool = True


class PublicationListSection(SectionBase):
    kind: Literal["publications"]
    entries: list[PublicationEntry] = Field(default_factory=list, max_length=200)


class LatexSection(SectionBase):
    kind: Literal["latex"]
    latex: str = Field(default="", max_length=262144)


DocumentSection = Annotated[
    StatementSection | ExperienceSection | EntryListSection | PublicationListSection | LatexSection,
    Field(discriminator="kind"),
]


class DocumentComposition(CompositionModel):
    format_version: Literal[1] = 1
    header_latex: str = Field(default="", max_length=65536)
    sections: list[DocumentSection] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def coherent_content(self):
        ids = []
        bindings = []
        for section in self.sections:
            ids.append(section.id)
            if isinstance(section, (StatementSection, ExperienceSection)):
                bindings.append(section.kind)
            if isinstance(section, (EntryListSection, PublicationListSection)):
                ids.extend(entry.id for entry in section.entries)
        if len(ids) != len(set(ids)):
            raise ValueError("Composition section and entry IDs must be globally unique")
        if len(bindings) != len(set(bindings)):
            raise ValueError("Statement/experience may each be bound at most once, including disabled sections")
        if len(self.model_dump_json().encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("Document composition exceeds the 2 MiB limit")
        return self
