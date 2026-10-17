"""LaTeX compilation boundary; document content and artifact metadata live elsewhere."""

from pathlib import Path
import shutil
import subprocess
import tempfile

from .outcomes import StageFailure
from .paths import project_root


def latex_comment(text: str) -> str:
    """Escape plain analysis text while leaving authored CV LaTeX untouched."""
    escapes = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
               '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
               '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(escapes.get(character, character) for character in text)


def latex_to_pdf(latex_string: str, output_pdf: str) -> None:
    """Publish only a successful, nonempty XeLaTeX result from isolated scratch space."""
    scratch = '/tmp/opencode' if Path('/tmp/opencode').is_dir() else None
    try:
        with tempfile.TemporaryDirectory(prefix='auto_cv_tex_', dir=scratch) as temporary:
            folder = Path(temporary)
            for name in ('resume.cls', 'resume_v2.cls'):
                source = project_root() / 'assets' / name
                if source.is_file():
                    shutil.copy(source, folder / name)
            tex = folder / 'temp.tex'
            tex.write_text(latex_string, encoding='utf-8')
            subprocess.run(['xelatex', '-interaction=nonstopmode', '-halt-on-error',
                            '-output-directory', str(folder), str(tex)],
                           check=True, capture_output=True, timeout=120)
            pdf = folder / 'temp.pdf'
            if not pdf.is_file() or pdf.stat().st_size == 0:
                raise RuntimeError('PDF was not generated or was empty')
            shutil.move(str(pdf), output_pdf)
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        raise StageFailure('pdf_render', 'xelatex', error) from error
