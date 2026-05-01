
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM

from tqdm import tqdm
import numpy as np
import os
import pandas as pd
from .utils import _trim_encap_tag_load_json, JobPostAnalysis, FullCVDocument
import json
from bs4 import BeautifulSoup # pip install beautifulsoup4

personal_statement_analysis = {
    'prompt_txt' : 
        ''' You are a CV and job posting HR and hiring analyzer bot.
        Your task is to analyze the personal statement of a potential candidate for a job posting, and
        judge whether they are relevant for that job posting, and explain your rating based on concrete 
        information that is included in the personal statement and the job posting. 
        
        In what follows, there is a piece of text that contains information about a particular job post, 
        and the personal statement taken from the CV of a candidate. 
        
        You should return a score from 0 to 10 about how relevant the personal statement of that candidate is, 
        together with a short explanation about your scoring. 
        
        IMPORTANT:
        Please note that the text will be fed-into latex! Make sure that you properly escape (or avoid) latex special characters, while not breaking python parsing!

        Job posting information:
        ------------------------
        {job_posting_data}
        
        Candidate personal statement:
        -----------------------------
        {personal_statement}
        
        Return your answer in JSON format, enclosed in an <output> tag. 
        
        Example output:
        ---------------
        <output>
            {{
                "statement_relevance_score" : 9,
                "explanation" : "The posting requests several skills and experience that the candidate states they have. Namely, the candidate has a M.Sc. and a Ph.D. from an elite university on a technical subject, and is an expert in computing and software engineering."
            }}
        </output>
        ''',
        'prompt_provides' : 'personal_statement_analysis'
}

personal_statement_list_analysis = {
    'prompt_txt' : '''
    """
    In the following, you are provided with the text of a job description/linkedin job post, and some alternative personal statements describing concisely the experience of a candidate.
    I would like to have a candidate personal statement calibrated to the job description, that uses ONLY statements from the example personal statements.

    I want you to (1) first collect a list of statements, (2) score them (0 to 10) in relevance and candidate strength according to the job posting. In the scoring give a higher score to unique and differentiating aspects - not on fairly standard skills.
    Finally (3) I want you to create a concise statement that takes the strongest points of the statements regarding this job posing.
    
    I want you to avoid repetition. Please do not make up statements but stick to the statements provided. If needed, you may slightly rephrase only for conciseness and 
    avoidance of repetition where applicable. I want the final re-written statement to be written in a similar style as the provided ones (e.g., as they were written by the candidate).
    
    You should wrap the analyzed output in appropriate tags. Namely, the analysis/scoring should be wrapped in an <analysis> ... </analysis> tag, and the final edited statement in an <edited_statement> ... </edited_statement> tag for easier parsing.

    Job posting:
    ----------------
    {job_posting_raw}

    Alternative Personal statements:
    --------------------------------
    {personal_statements}    
    ''',
    'prompt_provides' : 
        ['analysis','edited_statement']
}

section_experience_analysis = {
        'prompt_txt' : 
            ''' You are a CV and job posting HR and hiring analyzer bot. 
            Your tasks are to analyze sections of a professional CV, and assess how relevant they are to 
            particular asked skills and experience from a job post analysis. 
            
            In what follows, there is a piece of text that contains information about a particular job post, 
            and a passage from a CV, about some professional experience of a job candidate. 
            
            Your task is:
            1. to judge by assigning a number from 0 to 10, how relevant the CV passage is, to the job posting. You may assign at least 5 if the section has strong evidence of excellence or strong work ethic.
            2. to write a short explanation (less than 20 words) of why the score was assigned.
            3. to explain which parts of the job posting analysis are relevant to the CV passage.
            
            Job posting information:
            ------------------------
            {job_posting_data}    
            
            CV Experience information:
            ----------------------
            {cv_experience}
            
            You should return your response as in JSON format, wrapped around an <output> tag.
            Below, an example is provided for the assessment of relevance of the CV, for the statement:
            "I have designed and created Generative AI prototypes, using sound software engineering practices"
            If the output contains several dictionaries (e.g., because of multiple experience sections), return a list of dictionaries.
            
            Example output 1:
            ---------------
            <output>
            {{
                "experience_relevance_score" : 10,
                "explanation" : "The posting requests GenAI experience. The candidate states they have this experience in that passage",
                "posting_evidence" : "GenAI experience, Software Engineering"
            }}
            </output>
            
            Example output 2:
            -----------------
            <output>
            [
            {{
                "experience_relevance_score" : 10,
                "explanation" : "The posting requests GenAI experience. The candidate states they have this experience in that passage",
                "posting_evidence" : "GenAI experience, Software Engineering"
            }},
            {{
                "experience_relevance_score" : 5,
                "explanation" : "The posting requests advanced deep reinforcement learning experience. The candidate has generative models experience through this engagement which is relevant, but only moderately.",
                "posting_evidence" : "Software Engineering experience, Deep Generative Models experience",
            }}
            ]
            </output>
            RETURN ONLY THE REQUESTED STRUCTURED OUTPUT! No long explanations - be very concise!
            ''',
        'prompt_provides' : 'experience_section_analysis'
}

