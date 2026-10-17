"""Installed, CWD-independent entry points with explicit no-network/storage probes."""

import ast
from pathlib import Path
import os
import subprocess
import sys
import tomllib

import pytest

_PROBE_POPEN = subprocess.Popen
ROOT = Path(__file__).resolve().parents[1]


def test_legacy_imports_are_aliases_not_parallel_implementations():
    from src import utils, utils_cross_analysis, documents, posting, scoring, cover_letter, cache
    assert utils.FullCVDocument is documents.FullCVDocument
    assert utils.JobPostAnalysis is posting.JobPostAnalysis
    assert utils.CoverLetterModel is cover_letter.CoverLetterModel
    assert utils_cross_analysis.CVCrossAnalyzer is scoring.CVCrossAnalyzer
    assert utils_cross_analysis.AnalysisResultCache is cache.AnalysisResultCache
    assert utils_cross_analysis.CoverLetterDrafter is cover_letter.CoverLetterDrafter


def test_active_code_has_no_path_injection_or_legacy_utility_dependencies():
    for folder in ('src', 'server_application/backend', 'tools'):
        for path in (ROOT / folder).rglob('*.py'):
            if any(part in {'.venv', 'venv', '__pycache__', 'node_modules'} for part in path.relative_to(ROOT).parts):
                continue
            text = path.read_text()
            assert 'sys.path.' not in text, path
            assert 'TODO: describe' not in text, path
            tree = ast.parse(text)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    assert node.module not in ('src.utils', 'src.utils_cross_analysis'), path
                    if folder == 'server_application/backend' and node.level == 0:
                        assert (node.module or '').split('.')[0] not in {
                            'api', 'core', 'services', 'models', 'jobs', 'utils', 'application', 'repositories',
                        }, path


def test_dependency_metadata_and_docker_have_one_runtime_source():
    metadata = tomllib.loads((ROOT / 'pyproject.toml').read_text())
    assert metadata['tool']['setuptools']['dynamic']['dependencies']['file'] == ['requirements.txt']
    assert (ROOT / 'server_application/backend/requirements.txt').read_text().endswith('-r ../../requirements.txt\n')
    docker = (ROOT / 'Dockerfile.backend').read_text()
    assert '"server_application.backend.main:app"' in docker
    assert 'WORKDIR /app/server_application/backend' not in docker
    assert 'backend_requirements.txt' not in docker


@pytest.mark.parametrize('entry', ['cli', 'types', 'api', 'telemetry_import'])
def test_installed_commands_from_unrelated_cwd_without_store_or_network_access(tmp_path, entry):
    code = r'''
import os, sys, socket, subprocess
root = os.environ['AUTO_CV_DATA_ROOT']
def forbidden(*args, **kwargs): raise AssertionError('Unexpected network/process activity')
socket.socket.connect = socket.socket.connect_ex = forbidden
socket.create_connection = subprocess.Popen = forbidden
def audit(event, args):
    if event == 'open':
        path, mode, flags = args
        if isinstance(path, (str, bytes)) and os.fsdecode(path).startswith(root):
            raise AssertionError('Unexpected runtime access')
        if (isinstance(mode, str) and any(flag in mode for flag in 'wax+')) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT)):
            raise AssertionError('Unexpected write during entry-point probe')
    if event in ('os.mkdir', 'os.rename', 'os.remove', 'os.rmdir'):
        raise AssertionError('Unexpected filesystem mutation')
sys.addaudithook(audit)
from importlib.metadata import distribution
entry = sys.argv[1]
commands = {point.name: point for point in distribution('auto-cv').entry_points}
if entry == 'cli':
    sys.argv = ['auto-cv', '--help']
    try: commands['auto-cv'].load()()
    except SystemExit as error: assert error.code == 0
elif entry == 'types':
    sys.argv = ['auto-cv-types', '--check']
    commands['auto-cv-types'].load()()
elif entry == 'api':
    import uvicorn
    calls = []
    uvicorn.run = lambda *args, **kwargs: calls.append((args, kwargs))
    commands['auto-cv-api'].load()()
    assert calls[0][0] == ('server_application.backend.main:app',)
    from server_application.backend.main import app
    app.openapi()
    assert not hasattr(app.state, 'services')
else:
    commands['auto-cv-otel'].load()
    assert 'opentelemetry.sdk.trace' not in sys.modules
from src.paths import project_root, data_root
assert project_root() == __import__('pathlib').Path(os.environ['CV_CUSTOMIZER_ROOT'])
assert data_root() == __import__('pathlib').Path(root)
assert not any(name in sys.modules for name in ('api', 'core', 'services', 'models', 'jobs', 'application'))
print('entry-point probe passed')
'''
    env = {'PATH': os.environ.get('PATH', ''), 'HOME': str(tmp_path),
           'CV_CUSTOMIZER_ROOT': str(ROOT), 'AUTO_CV_DATA_ROOT': str(tmp_path / 'never-open'),
           'PYTHONDONTWRITEBYTECODE': '1', 'LANGCHAIN_TRACING_V2': 'false', 'LANGSMITH_TRACING': 'false'}
    # Deliberate subprocess exception, matching the existing import probe: this
    # interpreter installs independent audit/network guards, not live providers.
    with _PROBE_POPEN([sys.executable, '-B', '-c', code, entry], cwd=tmp_path, env=env,
                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as process:
        stdout, stderr = process.communicate(timeout=30)
    assert process.returncode == 0, stderr
    assert 'entry-point probe passed' in stdout
    assert not (tmp_path / 'never-open').exists()


def test_relative_data_root_is_checkout_relative_for_all_consumers(monkeypatch, tmp_path):
    from src.paths import data_root
    from src.cache import AnalysisResultCache
    from server_application.backend.core.paths import StoragePaths
    monkeypatch.setenv('CV_CUSTOMIZER_ROOT', str(tmp_path))
    monkeypatch.setenv('AUTO_CV_DATA_ROOT', 'isolated-data')
    assert data_root() == tmp_path / 'isolated-data'
    assert StoragePaths.from_env().cache == Path(AnalysisResultCache().cache_path)


def test_relative_checkout_root_is_rejected_instead_of_depending_on_cwd(monkeypatch):
    from src.paths import project_root
    monkeypatch.setenv('CV_CUSTOMIZER_ROOT', 'ambiguous-checkout')
    with pytest.raises(ValueError, match='absolute checkout'):
        project_root()
