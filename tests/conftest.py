"""Inject fresh application repositories per test; keep import/CLI defense too."""

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
    root = tmp_path / "runtime"
    monkeypatch.setenv("AUTO_CV_DATA_ROOT", str(root))
    monkeypatch.chdir(tmp_path)
    return root


@pytest.fixture(autouse=True)
def services(isolated_runtime):
    from core.paths import StoragePaths
    from services.application import ApplicationServices
    return ApplicationServices(StoragePaths(isolated_runtime))


@pytest.fixture
def job_manager(services):
    return services.jobs


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
def client(services, offline_dependencies):
    from application import create_app
    from fastapi.testclient import TestClient
    with TestClient(create_app(services=services)) as test_client:
        yield test_client
