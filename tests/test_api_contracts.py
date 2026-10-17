"""New contracts validate strictly; historical compatibility is read-boundary only."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError


@pytest.mark.parametrize("result", [
    {},
    {"sections": [], "unexpected": "not silently dropped"},
    {"sections": [{"title": "Experience", "items": [{"text": "Work", "unknown": True}]}]},
    {"sections": [], "artifacts": [{"id": "a", "type": "pdf", "name": "old.pdf"}]},
    {"sections": [], "artifacts": [{"id": "a", "kind": "pdf"}]},
    {"sections": [], "overall_score": float("nan")},
])
def test_invalid_new_results_do_not_change_job_or_disk(result):
    from jobs.job_manager import job_manager
    from models.api_models import JobStatus

    job = job_manager.create_job()
    path = Path(job_manager.storage_dir) / f"{job.id}.json"
    before = path.read_bytes()
    with pytest.raises(ValidationError):
        job_manager.update_job_status(job.id, JobStatus.SUCCEEDED, result=result)
    assert job_manager.get_job(job.id).status == JobStatus.QUEUED
    assert job_manager.get_job(job.id).result is None
    assert path.read_bytes() == before


def test_legacy_artifacts_normalize_once_without_rewriting_source(tmp_path):
    from jobs.job_manager import JobManager
    from models.api_models import CVJobResult

    directory = tmp_path / "legacy-jobs"
    manager = JobManager(str(directory))
    job = manager.create_job()
    payload = job.model_dump(mode="json")
    payload["result"] = {"sections": [], "artifacts": [{
        "id": "pdf_legacy", "type": "pdf", "name": "legacy.pdf", "path": "/old/legacy.pdf",
    }]}
    path = directory / f"{job.id}.json"
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    restored = JobManager(str(directory)).get_job(job.id)
    assert restored.result.artifacts == [{
        "id": "pdf_legacy", "kind": "pdf", "filename": "legacy.pdf", "path": "/old/legacy.pdf",
    }]
    assert path.read_bytes() == original
    with pytest.raises(ValidationError):
        CVJobResult.model_validate(payload["result"])


def test_conflicting_legacy_artifacts_are_not_silently_resolved():
    from models.legacy import normalize_artifact

    payload = {"id": "a", "kind": "pdf", "type": "latex", "filename": "cv.pdf"}
    before = copy.deepcopy(payload)
    with pytest.raises(ValueError, match="Conflicting"):
        normalize_artifact(payload)
    assert payload == before


def test_artifact_resolution_does_not_fall_back_to_the_wrong_kind(isolated_runtime):
    from api.cv_jobs import _resolve_artifact_file_path

    (isolated_runtime / "artifacts" / "cv_output_job.pdf").write_bytes(b"%PDF")
    assert _resolve_artifact_file_path("job", {
        "id": "latex", "kind": "latex", "filename": "cv.tex",
    }) is None


def test_job_analysis_only_has_the_declared_response(client):
    from models.api_models import JobAnalysisResponse

    response = client.post("/v1/cv-jobs/job-analysis", json={"job_description": "Python engineer"})
    assert response.status_code == 200
    parsed = JobAnalysisResponse.model_validate(response.json())
    assert parsed.job_analysis["basic_analysis"]["skills"] == "Python; LangChain"


@pytest.mark.parametrize("status,error", [("failed", "model unavailable"), ("cancelled", None)])
def test_terminal_sse_payload_is_exactly_the_http_snapshot(client, status, error):
    from jobs.job_manager import job_manager
    from models.api_models import CVJobResponse

    job = job_manager.create_job()
    job_manager.update_job_status(job.id, status, error=error,
                                  job_analysis={"basic_analysis": {"skills": "Python"}})
    http = client.get(f"/v1/cv-jobs/{job.id}").json()
    stream = client.get(f"/v1/cv-jobs/{job.id}/stream").text
    frames = stream.strip().split("\n\n")
    for frame in frames:
        payload = json.loads(frame.splitlines()[1].removeprefix("data: "))
        assert payload == http
        assert CVJobResponse.model_validate(payload).id == job.id


def test_successful_job_contract_retains_section_and_bullet_evidence(client):
    from jobs.job_manager import job_manager
    from models.api_models import JobStatus

    job = job_manager.create_job()
    job_manager.update_job_status(job.id, JobStatus.SUCCEEDED, result={"sections": [{
        "title": "Experience", "posting_evidence": "Role evidence", "items": [{
            "text": "Work", "posting_evidence": "Bullet evidence", "relevance_score": 8,
        }],
    }]})
    payload = client.get(f"/v1/cv-jobs/{job.id}").json()
    assert payload["result"]["sections"][0]["posting_evidence"] == "Role evidence"
    assert payload["result"]["sections"][0]["items"][0]["posting_evidence"] == "Bullet evidence"


def test_shared_frontend_fixture_is_the_real_http_and_sse_contract(client):
    from jobs.job_manager import job_manager
    from models.api_models import CVJobResponse

    fixture = json.loads((Path(__file__).parent / "fixtures/job-contract.json").read_text())
    job = CVJobResponse.model_validate(fixture)
    job_manager._jobs[job.id] = job
    job_manager._save_job(job)
    assert client.get(f"/v1/cv-jobs/{job.id}").json() == fixture
    stream = client.get(f"/v1/cv-jobs/{job.id}/stream").text
    for frame in stream.strip().split("\n\n"):
        assert json.loads(frame.splitlines()[1].removeprefix("data: ")) == fixture


def test_committed_frontend_types_match_backend_schemas():
    from tools.generate_api_types import OUTPUT, generate

    assert OUTPUT.read_text() == generate()