from .models import ModelFactory

def _load_defaults():
    from pathlib import Path
    import yaml
    _here = Path(__file__).resolve().parent.parent
    with open(os.path.join(_here, 'config/llm_defaults.yaml'),'r') as f:
        res = yaml.safe_load(f)
    return res

def _make_default_model():
    default_model_options = _load_defaults()
    print(default_model_options)
    return ModelFactory(**default_model_options['cv_cross_analysis_llm_default']).get_llm_model()


class CoverLetterDrafter:
    """ This function wraps different cover letter
    authoring functionality.
    
    Example:
    
        ```
        cover_letter_text = cld.get_cover_letter_text()
        ```
        
    """
    draft_prompt = """ I want you to draft a short cover letter for a job candidate. I will add a job description, a personal statement from the candidate, and
        the different professional experiences of that candidate. I want you to first carefully analyze the most important differentiating aspects of 
        that candidate as it pertains to that job. Based on these inputs, I want you to create a professional cover letter, stressing the candidate's eagerness for being considered in 
        this position, while shortly summarizing why this candidate  is appropriate for that position. Return the cover letter enclosed in tags <COVERLETTER>.

        The address to the hiring manager before and after the cover letter should be outside the <COVERLETTER> tag. 

        Example output: 
        Dear Hiring Manager, 

        <COVERLETTER>
        With this letter I would like to express my keen interest and apply for the [insert role] position at [insert company]. 
        ...
        I am looking forward to meeting you and further discussing my credentials and experience. 
        </COVERLETTER>

        Sincerely, ...

        Role Description:
        ----------
        {job_post_text}

        Personal Statement:
        ---------------
        {pers_statement}

        Professional Experience:
        -----------------------
        {exp_section}
        """
        
    def __init__(self, cvca : 'CVCrossAnalyzer', llm_editor_model = None):
        self.cvca = cvca
        
        self.llm_editor_model = llm_editor_model
        
        if self.llm_editor_model is None:
            self.llm_editor_model = self.cvca.llm_editor_model
        
        self._debug = {}
        
    def get_cover_letter_text(self):
        chain = ChatPromptTemplate.from_template(self.draft_prompt) | self.llm_editor_model
        
        _inputs = {
            "exp_section" : self.cvca.cv_model.experience_section.get_markdown(),
            'pers_statement' : self.cvca.cv_model.statement,
            'job_post_text' : self.cvca.job_post_analyzer.post_txt
        }
        
        res = chain.invoke(_inputs)
        self._debug['inputs'] = _inputs
        self._debug['raw_llm_output'] = res
        soup = BeautifulSoup(res,'html.parser')
        return soup.coverletter.text
    
    # def draft_cover_letter(self):
    #     main_text = self.get_cover_letter_text()
    #     clm = CoverLetterModel()
    
    # def author_cover_letter_from_analysis(self):
    #     chain = ChatPromptTemplate.from_template(self.draft_prompt) | self.llm_editor_model
    #     _inputs = {
    #         "exp_section" : cvca,
    #         'pers_statement' : ,
    #         'job_post_text' : 
    #     }
    #     outputs = chain.invoke(_inputs)
    #     return 


