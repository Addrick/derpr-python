import logging

from src import engine
from src.message_handler import *
from src.utils import *
from src.global_config import *


class Persona:
    def __init__(self, persona_name, model_name, prompt, context_limit=10, token_limit=100):
        self.persona_name = persona_name
        self.prompt = prompt
        self.context_length = int(context_limit)
        self.response_token_limit = token_limit

        self.model = None
        self.temperature = DEFAULT_TEMPERATURE
        self.top_p = DEFAULT_TOP_P
        self.top_k = DEFAULT_TOP_K

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
            logging.error("Error: Input is not an integer.")
            return False

    def set_temperature(self, new_temp):
        self.model.set_temperature(new_temp)

    def set_new_top_p(self, new_top_p):
        self.model.set_new_top_p(new_top_p)

    def set_new_top_k(self, new_top_k):
        self.model.set_new_top_k(new_top_k)

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
        model = engine.TextEngine(model_name,
                                  token_limit=(self.response_token_limit+1),
                                  top_k=self.top_k,
                                  top_p=self.top_p)
        self.model = model
        return model

    def get_model_name(self):
        return self.model.model_name

    def set_conversation_mode(self, conversation_mode):
        self.conversation_mode = conversation_mode

    async def generate_response(self, message, context):
        logging.info('Querying response as ' + self.persona_name + '...')
        context = context[1:self.context_length+1]
        context = context[::-1]  # Reverse the history list
        context = " \n".join(context)
        context = 'recent chat history: \n' + context

        # todo: implement token limit
        #  token_limit = self.response_token_limit
        response = await self.model.generate_response(self.prompt, message, context)
        self.last_json = self.model.get_raw_json_request()

        # conversation mode
        if self.conversation_mode and self.context_length < GLOBAL_CONTEXT_LIMIT:
            self.context_length += 2

        return response

