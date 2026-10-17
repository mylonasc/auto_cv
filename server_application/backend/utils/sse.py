"""SSE snapshots use the exact validated HTTP job contract."""

import asyncio
from typing import AsyncGenerator

from models.api_models import JobStatus, StreamError


async def job_status_stream(job_id: str, job_manager) -> AsyncGenerator[str, None]:
    last_revision = None
    idle_loops = 0
    while True:
        job = job_manager.get_job(job_id)
        if job is None:
            error = StreamError(id=job_id, error="Job not found")
            yield f"event: error\ndata: {error.model_dump_json()}\n\n"
            break
        revision = (job.status, job.updated_at, job.progress)
        if revision != last_revision:
            yield f"event: job_update\ndata: {job.model_dump_json()}\n\n"
            last_revision = revision
            idle_loops = 0
        else:
            idle_loops += 1
        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED):
            yield f"event: job_complete\ndata: {job.model_dump_json()}\n\n"
            break
        if idle_loops >= 15:
            yield ": keepalive\n\n"
            idle_loops = 0
        await asyncio.sleep(1)
