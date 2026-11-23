"""TRF-03: thin local-trusted authoring HTTP adapters."""

from fastapi import APIRouter, Depends
from src.template_package import TemplateRevision, TemplateID, RevisionID
from ..models.studio import StudioImportRequest, StudioDraft, StudioSaveRequest
from .dependencies import get_services

router = APIRouter(prefix='/v1/template-studio', tags=['Template Studio'])


@router.post('/import', response_model=StudioDraft)
def import_draft(request: StudioImportRequest, services=Depends(get_services)):
    return services.studio.import_draft(request)


@router.get('/packages', response_model=list[TemplateRevision])
def list_packages(services=Depends(get_services)):
    return services.studio.repository.list()


@router.get('/packages/{template_id}', response_model=TemplateRevision)
def get_package(template_id: TemplateID, revision: RevisionID | None = None, services=Depends(get_services)):
    return services.studio.repository.get(template_id, revision)


@router.post('/packages', response_model=TemplateRevision)
def save_package(request: StudioSaveRequest, services=Depends(get_services)):
    return services.studio.save(request)
