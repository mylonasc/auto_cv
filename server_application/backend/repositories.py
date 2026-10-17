"""Concrete JSON repositories. Construct explicitly, then inject into services.

Writers serialize with per-repository locks within the supported single process.
Atomic replacement prevents partial JSON; there is no multi-worker transaction
or optimistic-edit claim. Historical files are normalized on read, never swept.
"""

import json
import logging
from pathlib import Path
from threading import RLock

from src.cv_storage import cv_version_path, find_cv_file, load_cv_file, normalize_cv_data, save_cv_file
from src.storage import atomic_write_json
from models.api_models import WorkingCopy, Submission, RenderRecord
from models.legacy import normalize_working_copy, normalize_persisted_submission

logger = logging.getLogger(__name__)


def identifier(value: str) -> str:
    if not value or value in (".", "..") or any(character in value for character in ("/", "\\", "\0")):
        raise ValueError("Invalid storage identifier")
    return value


class CVRepository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.lock = RLock()

    def get(self, candidate, version="master"):
        with self.lock:
            return load_cv_file(find_cv_file(self.directory, identifier(candidate), identifier(version)), candidate)

    def save(self, candidate, version, data, *, create=False):
        with self.lock:
            candidate, version = identifier(candidate), identifier(version)
            if create and find_cv_file(self.directory, candidate, version).exists():
                raise FileExistsError(f"CV version '{version}' already exists")
            validated = normalize_cv_data(data, candidate)
            save_cv_file(cv_version_path(self.directory, candidate, version), validated)
            return validated

    def list(self, candidate):
        with self.lock:
            candidate = identifier(candidate)
            files = {path.stem: path for path in (self.directory / candidate).glob("*.json")}
            master = find_cv_file(self.directory, candidate, "master")
            if "master" not in files and master.exists():
                files["master"] = master
            return sorted([{"id": id, "name": id.replace("_", " ").title(), "last_modified": path.stat().st_mtime}
                           for id, path in files.items()], key=lambda row: row["last_modified"], reverse=True)

    def delete(self, candidate, version):
        with self.lock:
            path = cv_version_path(self.directory, identifier(candidate), identifier(version))
            if path.name == "master.json":
                raise ValueError("Cannot delete the master version")
            path.unlink()


class JSONRepository:
    def __init__(self, directory, model, key, normalize=lambda data: data):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.model, self.key, self.normalize = model, key, normalize
        self.lock = RLock()
        self.load_errors = {}

    def path(self, id):
        return self.directory / f"{identifier(id)}.json"

    def get(self, id):
        with self.lock:
            path = self.path(id)
            if not path.exists():
                return None
            return self.model.model_validate(self.normalize(json.loads(path.read_text(encoding="utf-8"))))

    def save(self, value):
        with self.lock:
            value = self.model.model_validate(value.model_dump())
            atomic_write_json(self.path(getattr(value, self.key)), value.model_dump(mode="json"))
            return value

    def update(self, id, transform):
        with self.lock:
            value = self.get(id)
            if value is None:
                raise FileNotFoundError(id)
            return self.save(transform(value))

    def list(self):
        with self.lock:
            self.load_errors = {}
            values = []
            for path in self.directory.glob("*.json"):
                try:
                    values.append(self.get(path.stem))
                except (ValueError, OSError) as error:
                    self.load_errors[path.name] = str(error)
                    logger.warning("Could not load %s; original record retained", path.name)
            return values

    def delete(self, id):
        with self.lock:
            self.path(id).unlink()


class WorkingCopyRepository(JSONRepository):
    def __init__(self, directory):
        super().__init__(directory, WorkingCopy, "job_id", normalize_working_copy)


class SubmissionRepository(JSONRepository):
    def __init__(self, directory):
        super().__init__(directory, Submission, "id", normalize_persisted_submission)


class ArtifactRepository:
    def __init__(self, directory, records_directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.records = JSONRepository(records_directory, RenderRecord, "id")

    def record(self, value):
        with self.records.lock:
            if self.records.path(value.id).exists():
                raise FileExistsError("Render records are immutable")
            return self.records.save(value)

    def for_artifact(self, job_id, artifact_id):
        return next((record for record in self.records.list() if record.job_id == job_id and
                     any(artifact["id"] == artifact_id for artifact in record.artifacts)), None)

    def resolve(self, job_id, artifact):
        extension = "tex" if artifact["kind"] == "latex" else artifact["kind"]
        stored = artifact.get("path")
        candidates = ([Path(stored), self.directory / Path(stored).name] if stored else [])
        candidates.append(self.directory / f"cv_output_{job_id}.{extension}")
        return next((str(path) for path in candidates if path.suffix == f".{extension}" and path.is_file()), None)
