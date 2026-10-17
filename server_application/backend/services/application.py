"""Application operations with explicitly injected repositories and execution."""

import asyncio
from datetime import datetime
from uuid import uuid4

from jobs.job_manager import JobManager
from repositories import CVRepository, WorkingCopyRepository, SubmissionRepository, ArtifactRepository
from models.api_models import (JobStatus, WorkingCopy, RenderRecord, Submission, RescoreResponse, RescoredItemResult)
from src.artifacts import render_artifacts
from src.config import BackendConfig
from src.domain import CVData, CandidateMetadata, ExperienceSectionData
from src.pipeline import analyze_posting, bullet_scoring_chain
from src.utils_cross_analysis import AnalysisResultCache
from .cv_processor import CVProcessor
from .job_runner import JobRunner
from .working_copy import create_working_copy, select_working_copy, document_from_working_copy


class OperationError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message
        super().__init__(message)


class ApplicationServices:
    def __init__(self, paths, *, jobs=None, cvs=None, working=None, submissions=None, artifacts=None,
                 cache=None, processor_factory=CVProcessor, runner_factory=JobRunner):
        self.paths = paths
        self.jobs = jobs if jobs is not None else JobManager(paths.jobs)
        self.cvs = cvs if cvs is not None else CVRepository(paths.cvs)
        self.working = working if working is not None else WorkingCopyRepository(paths.working_copies)
        self.submissions = submissions if submissions is not None else SubmissionRepository(paths.submissions)
        self.artifacts = artifacts if artifacts is not None else ArtifactRepository(paths.artifacts, paths.render_records)
        paths.cache.parent.mkdir(parents=True, exist_ok=True)
        self.cache = cache if cache is not None else AnalysisResultCache(str(paths.cache))
        self.config = BackendConfig()
        self.processor_factory = processor_factory
        self.runner = runner_factory(self.jobs, self.execute)

    def get_job(self, id):
        job = self.jobs.get_job(id)
        if job is None:
            raise OperationError(404, "Job not found")
        return job

    def completed_job(self, id):
        job = self.get_job(id)
        if job.status != JobStatus.SUCCEEDED or job.result is None:
            raise OperationError(409, "Job must have succeeded before this operation")
        return job

    async def create_job(self, request):
        config = (request.config or self.config).model_copy(deep=True)
        if config.outputs.include_cover_letter:
            raise OperationError(422, "Cover-letter output is CLI-only; disable it for HTTP jobs")
        source = self.cvs.get(request.candidate, request.cv_version_id)
        job = self.jobs.create_job(request.candidate, request.job_description, config,
                                   cv_version_id=request.cv_version_id, cv_snapshot=source)
        self.runner.start(job, config)
        return job

    async def analyze_posting(self, request):
        result = await analyze_posting(request.job_description, request.config or self.config)
        return {"job_analysis": result.data}

    async def execute(self, id, config, progress):
        job = self.get_job(id)
        processor = self.processor_factory(source=job.cv_snapshot.model_copy(deep=True), config=config,
                                           artifacts_dir=self.paths.artifacts, cache=self.cache)
        output = await processor.process(job.job_description, id, status_callback=progress)
        await progress(id, JobStatus.PROCESSING, "Saving working copy and render provenance...")
        # There is deliberately no await between the final cancellation gate and
        # these serialized publication writes. Success is last, after all records.
        pending = job.model_copy(update={"result": output.result, "job_analysis": output.job_analysis})
        copy = create_working_copy(pending)
        self.working.save(copy)
        if output.result.artifacts:
            self.record_render(pending, copy, output.result.artifacts, source=output.rendered_cv or job.cv_snapshot)
        self.jobs.update_job_status(id, JobStatus.SUCCEEDED, result=output.result, job_analysis=output.job_analysis,
                                     progress="Processing complete", message="CV has been successfully processed")

    def get_working_copy(self, id):
        job = self.completed_job(id)
        copy = self.working.get(id)
        return copy if copy is not None else self.working.save(create_working_copy(job))

    def save_working_copy(self, id, copy):
        self.completed_job(id)
        copy = copy.model_copy(deep=True)
        copy.job_id = id
        copy.updated_at = datetime.now().isoformat()
        copy.created_at = copy.created_at or copy.updated_at
        return self.working.save(copy)

    def record_render(self, job, copy, artifacts, *, source=None, template=None):
        source = source or job.cv_snapshot or CVData(candidate=CandidateMetadata(candidate_id=job.candidate))
        snapshot = source.model_copy(deep=True)
        snapshot.personal_statement = copy.personal_statement
        snapshot.alternative_statements = []
        snapshot.experience_sections = [ExperienceSectionData(company=section.company, position=section.position,
            duration=section.duration, text_items=[item.text for item in section.items if item.kept])
            for section in copy.sections if any(item.kept for item in section.items)]
        if template is not None:
            snapshot.cv_template = template
        return self.artifacts.record(RenderRecord(id=str(uuid4()), job_id=job.id, artifacts=artifacts,
            cv_snapshot=snapshot, working_copy=copy.model_copy(deep=True), scoring_snapshot=job.result.model_copy(deep=True),
            created_at=datetime.now().isoformat()))

    async def render(self, id, request):
        job = self.completed_job(id)
        copy = request.working_copy.model_copy(deep=True) if request.working_copy is not None else select_working_copy(job, request)
        copy.job_id = id
        title = job.cv_snapshot.cv_template.experience_section_title if job.cv_snapshot else (
            job.result.sections[0].title if job.result.sections else "Work Experience")
        document = document_from_working_copy(copy, request, title)
        artifacts = await asyncio.to_thread(render_artifacts, document, self.paths.artifacts,
            f"cv_output_{id}_{uuid4().hex}", render_pdf=request.render_pdf, include_latex=request.include_latex,
            include_scoring_comments=request.include_scoring_comments,
            source="working_copy" if request.working_copy is not None else "analysis")
        # Check that the job wasn't deleted while the render thread was running.
        job = self.completed_job(id)
        if artifacts:
            self.record_render(job, copy, artifacts, template=document.cv_template)
        return self.jobs.append_artifacts(id, artifacts)

    async def rescore(self, id, request):
        job = self.completed_job(id)
        baseline = self.get_working_copy(id)
        if request.section_index >= len(baseline.sections):
            raise OperationError(400, "Invalid section_index")
        section = baseline.sections[request.section_index]
        indices = request.item_indices or list(range(len(section.items)))
        if any(index < 0 or index >= len(section.items) for index in indices):
            raise OperationError(400, "Invalid item index")
        text_map = {item.index: item.text for item in request.items or [] if item.text is not None}
        chain = bullet_scoring_chain(job.effective_config or self.config)
        results = []
        changes = {}
        for index in indices:
            item = section.items[index]
            text = text_map.get(index, item.text)
            result = await chain.ainvoke({"cv_experience": text, "job_posting_data": str(job.job_analysis or {})})
            changes[item.id] = (item.text, text, result)
            results.append(RescoredItemResult(index=index, relevance_score=result.experience_relevance_score,
                explanation=result.explanation, posting_evidence=result.posting_evidence, scored_text=text))

        def apply(current):
            target = next((role for role in current.sections if role.id == section.id), None)
            if target is None:
                raise OperationError(409, "Working copy changed during rescoring")
            for item_id, (old_text, text, result) in changes.items():
                item = next((item for item in target.items if item.id == item_id), None)
                if item is None or item.text not in (old_text, text):
                    raise OperationError(409, "Bullet changed during rescoring; retry against current text")
                item.text = item.scored_text = text
                item.relevance_score = result.experience_relevance_score
                item.explanation, item.posting_evidence = result.explanation, result.posting_evidence
            current.updated_at = datetime.now().isoformat()
            return current
        self.working.update(id, apply)
        return RescoreResponse(section_index=request.section_index, items=results)

    def create_submission(self, request):
        job = self.completed_job(request.job_id)
        selected = request.artifact_ids or ([job.result.artifacts[-1]["id"]] if job.result.artifacts else [])
        if not selected:
            raise OperationError(409, "Render artifacts before creating a submission")
        available = {artifact["id"] for artifact in job.result.artifacts}
        if any(id not in available for id in selected):
            raise OperationError(400, "Artifact does not belong to this job")
        records = [self.artifacts.for_artifact(job.id, id) for id in selected]
        if any(record is None for record in records):
            raise OperationError(409, "Historical artifact has no render snapshot; render again before submission")
        record = records[0]
        if any(other.id != record.id for other in records):
            raise OperationError(409, "Select artifacts from a single render operation")
        artifacts = ([artifact for artifact in record.artifacts if artifact["id"] in selected]
                     if request.artifact_ids else record.artifacts)
        now = datetime.now().isoformat()
        industry = (job.job_analysis or {}).get("industry_and_position_analysis", {})
        scoring = record.scoring_snapshot.model_dump(mode="json")
        scoring["working_copy"] = record.working_copy.model_dump(mode="json")
        return self.submissions.save(Submission(id=str(uuid4()), job_id=job.id,
            company=industry.get("company_name") or "", job_title=industry.get("job_title") or "",
            overall_score=record.scoring_snapshot.overall_score, job_entered_at=job.created_at.isoformat(),
            submitted_at=now, notes=request.notes, cv_snapshot=record.cv_snapshot.model_dump(mode="json"),
            scoring_snapshot=scoring, artifacts=artifacts, created_at=now, updated_at=now))
