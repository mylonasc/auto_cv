"""TRF-04: offline preview execution, truthful diagnostics, limits and isolation."""

import asyncio
from copy import deepcopy
from pathlib import Path
import subprocess
import threading

import pytest

from src.domain import CVData, CandidateMetadata
from src.template_import import import_builtin_template
from src.template_package import package_revision
from src.tex_compiler import compile_latex, LatexCompileError, MAX_DIAGNOSTICS
from src.rendering import latex_to_pdf as production_job_compiler
from server_application.backend.models.studio import StudioPreviewRequest
from server_application.backend.services.studio_preview import StudioPreview, PreviewBusy


@pytest.fixture
def draft():
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Original')
    imported = import_builtin_template(source, root=Path(__file__).resolve().parents[1], new_template_id='preview', name='Preview')
    return StudioPreviewRequest(cv=imported.cv, package=imported.package)


def inventory(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_unsaved_preview_is_independent_binds_identity_and_never_persists(client, services, draft, fake_model):
    before = inventory(services.paths.root)
    draft.cv.personal_statement = 'Unsaved statement'
    draft.package.files['main.tex'] = draft.package.files['main.tex'].replace('<sections>', 'UNSAVED STYLE\n<sections>')
    assert draft.cv.cv_template.revision != package_revision(draft.package)
    calls = []
    def compiler(text, resources, *, timeout):
        assert timeout == 30
        calls.append((text, resources, threading.current_thread().name))
        return b'%PDF-preview'
    services.studio_preview.compiler = compiler
    payload = draft.model_dump(mode='json')
    untouched = deepcopy(payload)
    response = client.post('/v1/template-studio/preview', json=payload)
    assert response.status_code == 200, response.text
    assert response.content == b'%PDF-preview'
    assert response.headers['content-type'] == 'application/pdf'
    assert response.headers['cache-control'] == 'no-store'
    identity = response.headers['x-preview-input']
    assert len(identity) == 64
    assert 'Unsaved statement' in calls[0][0] and 'UNSAVED STYLE' in calls[0][0]
    assert calls[0][2] != threading.current_thread().name
    assert payload == untouched
    assert inventory(services.paths.root) == before
    assert not fake_model.calls
    second = client.post('/v1/template-studio/preview', json=payload)
    assert second.headers['x-preview-input'] == identity
    payload['cv']['personal_statement'] += ' Changed'
    third = client.post('/v1/template-studio/preview', json=payload)
    assert third.headers['x-preview-input'] != identity


def test_preview_failure_has_bounded_actionable_diagnostics(client, services, draft):
    def fail(*args, **kwargs):
        raise LatexCompileError('Compilation failed', './resume.cls:90: Undefined control sequence.\n' + 'x' * 20000)
    services.studio_preview.compiler = fail
    response = client.post('/v1/template-studio/preview', json=draft.model_dump(mode='json'))
    assert response.status_code == 422
    assert 'resume.cls:90' in response.json()['diagnostics']
    assert len(response.json()['diagnostics']) <= MAX_DIAGNOSTICS
    assert not services.templates.repository.list()


def test_preview_capacity_returns_retryable_http_error(client, services, draft):
    assert services.studio_preview.slots.acquire(blocking=False)
    try:
        response = client.post('/v1/template-studio/preview', json=draft.model_dump(mode='json'))
        assert response.status_code == 429
        assert response.headers['retry-after'] == '2'
        assert 'already compiling' in response.json()['detail']
    finally:
        services.studio_preview.slots.release()


def test_shared_job_compiler_keeps_detailed_failures_sanitized(monkeypatch, tmp_path):
    from src.outcomes import StageFailure
    def fail(*args, **kwargs):
        raise LatexCompileError('private-content', 'private diagnostics')
    monkeypatch.setattr('src.tex_compiler.compile_latex', fail)
    with pytest.raises(StageFailure) as result:
        production_job_compiler('source', str(tmp_path / 'pdf'))
    assert 'private' not in str(result.value)
    assert not (tmp_path / 'pdf').exists()


def test_preview_validation_rejects_unmanaged_mismatched_or_invalid_drafts(client, services, draft):
    def forbidden(*args, **kwargs):
        raise AssertionError('Invalid drafts must not compile')
    services.studio_preview.compiler = forbidden
    data = draft.model_dump(mode='json')
    data['cv']['cv_template']['template_id'] = 'other'
    assert client.post('/v1/template-studio/preview', json=data).status_code == 422
    data = draft.model_dump(mode='json')
    data['package']['files']['../escape.tex'] = 'bad'
    assert client.post('/v1/template-studio/preview', json=data).status_code == 422
    data = draft.model_dump(mode='json')
    data['package']['files']['main.tex'] = '<sections>'
    assert client.post('/v1/template-studio/preview', json=data).status_code == 422


@pytest.mark.asyncio
async def test_capacity_remains_held_after_caller_cancels_until_compiler_finishes(draft):
    entered, release, done = threading.Event(), threading.Event(), threading.Event()
    def compile(*args, **kwargs):
        entered.set()
        assert release.wait(5)
        done.set()
        return b'%PDF-test'
    service = StudioPreview(compiler=compile)
    task = asyncio.create_task(service.render(draft))
    assert await asyncio.to_thread(entered.wait, 5)
    try:
        with pytest.raises(PreviewBusy):
            await service.render(draft)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        with pytest.raises(PreviewBusy):
            await service.render(draft)
    finally:
        release.set()
        assert await asyncio.to_thread(done.wait, 5)
    # Wait for the actual worker's completion callback, not an arbitrary sleep.
    for pending in asyncio.all_tasks() - {asyncio.current_task()}:
        if pending.get_coro().__qualname__ == 'to_thread':
            await pending
    await asyncio.sleep(0)
    assert service.slots.acquire(blocking=False)
    service.slots.release()


@pytest.mark.parametrize('mode', ['success', 'process_failure', 'timeout', 'missing', 'empty', 'invalid', 'oversize'])
def test_shared_compiler_limits_output_flags_diagnostics_and_cleans_scratch(monkeypatch, mode):
    folders = []
    monkeypatch.setattr('src.tex_compiler.shutil.which', lambda name: '/fake/xelatex')
    def run(command, **kwargs):
        folder = Path(kwargs['cwd'])
        folders.append(folder)
        assert '-no-shell-escape' in command and '-file-line-error' in command
        assert kwargs['timeout'] == 30 and kwargs['check']
        assert kwargs['env']['openin_any'] == kwargs['env']['openout_any'] == 'p'
        assert 'RLIMIT_FSIZE' in command[2] and 'RLIMIT_CPU' in command[2]
        assert (folder / 'temp.tex').read_text() == 'source'
        pdf = folder / 'temp.pdf'
        if mode == 'missing': return
        if mode == 'oversize':
            with pdf.open('wb') as file:
                file.truncate(16 * 1024 * 1024 + 1)
            return
        pdf.write_bytes(b'' if mode == 'empty' else b'not-pdf' if mode == 'invalid' else b'%PDF-preview')
        if mode in ('timeout', 'process_failure'):
            kwargs['stdout'].write(b'x' * 20000 + b'\n./temp.tex:12: Undefined control sequence.\n')
            if mode == 'timeout': raise subprocess.TimeoutExpired(command, 30)
            raise subprocess.CalledProcessError(1, command)
    monkeypatch.setattr('src.tex_compiler.run_tex', run)
    if mode == 'success': assert compile_latex('source', timeout=30) == b'%PDF-preview'
    else:
        with pytest.raises(LatexCompileError) as result:
            compile_latex('source', timeout=30)
        if mode in ('timeout', 'process_failure'):
            assert 'temp.tex:12' in result.value.diagnostics
            assert len(result.value.diagnostics) <= MAX_DIAGNOSTICS
        if mode == 'timeout': assert 'timed out' in str(result.value)
    assert folders and all(not folder.exists() for folder in folders)


def test_missing_compiler_has_useful_message_and_cleans_temporary_files(monkeypatch):
    monkeypatch.setattr('src.tex_compiler.shutil.which', lambda name: None)
    with pytest.raises(LatexCompileError, match='not installed'):
        compile_latex('source', timeout=30)


def test_timeout_kills_and_reaps_the_owned_compiler_process_group(monkeypatch):
    from src.tex_compiler import run_tex
    import signal
    killed = []
    class Process:
        pid = 123456
        waits = 0
        def __init__(self, command, **kwargs):
            assert kwargs['start_new_session']
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def wait(self, timeout=None):
            self.waits += 1
            if self.waits == 1:
                assert timeout == 30
                raise subprocess.TimeoutExpired(['xelatex'], timeout)
            assert self.waits == 2
            return -9
    monkeypatch.setattr(subprocess, 'Popen', Process)
    monkeypatch.setattr('src.tex_compiler.os.killpg', lambda pid, sig: killed.append((pid, sig)))
    with pytest.raises(subprocess.TimeoutExpired):
        run_tex(['xelatex'], check=True, timeout=30, start_new_session=True)
    assert killed == [(123456, signal.SIGKILL)]
