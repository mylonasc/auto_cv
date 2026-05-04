"""
Pydantic models for the CV Customizer API.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelConfig(BaseModel):
    provider: str = "ollama"
    model: str = "gemma4:31b"
    config: Optional[Dict[str, Any]] = None


class RewritePolicy(BaseModel):
    max_section_items_keep: int = 5
    min_section_items_keep: int = 1
    min_relevance_score: int = 4


class AnalysisPolicy(BaseModel):
    max_section_parse_retries: int = 3


class OutputsConfig(BaseModel):
    include_cover_letter: bool = False
    render_pdf: bool = True
    include_latex: bool = True
    include_scoring_comments: bool = True


class BackendConfig(BaseModel):
    analysis_model: ModelConfig = Field(default_factory=lambda: ModelConfig())
    statement_editor_model: ModelConfig = Field(default_factory=lambda: ModelConfig())
    cover_letter_editor_model: ModelConfig = Field(default_factory=lambda: ModelConfig())
    rewrite_policy: RewritePolicy = Field(default_factory=lambda: RewritePolicy())
    analysis_policy: AnalysisPolicy = Field(default_factory=lambda: AnalysisPolicy())
    outputs: OutputsConfig = Field(default_factory=lambda: OutputsConfig())
    concurrency_limit: int = 5


class CreateJobRequest(BaseModel):
    job_description: str
    candidate: str = "charilaos_mylonas"
    cv_version_id: str = "master"
    config: Optional[BackendConfig] = None


class ExperienceItem(BaseModel):
    company: str
    duration: str
    position: str
    text_items: List[str]
    score: Optional[float] = None
    explanation: Optional[str] = None
    kept: Optional[bool] = True


class SectionResult(BaseModel):
    title: str
    company: Optional[str] = None
    position: Optional[str] = None
    duration: Optional[str] = None
    section_score: Optional[float] = None
    explanation: Optional[str] = None
    items: List[Dict[str, Any]] = []
    aggregate_score: Optional[float] = None


class CVJobResult(BaseModel):
    personal_statement: Optional[str] = None
    sections: List[SectionResult]
    overall_score: Optional[float] = None
    summary_metrics: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = []


class CVJobResponse(BaseModel):
    id: str
    status: JobStatus
    archived: bool = False
    job_description: Optional[str] = None
    progress: Optional[str] = None
    message: Optional[str] = None
    result: Optional[CVJobResult] = None
    job_analysis: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class ArtifactResponse(BaseModel):
    id: str
    job_id: str
    type: str  # "pdf", "latex", "json", etc.
    name: str
    created_at: datetime
