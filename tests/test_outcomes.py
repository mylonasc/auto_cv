"""Truthful failure/fallback results through production stages and HTTP."""

import asyncio
from pathlib import Path
import subprocess

import pytest
from langchain_core.runnables import RunnableLambda

from src import utils
from src.outcomes import StageFailure, gather_owned
from tests.helpers import wait_for_job

_COMPILE_LATEX = utils._latex_to_pdf


@pytest.fixture
def cv_payload():
    from src.domain import CVData, CandidateMetadata, ExperienceSectionData
    return CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Engineer',
        experience_sections=[ExperienceSectionData(company='Example', position='Engineer', duration='2020',
                                                   text_items=['Python delivery'])]).model_dump(mode='json')


def fail_schema(monkeypatch, fake_model, schema_name):
    original = fake_model.with_structured_output

    def structured(schema):
        if schema.__name__ != schema_name:
            return original(schema)

        def fail(prompt):
            raise RuntimeError("sensitive-provider-message")
        return RunnableLambda(fail)

    monkeypatch.setattr(fake_model, "with_structured_output", structured)


@pytest.mark.parametrize("schema,stage", [
    ("BasicAnalysis", "posting_analysis"), ("BulletAnalysis", "experience_bullet"),
    ("SectionAnalysis", "experience_section_synthesis"), ("PersonalStatementRewrite", "statement_rewrite"),
])
def test_analysis_failure_never_publishes_success(client, cv_payload, services, monkeypatch, fake_model, schema, stage):
    cv_payload["alternative_statements"] = ["Alternative"]
    assert client.put('/v1/cv-data/test', json=cv_payload).status_code == 200
    fail_schema(monkeypatch, fake_model, schema)
    created = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python engineer'}).json()
    job = wait_for_job(client, created['id'])
    assert job['status'] == 'failed' and job['result'] is None
    assert stage in job['error'] and 'sensitive' not in job['error']
    assert services.working.get(job['id']) is None
    assert services.artifacts.records.list() == []


def test_rescore_failure_leaves_working_copy_unchanged(client, cv_payload, services, monkeypatch, fake_model):
    client.put('/v1/cv-data/test', json=cv_payload)
    created = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python engineer'}).json()
    job = wait_for_job(client, created['id'])
    before = client.get(f"/v1/cv-jobs/{job['id']}/working-cv").json()
    original = services.working.path(job['id']).read_bytes()
    fail_schema(monkeypatch, fake_model, 'BulletAnalysis')
    response = client.post(f"/v1/cv-jobs/{job['id']}/working-cv/rescore", json={'section_index': 0})
    assert response.status_code == 502
    assert 'rescore' in response.json()['detail']
    assert before['sections'][0]['items'][0]['id'] in response.json()['detail']
    assert services.working.path(job['id']).read_bytes() == original


@pytest.mark.parametrize('posting,expected', [('Python required', 'python'), ('Unspecified position', 'Not identified in posting')])
def test_posting_fallback_is_labeled_not_invented(client, monkeypatch, fake_model, posting, expected):
    original = fake_model.with_structured_output

    def structured(schema):
        if schema.__name__ == 'BasicAnalysis':
            return RunnableLambda(lambda _: schema(skills='Skills', qualifications='N/A'))
        return original(schema)

    monkeypatch.setattr(fake_model, 'with_structured_output', structured)
    response = client.post('/v1/cv-jobs/job-analysis', json={'job_description': posting})
    assert response.status_code == 200
    analysis = response.json()['job_analysis']
    assert analysis['basic_analysis']['skills'] == expected
    assert analysis['provenance']['skills']['status'] == 'fallback'
    assert analysis['provenance']['qualifications']['method'] == 'posting_heuristic_v1'


@pytest.mark.parametrize('mode', ['process_failure', 'missing', 'empty', 'timeout', 'missing_executable'])
def test_real_pdf_compiler_fails_truthfully_without_publishing(monkeypatch, tmp_path, mode):
    def run(command, **kwargs):
        assert kwargs['check'] and kwargs['timeout'] == 120
        if mode == 'process_failure':
            # Even a process leaving a PDF before failing cannot publish it.
            (Path(command[command.index('-output-directory') + 1]) / 'temp.pdf').write_bytes(b'%PDF-invalid')
            raise subprocess.CalledProcessError(1, command)
        if mode == 'timeout':
            raise subprocess.TimeoutExpired(command, 120)
        if mode == 'missing_executable':
            raise FileNotFoundError('xelatex')
        if mode == 'empty':
            (Path(command[command.index('-output-directory') + 1]) / 'temp.pdf').touch()

    monkeypatch.setattr(subprocess, 'run', run)
    path = tmp_path / 'output.pdf'
    with pytest.raises(StageFailure, match='pdf_render'):
        _COMPILE_LATEX('test', str(path))
    assert not path.exists()


def test_pdf_failure_during_rerender_does_not_append_artifacts(client, job_manager, monkeypatch):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, 'succeeded', result={'sections': []})

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ['xelatex'])

    monkeypatch.setattr(utils, '_latex_to_pdf', fail)
    response = client.post(f'/v1/cv-jobs/{job.id}/render', json={})
    assert response.status_code == 502
    assert job_manager.get_job(job.id).result.artifacts == []


def test_initial_pdf_failure_is_a_failed_job_without_published_outputs(client, cv_payload, services, monkeypatch):
    client.put('/v1/cv-data/test', json=cv_payload)

    def fail(*args, **kwargs):
        raise subprocess.CalledProcessError(1, ['xelatex'])

    monkeypatch.setattr(utils, '_latex_to_pdf', fail)
    created = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python engineer'}).json()
    job = wait_for_job(client, created['id'])
    assert job['status'] == 'failed' and 'pdf_render' in job['error']
    assert job['result'] is None
    assert services.working.get(job['id']) is None
    assert services.artifacts.records.list() == []


def test_existing_output_cannot_masquerade_as_new_success(tmp_path):
    from src.artifacts import render_artifacts
    path = tmp_path / 'test.pdf'
    path.write_bytes(b'valuable original')
    with pytest.raises(StageFailure, match='FileExistsError'):
        render_artifacts(object(), tmp_path, 'test')
    assert path.read_bytes() == b'valuable original'


def test_later_output_failure_cannot_publish_partial_success(client, job_manager, monkeypatch):
    from src.utils import FullCVDocument
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, 'succeeded', result={'sections': []})
    original = FullCVDocument.make_latex
    calls = 0

    def fail_later(self, *args, **kwargs):
        nonlocal calls
        calls += 1
        if calls > 1:
            raise OSError('second output failed')
        return original(self, *args, **kwargs)

    monkeypatch.setattr(FullCVDocument, 'make_latex', fail_later)
    response = client.post(f'/v1/cv-jobs/{job.id}/render', json={})
    assert response.status_code == 502
    assert 'latex_render' in response.json()['detail']
    assert job_manager.get_job(job.id).result.artifacts == []


@pytest.mark.asyncio
async def test_parallel_stage_failure_cancels_and_awaits_siblings():
    cancelled = asyncio.Event()
    started = asyncio.Event()

    async def waiting():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def failing():
        await started.wait()
        raise RuntimeError('failure')

    with pytest.raises(RuntimeError):
        await gather_owned(waiting(), failing())
    assert cancelled.is_set()
