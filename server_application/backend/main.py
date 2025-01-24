from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel
from fpdf import FPDF
from fastapi.middleware.cors import CORSMiddleware

import logging

# Set up logging
logging.basicConfig(level=logging.INFO)


import io


app = FastAPI()


# Allow all origins, or restrict it to your frontend's URL
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Use ["http://localhost:5173"] for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class TextInput(BaseModel):
    text: str

# Setting an env. variable so we can find the CV PDF creator:
import os
try:
    CV_CUSTOMIZER_ROOT=os.getenv('CV_CUSTOMIZER_ROOT')
    if CV_CUSTOMIZER_ROOT is None:
        raise Exception('defaulting - cv customizer root')
except:
    CV_CUSTOMIZER_ROOT = '/home/charilaos/Workspace/auto_cv'
import sys
sys.path.append(CV_CUSTOMIZER_ROOT)
from src.utils import JobPostAnalysis, FullCVDocument
from src.utils_cross_analysis import CVCrossAnalyzer
from src.utils import DocSectionItem, DocSection, FullCVDocument


# DEFAULT_AUTHOR='charilaos_mylonas'
# DEFAULT_AUTHOR_DATA_PATH = os.path.join('cv_section_data', f'{DEFAULT_AUTHOR}_cv_data.json')

import json
class CVMaker:
    def __init__(self, position_descr_text = 'Its a job or whatever.',  candidate='charilaos_mylonas'):
        self.candidate = candidate
        self.candidate_cv_data_path = os.path.join('cv_section_data', f'{self.candidate}_cv_data.json')
        self.complete_cv_data = None
        self.position_descr_text = position_descr_text
        self.position_descr_text_path = 'current_text_file.txt'
        with open(self.position_descr_text_path,'w') as f:
            f.write(self.position_descr_text)
        self.generated_pdf_path = None
        
    def get_cv_data(self):
        if self.complete_cv_data is None:
            with open(self.candidate_cv_data_path, 'r') as f:
                self.complete_cv_data = json.loads(f.read())
        return self.complete_cv_data
        
    def generate_pdf_end_to_end(self, file_to_write = 'test_after_edits_nocomments.pdf'):
        print("Analyzing the posting...")
        jpa = JobPostAnalysis(self.position_descr_text_path)
        jpa.analyze()
        experience_fields = self.complete_cv_data['experience_sections']
        personal_statement = self.complete_cv_data['personal_statement']
        doc_section_items = [DocSectionItem(**_d) for _d in experience_fields]
        #####
        doc_section = DocSection('Work Experience', doc_section_items)
        fcv = FullCVDocument(personal_statement, doc_section)
        fcv_copy = fcv.copy()
        doc_section_copy = doc_section.copy()
        fcv = FullCVDocument(personal_statement, doc_section_copy)
        cvca = CVCrossAnalyzer(jpa, fcv)
        cvca.analyze_job_experience_section()
        # cvca.cv_model.copy().render_pdf("test_before_edits.pdf")
        
        agg_metrics_prev = cvca.rewrite_reviewed_experience_section(max_section_items_keep=5,min_relevance_score=4)
        
        agg_metrics_prev = cvca.analyze_job_experience_section()
        
        agg_metrics_post = cvca.get_section_aggregate_metrics()
        
        cvca.cv_model.copy().render_pdf(file_to_write)
        
        return file_to_write
        

@app.post("/generate-pdf")
async def generate_pdf(input: TextInput):

    c = CVMaker(input.text, candidate = 'charilaos_mylonas')
    c.get_cv_data()
    pdf_file_path=  c.generate_pdf_end_to_end()
    try:
        # Generate 
        # pdf = FPDF()
        # pdf.add_page()
        # pdf.set_font("Arial", size=12)
        # pdf.multi_cell(0, 10, input.text)

        # # Save PDF to a bytes buffer
        # pdf_buffer = io.BytesIO()
        # pdf.output(pdf_buffer)
        # pdf_buffer.seek(0)
    # pdf_file_path = c.get_path()
        return FileResponse(
            pdf_file_path,
            media_type='application/pdf',
            filename='generated_cv.pdf'
        )
        # return StreamingResponse(
        #     pdf_buffer,
        #     media_type="application/pdf",
        #     headers={"Content-Disposition": "inline; filename=generated.pdf"},
        # )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))