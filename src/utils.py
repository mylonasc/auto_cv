import subprocess
import tempfile
import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM
import json


TEMPLATE_NAME = os.path.join('assets','latex_cv_template_v0.tex')

def _trim_encap_tag_load_json(_res, encap_tag :str = 'output'):
    f1= _res.find("<" + encap_tag + ">")+len(encap_tag) + 2
    f2 = _res.find("</" + encap_tag + ">") 
    try:
        return json.loads(_res[f1:f2])
    except:
        print("----")
        print(f1,' to ',f2)
        print("----")
        print(_res[f1:f2])
        print("")
        raise Exception("json decode failed")

def _latex_to_pdf(latex_string, output_pdf):
    # Create a temporary directory to store intermediate files
    with tempfile.TemporaryDirectory() as tempdir:
        # Define the path for the temporary .tex file
        tex_file_path = os.path.join(tempdir, "temp.tex")
        
        # Write the LaTeX string to the .tex file
        with open(tex_file_path, "w") as tex_file:
            tex_file.write(latex_string)
        
        # Run xelatex to compile the .tex file into a PDF
        try:
            # -output-directory specifies where the PDF should be created (tempdir)
            subprocess.run(
                ["xelatex", "-output-directory", tempdir, tex_file_path],
                check=True
            )
            
            # Move the generated PDF to the specified output path
            pdf_path = os.path.join(tempdir, "temp.pdf")
            if os.path.exists(pdf_path):
                os.rename(pdf_path, output_pdf)
                print(f"PDF generated successfully: {output_pdf}")
            else:
                print("Error: PDF was not generated.")
        except subprocess.CalledProcessError as e:
            print("Error compiling LaTeX:", e)


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

class FullCVDocument:
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
    def copy(self):
        # new_experience = [e.copy() for e in self.experience_section.doc_section_items]
        return FullCVDocument(self.statement, self.experience_section.copy())


analyses_prompts = [
    {
    'prompt_txt' : '''
        You are a job analysis expert bot. You answer concisely, 
        and in a structured format. In what follows there is a post for a job position. 
        
        Job posting:
        ----
        {job_posting_text}
        
        Return in JSON format, a structured output that contains:
        1. the skills required for this position.
        2. the qualifications required for this position. 
        
        Wrap the answer in a <output> tag. 
            
        Example output:
        -----
        <output>
        {{ 
            "skills" : "python;machine learning;llm;German C1 level"
            "qualifications" : "PhD;Assembly;MS Word;5 years of experience;ability to work in teams;able to do double backflip;20 years of LLM experience"
            "preferred_qualifications" : "C++;NeurIPS first-authored publications"
        }}
        </output>
        
        Answer:
        ''',
        'prompt_provides' : 'basic_analysis'
    },
    {
    'prompt_txt' : '''You are a job analysis expert bot. You answer concisely, and in a structured format. 
        In what follows there is a post for a job position. 
        
        Job posting:
        ----
        {job_posting_text}
        
        Return in JSON format, a structured output that contains:
        1. The company name (if stated in the posting)
        2. The industry the company is operating in (if it is possible to infer from the posting)
        3. The title of the position
        4. Whether there are business and/or hands-on skills required for the position rated from 0 to 10 
        
        Wrap the answer in an <output> tag.
        
        Example output 1:
        -----
        <output>
        {{
            "company_name" : "Google",
            "industry" : "Software engineering, IT", 
            "job_title" : "Software Engineering III",
            "business_skills" :  2,
            "hands_on_skills" : 10
        }}
        </output>
        
        Example output 2:
        -----
        <output>
        {{
            "company_name" : "Meta",
            "industry" : "Software engineering, IT", 
            "job_title" : "Executive Assistant",
            "business_skills" :  10, 
            "hands_on_skills" : 1 
        }}
        </output>
        ''',
            'prompt_provides' : 'industry_and_position_analysis'     
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
        self.post_txt_file = post_txt_file
        with open(self.post_txt_file ,'r') as f:
            self.post_txt = f.read()
        
        if llm_model is None:
            self.model = _make_default_model_job_post_analysis()
        else:
            self.model = llm_model
        
        self.chains = []
        for an_t in analyses_prompts:
            prompt_str, prompt_provides = an_t['prompt_txt'], an_t['prompt_provides']
            prompt = ChatPromptTemplate.from_template(prompt_str)
            c = prompt | self.model
            self.chains.append({'chain' : c, 'provides' : prompt_provides})
        self.data = {} 
    
    def analyze(self):
        for c in self.chains:
            res = c['chain'].invoke({'job_posting_text' : self.post_txt})
            print(res)
            self.data[c['provides']] =_trim_encap_tag_load_json(res)
