import json
from global_config import *

class Persona:
    def __init__(self, name, model, prompt, context_limit=10, token_limit=100):
        self.name = name
        self.prompt = prompt
        self.context_length = context_limit
        self.response_token_limit = token_limit
        self.model = model  # must be model object
        self.last_json = 'none yet'

    def get_context_length(self):
        return self.context_length

    def set_context_length(self, context_length):
        self.context_length = context_length

    def get_response_token_limit(self):
        return self.response_token_limit

    def set_response_token_limit(self, response_token_limit):
        if isinstance(response_token_limit, int):
            self.context_length = response_token_limit
            return True
        else:
            print("Error: Input is not an integer.")
            return False

    def set_last_json(self, last_json):
        self.last_json = last_json

    def get_last_json(self):
        return self.last_json

    def set_prompt(self, prompt):
        self.prompt = prompt

    def update_prompt(self, message):
        self.prompt += message

    def get_prompt(self):
        return self.prompt

    def set_model(self, model):
        # model = models.get_model(model_name)
        if not model:
            return False
        else:
            self.model = model
            return True

    def get_model_name(self):
        return self.model.model_name

    def generate_response(self, message, context):
        if DEBUG:
            print('Querying response as ' + self.name + '...')
        response = self.model.generate_response(self.prompt, message, context, max_tokens=self.token_limit)
        self.last_json = self.model.get_raw_json_request()
        return response

