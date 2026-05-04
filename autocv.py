""" AutoCV helps creating a first customized CV and Cover letter draft
for job applications
""" 
from src.models import ModelFactory
from src.utils import JobPostAnalysis, FullCVDocument, CoverLetterModel, DocSectionItem, DocSection
from src.utils_cross_analysis import CVCrossAnalyzer, CoverLetterDrafter
from src.utils_cross_analysis import CoverLetterDrafter

from datetime import datetime
import json
import tempfile 
import os
import shutil

def _log_agg_metrics(agg_metrics, txt_suff = None):
    if txt_suff is None:
        txt_suff = ' ? '
    _log(f' - ({txt_suff}) Weighted Mean Section Relevance: ' , agg_metrics[0]['weighted_mean_section_relevance'])
    _log(f' - ({txt_suff}) Mean Section Relevance: ' , agg_metrics[0]['mean_section_relevance'])
    _log(f' - ({txt_suff}) Conciseness Relevance Metric: ' , agg_metrics[0]['conciseness_relevance_metric'])
    _log(f' - ({txt_suff}) Section Scores:\n', agg_metrics[1])

def _log(*s):
    print(*s)

#job_posting_path = 'job_postings_text/AltusSearch_MLStrategist_Commodities_26062025.txt'
#job_posting_path = 'job_postings_text/Capgemini_SeniorDataScientist_June3_2025-v2.txt'
#job_posting_path = 'job_postings_text/KAIKO_SeniorMLEngineer_27062025.txt'
# job_posting_path = 'job_postings_text/ON_SeniorMLScientist_02072025.txt' 
# job_posting_path = 'job_postings_text/RepRisk_SeniorMachineLearningEngineer_02072025.tex'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/AIMLQuality_GoogleYoutube_300825.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/Mistral_AIResearcher_161025.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/NVIdia_SeniorDeeplearningEng_151125.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/Anthropic_151125.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/Meta_151125.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/CloeRecruiter_linkedin_171125.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/DeepMind-280126.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/Google-YoutubeAIML_14022026.txt'
# job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/DeepMind-gemini-app_250426.txt'
job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/Microsoft-MAI-MachineLearning_250426.txt'
job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/FictionalJobPosting_Apr26.txt'
job_posting_path = '/home/charilaos/Workspace/auto_cv/job_postings_text/Google_GNNs_Apr30-2026.txt'


output_folder = 'autocv_output_' + job_posting_path.split('/')[-1][:-4]

company_name = 'Google'
name = 'Charilaos Mylonas'
prof_signature = "\\\\" + 'Lead Software Engineer \\\\ Zurich'
MAX_SECTION_ITEMS_KEEP = 5
MIN_RELEVANCE_SCORE_KEEP = 7
MIN_SECTION_ITEMS_KEEP = 1

ALT_STATEMENTS_PATH = 'assets/statements.txt'
# EXP_PATH= 'assets/experience_fields.json'
# EXP_PATH= 'assets/experience_fields_oct_25.json'
EXP_PATH= '/home/charilaos/Workspace/auto_cv/assets/experience_fields_oct25.json'


TMP_FOLDER = tempfile.mkdtemp()
#_ = input('temp folder is (press any key to continue)' + TMP_FOLDER)

# with open(ALT_STATEMENTS_PATH,'r') as f:
#     alt_statements = json.loads(f.read())
alt_statements = []
with open(ALT_STATEMENTS_PATH,'r') as f:
    alt_statements = f.read().split('\n')

with open(EXP_PATH,'r') as f:
    experience_fields = json.loads(f.read())

doc_section_items = [DocSectionItem(**_d) for _d in experience_fields]
doc_section = DocSection('Work Experience', doc_section_items)

_log(f'- loaded {len(alt_statements) } personal statements.')
_log(f'- loaded {len(experience_fields)} professional experience')


doc_section_copy = doc_section.copy()

# authoring_model_params = {
#     'model_provider' : 'google',
#     'model_str' : 'models/gemini-2.5-flash-preview-05-20'
# }

# authoring_model_params = {
#     'model_provider' : 'google',
#     'model_str' : 'models/gemini-2.5-pro'
# }

analysis_model_params = {
    'model_provider' : 'ollama',
    'model_str' : 'llama3.1:latest'
}

cover_letter_model_params = {
    'model_provider' : 'google',
    # 'model_str' : 'gemini-2.5-pro'
    'model_str' : 'gemini-3.1-pro-preview'
}
analysis_model_params = cover_letter_model_params
authoring_model_params = cover_letter_model_params


