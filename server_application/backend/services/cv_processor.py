"""
CV Processing service that wraps the existing CV customization logic.
"""
import os
import asyncio
from typing import Optional, Dict, Any

from core.paths import CV_DATA_DIR, ARTIFACTS_DIR, ensure_data_dirs, ensure_project_root_on_path

ensure_project_root_on_path()
ensure_data_dirs()

from src.utils import JobPostAnalysis, FullCVDocument, DocSectionItem, DocSection
from src.utils_cross_analysis import CVCrossAnalyzer
from src.models import ModelFactory
from src.cv_storage import find_cv_file, load_cv_file
from src.domain import CVData
from src.template_registry import resolve_cv_templates

from models.api_models import (
    CVJobResult, BackendConfig, JobStatus, ProcessingOutput
)


class CVProcessor:
    """Processes CVs based on job descriptions."""
    
    def __init__(self, candidate: str = "charilaos_mylonas", config: Optional[BackendConfig] = None, cv_version_id: str = "master"):
        """  init  .

        Args:
            candidate: TODO: describe.
            config: TODO: describe.
            cv_version_id: TODO: describe.

        Returns:
            TODO: describe return value.
        """
        self.candidate = candidate
        self.config = config or BackendConfig()
        self.cv_version_id = cv_version_id
        
    def _load_cv_data(self) -> CVData:
        """Load the candidate's CV data from the versioned storage."""
        path = find_cv_file(CV_DATA_DIR, self.candidate, self.cv_version_id)
        return load_cv_file(path, self.candidate)
    
    def _create_model_factory(self, model_config) -> ModelFactory:
        """Create a ModelFactory from config."""
        return ModelFactory(
            model_provider=model_config.provider,
            model_str=model_config.model,
            config=model_config.config
        )
    
    async def process(
        self, 
        job_description: str,
        job_id: str,
        status_callback=None
    ) -> ProcessingOutput:
        """Process a CV against a job description."""
        
        if status_callback:
            await status_callback(job_id, JobStatus.PROCESSING, "Analyzing job description...")
        
        # Save job description to temp file
        job_desc_path = f"current_text_file_{job_id}.txt"
        with open(job_desc_path, 'w') as f:
            f.write(job_description)
        
        try:
            # Analyze job posting
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Analyzing job posting...")
            
            jpa = JobPostAnalysis(job_desc_path)
            await jpa.analyze()
            
            # Load CV data
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Loading CV data...")
            
            cv_data = resolve_cv_templates(self._load_cv_data())
            
            # Create document sections
            experience_fields = [i.model_dump() for i in cv_data.experience_sections]
            master_personal_statement = cv_data.personal_statement
            alternative_statements = cv_data.alternative_statements
            
            doc_section_items = [DocSectionItem(**_d) for _d in experience_fields]
            doc_section = DocSection(cv_data.cv_template.experience_section_title, doc_section_items)
            
            # Initial full CV document with master statement
            fcv = FullCVDocument(master_personal_statement, doc_section, cv_template=cv_data.cv_template)
            
            # Perform cross-analysis
            cvca = CVCrossAnalyzer(jpa, fcv)
            
            # 1. Rewrite personal statement if alternatives are provided
            if alternative_statements:
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, "Optimizing personal statement...")
                
                # We add the master statement to the alternatives to consider it too
                all_statements = alternative_statements + [master_personal_statement]
                await cvca.analyze_rewrite_personal_statement(all_statements)
                
                # Update document with optimized statement
                optimized_statement = cvca.data.get('edited_statement')
                if optimized_statement:
                    fcv.statement = optimized_statement
            
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Cross-analyzing CV with job description (parallel)...")
            
            async def progress_wrapper(msg):
                """Progress wrapper.

                Args:
                    msg: TODO: describe.

                Returns:
                    TODO: describe return value.
                """
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, msg)

            # Perform experience analysis (parallel fan-out)
            # Re-initialize cvca with potentially updated fcv
            cvca = CVCrossAnalyzer(jpa, fcv)
            await cvca.analyze_job_experience_section(
                concurrency_limit=self.config.concurrency_limit,
                progress_callback=progress_wrapper
            )
            
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Generating optimized CV...")
            
            # Apply rewrite policies
            rewrite_policy = self.config.rewrite_policy
            # rewrite_reviewed_experience_section is still synchronous string manipulation
            await asyncio.to_thread(
                cvca.rewrite_reviewed_experience_section,
                min_section_items_keep=rewrite_policy.min_section_items_keep,
                max_section_items_keep=rewrite_policy.max_section_items_keep,
                min_relevance_score=rewrite_policy.min_relevance_score
            )
            
            # Selection never destroys the complete source analysis or reruns it.
            agg_metrics_tuple = await asyncio.to_thread(cvca.get_section_aggregate_metrics)
            agg_metrics_summary = agg_metrics_tuple[0]
            
            # Generate output artifacts
            artifacts = []
            artifacts_dir = ARTIFACTS_DIR
            os.makedirs(artifacts_dir, exist_ok=True)
            
            # Generate PDF if configured
            if self.config.outputs.render_pdf:
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, "Generating PDF...")
                pdf_path = os.path.join(artifacts_dir, f"cv_output_{job_id}.pdf")
                # render_pdf might also be blocking
                document = cvca.render_document(include_scoring_comments=self.config.outputs.include_scoring_comments)
                await asyncio.to_thread(document.render_pdf, pdf_path,
                                        include_scoring_comments=self.config.outputs.include_scoring_comments)
                artifacts.append({
                    "id": f"pdf_{job_id}",
                    "kind": "pdf",
                    "filename": "generated_cv.pdf",
                    "path": pdf_path
                })
            
            # Generate LaTeX if configured
            if self.config.outputs.include_latex:
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, "Generating LaTeX...")
                
                document = cvca.render_document(include_scoring_comments=self.config.outputs.include_scoring_comments)
                latex_content = await asyncio.to_thread(document.make_latex,
                                                       include_scoring_comments=self.config.outputs.include_scoring_comments)
                latex_path = os.path.join(artifacts_dir, f"cv_output_{job_id}.tex")
                with open(latex_path, 'w') as f:
                    f.write(latex_content)
                artifacts.append({
                    "id": f"latex_{job_id}",
                    "kind": "latex",
                    "filename": "generated_cv.tex",
                    "path": latex_path
                })
            
            # Build result
            sections = []
            for role in cvca.snapshot.roles:
                assessment = role.assessment
                bullet_items = [{
                    "id": bullet.id, "text": bullet.text,
                    "relevance_score": bullet.assessment.experience_relevance_score if bullet.assessment else None,
                    "explanation": bullet.assessment.explanation if bullet.assessment else None,
                    "posting_evidence": bullet.assessment.posting_evidence if bullet.assessment else None,
                    "kept": bullet.id in cvca.selected_ids,
                } for bullet in role.items]

                sections.append({
                    "id": role.id,
                    "title": cvca.source_cv.experience_section.section_title,
                    "company": role.company,
                    "position": role.position,
                    "duration": role.duration,
                    "section_score": assessment.experience_relevance_score if assessment else None,
                    "explanation": assessment.explanation if assessment else None,
                    "posting_evidence": assessment.posting_evidence if assessment else None,
                    "items": bullet_items
                })
            
            result_data = {
                "personal_statement": cvca.cv_model.statement,
                "sections": sections,
                "overall_score": agg_metrics_summary.get('weighted_mean_section_relevance'),
                "summary_metrics": agg_metrics_summary,
                "artifacts": artifacts
            }
            
            # Cleanup
            if os.path.exists(job_desc_path):
                os.remove(job_desc_path)
            
            return ProcessingOutput(result=CVJobResult.model_validate(result_data), job_analysis=jpa.data)
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(job_desc_path):
                os.remove(job_desc_path)
            raise e
