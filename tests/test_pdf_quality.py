"""TRF-05: offline layout-quality analysis; real tools are injected fakes here.

Only ``tests/test_render_visual.py`` (explicit opt-in) invokes XeLaTeX or
poppler. These tests prove the pure parsers, the pipeline boundary and the
report endpoint behave without any subprocess.
"""

import pytest

from src.pdf_quality import (build_report, find_outside_page, find_overlaps,
                             parse_missing_glyphs, parse_overfulls, parse_word_pages)

TRANSCRIPT = """[scratch]/temp.tex:38: Overfull \\hbox (30.0pt too wide) in paragraph at lines 38--38
Overfull \\vbox (52.95288pt too high) detected at line 40
Overfull \\hbox (1.66882pt too wide) in paragraph at lines 56--60
Missing character: There is no \\u2699 (U+2699) in font [lmroman10-regular]:!
LaTeX Font Warning: Font shape `TU/lmr/bx/sc' undefined
"""

XML = """<doc><page width="612.0" height="792.0">
<word xMin="10.0" yMin="10.0" xMax="60.0" yMax="20.0">alpha</word>
<word xMin="70.0" yMin="10.0" xMax="120.0" yMax="20.0">beta</word>
</page><page width="612.0" height="792.0">
<word xMin="10.0" yMin="10.0" xMax="200.0" yMax="40.0">wide</word>
<word xMin="50.0" yMin="20.0" xMax="120.0" yMax="35.0">overlap</word>
<word xMin="700.0" yMin="10.0" xMax="750.0" yMax="20.0">escaped</word>
</page></doc>"""


def test_overfull_and_glyph_parsing_is_bounded_and_totalled():
    overfulls, total = parse_overfulls(TRANSCRIPT + 'Overfull \\hbox (2.0pt too wide) in paragraph at lines 1--1\n' * 30)
    assert total == 33
    assert len(overfulls) == 20
    assert overfulls[0] == overfulls[0].__class__('hbox', 30.0, 38, 38, overfulls[0].excerpt)
    assert overfulls[1].kind == 'vbox' and overfulls[1].amount_pt == 52.95288
    glyphs = parse_missing_glyphs(TRANSCRIPT)
    assert any('Missing character' in item for item in glyphs)
    assert any('Font Warning' in item for item in glyphs)


def test_namespace_free_boxes_detect_overlaps_and_escaped_words():
    pages, sizes = parse_word_pages(XML)
    assert sizes == [(612.0, 792.0), (612.0, 792.0)]
    overlaps, _ = find_overlaps(pages)
    assert len(overlaps) == 1  # Adjacent alpha/beta merely touch and are ignored.
    assert overlaps[0].page == 1 and overlaps[0].first == 'wide'
    outside, _ = find_outside_page(pages, sizes)
    assert [(item.text, item.edge) for item in outside] == [('escaped', 'right')]


def test_build_report_assembles_bounded_quality_summary():
    report = build_report('a' * 64, TRANSCRIPT, XML)
    assert report.pages == 2 and report.words == 5
    assert report.overfull_count == 3 and len(report.overfulls) == 3
    assert len(report.overlaps) == 1 and len(report.outside_page) == 1
    assert report.missing_glyphs and report.omitted == {}


def test_pipeline_binds_revision_and_tolerates_plain_bytes_compilers():
    from src.domain import CVData, CandidateMetadata
    from src.render_pipeline import render_draft
    from src.template_import import import_builtin_template
    from pathlib import Path
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Statement')
    draft = import_builtin_template(source, root=Path(__file__).resolve().parents[1],
                                    new_template_id='quality', name='Quality')
    rendered = render_draft(draft.cv, draft.package,
                            compiler=lambda latex, resources, *, timeout: b'%PDF-bytes')
    assert rendered.pdf_bytes == b'%PDF-bytes' and rendered.transcript == ''
    assert len(rendered.input_id) == 64 and 'Statement' in rendered.latex


def test_report_endpoint_uses_fakes_without_subprocesses(client, services):
    from src.domain import CVData, CandidateMetadata
    from src.template_import import import_builtin_template
    from pathlib import Path
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Statement')
    draft = import_builtin_template(source, root=Path(__file__).resolve().parents[1],
                                    new_template_id='quality', name='Quality')
    services.studio_preview.compiler = lambda latex, resources, *, timeout: (b'%PDF-bytes', TRANSCRIPT)
    services.studio_preview.bbox_runner = lambda content, *, timeout: XML
    response = client.post('/v1/template-studio/preview-report', json={
        'cv': draft.cv.model_dump(mode='json'), 'package': draft.package.model_dump(mode='json')})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['pages'] == 2 and body['words'] == 5
    assert body['overfull_count'] == 3 and len(body['overlaps']) == 1
    assert body['outside_page'][0]['edge'] == 'right'
    assert len(body['input_id']) == 64


def test_report_rejects_invalid_drafts_and_missing_tools(client, services):
    from src.domain import CVData, CandidateMetadata
    from src.template_import import import_builtin_template
    from pathlib import Path
    from server_application.backend.services.studio_preview import PreviewToolsUnavailable
    source = CVData(candidate=CandidateMetadata(candidate_id='test'), personal_statement='Statement')
    draft = import_builtin_template(source, root=Path(__file__).resolve().parents[1],
                                    new_template_id='quality', name='Quality')
    payload = {'cv': draft.cv.model_dump(mode='json'), 'package': draft.package.model_dump(mode='json')}
    services.studio_preview.compiler = lambda latex, resources, *, timeout: (b'%PDF-bytes', TRANSCRIPT)
    services.studio_preview.bbox_runner = lambda content, *, timeout: XML
    payload['package']['files']['main.tex'] = '<sections>'
    assert client.post('/v1/template-studio/preview-report', json=payload).status_code == 422
    payload['package']['files']['main.tex'] = draft.package.files['main.tex']
    def missing(content, *, timeout):
        raise PreviewToolsUnavailable('pdftotext is not installed or not on PATH.')
    services.studio_preview.bbox_runner = missing
    response = client.post('/v1/template-studio/preview-report', json=payload)
    assert response.status_code == 501
    assert 'pdftotext' in response.json()['detail']
