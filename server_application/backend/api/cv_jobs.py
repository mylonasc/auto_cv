"""
API routes for CV job management.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional
import asyncio
import os
import glob

from models.api_models import (
    CreateJobRequest, CVJobResponse, JobStatus, CVJobResult
)
from jobs.job_manager import job_manager
from services.cv_processor import CVProcessor
from core.paths import ARTIFACTS_DIR, ensure_data_dirs

ensure_data_dirs()

router = APIRouter(prefix="/v1/cv-jobs", tags=["CV Jobs"])

# Store active background tasks
active_tasks = {}


def _resolve_artifact_file_path(job_id: str, artifact: dict) -> Optional[str]:
    """Resolve the on-disk artifact path across environments."""
    artifacts_dir = ARTIFACTS_DIR
    kind = artifact.get("kind") or artifact.get("type") or "pdf"
    ext = "tex" if kind == "latex" else kind

    candidates = []
    stored_path = artifact.get("path")
    if stored_path:
        candidates.append(stored_path)
        candidates.append(os.path.join(artifacts_dir, os.path.basename(stored_path)))

    filename = artifact.get("filename")
    if filename:
        candidates.append(os.path.join(artifacts_dir, filename))

    name = artifact.get("name")
    if name:
        candidates.append(os.path.join(artifacts_dir, name))

    candidates.append(os.path.join(artifacts_dir, f"cv_output_{job_id}.{ext}"))

    wildcard_matches = glob.glob(os.path.join(artifacts_dir, f"cv_output_{job_id}.*"))
    candidates.extend(wildcard_matches)

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate

    return None


async def status_callback(job_id: str, status: JobStatus, progress: Optional[str] = None, message: Optional[str] = None):
    """Callback to update job status."""
    # Check if cancelled
    job = job_manager.get_job(job_id)
    if job and job.status == JobStatus.CANCELLED:
        raise asyncio.CancelledError("Job was cancelled by user")
        
    job_manager.update_job_status(
        job_id=job_id,
        status=status,
        progress=progress,
        message=message
    )


async def process_job_background(job_id: str, request: CreateJobRequest):
    """Background task to process a CV job."""
    try:
        # Check if already cancelled
        job = job_manager.get_job(job_id)
        if not job or job.status == JobStatus.CANCELLED:
            return

        # Update status to processing
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress="Starting CV processing...",
            message="Initializing CV processor"
        )
        
        # Run processing
        processor = CVProcessor(
            candidate=request.candidate,
            config=request.config,
            cv_version_id=request.cv_version_id
        )

        
        # Process
        result, job_analysis = await processor.process(
            job_description=request.job_description,
            job_id=job_id,
            status_callback=status_callback
        )
        
        # Update job with result
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.SUCCEEDED,
            progress="Processing complete",
            message="CV has been successfully processed",
            result=result,
            job_analysis=job_analysis
        )
        
    except asyncio.CancelledError:
        # Job was already marked as CANCELLED in status_callback or cancel_job endpoint
        pass
    except Exception as e:
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=str(e),
            message=f"Processing failed: {str(e)}"
        )
    finally:
        # Clean up task reference
        if job_id in active_tasks:
            del active_tasks[job_id]


@router.post("/", response_model=CVJobResponse)
async def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    """
    Create a new CV processing job.
    
    - **job_description**: Text of the job posting
    - **candidate**: Candidate name (default: charilaos_mylonas)
    - **config**: Optional backend configuration
    """
    # Create job
    job = job_manager.create_job(candidate=request.candidate, job_description=request.job_description)
    
    # Store request for background task
    active_tasks[job.id] = request
    
    # Start background processing
    background_tasks.add_task(process_job_background, job.id, request)
    
    return job


@router.get("/{job_id}", response_model=CVJobResponse)
async def get_job(job_id: str):
    """Get the status and details of a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=CVJobResponse)
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    success = job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (not found or already completed)")
    
    job = job_manager.get_job(job_id)
    return job


@router.post("/{job_id}/archive", response_model=CVJobResponse)
async def archive_job(job_id: str):
    """Archive a job to declutter history views."""
    job = job_manager.archive_job(job_id, archived=True)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/unarchive", response_model=CVJobResponse)
async def unarchive_job(job_id: str):
    """Restore an archived job."""
    job = job_manager.archive_job(job_id, archived=False)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Permanently delete a job from history."""
    success = job_manager.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "job_id": job_id}


@router.get("/{job_id}/result", response_model=CVJobResult)
async def get_job_result(job_id: str):
    """Get the result of a completed job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(status_code=400, detail=f"Job is not completed (status: {job.status})")
    
    return job.result


@router.get("/", response_model=List[CVJobResponse])
async def list_jobs():
    """List all jobs."""
    return job_manager.list_jobs()


@router.get("/{job_id}/artifacts/{artifact_id}")
async def get_artifact(job_id: str, artifact_id: str, inline: bool = Query(default=False)):
    """Download a specific artifact from a job."""
    print(f"Artifact requested: job_id={job_id}, artifact_id={artifact_id}")
    job = job_manager.get_job(job_id)
    if not job or not job.result:
        print(f"Job or result not found for {job_id}")
        raise HTTPException(status_code=404, detail="Job or result not found")

    result_obj = job.result
    if isinstance(result_obj, dict):
        artifacts = result_obj.get("artifacts") or []
    else:
        artifacts = getattr(result_obj, "artifacts", None) or []

    if not isinstance(artifacts, list):
        artifacts = []
    
    # Try to find artifact by ID
    artifact = next((a for a in artifacts if isinstance(a, dict) and a.get("id") == artifact_id), None)
    
    if not artifact:
        # Fallback: maybe artifact_id is actually the kind (pdf/latex)
        artifact = next((a for a in artifacts if isinstance(a, dict) and (a.get("kind") == artifact_id or a.get("type") == artifact_id)), None)

    if not artifact:
        print(f"Artifact {artifact_id} not found in job {job_id}. Available IDs: {[a.get('id') for a in artifacts if isinstance(a, dict)]}")
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    file_path = _resolve_artifact_file_path(job_id, artifact)
    if not file_path:
        expected_filename = artifact.get("filename") or artifact.get("name") or f"cv_output_{job_id}"
        print(f"Artifact file not found for job {job_id}, artifact {artifact_id}")
        raise HTTPException(status_code=404, detail=f"Artifact file '{expected_filename}' not found on disk")

    from fastapi.responses import FileResponse
    response_filename = artifact.get("filename") or artifact.get("name") or os.path.basename(file_path)
    lower = response_filename.lower()
    media_type = 'application/octet-stream'
    if lower.endswith('.pdf'):
        media_type = 'application/pdf'
    elif lower.endswith('.tex'):
        media_type = 'application/x-tex'

    headers = None
    if inline:
        headers = {"Content-Disposition": f'inline; filename="{response_filename}"'}

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=response_filename,
        headers=headers
    )


@router.get("/{job_id}/stream")
async def stream_job_updates(job_id: str):
    """
    SSE endpoint for real-time job status updates.
    Returns a stream of events: job_update, job_complete, error
    """
    from fastapi.responses import StreamingResponse
    from utils.sse import job_status_stream
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return StreamingResponse(
        job_status_stream(job_id, job_manager),
        media_type="text/event-stream"
    )
