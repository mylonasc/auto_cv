"""
API routes for CV job management.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from typing import List, Optional
import asyncio
import os
import glob
import tempfile

from models.api_models import (
    CreateJobRequest, CVJobResponse, JobStatus, CVJobResult, RenderCVRequest, JobAnalysisRequest,
    WorkingCopy, WorkingCopySection, WorkingCopyItem, SectionFilterConfig,
    RescoreRequest, RescoreResponse, RescoredItemResult, RescoreItem,
)
from jobs.job_manager import job_manager
from services.cv_processor import CVProcessor
from core.paths import ARTIFACTS_DIR, WORKING_CVS_DIR, ensure_data_dirs
from src.utils import FullCVDocument, DocSection, DocSectionItem
from src.domain import CVTemplateData
from src.template_registry import resolve_template_path
from src.utils import JobPostAnalysis
from src.models import ModelFactory
from src.utils_cross_analysis import BulletAnalysis, section_experience_analysis_prompt, _make_default_model
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime

ensure_data_dirs()

router = APIRouter(prefix="/v1/cv-jobs", tags=["CV Jobs"])

# Store active background tasks
active_tasks = {}


def _resolve_artifact_file_path(job_id: str, artifact: dict) -> Optional[str]:
    """Resolve the on-disk artifact path across environments."""
    artifacts_dir = ARTIFACTS_DIR
    kind = artifact.get("kind") or artifact.get("type") or "pdf"
    ext = "tex" if kind == "latex" else kind

    candidates = []
    stored_path = artifact.get("path")
    if stored_path:
        candidates.append(stored_path)
        candidates.append(os.path.join(artifacts_dir, os.path.basename(stored_path)))

    filename = artifact.get("filename")
    if filename:
        candidates.append(os.path.join(artifacts_dir, filename))

    name = artifact.get("name")
    if name:
        candidates.append(os.path.join(artifacts_dir, name))

    candidates.append(os.path.join(artifacts_dir, f"cv_output_{job_id}.{ext}"))

    wildcard_matches = glob.glob(os.path.join(artifacts_dir, f"cv_output_{job_id}.*"))
    candidates.extend(wildcard_matches)

    seen = set()
    for candidate in candidates:
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        if os.path.exists(candidate):
            return candidate

    return None


# ── Working Copy Helpers ──────────────────────────────────────────────

def _create_working_copy_from_job(job) -> WorkingCopy:
    """Derive a WorkingCopy from a completed job result."""
    result_obj = job.result.model_dump() if hasattr(job.result, "model_dump") else job.result
    if not isinstance(result_obj, dict):
        result_obj = {}
    sections = result_obj.get("sections", []) or []
    personal_statement = result_obj.get("personal_statement", "") or ""

    wc_sections = []
    for section in sections:
        items = section.get("items", []) or []
        wc_items = [
            WorkingCopyItem(
                text=it.get("text", ""),
                original_text=it.get("text", ""),
                relevance_score=it.get("relevance_score"),
                explanation=it.get("explanation"),
                posting_evidence=it.get("posting_evidence"),
                kept=it.get("kept", True),
            )
            for it in items
        ]
        wc_sections.append(WorkingCopySection(
            company=section.get("company", ""),
            position=section.get("position", ""),
            duration=section.get("duration", ""),
            section_score=section.get("section_score"),
            section_explanation=section.get("explanation"),
            section_posting_evidence=section.get("posting_evidence"),
            items=wc_items,
        ))

    now = datetime.now().isoformat()
    return WorkingCopy(
        job_id=job.id,
        personal_statement=personal_statement,
        sections=wc_sections,
        created_at=now,
        updated_at=now,
    )


def _save_working_copy_to_disk(working_copy: WorkingCopy):
    """Persist a WorkingCopy to disk."""
    import json
    os.makedirs(WORKING_CVS_DIR, exist_ok=True)
    path = os.path.join(WORKING_CVS_DIR, f"{working_copy.job_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        f.write(working_copy.model_dump_json(indent=2))


def _load_working_copy_from_disk(job_id: str) -> Optional[WorkingCopy]:
    """Load a WorkingCopy from disk, or None."""
    import json
    path = os.path.join(WORKING_CVS_DIR, f"{job_id}.json")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return WorkingCopy(**data)


def _render_from_working_copy(working_copy: WorkingCopy, request: RenderCVRequest, job_id: str) -> list:
    """Render PDF/LaTeX artifacts from a WorkingCopy directly."""
    doc_items = []
    for section in working_copy.sections:
        kept_texts = [item.text for item in section.items if item.kept]
        if kept_texts:
            doc_items.append(DocSectionItem(
                company=section.company,
                duration=section.duration,
                position=section.position,
                text_items=kept_texts,
            ))

    title = "Work Experience"
    experience_section = DocSection(title, doc_items)
    cv_template_path = resolve_template_path("cv_templates", request.cv_template_id, request.cv_template_path)
    cv_template = CVTemplateData(template_id=request.cv_template_id, template_path=cv_template_path)
    document = FullCVDocument(working_copy.personal_statement, experience_section, cv_template=cv_template)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    artifacts: list = []

    if request.render_pdf:
        pdf_name = f"cv_output_{job_id}_{request.cv_template_id}_{timestamp}.pdf"
        pdf_path = os.path.join(ARTIFACTS_DIR, pdf_name)
        document.copy().render_pdf(pdf_path)
        artifacts.append({
            "id": f"pdf_{job_id}_{timestamp}",
            "kind": "pdf",
            "filename": pdf_name,
            "path": pdf_path,
            "source": "working_copy",
        })

    if request.include_latex:
        tex_name = f"cv_output_{job_id}_{request.cv_template_id}_{timestamp}.tex"
        tex_path = os.path.join(ARTIFACTS_DIR, tex_name)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(document.make_latex())
        artifacts.append({
            "id": f"latex_{job_id}_{timestamp}",
            "kind": "latex",
            "filename": tex_name,
            "path": tex_path,
            "source": "working_copy",
        })

    return artifacts


async def status_callback(job_id: str, status: JobStatus, progress: Optional[str] = None, message: Optional[str] = None):
    """Callback to update job status."""
    # Check if cancelled
    job = job_manager.get_job(job_id)
    if job and job.status == JobStatus.CANCELLED:
        raise asyncio.CancelledError("Job was cancelled by user")
        
    job_manager.update_job_status(
        job_id=job_id,
        status=status,
        progress=progress,
        message=message
    )


async def process_job_background(job_id: str, request: CreateJobRequest):
    """Background task to process a CV job."""
    try:
        # Check if already cancelled
        job = job_manager.get_job(job_id)
        if not job or job.status == JobStatus.CANCELLED:
            return

        # Update status to processing
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress="Starting CV processing...",
            message="Initializing CV processor"
        )
        
        # Run processing
        processor = CVProcessor(
            candidate=request.candidate,
            config=request.config,
            cv_version_id=request.cv_version_id
        )

        
        # Process
        result, job_analysis = await processor.process(
            job_description=request.job_description,
            job_id=job_id,
            status_callback=status_callback
        )
        
        # Save result to job (keep as PROCESSING so SSE doesn't fire job_complete yet)
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.PROCESSING,
            progress="Creating working copy...",
            message="Saving analysis and creating editable working copy",
            result=result,
            job_analysis=job_analysis
        )

        # Auto-create working copy from the result BEFORE marking succeeded
        # (avoids race condition where frontend loads WC before it's on disk)
        try:
            saved_job = job_manager.get_job(job_id)
            if saved_job and saved_job.result:
                wc = _create_working_copy_from_job(saved_job)
                _save_working_copy_to_disk(wc)
        except Exception as wc_err:
            print(f"Warning: failed to auto-create working copy: {wc_err}")

        # Now mark as succeeded
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.SUCCEEDED,
            progress="Processing complete",
            message="CV has been successfully processed",
        )
        
    except asyncio.CancelledError:
        # Job was already marked as CANCELLED in status_callback or cancel_job endpoint
        pass
    except Exception as e:
        job_manager.update_job_status(
            job_id=job_id,
            status=JobStatus.FAILED,
            error=str(e),
            message=f"Processing failed: {str(e)}"
        )
    finally:
        # Clean up task reference
        if job_id in active_tasks:
            del active_tasks[job_id]


@router.post("/", response_model=CVJobResponse)
async def create_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    """
    Create a new CV processing job.
    
    - **job_description**: Text of the job posting
    - **candidate**: Candidate name (default: charilaos_mylonas)
    - **config**: Optional backend configuration
    """
    # Create job
    job = job_manager.create_job(candidate=request.candidate, job_description=request.job_description)
    
    # Store request for background task
    active_tasks[job.id] = request
    
    # Start background processing
    background_tasks.add_task(process_job_background, job.id, request)
    
    return job


@router.post("/job-analysis")
async def analyze_job_only(request: JobAnalysisRequest):
    """Analyze job posting only and return extracted job analysis."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as tf:
        tf.write(request.job_description)
        temp_path = tf.name

    try:
        llm_model = None
        if request.config and request.config.analysis_model:
            llm_model = ModelFactory(
                model_provider=request.config.analysis_model.provider,
                model_str=request.config.analysis_model.model,
                config=request.config.analysis_model.config,
            ).get_llm_model()

        jpa = JobPostAnalysis(temp_path, llm_model=llm_model)
        await jpa.analyze()
        return {"job_analysis": jpa.data}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


