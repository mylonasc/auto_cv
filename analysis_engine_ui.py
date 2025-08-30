from src.utils import JobPostAnalysis, FullCVDocument
from src.utils_cross_analysis import CVCrossAnalyzer

def get_base_cv():
    from src.utils import DocSectionItem, DocSection, FullCVDocument
    statement = 'I am a data science and scientific computing expert, with a ' +\
        'strong mathematical and high performance computing background, and more ' + \
        'than 7 years of machine learning / deep learning experience. I hold a ' + \
        'Ph.D. on Machine Learning for Structural Health Monitoring, with original' + \
        'contributions on the use of deep learning and generative ML in ' + \
        'predictive maintenance. My overall organizational impact, during ' + \
        'both my academic tenure and within Deloitte, is in fostering maintainable' + \
        'and modular software engineering practices, solid DevOps practices, and an ' + \
        'inclusive culture of collaboration, and continuous learning.'

    d1 = {'text_items':[
            'Implemented a machine learning-enhanced methodology for improving the effectiveness of compliance monitoring.',
            'Contributed to successful business development activities on AI in energy trading, as a subject matter expert on AI and trading.'
        ],
        'company' : 'Deloitte',
        'duration' : 'Sept 2024 -- current',
        'position' : 'Assistant Manager'
    }

    d2 = {
        'company' : 'Deloitte',
        'duration' : 'Feb 2022 -- Sept 2024',
        'position' : 'Senior Consultant',
        'text_items' : [
            'Designed and created GenAI prototypes with retrieval augmented generation.',
            'Developed machine learning techniques for money laundering risk estimation.',
            'Created, and served as the product owner of a python package to interface with parts of legacy credit risk analytics code of a large Swiss bank (Python, Excel, R).',
            'Implemented and benchmarked a deep learning-based in-house diarization (speech processing) system for the compliance department of a large swiss bank.',
            #'Created a customized dataset and fine--tuned speech foundation models (Whisper) for speech processing tasks.',
            'Gained hands-on experience in financial risk management (low-default portfolios default risk estimation, portfolio theory, liquidity and leverage regulatory reporting).',
            'Facilitated communication with client stakeholders of varied seniority in a critical and dynamically evolving project, as part of the financial risk reporting team during the merger of two global systemically important banks. Introduced software project management practices for automation code, which improved accountability, ownership, code maintainability. This resulted in early delivery and persistent increases in efficiency for regulatory reporting.',
            'Completed online course on Financial Engineering and Risk management (Coursera certificate \href{https://coursera.org/share/173183767cfc52f36f66226afec78ee3}{[link]})'
        ]
    }


    d3 = {
        'company': 'ETH Zurich',
        'duration' : 'Sept 2016--Nov 2021',
        'position' : 'Ph.D. Candidate/Research Assistant',
        'text_items' : [
            'Researched scalable probabilistic machine learning for structural condition monitoring of wind turbines and wind farms (Python, TensorFlow).',
            'Implemented a message-passing GNN library (\\url{https://github.com/mylonasc/tf-gnns/}).',
            'Engaged in industrial collaborations (raw data curation, deep learning for remaining useful life prediction, wind farm data processing).',
            'Performed large-scale Monte-Carlo simulations (Bash, cluster computing)',
            'Awarded Ph.D. with no corrections on first submission, and nominated unanimously from examination panel for the ETH Medal.'
        ]
    }

    d4 = {
        'company': 'ETH Zurich',
        'duration' : 'Dec 2015--Sept 2016',
        'position' : 'Research Assistant',
        'text_items' : [
            'Contributed to the popular computational statistics software UQLab by implementing uncertainty quantification and sensitivity analysis algorithms',
            #'Implemented advanced statistical learning algorithms (high-dimensional regression with tensor decompositions), including original automated model selection pipelines (Matlab).',
            'Developed a web-based user interface for sensitivity and regression analysis (PHP, JavaScript, Matlab).'
        ]
    }

    d5 = {
        'company' : 'Credit Suisse',
        'duration' : 'Jul 2014--Dec 2014',
        'position' : 'Full-Stack Trading Tool Developer (internship)',
        'text_items' : [
            'Implemented and validated a high level interface for an option pricer (C++, R), achieving more than 10-fold improvement by replacing pre-existing interface.',
            'Implemented a RESTful time series server and a scriptable front-end visualization trading signal identification tool (Python, JavaScript, MySQL).'
        ]
    }
    experience_fields = [d1,d2,d3,d4,d5]
    doc_section_items = [DocSectionItem(**_d) for _d in [d1,d2,d3,d4,d5]]
    #####
    doc_section = DocSection('Work Experience', doc_section_items)
    fcv = FullCVDocument(statement, doc_section)
    return fcv


def proc_text_dummy(text):

    fcv = get_base_cv()
    fcv.render_pdf('dummy.pdf')
    return 'dummy.pdf'

def process_text(text):
    with open('posting.txt','w') as f:
        f.write(text)

    print("analyzing posting...")
    jpa = JobPostAnalysis('posting.txt')
    jpa.analyze()
    fcv = get_base_cv()
    fcv_copy = fcv.copy()
    doc_section_copy = fcv.experience_section.copy()
    fcv = FullCVDocument(fcv.statement, doc_section_copy)
    cvca = CVCrossAnalyzer(jpa, fcv)
    cvca.analyze_job_experience_section()
    metrics_pre = cvca.get_section_aggregate_metrics()
    agg_metrics_prev = cvca.rewrite_reviewed_experience_section(max_section_items_keep=5,min_relevance_score=4)
    cvca.analyze_job_experience_section()
    metrics_post = cvca.get_section_aggregate_metrics()
    cvca.cv_model.copy().render_pdf("result.pdf")
    return 'result.pdf'#, [metrics_pre, metrics_post]
