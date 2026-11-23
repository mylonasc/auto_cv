"""TRF-03 authoring uses production imports/storage and never mutates originals."""

import pytest
from src.domain import CVData, CandidateMetadata


@pytest.fixture
def request_data():
    return {'cv': CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Original').model_dump(mode='json'),
            'template_id': 'editable', 'name': 'Editable'}


def test_import_is_readonly_and_saves_are_separate(client, services, request_data):
    root = services.paths.root
    before = sorted(str(p.relative_to(root)) for p in root.rglob('*'))
    response = client.post('/v1/template-studio/import', json=request_data)
    assert response.status_code == 200, response.text
    draft = response.json()
    assert sorted(str(p.relative_to(root)) for p in root.rglob('*')) == before
    assert draft['cv']['personal_statement'] == 'Original'
    assert draft['cv']['document']['header_latex']
    result = client.post('/v1/template-studio/packages', json={'package': draft['package'], 'expected_revision': None})
    assert result.status_code == 200
    assert not services.cvs.list('test')
    revision = result.json()['revision']
    assert draft['cv']['cv_template']['revision'] == revision


def test_conflict_and_invalid_paths_retain_saved_revision(client, request_data):
    draft = client.post('/v1/template-studio/import', json=request_data).json()
    original = client.post('/v1/template-studio/packages', json={'package': draft['package'], 'expected_revision': None}).json()
    draft['package']['name'] = 'Changed'
    conflict = client.post('/v1/template-studio/packages', json={'package': draft['package'], 'expected_revision': None})
    assert conflict.status_code == 409
    assert 'reload' in conflict.json()['detail']
    assert client.get('/v1/template-studio/packages/editable').json() == original
    draft['package']['files']['../escape.tex'] = 'bad'
    assert client.post('/v1/template-studio/packages', json={'package': draft['package'], 'expected_revision': original['revision']}).status_code == 422
    assert client.get('/v1/template-studio/packages/editable', params={'revision': 'bad'}).status_code == 422


def test_unknown_import_rejected_without_writes(client, services, request_data):
    request_data['cv']['cv_template']['template_id'] = 'unknown'
    assert client.post('/v1/template-studio/import', json=request_data).status_code == 422
    assert services.templates.repository.list() == []
