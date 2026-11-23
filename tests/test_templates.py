"""RFK follow-up: template contracts exercise real expansion, API and compilation adapters."""

from hashlib import sha256
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.domain import CVData, CandidateMetadata, CVTemplateData
from src.documents import FullCVDocument, DocSection, DocSectionItem
from src.template_registry import resolve_template_path, TemplateError, TemplateRegistryResponse
from src.artifacts import render_artifacts
from src.rendering import latex_to_pdf as _COMPILE_LATEX
from tests.helpers import wait_for_job


def document(*, template=None, content_format="latex"):
    return FullCVDocument('Statement <experience_section> & 100%', DocSection('R&D', [
        DocSectionItem('A & B', '2020_2024', r'Engineer \& lead', ['100% delivery #1']),
    ]), cv_template=template, content_format=content_format)


def custom_registry(tmp_path, monkeypatch):
    """A genuinely different layout, with no dependency on resume-class macros."""
    fragments = {
        'section': 'SECTION[<title>]<roles>',
        'role': 'ROLE[<company>|<duration>|<position>]<comment><bullets>',
        'bullet': 'BULLET[<text>]<comment>', 'comment': 'NOTE[<text>]',
    }
    for name, text in fragments.items():
        (tmp_path / f'{name}.tex').write_text(text)
    (tmp_path / 'entry.tex').write_text('START <statement> <experience_section> END')
    (tmp_path / 'logo.bin').write_bytes(b'original resource')
    entry = {'path': 'entry.tex', 'layout': {name: f'{name}.tex' for name in fragments},
             'resources': {'images/logo.bin': 'logo.bin'}}
    config = tmp_path / 'config'
    config.mkdir()
    (config / 'templates.json').write_text(json.dumps({'cv_templates': {'different': entry}}))
    monkeypatch.setenv('CV_CUSTOMIZER_ROOT', str(tmp_path))
    return entry


def test_registry_api_has_a_declared_contract_and_keeps_path_catalog(client):
    response = client.get('/v1/cv-data/templates')
    catalog = TemplateRegistryResponse.model_validate(response.json())
    assert catalog.cv_templates['template2'] == 'assets/latex_cv_template_v2.tex'
    schema = client.get('/openapi.json').json()
    assert schema['paths']['/v1/cv-data/templates']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('TemplateRegistryResponse')


def test_unknown_id_and_missing_file_never_select_another_template(tmp_path):
    with pytest.raises(TemplateError, match='Unknown.*typo'):
        resolve_template_path('cv_templates', 'typo')
    with pytest.raises(TemplateError, match='entry file does not exist'):
        resolve_template_path('cv_templates', 'default_cv', str(tmp_path / 'missing.tex'))


def test_legacy_string_registry_and_explicit_sidecar_keep_their_contracts(tmp_path, monkeypatch):
    from src.template_registry import resolve_template_definition
    entry = custom_registry(tmp_path, monkeypatch)
    (tmp_path / 'config/templates.json').write_text(json.dumps({'cv_templates': {'legacy': 'entry.tex'}}))
    legacy = resolve_template_definition('cv_templates', 'legacy')
    assert legacy.layout.section == 'assets/templates/resume/section.tex'
    assert 'resume.cls' in legacy.resources
    path = tmp_path / 'custom.tex'
    path.write_text('<statement><experience_section>')
    Path(str(path) + '.json').write_text(json.dumps(entry))
    explicit = resolve_template_definition('cv_templates', 'legacy', str(path))
    assert explicit.path == str(path)
    assert explicit.resources == entry['resources']


