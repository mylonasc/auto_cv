"""HTTP adapters; repositories and job execution belong to application services."""

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse, StreamingResponse

from models.api_models import (CreateJobRequest, CVJobResponse, CVJobResult, JobAnalysisRequest,
    JobAnalysisResponse, WorkingCopy, RenderCVRequest, RescoreRequest, RescoreResponse)
from services.application import ApplicationServices, OperationError
from utils.sse import job_status_stream
from .dependencies import get_services

router = APIRouter(prefix="/v1/cv-jobs", tags=["CV Jobs"])


@router.post("/", response_model=CVJobResponse)
async def create_job(request: CreateJobRequest, services: ApplicationServices = Depends(get_services)):
    return await services.create_job(request)


@router.post("/job-analysis", response_model=JobAnalysisResponse)
async def analyze_job_only(request: JobAnalysisRequest, services: ApplicationServices = Depends(get_services)):
    return await services.analyze_posting(request)


@router.get("/", response_model=list[CVJobResponse])
async def list_jobs(services: ApplicationServices = Depends(get_services)):
    return services.jobs.list_jobs()


@router.get("/{job_id}", response_model=CVJobResponse)
async def get_job(job_id: str, services: ApplicationServices = Depends(get_services)):
    return services.get_job(job_id)


@router.post("/{job_id}/cancel", response_model=CVJobResponse)
async def cancel_job(job_id: str, services: ApplicationServices = Depends(get_services)):
    services.get_job(job_id)
    if not services.runner.cancel(job_id):
        raise OperationError(400, "Job cannot be cancelled after completion")
    return services.get_job(job_id)


@router.post("/{job_id}/archive", response_model=CVJobResponse)
async def archive_job(job_id: str, services: ApplicationServices = Depends(get_services)):
    services.get_job(job_id)
    return services.jobs.archive_job(job_id)


@router.post("/{job_id}/unarchive", response_model=CVJobResponse)
async def unarchive_job(job_id: str, services: ApplicationServices = Depends(get_services)):
    services.get_job(job_id)
    return services.jobs.archive_job(job_id, archived=False)


@router.delete("/{job_id}")
async def delete_job(job_id: str, services: ApplicationServices = Depends(get_services)):
    services.get_job(job_id)
    services.jobs.delete_job(job_id)
    # Conservatively retain working copies, artifacts, render records and sent
    # submissions. Deleting history does not authorize destroying user outputs.
    return {"ok": True, "job_id": job_id}


@router.get("/{job_id}/result", response_model=CVJobResult)
async def get_job_result(job_id: str, services: ApplicationServices = Depends(get_services)):
    return services.completed_job(job_id).result


@router.get("/{job_id}/stream")
async def stream_job_updates(job_id: str, services: ApplicationServices = Depends(get_services)):
    services.get_job(job_id)
    return StreamingResponse(job_status_stream(job_id, services.jobs), media_type="text/event-stream")


@router.get("/{job_id}/artifacts/{artifact_id}")
async def get_artifact(job_id: str, artifact_id: str, inline: bool = Query(default=False),
                       services: ApplicationServices = Depends(get_services)):
    job = services.completed_job(job_id)
    artifact = next((item for item in job.result.artifacts if item["id"] == artifact_id), None)
    if artifact is None:
        raise OperationError(404, "Artifact not found")
    path = services.artifacts.resolve(job_id, artifact)
    if path is None:
        raise OperationError(404, "Artifact file not found")
    media = {"pdf": "application/pdf", "latex": "application/x-tex", "json": "application/json"}[artifact["kind"]]
    headers = {"Content-Disposition": f'inline; filename="{artifact["filename"]}"'} if inline else None
    return FileResponse(path, media_type=media, filename=artifact["filename"], headers=headers)


@router.get("/{job_id}/working-cv", response_model=WorkingCopy)
async def get_working_copy(job_id: str, services: ApplicationServices = Depends(get_services)):
    return services.get_working_copy(job_id)


@router.put("/{job_id}/working-cv", response_model=WorkingCopy)
async def save_working_copy(job_id: str, copy: WorkingCopy, services: ApplicationServices = Depends(get_services)):
    return services.save_working_copy(job_id, copy)


@router.post("/{job_id}/working-cv/rescore", response_model=RescoreResponse)
async def rescore_working_copy_items(job_id: str, request: RescoreRequest, services: ApplicationServices = Depends(get_services)):
    return await services.rescore(job_id, request)


@router.post("/{job_id}/render", response_model=CVJobResponse)
async def render_job_artifacts(job_id: str, request: RenderCVRequest, services: ApplicationServices = Depends(get_services)):
    return await services.render(job_id, request)
