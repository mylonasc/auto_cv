"""Mutable document/render adapters; canonical writable content is src.domain.CVData."""

import json
from uuid import uuid4

from . import rendering
from .domain import CVTemplateData
from .template_registry import resolve_template_path


class DocSection:
    """Ordered roles with an authored section heading."""
    def __init__(self, section_title, doc_section_items):
        self.section_title, self.doc_section_items = section_title, doc_section_items

    def get_markdown(self):
        return f'## {self.section_title} \n' + ''.join(item.get_markdown() for item in self.doc_section_items) + '\n'

    def get_latex(self, include_scoring_comments=False):
        return (f'\\begin{{rSection}}{{{self.section_title}}}\n' +
                ''.join(item.get_latex(include_scoring_comments=include_scoring_comments) + '\n' for item in self.doc_section_items) +
                '\\end{rSection}\n')

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
        comment = f'\\pdfcomment{{{rendering.latex_comment(self.comment)}}}' if include_scoring_comments and self.comment is not None else ''
        return f'    \\item {self.text}{comment}\n'

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
        comment = f'\\pdfcomment{{{rendering.latex_comment(self.comment)}}}' if include_scoring_comments and self.comment is not None else ''
        return (f'  \\begin{{myrSubsection}}{{{self.company}}}{{{self.duration}}}{{{self.position}{comment}}}\n' +
                ''.join(item.get_latex(include_scoring_comments=include_scoring_comments) for item in self.section_item_list) +
                '  \\end{myrSubsection}\n')

    def to_dict(self):
        return {'id': self.id, 'item_ids': [item.id for item in self.section_item_list], 'company': self.company,
                'duration': self.duration, 'position': self.position, 'text_items': [item.text for item in self.section_item_list]}

    def to_json(self, file):
        with open(file, 'w', encoding='utf-8') as target:
            json.dump(self.to_dict(), target, indent=4)


class FullCVDocument:
    """Selected statement/roles plus a template; never a second canonical CV store."""
    def __init__(self, statement, experience_section, cv_template=None):
        self.statement, self.experience_section = statement, experience_section
        self.cv_template = cv_template or CVTemplateData()

    def make_latex(self, newpage_after_experience=True, include_scoring_comments=False):
        path = resolve_template_path('cv_templates', self.cv_template.template_id, self.cv_template.template_path)
        with open(path, encoding='utf-8') as template:
            text = template.read()
        experience = self.experience_section.get_latex(include_scoring_comments=include_scoring_comments)
        if newpage_after_experience:
            experience += '\n\\newpage\n\n'
        return text.replace('<statement>', self.statement).replace('<experience_section>', experience)

    def render_pdf(self, out_file, include_scoring_comments=False):
        rendering.latex_to_pdf(self.make_latex(include_scoring_comments=include_scoring_comments), out_file)

    def to_json(self, file):
        with open(file, 'w', encoding='utf-8') as target:
            json.dump({'statement': self.statement, 'experience_section': {
                'section_title': self.experience_section.section_title,
                'doc_section_items': [item.to_dict() for item in self.experience_section.doc_section_items],
            }}, target, indent=4)

    @staticmethod
    def from_json(file):
        """Read the historical document export shape, not canonical CV content."""
        with open(file, encoding='utf-8') as source:
            data = json.load(source)
        section = data['experience_section']
        return FullCVDocument(data['statement'], DocSection(section['section_title'], [DocSectionItem(**item) for item in section['doc_section_items']]))

    def copy(self):
        return FullCVDocument(self.statement, self.experience_section.copy(), cv_template=self.cv_template.model_copy(deep=True))
