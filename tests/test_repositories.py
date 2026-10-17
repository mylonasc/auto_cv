from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def test_job_failed_replacement_changes_neither_memory_nor_original_file(job_manager, monkeypatch):
    from src import storage

    job = job_manager.create_job()
    path = Path(job_manager.storage_dir) / f"{job.id}.json"
    original = path.read_bytes()

    def fail(*args):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(storage.os, "replace", fail)
    with pytest.raises(OSError, match="disk failure"):
        job_manager.update_job_status(job.id, "processing")
    assert path.read_bytes() == original
    assert job_manager.get_job(job.id).status == "queued"
    assert not list(path.parent.glob(f".{path.name}.*"))


def test_job_reads_and_input_snapshots_are_independent(job_manager):
    from src.domain import CVData, CandidateMetadata

    source = CVData(candidate=CandidateMetadata(candidate_id="test"), personal_statement="Original")
    job = job_manager.create_job(candidate="test", cv_version_id="chosen", cv_snapshot=source)
    source.personal_statement = "Changed source"
    job.cv_snapshot.personal_statement = "Changed response"
    loaded = job_manager.get_job(job.id)
    assert loaded.cv_version_id == "chosen"
    assert loaded.cv_snapshot.personal_statement == "Original"
    loaded.cv_snapshot.personal_statement = "Changed read"
    assert job_manager.get_job(job.id).cv_snapshot.personal_statement == "Original"


@pytest.mark.parametrize("terminal", ["failed", "cancelled", "succeeded"])
def test_terminal_status_cannot_reenter_processing_or_another_terminal(job_manager, terminal):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, terminal)
    for status in ("processing", "succeeded" if terminal != "succeeded" else "failed"):
        with pytest.raises(ValueError, match="terminal"):
            job_manager.update_job_status(job.id, status)
    assert job_manager.get_job(job.id).status == terminal


def test_concurrent_artifact_publication_does_not_lose_updates(job_manager):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, "succeeded", result={"sections": []})

    def add(index):
        job_manager.append_artifacts(job.id, [{"id": str(index), "kind": "json", "filename": f"{index}.json"}])

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(add, range(20)))
    artifacts = job_manager.get_job(job.id).result.artifacts
    assert {item["id"] for item in artifacts} == {str(index) for index in range(20)}


def test_repository_read_modify_write_is_serialized(services):
    from models.api_models import WorkingCopy

    services.working.save(WorkingCopy(job_id="test"))

    def append(_):
        def update(value):
            value.personal_statement += "x"
            return value
        services.working.update("test", update)

    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(append, range(20)))
    assert services.working.get("test").personal_statement == "x" * 20


def test_corrupt_records_are_reported_and_preserved(services):
    path = services.submissions.directory / "corrupt.json"
    original = b"not-json-user-data"
    path.write_bytes(original)
    assert services.submissions.list() == []
    assert "corrupt.json" in services.submissions.load_errors
    assert path.read_bytes() == original


def test_active_jobs_cannot_be_deleted(job_manager):
    job = job_manager.create_job()
    with pytest.raises(ValueError, match="Cancel or finish"):
        job_manager.delete_job(job.id)
    assert job_manager.get_job(job.id) is not None


def test_processing_job_cannot_return_to_queue(job_manager):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, "processing")
    with pytest.raises(ValueError, match="queue"):
        job_manager.update_job_status(job.id, "queued")
