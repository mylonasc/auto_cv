"""CLI-only cover-letter drafting and template rendering adapters."""

from bs4 import BeautifulSoup
from langchain_core.prompts import ChatPromptTemplate
from .domain import MotivationLetterTemplateData
from .template_registry import resolve_template_path
from . import rendering
from .latex_templates import prepare_template


class CoverLetterModel:
    def __init__(self, motivation_template=None, cover_letter_template_path=None):
        self.motivation_template = motivation_template or MotivationLetterTemplateData(template_path=cover_letter_template_path)
        self.cover_letter_template_path = resolve_template_path('motivation_letter_templates',
            self.motivation_template.template_id, self.motivation_template.template_path)

    def set_data(self, date_str, company_name, letter_body, name='Charilaos Mylonas, PhD',
                 prof_signature='\\\\Machine Learning Engineer\\\\Zurich'):
        self.date_str, self.company_name, self.letter_body = date_str, company_name, letter_body
        self.name, self.prof_signature = name, prof_signature

    def render_tex_template(self):
        return self.prepare_latex().latex

    def prepare_latex(self, include_scoring_comments=False):
        return prepare_template('motivation_letter_templates', self.motivation_template, {
            'DATETODAY': self.date_str, 'COMPANYNAME': self.company_name, 'LETTERCONTENT': self.letter_body,
            'NAME': self.name, 'PROF_SIGNATURE': self.prof_signature,
        })

    def to_pdf(self, file): self.render_pdf(file)
    def make_latex(self, include_scoring_comments=False): return self.render_tex_template()
    def render_pdf(self, file, include_scoring_comments=False):
        prepared = self.prepare_latex()
        rendering.latex_to_pdf(prepared.latex, file, resources=prepared.resources)


class CoverLetterDrafter:
    draft_prompt = """ I want you to draft a short cover letter for a job candidate. I will add a job description, a personal statement from the candidate, and
        the different professional experiences of that candidate.
        Role Description: {job_post_text}
        Personal Statement: {pers_statement}
        Professional Experience: {exp_section}
        Return the cover letter enclosed in <COVERLETTER> tags.
        """
    def __init__(self, cvca, llm_editor_model=None):
        self.cvca, self.llm_editor_model = cvca, llm_editor_model or cvca.llm_editor_model
        self._debug = {}

    async def get_cover_letter_text(self):
        inputs = {'exp_section': self.cvca.cv_model.experience_section.get_markdown(),
                  'pers_statement': self.cvca.cv_model.statement, 'job_post_text': self.cvca.job_post_analyzer.post_txt}
        result = await (ChatPromptTemplate.from_template(self.draft_prompt) | self.llm_editor_model).ainvoke(inputs)
        self._debug.update(inputs=inputs, raw_llm_output=result)
        text = result.content if hasattr(result, 'content') else str(result)
        soup = BeautifulSoup(text, 'html.parser')
        return soup.coverletter.text if soup.coverletter else text
