"""TRF-04 / RFK-07: bounded shared XeLaTeX execution, not an untrusted-TeX sandbox."""

from pathlib import Path
import os
import shutil
import subprocess
import signal
import sys
import tempfile

MAX_PDF_BYTES = 16 * 1024 * 1024
MAX_DIAGNOSTICS = 8192
# Set limits in a separate single-threaded child, never preexec_fn in a server thread.
LIMIT_SCRIPT = '''import os, resource, sys
resource.setrlimit(resource.RLIMIT_FSIZE, (16777216, 16777216))
resource.setrlimit(resource.RLIMIT_CPU, (120, 120))
os.execv(sys.argv[1], sys.argv[1:])
'''


class LatexCompileError(RuntimeError):
    def __init__(self, message, diagnostics=''):
        self.diagnostics = diagnostics[:MAX_DIAGNOSTICS]
        super().__init__(message)


def run_tex(command, *, check, timeout, **kwargs):
    """Own the compiler process group, including XeTeX's PDF/font helpers."""
    with subprocess.Popen(command, **kwargs) as process:
        try:
            code = process.wait(timeout=timeout)
            if check and code:
                raise subprocess.CalledProcessError(code, command)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise


def compile_latex(latex: str, resources=(), *, timeout=120) -> bytes:
    """Compile and return PDF bytes; transcript details are discarded."""
    content, _transcript = compile_latex_with_transcript(latex, resources, timeout=timeout)
    return content


def compile_latex_with_transcript(latex: str, resources=(), *, timeout=120) -> tuple[bytes, str]:
    """Compile and also return the bounded transcript tail for layout-quality review."""
    # Lazy import avoids a cycle: the ordinary rendering adapter calls this boundary.
    from .rendering import materialize_resources
    scratch = '/tmp/opencode' if Path('/tmp/opencode').is_dir() else None
    with tempfile.TemporaryDirectory(prefix='auto_cv_tex_', dir=scratch) as temporary:
        folder = Path(temporary)
        materialize_resources(resources, folder)
        (folder / 'temp.tex').write_text(latex, encoding='utf-8')
        executable = shutil.which('xelatex')
        if not executable:
            raise LatexCompileError('XeLaTeX is not installed or not on PATH.')
        command = [sys.executable, '-c', LIMIT_SCRIPT, executable, '-no-shell-escape',
            '-file-line-error', '-interaction=nonstopmode', '-halt-on-error',
            '-output-directory', str(folder), 'temp.tex']
        # stdout is file-backed and child file-size limited, not an unbounded pipe.
        with tempfile.TemporaryFile(dir=scratch) as transcript:
            try:
                run_tex(command, check=True, stdout=transcript, stderr=subprocess.STDOUT,
                    timeout=timeout, cwd=folder, start_new_session=True,
                    env={**os.environ, 'openin_any': 'p', 'openout_any': 'p'})
            except (OSError, subprocess.SubprocessError) as error:
                diagnostics = _transcript_tail(transcript, folder)
                message = f'XeLaTeX timed out after {timeout} seconds.' if isinstance(error, subprocess.TimeoutExpired) else 'XeLaTeX compilation failed. Check the file/line diagnostics below.'
                raise LatexCompileError(message, diagnostics) from error
            transcript_text = _transcript_tail(transcript, folder)
        pdf = folder / 'temp.pdf'
        if not pdf.is_file() or not 0 < pdf.stat().st_size <= MAX_PDF_BYTES:
            raise LatexCompileError('XeLaTeX did not produce a nonempty PDF within the 16 MiB limit.')
        content = pdf.read_bytes()
        if not content.startswith(b'%PDF-'):
            raise LatexCompileError('XeLaTeX output is not a PDF.')
        return content, transcript_text


def _transcript_tail(transcript, folder: Path) -> str:
    transcript.seek(0, 2)
    transcript.seek(max(0, transcript.tell() - MAX_DIAGNOSTICS))
    return transcript.read(MAX_DIAGNOSTICS).decode('utf-8', errors='replace').replace(str(folder), '[scratch]')
