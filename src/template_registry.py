"""Template registry helpers for CV and motivation letter templates."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from .domain import CVData


def _repo_root() -> str:
    return os.getenv("CV_CUSTOMIZER_ROOT", str(Path(__file__).resolve().parent.parent))


def _registry_path() -> str:
    return os.path.join(_repo_root(), "config", "templates.json")


def load_template_registry() -> Dict[str, Dict[str, str]]:
    """Load template registry definitions from config/templates.json."""
    path = _registry_path()
    if not os.path.exists(path):
        return {"cv_templates": {}, "motivation_letter_templates": {}}
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        "cv_templates": data.get("cv_templates", {}),
        "motivation_letter_templates": data.get("motivation_letter_templates", {}),
    }


def resolve_template_path(template_type: str, template_id: str, explicit_path: str | None = None) -> str:
    """Resolve a template path using explicit path or registry fallback."""
    path: str | None = None
    if explicit_path:
        path = explicit_path
    else:
        registry = load_template_registry()
        group = registry.get(template_type, {})
        if template_id in group:
            path = group[template_id]
        elif group:
            path = next(iter(group.values()))

    if not path:
        raise KeyError(f"No templates configured for '{template_type}'")

    if not os.path.isabs(path):
        path = os.path.join(_repo_root(), path)

    return path


def resolve_cv_templates(
    cv: CVData,
    *,
    cv_template_id: str | None = None,
    cv_template_path: str | None = None,
    motivation_template_id: str | None = None,
    motivation_template_path: str | None = None,
) -> CVData:
    """Resolve a render-time copy without changing persisted template choices.

    Explicit CLI paths win, then explicit CLI IDs, then stored paths/IDs. An ID
    override intentionally does not reuse a path belonging to the old template.
    """
    result = cv.model_copy(deep=True)
    for field, group, template_id, template_path in (
        ("cv_template", "cv_templates", cv_template_id, cv_template_path),
        ("motivation_letter_template", "motivation_letter_templates",
         motivation_template_id, motivation_template_path),
    ):
        template = getattr(result, field)
        explicit_path = template_path
        if explicit_path is None and template_id is None:
            explicit_path = template.template_path
        template.template_id = template_id or template.template_id
        template.template_path = resolve_template_path(group, template.template_id, explicit_path)
    return result
