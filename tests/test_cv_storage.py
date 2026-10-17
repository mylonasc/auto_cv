"""Canonical-format and recovery contracts, independent of HTTP consumers."""

import copy
import json

import pytest
from pydantic import ValidationError

from src.cv_storage import CVDataConflict, load_cv_file, normalize_cv_data, save_cv_file


@pytest.fixture
def flat_cv():
    return {"full_name": "Test Candidate", "profile": {"location": "Test City"},
            "personal_statement": "Statement", "alternative_statements": ["Alternative"],
            "experience_sections": [{"company": "Test", "position": "Engineer",
                                     "duration": "2020", "text_items": ["Python work"]}],
            "cv_template": {"template_id": "template2"}}


@pytest.mark.parametrize("shape", ["flat", "nested", "duplicated", "list"])
def test_legacy_shapes_are_idempotent_and_do_not_mutate_input(flat_cv, shape):
    if shape == "nested":
        payload = {"candidate": {k: v for k, v in flat_cv.items() if k != "cv_template"},
                   "cv_template": flat_cv["cv_template"]}
    elif shape == "duplicated":
        payload = dict(flat_cv, candidate={k: v for k, v in flat_cv.items() if k != "cv_template"})
    elif shape == "list":
        payload = flat_cv["experience_sections"]
    else:
        payload = flat_cv
    original = copy.deepcopy(payload)
    cv = normalize_cv_data(payload, "test")
    assert payload == original
    assert normalize_cv_data(cv.model_dump(), "test") == cv
    assert cv.experience_sections[0].text_items == ["Python work"]
    assert cv.candidate.candidate_id == "test"
    assert not ({"personal_statement", "experience_sections"} & cv.candidate.model_dump().keys())
    if shape != "list":
        assert cv.candidate.full_name == "Test Candidate"
        assert cv.candidate.profile == {"location": "Test City"}
        assert cv.cv_template.template_id == "template2"


@pytest.mark.parametrize("field,value", [
    ("personal_statement", "Different"), ("alternative_statements", []),
    ("experience_sections", []), ("full_name", "Different"), ("profile", {}),
])
def test_ambiguous_copies_are_rejected_without_mutation(flat_cv, field, value):
    flat_cv["candidate"] = {field: value}
    original = copy.deepcopy(flat_cv)
    with pytest.raises(CVDataConflict, match="Conflicting legacy CV copies"):
        normalize_cv_data(flat_cv, "test")
    assert flat_cv == original


@pytest.mark.parametrize("payload", [
    None, "invalid", {"candidate": []}, {"unexpected": "must not disappear"},
    {"experience_sections": [{"company": "Missing fields"}]},
    {"candidate": {"candidate_id": "someone-else"}},
    {"schema_version": 2, "candidate": {"candidate_id": "test"}},
    {"schema_version": 1, "candidate": {"candidate_id": "test", "personal_statement": "duplicate"}},
])
def test_malformed_or_unsupported_documents_fail_explicitly(payload):
    with pytest.raises((ValueError, ValidationError)):
        normalize_cv_data(payload, "test")


def test_reads_do_not_migrate_files_and_saves_preserve_original_backups(tmp_path, flat_cv):
    source = tmp_path / "master.json"
    original = json.dumps(flat_cv, indent=4).encode()
    source.write_bytes(original)
    old_backup = tmp_path / "master.json.bak"
    old_backup.write_bytes(b"earlier backup")
    cv = load_cv_file(source, "test")
    assert source.read_bytes() == original
    backup = save_cv_file(source, cv)
    assert backup.read_bytes() == original
    assert old_backup.read_bytes() == b"earlier backup"
    assert json.loads(source.read_text()) == cv.model_dump(mode="json")
    save_cv_file(source, cv)
    save_cv_file(source, cv)
    assert backup.read_bytes() == original
    assert len(list(tmp_path.glob("*.backup-*.bak"))) == 2
    assert load_cv_file(source, "test") == cv


def test_conflicting_read_leaves_source_and_backups_untouched(tmp_path, flat_cv):
    source = tmp_path / "master.json"
    flat_cv["candidate"] = {"personal_statement": "Conflicting"}
    original = json.dumps(flat_cv).encode()
    source.write_bytes(original)
    existing_files = set(tmp_path.iterdir())
    with pytest.raises(CVDataConflict):
        load_cv_file(source, "test")
    assert source.read_bytes() == original
    assert set(tmp_path.iterdir()) == existing_files


