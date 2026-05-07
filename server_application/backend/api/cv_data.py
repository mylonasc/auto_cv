"""
API routes for CV data management with version support.
"""
import logging
import sys
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
import os
import json
import shutil
from core.paths import CV_DATA_DIR, ensure_data_dirs
from src.template_registry import load_template_registry

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter(prefix="/v1/cv-data", tags=["CV Data"])

ensure_data_dirs()
CV_DATA_BASE_DIR = CV_DATA_DIR

def ensure_candidate_dir(candidate: str):
    """Ensure candidate dir."""
    candidate_dir = os.path.join(CV_DATA_BASE_DIR, candidate)
    if not os.path.exists(candidate_dir):
        os.makedirs(candidate_dir, exist_ok=True)
        
        # Migration: if old style file exists, move it to master.json
        old_style_path = os.path.join(CV_DATA_BASE_DIR, f'{candidate}_cv_data.json')
        if os.path.exists(old_style_path):
            shutil.copy(old_style_path, os.path.join(candidate_dir, 'master.json'))
    return candidate_dir

def get_cv_version_path(candidate: str, version_id: str):
    """Get cv version path."""
    candidate_dir = ensure_candidate_dir(candidate)
    # Ensure version_id is safe and ends with .json
    safe_version_id = os.path.basename(version_id)
    if not safe_version_id.endswith('.json'):
        safe_version_id += '.json'
    return os.path.join(candidate_dir, safe_version_id)

def _normalize_cv_payload(data: Dict[str, Any], candidate: str) -> Dict[str, Any]:
    """ normalize cv payload."""
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

class ExperienceSection(BaseModel):
    """ExperienceSection model."""
    company: str
    duration: str
    position: str
    text_items: List[str]

class CVData(BaseModel):
    """CVData model."""
    candidate: Optional[Dict[str, Any]] = None
    cv_template: Optional[Dict[str, Any]] = None
    motivation_letter_template: Optional[Dict[str, Any]] = None
    personal_statement: str = ""
    alternative_statements: List[str] = Field(default_factory=list)
    experience_sections: List[ExperienceSection] = Field(default_factory=list)

class CVVersionInfo(BaseModel):
    """CVVersionInfo model."""
    id: str
    name: str
    last_modified: float

@router.get("/templates")
async def list_templates():
    """List available CV and motivation letter templates."""
    return load_template_registry()

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
async def get_cv_version(candidate: str, version_id: str):
    """Get a specific CV version."""
    path = get_cv_version_path(candidate, version_id)
    logger.info(f"GET: candidate={candidate} version_id={version_id} path={path}")
    
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"CV version '{version_id}' not found at {path}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    logger.info(f"GET: loaded experience_sections count={len(data.get('candidate', {}).get('experience_sections', []))}")
    payload = _normalize_cv_payload(data, candidate)
    
    # Prevent caching
    response = JSONResponse(content=payload)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@router.post("/{candidate}/versions/{version_id}", response_model=CVData)
async def create_cv_version(version_id: str, data: CVData, candidate: str = "charilaos_mylonas"):
    """Create a new CV version."""
    path = get_cv_version_path(candidate, version_id)
    if os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"CV version '{version_id}' already exists")
        
    payload = _normalize_cv_payload(data.model_dump(), candidate)
    with open(path, 'w') as f:
        json.dump(payload, f, indent=4)
    logger.info(f"POST: created version_id={version_id} with {len(payload.get('experience_sections', []))} experience_sections")
    return payload

@router.put("/{candidate}/versions/{version_id}", response_model=CVData)
async def update_cv_version(candidate: str, version_id: str, data: CVData):
    """Update an existing CV version."""
    path = get_cv_version_path(candidate, version_id)
    logger.info(f"PUT: candidate={candidate} version_id={version_id} path={path}")
    logger.info(f"PUT: incoming experience_sections count={len(data.experience_sections)}")
    
    # Backup if exists
    if os.path.exists(path):
        shutil.copy(path, path + ".bak")
        
    payload = _normalize_cv_payload(data.model_dump(), candidate)
    logger.info(f"PUT: payload experience_sections count={len(payload.get('experience_sections', []))}")
    
    with open(path, 'w') as f:
        json.dump(payload, f, indent=4)
    
    # Verify save
    with open(path, 'r') as f:
        saved = json.load(f)
    logger.info(f"PUT: verified saved experience_sections count={len(saved.get('candidate', {}).get('experience_sections', []))}")
    
    # Prevent caching
    response = JSONResponse(content=payload)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

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
    return await get_cv_version(candidate, "master")

@router.put("/{candidate}", response_model=CVData)
async def update_cv_data_legacy(data: CVData, candidate: str = "charilaos_mylonas"):
    """Update the master CV data (legacy endpoint)."""
    return await update_cv_version(candidate, "master", data)
