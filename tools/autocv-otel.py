""" AutoCV helps creating a first customized CV and Cover letter draft
for job applications
""" 
from src.models import ModelFactory
from src.utils import JobPostAnalysis, FullCVDocument, CoverLetterModel, DocSectionItem, DocSection
from src.utils_cross_analysis import CVCrossAnalyzer, CoverLetterDrafter
from src.utils_cross_analysis import CoverLetterDrafter
from langchain_core.prompts import ChatPromptTemplate
from datetime import datetime
import json
import tempfile 
import os
import shutil

from opentelemetry.instrumentation.langchain import LangchainInstrumentor
from opentelemetry.instrumentation.ollama import OllamaInstrumentor


import os
import logging
from opentelemetry import trace, metrics, _logs
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter

os.environ['OTEL_SERVICE_NAME'] = "auto-cv-test-langsmith"
os.environ['LANGSMITH_OTEL_ENABLED'] = 'TRUE'


LangchainInstrumentor().instrument()
OllamaInstrumentor().instrument()

def _log_agg_metrics(agg_metrics, txt_suff = None):
    """ log agg metrics.

    Args:
        agg_metrics: TODO: describe.
        txt_suff: TODO: describe.

    Returns:
        TODO: describe return value.
    """
    if txt_suff is None:
        txt_suff = ' ? '
    _log(f' - ({txt_suff}) Weighted Mean Section Relevance: ' , agg_metrics[0]['weighted_mean_section_relevance'])
    _log(f' - ({txt_suff}) Mean Section Relevance: ' , agg_metrics[0]['mean_section_relevance'])
    _log(f' - ({txt_suff}) Conciseness Relevance Metric: ' , agg_metrics[0]['conciseness_relevance_metric'])
    _log(f' - ({txt_suff}) Section Scores:\n', agg_metrics[1])

def _log(*s):
    """ log.

    Returns:
        TODO: describe return value.
    """
    print(*s)

#job_posting_path = 'job_postings_text/AltusSearch_MLStrategist_Commodities_26062025.txt'
#job_posting_path = 'job_postings_text/Capgemini_SeniorDataScientist_June3_2025-v2.txt'
#job_posting_path = 'job_postings_text/KAIKO_SeniorMLEngineer_27062025.txt'
# job_posting_path = 'job_postings_text/ON_SeniorMLScientist_02072025.txt' 
def initialize_opentelemetry_sdk(service_name: str, otlp_endpoint: str = "http://localhost:4317"):
    """
    Initializes the OpenTelemetry SDK with OTLP gRPC exporters.
    """
    resource = Resource.create({
        "service.name": service_name,
        "service.instance.id": os.getenv("HOSTNAME", "unknown"),
        "deployment.environment": os.getenv("ENVIRONMENT", "development")
    })

    # Configure Traces
    trace_provider = TracerProvider(resource=resource)
    trace_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
    span_processor = BatchSpanProcessor(trace_exporter)
    trace_provider.add_span_processor(span_processor)
    trace.set_tracer_provider(trace_provider)

    # Configure Metrics
    metric_reader = PeriodicExportingMetricReader(OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True))
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    # Return providers if you need to manually flush them later
    return trace_provider, meter_provider

def shutdown_opentelemetry_sdk(trace_provider, meter_provider):
    """
    Shuts down and flushes OpenTelemetry providers.
    """
    if trace_provider:
        trace_provider.force_flush()
        trace_provider.shutdown()
    if meter_provider:
        meter_provider.force_flush()
        meter_provider.shutdown()

