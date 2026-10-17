"""CV version endpoints using one canonical schema and a storage adapter."""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel

from core.paths import CV_DATA_DIR, ensure_data_dirs
from src.cv_storage import (
    cv_version_path, find_cv_file, load_cv_file, normalize_cv_data, save_cv_file,
)
from src.domain import CVData
from src.template_registry import load_template_registry

router = APIRouter(prefix="/v1/cv-data", tags=["CV Data"])
ensure_data_dirs()
CV_DATA_BASE_DIR = CV_DATA_DIR


class CVVersionInfo(BaseModel):
    id: str
    name: str
    last_modified: float


def _no_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _validate_identity(data: CVData, candidate: str) -> CVData:
    try:
        return normalize_cv_data(data, candidate)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/templates")
async def list_templates():
    return load_template_registry()


@router.get("/{candidate}/versions", response_model=list[CVVersionInfo])
async def list_cv_versions(candidate: str = "charilaos_mylonas"):
    directory = Path(CV_DATA_BASE_DIR) / candidate
    files = {path.stem: path for path in directory.glob("*.json")}
    master = find_cv_file(CV_DATA_BASE_DIR, candidate, "master")
    if "master" not in files and master.exists():
        files["master"] = master
    return sorted(
        [CVVersionInfo(id=version, name=version.replace("_", " ").title(),
                       last_modified=os.path.getmtime(path)) for version, path in files.items()],
        key=lambda item: item.last_modified, reverse=True,
    )


@router.get("/{candidate}/versions/{version_id}", response_model=CVData)
async def get_cv_version(candidate: str, version_id: str, response: Response):
    path = find_cv_file(CV_DATA_BASE_DIR, candidate, version_id)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"CV version '{version_id}' not found")
    try:
        data = load_cv_file(path, candidate)
    except ValueError as error:
        # No write/migration has taken place. The user can resolve the original
        # file explicitly instead of losing one side of a conflicting document.
        raise HTTPException(status_code=409, detail=f"CV data requires resolution: {error}") from error
    _no_cache(response)
    return data


@router.post("/{candidate}/versions/{version_id}", response_model=CVData)
async def create_cv_version(version_id: str, data: CVData, candidate: str = "charilaos_mylonas"):
    if find_cv_file(CV_DATA_BASE_DIR, candidate, version_id).exists():
        raise HTTPException(status_code=400, detail=f"CV version '{version_id}' already exists")
    data = _validate_identity(data, candidate)
    save_cv_file(cv_version_path(CV_DATA_BASE_DIR, candidate, version_id), data)
    return data


@router.put("/{candidate}/versions/{version_id}", response_model=CVData)
async def update_cv_version(candidate: str, version_id: str, data: CVData, response: Response):
    data = _validate_identity(data, candidate)
    save_cv_file(cv_version_path(CV_DATA_BASE_DIR, candidate, version_id), data)
    _no_cache(response)
    return data


@router.delete("/{candidate}/versions/{version_id}")
async def delete_cv_version(version_id: str, candidate: str = "charilaos_mylonas"):
    path = cv_version_path(CV_DATA_BASE_DIR, candidate, version_id)
    if path.name == "master.json":
        raise HTTPException(status_code=400, detail="Cannot delete the master version")
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"CV version '{version_id}' not found")
    path.unlink()
    return {"status": "success", "message": f"Version '{version_id}' deleted"}


# Preserve endpoint aliases, not competing payload shapes.
@router.get("/{candidate}", response_model=CVData)
async def get_cv_data_legacy(response: Response, candidate: str = "charilaos_mylonas"):
    return await get_cv_version(candidate, "master", response)


@router.put("/{candidate}", response_model=CVData)
async def update_cv_data_legacy(data: CVData, response: Response, candidate: str = "charilaos_mylonas"):
    return await update_cv_version(candidate, "master", data, response)
