"""
CV Processing service that wraps the existing CV customization logic.
"""
import os
import sys
import json
import asyncio
import shutil
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add the project root to the path
CV_CUSTOMIZER_ROOT = os.getenv('CV_CUSTOMIZER_ROOT', '/home/charilaos/Workspace/auto_cv')
if CV_CUSTOMIZER_ROOT not in sys.path:
    sys.path.append(CV_CUSTOMIZER_ROOT)

from src.utils import JobPostAnalysis, FullCVDocument, DocSectionItem, DocSection
from src.utils_cross_analysis import CVCrossAnalyzer
from src.models import ModelFactory

from models.api_models import (
    CVJobResult, SectionResult, ExperienceItem, 
    BackendConfig, JobStatus
)


class CVProcessor:
    """Processes CVs based on job descriptions."""
    
    def __init__(self, candidate: str = "charilaos_mylonas", config: Optional[BackendConfig] = None, cv_version_id: str = "master"):
        self.candidate = candidate
        self.config = config or BackendConfig()
        self.cv_version_id = cv_version_id
        
    def _load_cv_data(self) -> Dict[str, Any]:
        """Load the candidate's CV data from the versioned storage."""
        candidate_dir = os.path.join(
            CV_CUSTOMIZER_ROOT, 'server_application/backend/cv_section_data', 
            self.candidate
        )
        # Ensure dir exists (it will be created by the API, but let's be safe)
        if not os.path.exists(candidate_dir):
            os.makedirs(candidate_dir, exist_ok=True)
            
        path = os.path.join(candidate_dir, f'{self.cv_version_id}.json')
        
        # Fallback to legacy path if master doesn't exist
        if not os.path.exists(path) and self.cv_version_id == "master":
            legacy_path = os.path.join(
                CV_CUSTOMIZER_ROOT, 'server_application/backend/cv_section_data', 
                f'{self.candidate}_cv_data.json'
            )
            if os.path.exists(legacy_path):
                # Migrate to new location
                shutil.copy(legacy_path, path)
            else:
                raise FileNotFoundError(f"CV data not found for candidate {self.candidate}")
        
        if not os.path.exists(path):
             raise FileNotFoundError(f"CV version '{self.cv_version_id}' not found for candidate {self.candidate}")

        with open(path, 'r') as f:
            return json.load(f)
    
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
    ) -> CVJobResult:
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
            
            cv_data = self._load_cv_data()
            
            # Create document sections
            experience_fields = cv_data.get('experience_sections', [])
            master_personal_statement = cv_data.get('personal_statement', '')
            alternative_statements = cv_data.get('alternative_statements', [])
            
            doc_section_items = [DocSectionItem(**_d) for _d in experience_fields]
            doc_section = DocSection('Work Experience', doc_section_items)
            
            # Initial full CV document with master statement
            fcv = FullCVDocument(master_personal_statement, doc_section)
            
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
                max_section_items_keep=rewrite_policy.max_section_items_keep,
                min_relevance_score=rewrite_policy.min_relevance_score
            )
            
            # Get results
            # Update metrics after rewrite
            await cvca.analyze_job_experience_section(
                concurrency_limit=self.config.concurrency_limit,
                progress_callback=progress_wrapper
            )
            agg_metrics_tuple = await asyncio.to_thread(cvca.get_section_aggregate_metrics)
            agg_metrics_summary = agg_metrics_tuple[0]
            
            # Generate output artifacts
            artifacts = []
            artifacts_dir = os.path.join(CV_CUSTOMIZER_ROOT, 'server_application/backend/artifacts')
            os.makedirs(artifacts_dir, exist_ok=True)
            
            # Generate PDF if configured
            if self.config.outputs.render_pdf:
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, "Generating PDF...")
                pdf_path = os.path.join(artifacts_dir, f"cv_output_{job_id}.pdf")
                # render_pdf might also be blocking
                cv_copy = cvca.cv_model.copy()
                await asyncio.to_thread(cv_copy.render_pdf, pdf_path)
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
                
                latex_content = await asyncio.to_thread(cvca.cv_model.make_latex)
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
            # We treat each DocSectionItem as a section for the frontend's benefit
            experience_section = cvca.cv_model.experience_section
            analysis_data = cvca.data.get('experience_section_analysis', {})
            full_section_analysis = analysis_data.get('full_section_analysis', {})
            by_item_analysis = analysis_data.get('by_section_item_analysis', {})
            
            for item in experience_section.doc_section_items:
                item_analysis = full_section_analysis.get(item, {})
                
                # Extract score and explanation
                score = None
                explanation = None
                if isinstance(item_analysis, dict):
                    score = item_analysis.get('experience_relevance_score')
                    explanation = item_analysis.get('explanation')
                elif isinstance(item_analysis, list) and len(item_analysis) > 0:
                    score = item_analysis[0].get('experience_relevance_score')
                    explanation = item_analysis[0].get('explanation')
                
                # Get individual bullet point analyses
                bullet_items = []
                item_bullets_analysis = by_item_analysis.get(item, {})
                for bullet in item.section_item_list:
                    bullet_analysis = item_bullets_analysis.get(bullet, {})
                    bullet_score = None
                    bullet_explanation = None
                    bullet_evidence = None
                    if isinstance(bullet_analysis, dict):
                        bullet_score = bullet_analysis.get('experience_relevance_score')
                        bullet_explanation = bullet_analysis.get('explanation')
                        bullet_evidence = bullet_analysis.get('posting_evidence')
                    
                    bullet_items.append({
                        "text": bullet.text,
                        "relevance_score": bullet_score,
                        "explanation": bullet_explanation,
                        "posting_evidence": bullet_evidence,
                        "kept": True # Since it was kept in the filtered list
                    })

                sections.append({
                    "title": experience_section.section_title,
                    "company": item.company,
                    "position": item.position,
                    "duration": item.duration,
                    "section_score": score,
                    "explanation": explanation,
                    "items": bullet_items
                })
            
            result_data = {
                "personal_statement": cvca.cv_model.statement,
                "sections": sections,
                "overall_score": agg_metrics_summary.get('weighted_mean_section_relevance'),
                "summary_metrics": agg_metrics_summary,
                "artifacts": artifacts
            }
            
            # We'll return a dict that matches what the frontend wants more closely, 
            # even if it slightly deviates from the Pydantic model (FastAPI will serialize it)
            # Actually, let's just make sure it's a valid dict.
            
            # Cleanup
            if os.path.exists(job_desc_path):
                os.remove(job_desc_path)
            
            return result_data, jpa.data
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(job_desc_path):
                os.remove(job_desc_path)
            raise e
