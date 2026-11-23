"""TRF-02 / RFK-04: real composed output across source, analysis, HTTP and CLI."""

from pathlib import Path

import pytest

from src.composition import (EducationEntry, EducationSection, EntryListSection, ItemGroup, ItemGroupsSection,
    ProjectEntry, PublicationListSection, PublicationEntry, SkillGroup, SkillsSection)
from src.domain import CVData, CandidateMetadata, ExperienceSectionData
from src.documents import FullCVDocument
from src.template_import import import_builtin_template
from src.template_package import package_revision
from src.template_registry import TemplateError
from tests.helpers import wait_for_job

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def composed(services):
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Engineer',
        experience_sections=[ExperienceSectionData(company='Company', position='Engineer', duration='2020',
            text_items=['Python delivery', 'Did admin work'])])
    draft = import_builtin_template(source, root=ROOT, new_template_id='studio', name='Studio')
    draft.cv.document.sections[-1].enabled = False
    draft.cv.document.sections.insert(1, EntryListSection(kind='entries', id='projects', title='Personal projects',
        page_break_before=True, entries=[ProjectEntry(id='project', name='R&D project', technologies=['Python', 'C++'],
            bullets=['100% delivery'], description='Research & delivery')]))
    draft.cv.document.sections.append(PublicationListSection(kind='publications', id='papers', title='Publications', entries=[
        PublicationEntry(id='paper', title='A paper', authors='Author & Author', year='2024'),
        PublicationEntry(id='hidden-paper', title='Hidden paper', enabled=False)]))
    services.templates.repository.save(draft.package, expected_revision=None)
    return draft


def test_source_render_preserves_order_visibility_escaping_and_snapshots(composed, services):
    before = composed.cv.model_dump_json()
    document = FullCVDocument.from_cv(composed.cv, template_catalog=services.templates)
    prepared = document.prepare_latex()
    assert prepared.latex.index('Personal projects') < prepared.latex.index('Work Experience')
    assert r'R\&D project' in prepared.latex and r'100\% delivery' in prepared.latex
    assert 'Selected Publications' not in prepared.latex and 'Hidden paper' not in prepared.latex
    assert r'Author \& Author' in prepared.latex
    assert '\\newpage\n' in prepared.latex
    assert prepared.manifest.options['template_revision'] == composed.cv.cv_template.revision
    assert 'resume.cls' in {resource.destination for resource in prepared.resources}
    assert 'my_pic.jpeg' in {resource.destination for resource in prepared.resources}
    assert document.copy().make_latex() == prepared.latex
    assert composed.cv.model_dump_json() == before


def test_render_uses_exact_pin_not_changed_head(composed, services):
    changed = composed.package.model_copy(deep=True)
    changed.files['main.tex'] = changed.files['main.tex'].replace('<sections>', 'NEW STYLE\n<sections>')
    new = services.templates.repository.save(changed, expected_revision=package_revision(composed.package))
    assert new.revision != composed.cv.cv_template.revision
    text = FullCVDocument.from_cv(composed.cv, template_catalog=services.templates).make_latex()
    assert 'NEW STYLE' not in text


def test_imported_project_fragment_guards_empty_bullets(composed, services):
    project = next(section for section in composed.cv.document.sections if section.kind == 'entries').entries[0]
    project.bullets = []
    text = FullCVDocument.from_cv(composed.cv, template_catalog=services.templates).make_latex()
    assert r'\if\relax\detokenize{}\relax\else' in text
    assert r'R\&D project' in text


def test_imported_role_fragment_preserves_empty_role_without_empty_list(composed, services):
    composed.cv.experience_sections[0].text_items = []
    text = FullCVDocument.from_cv(composed.cv, template_catalog=services.templates).make_latex()
    assert r'\if\relax\detokenize{}\relax' in text
    assert r'\textbf{Company}' in text