@router.get("/{job_id}", response_model=CVJobResponse)
async def get_job(job_id: str):
    """Get the status and details of a specific job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/cancel", response_model=CVJobResponse)
async def cancel_job(job_id: str):
    """Cancel a running or queued job."""
    success = job_manager.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Job cannot be cancelled (not found or already completed)")
    
    job = job_manager.get_job(job_id)
    return job


@router.post("/{job_id}/archive", response_model=CVJobResponse)
async def archive_job(job_id: str):
    """Archive a job to declutter history views."""
    job = job_manager.archive_job(job_id, archived=True)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/unarchive", response_model=CVJobResponse)
async def unarchive_job(job_id: str):
    """Restore an archived job."""
    job = job_manager.archive_job(job_id, archived=False)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.delete("/{job_id}")
async def delete_job(job_id: str):
    """Permanently delete a job from history."""
    success = job_manager.delete_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"ok": True, "job_id": job_id}


@router.get("/{job_id}/result", response_model=CVJobResult)
async def get_job_result(job_id: str):
    """Get the result of a completed job."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != JobStatus.SUCCEEDED:
        raise HTTPException(status_code=400, detail=f"Job is not completed (status: {job.status})")
    
    return job.result


@router.get("/", response_model=List[CVJobResponse])
async def list_jobs():
    """List all jobs."""
    return job_manager.list_jobs()


