"""TRF-04/TRF-05: ephemeral draft preview and layout-quality reports.

Neither preview nor report saves revisions/CVs, calls models, or creates jobs,
submissions, render records or artifacts. Both share one compile slot per
application process so concurrent drafts cannot overload XeLaTeX.
"""

import asyncio
import shutil
import subprocess
import threading

from src.render_pipeline import render_draft, RenderedDraft
from src.pdf_quality import build_report, QualityReport
from src.tex_compiler import compile_latex_with_transcript


class PreviewBusy(RuntimeError):
    pass


class PreviewToolsUnavailable(RuntimeError):
    pass


def _bbox_xml(pdf_bytes: bytes, *, timeout: int) -> str:
    executable = shutil.which('pdftotext')
    if not executable:
        raise PreviewToolsUnavailable('pdftotext is not installed or not on PATH.')
    try:
        completed = subprocess.run([executable, '-bbox', '-', '-'], input=pdf_bytes,
                                   capture_output=True, timeout=timeout)
    except OSError as error:
        raise PreviewToolsUnavailable(f'pdftotext could not run: {error}') from error
    except subprocess.SubprocessError as error:
        raise PreviewToolsUnavailable(f'pdftotext failed: {error}') from error
    if completed.returncode:
        raise PreviewToolsUnavailable('pdftotext could not extract word boxes from the preview PDF.')
    return completed.stdout.decode('utf-8', errors='replace')


class StudioPreview:
    def __init__(self, *, compiler=compile_latex_with_transcript, bbox_runner=_bbox_xml):
        self.compiler = compiler
        self.bbox_runner = bbox_runner
        self.slots = threading.BoundedSemaphore(1)

    async def _guarded(self, operation):
        if not self.slots.acquire(blocking=False):
            raise PreviewBusy('A preview is already compiling. Try again shortly.')
        task = asyncio.create_task(asyncio.to_thread(operation))
        def finished(task):
            self.slots.release()
            if not task.cancelled():
                task.exception()  # Retrieve failures even if the HTTP caller disconnected.
        task.add_done_callback(finished)
        # Cancellation must not free capacity while the compiler thread is still alive.
        return await asyncio.shield(task)

    async def render(self, draft):
        return await self._guarded(lambda: self._render(draft))

    async def render_report(self, draft, *, bbox_timeout: int = 15):
        return await self._guarded(lambda: self._render_report(draft, bbox_timeout))

    def _render(self, draft):
        rendered = render_draft(draft.cv, draft.package, timeout=30, compiler=self.compiler)
        return rendered.pdf_bytes, rendered.input_id

    def _render_report(self, draft, bbox_timeout: int) -> QualityReport:
        rendered: RenderedDraft = render_draft(draft.cv, draft.package, timeout=30, compiler=self.compiler)
        xml = self.bbox_runner(rendered.pdf_bytes, timeout=bbox_timeout)
        return build_report(rendered.input_id, rendered.transcript, xml)
