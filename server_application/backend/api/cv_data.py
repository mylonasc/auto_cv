"""
API routes for CV data management with version support.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import json
import sys
import shutil

# Add project root to path
CV_CUSTOMIZER_ROOT = os.getenv('CV_CUSTOMIZER_ROOT', '/home/charilaos/Workspace/auto_cv')
if CV_CUSTOMIZER_ROOT not in sys.path:
    sys.path.append(CV_CUSTOMIZER_ROOT)

router = APIRouter(prefix="/v1/cv-data", tags=["CV Data"])

CV_DATA_BASE_DIR = os.path.join(CV_CUSTOMIZER_ROOT, 'server_application/backend/cv_section_data')

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
    personal_statement: str
    alternative_statements: List[str] = []
    experience_sections: List[ExperienceSection]

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
        return json.load(f)

@router.post("/{candidate}/versions/{version_id}", response_model=CVData)
async def create_cv_version(version_id: str, data: CVData, candidate: str = "charilaos_mylonas"):
    """Create a new CV version."""
    path = get_cv_version_path(candidate, version_id)
    if os.path.exists(path):
        raise HTTPException(status_code=400, detail=f"CV version '{version_id}' already exists")
        
    with open(path, 'w') as f:
        json.dump(data.model_dump(), f, indent=4)
    return data

@router.put("/{candidate}/versions/{version_id}", response_model=CVData)
async def update_cv_version(version_id: str, data: CVData, candidate: str = "charilaos_mylonas"):
    """Update an existing CV version."""
    path = get_cv_version_path(candidate, version_id)
    
    # Backup if exists
    if os.path.exists(path):
        shutil.copy(path, path + ".bak")
        
    with open(path, 'w') as f:
        json.dump(data.model_dump(), f, indent=4)
    return data

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