def test_shared_entrypoint_resolves_the_selected_layout_not_the_first_id(tmp_path, monkeypatch):
    from src.template_registry import resolve_template_definition
    entry = custom_registry(tmp_path, monkeypatch)
    other = {**entry, 'resources': {}}
    (tmp_path / 'config/templates.json').write_text(json.dumps({'cv_templates': {'first': entry, 'second': other}}))
    resolved = resolve_template_definition('cv_templates', 'second', str(tmp_path / 'entry.tex'))
    assert resolved.resources == {}
    with pytest.raises(TemplateError, match='Multiple templates'):
        resolve_template_definition('cv_templates', 'missing', str(tmp_path / 'entry.tex'))


@pytest.mark.parametrize('text,missing', [
    ('No content', 'statement'), ('<statement>', 'experience_section'),
    ('<statement><experience_section><typo>', 'typo'),
])
def test_missing_and_unknown_placeholders_fail_before_outputs(tmp_path, text, missing, pdf_calls):
    path = tmp_path / 'custom.tex'
    path.write_text(text)
    doc = document(template=CVTemplateData(template_path=str(path)))
    with pytest.raises(TemplateError, match=missing):
        render_artifacts(doc, tmp_path / 'output', 'result')
    assert pdf_calls == []
    assert list((tmp_path / 'output').iterdir()) == []


def test_one_pass_expansion_preserves_authored_tokens_and_latex_and_template_owns_pagebreak():
    text = document().make_latex()
    assert 'Statement <experience_section> & 100%' in text
    assert r'Engineer \& lead' in text
    assert text.count(r'\newpage') == 1


def test_plain_text_is_escaped_without_changing_source_or_comments():
    doc = document(content_format='plain_text')
    doc.experience_section.doc_section_items[0].set_comment('Evidence & 90%')
    text = doc.make_latex(include_scoring_comments=True)
    assert r'Statement <experience\_section> \& 100\%' in text
    assert r'{A \& B}' in text and r'{R\&D}' in text
    assert r'100\% delivery \#1' in text
    assert r'Evidence \& 90\%' in text
    assert doc.statement.endswith('& 100%')
    assert doc.copy().content_format == 'plain_text'


def test_custom_layout_and_resources_are_snapshot_inputs_not_python_macros(tmp_path, monkeypatch):
    custom_registry(tmp_path, monkeypatch)
    prepared = document(template=CVTemplateData(template_id='different')).prepare_latex()
    assert 'SECTION[R&D]ROLE[A & B|2020_2024|' in prepared.latex
    assert r'\begin{myrSubsection}' not in prepared.latex
    assert prepared.resources[0].destination == 'images/logo.bin'
    assert prepared.resources[0].content == b'original resource'
    assert prepared.manifest.resource_hashes == {'images/logo.bin': sha256(b'original resource').hexdigest()}
    (tmp_path / 'logo.bin').write_bytes(b'new resource')
    assert prepared.resources[0].content == b'original resource'
    next_render = document(template=CVTemplateData(template_id='different')).prepare_latex()
    assert next_render.manifest.input_hashes != prepared.manifest.input_hashes


def test_shared_template_input_is_read_once_even_through_path_aliases(tmp_path):
    from src.latex_templates import TemplateInputs
    path = tmp_path / 'fragment.tex'
    path.write_text('original')
    inputs = TemplateInputs()
    assert inputs.text(str(path)) == 'original'
    path.write_text('changed during render')
    assert inputs.text(str(tmp_path) + '/./fragment.tex') == 'original'


def test_both_outputs_use_exactly_one_expansion(tmp_path, monkeypatch, pdf_calls):
    doc = document()
    original = doc.prepare_latex
    calls = []

    def prepare(*args, **kwargs):
        calls.append(1)
        assert len(calls) == 1
        return original(*args, **kwargs)

    monkeypatch.setattr(doc, 'prepare_latex', prepare)
    result = render_artifacts(doc, tmp_path, 'render')
    latex = (tmp_path / 'render.tex').read_text()
    assert latex == pdf_calls[0].latex
    assert result.manifest.latex_sha256 == sha256(latex.encode()).hexdigest()
    assert len(result.artifacts) == 2