# cover_letter_model_params = {
#     'model_provider' : 'google',
#     'model_str' : 'gemini-2.5-flash-preview-05-20'
# }



import asyncio

async def main():
    llm_statement_editor = ModelFactory(**authoring_model_params).get_llm_model()
    llm_analysis_model = ModelFactory(**analysis_model_params).get_llm_model()
    llm_cover_letter_editor = ModelFactory(**cover_letter_model_params).get_llm_model()

    jpa = JobPostAnalysis(job_posting_path, llm_model = llm_analysis_model)

    await jpa.analyze()

    fcv = FullCVDocument(alt_statements[-1], doc_section_copy)

    cvca = CVCrossAnalyzer(
        jpa, 
        fcv, 
        llm_model = llm_analysis_model,  
        llm_editor_model = llm_statement_editor
    )

    ## 1. Analyze and re-write the personal statement.
    await cvca.analyze_rewrite_personal_statement(alt_statements)

    doc_section_copy = doc_section.copy()
    fcv = FullCVDocument(cvca.data['edited_statement'], doc_section_copy)
    cvca = CVCrossAnalyzer(
        jpa,
        fcv,
        llm_model = llm_analysis_model,  
        llm_editor_model = llm_statement_editor    
    )
    fcv_copy = fcv.copy()

    ## 2. Analyze the job experience section
    agg_metrics_prev = await cvca.analyze_job_experience_section()

    ## 2.1 Preview some metrics coming out of the analysis
    agg_metrics_prev = cvca.get_section_aggregate_metrics()
    _log_agg_metrics(agg_metrics_prev, 'prev')

    ## 3. Write a cover letter (use the best LLM available to get better authoring capabilities)
    clm = CoverLetterModel()
    cld = CoverLetterDrafter(cvca, llm_cover_letter_editor)

    letter_body = await cld.get_cover_letter_text()
    letter_body = letter_body.replace('&','\\&')

    date_str = datetime.now().strftime('%-d %B %Y')
    clm.set_data(date_str, company_name, letter_body, name , prof_signature)

    # 4. Store the cover letter PDF (for easier inspection as PDF)
    clm.to_pdf(os.path.join(TMP_FOLDER,'cover_letter_tmp.pdf'))

    # 4.1 Store the cover letter as tex file (can be used for latter manual edits)
    with open(os.path.join(TMP_FOLDER, 'cover_letter_tmp.tex'),'w') as f:
        f.write(clm.render_tex_template())
        

    cvca.cv_model.copy().render_pdf(os.path.join(TMP_FOLDER, "test_before_edits.pdf"))

    rewrite_output = cvca.rewrite_reviewed_experience_section(
        max_section_items_keep=MAX_SECTION_ITEMS_KEEP,
        min_relevance_score=MIN_RELEVANCE_SCORE_KEEP, 
        min_section_items_keep=MIN_SECTION_ITEMS_KEEP
    )

    agg_metrics_post = cvca.get_section_aggregate_metrics()
    _log_agg_metrics(agg_metrics_post, 'after edits')

    metrics_summary = agg_metrics_post[0]
    with open(os.path.join(TMP_FOLDER, 'metrics_summary.txt'),'w') as f:
        f.write(json.dumps(metrics_summary))
        
    # Render the CV with comments on scoring etc
    cvca.cv_model.render_pdf(os.path.join(TMP_FOLDER, 'test_after_edits.pdf'))

    # copy to remove the comments
    cvca.cv_model.copy().render_pdf(os.path.join(TMP_FOLDER, 'test_after_edits_nocomments.pdf'))

    # 5. Copy to the output folder for further editing and inspection
    global output_folder # Use the one calculated outside or pass it
    try:
        shutil.move(TMP_FOLDER, output_folder)
        os.mkdir(os.path.join(output_folder,'latex_folder'))
    except:
        print("file exists")

    with open('job_post.txt','w') as f:
        f.write(jpa.post_txt)

    shutil.copy('job_post.txt', os.path.join(output_folder, 'job_post.txt'))

    latex_root = os.path.join(output_folder, 'latex_folder')
    fdat_with_comments = cvca.cv_model.make_latex()
    with open(os.path.join(latex_root, 'cv_edited_with_comments.tex'),'w') as f:
        f.write(fdat_with_comments)
        
    fdat_no_comments = cvca.cv_model.copy().make_latex()
    with open(os.path.join(latex_root,'cv_edited_no_comments.tex'),'w') as f:
        f.write(fdat_no_comments)
        
    shutil.copy('assets/images/my_pic.jpeg',latex_root)
    shutil.copy('assets/resume.cls',latex_root)

if __name__ == "__main__":
    asyncio.run(main())
