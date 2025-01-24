from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from fpdf import FPDF
from sse_starlette.sse import EventSourceResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import time
import asyncio

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


PDF_DIR = "generated_pdfs"
os.makedirs(PDF_DIR, exist_ok=True)

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
        self.state_history = []
        
    def get_cv_data(self):
        if self.complete_cv_data is None:
            with open(self.candidate_cv_data_path, 'r') as f:
                self.complete_cv_data = json.loads(f.read())
        return self.complete_cv_data
    
    def update_state(self, msg):
        self.state = msg
        self.state_history.append(msg)
    
    def analyze(self):
        self.job_posting_analysis_obj = JobPostAnalysis(self.position_descr_text_path)
        self.job_posting_analysis_obj.analyze()        
        self.update_state('job posting analyzed')
        
        
    
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

async def process_stages(text: str):
    """
    Simulates processing stages (CV analysis, cross-analysis, PDF generation).
    Yields progress updates.
    """
    # Stage 1: CV analysis
    await asyncio.sleep(2)  # Simulating time delay
    yield {"stage": "CV Analysis", "progress": "50%", "message": "CV analysis completed"}

    # Stage 2: Cross-analysis
    await asyncio.sleep(2)  # Simulating time delay
    yield {"stage": "Cross-Analysis", "progress": "75%", "message": "Cross-analysis completed"}

    # Stage 3: PDF generation
    pdf_path = os.path.join(PDF_DIR, "generated.pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, text)
    pdf.output(pdf_path)
    await asyncio.sleep(2)  # Simulating time delay
    yield {"stage": "PDF Generation", "progress": "100%", "message": "PDF generated successfully", "file_path": pdf_path}

@app.get("/generate-progress")
async def generate_with_progress(text: str = Query(...)):
    if not text:
        raise HTTPException(status_code=400, detail="Text parameter is required")
    
@app.get("/download-pdf/{filename}")
async def download_pdf(filename: str):
    pdf_path = os.path.join(PDF_DIR, filename)
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(pdf_path, media_type="application/pdf", filename=filename)
