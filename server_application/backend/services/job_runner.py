"""Owned asyncio execution handles and explicit shutdown/restart behavior."""

import asyncio

from models.api_models import JobStatus
from jobs.job_manager import TERMINAL


class JobRunner:
    def __init__(self, jobs, execute):
        self.jobs, self.execute = jobs, execute
        self.tasks = {}

    def start(self, job, config):
        if job.id in self.tasks:
            raise ValueError("Job already has an execution handle")
        task = asyncio.create_task(self._run(job.id, config), name=f"cv-job:{job.id}")
        self.tasks[job.id] = task

        def cleanup(completed):
            if self.tasks.get(job.id) is completed:
                self.tasks.pop(job.id, None)
        task.add_done_callback(cleanup)

    async def _run(self, id, config):
        try:
            job = self.jobs.get_job(id)
            if job is None or job.status in TERMINAL:
                return
            self.jobs.update_job_status(id, JobStatus.PROCESSING, progress="Starting CV processing...")
            await self.execute(id, config, self.progress)
        except asyncio.CancelledError:
            self.jobs.cancel_job(id)
        except Exception as error:
            job = self.jobs.get_job(id)
            if job and job.status not in TERMINAL:
                self.jobs.update_job_status(id, JobStatus.FAILED, error=str(error), message="Processing failed")

    async def progress(self, id, status, progress=None, message=None):
        job = self.jobs.get_job(id)
        if job is None or job.status in TERMINAL:
            raise asyncio.CancelledError("Job is no longer running")
        self.jobs.update_job_status(id, status, progress=progress, message=message)

    def cancel(self, id):
        if not self.jobs.cancel_job(id):
            return False
        task = self.tasks.get(id)
        if task:
            task.cancel()
        return True

    async def shutdown(self):
        pending = list(self.tasks.items())
        for id, task in pending:
            self.jobs.cancel_job(id, message="Server shut down; job was cancelled")
            task.cancel()
        await asyncio.gather(*(task for _, task in pending), return_exceptions=True)
        self.tasks.clear()
