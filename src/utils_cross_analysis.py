
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama.llms import OllamaLLM

from tqdm import tqdm
import numpy as np
import pandas as pd
from .utils import _trim_encap_tag_load_json
import json

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

section_experience_analysis = {
        'prompt_txt' : 
            ''' You are a CV and job posting HR and hiring analyzer bot. 
            Your tasks are to analyze sections of a professional CV, and assess how relevant they are to 
            particular asked skills and experience from a job post analysis. 
            
            In what follows, there is a piece of text that contains information about a particular job post, 
            and a passage from a CV, about some professional experience of a job candidate. 

            Your task is:
            1. to judge by assigning a number from 0 to 10, how relevant the CV passage is, to the job posting.
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



class CVCrossAnalyzer:
    def __init__(self, job_post_analyzer, full_cv_document, ollama_llm_str = 'llama3.1', max_section_parse_retries = 3):
        self.cv_model = full_cv_document
        self.job_post_analyzer = job_post_analyzer
        # self.cv_cross_analyzer_prompts = cv_cross_analyzer_prompts
        self.model = OllamaLLM(model = ollama_llm_str)
        self.max_section_parse_retries = max_section_parse_retries
        ## Customized chains:
        experience_analysis_chain = ChatPromptTemplate.from_template(section_experience_analysis['prompt_txt']) | self.model
        personal_statement_analysis_chain = ChatPromptTemplate.from_template(personal_statement_analysis['prompt_txt']) | self.model
        self.chains = {
            'personal_statement_analysis' : {
                'chain' : personal_statement_analysis_chain, 
                'provides' : personal_statement_analysis['prompt_provides']
            },
            'experience_section_analysis' : {
                'chain' :experience_analysis_chain, 
                'provides' : section_experience_analysis['prompt_provides']
            }
        }
        ## Somewhere to put the data:
        self.data = {}
        
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
                section_parse_retries = 0 
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
            
            temp_list = sorted(k.section_item_list, key = lambda x : -_get_exp_rel_score(bsa[k][x]))
            for section_item in temp_list:
                try:
                    relevance_score = bsa[k][section_item]['experience_relevance_score']
                except:
                    print("Failed to get 'experience_relevance_score'. Offending part:")
                    print(bsa[k][section_item])
                if len(new_section_item_list) < min_section_items_keep:
                    new_section_item_list.append(section_item)
                    continue
                if len(new_section_item_list) > max_section_items_keep:
                    break
                if min_relevance_score <= relevance_score:
                    new_section_item_list.append(section_item)
            k.section_item_list = new_section_item_list