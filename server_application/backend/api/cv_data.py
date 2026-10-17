"""Canonical CV HTTP adapters; legacy adaptation and saves belong to the repository."""

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from src.domain import CVData
from src.template_registry import load_template_registry
from services.application import ApplicationServices, OperationError
from .dependencies import get_services

router = APIRouter(prefix="/v1/cv-data", tags=["CV Data"])


class CVVersionInfo(BaseModel):
    id: str
    name: str
    last_modified: float


def _no_cache(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"


def _validate_identity(data, candidate):
    if data.candidate.candidate_id != candidate:
        raise OperationError(422, "candidate_id does not match the requested candidate")


@router.get("/templates")
async def list_templates():
    return load_template_registry()


@router.get("/{candidate}/versions", response_model=list[CVVersionInfo])
async def list_cv_versions(candidate: str, services: ApplicationServices = Depends(get_services)):
    return services.cvs.list(candidate)


@router.get("/{candidate}/versions/{version_id}", response_model=CVData)
async def get_cv_version(candidate: str, version_id: str, response: Response,
                         services: ApplicationServices = Depends(get_services)):
    result = services.cvs.get(candidate, version_id)
    _no_cache(response)
    return result


@router.post("/{candidate}/versions/{version_id}", response_model=CVData)
async def create_cv_version(candidate: str, version_id: str, data: CVData,
                            services: ApplicationServices = Depends(get_services)):
    _validate_identity(data, candidate)
    return services.cvs.save(candidate, version_id, data, create=True)


@router.put("/{candidate}/versions/{version_id}", response_model=CVData)
async def update_cv_version(candidate: str, version_id: str, data: CVData, response: Response,
                            services: ApplicationServices = Depends(get_services)):
    _validate_identity(data, candidate)
    result = services.cvs.save(candidate, version_id, data)
    _no_cache(response)
    return result


@router.delete("/{candidate}/versions/{version_id}")
async def delete_cv_version(candidate: str, version_id: str, services: ApplicationServices = Depends(get_services)):
    services.cvs.delete(candidate, version_id)
    return {"status": "success", "message": f"Version '{version_id}' deleted"}


@router.get("/{candidate}", response_model=CVData)
async def get_cv_data_legacy(candidate: str, response: Response, services: ApplicationServices = Depends(get_services)):
    return await get_cv_version(candidate, "master", response, services)


@router.put("/{candidate}", response_model=CVData)
async def update_cv_data_legacy(candidate: str, data: CVData, response: Response,
                               services: ApplicationServices = Depends(get_services)):
    return await update_cv_version(candidate, "master", data, response, services)
