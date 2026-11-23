"""TRF-01 / RFK-04: immutable JSON revisions with serialized compare-and-save.

Constructing/reading the repository never creates storage. Explicit saves use a
local advisory writer lock, publish the immutable revision first and replace HEAD
last. An interrupted HEAD write leaves a recoverable revision, never lost history.
"""

from contextlib import contextmanager
import fcntl
import json
from pathlib import Path

from .storage import atomic_write_json
from .template_package import TemplatePackage, TemplateRevision, TemplateID, RevisionID, package_revision
from pydantic import TypeAdapter


class TemplateRevisionConflict(ValueError):
    """Another editor saved first; callers must explicitly reload/merge."""


class ManagedTemplateRepository:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)

    def _path(self, *parts):
        root = self.directory.resolve()
        path = self.directory
        for part in parts:
            path = path / part
            if path.is_symlink():
                raise ValueError("Managed-template storage cannot traverse symlinks")
        if not path.resolve().is_relative_to(root):
            raise ValueError("Managed-template path escapes storage")
        return path

    @contextmanager
    def _writer(self, template_id):
        lock = self._path(template_id, '.write.lock')
        lock.parent.mkdir(parents=True, exist_ok=True)
        with lock.open('a+b') as file:
            fcntl.flock(file, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(file, fcntl.LOCK_UN)

    def head(self, template_id: str) -> str | None:
        TypeAdapter(TemplateID).validate_python(template_id)
        path = self._path(template_id, 'head.json')
        if not path.exists():
            return None
        return TypeAdapter(RevisionID).validate_python(json.loads(path.read_text(encoding='utf-8')))

    def get(self, template_id: str, revision: str | None = None) -> TemplateRevision:
        TypeAdapter(TemplateID).validate_python(template_id)
        revision = revision if revision is not None else self.head(template_id)
        if revision is None:
            raise FileNotFoundError(f"Managed template not found: {template_id}")
        TypeAdapter(RevisionID).validate_python(revision)
        path = self._path(template_id, 'revisions', f'{revision}.json')
        value = TemplateRevision.model_validate_json(path.read_bytes())
        if value.revision != revision or value.package.template_id != template_id:
            raise ValueError("Managed revision identity does not match its storage path")
        return value

    def save(self, package: TemplatePackage, *, expected_revision: str | None) -> TemplateRevision:
        package = TemplatePackage.model_validate(package.model_dump(mode='json'))
        if expected_revision is not None:
            TypeAdapter(RevisionID).validate_python(expected_revision)
        with self._writer(package.template_id):
            current = self.head(package.template_id)
            if current != expected_revision:
                raise TemplateRevisionConflict('Template changed; reload the saved revision before saving')
            if current is not None:
                self.get(package.template_id, current)  # Do not hide a damaged HEAD revision.
            revision = package_revision(package)
            value = TemplateRevision(revision=revision, package=package)
            path = self._path(package.template_id, 'revisions', f'{revision}.json')
            if path.exists():
                if self.get(package.template_id, revision) != value:
                    raise ValueError('Existing managed revision differs; original retained')
            else:
                atomic_write_json(path, value.model_dump(mode='json'))
            if current != revision:
                atomic_write_json(self._path(package.template_id, 'head.json'), revision)
            return value

    def list(self) -> list[TemplateRevision]:
        if not self.directory.exists():
            return []
        return [self.get(path.name) for path in sorted(self.directory.iterdir())
                if self._path(path.name, 'head.json').is_file()]
