"""TRF-02 / RFK-04: pure composition rendering over captured managed inputs."""

from hashlib import sha256

from .latex_templates import DocumentLayout, PreparedLatex, RenderResource, RenderManifest, expand, latex_text
from .template_package import TemplatePackage, package_revision
from .template_registry import TemplateError


class PackageLayout(DocumentLayout):
    def __init__(self, package, content_format):
        self.fragments = {name: package.files[path] for name, path in package.fragments.model_dump().items()}
        self.content_format = content_format


def prepare_composed(document, package: TemplatePackage, *, include_scoring_comments=False):
    package = TemplatePackage.model_validate(package.model_dump(mode='json'))
    revision = package_revision(package)
    if document.composition is None or document.cv_template.revision != revision or document.cv_template.template_id != package.template_id:
        raise TemplateError('Composition and the exact managed template revision must match')
    layout = PackageLayout(package, document.content_format)
    sections = []
    for section in document.composition.sections:
        if not section.enabled:
            continue
        title = latex_text(section.title)
        if section.kind == 'statement':
            body = layout.fragment('statement', {'title': title, 'statement': layout.text(document.statement)})
        elif section.kind == 'experience':
            body = layout.fragment('experience', {'title': title, 'roles': ''.join(
                layout.role(role, include_scoring_comments) for role in document.experience_section.doc_section_items)})
        elif section.kind == 'latex':
            body = section.latex
        else:
            entries = []
            for item in section.entries:
                if not item.enabled:
                    continue
                if section.kind == 'entries':
                    entries.append(layout.fragment('entry', {
                        'name': latex_text(item.name), 'description': latex_text(item.description),
                        'technologies': latex_text(', '.join(item.technologies)), 'url': latex_text(item.url),
                        'bullets': ''.join(layout.fragment('bullet', {'text': latex_text(text), 'comment': ''}) for text in item.bullets),
                    }))
                else:
                    entries.append(layout.fragment('publication', {key: latex_text(getattr(item, key))
                        for key in ('authors', 'title', 'venue', 'year', 'url')}))
            inner = layout.fragment(section.kind, {'entries': ''.join(entries)})
            body = layout.fragment('section', {'title': title, 'body': inner})
        sections.append(('\n\\newpage\n' if section.page_break_before else '') + body)
    latex = expand(package.files[package.entrypoint], {'header': document.composition.header_latex,
        'sections': ''.join(sections)}, context='managed shell')
    captured = {name: text.encode('utf-8') for name, text in package.files.items()}
    captured.update({name: asset.content() for name, asset in package.assets.items()})
    resources = tuple(RenderResource(name, content) for name, content in captured.items() if name != package.entrypoint)
    return PreparedLatex(latex, resources, RenderManifest(template_id=package.template_id,
        template_path=f'managed:{package.template_id}@{revision}/{package.entrypoint}',
        input_hashes={name: sha256(content).hexdigest() for name, content in captured.items()},
        resource_hashes={item.destination: sha256(item.content).hexdigest() for item in resources},
        latex_sha256=sha256(latex.encode('utf-8')).hexdigest(), options={
            'template_revision': revision, 'content_format': document.content_format,
            'include_scoring_comments': include_scoring_comments}))
