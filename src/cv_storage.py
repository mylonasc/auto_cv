"""CV format boundary: explicit legacy adaptation and recoverable JSON saves.

Reads never rewrite source files. Saves retain byte-exact, content-addressed
backups before replacing an existing file. Broader repository/job lifecycle
ownership belongs to RFK-06; format compatibility lives here, not in consumers.
"""

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .domain import CVData, CandidateMetadata
from .storage import atomic_write_bytes


class CVDataConflict(ValueError):
    """Legacy copies disagree; choosing a winner could silently lose edits."""


def cv_version_path(data_dir: str | Path, candidate_id: str, version_id: str) -> Path:
    """Canonical destination for a version, matching historical filename rules."""
    filename = Path(version_id).name
    if not filename.endswith(".json"):
        filename += ".json"
    return Path(data_dir) / candidate_id / filename


def find_cv_file(data_dir: str | Path, candidate_id: str, version_id: str) -> Path:
    """Prefer versioned storage; legacy master locations are read-only fallbacks."""
    path = cv_version_path(data_dir, candidate_id, version_id)
    if not path.exists() and path.name == "master.json":
        for directory in (Path(data_dir), Path(data_dir).parent):
            legacy = directory / f"{candidate_id}_cv_data.json"
            if legacy.exists():
                return legacy
    return path


def normalize_cv_data(data: Any, candidate_id: str) -> CVData:
    """Adapt flat, nested, duplicated, or experience-list legacy payloads.

    Missing values may be filled from the other legacy location; equal copies
    collapse. Unequal copies (including empty versus nonempty) require explicit
    resolution. Versioned documents are validated strictly without adaptation.
    The input is never mutated and unknown fields are never silently dropped.
    """
    if isinstance(data, CVData):
        data = data.model_dump(mode="json")
    if isinstance(data, list):
        data = {"experience_sections": data}
    if not isinstance(data, dict):
        raise ValueError("CV data must be an object or legacy list of experience sections")
    payload = deepcopy(data)
    if "schema_version" not in payload:
        candidate = payload.pop("candidate", None)
        if candidate is None:
            candidate = {}
        if not isinstance(candidate, dict):
            raise ValueError("candidate must be an object")
        for field in ("personal_statement", "alternative_statements", "experience_sections"):
            if field in candidate:
                value = candidate.pop(field)
                if field in payload and payload[field] != value:
                    raise CVDataConflict(f"Conflicting legacy CV copies: {field}")
                payload[field] = value
        for field in CandidateMetadata.model_fields:
            if field in payload:
                value = payload.pop(field)
                if field in candidate and candidate[field] != value:
                    raise CVDataConflict(f"Conflicting legacy CV copies: candidate.{field}")
                candidate[field] = value
        candidate.setdefault("candidate_id", candidate_id)
        payload["candidate"] = candidate
        # Historical API responses could explicitly contain null template objects.
        for field in ("cv_template", "motivation_letter_template"):
            if payload.get(field) is None:
                payload.pop(field, None)
    result = CVData.model_validate(payload)
    if result.candidate.candidate_id != candidate_id:
        raise CVDataConflict("candidate_id does not match the requested candidate")
    return result


def load_cv_file(path: str | Path, candidate_id: str) -> CVData:
    """Load and normalize in memory only, preserving the original on disk."""
    return normalize_cv_data(json.loads(Path(path).read_text(encoding="utf-8")), candidate_id)


def save_cv_file(path: str | Path, data: CVData) -> Path | None:
    """Write canonical JSON atomically; return the immutable backup if replacing.

    Validation/serialization happens before any filesystem changes. Existing .bak
    files are never overwritten. A failed backup aborts the save, leaving source
    bytes intact; a failed replacement leaves the backup available for recovery.
    """
    content = CVData.model_validate(data.model_dump()).model_dump_json(indent=2).encode("utf-8")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = None
    if path.exists():
        original = path.read_bytes()
        digest = hashlib.sha256(original).hexdigest()
        backup = path.with_name(f"{path.name}.backup-{digest}.bak")
        try:
            with backup.open("xb") as target:
                target.write(original)
        except FileExistsError:
            if backup.read_bytes() != original:
                raise ValueError("Existing CV backup does not match its content hash")
    atomic_write_bytes(path, content)
    return backup
