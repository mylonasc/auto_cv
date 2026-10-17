"""Isolate storage before collection, then isolate each test's dependencies.

The application currently initializes stores during import. An autouse fixture
alone is too late: tests import application modules during collection. RFK-06
will remove those globals; until then the session sandbox protects imports too.
"""

import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile

import pytest

from tests.fakes import PDFCall, StructuredModel

REPO_ROOT = Path(__file__).resolve().parents[1]


def pytest_configure(config):
    if "core.paths" in sys.modules or "src.utils_cross_analysis" in sys.modules:
        raise pytest.UsageError("Application stores were imported before test isolation")
    scratch = "/tmp/opencode" if Path("/tmp/opencode").is_dir() else None
    sandbox = tempfile.TemporaryDirectory(prefix="auto_cv_pytest_", dir=scratch)
    config._cv_sandbox = sandbox
    config._cv_env = {key: os.environ.get(key) for key in (
        "AUTO_CV_DATA_ROOT", "CV_CUSTOMIZER_ROOT", "LANGCHAIN_TRACING_V2",
        "LANGSMITH_TRACING",
    )}
    os.environ.update(
        AUTO_CV_DATA_ROOT=sandbox.name,
        CV_CUSTOMIZER_ROOT=str(REPO_ROOT),
        LANGCHAIN_TRACING_V2="false",
        LANGSMITH_TRACING="false",
    )
    sys.path.insert(0, str(REPO_ROOT / "server_application" / "backend"))


def pytest_unconfigure(config):
    for key, value in getattr(config, "_cv_env", {}).items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    if hasattr(config, "_cv_sandbox"):
        config._cv_sandbox.cleanup()


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    from core import paths
    from jobs import job_manager as jobs
    from api import config, cv_data, cv_jobs, submissions
    from models.api_models import BackendConfig
    from services import cv_processor
    from src import utils_cross_analysis

    root = tmp_path / "runtime"
    monkeypatch.setenv("AUTO_CV_DATA_ROOT", str(root))
    directories = {
        "DATA_ROOT": root,
        "CV_DATA_DIR": root / "cv_section_data",
        "ARTIFACTS_DIR": root / "artifacts",
        "CACHE_DIR": root / "cache",
        "JOBS_DIR": root / "jobs",
        "WORKING_CVS_DIR": root / "working_cvs",
        "SUBMISSIONS_DIR": root / "submissions",
    }
    # Rebind aliases imported by value until repositories replace these globals.
    for module in (paths, jobs, cv_data, cv_jobs, submissions, cv_processor):
        for name, directory in directories.items():
            if hasattr(module, name):
                monkeypatch.setattr(module, name, str(directory))
    monkeypatch.setattr(cv_data, "CV_DATA_BASE_DIR", str(directories["CV_DATA_DIR"]))
    paths.ensure_data_dirs()
    manager = jobs.JobManager(storage_dir=str(directories["JOBS_DIR"]))
    for module in (jobs, cv_jobs, submissions):
        monkeypatch.setattr(module, "job_manager", manager)
    monkeypatch.setattr(cv_jobs, "active_tasks", {})
    monkeypatch.setattr(config, "_current_config", BackendConfig())
    monkeypatch.setattr(utils_cross_analysis, "_analysis_cache",
                        utils_cross_analysis.AnalysisResultCache(
                            str(directories["CACHE_DIR"] / "analysis.json")))
    # Legacy processing uses relative temporary files; they belong to this test.
    monkeypatch.chdir(tmp_path)
    return root


@pytest.fixture
def fake_model():
    return StructuredModel()


@pytest.fixture
def pdf_calls():
    return []


@pytest.fixture(autouse=True)
def offline_dependencies(monkeypatch, fake_model, pdf_calls):
    from src.models import ModelFactory
    from src import utils

    def forbidden(*args, **kwargs):
        raise AssertionError("Offline tests must not open network connections or processes")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(ModelFactory, "get_llm_model", lambda self: fake_model)

    def fake_pdf(latex, output):
        output = Path(output)
        pdf_calls.append(PDFCall(latex, output))
        output.write_bytes(b"%PDF-1.4\n% offline test placeholder; not a real rendered document\n")

    monkeypatch.setattr(utils, "_latex_to_pdf", fake_pdf)


@pytest.fixture
def client(isolated_runtime, offline_dependencies):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from api import config, cv_data, cv_jobs, submissions

    app = FastAPI()
    for router in (config.router, cv_data.router, cv_jobs.router, submissions.router):
        app.include_router(router)
    with TestClient(app) as test_client:
        yield test_client
