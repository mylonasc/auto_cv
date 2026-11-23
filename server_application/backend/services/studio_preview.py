"""TRF-04: ephemeral draft preview, separate from jobs, scoring and persistence."""

import asyncio
from hashlib import sha256
import threading

from src.composed_rendering import prepare_composed
from src.documents import FullCVDocument
from src.template_package import package_revision
from src.tex_compiler import compile_latex
from src.template_registry import TemplateError


class PreviewBusy(RuntimeError):
    pass


class StudioPreview:
    def __init__(self, *, compiler=compile_latex):
        self.compiler = compiler
        self.slots = threading.BoundedSemaphore(1)

    async def render(self, draft):
        if not self.slots.acquire(blocking=False):
            raise PreviewBusy('A preview is already compiling. Try again shortly.')
        task = asyncio.create_task(asyncio.to_thread(self._render, draft))
        def finished(task):
            self.slots.release()
            if not task.cancelled():
                task.exception()  # Retrieve failures even if the HTTP caller disconnected.
        task.add_done_callback(finished)
        # Cancellation must not free capacity while the compiler thread is still alive.
        return await asyncio.shield(task)

    def _render(self, draft):
        cv = draft.cv.model_copy(deep=True)
        if cv.document is None or cv.cv_template.template_id != draft.package.template_id:
            raise TemplateError('Preview requires a composed CV and its matching managed template draft.')
        cv.cv_template.revision = package_revision(draft.package)
        prepared = prepare_composed(FullCVDocument.from_cv(cv), draft.package)
        identity = sha256((cv.model_dump_json() + cv.cv_template.revision).encode('utf-8')).hexdigest()
        return self.compiler(prepared.latex, prepared.resources, timeout=30), identity
