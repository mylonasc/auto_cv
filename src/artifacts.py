"""One artifact convention and writer for API and CLI rendering adapters."""

from pathlib import Path
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4
from typing_extensions import TypedDict, NotRequired
from pydantic import ConfigDict, with_config
from .outcomes import StageFailure
from .latex_templates import RenderManifest, RenderResource
from . import rendering
from .storage import atomic_write_bytes
from .template_registry import TemplateError


@with_config(ConfigDict(extra="forbid", allow_inf_nan=False))
class Artifact(TypedDict):
    id: str
    kind: Literal["pdf", "latex", "json"]
    filename: str
    path: NotRequired[str | None]
    source: NotRequired[str | None]
    job_id: NotRequired[str]
    created_at: NotRequired[str]


@dataclass(frozen=True)
class RenderOutput:
    artifacts: list[Artifact]
    manifest: RenderManifest | None
    resources: tuple[RenderResource, ...] = ()


def render_artifacts(document, directory, stem, *, render_pdf=True, include_latex=True,
                     include_scoring_comments=False, source="analysis") -> RenderOutput:
    directory = Path(directory)
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise StageFailure("artifact_render", stem, error) from error
    outputs = [(kind, directory / f"{stem}.{extension}")
               for kind, extension, enabled in (("pdf", "pdf", render_pdf), ("latex", "tex", include_latex)) if enabled]
    for _, path in outputs:
        if path.exists():
            raise StageFailure("artifact_render", stem, FileExistsError("Output already exists"))
    if not outputs:
        return RenderOutput([], None)
    try:
        prepared = document.prepare_latex(include_scoring_comments=include_scoring_comments)
    except TemplateError:
        raise
    except Exception as error:
        raise StageFailure("latex_render", stem, error) from error
    result = []
    created = []
    try:
        for kind, path in outputs:
            created.append(path)
            if kind == "pdf":
                rendering.latex_to_pdf(prepared.latex, str(path), resources=prepared.resources)
                if not path.is_file() or path.stat().st_size == 0:
                    raise RuntimeError("PDF rendering did not produce a nonempty artifact")
            else:
                atomic_write_bytes(path, prepared.latex.encode("utf-8"))
            result.append({"id": f"{kind}_{uuid4().hex}", "kind": kind, "filename": path.name,
                           "path": str(path), "source": source})
    except Exception as error:
        # Only this operation's fresh paths; never sweep the artifact directory.
        for path in created:
            path.unlink(missing_ok=True)
        if isinstance(error, StageFailure):
            raise
        raise StageFailure("pdf_render" if kind == "pdf" else "latex_render", stem, error) from error
    manifest = prepared.manifest.model_copy(update={"options": {**prepared.manifest.options,
        "render_pdf": render_pdf, "include_latex": include_latex, "source": source}})
    return RenderOutput(result, manifest, prepared.resources)
