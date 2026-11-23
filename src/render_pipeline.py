"""TRF-05: isolated rendering boundary for composed Studio drafts.

All PDF production for unsaved drafts flows through :func:`render_draft`:
validate the CV/package pair, prepare LaTeX from the exact package revision,
compile in owned scratch space and return bytes, transcript and input identity.
Job rendering (:mod:`src.rendering`) and Studio preview delegate to this module
instead of composing compiler calls themselves.
"""

from dataclasses import dataclass
from hashlib import sha256

from .composed_rendering import prepare_composed
from .documents import FullCVDocument
from .template_package import package_revision
from .template_registry import TemplateError
from .tex_compiler import compile_latex_with_transcript


@dataclass(frozen=True)
class RenderedDraft:
    pdf_bytes: bytes
    transcript: str
    input_id: str
    latex: str


def render_draft(cv, package, *, timeout: int = 30, compiler=compile_latex_with_transcript) -> RenderedDraft:
    """Render an unsaved composed draft; never saves, scores or persists anything."""
    draft_cv = cv.model_copy(deep=True)
    if draft_cv.document is None or draft_cv.cv_template.template_id != package.template_id:
        raise TemplateError('Rendering requires a composed CV and its matching managed template draft.')
    draft_cv.cv_template.revision = package_revision(package)
    prepared = prepare_composed(FullCVDocument.from_cv(draft_cv), package)
    identity = sha256((draft_cv.model_dump_json() + draft_cv.cv_template.revision).encode('utf-8')).hexdigest()
    result = compiler(prepared.latex, prepared.resources, timeout=timeout)
    # Plain-bytes compilers (older fakes/adapters) carry no transcript for review.
    content, transcript = result if isinstance(result, tuple) else (result, '')
    return RenderedDraft(pdf_bytes=content, transcript=transcript, input_id=identity, latex=prepared.latex)
