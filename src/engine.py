import asyncio
import json

from src import utils
from stuff import api_keys
import openai
from openai import OpenAI

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

        self.openai_client = OpenAI(api_key=api_keys.openai)

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


        # TODO: test (finish?) Google model query
        elif self.model_name in self.google_models_available:
            response = self._generate_google_response(prompt, message, context)

        elif self.model_name == 'local':
            response = self._generate_local_response(prompt, message, context)

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
                completion = self.openai_client.chat.completions.create(
                    messages=messages,
                    model=self.model_name,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    top_p=self.top_p,
                    frequency_penalty=self.frequency_penalty,
                    presence_penalty=self.presence_penalty)
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
                token_count = ' (' + str(completion.usage.total_tokens) + ')'
                response = completion.choices[0].message.content

            except openai.APIError as e:
                return e.http_status + ": \n" + e.user_message

            except openai.APIConnectionError as e:
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

        # TODO: test me

    def _generate_local_response(self, prompt, message, context=[]):
        import requests

        url = 'http://localhost:5001/api/v1/generate'
        # TODO: experiment with prompting structures
        # hardcoded for mistral 8x7b, the settings below actually just seems to do that thing where the LLM dumps its training data
        # <s> [INST] Instruction [/INST] Model answer</s> [INST] Follow-up instruction [/INST]
        # payload = {
        #     "prompt": prompt + ", now respond to this chat message and history: " + message,
        #     "temperature": 0.5,
        #     "top_p": self.top_p,
        #     "max_context_length": 10,
        #     "max_length": self.max_tokens,
        #     "quiet": False,
        #     "rep_pen": 1.1,
        #     "rep_pen_range": 256,
        #     "rep_pen_slope": 1,
        #     "tfs": 1,
        #     "top_a": 0,
        #     "top_k": self.top_k,
        #     "typical": 1
        # }
        ######################################
        # # hardcoded for mistral miqu-1-70b
        # <s> [INST] QUERY_1 [/INST] ANSWER_1</s> [INST] QUERY_2 [/INST] ANSWER_2</s>...
        payload = {
            "n": 1,
            "max_context_length": 2048,
            "max_length": 128,
            "rep_pen": 1.1,
            "temperature": .5,
            "top_p": 0.95,
            "top_k": 0,
            "top_a": 0,
            "typical": 1,
            "tfs": 1,
            "rep_pen_range": 300,
            "rep_pen_slope": 0.7,
            "sampler_order": [6, 0, 1, 3, 4, 2, 5],
            "memory": "", "min_p": 0, "presence_penalty": 0,
            "genkey": "KCPP6857", "prompt": prompt + ", now respond to this chat message: " + message,
            "quiet": True,
            "stop_sequence": ["You:", "\nYou"],
            "use_default_badwordsids": False
        }
        try:
            raw_response = requests.post(url, json=payload)
            raw_response.raise_for_status()  # Raise an exception for non-2xx status codes
            response = raw_response.text.replace('{"results": [{"text": "\nresponse:', '{"results": [{"text": "\\nresponse:')

            # Parse the string as JSON
            json_data = json.loads(response)

            # Extract the <response> value
            response = json_data['results'][0]['text'].split(': ')[1]

            print(response)
            return response
        except requests.exceptions.RequestException as e:
            err_response = (f"An error occurred: {e}")
            print(err_response)
            return err_response
