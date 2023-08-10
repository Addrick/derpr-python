# A more condensed version of the code can be achieved by creating a base class that the three individual
# classes inherit from. The base class can include the common methods and attributes,
# reducing the code repetition. This also makes it easier to apply changes across all classes.

import api_keys
import openai
import google.generativeai as palm
import inspect
import sys



def get_available_models():
    model_list = []
    for _, model in inspect.getmembers(sys.modules[__name__]):
        if inspect.isclass(model) and model != BaseModel:
            model_list.append(model.__name__)
    return model_list

def get_model(model_name):
    module = sys.modules['models']
    classes = inspect.getmembers(module, inspect.isclass)
    for _, model_class in classes:
        if _ == model_name:
            return model_class()
    return False

class BaseModel:
    def __init__(self, model_name, temperature=0.8, max_tokens=100, top_p=1.0):
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.json_request = None
        self.json_response = None

    def get_raw_json_request(self):
        return self.json_request

    def get_max_tokens(self):
        return self.max_tokens

    def set_response_token_limit(self, new_response_token_limit):
        if isinstance(new_response_token_limit, int):
            self.max_tokens = new_response_token_limit
            return True
        else:
            print("Error: Input is not an integer.")
            return False

class Gpt3Turbo(BaseModel):
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.8, max_tokens=200, top_p=1.0):
        super().__init__(model_name, temperature, max_tokens, top_p)
        self.api_key = api_keys.openai
        self.frequency_penalty = 0
        self.presence_penalty = 0

    def generate_response(self, prompt, message, context):
        openai.api_key = self.api_key
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": context},
            {"role": "user", "content": message.content}
        ]
        return self._create_completion(messages)

    def _create_completion(self, messages):
        completion = openai.ChatCompletion.create(
            messages=messages,
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            frequency_penalty=self.frequency_penalty,
            presence_penalty=self.presence_penalty
        )
        self.json_request = {
            "model": self.model_name,
            "messages": messages,
            "options": {
                "use_cache": False,
                "best_of": 1,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "frequency_penalty": self.frequency_penalty,
                "presence_penalty": self.presence_penalty
            },
            "object": "chat.completion",
            "id": self.model_name,
        }
        self.json_response = completion
        return completion.choices[0].message.content

class Gpt4(Gpt3Turbo):
    def __init__(self, model_name="gpt-4", temperature=0.8, max_tokens=200, top_p=1.0):
        super().__init__(model_name, temperature, max_tokens, top_p)

class PalmBison(BaseModel):
    def __init__(self, model_name='models/chat-bison-001', temperature=0.8, max_tokens=200, top_p=1.0):
        super().__init__(model_name, temperature, max_tokens, top_p)
        self.api_key = api_keys.google

    def generate_response(self, prompt, message, context=[], examples=[]):
        palm.configure(api_key=self.api_key)
        context.append("NEXT REQUEST")
        completion = self._create_completion(context)
        return completion

    def _create_completion(self, context):
        defaults = {
            'model': self.model_name,
            'temperature': self.temperature,
            'candidate_count': 1,
            'top_k': 40,
            'top_p': 0.95,
        }
        completion = palm.chat(
            **defaults,
            context=context,
            messages=context
        )
        if completion.last is None:
            print('good job, no response')
            print('filter info:')
            print(completion.filters)
            print(completion.last)
        self.json_response = completion
        return completion.last[0]

# TODO: redo this and generate a list on startup, then just reference the list
def create_available_models_list():
    model_list = []
    module = sys.modules[__name__]
    classes = inspect.getmembers(module, inspect.isclass)
    for _, model_class in classes:
        if issubclass(model_class, BaseModel):
            model_instance = model_class()
            if hasattr(model_instance, "model_name"):
                model_list.append(model_instance.model_name)
    return model_list
