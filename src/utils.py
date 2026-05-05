import json
import os
import subprocess
import tempfile
import asyncio
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate


from pathlib import Path

# Define project root
_here = Path(__file__).resolve().parent.parent
CV_CUSTOMIZER_ROOT = os.getenv('CV_CUSTOMIZER_ROOT', str(_here))

TEMPLATE_NAME = os.path.join(CV_CUSTOMIZER_ROOT, 'assets', 'latex_cv_template_v0.tex')
TEMPLATE_COVER_LETTER = os.path.join(CV_CUSTOMIZER_ROOT, 'assets', 'cover_letter', 'CoverLetter_Template.tex')

def _trim_encap_tag_load_json(_res: Any, encap_tag: str = "output") -> Dict[str, Any]:
    # Handle AIMessage or other objects by casting to string
    res_str = str(_res.content) if hasattr(_res, 'content') else str(_res)
    f1 = res_str.find("<" + encap_tag + ">") + len(encap_tag) + 2
    f2 = res_str.find("</" + encap_tag + ">")
    try:
        return json.loads(res_str[f1:f2])
    except Exception as exc:
        print("----")
        print(f1, " to ", f2)
        print("----")
        print(res_str[f1:f2])
        print("")
        raise Exception("json decode failed") from exc

def _latex_to_pdf(latex_string: str, output_pdf: str) -> None:
    import shutil
    # Create a temporary directory to store intermediate files
    with tempfile.TemporaryDirectory() as tempdir:
        # Define the path for the temporary .tex file
        tex_file_path = os.path.join(tempdir, "temp.tex")

        # Copy resume.cls if it exists in assets
        resume_cls_src = os.path.join(CV_CUSTOMIZER_ROOT, 'assets', 'resume.cls')
        if os.path.exists(resume_cls_src):
            shutil.copy(resume_cls_src, os.path.join(tempdir, 'resume.cls'))

        # Write the LaTeX string to the .tex file
        with open(tex_file_path, "w") as tex_file:
            tex_file.write(latex_string)

        # Run xelatex to compile the .tex file into a PDF
        try:
            # -output-directory specifies where the PDF should be created (tempdir)
            subprocess.run(
                ["xelatex", "-output-directory", tempdir, tex_file_path],
                check=True,
            )

            # Move the generated PDF to the specified output path
            pdf_path = os.path.join(tempdir, "temp.pdf")
            if os.path.exists(pdf_path):
                shutil.move(pdf_path, output_pdf)
                print(f"PDF generated successfully: {output_pdf}")
            else:
                print("Error: PDF was not generated.")
        except subprocess.CalledProcessError as exc:
            print("Error compiling LaTeX:", exc)

class DocSection:
    def __init__(self, section_title, doc_section_items):
        self.section_title = section_title
        self.doc_section_items = doc_section_items
    def get_markdown(self):
        s = f'## {self.section_title} \n'
        for _i in self.doc_section_items:
            s += _i.get_markdown()
        return s + '\n'
    def get_latex(self):
        s = f'\\begin{{rSection}}{{{self.section_title}}}\n'
        for _i in self.doc_section_items:
            s += _i.get_latex() + '\n'
        s += '\\end{rSection}\n'
        return s
    def copy(self):
        new_section_items = [i.copy() for i in self.doc_section_items]
        return DocSection(self.section_title, new_section_items)
    
class SectionListItem:
    def __init__(self, text, parent = None, comment = None):
        self.text = text
        self.parent = parent
        self.comment = comment
    def set_comment(self, comment):
        self.comment = comment
    def get_markdown(self):
        s = f'* {self.text}'
        if self.comment is not None:
            s += f' (comment:  {self.comment})'
        return s + '\n'
    def get_latex(self):
        s = f'    \\item {self.text}'
        if self.comment is not None:
            s += f'\\pdfcomment{{{self.comment}}}'
        return s + '\n'
    def copy(self):
        return SectionListItem(self.text, self.parent, self.comment)

class DocSectionItem:
    def __init__(self, company : str, duration : str, position : str, text_items : list[str]):
        self.company, self.duration, self.position =  company, duration, position
        self.section_item_list = [SectionListItem(li, parent = self) for li in text_items]
        self.comment = None
    def set_comment(self, comment):
        self.comment = comment
    def get_markdown(self):
        s = f'### {self.company} at {self.position} ({self.duration})\n'
        for i in self.section_item_list:
            s += i.get_markdown()
        return s
    def copy(self):
        text_items_copy = [i.text for i in self.section_item_list]
        return DocSectionItem(self.company, self.duration, self.position, text_items_copy)
    def get_latex(self):
        s = f"  \\begin{{myrSubsection}}{{{self.company}}}{{{self.duration}}}{{{self.position}}}\n"
        if self.comment is not None:
            s = f"  \\begin{{myrSubsection}}{{{self.company}}}{{{self.duration}}}{{{self.position}\\pdfcomment{{{self.comment}}}}}\n"
        for i in self.section_item_list:
            s += i.get_latex()
        s += f'  \\end{{myrSubsection}}\n'
        return s
    
    def to_dict(self):
        return {
            'company' : self.company,
            'duration' : self.duration,
            'position' : self.position,
            'text_items' : [i.text for i in self.section_item_list]
        }
    
    def to_json(self, file):
        with open(file,'w') as f:
            json.dump(self.to_dict(), f, indent=4)

