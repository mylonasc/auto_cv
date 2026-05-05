"""Domain data objects for candidate and templates."""

from __future__ import annotations

from typing import List, Dict, Any
from pydantic import BaseModel, Field
import os


class ExperienceSectionData(BaseModel):
    company: str
    duration: str
    position: str
    text_items: List[str]


class CandidateData(BaseModel):
    candidate_id: str = "charilaos_mylonas"
    full_name: str = ""
    profile: Dict[str, Any] = Field(default_factory=dict)
    personal_statement: str = ""
    alternative_statements: List[str] = Field(default_factory=list)
    experience_sections: List[ExperienceSectionData] = Field(default_factory=list)


class CVTemplateData(BaseModel):
    template_id: str = "default_cv"
    template_path: str
    experience_section_title: str = "Work Experience"


class MotivationLetterTemplateData(BaseModel):
    template_id: str = "default_motivation_letter"
    template_path: str


class CandidateBundle(BaseModel):
    candidate: CandidateData
    cv_template: CVTemplateData
    motivation_letter_template: MotivationLetterTemplateData


def candidate_bundle_from_legacy(data: Dict[str, Any], candidate_id: str, cv_template_path: str, motivation_template_path: str) -> CandidateBundle:
    cv_root = os.getenv("CV_CUSTOMIZER_ROOT", os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    if not os.path.isabs(cv_template_path):
        cv_template_path = os.path.join(cv_root, cv_template_path)
    if not os.path.isabs(motivation_template_path):
        motivation_template_path = os.path.join(cv_root, motivation_template_path)
    candidate = CandidateData(
        candidate_id=candidate_id,
        full_name=data.get("full_name", ""),
        profile=data.get("profile", {}),
        personal_statement=data.get("personal_statement", ""),
        alternative_statements=data.get("alternative_statements", []),
        experience_sections=[ExperienceSectionData(**item) for item in data.get("experience_sections", [])],
    )
    cv_template = CVTemplateData(template_path=cv_template_path)
    motivation = MotivationLetterTemplateData(template_path=motivation_template_path)
    return CandidateBundle(candidate=candidate, cv_template=cv_template, motivation_letter_template=motivation)
