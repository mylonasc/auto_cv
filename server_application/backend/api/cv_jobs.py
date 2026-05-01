"""
API routes for CV job management.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import List, Optional
from datetime import datetime
import asyncio

from models.api_models import (
    CreateJobRequest, CVJobResponse, JobStatus, 
    CVJobResult, BackendConfig
)
from jobs.job_manager import job_manager
from services.cv_processor import CVProcessor

router = APIRouter(prefix="/v1/cv-jobs", tags=["CV Jobs"])

# Store active background tasks
active_tasks = {}


async def status_callback(job_id: str, status: JobStatus, progress: Optional[str] = None, message: Optional[str] = None):
    """Callback to update job status."""
    job_manager.update_job_status(
        job_id=job_id,
        status=status,
        progress=progress,
        message=message
    )


async def process_job_background(job_id: str, request: CreateJobRequest):
    """Background task to process a CV job."""
    try:
        # Update status to processing
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress="Starting CV processing...",
            message="Initializing CV processor"
        )
        
        # Create processor
        processor = CVProcessor(
            candidate=request.candidate,
            config=request.config
        )
        
        # Process
        result = await processor.process(
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
            result=result
        )
        
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
    job = job_manager.create_job(candidate=request.candidate)
    
    # Store request for background task
    active_tasks[job.id] = request
    
    # Start background processing
    asyncio.create_task(process_job_background(job.id, request))
    
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
async def get_artifact(job_id: str, artifact_id: str):
    """Download a specific artifact from a job."""
    job = job_manager.get_job(job_id)
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Job or result not found")
    
    artifact = next((a for a in job.result.artifacts if a.get("id") == artifact_id), None)
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    file_path = artifact.get("path")
    if not file_path or not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Artifact file not found")
    
    from fastapi.responses import FileResponse
    return FileResponse(
        path=file_path,
        media_type='application/octet-stream',
        filename=artifact.get("name", "artifact")
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