def test_compiler_materializes_only_declared_snapshot_resources_and_uses_scratch_cwd(tmp_path, monkeypatch):
    from src import rendering
    from src.latex_templates import RenderResource

    def run(command, **kwargs):
        folder = Path(kwargs['cwd'])
        assert (folder / 'images/logo.bin').read_bytes() == b'snapshot'
        assert not (folder / 'resume.cls').exists()
        assert (folder / 'temp.tex').read_text() == 'test latex'
        (folder / 'temp.pdf').write_bytes(b'%PDF-test')

    monkeypatch.setattr(rendering.subprocess, 'run', run)
    output = tmp_path / 'result.pdf'
    _COMPILE_LATEX('test latex', str(output), resources=(RenderResource('images/logo.bin', b'snapshot'),))
    assert output.read_bytes() == b'%PDF-test'


def test_resource_export_refuses_to_overwrite_different_existing_content(tmp_path):
    from src.rendering import materialize_resources
    from src.latex_templates import RenderResource
    original = tmp_path / 'asset.bin'
    original.write_bytes(b'preserve')
    materialize_resources((RenderResource('asset.bin', b'preserve'),), tmp_path)
    with pytest.raises(TemplateError, match='Conflicting template resource'):
        materialize_resources((RenderResource('asset.bin', b'different'),), tmp_path)
    assert original.read_bytes() == b'preserve'


@pytest.mark.asyncio
async def test_cli_exports_only_declared_resources_for_a_different_template(tmp_path, monkeypatch):
    from tools.autocv import _make_parser, run_pipeline
    custom_registry(tmp_path, monkeypatch)
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Engineer',
                    cv_template=CVTemplateData(template_id='different'))
    path = tmp_path / 'cv.json'
    path.write_text(source.model_dump_json())
    posting = tmp_path / 'posting.txt'
    posting.write_text('Python engineer')
    output = tmp_path / 'output'
    args = _make_parser().parse_args(['--candidate-json', str(path), '--candidate-id', 'test',
        '--job-posting', str(posting), '--output-dir', str(output), '--skip-cover-letter'])
    await run_pipeline(args)
    assert (output / 'latex_folder/images/logo.bin').read_bytes() == b'original resource'
    assert not (output / 'latex_folder/resume.cls').exists()
    assert 'SECTION[' in (output / 'latex_folder/cv_edited_no_comments.tex').read_text()


@pytest.mark.parametrize('destination', ['../outside', '/absolute', 'temp.pdf', 'temp.tex', r'..\outside'])
def test_resource_destinations_cannot_escape_or_shadow_outputs(tmp_path, monkeypatch, destination):
    entry = custom_registry(tmp_path, monkeypatch)
    entry['resources'] = {destination: 'logo.bin'}
    (tmp_path / 'config/templates.json').write_text(json.dumps({'cv_templates': {'different': entry}}))
    with pytest.raises(TemplateError, match='resource destination'):
        document(template=CVTemplateData(template_id='different')).prepare_latex()


def test_rerender_inherits_source_template_and_persists_manifest(client, services):
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), content_format='plain_text',
                    personal_statement='R&D', cv_template=CVTemplateData(template_id='template2'))
    services.cvs.save('test', 'master', source)
    job_id = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python'}).json()['id']
    assert wait_for_job(client, job_id)['status'] == 'succeeded'
    response = client.post(f'/v1/cv-jobs/{job_id}/render', json={})
    assert response.status_code == 200
    records = services.artifacts.records.list()
    assert len(records) == 2
    assert all(record.cv_snapshot.cv_template.template_id == 'template2' for record in records)
    assert all(record.cv_snapshot.content_format == 'plain_text' for record in records)
    assert all(record.manifest.template_id == 'template2' for record in records)
    assert all(record.manifest.options['content_format'] == 'plain_text' for record in records)
    response = client.post(f'/v1/cv-jobs/{job_id}/render', json={'cv_template_id': 'default_cv'})
    assert response.status_code == 200
    assert any(record.cv_snapshot.cv_template.template_id == 'default_cv' for record in services.artifacts.records.list())
    assert services.jobs.get_job(job_id).cv_snapshot.cv_template.template_path is None


