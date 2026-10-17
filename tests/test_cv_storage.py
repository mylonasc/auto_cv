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
