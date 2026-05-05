"""
API routes for CV data management with version support.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import shutil
from core.paths import CV_DATA_DIR, ensure_data_dirs

router = APIRouter(prefix="/v1/cv-data", tags=["CV Data"])

ensure_data_dirs()
CV_DATA_BASE_DIR = CV_DATA_DIR

def ensure_candidate_dir(candidate: str):
    candidate_dir = os.path.join(CV_DATA_BASE_DIR, candidate)
    if not os.path.exists(candidate_dir):
        os.makedirs(candidate_dir, exist_ok=True)
        
        # Migration: if old style file exists, move it to master.json
        old_style_path = os.path.join(CV_DATA_BASE_DIR, f'{candidate}_cv_data.json')
        if os.path.exists(old_style_path):
            shutil.copy(old_style_path, os.path.join(candidate_dir, 'master.json'))
    return candidate_dir

def get_cv_version_path(candidate: str, version_id: str):
    candidate_dir = ensure_candidate_dir(candidate)
    # Ensure version_id is safe and ends with .json
    safe_version_id = os.path.basename(version_id)
    if not safe_version_id.endswith('.json'):
        safe_version_id += '.json'
    return os.path.join(candidate_dir, safe_version_id)

class ExperienceSection(BaseModel):
    company: str
    duration: str
    position: str
    text_items: List[str]

class CVData(BaseModel):
    candidate: Optional[Dict[str, Any]] = None
    cv_template: Optional[Dict[str, Any]] = None
    motivation_letter_template: Optional[Dict[str, Any]] = None
    personal_statement: str = ""
    alternative_statements: List[str] = Field(default_factory=list)
    experience_sections: List[ExperienceSection] = Field(default_factory=list)


def _normalize_cv_payload(data: Dict[str, Any], candidate: str) -> Dict[str, Any]:
    payload = dict(data)
    candidate_obj = payload.get("candidate") or {}
    if not isinstance(candidate_obj, dict):
        candidate_obj = {}

    candidate_obj.setdefault("candidate_id", candidate)
    candidate_obj.setdefault("full_name", payload.get("full_name", ""))
    candidate_obj.setdefault("profile", payload.get("profile", {}))
    candidate_obj.setdefault("personal_statement", payload.get("personal_statement", ""))
    candidate_obj.setdefault("alternative_statements", payload.get("alternative_statements", []))
    candidate_obj.setdefault("experience_sections", payload.get("experience_sections", []))
    payload["candidate"] = candidate_obj

    cv_template = payload.get("cv_template") or {}
    if not isinstance(cv_template, dict):
        cv_template = {}
    payload["cv_template"] = {
        "template_id": "default_cv",
        "template_path": "assets/latex_cv_template_v0.tex",
        "experience_section_title": "Work Experience",
        **cv_template,
    }

    motivation_template = payload.get("motivation_letter_template") or {}
    if not isinstance(motivation_template, dict):
        motivation_template = {}
    payload["motivation_letter_template"] = {
        "template_id": "default_motivation_letter",
        "template_path": "assets/cover_letter/CoverLetter_Template.tex",
        **motivation_template,
    }

    # Backward compatibility fields expected by current frontend
    payload["personal_statement"] = candidate_obj.get("personal_statement", "")
    payload["alternative_statements"] = candidate_obj.get("alternative_statements", [])
    payload["experience_sections"] = candidate_obj.get("experience_sections", [])
    return payload

class CVVersionInfo(BaseModel):
    id: str
    name: str
    last_modified: float

@router.get("/{candidate}/versions", response_model=List[CVVersionInfo])
async def list_cv_versions(candidate: str = "charilaos_mylonas"):
    """List all available CV versions for a candidate."""
    candidate_dir = ensure_candidate_dir(candidate)
    versions = []
    for filename in os.listdir(candidate_dir):
        if filename.endswith(".json"):
            path = os.path.join(candidate_dir, filename)
            stat = os.stat(path)
            versions.append(CVVersionInfo(
                id=filename[:-5],
                name=filename[:-5].replace("_", " ").title(),
                last_modified=os.path.getmtime(path)
            ))
    return sorted(versions, key=lambda x: x.last_modified, reverse=True)

@router.get("/{candidate}/versions/{version_id}", response_model=CVData)
async def get_cv_version(version_id: str, candidate: str = "charilaos_mylonas"):
    """Get a specific CV version."""
    path = get_cv_version_path(candidate, version_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"CV version '{version_id}' not found")
    
    with open(path, 'r') as f:
        data = json.load(f)
    return _normalize_cv_payload(data, candidate)

@router.post("/{candidate}/versions/{version_id}", response_model=CVData)
async def create_cv_version(version_id: str, data: CVData, candidate: str = "charilaos_mylonas"):
    """Create a new CV version."""
    path = get_cv_version_path(candidate, version_id)
    if os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"CV version '{version_id}' already exists")
        
    payload = _normalize_cv_payload(data.model_dump(), candidate)
    with open(path, 'w') as f:
        json.dump(payload, f, indent=4)
    return payload

@router.put("/{candidate}/versions/{version_id}", response_model=CVData)
async def update_cv_version(version_id: str, data: CVData, candidate: str = "charilaos_mylonas"):
    """Update an existing CV version."""
    path = get_cv_version_path(candidate, version_id)
    
    # Backup if exists
    if os.path.exists(path):
        shutil.copy(path, path + ".bak")
        
    payload = _normalize_cv_payload(data.model_dump(), candidate)
    with open(path, 'w') as f:
        json.dump(payload, f, indent=4)
    return payload

@router.delete("/{candidate}/versions/{version_id}")
async def delete_cv_version(version_id: str, candidate: str = "charilaos_mylonas"):
    """Delete a CV version."""
    path = get_cv_version_path(candidate, version_id)
    if version_id == "master":
        raise HTTPException(status_code=400, detail="Cannot delete the master version")
    
    if os.path.exists(path):
        os.remove(path)
        return {"status": "success", "message": f"Version '{version_id}' deleted"}
    else:
        raise HTTPException(status_code=404, detail=f"Version '{version_id}' not found")

# Legacy compatibility endpoints
@router.get("/{candidate}", response_model=CVData)
async def get_cv_data_legacy(candidate: str = "charilaos_mylonas"):
    """Get the master CV data (legacy endpoint)."""
    return await get_cv_version("master", candidate)

@router.put("/{candidate}", response_model=CVData)
async def update_cv_data_legacy(data: CVData, candidate: str = "charilaos_mylonas"):
    """Update the master CV data (legacy endpoint)."""
    return await update_cv_version("master", data, candidate)