@router.get("/{job_id}/artifacts/{artifact_id}")
async def get_artifact(job_id: str, artifact_id: str, inline: bool = Query(default=False)):
    """Download a specific artifact from a job."""
    print(f"Artifact requested: job_id={job_id}, artifact_id={artifact_id}")
    job = job_manager.get_job(job_id)
    if not job or not job.result:
        print(f"Job or result not found for {job_id}")
        raise HTTPException(status_code=404, detail="Job or result not found")

    result_obj = job.result
    if isinstance(result_obj, dict):
        artifacts = result_obj.get("artifacts") or []
    else:
        artifacts = getattr(result_obj, "artifacts", None) or []

    if not isinstance(artifacts, list):
        artifacts = []
    
    # Try to find artifact by ID
    artifact = next((a for a in artifacts if isinstance(a, dict) and a.get("id") == artifact_id), None)
    
    if not artifact:
        # Fallback: maybe artifact_id is actually the kind (pdf/latex)
        artifact = next((a for a in artifacts if isinstance(a, dict) and (a.get("kind") == artifact_id or a.get("type") == artifact_id)), None)

    if not artifact:
        print(f"Artifact {artifact_id} not found in job {job_id}. Available IDs: {[a.get('id') for a in artifacts if isinstance(a, dict)]}")
        raise HTTPException(status_code=404, detail="Artifact not found")
    
    file_path = _resolve_artifact_file_path(job_id, artifact)
    if not file_path:
        expected_filename = artifact.get("filename") or artifact.get("name") or f"cv_output_{job_id}"
        print(f"Artifact file not found for job {job_id}, artifact {artifact_id}")
        raise HTTPException(status_code=404, detail=f"Artifact file '{expected_filename}' not found on disk")

    from fastapi.responses import FileResponse
    response_filename = artifact.get("filename") or artifact.get("name") or os.path.basename(file_path)
    lower = response_filename.lower()
    media_type = 'application/octet-stream'
    if lower.endswith('.pdf'):
        media_type = 'application/pdf'
    elif lower.endswith('.tex'):
        media_type = 'application/x-tex'

    headers = None
    if inline:
        headers = {"Content-Disposition": f'inline; filename="{response_filename}"'}

    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=response_filename,
        headers=headers
    )


