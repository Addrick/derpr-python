import json
from global_config import *
from src import engine, utils

# TODO: dump_last needs to be handled here as the last request is now persona-specific (right?)
class Persona:
    def __init__(self, persona_name, model_name, prompt, context_limit=10, token_limit=100):
        self.persona_name = persona_name
        self.prompt = prompt
        self.context_length = int(context_limit)
        self.response_token_limit = token_limit
        self.model = None
        self.last_json = 'none yet'
        self.conversation_mode = False
        # self.last_response = 'none yet'

        self.set_model(model_name)

    def get_context_length(self):
        return self.context_length

    def set_context_length(self, context_length):
        self.context_length = int(context_length)

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

    def set_model(self, model_name):
        # Model name should be checked before calling this, messages will fail later if model name is invalid
        model = engine.TextEngine(model_name, token_limit=(self.response_token_limit+1))
        self.model = model
        return model

    def get_model_name(self):
        return self.model.model_name

    def set_conversation_mode(self, conversation_mode):
        self.conversation_mode = conversation_mode

    def generate_response(self, message, context):
        if DEBUG:
            print('Querying response as ' + self.persona_name + '...')
        context = context[1:self.context_length]
        context = context[::-1]  # Reverse the history list
        context = " \n".join(context)
        context = 'recent chat history: \n' + context

        # todo: implement token limit
        #  token_limit = self.response_token_limit
        response = self.model.generate_response(self.prompt, message, context)
        self.last_json = self.model.get_raw_json_request()

        # conversation mode
        if self.conversation_mode and self.context_length < GLOBAL_CONTEXT_LIMIT:
            self.context_length += 2

        return response

