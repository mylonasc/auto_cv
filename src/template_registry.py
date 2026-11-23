"""Validated template references and explicit legacy-registry adaptation.

Paths remain checkout-relative in storage and the public catalog. Resolving a
reference never changes that reference and never substitutes a different ID.
"""

from pathlib import Path
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .domain import CVData
from .paths import project_root

TemplateGroup = Literal["cv_templates", "motivation_letter_templates"]


class TemplateError(ValueError):
    """Safe, actionable template-authoring error, never a provider error."""


class LatexLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")
    section: str = "assets/templates/resume/section.tex"
    role: str = "assets/templates/resume/role.tex"
    bullet: str = "assets/templates/resume/bullet.tex"
    comment: str = "assets/templates/resume/comment.tex"


class TemplateDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1)
    # Destination paths are relative to compilation scratch, not the caller CWD.
    resources: dict[str, str] = Field(default_factory=dict)
    layout: LatexLayout | None = None


class TemplateRegistryResponse(BaseModel):
    """Stable public path catalog; rendering details stay owned by the backend."""
    model_config = ConfigDict(extra="forbid")
    cv_templates: dict[str, str] = Field(default_factory=dict)
    motivation_letter_templates: dict[str, str] = Field(default_factory=dict)


def absolute_path(path: str) -> Path:
    value = Path(path).expanduser()
    return value if value.is_absolute() else project_root() / value


def legacy_definition(group: TemplateGroup, path: str) -> TemplateDefinition:
    """Existing string entries/custom paths retain the historical resume contract."""
    return TemplateDefinition(path=path, layout=LatexLayout() if group == "cv_templates" else None,
        resources={name: f"assets/{name}" for name in ("resume.cls", "resume_v2.cls")}
        if group == "cv_templates" else {})


def load_template_definitions(*, root: Path | None = None) -> dict[str, dict[str, TemplateDefinition]]:
    path = (root if root is not None else project_root()) / "config/templates.json"
    if not path.exists():
        return {"cv_templates": {}, "motivation_letter_templates": {}}
    return parse_template_definitions(json.loads(path.read_text(encoding="utf-8")))


def parse_template_definitions(raw) -> dict[str, dict[str, TemplateDefinition]]:
    """Adapt one captured registry value without filesystem access."""
    if not isinstance(raw, dict) or set(raw) - {"cv_templates", "motivation_letter_templates"}:
        raise ValueError("Invalid template registry groups")
    result = {}
    for group in ("cv_templates", "motivation_letter_templates"):
        entries = raw.get(group, {})
        if not isinstance(entries, dict):
            raise ValueError(f"Invalid template registry group: {group}")
        result[group] = {id: legacy_definition(group, entry) if isinstance(entry, str)
                         else TemplateDefinition.model_validate(entry) for id, entry in entries.items()}
    return result


def load_template_registry() -> TemplateRegistryResponse:
    definitions = load_template_definitions()
    return TemplateRegistryResponse(**{group: {id: entry.path for id, entry in entries.items()}
                                      for group, entries in definitions.items()})


def resolve_template_definition(group: TemplateGroup, template_id: str,
                                explicit_path: str | None = None) -> TemplateDefinition:
    entries = load_template_definitions()[group]
    if explicit_path:
        # Registry choices supplied by older clients still use their declared resources.
        matches = {id: entry for id, entry in entries.items()
                   if absolute_path(entry.path).resolve() == absolute_path(explicit_path).resolve()}
        if template_id in matches:
            return matches[template_id]
        if len(matches) == 1:
            return next(iter(matches.values()))
        if len(matches) > 1:
            raise TemplateError(f"Multiple templates use {explicit_path!r}; specify their matching template ID")
        # Custom paths may opt into a layout/resource contract with a sidecar manifest.
        sidecar = Path(str(absolute_path(explicit_path)) + ".json")
        if sidecar.exists():
            return TemplateDefinition.model_validate({**json.loads(sidecar.read_text(encoding="utf-8")),
                                                       "path": explicit_path})
        return legacy_definition(group, explicit_path)
    if template_id not in entries:
        raise TemplateError(f"Unknown {group} template ID: {template_id!r}")
    return entries[template_id]


def resolve_template_path(template_type: TemplateGroup, template_id: str,
                          explicit_path: str | None = None) -> str:
    entry = resolve_template_definition(template_type, template_id, explicit_path)
    path = absolute_path(entry.path)
    if not path.is_file():
        raise TemplateError(f"Template {template_id!r} entry file does not exist: {path}")
    return str(path)


def apply_template_overrides(cv: CVData, *, cv_template_id=None, cv_template_path=None,
                             motivation_template_id=None, motivation_template_path=None) -> CVData:
    """Apply choices without filesystem access; analysis does not require templates."""
    result = cv.model_copy(deep=True)
    for field, id, path in (
        ("cv_template", cv_template_id, cv_template_path),
        ("motivation_letter_template", motivation_template_id, motivation_template_path),
    ):
        template = getattr(result, field)
        if path is None and id is None:
            path = template.template_path
        if id is not None:
            template.template_id = id
        template.template_path = path
    return result


def resolve_cv_templates(cv: CVData, **overrides) -> CVData:
    """Explicit render-time compatibility helper; never use this to prepare analysis."""
    result = apply_template_overrides(cv, **overrides)
    for field, group in (("cv_template", "cv_templates"), ("motivation_letter_template", "motivation_letter_templates")):
        template = getattr(result, field)
        template.template_path = resolve_template_path(group, template.template_id, template.template_path)
    return result
