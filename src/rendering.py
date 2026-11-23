"""LaTeX compilation boundary; document content and artifact metadata live elsewhere."""

from pathlib import Path
import subprocess

from .outcomes import StageFailure
from .latex_templates import latex_text, RenderResource, resource_destination
from .template_registry import TemplateError


def latex_comment(text: str) -> str:
    """Escape plain analysis text while leaving authored CV LaTeX untouched."""
    return latex_text(text)


def materialize_resources(resources: tuple[RenderResource, ...], folder: Path) -> None:
    """Compile/export captured resources without replacing different existing files."""
    for resource in resources:
        target = folder / resource_destination(resource.destination)
        if not target.resolve().is_relative_to(folder.resolve()):
            raise TemplateError('Template resource escapes its destination directory')
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with target.open('xb') as output:
                output.write(resource.content)
        except FileExistsError:
            if target.read_bytes() != resource.content:
                raise TemplateError(f'Conflicting template resource: {resource.destination}')


def latex_to_pdf(latex_string: str, output_pdf: str, *, resources: tuple[RenderResource, ...] = ()) -> None:
    """Publish only a successful, nonempty XeLaTeX result from isolated scratch space."""
    from .tex_compiler import compile_latex
    try:
        content = compile_latex(latex_string, resources)
        Path(output_pdf).write_bytes(content)
    except (OSError, subprocess.SubprocessError, RuntimeError) as error:
        raise StageFailure('pdf_render', 'xelatex', error) from error