def run_autocv_pipeline_full(
        job_posting_path, 
        output_folder, 
        company_name, 
        name, 
        prof_signature, 
        MAX_SECTION_ITEMS_KEEP, 
        MIN_RELEVANCE_SCORE_KEEP,
        alt_statements, 
        experience_fields, 
        doc_section, 
        authoring_model_params, 
        analysis_model_params, 
        cover_letter_model_params
    ):

    """Run autocv pipeline full.

    Args:
        job_posting_path: TODO: describe.
        output_folder: TODO: describe.
        company_name: TODO: describe.
        name: TODO: describe.
        prof_signature: TODO: describe.
        MAX_SECTION_ITEMS_KEEP: TODO: describe.
        MIN_RELEVANCE_SCORE_KEEP: TODO: describe.
        alt_statements: TODO: describe.
        experience_fields: TODO: describe.
        doc_section: TODO: describe.
        authoring_model_params: TODO: describe.
        analysis_model_params: TODO: describe.
        cover_letter_model_params: TODO: describe.

    Returns:
        TODO: describe return value.
    """
    llm_statement_editor = ModelFactory(**authoring_model_params).get_llm_model()
    llm_analysis_model = ModelFactory(**analysis_model_params).get_llm_model()
    llm_cover_letter_editor = ModelFactory(**cover_letter_model_params).get_llm_model()

    jpa = JobPostAnalysis(job_posting_path, llm_model = llm_analysis_model)
    jpa.analyze()
    
    doc_section_copy = doc_section.copy()

    fcv = FullCVDocument(alt_statements[-1], doc_section_copy)

    cvca = CVCrossAnalyzer(
        jpa, 
        fcv, 
        llm_model = llm_analysis_model,  
        llm_editor_model = llm_statement_editor
    )

    ## 1. Analyze and re-write the personal statement.
    cvca.analyze_rewrite_personal_statement(alt_statements)

    doc_section_copy = doc_section.copy()
    fcv = FullCVDocument(cvca.data['edited_statement'], doc_section_copy)
    cvca = CVCrossAnalyzer(jpa, fcv)
    fcv_copy = fcv.copy()

    ## 2. Analyze the job experience section
    agg_metrics_prev = cvca.analyze_job_experience_section()

    ## 2.1 Preview some metrics coming out of the analysis
    agg_metrics_prev = cvca.get_section_aggregate_metrics()
    _log_agg_metrics(agg_metrics_prev, 'prev')

    ## 3. Write a cover letter (use the best LLM available to get better authoring capabilities)
    clm = CoverLetterModel()
    cld = CoverLetterDrafter(cvca, llm_cover_letter_editor)

    letter_body = cld.get_cover_letter_text()
    letter_body = letter_body.replace('&','\\&')

    date_str = datetime.now().strftime('%-d %B %Y')
    clm.set_data(date_str, company_name, letter_body, name , prof_signature)

    # 4. Store the cover letter PDF (for easier inspection as PDF)
    clm.to_pdf(os.path.join(TMP_FOLDER,'cover_letter_tmp.pdf'))

    # 4.1 Store the cover letter as tex file (can be used for latter manual edits)
    with open(os.path.join(TMP_FOLDER, 'cover_letter_tmp.tex'),'w') as f:
        f.write(clm.render_tex_template())
        

    cvca.cv_model.copy().render_pdf(os.path.join(TMP_FOLDER, "test_before_edits.pdf"))

    rewrite_output = cvca.rewrite_reviewed_experience_section(max_section_items_keep=MAX_SECTION_ITEMS_KEEP,min_relevance_score=MIN_RELEVANCE_SCORE_KEEP)

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

if __name__ == '__main__':
    
    
    # job_posting_path = 'job_postings_text/Signal_QuantitativeResearcher_04072025.txt'
    job_posting_path = 'job_postings_text/OneApps_SeniorDataScientist_24072025.txt'
    output_folder = 'autocv_output_' + job_posting_path.split('/')[-1][:-4]
    company_name = 'OneApps'
    name = 'Charilaos Mylonas'
    prof_signature = "\\\\" + 'Data Scientist \\& Software Engineer \\\\ Zurich'
    MAX_SECTION_ITEMS_KEEP = 4
    MIN_RELEVANCE_SCORE_KEEP = 3
    
    TMP_FOLDER = tempfile.mkdtemp()
    _ = input('temp folder is (press any key to continue)' + TMP_FOLDER)
    
    ALT_STATEMENTS_PATH = 'assets/alt_statements.json'
    with open(ALT_STATEMENTS_PATH,'r') as f:
        alt_statements = json.loads(f.read())
        
    EXP_PATH = 'assets/experience_fields.json'
    with open(EXP_PATH,'r') as f:        
        experience_fields = json.loads(f.read())
    
    
    doc_section_items = [DocSectionItem(**_d) for _d in experience_fields]
    doc_section = DocSection('Work Experience', doc_section_items)

    _log(f'- loaded {len(alt_statements) } personal statements.')
    _log(f'- loaded {len(experience_fields)} professional experience')

    
    # authoring_model_params = {
    #     'model_provider' : 'google',
    #     'model_str' : 'models/gemini-2.5-pro' # 'models/gemini-2.5-flash-preview-05-20'
    # }
    authoring_model_params = {
        'model_provider' : 'google',
        'model_str' : 'models/gemini-2.5-flash-preview-05-20'
    }

    analysis_model_params = {
        'model_provider' : 'ollama',
        'model_str' : 'llama3.1:latest'
    }

    cover_letter_model_params = {
        'model_provider' : 'google',
        'model_str' : 'models/gemini-2.5-flash-preview-05-20'
    }

    # --- Core OpenTelemetry Setup ---
    # Use environment variables for flexibility
    SERVICE_NAME = os.getenv("OTEL_SERVICE_NAME", "autocv")
    OTEL_COLLECTOR_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://trillian:4317")

    trace_provider, meter_provider = initialize_opentelemetry_sdk(SERVICE_NAME, OTEL_COLLECTOR_ENDPOINT)

    res = run_autocv_pipeline_full(
        job_posting_path, 
        output_folder, 
        company_name, 
        name, 
        prof_signature, 
        MAX_SECTION_ITEMS_KEEP, 
        MIN_RELEVANCE_SCORE_KEEP,
        alt_statements, 
        experience_fields, 
        doc_section,
        authoring_model_params,
        analysis_model_params,
        cover_letter_model_params
    )
    shutdown_opentelemetry_sdk(trace_provider, meter_provider)