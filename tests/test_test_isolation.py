"""Regression tests for the test harness itself, not application behavior."""

from pathlib import Path
import socket
import subprocess

import pytest


def test_application_stores_are_empty_and_inside_test_runtime(isolated_runtime):
    from api import cv_data, cv_jobs, submissions
    from core import paths
    from jobs.job_manager import job_manager
    from services import cv_processor
    from src.utils_cross_analysis import _analysis_cache

    for path in (
        paths.DATA_ROOT, cv_data.CV_DATA_BASE_DIR, cv_jobs.ARTIFACTS_DIR,
        cv_jobs.WORKING_CVS_DIR, submissions.SUBMISSIONS_DIR,
        cv_processor.CV_DATA_DIR, job_manager.storage_dir, _analysis_cache.cache_path,
    ):
        assert Path(path).is_relative_to(isolated_runtime)
    assert job_manager.list_jobs() == []
    assert list(isolated_runtime.rglob("*.json")) == []


def test_working_copy_write_does_not_touch_neighboring_user_data(tmp_path, isolated_runtime):
    from api.cv_jobs import _save_working_copy_to_disk
    from models.api_models import WorkingCopy

    # This sentinel is outside the runtime root, as a real user's data would be.
    sentinel = tmp_path / "user-data" / "working_cvs" / "same-id.json"
    sentinel.parent.mkdir(parents=True)
    sentinel.write_text("user content")
    _save_working_copy_to_disk(WorkingCopy(job_id="same-id", personal_statement="test"))
    assert sentinel.read_text() == "user content"
    assert (isolated_runtime / "working_cvs" / "same-id.json").is_file()


def test_network_access_is_blocked():
    with socket.socket() as connection:
        with pytest.raises(AssertionError, match="Offline tests"):
            connection.connect(("127.0.0.1", 11434))


def test_external_process_execution_is_blocked():
    with pytest.raises(AssertionError, match="Offline tests"):
        subprocess.run(["xelatex", "--version"], check=True)


def test_pdf_boundary_is_fake_but_latex_generation_is_real(tmp_path, pdf_calls):
    from src.utils import FullCVDocument, DocSection, DocSectionItem

    document = FullCVDocument("Test statement", DocSection("Work Experience", [
        DocSectionItem("Test company", "2020", "Engineer", ["Test bullet"]),
    ]))
    target = tmp_path / "cv.pdf"
    document.render_pdf(str(target))
    assert target.read_bytes().startswith(b"%PDF")
    assert len(pdf_calls) == 1
    assert pdf_calls[0].output == target
    assert "Test statement" in pdf_calls[0].latex
    assert "Test bullet" in pdf_calls[0].latex
