"""Template-owned LaTeX layout, one-pass expansion and immutable render inputs."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import PurePosixPath
import re

from pydantic import BaseModel, ConfigDict, Field

from .template_registry import absolute_path, resolve_template_definition, LatexLayout, TemplateError

TOKEN = re.compile(r"<([A-Za-z_][A-Za-z_0-9]*)>")


def resource_destination(destination: str) -> str:
    relative = PurePosixPath(destination)
    if (relative.is_absolute() or not relative.parts or '..' in relative.parts or '\\' in destination
            or destination != relative.as_posix() or destination in ('temp.tex', 'temp.pdf')):
        raise TemplateError(f"Invalid template resource destination: {destination!r}")
    return destination


def latex_text(text: str) -> str:
    """Escape plain text exactly once; authored LaTeX must explicitly bypass this."""
    escapes = {'\\': r'\textbackslash{}', '&': r'\&', '%': r'\%', '$': r'\$',
               '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}',
               '~': r'\textasciitilde{}', '^': r'\textasciicircum{}'}
    return ''.join(escapes.get(character, character) for character in text)


def expand(text: str, values: dict[str, str], *, context: str) -> str:
    """Validate the template, not inserted content; replacements cannot become tokens."""
    present = set(TOKEN.findall(text))
    if present != set(values):
        raise TemplateError(f"Template {context}: missing placeholders {sorted(set(values) - present)}; "
                         f"unknown placeholders {sorted(present - set(values))}")
    return TOKEN.sub(lambda match: values[match[1]], text)


class RenderManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    template_id: str
    template_path: str
    input_hashes: dict[str, str]
    resource_hashes: dict[str, str]
    latex_sha256: str
    options: dict[str, str | bool] = Field(default_factory=dict)


@dataclass(frozen=True)
class RenderResource:
    destination: str
    content: bytes


@dataclass(frozen=True)
class PreparedLatex:
    latex: str
    resources: tuple[RenderResource, ...]
    manifest: RenderManifest


class TemplateInputs:
    def __init__(self):
        self.hashes = {}
        self.contents = {}

    def read(self, path: str) -> bytes:
        try:
            canonical = absolute_path(path).resolve()
            if canonical not in self.contents:
                self.contents[canonical] = canonical.read_bytes()
            content = self.contents[canonical]
        except OSError as error:
            raise TemplateError(f"Cannot read template input: {path}") from error
        self.hashes[path] = sha256(content).hexdigest()
        return content

    def text(self, path: str) -> str:
        try:
            return self.read(path).decode("utf-8")
        except UnicodeError as error:
            raise TemplateError(f"Template input must be UTF-8: {path}") from error


class DocumentLayout:
    """All markup comes from declared fragments, not document/domain classes."""
    def __init__(self, paths: LatexLayout, inputs: TemplateInputs, *, content_format="latex"):
        self.fragments = {name: inputs.text(path) for name, path in paths.model_dump().items()}
        self.content_format = content_format
        for name, fields in {'section': ('title', 'roles'), 'role': ('company', 'duration', 'position', 'comment', 'bullets'),
                             'bullet': ('text', 'comment'), 'comment': ('text',)}.items():
            expand(self.fragments[name], dict.fromkeys(fields, ''), context=f'layout.{name}')

    def text(self, value):
        return latex_text(value) if self.content_format == "plain_text" else value

    def fragment(self, name, values):
        return expand(self.fragments[name], values, context=f"layout.{name}")

    def comment(self, value, enabled):
        return self.fragment("comment", {"text": latex_text(value)}).rstrip() if enabled and value is not None else ""

    def bullet(self, item, enabled=False):
        return self.fragment("bullet", {"text": self.text(item.text), "comment": self.comment(item.comment, enabled)})

    def role(self, role, enabled=False):
        return self.fragment("role", {"company": self.text(role.company), "duration": self.text(role.duration),
            "position": self.text(role.position), "comment": self.comment(role.comment, enabled),
            "bullets": ''.join(self.bullet(item, enabled) for item in role.section_item_list)})

    def section(self, section, enabled=False):
        return self.fragment("section", {"title": self.text(section.section_title),
            "roles": ''.join(self.role(role, enabled) for role in section.doc_section_items)})


def legacy_layout():
    """Compatibility for callers of the historical get_latex methods."""
    return DocumentLayout(LatexLayout(), TemplateInputs())


def prepare_template(group, reference, values=None, *, document=None, include_scoring_comments=False):
    definition = resolve_template_definition(group, reference.template_id, reference.template_path)
    inputs = TemplateInputs()
    source = inputs.text(definition.path)
    options = {"include_scoring_comments": include_scoring_comments}
    if document is not None:
        if definition.layout is None:
            raise TemplateError(f"CV template {reference.template_id!r} must declare a layout")
        layout = DocumentLayout(definition.layout, inputs, content_format=document.content_format)
        values = {"statement": layout.text(document.statement),
                  "experience_section": layout.section(document.experience_section, include_scoring_comments)}
        options["content_format"] = document.content_format
    latex = expand(source, values, context=f"{reference.template_id} ({definition.path})")
    resources = []
    for destination, path in definition.resources.items():
        resources.append(RenderResource(resource_destination(destination), inputs.read(path)))
    return PreparedLatex(latex, tuple(resources), RenderManifest(template_id=reference.template_id,
        template_path=definition.path, input_hashes=inputs.hashes,
        resource_hashes={resource.destination: sha256(resource.content).hexdigest() for resource in resources},
        latex_sha256=sha256(latex.encode()).hexdigest(), options=options))
