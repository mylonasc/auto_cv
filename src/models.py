""" 
A set of simplified interfaces to different LLM providers for use with the implemented code.

This code also implements tools to query available models etc where applicable
"""

from typing import Optional
import os

MODEL_PROVIDERS = [
    'ollama',
    'google'
]

DEFAULT_MODEL_PROVIDER = 'ollama' # local model

MODEL_DEFAULTS = {
    'ollama' : 'llama3', 
    'google' : 'models/gemini-2.5-flash-preview-05-20'
}

MODELS_DEFAULT_CONFIG = {
    'ollama' : {'num_predict' : 8000, 'temperature' : 0.9},
    'google' : {'num_predict' : 8000, 'temperature' : 0.9}
}

def _log_msg(msg):
    print(msg)

class OllamaModelWrapper:
    def __init__(self, model_string, config = None):
        print(model_string)
        self._model_string, self._config = model_string, config
        if self._model_string is None:
            raise Exception("You have not provided a model to initialize! This is not supported - aborting.")
        
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        
        _avail_models = self.list(host=self.ollama_host)
        if self._model_string not in _avail_models:
            # Try to see if there's a tag mismatch (e.g. llama3 vs llama3:latest)
            if ":" not in self._model_string and f"{self._model_string}:latest" in _avail_models:
                self._model_string = f"{self._model_string}:latest"
            else:
                raise Exception(f"The model you requested ({self._model_string}) is not locally available on {self.ollama_host}. List of available models: \n {_avail_models} \n\n \n Please see ollama documentation (https://github.com/ollama/ollama/blob/main/README.md#quickstart) on how to download it.")
        
    def get_llm_model(self):
        from langchain_ollama import ChatOllama
        params = (self._config or {}).copy()
        params['model'] = self._model_string
        params['base_url'] = self.ollama_host
        return ChatOllama(**params)
    
    @classmethod
    def list(cls, str_output = True, host = None):
        """Returns the models that are locally available
        
        Args:
          str_output : (str) whether the output is going to be a string.
            if "False" it returns the "Model" objects.         
          host : (str) Optional host URL for Ollama server.
        """
        import ollama
        client = ollama.Client(host=host or os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
        return [m.model for m in client.list().models]
        
def _gemini_api_key_setup(set_environ = False):
    """ This function attempts to sort-out where to find the 
    gemini api key. If it's not in the env. variables, it searches for a 
    path in the config that points to a text file that stores the key.
    """
    from pathlib import Path
    import yaml
    _here = Path(__file__).resolve().parent.parent
    
    if 'GEMINI_API_KEY' not in os.environ:
        with open(os.path.join(_here, 'config/google_config.yaml'),'r') as f:
            res = yaml.safe_load(f)
        print(res)
        with open(res['gemini_api_key_path'] ,'r') as f:
            gemini_api_key = f.read().rstrip(' ').rstrip('\n')
        if set_environ:
            os.environ['GEMINI_API_KEY'] = gemini_api_key
    else:
        gemini_api_key = os.environ['GEMINI_API_KEY']
    return gemini_api_key

class GoogleModelWrapper:
    def __init__(self, model_string, config = None):
        """ Model provider wrapper for google
        Check instructions and documentation in:
        * https://github.com/langchain-ai/langchain-google/tree/main/libs/genai
        * https://googleapis.github.io/python-genai
        
        Args:
            model_string : (str) a string determining the LLM to be used. 
                note that some of the available models are not simple LLMs 
                and may not be appropriate for use with this library.
                
            config : (None) a config hashmap containing options to be passed
                to the llm constuctor. If the API key is not determined system-wide
                using the GEMINI_API_KEY, it stores the API_KEY property containing 
                the key.                
        """
        self._api_key = None
        self._api_version = 'v1alpha'
        
        if 'GEMINI_API_KEY' in os.environ:
            self._api_key = os.environ['GEMINI_API_KEY']
        else:
            self._api_key = _gemini_api_key_setup(set_environ = False)
            
        if config is not None:
            if 'API_KEY' in config:
                self._api_key = config['API_KEY']
            if 'api_version' in config:
                self._api_version = config['api_version']
                
        if self._api_key is None:
            raise Exception('you need to provide the API key for the Google GenAI Dev API to use this functionality! \
                Add the field in "config[\'API_KEY\']" or in the environment variable "GEMINI_API_KEY" and re-try. ')
        self._model_string = model_string
        self._config = config
                
    def check_model_avail(self):
        """checks if the model string is valid (i.e., from the available models) and trows an exception if not.
        """
        avail_models = self.list_models()
        if self._model_string not in avail_models:
            raise Exception(f"requested model {self._model_string} is not within the available models in google API. List of models: \n{'\n-'.join(avail_models)}.")        
    
    def get_llm_model(self, check_avail = False):
        
        if check_avail:
            self.check_model_avail()
        
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        if self._config is not None:
            config = self._config.copy()
            _config_props_remove = ['API_KEY', 'api_version']
            for _prop_rm in _config_props_remove:
                if _prop_rm in config:
                    del config[_prop_rm]
            return ChatGoogleGenerativeAI(model = self._model_string, api_key = self._api_key, **config)
        else:
            return ChatGoogleGenerativeAI(model = self._model_string, api_key = self._api_key)
        
    def list_models(self, return_string = True):
        from google import genai
        from google.genai import types
        client = genai.Client(
            api_key=self._api_key,
            http_options=types.HttpOptions(api_version=self._api_version)
        )
        if return_string:
            return [m.name for m in client.models.list()]
        return client.models.list()


class ModelFactory:
    """ A factory for LLM model creation (independent of whether it is local from ollama or from google).
    
    available model providers can be shown with:
    `ModelFactory.MODEL_PROVIDERS`
    
    The corresponding default models can be show with:
    `ModelFactory.MODEL_DEFAULTS`
    
    
    Example:
    ```
        model_factory = ModelFactory(model_provider = 'ollama', model_str = 'llama3.1:latest')
        model_wrapper = model_factory.get_model_wrapper() # this is the inner model wrapper. 
            typically you don't have to use that (just the top-level factory).
    ```
    """
    MODEL_PROVIDERS = MODEL_PROVIDERS
    MODEL_DEFAULTS = MODEL_DEFAULTS
    
    def __init__(self, model_provider : Optional[str] = None, model_str : Optional[str] = None, config : Optional[dict] = None):        
        self._model_provider = model_provider
        self._model_str = model_str
        self._config = config
        
        if model_provider is None:
            self._model_provider = DEFAULT_MODEL_PROVIDER
            _log_msg(f"selecting default model provider {self._model_provider}")
            
        if model_str is None:
            self._model_str = MODEL_DEFAULTS[self._model_provider]
            _log_msg(f"selecting default model for {self._model_provider}: '{self._model_str}'")
            
    def get_model_wrapper(self):
        def _make_ollama():
            model_wrapper = OllamaModelWrapper(self._model_str, self._config)
            return model_wrapper
        
        def _make_google():
            model_wrapper = GoogleModelWrapper(self._model_str, self._config)
            return model_wrapper
        
        _make_model_options = {
            'ollama' : _make_ollama,
            'google' : _make_google
        }
        
        return _make_model_options[self._model_provider]()
            
    def get_llm_model(self):
        self.model_wrapper = self.get_model_wrapper()
        return self.model_wrapper.get_llm_model()
