"""TRF-03: thin local-trusted authoring HTTP adapters."""

from fastapi import APIRouter, Depends, Response
from fastapi.responses import JSONResponse
from src.template_package import TemplateRevision, TemplateID, RevisionID
from ..models.studio import StudioImportRequest, StudioDraft, StudioSaveRequest
from .dependencies import get_services
from ..models.studio import StudioPreviewRequest, StudioPreviewError
from ..services.studio_preview import PreviewBusy
from src.tex_compiler import LatexCompileError

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


@router.post('/preview', responses={200: {'content': {'application/pdf': {}}},
    422: {'model': StudioPreviewError}, 429: {'model': StudioPreviewError}})
async def preview(request: StudioPreviewRequest, services=Depends(get_services)):
    try:
        content, identity = await services.studio_preview.render(request)
    except PreviewBusy as error:
        return JSONResponse(status_code=429, content=StudioPreviewError(detail=str(error)).model_dump(), headers={'Retry-After': '2', 'Cache-Control': 'no-store'})
    except LatexCompileError as error:
        return JSONResponse(status_code=422, content=StudioPreviewError(detail=str(error), diagnostics=error.diagnostics).model_dump(), headers={'Cache-Control': 'no-store'})
    return Response(content, media_type='application/pdf', headers={'Cache-Control': 'no-store',
        'Content-Disposition': 'inline; filename="studio-preview.pdf"', 'X-Preview-Input': identity})
