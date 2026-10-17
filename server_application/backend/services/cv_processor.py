"""HTTP job adapter around the shared application pipeline."""

from uuid import uuid4
from core.paths import CV_DATA_DIR, ARTIFACTS_DIR
from src.cv_storage import find_cv_file, load_cv_file
from src.config import BackendConfig
from src.pipeline import analyze_cv
from src.artifacts import render_artifacts
from models.api_models import CVJobResult, JobStatus, ProcessingOutput


class CVProcessor:
    def __init__(self, candidate="charilaos_mylonas", config=None, cv_version_id="master"):
        self.candidate = candidate
        self.config = config or BackendConfig()
        self.cv_version_id = cv_version_id

    def _load_cv_data(self):
        return load_cv_file(find_cv_file(CV_DATA_DIR, self.candidate, self.cv_version_id), self.candidate)

    async def process(self, job_description, job_id, status_callback=None) -> ProcessingOutput:
        async def progress(message):
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, message)

        run = await analyze_cv(self._load_cv_data(), job_description, self.config, progress_callback=progress)
        await progress("Rendering selected CV outputs...")
        import asyncio
        artifacts = await asyncio.to_thread(
            render_artifacts, run.analyzer.render_document(self.config.outputs.include_scoring_comments),
            ARTIFACTS_DIR, f"cv_output_{job_id}_{uuid4().hex}",
            render_pdf=self.config.outputs.render_pdf, include_latex=self.config.outputs.include_latex,
            include_scoring_comments=self.config.outputs.include_scoring_comments,
        )
        sections = []
        for role in run.analyzer.snapshot.roles:
            assessment = role.assessment
            sections.append({
                "id": role.id, "title": run.source.cv_template.experience_section_title,
                "company": role.company, "position": role.position, "duration": role.duration,
                "section_score": assessment.experience_relevance_score if assessment else None,
                "explanation": assessment.explanation if assessment else None,
                "posting_evidence": assessment.posting_evidence if assessment else None,
                "items": [{
                    "id": item.id, "text": item.text, "kept": item.id in run.analyzer.selected_ids,
                    "relevance_score": item.assessment.experience_relevance_score if item.assessment else None,
                    "explanation": item.assessment.explanation if item.assessment else None,
                    "posting_evidence": item.assessment.posting_evidence if item.assessment else None,
                } for item in role.items],
            })
        metrics = run.analyzer.get_section_aggregate_metrics()[0]
        result = CVJobResult(personal_statement=run.analyzer.cv_model.statement, sections=sections,
                             overall_score=metrics['weighted_mean_section_relevance'],
                             summary_metrics=metrics, artifacts=artifacts)
        return ProcessingOutput(result=result, job_analysis=run.job.data)
