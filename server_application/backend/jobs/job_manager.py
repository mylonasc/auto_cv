"""Explicitly constructed job repository; no global store or task ownership."""

from datetime import datetime
import json
import logging
from pathlib import Path
from threading import RLock
from uuid import uuid4

from models.api_models import CVJobResponse, JobStatus
from models.legacy import normalize_persisted_job
from src.config import public_config
from src.storage import atomic_write_json

logger = logging.getLogger(__name__)
TERMINAL = frozenset((JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED))


class JobManager:
    """Single-process, lock-serialized JSON job records with terminal-state guards.

    Callers receive copies. Writes validate and atomically replace disk data
    before publishing new memory state. A queued job may finish immediately;
    terminal statuses cannot transition back or change to another terminal state.
    """
    def __init__(self, storage_dir):
        self.storage_dir = str(storage_dir)
        Path(storage_dir).mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._jobs = {}
        self.load_errors = {}
        for path in Path(storage_dir).glob("*.json"):
            try:
                job = CVJobResponse.model_validate(normalize_persisted_job(json.loads(path.read_text())))
                if path.stem != job.id:
                    raise ValueError("Job ID does not match record filename")
                self._jobs[job.id] = job
            except (ValueError, OSError) as error:
                self.load_errors[path.name] = str(error)
                logger.warning("Could not load job %s; original retained", path.name)

    def _job_path(self, job_id):
        if not job_id or Path(job_id).name != job_id or job_id in (".", "..") or "\\" in job_id:
            raise ValueError("Invalid job ID")
        return Path(self.storage_dir) / f"{job_id}.json"

    def _save_job(self, job):
        atomic_write_json(self._job_path(job.id), job.model_dump(mode="json"))

    def create_job(self, candidate="charilaos_mylonas", job_description=None, effective_config=None,
                   cv_version_id=None, cv_snapshot=None):
        with self._lock:
            now = datetime.now()
            job = CVJobResponse(id=str(uuid4()), status=JobStatus.QUEUED, candidate=candidate,
                                cv_version_id=cv_version_id, cv_snapshot=cv_snapshot.model_copy(deep=True) if cv_snapshot is not None else None,
                                effective_config=public_config(effective_config) if effective_config else None,
                                job_description=job_description, progress="Job created",
                                message="Job has been queued for processing", created_at=now, updated_at=now)
            self._save_job(job)
            self._jobs[job.id] = job
            return job.model_copy(deep=True)

    def get_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def update_job_status(self, job_id, status, progress=None, message=None, result=None, job_analysis=None, error=None):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            if job.status in TERMINAL and status != job.status:
                raise ValueError(f"Cannot transition terminal job {job.status} to {status}")
            if job.status == JobStatus.PROCESSING and status == JobStatus.QUEUED:
                raise ValueError("Cannot return a processing job to the queue")
            data = job.model_dump()
            data.update(status=status, updated_at=datetime.now())
            for key, value in (("progress", progress), ("message", message), ("result", result),
                               ("job_analysis", job_analysis), ("error", error)):
                if value is not None:
                    data[key] = value
            updated = CVJobResponse.model_validate(data).model_copy(deep=True)
            self._save_job(updated)
            self._jobs[job_id] = updated
            return updated.model_copy(deep=True)

    def append_artifacts(self, job_id, artifacts):
        with self._lock:
            job = self._jobs[job_id]
            if job.status != JobStatus.SUCCEEDED or job.result is None:
                raise ValueError("Only succeeded jobs can publish render artifacts")
            result = job.result.model_dump()
            result["artifacts"].extend(artifacts)
            return self.update_job_status(job_id, job.status, result=result)

    def cancel_job(self, job_id, message="Job was cancelled by user"):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.status in TERMINAL:
                return False
            self.update_job_status(job_id, JobStatus.CANCELLED, message=message)
            return True

    def list_jobs(self):
        with self._lock:
            return [job.model_copy(deep=True) for job in self._jobs.values()]

    def archive_job(self, job_id, archived=True):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            updated = CVJobResponse.model_validate(dict(job.model_dump(), archived=archived, updated_at=datetime.now()))
            self._save_job(updated)
            self._jobs[job_id] = updated
            return updated.model_copy(deep=True)

    def delete_job(self, job_id):
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return False
            if job.status not in TERMINAL:
                raise ValueError("Cancel or finish a job before deleting it")
            self._job_path(job_id).unlink(missing_ok=True)
            del self._jobs[job_id]
            return True

    def recover_interrupted(self):
        for job in self.list_jobs():
            if job.status not in TERMINAL:
                self.update_job_status(job.id, JobStatus.FAILED,
                    error="Processing interrupted by server restart; create a new job",
                    message="Interrupted job was not automatically replayed")
