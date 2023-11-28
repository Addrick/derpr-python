import asyncio

from src import utils
from stuff import api_keys
import openai
import google.generativeai as palm
import inspect
import sys
from global_config import *

class TextEngine:
    def __init__(self, model_name='none',
                 token_limit=DEFAULT_TOKEN_LIMIT,
                 temperature=DEFAULT_TEMPERATURE,
                 top_p=DEFAULT_TOP_P,
                 top_k=DEFAULT_TOP_K):

        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = token_limit
        self.top_p = top_p
        self.json_request = None
        self.json_response = None
        # self.all_available_models

        # OpenAI models
        self.openai_models_available = utils.get_model_list()['From OpenAI']
        self.frequency_penalty = 0
        self.presence_penalty = 0

        # Google models
        self.google_models_available = utils.get_model_list()['From Google']
        self.top_k = top_k

        # Local models
        # TODO: add me (Kobold cpp?)

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

    # Generates response based on model_name
    def generate_response(self, prompt, message, context):
        # route specific API and model to use based on model_name
        # if model_name matches models found in various APIs
        if self.model_name in self.openai_models_available:
            messages = [
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},  # TODO: try iterating this for 1 msg/context block
                {"role": "user", "content": message}]
            response = self._generate_openai_response(messages)
            # loop = asyncio.get_event_loop()
            # response = loop.run_until_complete(self._generate_openai_response_stream(messages))


        # TODO: Google model query
        elif self.model_name in self.google_models_available:
            response = self._generate_google_response(prompt, message, context)

        # TODO: Local model query
        elif self.model_name == 'local':
            response = 'local not yet implemented'

        else:
            print("Error: persona's model name not found.")
            response = "Error: persona's model name not found."

        return response

    def _generate_openai_response(self, messages):
        response = 'Error: empty/no completion.'
        if self.model_name not in self.openai_models_available:
            print("Error: model name not found in available OpenAI models.")
            return "Error: model name not found in available OpenAI models."
        else:
            try:
                completion = openai.ChatCompletion.create(
                    api_key=api_keys.openai,
                    messages=messages,
                    model=self.model_name,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    frequency_penalty=self.frequency_penalty,
                    presence_penalty=self.presence_penalty,
                )
                self.json_request = {
                    "model": self.model_name,
                    "messages": messages,
                    "options": {
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "top_p": self.top_p,
                        "frequency_penalty": self.frequency_penalty,
                        "presence_penalty": self.presence_penalty
                    },
                    "object": "chat.completion",
                    "id": self.model_name,
                    "stream": False
                }
                self.json_response = completion
                token_count = ' (' + str(completion.usage['total_tokens']) + ')'
                response = completion.choices[0].message.content

            except openai.error.APIError as e:
                return e.http_status + ": \n" + e.user_message

            except openai.error.APIConnectionError as e:
                return e.user_message

        return response + token_count

    # async def _generate_openai_response_stream(self, messages):
    #     from openai import AsyncOpenAI
    #     client = AsyncOpenAI()
    #     response = 'Error: empty/no completion.'
    #     if self.model_name not in self.openai_models_available:
    #         print("Error: model name not found in available OpenAI models.")
    #         return "Error: model name not found in available OpenAI models."
    #     else:
    #         try:
    #             completion = openai.ChatCompletion.create(
    #                 api_key=api_keys.openai,
    #                 messages=messages,
    #                 model=self.model_name,
    #                 temperature=self.temperature,
    #                 max_tokens=self.max_tokens,
    #                 top_p=self.top_p,
    #                 frequency_penalty=self.frequency_penalty,
    #                 presence_penalty=self.presence_penalty,
    #                 stream=True,
    #             )
    #             self.json_request = {
    #                 "model": self.model_name,
    #                 "messages": messages,
    #                 "options": {
    #                     "temperature": self.temperature,
    #                     "max_tokens": self.max_tokens,
    #                     "top_p": self.top_p,
    #                     "frequency_penalty": self.frequency_penalty,
    #                     "presence_penalty": self.presence_penalty
    #                 },
    #                 "object": "chat.completion",
    #                 "id": self.model_name,
    #                 "stream": False
    #             }
    #             self.json_response = completion
    #
    #         except openai.error.APIError as e:
    #             return e.http_status + ": \n" + e.user_message
    #
    #         except openai.error.APIConnectionError as e:
    #             return e.user_message
    #
    #     responses = []
    #     async for message in completion:
    #         responses.append(message['choices'][0]['message']['content'])
    #     return responses

    def _generate_google_response(self, prompt, message, context=[], examples=[]):
        palm.configure(api_key=api_keys.google)
        context.append("NEXT REQUEST")  # Google seems to do this on all their autogenerated code
        persona_name = message.split()[0]  # name should be first word of latest message
        chat_request = f"you are in character as {persona_name}. {prompt} {persona_name} is chatting with others, " \
                       f"here is the most recent conversation: \n{context}\n " \
                       f"Now, respond to the chat request as {persona_name}: "
        defaults = {
            'model': 'models/' + self.model_name,
            'temperature': self.temperature,
            'candidate_count': 1,
            'top_k': self.top_k,
            'top_p': self.top_p,
        }
        completion = palm.generate_text(
            **defaults,
            model='models/text-bison-001',
            prompt=prompt,
            safety_settings=[
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_UNSPECIFIED,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_DEROGATORY,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_TOXICITY,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_VIOLENCE,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_SEXUAL,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_MEDICAL,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                },
                {
                    "category": palm.safety_types.HarmCategory.HARM_CATEGORY_DANGEROUS,
                    "threshold": palm.safety_types.HarmBlockThreshold.BLOCK_NONE,
                }])
        if completion.last is None:
            print('good job, no response from server')
            print('filter info:')
            print(completion.filters)
            print(completion.last)
        self.json_response = completion
        return completion.last[0]
