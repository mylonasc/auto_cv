"""TRF-01 / RFK-04: explicit, read-only import of the two shipped CV templates.

This is a curated converter, not a LaTeX parser. Exact entry fingerprints reject
unknown/customized layouts rather than guessing at content boundaries. Class and
resource edits are captured as bytes in the independent managed package draft.
"""

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
import re

from .composition import DocumentComposition, StatementSection, ExperienceSection, LatexSection
from .domain import CVData, CVTemplateData
from .template_package import (TemplatePackage, ComposedFragments, BinaryAsset, TEXT_EXTENSIONS,
                               logical_filename, package_revision)
from .template_registry import TemplateError, parse_template_definitions

BUILTINS = {
    "default_cv": ("assets/latex_cv_template_v0.tex", "ff64f2804b2a81c9263f357fce03b171ca3dad5942e7550a49c9b4a1a0aa9061"),
    "template2": ("assets/latex_cv_template_v2.tex", "3d51cb749d102fce1959724e0cd1272c354aed7385ca10b0c81e94df0119dd47"),
}


@dataclass(frozen=True)
class ImportedTemplate:
    """Unsaved values; the caller must explicitly create a new CV/package version."""
    cv: CVData
    package: TemplatePackage


def import_builtin_template(cv: CVData, *, root: Path, new_template_id: str, name: str) -> ImportedTemplate:
    if cv.document is not None or cv.cv_template.revision is not None:
        raise TemplateError("This CV is already composed; clone its managed package instead of importing a legacy template")
    id = cv.cv_template.template_id
    if id not in BUILTINS:
        raise TemplateError("Only the two shipped template layouts have a curated importer")
    if new_template_id == id:
        raise TemplateError("Choose a new template ID for the editable copy")
    root = Path(root).resolve()
    path, expected_hash = BUILTINS[id]
    expected_path = (root / path).resolve()
    if cv.cv_template.template_path:
        explicit = Path(cv.cv_template.template_path)
        explicit = explicit if explicit.is_absolute() else root / explicit
        if explicit.resolve() != expected_path:
            raise TemplateError("A custom explicit template path cannot be imported as a shipped layout")

    captured = {}
    hashes = {}

    def read(path):
        file = Path(path)
        file = (file if file.is_absolute() else root / file).resolve()
        if not file.is_relative_to(root):
            raise TemplateError("Built-in import dependencies must be inside the injected checkout")
        if file not in captured:
            try:
                captured[file] = file.read_bytes()
            except OSError as error:
                raise TemplateError(f"Cannot capture built-in template dependency: {file.name}") from error
        hashes[file.relative_to(root).as_posix()] = sha256(captured[file]).hexdigest()
        return captured[file]

    source_bytes = read(path)
    if sha256(source_bytes).hexdigest() != expected_hash:
        raise TemplateError("Shipped entry file has changed; preserve it and use a reviewed conversion instead of guessing")
    definitions = parse_template_definitions(json.loads(read('config/templates.json')))
    definition = definitions['cv_templates'].get(id)
    if definition is None or (root / definition.path).resolve() != expected_path or definition.layout is None:
        raise TemplateError("Built-in registry definition no longer matches the curated import")
    source = source_bytes.decode('utf-8')
    begin = r'\begin{document}'
    end = r'\end{document}'
    header_start = source.index(r'\name{')
    document_start = source.index(begin)
    statement_start = source.index(r'\begin{rSection}{About}')
    statement_end = source.index(r'\end{rSection}', statement_start) + len(r'\end{rSection}')
    experience_start = source.index('<experience_section>')
    static = source[experience_start + len('<experience_section>'):source.rindex(end)]
    technical = re.search(r'^%[-]+\n%\s+TECHNICAL STRENGTHS SECTION', static, re.MULTILINE).start()
    other = static.index('\n%\\vspace{-.0pt}\n\\begin{rSection}{Other Information}')
    publications = static.index('\n\\begin{rSection}{Selected Publications}')
    boundaries = (0, technical, other, publications, len(static))
    labels = (('education', 'Education'), ('strengths', 'Technical Strengths'),
              ('other_information', 'Other Information'), ('publications', 'Selected Publications'))
    composition = DocumentComposition(header_latex=source[header_start:document_start], sections=[
        StatementSection(kind='statement', id='about', title='About'),
        ExperienceSection(kind='experience', id='experience', title=cv.cv_template.experience_section_title),
        *(LatexSection(kind='latex', id=section_id, title=title, latex=static[boundaries[index]:boundaries[index + 1]])
          for index, (section_id, title) in enumerate(labels)),
    ])
    files = {
        'main.tex': source[:header_start] + '<header>' + begin + source[document_start + len(begin):statement_start]
                    + '<sections>' + source[source.rindex(end):],
        'fragments/statement.tex': source[statement_start:statement_end].replace('{About}', '{<title>}', 1),
    }
    layout = {key: read(value).decode('utf-8') for key, value in definition.layout.model_dump().items()}
    files.update({
        'fragments/experience.tex': source[statement_end:experience_start] + layout['section'],
        'fragments/section.tex': layout['section'].replace('<roles>', '<body>'),
        'fragments/role.tex': layout['role'], 'fragments/bullet.tex': layout['bullet'],
        'fragments/comment.tex': layout['comment'],
        'fragments/entries.tex': '<entries>',
        'fragments/entry.tex': '\\textbf{<name>}\\hfill <url>\\par\n<description>\\par\n'
                                '\\textit{<technologies>}\n'
                                '\\if\\relax\\detokenize{<bullets>}\\relax\\else\n'
                                '\\begin{itemize}\n<bullets>\\end{itemize}\n\\fi\n',
        'fragments/publications.tex': '<entries>',
        'fragments/publication.tex': '<authors> (<year>). \\textit{<title>}. <venue>. <url>\\par\n',
    })
    assets = {}
    for destination, path in definition.resources.items():
        logical_filename(destination)
        if destination in files:
            raise TemplateError(f"Import resource conflicts with a generated file: {destination}")
        content = read(path)
        if PurePosixPath(destination).suffix in TEXT_EXTENSIONS:
            files[destination] = content.decode('utf-8')
        else:
            assets[destination] = BinaryAsset.from_bytes(content)
    required_classes = {'resume.cls'} if id == 'default_cv' else {'resume.cls', 'resume_v2.cls'}
    if not required_classes.issubset(files):
        raise TemplateError('Built-in registry is missing a required class resource; refusing an incomplete import')
    package = TemplatePackage(template_id=new_template_id, name=name, entrypoint='main.tex',
        files=files, assets=assets, fragments=ComposedFragments(**{key: f'fragments/{key}.tex' for key in (
            'statement', 'experience', 'section', 'role', 'bullet', 'comment', 'entries', 'entry', 'publications', 'publication')}),
        imported_from=id, imported_hashes=hashes)
    payload = cv.model_dump(mode='json')
    payload['document'] = composition.model_dump(mode='json')
    payload['cv_template'] = CVTemplateData(template_id=new_template_id, revision=package_revision(package)).model_dump(mode='json')
    return ImportedTemplate(CVData.model_validate(payload), package)
