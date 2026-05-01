"""
Job manager for tracking CV processing jobs.
"""
import uuid
import json
import os
from datetime import datetime
from typing import Optional, Dict, List
from models.api_models import (
    CVJobResponse, JobStatus, CVJobResult, 
    SectionResult, ExperienceItem, ArtifactResponse
)


class JobManager:
    """Manages job creation, tracking, and persistence."""
    
    def __init__(self, storage_dir: str = "jobs"):
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self._jobs: Dict[str, CVJobResponse] = {}
        self._load_jobs()
    
    def _job_path(self, job_id: str) -> str:
        return os.path.join(self.storage_dir, f"{job_id}.json")
    
    def _load_jobs(self):
        """Load existing jobs from disk."""
        if not os.path.exists(self.storage_dir):
            return
        for filename in os.listdir(self.storage_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(self.storage_dir, filename), 'r') as f:
                        data = json.load(f)
                        job = CVJobResponse(**data)
                        self._jobs[job.id] = job
                except Exception as e:
                    print(f"Error loading job {filename}: {e}")
    
    def _save_job(self, job: CVJobResponse):
        """Save job to disk."""
        with open(self._job_path(job.id), 'w') as f:
            json.dump(job.model_dump(mode='json'), f, default=str)
    
    def create_job(self, candidate: str = "charilaos_mylonas") -> CVJobResponse:
        """Create a new job."""
        now = datetime.now()
        job = CVJobResponse(
            id=str(uuid.uuid4()),
            status=JobStatus.QUEUED,
            progress="Job created",
            message="Job has been queued for processing",
            created_at=now,
            updated_at=now
        )
        self._jobs[job.id] = job
        self._save_job(job)
        return job
    
    def get_job(self, job_id: str) -> Optional[CVJobResponse]:
        """Get a job by ID."""
        return self._jobs.get(job_id)
    
    def update_job_status(
        self, 
        job_id: str, 
        status: JobStatus,
        progress: Optional[str] = None,
        message: Optional[str] = None,
        result: Optional[CVJobResult] = None,
        error: Optional[str] = None
    ) -> Optional[CVJobResponse]:
        """Update job status and details."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        
        job.status = status
        job.updated_at = datetime.now()
        
        if progress is not None:
            job.progress = progress
        if message is not None:
            job.message = message
        if result is not None:
            job.result = result
        if error is not None:
            job.error = error
        
        self._save_job(job)
        return job
    
    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's still pending/processing."""
        job = self._jobs.get(job_id)
        if not job:
            return False
        if job.status in [JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED]:
            return False
        job.status = JobStatus.CANCELLED
        job.updated_at = datetime.now()
        job.message = "Job was cancelled by user"
        self._save_job(job)
        return True
    
    def list_jobs(self) -> List[CVJobResponse]:
        """List all jobs."""
        return list(self._jobs.values())
    
    def add_artifact(self, job_id: str, artifact_type: str, name: str, path: str) -> Optional[ArtifactResponse]:
        """Add an artifact to a job."""
        job = self._jobs.get(job_id)
        if not job:
            return None
        
        if not job.result:
            job.result = CVJobResult(sections=[], artifacts=[])
        
        artifact = {
            "id": str(uuid.uuid4()),
            "job_id": job_id,
            "type": artifact_type,
            "name": name,
            "path": path,
            "created_at": datetime.now().isoformat()
        }
        job.result.artifacts.append(artifact)
        job.updated_at = datetime.now()
        self._save_job(job)
        return ArtifactResponse(**artifact)


# Global job manager instance
job_manager = JobManager()