def test_failed_replacement_retains_original_and_backup(tmp_path, flat_cv, monkeypatch):
    from src import cv_storage

    path = tmp_path / "master.json"
    original = json.dumps(flat_cv).encode()
    path.write_bytes(original)

    def fail_replace(*args):
        raise OSError("simulated failure")

    monkeypatch.setattr(cv_storage.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated failure"):
        save_cv_file(path, normalize_cv_data(flat_cv, "test"))
    assert path.read_bytes() == original
    backups = list(tmp_path.glob("*.bak"))
    assert len(backups) == 1 and backups[0].read_bytes() == original
    assert not list(tmp_path.glob(".master.json.*"))


@pytest.mark.parametrize("shape", ["flat", "nested", "duplicated", "list"])
def test_api_and_repository_use_same_adapter_without_rewriting_source(client, isolated_runtime, flat_cv, shape, services):

    if shape == "nested":
        payload = {"candidate": {k: v for k, v in flat_cv.items() if k != "cv_template"},
                   "cv_template": flat_cv["cv_template"]}
    elif shape == "duplicated":
        payload = dict(flat_cv, candidate={k: v for k, v in flat_cv.items() if k != "cv_template"})
    elif shape == "list":
        payload = flat_cv["experience_sections"]
    else:
        payload = flat_cv
    path = isolated_runtime / "cv_section_data" / "test" / "master.json"
    path.parent.mkdir()
    original = json.dumps(payload).encode()
    path.write_bytes(original)
    response = client.get("/v1/cv-data/test/versions/master")
    assert response.status_code == 200
    canonical = response.json()
    assert canonical == services.cvs.get("test").model_dump(mode="json")
    assert canonical["schema_version"] == 1
    assert set(canonical["candidate"]) == {"candidate_id", "full_name", "profile"}
    assert path.read_bytes() == original
    assert not list(path.parent.glob("*.bak"))
    assert client.put("/v1/cv-data/test/versions/master", json=canonical).status_code == 200
    assert json.loads(path.read_text()) == canonical
    assert next(path.parent.glob("*.bak")).read_bytes() == original


@pytest.mark.parametrize("location", ["cv_section_data", "."])
def test_legacy_master_filename_is_read_only_fallback(client, isolated_runtime, flat_cv, location, services):

    source = isolated_runtime / location / "test_cv_data.json"
    original = json.dumps(flat_cv).encode()
    source.write_bytes(original)
    response = client.get("/v1/cv-data/test")
    assert response.status_code == 200
    assert response.json() == services.cvs.get("test").model_dump(mode="json")
    assert client.get("/v1/cv-data/test/versions").json()[0]["id"] == "master"
    destination = isolated_runtime / "cv_section_data" / "test" / "master.json"
    assert not destination.exists()
    assert client.put("/v1/cv-data/test", json=response.json()).status_code == 200
    assert destination.exists()
    assert source.read_bytes() == original


def test_api_rejects_conflicting_stored_data_without_overwriting(client, isolated_runtime, flat_cv):
    path = isolated_runtime / "cv_section_data" / "test" / "master.json"
    path.parent.mkdir()
    flat_cv["candidate"] = {"personal_statement": "Conflicting"}
    original = json.dumps(flat_cv).encode()
    path.write_bytes(original)
    response = client.get("/v1/cv-data/test/versions/master")
    assert response.status_code == 409
    assert "personal_statement" in response.json()["detail"]
    assert path.read_bytes() == original


def test_api_rejects_competing_payload_fields_and_wrong_identity(client, flat_cv):
    payload = normalize_cv_data(flat_cv, "test").model_dump(mode="json")
    payload["candidate"]["personal_statement"] = "Duplicate"
    assert client.post("/v1/cv-data/test/versions/master", json=payload).status_code == 422
    del payload["candidate"]["personal_statement"]
    payload["candidate"]["candidate_id"] = "someone-else"
    assert client.post("/v1/cv-data/test/versions/master", json=payload).status_code == 422
    assert client.get("/v1/cv-data/test/versions").json() == []


def test_template_resolution_is_render_time_only_and_honors_overrides(flat_cv):
    from src.template_registry import resolve_cv_templates

    cv = normalize_cv_data(flat_cv, "test")
    assert cv.cv_template.template_path is None
    resolved = resolve_cv_templates(cv)
    assert resolved.cv_template.template_path.endswith("latex_cv_template_v2.tex")
    assert cv.cv_template.template_path is None
    overridden = resolve_cv_templates(cv, cv_template_id="default_cv")
    assert overridden.cv_template.template_path.endswith("latex_cv_template_v0.tex")
    explicit = resolve_cv_templates(cv, cv_template_id="template2", cv_template_path="custom.tex")
    assert explicit.cv_template.template_path.endswith("custom.tex")


@pytest.mark.parametrize("template_id", ["default_cv", "template2"])
def test_supported_cv_loads_and_expands_each_template(tmp_path, template_id, pdf_calls):
    from pathlib import Path
    from src.template_registry import resolve_cv_templates
    from src.utils import FullCVDocument, DocSection, DocSectionItem

    repo = Path(__file__).resolve().parents[1]
    # Use the tracked supported CV, not an application store written by the test.
    source = repo / "server_application/backend/cv_section_data/charilaos_mylonas/master.json"
    original = source.read_bytes()
    cv = resolve_cv_templates(load_cv_file(source, "charilaos_mylonas"), cv_template_id=template_id)
    document = FullCVDocument(cv.personal_statement,
                             DocSection(cv.cv_template.experience_section_title, [
                                 DocSectionItem(**section.model_dump()) for section in cv.experience_sections
                             ]), cv_template=cv.cv_template)
    document.render_pdf(str(tmp_path / "cv.pdf"))
    assert cv.personal_statement in pdf_calls[0].latex
    assert cv.experience_sections[0].text_items[0] in pdf_calls[0].latex
    assert "<statement>" not in pdf_calls[0].latex
    assert "<experience_section>" not in pdf_calls[0].latex
    assert source.read_bytes() == original


@pytest.mark.asyncio
async def test_cli_consumes_canonical_cv_and_preserves_template_choice(tmp_path, flat_cv, pdf_calls):
    from tools.autocv import _make_parser, run_pipeline

    source = tmp_path / "input.json"
    save_cv_file(source, normalize_cv_data(flat_cv, "test"))
    original = source.read_bytes()
    posting = tmp_path / "job.txt"
    posting.write_text("Python engineer needed")
    args = _make_parser().parse_args([
        "--candidate-json", str(source), "--candidate-id", "test",
        "--job-posting", str(posting), "--output-dir", str(tmp_path / "output"),
        "--skip-cover-letter",
    ])
    await run_pipeline(args)
    assert len(pdf_calls) == 3
    assert all("resume_v2" in call.latex for call in pdf_calls)
    assert source.read_bytes() == original
