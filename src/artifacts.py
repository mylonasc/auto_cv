"""One artifact convention and writer for API and CLI rendering adapters."""

from pathlib import Path
from typing import Literal
from uuid import uuid4
from typing_extensions import TypedDict, NotRequired
from pydantic import ConfigDict, with_config


@with_config(ConfigDict(extra="forbid", allow_inf_nan=False))
class Artifact(TypedDict):
    id: str
    kind: Literal["pdf", "latex", "json"]
    filename: str
    path: NotRequired[str | None]
    source: NotRequired[str | None]
    job_id: NotRequired[str]
    created_at: NotRequired[str]


def render_artifacts(document, directory, stem, *, render_pdf=True, include_latex=True,
                     include_scoring_comments=False, source="analysis") -> list[Artifact]:
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for kind, extension, enabled in (("pdf", "pdf", render_pdf), ("latex", "tex", include_latex)):
        if not enabled:
            continue
        path = directory / f"{stem}.{extension}"
        if kind == "pdf":
            document.render_pdf(str(path), include_scoring_comments=include_scoring_comments)
            if not path.is_file():
                raise RuntimeError("PDF rendering did not produce an artifact")
        else:
            path.write_text(document.make_latex(include_scoring_comments=include_scoring_comments), encoding="utf-8")
        result.append({"id": f"{kind}_{uuid4().hex}", "kind": kind, "filename": path.name,
                       "path": str(path), "source": source})
    return result