@router.get("/{job_id}/stream")
async def stream_job_updates(job_id: str):
    """
    SSE endpoint for real-time job status updates.
    Returns a stream of events: job_update, job_complete, error
    """
    from fastapi.responses import StreamingResponse
    from utils.sse import job_status_stream
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return StreamingResponse(
        job_status_stream(job_id, job_manager),
        media_type="text/event-stream"
    )


# ── Working Copy Endpoints ────────────────────────────────────────────


@router.get("/{job_id}/working-cv", response_model=WorkingCopy)
async def get_working_copy(job_id: str):
    """Get the working copy for a job. Auto-creates from result if missing."""
    wc = _load_working_copy_from_disk(job_id)
    if wc:
        return wc

    # Auto-create from job result
    job = job_manager.get_job(job_id)
    if not job or not job.result:
        raise HTTPException(status_code=404, detail="Job not found or has no result")
    wc = _create_working_copy_from_job(job)
    _save_working_copy_to_disk(wc)
    return wc


@router.put("/{job_id}/working-cv", response_model=WorkingCopy)
async def save_working_copy(job_id: str, working_copy: WorkingCopy):
    """Save (overwrite) the working copy for a job."""
    working_copy.job_id = job_id
    working_copy.updated_at = datetime.now().isoformat()
    if not working_copy.created_at:
        working_copy.created_at = working_copy.updated_at
    _save_working_copy_to_disk(working_copy)
    return working_copy