def test_structured_sections_render_order_visibility_escaping_and_layout(composed, services):
    sections = composed.cv.document.sections
    sections.append(EducationSection(kind='education', id='schools', title='Education & training',
        entries=[EducationEntry(id='s1', institution='Example & Uni', dates='2020', degree='Ph.D. \\textit{Field}',
                                        details=['Advisor: Prof. X & Co.']),
                         EducationEntry(id='hidden-school', institution='Hidden', enabled=False)]))
    sections.append(SkillsSection(kind='skills', id='skills-extra', title='Extra skills',
        groups=[SkillGroup(id='g1', name='Lang & tools', items='A & B', rating=3),
                SkillGroup(id='g2', name='Plain skill', items='Just text')]))
    sections.append(ItemGroupsSection(kind='item_groups', id='service', title='Service',
        page_break_before=True,
        groups=[ItemGroup(id='service-group-1', title='Roles & duties', items=['Did 100% of X'])]))
    text = FullCVDocument.from_cv(composed.cv, template_catalog=services.templates).make_latex()
    assert text.index('Education \\& training') < text.index('Extra skills') < text.index('Service')
    assert 'Hidden' not in text
    # Authored LaTeX passes through in latex mode...
    assert r'Example & Uni' in text and 'Advisor: Prof. X & Co.' in text
    assert r'Ph.D. \textit{Field}' in text
    assert r'Roles & duties' in text and r'Did 100% of X' in text
    # ...and is escaped exactly once in plain-text mode.
    plain = composed.cv.model_copy(deep=True)
    plain.content_format = 'plain_text'
    plain_text = FullCVDocument.from_cv(plain, template_catalog=services.templates).make_latex()
    assert r'Example \& Uni' in plain_text and r'Did 100\% of X' in plain_text
    assert r'\textbackslash{}textit' in plain_text
    region = text.split('Extra skills')[1].split('Service')[0]
    assert region.count('\\bcirc') == 3 and region.count('\\wcirc') == 3
    assert '   \\bf{Lang & tools}&  A & B & \\bcirc \\bcirc \\bcirc \\wcirc \\wcirc \\wcirc \\\\' in text
    assert 'Plain skill' in text and 'Just text' in text
    assert sections[-1].page_break_before and '\\newpage\n' in text
    # Missing structured fragments fail closed instead of rendering raw text.
    import types
    broken = composed.package.model_copy(deep=True)
    broken.fragments.education_entry = None
    broken.files.pop('fragments/education_entry.tex')
    from src.template_package import package_revision as revision
    broken_cv = composed.cv.model_copy(deep=True)
    broken_cv.cv_template.revision = revision(broken)
    fake_catalog = types.SimpleNamespace(get=lambda reference: broken)
    with pytest.raises(TemplateError, match='education_entry'):
        FullCVDocument.from_cv(broken_cv, template_catalog=fake_catalog).prepare_latex()


def test_document_export_retains_composition_and_pin(composed, services, tmp_path):
    document = FullCVDocument.from_cv(composed.cv, template_catalog=services.templates)
    path = tmp_path / 'document.json'
    document.to_json(path)
    loaded = FullCVDocument.from_json(path)
    loaded.template_catalog = services.templates
    assert loaded.composition == document.composition
    assert loaded.cv_template == document.cv_template
    assert loaded.make_latex() == document.make_latex()


def test_initial_render_working_copy_and_submission_preserve_composition(client, services, composed, fake_model, pdf_calls):
    services.cvs.save('test', 'master', composed.cv)
    job_id = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python engineer'}).json()['id']
    job = wait_for_job(client, job_id)
    assert job['status'] == 'succeeded', job['error']
    assert 'Personal projects' in pdf_calls[-1].latex and 'A paper' in pdf_calls[-1].latex
    assert 'Did admin work' not in pdf_calls[-1].latex
    assert not any('Personal projects' in prompt for schema, prompt in fake_model.calls if schema == 'BulletAnalysis')
    copy = client.get(f'/v1/cv-jobs/{job_id}/working-cv').json()
    copy['personal_statement'] = 'Edited statement'
    result = client.post(f'/v1/cv-jobs/{job_id}/render', json={'working_copy': copy})
    assert result.status_code == 200
    assert 'Edited statement' in pdf_calls[-1].latex and 'Personal projects' in pdf_calls[-1].latex
    record = services.artifacts.for_artifact(job_id, result.json()['result']['artifacts'][-1]['id'])
    assert record.cv_snapshot.document == composed.cv.document
    assert record.cv_snapshot.cv_template.revision == composed.cv.cv_template.revision
    assert record.manifest.options['template_revision'] == composed.cv.cv_template.revision
    response = client.post('/v1/submissions/', json={'job_id': job_id})
    assert response.status_code == 200
    assert response.json()['cv_snapshot']['document'] == composed.cv.document.model_dump(mode='json')
    assert client.post(f'/v1/cv-jobs/{job_id}/render', json={'cv_template_id': 'default_cv'}).status_code == 422


@pytest.mark.asyncio
async def test_composed_cli_and_http_have_identical_selected_latex(client, services, composed, tmp_path):
    from tools.autocv import _make_parser, run_pipeline
    from src.cv_storage import save_cv_file
    services.cvs.save('test', 'master', composed.cv)
    job_id = client.post('/v1/cv-jobs/', json={'candidate': 'test', 'job_description': 'Python engineer'}).json()['id']
    job = wait_for_job(client, job_id)
    assert job['status'] == 'succeeded', job['error']
    input = tmp_path / 'input.json'
    save_cv_file(input, composed.cv)
    posting = tmp_path / 'posting.txt'
    posting.write_text('Python engineer')
    output = tmp_path / 'cli'
    args = _make_parser().parse_args(['--candidate-json', str(input), '--candidate-id', 'test', '--job-posting', str(posting),
        '--output-dir', str(output), '--skip-cover-letter'])
    await run_pipeline(args)
    api_tex = Path(next(artifact['path'] for artifact in job['result']['artifacts'] if artifact['kind'] == 'latex')).read_text()
    assert (output / 'latex_folder/cv_edited_with_comments.tex').read_text() == api_tex
    assert (output / 'latex_folder/resume.cls').is_file()
