"""
Pydantic models for the CV Customizer API.
"""
from pydantic import BaseModel, ConfigDict, Field, with_config, model_validator
from typing import Optional, Dict, Any, List, Literal
from typing_extensions import TypedDict, NotRequired
from datetime import datetime
from enum import Enum
from uuid import uuid4
from src.artifacts import Artifact
from src.config import ModelConfig, RewritePolicy, AnalysisPolicy, OutputsConfig, BackendConfig
from src.domain import CVData


class APIModel(BaseModel):
    """New API data is validated, never silently truncated or retained malformed."""
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, validate_assignment=True)


@with_config(ConfigDict(extra="forbid", allow_inf_nan=False))
class ResultItem(TypedDict):
    id: NotRequired[str]
    text: str
    relevance_score: NotRequired[float | None]
    explanation: NotRequired[str | None]
    posting_evidence: NotRequired[str | None]
    kept: NotRequired[bool]


@with_config(ConfigDict(extra="forbid"))
class BasicJobAnalysis(TypedDict, total=False):
    skills: str
    qualifications: str
    preferred_qualifications: str | None


@with_config(ConfigDict(extra="forbid", allow_inf_nan=False))
class IndustryJobAnalysis(TypedDict, total=False):
    company_name: str | None
    industry: str | None
    job_title: str
    business_skills: float
    hands_on_skills: float


@with_config(ConfigDict(extra="forbid"))
class FieldProvenance(TypedDict):
    status: Literal["success", "fallback"]
    method: str
    reason: NotRequired[str]


@with_config(ConfigDict(extra="forbid"))
class JobAnalysis(TypedDict, total=False):
    basic_analysis: BasicJobAnalysis
    industry_and_position_analysis: IndustryJobAnalysis
    provenance: Dict[str, FieldProvenance]


class JobStatus(str, Enum):
    """JobStatus model."""
    QUEUED = "queued"
    PROCESSING = "processing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CreateJobRequest(APIModel):
    """CreateJobRequest model."""
    job_description: str
    candidate: str = "charilaos_mylonas"
    cv_version_id: str = "master"
    config: Optional[BackendConfig] = None


class JobAnalysisRequest(APIModel):
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


class SectionResult(APIModel):
    """SectionResult model."""
    title: str
    id: Optional[str] = None
    company: Optional[str] = None
    position: Optional[str] = None
    duration: Optional[str] = None
    section_score: Optional[float] = None
    explanation: Optional[str] = None
    posting_evidence: Optional[str] = None
    items: List[ResultItem] = Field(default_factory=list)
    aggregate_score: Optional[float] = None


class CVJobResult(APIModel):
    """CVJobResult model."""
    personal_statement: Optional[str] = None
    sections: List[SectionResult]
    overall_score: Optional[float] = None
    summary_metrics: Optional[Dict[str, float | None]] = None
    artifacts: List[Artifact] = Field(default_factory=list)


class ProcessingOutput(APIModel):
    """The processor returns analysis and result explicitly, not an untyped tuple."""
    result: CVJobResult
    job_analysis: JobAnalysis
    rendered_cv: Optional[CVData] = None


class JobAnalysisResponse(APIModel):
    job_analysis: JobAnalysis


class StreamError(APIModel):
    id: str
    error: str


class CVJobResponse(APIModel):
    """CVJobResponse model."""
    id: str
    status: JobStatus
    effective_config: Optional[BackendConfig] = None
    candidate: str = "charilaos_mylonas"
    cv_version_id: Optional[str] = None
    cv_snapshot: Optional[CVData] = None
    archived: bool = False
    job_description: Optional[str] = None
    progress: Optional[str] = None
    message: Optional[str] = None
    result: Optional[CVJobResult] = None
    job_analysis: Optional[JobAnalysis] = None
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SectionFilterConfig(APIModel):
    """Per-section filtering thresholds."""
    min_relevance_score: int = 3
    min_items_keep: int = 1
    max_items_keep: int = 6


class WorkingCopyItem(APIModel):
    """A single bullet item in a working copy section."""
    text: str
    id: str = Field(default_factory=lambda: str(uuid4()))
    scored_text: Optional[str] = None
    original_text: str = ""
    relevance_score: Optional[float] = None
    explanation: Optional[str] = None
    posting_evidence: Optional[str] = None
    kept: bool = True


class WorkingCopySection(APIModel):
    """A single experience section in a working copy."""
    company: str = ""
    id: str = Field(default_factory=lambda: str(uuid4()))
    position: str = ""
    duration: str = ""
    section_score: Optional[float] = None
    section_explanation: Optional[str] = None
    section_posting_evidence: Optional[str] = None
    filter_config: SectionFilterConfig = Field(default_factory=SectionFilterConfig)
    items: List[WorkingCopyItem] = Field(default_factory=list)


class WorkingCopy(APIModel):
    """Working copy — an editable CV derived from an analysis result."""
    job_id: str
    personal_statement: str = ""
    sections: List[WorkingCopySection] = Field(default_factory=list)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RescoreItem(APIModel):
    """Item to rescore with optional new text."""
    index: int = Field(ge=0)
    text: Optional[str] = None


class RescoreRequest(APIModel):
    """Request to rescore specific items in a working copy."""
    section_index: int = Field(ge=0)
    item_indices: List[int] = Field(default_factory=list)
    items: Optional[List[RescoreItem]] = None


class RescoredItemResult(APIModel):
    """Result of rescoring a single item."""
    index: int
    relevance_score: float
    explanation: str
    posting_evidence: str
    scored_text: str


class RescoreResponse(APIModel):
    """Response from rescoring operation."""
    section_index: int
    items: List[RescoredItemResult]


class RenderCVRequest(APIModel):
    """RenderCVRequest model."""
    min_relevance_score: int = Field(default=4, ge=0, le=10)
    min_section_items_keep: int = Field(default=1, ge=0)
    max_section_items_keep: int = Field(default=5, ge=0)
    cv_template_id: str = "default_cv"
    cv_template_path: Optional[str] = None
    include_latex: bool = True
    render_pdf: bool = True
    include_scoring_comments: bool = False
    working_copy: Optional[WorkingCopy] = None

    @model_validator(mode="after")
    def valid_limits(self):
        if self.min_section_items_keep > self.max_section_items_keep:
            raise ValueError("minimum items cannot exceed maximum items")
        return self


class SubmissionCreateRequest(APIModel):
    """Request to create a submission from a completed job."""
    job_id: str
    artifact_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class SubmissionUpdateRequest(APIModel):
    """Request to update a submission's result."""
    result: Optional[str] = None  # INTERVIEW, REJECTED, OFFER, NO_RESPONSE, WITHDREW
    notes: Optional[str] = None


class Submission(APIModel):
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
    artifacts: List[Artifact] = Field(default_factory=list)
    created_at: str
    updated_at: str


class RenderRecord(APIModel):
    """Immutable source/selection/scoring provenance for one render operation."""
    id: str
    job_id: str
    artifacts: List[Artifact]
    cv_snapshot: CVData
    working_copy: WorkingCopy
    scoring_snapshot: CVJobResult
    created_at: str