@router.post("/{job_id}/working-cv/rescore", response_model=RescoreResponse)
async def rescore_working_copy_items(job_id: str, request: RescoreRequest):
    """Rescore specific items in a working copy, optionally with new text."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    wc = _load_working_copy_from_disk(job_id)
    if not wc:
        raise HTTPException(status_code=404, detail="Working copy not found")

    if request.section_index >= len(wc.sections):
        raise HTTPException(status_code=400, detail="Invalid section_index")

    section = wc.sections[request.section_index]

    # Determine which items to rescore (empty = all)
    indices = request.item_indices if request.item_indices else list(range(len(section.items)))

    # Build optional new-text map
    text_map: dict = {}
    if request.items:
        for ri in request.items:
            text_map[ri.index] = ri.text

    # Job posting context for the LLM
    job_analysis_data = job.job_analysis or {}
    job_post_data_str = str(job_analysis_data)

    # Create the analysis chain
    llm = _make_default_model()
    chain = ChatPromptTemplate.from_template(section_experience_analysis_prompt) | llm.with_structured_output(BulletAnalysis)

    results: list = []
    for idx in indices:
        if idx >= len(section.items):
            continue
        item = section.items[idx]
        text = text_map.get(idx, item.text)

        try:
            res = await chain.ainvoke({
                "cv_experience": text,
                "job_posting_data": job_post_data_str,
            })

            item.text = text
            item.relevance_score = res.experience_relevance_score
            item.explanation = res.explanation
            item.posting_evidence = res.posting_evidence

            results.append(RescoredItemResult(
                index=idx,
                relevance_score=res.experience_relevance_score,
                explanation=res.explanation,
                posting_evidence=res.posting_evidence,
            ))
        except Exception as e:
            print(f"Rescore failed for item {idx}: {e}")

    wc.updated_at = datetime.now().isoformat()
    _save_working_copy_to_disk(wc)

    return RescoreResponse(section_index=request.section_index, items=results)


# ── Render ────────────────────────────────────────────────────────────


@router.post("/{job_id}/render", response_model=CVJobResponse)
async def render_job_artifacts(job_id: str, request: RenderCVRequest):
    """Render CV artifacts from existing analysis or from a WorkingCopy."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # ── Branch: render from WorkingCopy when provided ──
    if request.working_copy:
        artifacts = _render_from_working_copy(request.working_copy, request, job_id)
        # Update job result artifacts
        result_obj = job.result.model_dump() if hasattr(job.result, "model_dump") else job.result
        if isinstance(result_obj, dict):
            existing = result_obj.get("artifacts", []) or []
            result_obj["artifacts"] = existing + artifacts
            job_manager.update_job_status(job_id=job_id, status=job.status, result=result_obj)
        updated = job_manager.get_job(job_id)
        if not updated:
            raise HTTPException(status_code=404, detail="Job not found after rendering")
        return updated

    # ── Legacy path: render from stored analysis ──
    if not job.result:
        raise HTTPException(status_code=404, detail="Job result not found")

    result_obj = job.result.model_dump() if hasattr(job.result, "model_dump") else job.result
    sections = result_obj.get("sections") if isinstance(result_obj, dict) else None
    if not sections:
        raise HTTPException(status_code=400, detail="Job has no section analysis to render from")

    doc_items = []
    for section in sections:
        raw_items = section.get("items") or []
        sorted_items = sorted(raw_items, key=lambda x: -(x.get("relevance_score") or 0))
        kept = []
        for item in sorted_items:
            score = item.get("relevance_score") or 0
            if len(kept) < request.min_section_items_keep or (
                len(kept) < request.max_section_items_keep and score >= request.min_relevance_score
            ):
                kept.append(item.get("text") or "")

        if not kept:
            kept = [it.get("text") or "" for it in sorted_items[:request.min_section_items_keep]]

        doc_items.append(
            DocSectionItem(
                company=section.get("company") or "",
                duration=section.get("duration") or "",
                position=section.get("position") or "",
                text_items=[t for t in kept if t],
            )
        )

    title = sections[0].get("title") if sections and isinstance(sections[0], dict) else "Work Experience"
    experience_section = DocSection(title or "Work Experience", doc_items)
    cv_template_path = resolve_template_path("cv_templates", request.cv_template_id, request.cv_template_path)
    cv_template = CVTemplateData(template_id=request.cv_template_id, template_path=cv_template_path)
    document = FullCVDocument(result_obj.get("personal_statement", ""), experience_section, cv_template=cv_template)

    os.makedirs(ARTIFACTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    artifacts = result_obj.get("artifacts", [])

    if request.render_pdf:
        pdf_name = f"cv_output_{job_id}_{request.cv_template_id}_{timestamp}.pdf"
        pdf_path = os.path.join(ARTIFACTS_DIR, pdf_name)
        document.copy().render_pdf(pdf_path)
        artifacts.append({
            "id": f"pdf_{job_id}_{timestamp}",
            "kind": "pdf",
            "filename": pdf_name,
            "path": pdf_path,
        })

    if request.include_latex:
        tex_name = f"cv_output_{job_id}_{request.cv_template_id}_{timestamp}.tex"
        tex_path = os.path.join(ARTIFACTS_DIR, tex_name)
        with open(tex_path, "w", encoding="utf-8") as f:
            f.write(document.make_latex())
        artifacts.append({
            "id": f"latex_{job_id}_{timestamp}",
            "kind": "latex",
            "filename": tex_name,
            "path": tex_path,
        })

    result_obj["artifacts"] = artifacts
    job_manager.update_job_status(job_id=job_id, status=job.status, result=result_obj)
    updated = job_manager.get_job(job_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Job not found after rendering")
    return updated