class CVCrossAnalyzer:
    """ This class contains utilities to cross-analyze the job posting and the cv.
    It returns a set of scores for each section of the CV (e.g., relevance) and the job posting.

    It also contains a utility (and chain) to analyze alternative personal introduction statements, 
    and align them with the job postings' requirements. 
    """
    def __init__(
                self, 
                job_post_analyzer : JobPostAnalysis,
                full_cv_document : FullCVDocument,
                llm_model = None, 
                llm_editor_model = None, # A more powerful model (e.g., Gemini or O3) to be used for "reasoning" and editing where needed (e.g., re-writing statements).
                max_section_parse_retries = 3
        ):
        self.cv_model = full_cv_document
        self.job_post_analyzer = job_post_analyzer
        if llm_model is None:
            self.model = _make_default_model()
        else:
            self.model = llm_model
            
        if llm_editor_model is None:
            llm_editor_model = self.model
            
        self.llm_editor_model = llm_editor_model
        
        self.max_section_parse_retries = max_section_parse_retries
        
        ## Customized chains:
        experience_analysis_chain =\
            ChatPromptTemplate.from_template(section_experience_analysis['prompt_txt']) | self.model
            
        personal_statement_analysis_chain =\
            ChatPromptTemplate.from_template(personal_statement_analysis['prompt_txt']) | self.model
            
        personal_statement_list_rewrite_chain = \
            ChatPromptTemplate.from_template(personal_statement_list_analysis['prompt_txt']) | self.llm_editor_model
            
        self.chains = {
            'personal_statement_analysis' : {
                'chain' : personal_statement_analysis_chain, 
                'provides' : personal_statement_analysis['prompt_provides']
            },
            'experience_section_analysis' : {
                'chain' :experience_analysis_chain, 
                'provides' : section_experience_analysis['prompt_provides']
            },
            'personal_statement_rewrite' : {
                'chain' : personal_statement_list_rewrite_chain,
                'provides' : personal_statement_list_analysis['prompt_provides']
            }
        }
        ## Somewhere to put the data:
        self.data = {}
        
    def analyze_rewrite_personal_statement(self, statements_list = None):
        post_txt = self.job_post_analyzer.post_txt
        if statements_list is None:
            statements_list = self.personal_statements
        if statements_list is None:
            raise Exception("You need to provide a list of personal statements for this task (either in the cross analyzer object or as a parameter in the call)")
        statements_str = ''.join(['Personal Statement %i'%i+'-'*10+s+'\n\n' for i, s in enumerate(statements_list)])
        _curr_chain = self.chains['personal_statement_rewrite']['chain']
        res = _curr_chain.invoke({'job_posting_raw' : post_txt ,'personal_statements' : statements_str})
        
        # parsing the outputs:
        soup = BeautifulSoup(res, "html.parser")
        analysis = soup.analysis
        # edited_statement = soup.edited_statement.string
        # The following should correspond to the "provides" part of the chain.
        self.data['edited_statement'] = soup.edited_statement.string
        self.data['statement_list_analysis'] = str(soup.analysis)
        
    def analyze_personal_statement(self):
        statement = self.cv_model.statement
        _job_post_data = str(self.job_post_analyzer.data)
        _res = self.chains['personal_statement_analysis']['chain'].invoke({'job_posting_data' : _job_post_data, 'personal_statement' : statement})
        jdata = _trim_encap_tag_load_json(_res)
        self.data[self.chains['personal_statement_analysis']['provides']] = jdata
        
    def analyze_job_experience_section(self):
        section = self.cv_model.experience_section
        _job_post_data = str(self.job_post_analyzer.data)
        by_section_item_analysis = {}
        by_section_analysis = {}
        analysis_item = self.chains['experience_section_analysis']
        for s in tqdm(section.doc_section_items):
            section_notes = ''
            section_items_list_dict = {}
            for i in s.section_item_list:
                for k in range(self.max_section_parse_retries):
                    try:
                        _res = analysis_item['chain'].invoke({'cv_experience' : i.text,'job_posting_data' : _job_post_data})
                        jdata = _trim_encap_tag_load_json(_res)
                        break
                    except:
                        print(f"Retrying to generate and parse section - retries: {k} out of {self.max_section_parse_retries}")
                section_notes += str(jdata) + '\n'
                section_items_list_dict[i] = jdata
                i.set_comment(str(jdata).replace(' & ',' and '))
            by_section_item_analysis[s] = section_items_list_dict
            print('analyzing full section...' , str(s))
            jdata_section = None
            for k in range(self.max_section_parse_retries):                
                try:
                    _res_section = analysis_item['chain'].invoke({'cv_experience' : s.get_markdown(), 'job_posting_data' : _job_post_data})
                    jdata_section = _trim_encap_tag_load_json(_res_section)
                    break
                except:
                    print(f"Retrying to generate and parse section - retries: {k} out of {self.max_section_parse_retries}")
                    print("jdata_section: ")
                    print(_res_section)
            if jdata_section is None:
                raise Exception("Did not manage to analyze section!")
            by_section_analysis[s] = jdata_section
            s.set_comment(str(jdata_section))
        _field = self.chains['experience_section_analysis']['provides']
        self.data[_field] = {'full_section_analysis' : by_section_analysis,'by_section_item_analysis' : by_section_item_analysis}
        return self.data[_field]
        
    def get_section_aggregate_metrics(self):
        def _count_words(s):
            return len(s.split(' '))

        section_scoring = []
        section_weights = []
        for section, s in self.data['experience_section_analysis']['full_section_analysis'].items():
            # print(sss.get_markdown())
            weight_num_words = _count_words(section.get_markdown())
            if isinstance(s, list):
                section_scores = [_s['experience_relevance_score'] for _s in s]
            if isinstance(s, dict):
                section_scores = [s['experience_relevance_score']]
            section_scoring.append(section_scores)
            section_weights.append(weight_num_words)
            
        section_scoring_numbers = [[(max(s) + np.mean(s))/2, sw] for s, sw in zip(section_scoring, section_weights)]
        all_dat = pd.DataFrame(section_scoring_numbers, columns = ['section_relevance','section_weight'])
        mean_section_relevance = np.mean(all_dat['section_relevance'])
        weighted_mean_section_relevance = np.sum(all_dat['section_relevance'] * all_dat['section_weight'] / np.sum(all_dat['section_weight']))
        conciseness_relevance_metric = weighted_mean_section_relevance - mean_section_relevance
        _res  = {
            'conciseness_relevance_metric' : conciseness_relevance_metric, 
            'mean_section_relevance' : mean_section_relevance,
            'weighted_mean_section_relevance' : weighted_mean_section_relevance
        }
        return _res, all_dat, section_scoring_numbers
    
    def rewrite_reviewed_experience_section(self,
        min_section_items_keep = 1,
        max_section_items_keep = 6,
        min_relevance_score = 3
    ):
        """ Edits the item list for all work experience sections, given the analysis data.
        
        Args:
            min_section_items_keep : how many section items to keep 
            max_section_items_keep : how many section items to keep 
            min_relevance_score : the threshold of relevance to keep or replace an experience
        """
        experience_section_analysis_data = self.data['experience_section_analysis']
        
        bsa = experience_section_analysis_data['by_section_item_analysis']
        fsa = experience_section_analysis_data['full_section_analysis']
        
        def _get_exp_rel_score(s):
            if isinstance(s, dict):
                ss = s['experience_relevance_score']
            if isinstance(s, list):
                ss = np.mean([_s['experience_relevance_score'] for _s in s])
            
            return ss
        
        for k, v in fsa.items():
            new_section_item_list = []
            # First sort by relevance:
            # relevance_scores = [ss for ss in k.section_item_list]
            temp_list = sorted(k.section_item_list, key = lambda x : -_get_exp_rel_score(bsa[k][x]))
            
            for section_item in temp_list:
                try:
                    _tmp = bsa[k][section_item]
                    relevance_score = _get_exp_rel_score(_tmp)
                    # if isinstance(_tmp, list):
                    #     relevance_score = _tmp[0]['experience_relevance_score']
                    # else:
                    #     relevance_score = _tmp['experience_relevance_score']
                    
                except:
                    print("Failed to get 'experience_relevance_score'. Offending part:")
                    print(bsa[k][section_item])
                    raise Exception("Couldn't pass relevance score! Aborting!")
                # the new section is added regardless of relevance, due to the minimum items per-section:
                
                # There is a max number of sections - if it is passed then no more sections are added.
                if len(new_section_item_list) >= max_section_items_keep:
                    break
                
                if len(new_section_item_list) < min_section_items_keep:
                    new_section_item_list.append(section_item)
                    print(f" --- --- --- -- -- Adding section because of the min_num_sections (min sections: {min_section_items_keep}, curr_nsections: {len(new_section_item_list)} constraint - section item: ", section_item.get_markdown())
                    continue
                
                # when the new number of sections are between min_section_items and max_sections, 
                # A section is added only if it is relevant. 
                if min_relevance_score <= relevance_score:
                    print(f" --- --- ->> -- -- Adding section because of the RELEVANCE ({min_relevance_score}, {relevance_score})score constraint - section item: ", section_item.get_markdown())
                    
                    new_section_item_list.append(section_item)
            k.section_item_list = new_section_item_list
        