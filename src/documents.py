"""Mutable document/render adapters; canonical writable content is src.domain.CVData."""

import json
from uuid import uuid4

from . import rendering
from .domain import CVTemplateData, ContentFormat
from .composition import DocumentComposition
from .latex_templates import prepare_template, legacy_layout


class DocSection:
    """Ordered roles with an authored section heading."""
    def __init__(self, section_title, doc_section_items):
        self.section_title, self.doc_section_items = section_title, doc_section_items

    def get_markdown(self):
        return f'## {self.section_title} \n' + ''.join(item.get_markdown() for item in self.doc_section_items) + '\n'

    def get_latex(self, include_scoring_comments=False):
        return legacy_layout().section(self, include_scoring_comments)

    def copy(self):
        return DocSection(self.section_title, [item.copy() for item in self.doc_section_items])


class SectionListItem:
    """One identified bullet; optional analysis comments are rendered only on request."""
    def __init__(self, text, parent=None, comment=None, id=None):
        self.text, self.parent, self.comment = text, parent, comment
        self.id = id or str(uuid4())

    def set_comment(self, comment): self.comment = comment

    def get_markdown(self):
        return f'* {self.text}' + (f' (comment:  {self.comment})' if self.comment is not None else '') + '\n'

    def get_latex(self, include_scoring_comments=False):
        return legacy_layout().bullet(self, include_scoring_comments)

    def copy(self): return SectionListItem(self.text, self.parent, self.comment, id=self.id)


class DocSectionItem:
    """Role metadata and identified bullets; copying preserves IDs and annotations."""
    def __init__(self, company, duration, position, text_items, id=None, item_ids=None):
        self.company, self.duration, self.position = company, duration, position
        self.id, self.comment = id or str(uuid4()), None
        if item_ids is not None and len(item_ids) != len(text_items):
            raise ValueError('item_ids must match text_items')
        self.section_item_list = [SectionListItem(text, parent=self, id=item_ids[index] if item_ids else None)
                                  for index, text in enumerate(text_items)]

    def set_comment(self, comment): self.comment = comment

    def get_markdown(self):
        return f'### {self.company} at {self.position} ({self.duration})\n' + ''.join(item.get_markdown() for item in self.section_item_list)

    def copy(self):
        result = DocSectionItem(self.company, self.duration, self.position, [item.text for item in self.section_item_list],
                                id=self.id, item_ids=[item.id for item in self.section_item_list])
        result.comment = self.comment
        for original, copied in zip(self.section_item_list, result.section_item_list):
            copied.comment = original.comment
        return result

    def get_latex(self, include_scoring_comments=False):
        return legacy_layout().role(self, include_scoring_comments)

    def to_dict(self):
        return {'id': self.id, 'item_ids': [item.id for item in self.section_item_list], 'company': self.company,
                'duration': self.duration, 'position': self.position, 'text_items': [item.text for item in self.section_item_list]}

    def to_json(self, file):
        with open(file, 'w', encoding='utf-8') as target:
            json.dump(self.to_dict(), target, indent=4)


class FullCVDocument:
    """Selected statement/roles plus a template; never a second canonical CV store."""
    def __init__(self, statement, experience_section, cv_template=None, *, content_format: ContentFormat = "latex",
                 composition: DocumentComposition | None = None, template_catalog=None):
        self.statement, self.experience_section = statement, experience_section
        self.cv_template = cv_template or CVTemplateData()
        if content_format not in ("latex", "plain_text"):
            raise ValueError("Unsupported CV content format")
        self.content_format = content_format
        self.composition = composition.model_copy(deep=True) if composition is not None else None
        self.template_catalog = template_catalog

    @classmethod
    def from_cv(cls, cv, *, template_catalog=None):
        return cls(cv.personal_statement, DocSection(cv.cv_template.experience_section_title,
            [DocSectionItem(**role.model_dump()) for role in cv.experience_sections]), cv.cv_template.model_copy(deep=True),
            content_format=cv.content_format, composition=cv.document, template_catalog=template_catalog)

    def prepare_latex(self, include_scoring_comments=False):
        if self.cv_template.revision is not None:
            from .template_catalog import TemplateCatalog
            from .composed_rendering import prepare_composed
            catalog = self.template_catalog if self.template_catalog is not None else TemplateCatalog.from_env()
            return prepare_composed(self, catalog.get(self.cv_template), include_scoring_comments=include_scoring_comments)
        if self.composition is not None:
            from .template_registry import TemplateError
            raise TemplateError('Composed content cannot use an unpinned legacy template')
        return prepare_template('cv_templates', self.cv_template, document=self,
                                include_scoring_comments=include_scoring_comments)

    def make_latex(self, include_scoring_comments=False):
        return self.prepare_latex(include_scoring_comments).latex

    def render_pdf(self, out_file, include_scoring_comments=False):
        prepared = self.prepare_latex(include_scoring_comments)
        rendering.latex_to_pdf(prepared.latex, out_file, resources=prepared.resources)

    def to_json(self, file):
        with open(file, 'w', encoding='utf-8') as target:
            json.dump({'statement': self.statement, 'content_format': self.content_format,
                'cv_template': self.cv_template.model_dump(mode='json'),
                'composition': self.composition.model_dump(mode='json') if self.composition is not None else None,
                'experience_section': {
                'section_title': self.experience_section.section_title,
                'doc_section_items': [item.to_dict() for item in self.experience_section.doc_section_items],
            }}, target, indent=4)

    @staticmethod
    def from_json(file):
        """Read the historical document export shape, not canonical CV content."""
        with open(file, encoding='utf-8') as source:
            data = json.load(source)
        section = data['experience_section']
        return FullCVDocument(data['statement'], DocSection(section['section_title'], [DocSectionItem(**item) for item in section['doc_section_items']]),
            CVTemplateData.model_validate(data.get('cv_template', {})), content_format=data.get('content_format', 'latex'),
            composition=DocumentComposition.model_validate(data['composition']) if data.get('composition') is not None else None)

    def copy(self):
        return FullCVDocument(self.statement, self.experience_section.copy(), cv_template=self.cv_template.model_copy(deep=True),
            content_format=self.content_format, composition=self.composition, template_catalog=self.template_catalog)
