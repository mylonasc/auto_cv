"""Application ownership, cancellation races, restart policy and render provenance."""

import asyncio
from pathlib import Path
import os
import subprocess
import sys
import threading

import pytest

from core.paths import StoragePaths
from application import create_app
from models.api_models import CreateJobRequest, CVJobResult, ProcessingOutput
from src.domain import CVData, CandidateMetadata, ExperienceSectionData
from tests.helpers import wait_for_job

# This narrowly scoped probe launches only the same Python interpreter with
# filesystem/network guards; model/PDF process launches remain forbidden.
_IMPORT_PROBE_POPEN = subprocess.Popen


@pytest.fixture
def captured_source(services):
    source = CVData(candidate=CandidateMetadata(candidate_id="test", full_name="Chosen Candidate"),
                    personal_statement="Chosen version statement", experience_sections=[ExperienceSectionData(
                        company="Example", position="Engineer", duration="2020", text_items=["Python delivery"],
                    )])
    services.cvs.save("test", "chosen", source)
    return source


def request():
    return CreateJobRequest(candidate="test", cv_version_id="chosen", job_description="Python engineer")


def output(statement="Done"):
    return ProcessingOutput(result=CVJobResult(personal_statement=statement, sections=[]), job_analysis={})


def test_factory_and_service_imports_do_not_touch_runtime_stores(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "user-stores"
    runtime.mkdir()
    sentinel = runtime / "sentinel.json"
    sentinel.write_text("user data")
    code = r'''
import os, sys, socket, subprocess
root = os.environ['AUTO_CV_DATA_ROOT']
def forbidden(*args, **kwargs):
    raise AssertionError('Import attempted network/process activity')
socket.socket.connect = socket.socket.connect_ex = forbidden
socket.create_connection = subprocess.Popen = forbidden
def audit(event, args):
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes)) and os.fsdecode(path).startswith(root):
            raise AssertionError('Import accessed runtime store: ' + str(path))
        if (isinstance(mode, str) and any(flag in mode for flag in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)):
            raise AssertionError('Import opened a file for writing')
    if event in ('os.mkdir', 'os.rename', 'os.remove', 'os.rmdir'):
        raise AssertionError('Import performed a filesystem mutation')
    if event in ('os.listdir', 'os.scandir') and args and isinstance(args[0], (str, bytes)):
        if os.fsdecode(args[0]).startswith(root):
            raise AssertionError('Import enumerated runtime store')
sys.addaudithook(audit)
import server_application.backend
import repositories, services.application, services.cv_processor, services.job_runner
import src.analysis, src.pipeline, src.utils_cross_analysis
from application import create_app
app = create_app()
app.openapi()
assert not hasattr(app.state, 'services')
print('import/factory probe passed')
'''
    env = {"PATH": os.environ.get("PATH", ""), "HOME": str(tmp_path / "home"),
           "PYTHONPATH": os.pathsep.join((str(repo), str(repo / "server_application/backend"))),
           "CV_CUSTOMIZER_ROOT": str(repo), "AUTO_CV_DATA_ROOT": str(runtime),
           "PYTHONDONTWRITEBYTECODE": "1", "LANGCHAIN_TRACING_V2": "false", "LANGSMITH_TRACING": "false"}
    with _IMPORT_PROBE_POPEN([sys.executable, "-B", "-c", code], cwd=repo, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        stdout, stderr = process.communicate(timeout=20)
    assert process.returncode == 0, stderr
    assert "probe passed" in stdout
    assert sentinel.read_text() == "user data"
    assert list(runtime.iterdir()) == [sentinel]


def test_two_apps_have_independent_repositories_and_configuration(tmp_path):
    from fastapi.testclient import TestClient
    one, two = StoragePaths(tmp_path / "one"), StoragePaths(tmp_path / "two")
    app_one, app_two = create_app(paths=one), create_app(paths=two)
    assert not one.root.exists() and not two.root.exists()
    with TestClient(app_one) as first, TestClient(app_two) as second:
        config = first.get("/v1/config/").json()
        config["analysis_model"]["model"] = "first-app-only"
        assert first.put("/v1/config/", json=config).status_code == 200
        assert second.get("/v1/config/").json()["analysis_model"]["model"] != "first-app-only"
        assert app_one.state.services.jobs is not app_two.state.services.jobs
        assert app_one.state.services.cache is not app_two.state.services.cache


def test_application_accepts_injected_runner_factory(services):
    from services.application import ApplicationServices
    runner = object()
    observed = []

    def factory(jobs, execute):
        observed.append((jobs, execute))
        return runner

    injected = ApplicationServices(services.paths, jobs=services.jobs, cvs=services.cvs,
        working=services.working, submissions=services.submissions, artifacts=services.artifacts,
        cache=services.cache, runner_factory=factory)
    assert injected.runner is runner
    assert observed == [(services.jobs, injected.execute)]


@pytest.mark.asyncio
async def test_cancel_before_execution_removes_actual_task_handle(services, captured_source):
    job = await services.create_job(request())
    task = services.runner.tasks[job.id]
    assert services.runner.cancel(job.id)
    await asyncio.gather(task, return_exceptions=True)
    assert services.jobs.get_job(job.id).status == "cancelled"
    assert job.id not in services.runner.tasks
    assert services.working.get(job.id) is None


@pytest.mark.asyncio
async def test_cancelled_processor_cannot_publish_late_success(services, captured_source):
    started = asyncio.Event()

    class StubbornProcessor:
        def __init__(self, **kwargs): pass
        async def process(self, *args, **kwargs):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                return output("Late success")  # Simulate a provider suppressing cancellation.

    services.processor_factory = StubbornProcessor
    job = await services.create_job(request())
    task = services.runner.tasks[job.id]
    await asyncio.wait_for(started.wait(), 2)
    assert services.runner.cancel(job.id)
    await task
    saved = services.jobs.get_job(job.id)
    assert saved.status == "cancelled" and saved.result is None
    assert services.working.get(job.id) is None
    assert services.artifacts.records.list() == []


@pytest.mark.asyncio
async def test_shutdown_cancels_and_awaits_owned_jobs(services, captured_source):
    started = asyncio.Event()

    class WaitingProcessor:
        def __init__(self, **kwargs): pass
        async def process(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()

    services.processor_factory = WaitingProcessor
    job = await services.create_job(request())
    await asyncio.wait_for(started.wait(), 2)
    await services.runner.shutdown()
    assert services.jobs.get_job(job.id).status == "cancelled"
    assert services.runner.tasks == {}


@pytest.mark.asyncio
async def test_job_uses_creation_snapshot_not_a_later_version_edit(services, captured_source):
    observed = []

    class SnapshotProcessor:
        def __init__(self, *, source, **kwargs): self.source = source
        async def process(self, *args, **kwargs):
            observed.append(self.source.personal_statement)
            return output(self.source.personal_statement)

    services.processor_factory = SnapshotProcessor
    job = await services.create_job(request())
    captured_source.personal_statement = "Later edit"
    services.cvs.save("test", "chosen", captured_source)
    await services.runner.tasks[job.id]
    saved = services.jobs.get_job(job.id)
    assert observed == ["Chosen version statement"]
    assert saved.result.personal_statement == saved.cv_snapshot.personal_statement == "Chosen version statement"
    assert saved.cv_version_id == "chosen"


def test_restart_fails_interrupted_jobs_without_replaying(services, fake_model):
    from fastapi.testclient import TestClient
    queued = services.jobs.create_job()
    processing = services.jobs.create_job()
    services.jobs.update_job_status(processing.id, "processing")
    completed = services.jobs.create_job()
    services.jobs.update_job_status(completed.id, "succeeded", result={"sections": []})
    with TestClient(create_app(services=services)):
        for job in (queued, processing):
            saved = services.jobs.get_job(job.id)
            assert saved.status == "failed"
            assert "restart" in saved.error
        assert services.jobs.get_job(completed.id).status == "succeeded"
        assert services.runner.tasks == {}
    assert fake_model.calls == []


def test_http_post_returns_before_work_finishes_and_cancel_owns_the_handle(client, services, captured_source):
    started = threading.Event()

    class WaitingProcessor:
        def __init__(self, **kwargs): pass
        async def process(self, *args, **kwargs):
            started.set()
            await asyncio.Event().wait()

    services.processor_factory = WaitingProcessor
    response = client.post("/v1/cv-jobs/", json=request().model_dump())
    assert response.status_code == 200
    assert started.wait(timeout=2)
    job = response.json()
    assert client.post(f"/v1/cv-jobs/{job['id']}/cancel").json()["status"] == "cancelled"
    assert wait_for_job(client, job['id'])["status"] == "cancelled"
    assert client.get(f"/v1/cv-jobs/{job['id']}/result").status_code == 409


def test_submission_pins_selected_render_and_survives_later_edits_and_history_deletion(client, services, captured_source):
    created = client.post("/v1/cv-jobs/", json=request().model_dump()).json()
    job = wait_for_job(client, created['id'])
    assert job['status'] == 'succeeded', job['error']
    initial_artifact = job['result']['artifacts'][0]['id']
    copy = client.get(f"/v1/cv-jobs/{job['id']}/working-cv").json()
    copy['personal_statement'] = 'Actually submitted statement'
    copy['sections'][0]['items'][0]['text'] = 'Actually submitted bullet'
    rendered = client.post(f"/v1/cv-jobs/{job['id']}/render", json={
        'working_copy': copy, 'cv_template_id': 'template2',
    }).json()
    artifact = rendered['result']['artifacts'][-1]
    captured_source.personal_statement = 'Different current source'
    services.cvs.save('test', 'chosen', captured_source)
    # No master version exists at all; submission cannot quietly read one.
    sent = client.post('/v1/submissions/', json={'job_id': job['id'], 'artifact_ids': [artifact['id']]})
    assert sent.status_code == 200
    submission = sent.json()
    snapshot = submission['cv_snapshot']
    assert snapshot['personal_statement'] == 'Actually submitted statement'
    assert snapshot['candidate']['full_name'] == 'Chosen Candidate'
    assert snapshot['experience_sections'][0]['text_items'] == ['Actually submitted bullet']
    assert snapshot['cv_template']['template_id'] == 'template2'
    assert submission['scoring_snapshot']['working_copy']['sections'][0]['items'][0]['scored_text'] == 'Python delivery'
    assert client.post('/v1/submissions/', json={
        'job_id': job['id'], 'artifact_ids': [initial_artifact, artifact['id']],
    }).status_code == 409
    current = client.get(f"/v1/cv-jobs/{job['id']}/working-cv").json()
    current['personal_statement'] = 'Later working copy'
    assert client.put(f"/v1/cv-jobs/{job['id']}/working-cv", json=current).status_code == 200
    assert client.delete(f"/v1/cv-jobs/{job['id']}").status_code == 200
    assert client.get(f"/v1/cv-jobs/{job['id']}").status_code == 404
    assert client.get(f"/v1/submissions/{submission['id']}").json() == submission
    assert services.working.get(job['id']) is not None
    assert Path(artifact['path']).is_file()
    record = services.artifacts.for_artifact(job['id'], artifact['id'])
    assert record is not None
    with pytest.raises(FileExistsError, match='immutable'):
        services.artifacts.record(record)


def test_historical_artifacts_without_provenance_are_not_snapshot_from_current_master(client, job_manager):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, 'succeeded', result={'sections': [], 'artifacts': [
        {'id': 'historical', 'kind': 'pdf', 'filename': 'old.pdf'},
    ]})
    response = client.post('/v1/submissions/', json={'job_id': job.id})
    assert response.status_code == 409
    assert 'snapshot' in response.json()['detail']
