"""
CV Processing service that wraps the existing CV customization logic.
"""
import os
import sys
import json
import asyncio
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
    
    def __init__(self, candidate: str = "charilaos_mylonas", config: Optional[BackendConfig] = None):
        self.candidate = candidate
        self.config = config or BackendConfig()
        self.candidate_cv_data_path = os.path.join(
            CV_CUSTOMIZER_ROOT, 'server_application/backend/cv_section_data', 
            f'{candidate}_cv_data.json'
        )
        
    def _load_cv_data(self) -> Dict[str, Any]:
        """Load the candidate's CV data."""
        with open(self.candidate_cv_data_path, 'r') as f:
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
            jpa.analyze()
            
            # Load CV data
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Loading CV data...")
            
            cv_data = self._load_cv_data()
            
            # Create document sections
            experience_fields = cv_data.get('experience_sections', [])
            personal_statement = cv_data.get('personal_statement', '')
            
            doc_section_items = [DocSectionItem(**_d) for _d in experience_fields]
            doc_section = DocSection('Work Experience', doc_section_items)
            
            # Create full CV document
            fcv = FullCVDocument(personal_statement, doc_section)
            
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Cross-analyzing CV with job description...")
            
            # Perform cross-analysis
            cvca = CVCrossAnalyzer(jpa, fcv)
            cvca.analyze_job_experience_section()
            
            if status_callback:
                await status_callback(job_id, JobStatus.PROCESSING, "Generating optimized CV...")
            
            # Apply rewrite policies
            rewrite_policy = self.config.rewrite_policy
            cvca.rewrite_reviewed_experience_section(
                max_section_items_keep=rewrite_policy.max_section_items_keep,
                min_relevance_score=rewrite_policy.min_relevance_score
            )
            
            # Get results
            cvca.analyze_job_experience_section()
            agg_metrics = cvca.get_section_aggregate_metrics()
            
            # Generate output artifacts
            artifacts = []
            
            # Generate PDF if configured
            if self.config.outputs.render_pdf:
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, "Generating PDF...")
                pdf_path = f"cv_output_{job_id}.pdf"
                cvca.cv_model.copy().render_pdf(pdf_path)
                artifacts.append({
                    "type": "pdf",
                    "name": "generated_cv.pdf",
                    "path": pdf_path
                })
            
            # Generate LaTeX if configured
            if self.config.outputs.include_latex:
                if status_callback:
                    await status_callback(job_id, JobStatus.PROCESSING, "Generating LaTeX...")
                latex_content = cvca.cv_model.get_latex()
                latex_path = f"cv_output_{job_id}.tex"
                with open(latex_path, 'w') as f:
                    f.write(latex_content)
                artifacts.append({
                    "type": "latex",
                    "name": "generated_cv.tex",
                    "path": latex_path
                })
            
            # Build result
            sections = []
            for section in cvca.cv_model.sections:
                items = []
                for item in section.doc_section_items:
                    items.append(ExperienceItem(
                        company=item.company,
                        duration=item.duration,
                        position=item.position,
                        text_items=[li.text for li in item.section_item_list],
                        score=getattr(item, 'relevance_score', None),
                        explanation=getattr(item, 'explanation', None),
                        kept=True
                    ))
                
                section_result = SectionResult(
                    title=section.section_title,
                    items=items,
                    aggregate_score=agg_metrics.get(section.section_title, {}).get('average_score', None)
                )
                sections.append(section_result)
            
            result = CVJobResult(
                personal_statement=cvca.cv_model.personal_statement,
                sections=sections,
                overall_score=agg_metrics.get('overall_score', None),
                artifacts=artifacts
            )
            
            # Cleanup
            if os.path.exists(job_desc_path):
                os.remove(job_desc_path)
            
            return result
            
        except Exception as e:
            # Cleanup on error
            if os.path.exists(job_desc_path):
                os.remove(job_desc_path)
            raise e
