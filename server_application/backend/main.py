"""
Main FastAPI application for CV Customizer.
Provides async job-based API for CV processing with real-time status updates.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.websockets import WebSocket
from typing import Optional, List
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
CV_CUSTOMIZER_ROOT = os.getenv('CV_CUSTOMIZER_ROOT', '/home/charilaos/Workspace/auto_cv')
if CV_CUSTOMIZER_ROOT not in sys.path:
    sys.path.append(CV_CUSTOMIZER_ROOT)

from models.api_models import (
    CreateJobRequest, CVJobResponse, JobStatus, 
    CVJobResult, BackendConfig, ArtifactResponse, SectionResult
)
from jobs.job_manager import job_manager
from services.cv_processor import CVProcessor

# Create FastAPI app
app = FastAPI(
    title="CV Customizer API",
    description="API for AI-powered CV customization based on job descriptions",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for SSE connections
active_connections: List[WebSocket] = []


async def update_job_status(job_id: str, status: JobStatus, progress: Optional[str] = None, message: Optional[str] = None):
    """Update job status and notify clients via SSE."""
    job = job_manager.update_job_status(
        job_id=job_id,
        status=status,
        progress=progress,
        message=message
    )
    # Notify via WebSocket if available
    for connection in active_connections:
        try:
            await connection.send_json({
                "event": "job_update",
                "job_id": job_id,
                "status": status,
                "progress": progress,
                "message": message
            })
        except:
            pass
    return job


async def process_cv_job(job_id: str, job_description: str, candidate: str, config: Optional[BackendConfig]):
    """Background task to process CV job."""
    try:
        # Update status to processing
        await update_job_status(
            job_id, JobStatus.PROCESSING, 
            progress="Starting CV processing...",
            message="Initializing CV processor"
        )
        
        # Create processor
        processor = CVProcessor(candidate=candidate, config=config)
        
        # Define callback for status updates
        async def status_callback(jid, status, progress):
            await update_job_status(jid, status, progress=progress)
        
        # Process the CV
        result = await processor.process(
            job_description=job_description,
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
        # Update job with error
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=str(e),
            message=f"Processing failed: {str(e)}"
        )


@app.get("/")
async def root():
    """API root - returns basic info."""
    return {
        "name": "CV Customizer API",
        "version": "1.0.0",
        "endpoints": {
            "create_job": "POST /v1/cv-jobs/",
            "get_job": "GET /v1/cv-jobs/{job_id}",
            "cancel_job": "POST /v1/cv-jobs/{job_id}/cancel",
            "get_result": "GET /v1/cv-jobs/{job_id}/result",
            "get_artifact": "GET /v1/cv-jobs/{job_id}/artifacts/{artifact_id}",
            "list_jobs": "GET /v1/cv-jobs/",
            "config": "GET/PUT /v1/config",
            "models": "GET /v1/models/available"
        }
    }


@app.post("/v1/cv-jobs/", response_model=CVJobResponse)
async def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    """
    Create a new CV processing job.
    
    - **job_description**: Text of the job posting
    - **candidate**: Candidate name (default: charilaos_mylonas)
    - **config**: Optional backend configuration
    """
    # Create job
    job = job_manager.create_job(candidate=request.candidate)
    
    # Start background processing
    background_tasks.add_task(
        process_cv_job,
        job_id=job.id,
        job_description=request.job_description,
        candidate=request.candidate,
        config=request.config
    )
    
    return job


@app.get("/v1/cv-jobs/{job_id}", response_model=CVJobResponse)
async def get_job(job_id: str):
    """Get the status and details of a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/v1/cv-jobs/{job_id}/cancel", response_model=CVJobResponse)
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    success = job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (not found or already completed)")
    
    job = job_manager.get_job(job_id)
    return job


@app.get("/v1/cv-jobs/{job_id}/result", response_model=CVJobResult)
async def get_job_result(job_id: str):
    """Get the result of a completed job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(status_code=400, detail=f"Job is not completed (status: {job.status})")
    
    return job.result


@app.get("/v1/cv-jobs/", response_model=List[CVJobResponse])
async def list_jobs():
    """List all jobs."""
    return job_manager.list_jobs()


@app.get("/v1/cv-jobs/{job_id}/artifacts/{artifact_id}")
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
    
    return FileResponse(
        path=file_path,
        media_type='application/octet-stream',
        filename=artifact.get("name", "artifact")
    )


@app.get("/v1/config", response_model=BackendConfig)
async def get_config():
    """Get current backend configuration."""
    # Return default config (in production, this would be stored)
    return BackendConfig()


@app.put("/v1/config", response_model=BackendConfig)
async def update_config(config: BackendConfig):
    """Update backend configuration."""
    # In production, save to persistent storage
    return config


@app.get("/v1/models/available")
async def list_available_models(provider: Optional[str] = None):
    """
    List available LLM models.
    
    - **provider**: Filter by provider (ollama, google)
    """
    models = {
        "ollama": [],
        "google": []
    }
    
    # Get Ollama models
    try:
        import ollama
        ollama_models = ollama.list()
        models["ollama"] = [m.model for m in ollama_models.models]
    except:
        pass
    
    # Google models (static list)
    models["google"] = [
        "models/gemini-2.5-flash-preview-05-20",
        "models/gemini-1.5-pro",
        "models/gemini-1.5-flash"
    ]
    
    if provider:
        return {provider: models.get(provider, [])}
    return models


@app.websocket("/v1/ws/jobs")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time job updates."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo back for now (could handle commands)
            await websocket.send_text(f"Message received: {data}")
    except:
        pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)


@app.get("/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


# Mount static files for artifacts if needed
artifacts_dir = Path("artifacts")
if artifacts_dir.exists():
    app.mount("/artifacts", StaticFiles(directory="artifacts"), name="artifacts")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