class FullCVDocument:
    """ A class that takes care of rendering and encapsulating different standardized
    sections of the CV.
    """
    def __init__(self, statement : str, experience_section : DocSection):
        self.statement, self.experience_section = statement, experience_section
        
    def make_latex(self, newpage_after_experience = True):
        with open(TEMPLATE_NAME, 'r') as f:
            ff = f.read()

        ff = ff.replace('<statement>', self.statement)
        _exp_latex = self.experience_section.get_latex()
        if newpage_after_experience:
            _exp_latex += '\n' + '\\newpage' + '\n'  *2
        ff = ff.replace('<experience_section>', _exp_latex)
        return ff
    
    def render_pdf(self, out_file):
        _latex_to_pdf(self.make_latex(), out_file)
    
    def to_json(self, file):
        with open(file,'w') as f:
            json.dump({
                'statement' : self.statement,
                'experience_section' : {
                    'section_title' : self.experience_section.section_title,
                    'doc_section_items' : [
                        d.to_dict() for d in self.experience_section.doc_section_items
                    ]
                }
            }, f, indent=4)

    def from_json(file):
        with open(file,'r') as f:
            res = json.load(f)
        experience_section = DocSection(
            res['experience_section']['section_title'],
            [DocSectionItem(**d) for d in res['experience_section']['doc_section_items']]
        )
        return FullCVDocument(res['statement'], experience_section)

    

    def copy(self):
        # new_experience = [e.copy() for e in self.experience_section.doc_section_items]
        return FullCVDocument(self.statement, self.experience_section.copy())

class CoverLetterModel:
    def __init__(self, cover_letter_template_path = TEMPLATE_COVER_LETTER):
        self.cover_letter_template_path = cover_letter_template_path
        with open(self.cover_letter_template_path,'r') as f:
            self.cover_letter_template_tex_contents = f.read()
                    
    def set_data(self, date_str, company_name, letter_body, name = 'Charilaos Mylonas, PhD', prof_signature = "\\\\" + 'Machine Learning Engineer' + '\\\\' + 'Zurich'):
        self.date_str = date_str # <DATETODAY>
        self.company_name =company_name # <COMPANYNAME>
        self.letter_body = letter_body # <LETTERCONTENT>
        self.name = name  # <NAME>
        self.prof_signature = prof_signature #<PROF_SIGNATURE>
        
    def render_tex_template(self):
        replace_data = {
            'DATETODAY' : self.date_str, 
            'COMPANYNAME' : self.company_name, 
            'LETTERCONTENT' : self.letter_body,
            'NAME' : self.name,
            'PROF_SIGNATURE' : self.prof_signature
        }
        with open(self.cover_letter_template_path,'r') as f:
            new_tex = f.read()
        
        for k, v in replace_data.items():
            new_tex= new_tex.replace(f'<{k}>',v)
        
        return new_tex
    
    def to_pdf(self, file):
        _latex_to_pdf(self.render_tex_template(), file)

class BasicAnalysis(BaseModel):
    skills: str = Field(..., description="Semicolon separated list of required skills.")
    qualifications: str = Field(..., description="Semicolon separated list of required qualifications.")
    preferred_qualifications: Optional[str] = Field(None, description="Semicolon separated list of preferred qualifications.")

class IndustryPositionAnalysis(BaseModel):
    company_name: Optional[str] = Field(None, description="Name of the company.")
    industry: Optional[str] = Field(None, description="Industry the company operates in.")
    job_title: str = Field(..., description="Title of the position.")
    business_skills: float = Field(..., description="Business skills required (0-10).")
    hands_on_skills: float = Field(..., description="Hands-on skills required (0-10).")

analyses_prompts = [
    {
        'prompt_txt' : 'Analyze this job posting for required skills and qualifications: {job_posting_text}',
        'prompt_provides' : 'basic_analysis',
        'schema': BasicAnalysis
    },
    {
        'prompt_txt' : 'Analyze this job posting for company, industry, title and skill balance: {job_posting_text}',
        'prompt_provides' : 'industry_and_position_analysis',
        'schema': IndustryPositionAnalysis
    }
]

from .models import ModelFactory

def _load_defaults():
    from pathlib import Path
    import yaml
    _here = Path(__file__).resolve().parent.parent
    with open(os.path.join(_here, 'config/llm_defaults.yaml'),'r') as f:
        res = yaml.safe_load(f)
    return res

def _make_default_model_job_post_analysis():
    default_model_options = _load_defaults()
    return ModelFactory(**default_model_options['job_post_analysis_llm_default']).get_llm_model()

class JobPostAnalysis:
    def __init__(self, post_txt_file, analysis_prompts = analyses_prompts, llm_model = None):
        """ A class to manage analysis of the job posting. """
        self.post_txt_file = post_txt_file
        with open(self.post_txt_file ,'r') as f:
            self.post_txt = f.read()
        
        self.model = llm_model or _make_default_model_job_post_analysis()
        
        self.chains = []
        for an_t in analysis_prompts:
            prompt = ChatPromptTemplate.from_template(an_t['prompt_txt'])
            # Use structured output
            c = prompt | self.model.with_structured_output(an_t['schema'])
            self.chains.append({'chain' : c, 'provides' : an_t['prompt_provides']})
        self.data = {} 
    
    async def analyze(self):
        tasks = []
        for c in self.chains:
            tasks.append(c['chain'].ainvoke({'job_posting_text' : self.post_txt}))

        results = await asyncio.gather(*tasks)
        for c, res in zip(self.chains, results):
            # res is already a Pydantic object
            self.data[c['provides']] = res.model_dump()
