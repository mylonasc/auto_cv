"""Domain data objects for candidate and templates."""

from __future__ import annotations

from typing import List, Dict, Any, Union
from pydantic import BaseModel, Field
import os
from .template_registry import resolve_template_path


class ExperienceSectionData(BaseModel):
    """ExperienceSectionData model."""
    company: str
    duration: str
    position: str
    text_items: List[str]


class CandidateData(BaseModel):
    """CandidateData model."""
    candidate_id: str = "charilaos_mylonas"
    full_name: str = ""
    profile: Dict[str, Any] = Field(default_factory=dict)
    personal_statement: str = ""
    alternative_statements: List[str] = Field(default_factory=list)
    experience_sections: List[ExperienceSectionData] = Field(default_factory=list)


class CVTemplateData(BaseModel):
    """CVTemplateData model."""
    template_id: str = "default_cv"
    template_path: str
    experience_section_title: str = "Work Experience"


class MotivationLetterTemplateData(BaseModel):
    """MotivationLetterTemplateData model."""
    template_id: str = "default_motivation_letter"
    template_path: str


class CandidateBundle(BaseModel):
    """CandidateBundle model."""
    candidate: CandidateData
    cv_template: CVTemplateData
    motivation_letter_template: MotivationLetterTemplateData


def candidate_bundle_from_legacy(
    data: Union[Dict[str, Any], List[Dict[str, Any]]],
    candidate_id: str,
    cv_template_id: str = "default_cv",
    cv_template_path: str | None = None,
    motivation_template_id: str = "default_motivation_letter",
    motivation_template_path: str | None = None,
) -> CandidateBundle:
    """Build a candidate/template bundle from legacy payload shapes.

    Args:
        data: Candidate payload as either a full mapping or a plain list of
            experience section entries.
        candidate_id: Candidate identifier.
        cv_template_id: CV template identifier.
        cv_template_path: CV template file path (relative or absolute).
        motivation_template_id: Motivation letter template identifier.
        motivation_template_path: Motivation letter template path (relative or
            absolute).

    Returns:
        CandidateBundle: Normalized bundle with candidate and template objects.
    """
    cv_root = os.getenv("CV_CUSTOMIZER_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    cv_template_path = resolve_template_path("cv_templates", cv_template_id, cv_template_path)
    motivation_template_path = resolve_template_path(
        "motivation_letter_templates",
        motivation_template_id,
        motivation_template_path,
    )

    if not os.path.isabs(cv_template_path):
        cv_template_path = os.path.join(cv_root, cv_template_path)
    if not os.path.isabs(motivation_template_path):
        motivation_template_path = os.path.join(cv_root, motivation_template_path)

    if isinstance(data, list):
        data = {
            "experience_sections": data,
            "personal_statement": "",
            "alternative_statements": [],
            "profile": {},
            "full_name": "",
        }
    elif not isinstance(data, dict):
        raise TypeError("candidate data must be a dict or a list of experience sections")

    candidate = CandidateData(
        candidate_id=candidate_id,
        full_name=data.get("full_name", ""),
        profile=data.get("profile", {}),
        personal_statement=data.get("personal_statement", ""),
        alternative_statements=data.get("alternative_statements", []),
        experience_sections=[ExperienceSectionData(**item) for item in data.get("experience_sections", [])],
    )
    cv_template = CVTemplateData(template_id=cv_template_id, template_path=cv_template_path)
    motivation = MotivationLetterTemplateData(template_id=motivation_template_id, template_path=motivation_template_path)
    return CandidateBundle(candidate=candidate, cv_template=cv_template, motivation_letter_template=motivation)
