"""TRF-01 / RFK-04: self-contained, revisionable managed template values.

Text files are editable; binary assets are immutable snapshots encoded explicitly
for atomic JSON storage. There are no live filesystem paths in a package.
"""

import base64
from hashlib import sha256
import json
from pathlib import PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .latex_templates import expand, resource_destination
from .domain import MANAGED_TEMPLATE_ID_PATTERN, TEMPLATE_REVISION_PATTERN

TemplateID = Annotated[str, Field(pattern=MANAGED_TEMPLATE_ID_PATTERN)]
RevisionID = Annotated[str, Field(pattern=TEMPLATE_REVISION_PATTERN)]

TEXT_EXTENSIONS = {".tex", ".cls", ".sty"}
BINARY_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".ttf", ".otf", ".woff", ".woff2"}


def logical_filename(value: str) -> str:
    resource_destination(value)
    if len(value) > 200 or any(ord(character) < 32 or character in (':', '\x7f') for character in value):
        raise ValueError("Invalid managed-template logical filename")
    return value


class PackageModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class BinaryAsset(PackageModel):
    data_base64: str = Field(max_length=2796204)

    @field_validator("data_base64")
    @classmethod
    def bounded_base64(cls, value):
        content = base64.b64decode(value, validate=True)
        if len(content) > 2 * 1024 * 1024 or base64.b64encode(content).decode("ascii") != value:
            raise ValueError("Asset must be canonical base64 and at most 2 MiB")
        return value

    def content(self) -> bytes:
        return base64.b64decode(self.data_base64, validate=True)

    @classmethod
    def from_bytes(cls, content: bytes):
        return cls(data_base64=base64.b64encode(content).decode("ascii"))


class ComposedFragments(PackageModel):
    statement: str
    experience: str
    section: str
    role: str
    bullet: str
    comment: str
    entries: str
    entry: str
    publications: str
    publication: str


FRAGMENT_FIELDS = {
    "statement": ("title", "statement"),
    "experience": ("title", "roles"),
    "section": ("title", "body"),
    "role": ("company", "duration", "position", "comment", "bullets"),
    "bullet": ("text", "comment"), "comment": ("text",),
    "entries": ("entries",),
    "entry": ("name", "description", "technologies", "url", "bullets"),
    "publications": ("entries",),
    "publication": ("authors", "title", "venue", "year", "url"),
}


class TemplatePackage(PackageModel):
    format_version: Literal[1] = 1
    template_id: TemplateID
    name: str = Field(min_length=1, max_length=200)
    entrypoint: str
    fragments: ComposedFragments
    files: dict[str, str] = Field(max_length=64)
    assets: dict[str, BinaryAsset] = Field(default_factory=dict, max_length=32)
    # Provenance is informational, never a resolver or a second writable source.
    imported_from: str | None = Field(default=None, max_length=200)
    imported_hashes: dict[str, RevisionID] = Field(default_factory=dict, max_length=128)

    @model_validator(mode="after")
    def validate_sources(self):
        for path in self.imported_hashes:
            logical_filename(path)
        names = list(self.files) + list(self.assets)
        if len(names) != len(set(names)):
            raise ValueError("Text and binary assets cannot share a logical filename")
        for name, text in self.files.items():
            logical_filename(name)
            if PurePosixPath(name).suffix not in TEXT_EXTENSIONS:
                raise ValueError("Managed text files must be .tex, .cls or .sty")
            if len(text.encode("utf-8")) > 262144:
                raise ValueError("A managed text file exceeds 256 KiB")
        for name in self.assets:
            logical_filename(name)
            if PurePosixPath(name).suffix not in BINARY_EXTENSIONS:
                raise ValueError("Unsupported managed binary asset type")
        for name in names:
            if any(str(parent) in names for parent in PurePosixPath(name).parents if str(parent) != '.'):
                raise ValueError("A package file cannot also be a parent directory")
        if self.entrypoint not in self.files:
            raise ValueError("Entrypoint must name a managed text file")
        shell = self.files[self.entrypoint]
        expand(shell, {"header": "", "sections": ""}, context="managed entrypoint")
        if shell.count("<header>") != 1 or shell.count("<sections>") != 1:
            raise ValueError("Managed shell must bind header and sections exactly once")
        for field, path in self.fragments.model_dump().items():
            if path not in self.files:
                raise ValueError(f"Fragment {field!r} must name a managed text file")
            expand(self.files[path], dict.fromkeys(FRAGMENT_FIELDS[field], ''), context=f"managed fragment {field}")
        if sum(len(text.encode("utf-8")) for text in self.files.values()) > 2 * 1024 * 1024:
            raise ValueError("Managed template text exceeds 2 MiB")
        if sum(len(asset.content()) for asset in self.assets.values()) > 8 * 1024 * 1024:
            raise ValueError("Managed template assets exceed 8 MiB")
        return self


def package_revision(package: TemplatePackage) -> str:
    """Hash all saved choices/bytes, independent of dictionary insertion order."""
    content = json.dumps(package.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return sha256(content.encode("utf-8")).hexdigest()


class TemplateRevision(PackageModel):
    revision: RevisionID
    package: TemplatePackage

    @model_validator(mode="after")
    def check_digest(self):
        if self.revision != package_revision(self.package):
            raise ValueError("Managed template revision does not match its content")
        return self
