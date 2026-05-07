"""
Pydantic models for the CV Customizer API.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class JobStatus(str, Enum):
    """JobStatus model."""
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ModelConfig(BaseModel):
    """ModelConfig model."""
    provider: str = "ollama"
    model: str = "gemma4:31b"
    config: Optional[Dict[str, Any]] = None


class RewritePolicy(BaseModel):
    """RewritePolicy model."""
    max_section_items_keep: int = 5
    min_section_items_keep: int = 1
    min_relevance_score: int = 4


class AnalysisPolicy(BaseModel):
    """AnalysisPolicy model."""
    max_section_parse_retries: int = 3


class OutputsConfig(BaseModel):
    """OutputsConfig model."""
    include_cover_letter: bool = False
    render_pdf: bool = True
    include_latex: bool = True
    include_scoring_comments: bool = True


class BackendConfig(BaseModel):
    """BackendConfig model."""
    analysis_model: ModelConfig = Field(default_factory=lambda: ModelConfig())
    statement_editor_model: ModelConfig = Field(default_factory=lambda: ModelConfig())
    cover_letter_editor_model: ModelConfig = Field(default_factory=lambda: ModelConfig())
    rewrite_policy: RewritePolicy = Field(default_factory=lambda: RewritePolicy())
    analysis_policy: AnalysisPolicy = Field(default_factory=lambda: AnalysisPolicy())
    outputs: OutputsConfig = Field(default_factory=lambda: OutputsConfig())
    concurrency_limit: int = 5


class CreateJobRequest(BaseModel):
    """CreateJobRequest model."""
    job_description: str
    candidate: str = "charilaos_mylonas"
    cv_version_id: str = "master"
    config: Optional[BackendConfig] = None


class JobAnalysisRequest(BaseModel):
    """JobAnalysisRequest model."""
    job_description: str
    candidate: str = "charilaos_mylonas"
    config: Optional[BackendConfig] = None


class ExperienceItem(BaseModel):
    """ExperienceItem model."""
    company: str
    duration: str
    position: str
    text_items: List[str]
    score: Optional[float] = None
    explanation: Optional[str] = None
    kept: Optional[bool] = True


class SectionResult(BaseModel):
    """SectionResult model."""
    title: str
    company: Optional[str] = None
    position: Optional[str] = None
    duration: Optional[str] = None
    section_score: Optional[float] = None
    explanation: Optional[str] = None
    items: List[Dict[str, Any]] = Field(default_factory=list)
    aggregate_score: Optional[float] = None


class CVJobResult(BaseModel):
    """CVJobResult model."""
    personal_statement: Optional[str] = None
    sections: List[SectionResult]
    overall_score: Optional[float] = None
    summary_metrics: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)


class CVJobResponse(BaseModel):
    """CVJobResponse model."""
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


class SectionFilterConfig(BaseModel):
    """Per-section filtering thresholds."""
    min_relevance_score: int = 3
    min_items_keep: int = 1
    max_items_keep: int = 6


class WorkingCopyItem(BaseModel):
    """A single bullet item in a working copy section."""
    text: str
    original_text: str = ""
    relevance_score: Optional[float] = None
    explanation: Optional[str] = None
    posting_evidence: Optional[str] = None
    kept: bool = True


class WorkingCopySection(BaseModel):
    """A single experience section in a working copy."""
    company: str = ""
    position: str = ""
    duration: str = ""
    section_score: Optional[float] = None
    section_explanation: Optional[str] = None
    section_posting_evidence: Optional[str] = None
    filter_config: SectionFilterConfig = Field(default_factory=SectionFilterConfig)
    items: List[WorkingCopyItem] = Field(default_factory=list)


class WorkingCopy(BaseModel):
    """Working copy — an editable CV derived from an analysis result."""
    job_id: str
    personal_statement: str = ""
    sections: List[WorkingCopySection] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RescoreItem(BaseModel):
    """Item to rescore with optional new text."""
    index: int
    text: Optional[str] = None


class RescoreRequest(BaseModel):
    """Request to rescore specific items in a working copy."""
    section_index: int
    item_indices: List[int] = Field(default_factory=list)
    items: Optional[List[RescoreItem]] = None


class RescoredItemResult(BaseModel):
    """Result of rescoring a single item."""
    index: int
    relevance_score: float
    explanation: str
    posting_evidence: str


class RescoreResponse(BaseModel):
    """Response from rescoring operation."""
    section_index: int
    items: List[RescoredItemResult]


class RenderCVRequest(BaseModel):
    """RenderCVRequest model."""
    min_relevance_score: int = 4
    min_section_items_keep: int = 1
    max_section_items_keep: int = 5
    cv_template_id: str = "default_cv"
    cv_template_path: Optional[str] = None
    include_latex: bool = True
    render_pdf: bool = True
    working_copy: Optional[WorkingCopy] = None


class SubmissionCreateRequest(BaseModel):
    """Request to create a submission from a completed job."""
    job_id: str
    artifact_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class SubmissionUpdateRequest(BaseModel):
    """Request to update a submission's result."""
    result: Optional[str] = None  # INTERVIEW, REJECTED, OFFER, NO_RESPONSE, WITHDREW
    notes: Optional[str] = None


class Submission(BaseModel):
    """A CV submission — tracking a sent application."""
    id: str
    job_id: str
    company: str = ""
    job_title: str = ""
    overall_score: Optional[float] = None
    job_entered_at: Optional[str] = None
    submitted_at: Optional[str] = None
    result: Optional[str] = None
    notes: Optional[str] = None
    cv_snapshot: Optional[Dict[str, Any]] = None
    scoring_snapshot: Optional[Dict[str, Any]] = None
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str
    updated_at: str


class ArtifactResponse(BaseModel):
    """ArtifactResponse model."""
    id: str
    job_id: str
    type: str  # "pdf", "latex", "json", etc.
    name: str
    created_at: datetime
