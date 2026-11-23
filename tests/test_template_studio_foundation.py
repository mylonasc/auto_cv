"""TRF-01 / RFK-04: canonical composition and recoverable template values/storage."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.composition import DocumentComposition
from src.domain import CVData, CandidateMetadata, CVTemplateData, ExperienceSectionData
from src.template_import import import_builtin_template
from src.template_package import BinaryAsset, TemplatePackage, TemplateRevision, package_revision
from src.template_registry import TemplateError
from src.template_storage import ManagedTemplateRepository, TemplateRevisionConflict

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def source():
    return CVData(candidate=CandidateMetadata(candidate_id='test', full_name='Identity metadata', profile={'custom': 'preserve'}),
        personal_statement='Source statement', alternative_statements=['Alternative'],
        experience_sections=[ExperienceSectionData(company='Example', duration='2020', position='Engineer', text_items=['Python work'])])


@pytest.fixture
def imported(source):
    return import_builtin_template(source, root=ROOT, new_template_id='studio_copy', name='Studio Copy')


@pytest.fixture
def repository(tmp_path):
    return ManagedTemplateRepository(tmp_path / 'managed-templates')


def composition():
    return {
        'header_latex': r'\name{Example}',
        'sections': [
            {'kind': 'statement', 'id': 'about', 'title': 'About'},
            {'kind': 'experience', 'id': 'experience', 'title': 'Experience'},
            {'kind': 'entries', 'id': 'projects', 'title': 'Projects', 'entries': [
                {'id': 'project-one', 'name': 'Project', 'technologies': ['Python'], 'bullets': ['Built it']} ]},
            {'kind': 'publications', 'id': 'publications', 'title': 'Publications', 'enabled': False, 'entries': [
                {'id': 'paper-one', 'title': 'A paper', 'authors': 'A. Author', 'year': '2024'}]},
            {'kind': 'latex', 'id': 'education', 'title': 'Education', 'latex': r'\textbf{Degree}'}],
    }


def test_composition_preserves_order_ids_and_disabled_content_without_mutation():
    payload = composition()
    original = deepcopy(payload)
    value = DocumentComposition.model_validate(payload)
    assert payload == original
    assert [section.id for section in value.sections] == ['about', 'experience', 'projects', 'publications', 'education']
    assert value.sections[3].enabled is False
    assert value.sections[3].entries[0].title == 'A paper'
    assert DocumentComposition.model_validate_json(value.model_dump_json()) == value


@pytest.mark.parametrize('change', [
    lambda data: data['sections'][0].update(personal_statement='duplicate'),
    lambda data: data['sections'][1].update(experience_sections=[]),
    lambda data: data['sections'][1].update(id='about'),
    lambda data: data['sections'][2]['entries'][0].update(id='about'),
    lambda data: data['sections'].append({'kind': 'statement', 'id': 'another-statement', 'title': 'Duplicate binding'}),
    lambda data: data['sections'][0].update(kind='unknown'),
    lambda data: data['sections'][0].update(id='../outside'),
    lambda data: data['sections'][0].update(id=''),
])
def test_invalid_or_duplicated_composition_fails(change):
    payload = composition()
    change(payload)
    with pytest.raises(ValidationError):
        DocumentComposition.model_validate(payload)


def test_composition_and_revision_are_a_pair(source):
    with pytest.raises(ValidationError, match='supplied together'):
        CVData.model_validate({**source.model_dump(), 'document': composition()})
    with pytest.raises(ValidationError, match='supplied together'):
        CVData.model_validate({**source.model_dump(), 'cv_template': {'template_id': 'managed', 'revision': 'a' * 64}})
    with pytest.raises(ValidationError, match='legacy filesystem path'):
        CVTemplateData(template_id='managed', revision='a' * 64, template_path='custom.tex')
    with pytest.raises(ValidationError, match='Invalid managed template ID'):
        CVTemplateData(template_id='../outside', revision='a' * 64)


def test_legacy_cv_adapts_without_creating_composition_or_rewriting_source(source, tmp_path):
    from src.cv_storage import load_cv_file
    payload = source.model_dump(mode='json')
    del payload['document']
    del payload['cv_template']['revision']
    path = tmp_path / 'cv.json'
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    value = load_cv_file(path, 'test')
    assert value.document is None and value.cv_template.revision is None
    assert path.read_bytes() == original


def test_composition_round_trips_through_cv_api_recoverable_save(client, services, imported):
    value = imported.cv.model_dump(mode='json')
    value['document'] = DocumentComposition.model_validate(composition()).model_dump(mode='json')
    value['document'] = DocumentComposition.model_validate(composition()).model_dump(mode='json')
    response = client.post('/v1/cv-data/test/versions/studio_copy', json=value)
    assert response.status_code == 200 and response.json() == value
    path = services.cvs.directory / 'test/studio_copy.json'
    original = path.read_bytes()
    value['document']['sections'].reverse()
    value['document']['sections'][0]['enabled'] = False
    assert client.put('/v1/cv-data/test/versions/studio_copy', json=value).status_code == 200
    assert client.get('/v1/cv-data/test/versions/studio_copy').json() == value
    assert any(backup.read_bytes() == original for backup in path.parent.glob('*.bak'))


def test_composition_size_and_count_limits_are_enforced():
    with pytest.raises(ValidationError):
        DocumentComposition(header_latex='x' * 65537)
    with pytest.raises(ValidationError):
        DocumentComposition(sections=[{'kind': 'latex', 'id': str(index), 'title': 'Raw'} for index in range(65)])
    with pytest.raises(ValidationError, match='2 MiB'):
        DocumentComposition(sections=[{'kind': 'latex', 'id': str(index), 'title': 'Raw', 'latex': '\U0001f600' * 262144}
                                      for index in range(3)])


@pytest.mark.parametrize('id', ['default_cv', 'template2'])
def test_import_is_an_independent_draft_preserving_all_static_bytes(source, id):
    from src.template_import import BUILTINS
    payload = source.model_dump(mode='json')
    source.cv_template.template_id = id
    original_cv = source.model_dump_json()
    path = ROOT / BUILTINS[id][0]
    original = path.read_bytes()
    draft = import_builtin_template(source, root=ROOT, new_template_id='new_template', name='New Template')
    assert source.model_dump_json() == original_cv
    assert path.read_bytes() == original
    assert draft.cv.personal_statement == payload['personal_statement']
    assert draft.cv.experience_sections == source.experience_sections
    assert draft.cv.candidate == source.candidate
    assert draft.cv.alternative_statements == source.alternative_statements
    assert draft.cv.cv_template.revision == package_revision(draft.package)
    assert draft.cv.cv_template.template_path is None
    assert draft.cv.cv_template.template_id == 'new_template'
    text = original.decode('utf-8')
    static = text.split('<experience_section>', 1)[1].rsplit(r'\end{document}', 1)[0]
    sections = draft.cv.document.sections
    assert [section.kind for section in sections] == ['statement', 'experience', 'education', 'skills',
                                                      'item_groups', 'latex']
    assert [section.id for section in sections] == ['about', 'experience', 'education', 'skills',
                                                    'other_information', 'publications']
    # No forced break: education flows after experience; page breaks stay an
    # explicit per-version choice.
    assert sections[2].page_break_before is False
    assert [entry.institution for entry in sections[2].entries] == ['ETH Zurich', 'ETH Zurich']
    assert sections[2].entries[0].details == ['Advisor: Prof. Eleni Chatzi']
    assert [(group.name, group.rating) for group in sections[3].groups] == [
        ('Programming', 6), ('Languages', 4),
        ('Other software {development} {skills}', None), ('Deep Learning', None)]
    assert [group.title for group in sections[4].groups] == [
        'Teaching assistant roles', 'Other academic engagements', 'Distinctions and certificates']
    assert sum(len(group.items) for group in sections[4].groups) == 7
    # Publications stay preserved raw LaTeX, never guessed into structured rows.
    assert sections[5].latex == static[static.index('\n\\begin{rSection}{Selected Publications}'):]
    assert draft.cv.document.header_latex == text[text.index(r'\name{'):text.index(r'\begin{document}')]
    shell = draft.package.files['main.tex']
    assert '<header>' in shell and '<sections>' in shell
    assert r'\name{' not in shell and 'ETH Zurich' not in shell and 'Selected Publications' not in shell
    assert draft.package.files['resume.cls'].encode() == (ROOT / 'assets/resume.cls').read_bytes()
    for logical_path, digest in draft.package.imported_hashes.items():
        assert sha256((ROOT / logical_path).read_bytes()).hexdigest() == digest


def test_import_rejects_custom_path_unknown_template_and_reimport(source, imported):
    source.cv_template.template_path = 'custom.tex'
    with pytest.raises(TemplateError, match='custom explicit'):
        import_builtin_template(source, root=ROOT, new_template_id='copy', name='Copy')
    source.cv_template.template_path = None
    source.cv_template.template_id = 'unknown'
    with pytest.raises(TemplateError, match='curated importer'):
        import_builtin_template(source, root=ROOT, new_template_id='copy', name='Copy')
    with pytest.raises(TemplateError, match='already composed'):
        import_builtin_template(imported.cv, root=ROOT, new_template_id='copy', name='Copy')


def test_modified_builtin_is_not_silently_parsed(source, tmp_path):
    source.cv_template.template_id = 'default_cv'
    asset = tmp_path / 'assets/latex_cv_template_v0.tex'
    asset.parent.mkdir()
    asset.write_text((ROOT / 'assets/latex_cv_template_v0.tex').read_text() + '\n% modified\n')
    original = asset.read_bytes()
    with pytest.raises(TemplateError, match='entry file has changed'):
        import_builtin_template(source, root=tmp_path, new_template_id='copy', name='Copy')
    assert asset.read_bytes() == original


def test_import_snapshots_mutable_class_resources_and_rejects_missing_classes(source, tmp_path):
    source.cv_template.template_id = 'default_cv'
    isolated = import_builtin_template(source, root=ROOT, new_template_id='isolated_copy', name='Copy')
    for logical in isolated.package.imported_hashes:
        target = tmp_path / logical
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / logical).read_bytes())
    draft = import_builtin_template(source, root=tmp_path, new_template_id='isolated_copy', name='Copy')
    captured_class = draft.package.files['resume.cls']
    (tmp_path / 'assets/resume.cls').write_text('changed after import')
    assert draft.package.files['resume.cls'] == captured_class
    config_path = tmp_path / 'config/templates.json'
    config = json.loads(config_path.read_text())
    config['cv_templates']['default_cv']['resources'] = {}
    config_path.write_text(json.dumps(config))
    with pytest.raises(TemplateError, match='missing a required class'):
        import_builtin_template(source, root=tmp_path, new_template_id='another_copy', name='Copy')


def test_constructing_or_reading_missing_repository_does_not_create_storage(repository):
    assert repository.list() == []
    assert repository.head('missing') is None
    with pytest.raises(FileNotFoundError):
        repository.get('missing')
    assert not repository.directory.exists()


def test_revisions_are_pinned_and_immutable_and_noop_save_is_idempotent(repository, imported):
    first = repository.save(imported.package, expected_revision=None)
    path = repository.directory / 'studio_copy/revisions' / f'{first.revision}.json'
    original = path.read_bytes()
    assert repository.save(imported.package, expected_revision=first.revision) == first
    assert path.read_bytes() == original
    changed = imported.package.model_copy(update={'name': 'Updated name'})
    second = repository.save(changed, expected_revision=first.revision)
    assert second.revision != first.revision
    assert repository.get('studio_copy') == second
    assert repository.get('studio_copy', first.revision) == first
    assert repository.list() == [second]
    assert path.read_bytes() == original


def test_stale_save_and_unconditional_overwrite_fail_without_touching_current(repository, imported):
    first = repository.save(imported.package, expected_revision=None)
    for expected in (None, '0' * 64):
        with pytest.raises(TemplateRevisionConflict):
            repository.save(imported.package.model_copy(update={'name': 'Conflict'}), expected_revision=expected)
    assert repository.get('studio_copy') == first


def test_concurrent_repository_instances_serialize_compare_and_save(repository, imported):
    first = repository.save(imported.package, expected_revision=None)

    def save(name):
        other = ManagedTemplateRepository(repository.directory)
        try:
            return other.save(imported.package.model_copy(update={'name': name}), expected_revision=first.revision)
        except TemplateRevisionConflict:
            return 'conflict'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(save, ['one', 'two']))
    assert sum(result == 'conflict' for result in results) == 1
    assert sum(isinstance(result, TemplateRevision) for result in results) == 1
    assert repository.get('studio_copy').package.name in ('one', 'two')


def test_head_publication_failure_keeps_history_and_retry_recovers(repository, imported, monkeypatch):
    from src import template_storage
    first = repository.save(imported.package, expected_revision=None)
    changed = imported.package.model_copy(update={'name': 'Pending'})
    write = template_storage.atomic_write_json

    def fail_head(path, data):
        if path.name == 'head.json':
            raise OSError('disk failure')
        write(path, data)

    with monkeypatch.context() as context:
        context.setattr(template_storage, 'atomic_write_json', fail_head)
        with pytest.raises(OSError, match='disk failure'):
            repository.save(changed, expected_revision=first.revision)
    assert repository.get('studio_copy') == first
    assert repository.get('studio_copy', package_revision(changed)).package == changed
    saved = repository.save(changed, expected_revision=first.revision)
    assert repository.get('studio_copy') == saved


def test_corrupt_revision_is_reported_and_retained(repository, imported):
    first = repository.save(imported.package, expected_revision=None)
    path = repository.directory / 'studio_copy/revisions' / f'{first.revision}.json'
    payload = json.loads(path.read_text())
    payload['package']['name'] = 'tampered'
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    with pytest.raises(ValidationError, match='does not match its content'):
        repository.get('studio_copy')
    with pytest.raises(ValidationError):
        repository.save(imported.package, expected_revision=first.revision)
    assert path.read_bytes() == original


@pytest.mark.parametrize('path', ['../outside.tex', '/outside.tex', 'x/../outside.tex', 'x//file.tex', r'x\file.tex', 'C:outside.tex', 'temp.tex', 'x/\x00file.tex'])
def test_bad_logical_filenames_cannot_be_saved(imported, path):
    payload = imported.package.model_dump(mode='json')
    payload['files'][path] = 'text'
    with pytest.raises(ValueError):
        TemplatePackage.model_validate(payload)


def test_package_rejects_missing_bindings_file_directory_collisions_and_oversize_text(imported):
    for path, text in [('main.tex', '<sections>'), ('bad.tex/file.tex', 'collision'), ('huge.tex', 'a' * 262145)]:
        payload = imported.package.model_dump(mode='json')
        payload['files'].update({path: text, 'bad.tex': 'parent'})
        with pytest.raises(ValueError):
            TemplatePackage.model_validate(payload)


def test_binary_assets_round_trip_without_live_files_and_cannot_shadow_text(imported, repository):
    package = imported.package.model_copy(deep=True)
    package.assets['images/logo.png'] = BinaryAsset.from_bytes(b'captured binary')
    saved = repository.save(package, expected_revision=None)
    assert saved.package.assets['images/logo.png'].content() == b'captured binary'
    payload = package.model_dump(mode='json')
    payload['assets']['main.tex'] = BinaryAsset.from_bytes(b'conflict').model_dump()
    with pytest.raises(ValidationError):
        TemplatePackage.model_validate(payload)
    with pytest.raises(ValidationError):
        BinaryAsset(data_base64='not base64')
    with pytest.raises(ValidationError):
        BinaryAsset.from_bytes(b'x' * (2 * 1024 * 1024 + 1))


def test_storage_symlink_cannot_redirect_a_save_to_neighboring_data(repository, imported, tmp_path):
    external = tmp_path / 'valuable'
    external.mkdir()
    sentinel = external / 'sentinel.json'
    sentinel.write_bytes(b'preserve')
    repository.directory.mkdir()
    (repository.directory / 'studio_copy').symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match='symlinks'):
        repository.save(imported.package, expected_revision=None)
    assert sentinel.read_bytes() == b'preserve'
    assert list(external.iterdir()) == [sentinel]


def test_renderer_refuses_to_drop_composition_when_its_package_is_missing(imported, tmp_path):
    from src.documents import FullCVDocument, DocSection
    document = FullCVDocument('Statement', DocSection('Experience', []), imported.cv.cv_template)
    with pytest.raises(TemplateError, match='Cannot load managed template'):
        document.render_pdf(str(tmp_path / 'not-created.pdf'))
    assert not (tmp_path / 'not-created.pdf').exists()
