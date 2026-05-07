"""
API routes for CV submission tracking.
"""
import uuid
import json
import os
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from models.api_models import (
    Submission, SubmissionCreateRequest, SubmissionUpdateRequest,
)
from jobs.job_manager import job_manager
from core.paths import SUBMISSIONS_DIR, ensure_data_dirs

ensure_data_dirs()

router = APIRouter(prefix="/v1/submissions", tags=["Submissions"])


def _submission_path(submission_id: str) -> str:
    return os.path.join(SUBMISSIONS_DIR, f"{submission_id}.json")


def _load_all_submissions() -> List[Submission]:
    submissions = []
    if not os.path.exists(SUBMISSIONS_DIR):
        return submissions
    for filename in sorted(os.listdir(SUBMISSIONS_DIR), reverse=True):
        if filename.endswith(".json"):
            try:
                with open(os.path.join(SUBMISSIONS_DIR, filename), "r") as f:
                    data = json.load(f)
                    submissions.append(Submission(**data))
            except Exception as e:
                print(f"Error loading submission {filename}: {e}")
    return submissions


def _save_submission(submission: Submission):
    os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
    with open(_submission_path(submission.id), "w") as f:
        json.dump(submission.model_dump(mode="json"), f, default=str, indent=2)


@router.post("/", response_model=Submission)
async def create_submission(request: SubmissionCreateRequest):
    """Create a new submission from a completed job."""
    job = job_manager.get_job(request.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    now = datetime.now().isoformat()

    # Gather job-level metadata
    company = ""
    job_title = ""
    if job.job_analysis:
        jia = job.job_analysis.get("industry_and_position_analysis", {}) or {}
        company = jia.get("company_name", "") or ""
        job_title = jia.get("job_title", "") or ""

    # Gather scoring snapshot
    overall_score = None
    scoring_snapshot = None
    if job.result:
        overall_score = job.result.overall_score
        scoring_snapshot = job.result.model_dump(mode="json") if hasattr(job.result, "model_dump") else {}

    # Determine which artifacts to include
    all_artifacts = []
    if job.result and job.result.artifacts:
        if request.artifact_ids:
            all_artifacts = [a for a in job.result.artifacts if a.get("id") in request.artifact_ids]
        else:
            all_artifacts = job.result.artifacts

    # CV snapshot
    cv_snapshot = None
    if job.job_analysis:
        try:
            candidate_dir = os.path.join(
                os.path.dirname(SUBMISSIONS_DIR), "cv_section_data"
            )
            candidate_path = os.path.join(candidate_dir, "charilaos_mylonas", "master.json")
            if os.path.exists(candidate_path):
                with open(candidate_path, "r") as f:
                    cv_snapshot = json.load(f)
        except Exception:
            cv_snapshot = None

    job_entered_at = job.created_at.isoformat() if hasattr(job.created_at, "isoformat") else str(job.created_at)

    submission = Submission(
        id=str(uuid.uuid4()),
        job_id=request.job_id,
        company=company,
        job_title=job_title,
        overall_score=overall_score,
        job_entered_at=job_entered_at,
        submitted_at=now,
        result=None,
        notes=request.notes,
        cv_snapshot=cv_snapshot,
        scoring_snapshot=scoring_snapshot,
        artifacts=all_artifacts,
        created_at=now,
        updated_at=now,
    )

    _save_submission(submission)
    return submission


@router.get("/", response_model=List[Submission])
async def list_submissions():
    """List all submissions (most recent first)."""
    return _load_all_submissions()


@router.get("/{submission_id}", response_model=Submission)
async def get_submission(submission_id: str):
    """Get a single submission by ID."""
    path = _submission_path(submission_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Submission not found")
    with open(path, "r") as f:
        return Submission(**json.load(f))


@router.put("/{submission_id}", response_model=Submission)
async def update_submission(submission_id: str, request: SubmissionUpdateRequest):
    """Update a submission's result and/or notes."""
    path = _submission_path(submission_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Submission not found")
    with open(path, "r") as f:
        submission = Submission(**json.load(f))

    if request.result is not None:
        submission.result = request.result
    if request.notes is not None:
        submission.notes = request.notes
    submission.updated_at = datetime.now().isoformat()

    _save_submission(submission)
    return submission


@router.delete("/{submission_id}")
async def delete_submission(submission_id: str):
    """Delete a submission."""
    path = _submission_path(submission_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Submission not found")
    os.remove(path)
    return {"ok": True, "submission_id": submission_id}
