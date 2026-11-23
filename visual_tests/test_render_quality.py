"""TRF-05 opt-in render-quality checks: real XeLaTeX and poppler, no fakes.

This directory is intentionally outside ``tests/`` so the default sandboxed
suite never collects it and its process guards never apply. Everything here
requires local XeLaTeX and poppler-utils and runs only on explicit request:

    datastore=$(mktemp -d /tmp/opencode/auto_cv_visual.XXXXXX)
    AUTO_CV_DATA_ROOT="$datastore" .venv/bin/python -m pytest -q visual_tests/

Only synthetic CVs are compiled; the seeded verbose CV exists solely in the
temporary data root above. Nothing is written to the checkout, and no model or
network call is made. Rendered PDFs, page PNGs and JSON quality reports are
left under ``$datastore/visual`` for human review.
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.composition import EntryListSection, ProjectEntry
from src.domain import CVData, CandidateMetadata, CVTemplateData, ExperienceSectionData
from src.render_pipeline import render_draft
from src.pdf_quality import build_report, parse_word_pages
from src.template_import import import_builtin_template

ROOT = Path(__file__).resolve().parents[1]
RUNS = [("default_cv", "Classic narrow work-experience rows"),
        ("template2", "Wide full-width work-experience rows")]


def representative_cv(template_id: str) -> CVData:
    long_bullet = ("Led Python delivery across a multi-team programme with a deliberately long bullet "
                   "that wraps across the row to expose indentation, wrapping and overflow behaviour.")
    return CVData(
        candidate=CandidateMetadata(candidate_id="visual", full_name="Visual Check"),
        personal_statement="Synthetic statement for render-quality review.",
        content_format="latex",
        cv_template=CVTemplateData(template_id=template_id),
        experience_sections=[
            ExperienceSectionData(company="Acme Corp", position="Senior Engineer",
                                  duration="2020 -- 2024", text_items=[long_bullet, "Shipped LaTeX tooling."]),
            ExperienceSectionData(company="Beta Ltd", position="Engineer",
                                  duration="2018 -- 2020", text_items=["Did admin work with Python."]),
        ])


def bbox_xml(pdf: Path) -> str:
    return subprocess.run(["pdftotext", "-bbox", str(pdf), "-"], capture_output=True,
                          text=True, check=True, timeout=30).stdout


def first_bullet_xmin(xml: str) -> float:
    pages, _sizes = parse_word_pages(xml)
    for page in pages:
        for word in page:
            if "Python" in word.text:
                return word.x_min
    raise AssertionError("representative bullet text missing from the rendered PDF")


@pytest.mark.parametrize("template_id,label", RUNS)
def test_starter_compiles_clean_boxes_and_records_quality(template_id, label, tmp_path, monkeypatch):
    datastore = Path(os.environ.get("AUTO_CV_DATA_ROOT", tmp_path / "data"))
    monkeypatch.setenv("AUTO_CV_DATA_ROOT", str(datastore))
    out = datastore / "visual" / template_id
    out.mkdir(parents=True, exist_ok=True)

    source = representative_cv(template_id)
    source.document = None
    imported = import_builtin_template(source, root=ROOT, new_template_id="visual", name="Visual")
    composed = imported.cv.model_copy(deep=True)
    composed.document.sections.insert(
        1, EntryListSection(kind="entries", id="projects", title="Personal projects",
                            entries=[ProjectEntry(id="p1", name="Renderer probe",
                                                  technologies=["Python", "LaTeX"],
                                                  bullets=["Wrapped bullet for the entries fragment."])]))
    rendered = render_draft(composed, imported.package, timeout=120)
    pdf = out / "cv.pdf"
    pdf.write_bytes(rendered.pdf_bytes)
    (out / "assembled.tex").write_text(rendered.latex, encoding="utf-8")
    (out / "transcript.txt").write_text(rendered.transcript, encoding="utf-8")
    subprocess.run(["pdftoppm", "-png", "-r", "80", str(pdf), str(out / "page")],
                   check=True, timeout=60)

    xml = bbox_xml(pdf)
    report = build_report(rendered.input_id, rendered.transcript, xml)
    (out / "quality.json").write_text(json.dumps({
        "starter": template_id, "label": label, "input_id": report.input_id,
        "pages": report.pages, "words": report.words,
        "overfull_count": report.overfull_count,
        "overfulls": [item.__dict__ for item in report.overfulls],
        "overlaps": [item.__dict__ for item in report.overlaps],
        "outside_page": [item.__dict__ for item in report.outside_page],
        "missing_glyphs": list(report.missing_glyphs), "omitted": report.omitted,
    }, indent=2), encoding="utf-8")

    assert report.pages >= 1 and report.words > 100
    assert report.overlaps == (), f"{template_id} word boxes overlap: {report.overlaps[:3]}"
    assert report.outside_page == (), f"{template_id} words escaped the page: {report.outside_page[:3]}"
    hard_missing = [item for item in report.missing_glyphs if item.startswith('Missing character')]
    assert hard_missing == [], f"{template_id} glyphs missing from the PDF: {hard_missing[:3]}"
    if report.missing_glyphs:
        print(f"[{template_id}] font substitutions (recorded, not failing): {report.missing_glyphs[:3]}")
    print(f"\n[{template_id}] {report.words} words, {report.overfull_count} overfull warnings; "
          f"artifacts: {out}")


def test_wide_starter_bullets_start_left_of_classic(tmp_path, monkeypatch):
    xmin = {}
    for template_id, _label in RUNS:
        imported = import_builtin_template(representative_cv(template_id), root=ROOT,
                                           new_template_id="visual", name="Visual")
        rendered = render_draft(imported.cv, imported.package, timeout=120)
        with tempfile.TemporaryDirectory(prefix="auto_cv_visual_", dir="/tmp/opencode") as folder:
            pdf = Path(folder) / "cv.pdf"
            pdf.write_bytes(rendered.pdf_bytes)
            xmin[template_id] = first_bullet_xmin(bbox_xml(pdf))
    assert xmin["template2"] < xmin["default_cv"], xmin
    print(f"\nfirst-bullet xMin: classic={xmin['default_cv']:.1f}pt wide={xmin['template2']:.1f}pt")