def test_analysis_only_needs_no_templates_or_motivation_assets(client, services):
    from src.domain import MotivationLetterTemplateData
    from src.config import BackendConfig, OutputsConfig
    source = CVData(candidate=CandidateMetadata(candidate_id='test'),
        cv_template=CVTemplateData(template_id='unavailable-cv'),
        motivation_letter_template=MotivationLetterTemplateData(template_id='unavailable-letter'))
    services.cvs.save('test', 'master', source)
    config = BackendConfig(outputs=OutputsConfig(render_pdf=False, include_latex=False))
    job_id = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python',
                                             'config': config.model_dump()}).json()['id']
    assert wait_for_job(client, job_id)['status'] == 'succeeded'
    response = client.post(f'/v1/cv-jobs/{job_id}/render', json={'cv_template_id': 'default_cv'})
    assert response.status_code == 200
    assert services.jobs.get_job(job_id).cv_snapshot == source


def test_render_inherits_explicit_source_path_until_an_id_override(client, services, tmp_path, pdf_calls):
    path = tmp_path / 'custom.tex'
    path.write_text('CUSTOM <statement> <experience_section>')
    source = CVData(candidate=CandidateMetadata(candidate_id='test'),
                    cv_template=CVTemplateData(template_id='custom-only', template_path=str(path)))
    job = services.jobs.create_job('test', 'Python', cv_snapshot=source)
    services.jobs.update_job_status(job.id, 'succeeded', result={'sections': []})
    assert client.post(f'/v1/cv-jobs/{job.id}/render', json={}).status_code == 200
    assert pdf_calls[-1].latex.startswith('CUSTOM')
    assert client.post(f'/v1/cv-jobs/{job.id}/render', json={'cv_template_id': 'template2'}).status_code == 200
    assert 'resume_v2' in pdf_calls[-1].latex


def test_template_errors_are_actionable_and_do_not_publish_artifacts(client, job_manager):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, 'succeeded', result={'sections': []})
    response = client.post(f'/v1/cv-jobs/{job.id}/render', json={'cv_template_id': 'typo'})
    assert response.status_code == 422 and 'typo' in response.json()['detail']
    assert job_manager.get_job(job.id).result.artifacts == []


@pytest.mark.parametrize('patch', [
    {'sections': [{'id': 'same', 'items': [{'id': 'same', 'text': 'x'}]}]},
    {'sections': [{'id': '', 'items': []}]},
    {'sections': [{'items': [{'text': 'x', 'relevance_score': 99}]}]},
    {'sections': [{'section_score': -1}]},
    {'sections': [{'filter_config': {'min_items_keep': 3, 'max_items_keep': 1}}]},
    {'sections': [{'filter_config': {'min_relevance_score': 11}}]},
])
def test_invalid_working_copy_cannot_replace_persisted_copy(client, job_manager, services, patch):
    job = job_manager.create_job()
    job_manager.update_job_status(job.id, 'succeeded', result={'sections': []})
    original = client.get(f'/v1/cv-jobs/{job.id}/working-cv').json()
    before = services.working.path(job.id).read_bytes()
    response = client.put(f'/v1/cv-jobs/{job.id}/working-cv', json={**original, **patch})
    assert response.status_code == 422
    assert services.working.path(job.id).read_bytes() == before


def test_legacy_format_default_is_non_destructive_and_invalid_format_rejected():
    data = {'candidate': {'candidate_id': 'test'}}
    assert CVData.model_validate(data).content_format == 'latex'
    assert 'content_format' not in data
    with pytest.raises(ValidationError):
        CVData.model_validate({**data, 'content_format': 'html'})
