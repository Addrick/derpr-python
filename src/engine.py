import json
import logging

import aiohttp
import google.generativeai as palm
import openai
import anthropic

from openai import OpenAI, AsyncOpenAI
from stuff import api_keys

from src import utils
from src.global_config import *


def launch_koboldcpp():
    import traceback
    import subprocess

    try:
        # Launches koboldcpp with preconfigured settings file
        command = [KOBOLDCPP_EXE, "--config", KOBOLDCPP_CONFIG]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        while True:
            output = process.stdout.readline()
            if output == b'' and process.poll() is not None:
                break
            if output:
                output = output.strip().decode('utf-8')
                logging.info("koboldcpp: " + output)  # Process the output as needed
                if "Please connect to custom endpoint at http://localhost:5001" in output:
                    #  report startup status to chat
                    return True

        # Get the return code of the subprocess
        return_code = process.poll()
        logging.info('Subprocess returned with code: %s', return_code)

    except Exception:
        traceback.print_exc()


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
        # self.openai_client = AsyncOpenAI(api_key=api_keys.openai) # TODO: this should be here instead of
        #  re-instantiated on every _generate_openai_response call but when moving declaration here 'await' throws an
        #  error and not using await blocks code during the request
        self.openai_models_available = utils.get_model_list()['From OpenAI']
        self.frequency_penalty = 0
        self.presence_penalty = 0

        # Google models
        self.google_models_available = utils.get_model_list()['From Google']
        self.top_k = top_k

        # Anthropic models
        self.anthropic_models_available = utils.get_model_list()['From Anthropic']

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
            logging.info("Error: Input is not an integer.")
            return False

    def set_temperature(self, new_temp):
        self.temperature = new_temp

    def set_top_p(self, top_p):
        self.top_p = top_p

    def set_top_k(self, top_k):
        self.top_k = top_k

    # Generates response based on model_name
    async def generate_response(self, prompt, message, context):
        # route specific API and model to use based on model_name
        # if model_name matches models found in various APIs

        # OpenAI request
        if self.model_name in self.openai_models_available:
            if context is not None:
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": context},
                    # TODO: try iterating this for 1 msg/context block for better model processing
                    {"role": "user", "content": message}]
            else:
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": message}]
            response = await self._generate_openai_response(messages)
        # Anthropic request
        if self.model_name in self.anthropic_models_available:
            if context is not None:
                messages = [
                    {"role": "user", "content": f'{context} \n {message}'}]
                    # TODO: this needs distinct flagging of assistant message, so logic based on username
            else:
                messages = [
                    {"role": "user", "content": message}]

            if self.model_name in self.anthropic_models_available:
                response = await self._generate_anthropic_response(prompt, messages)

        # TODO: test (finish?) Google model query
        elif self.model_name in self.google_models_available:
            response = await self._generate_google_response(prompt, message, context)

        elif self.model_name == 'local':
            response = await self._generate_local_response(prompt, message, context)


        else:
            logging.info("Error: persona's model name not found.")
            response = "Error: persona's model name not found."

        return response

    async def _generate_openai_response(self, messages):
        openai_client = AsyncOpenAI(api_key=api_keys.openai)
        if self.model_name not in self.openai_models_available:
            logging.info("Error: model name not found in available OpenAI models.")
            return "Error: model name not found in available OpenAI models."
        else:
            try:
                completion = await openai_client.chat.completions.create(
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
                }
                self.json_response = completion
                token_count_and_model = f' ({str(completion.usage.total_tokens)} tokens using {self.model_name})'
                response = completion.choices[0].message.content
                logging.debug(response + token_count_and_model)
                return response + token_count_and_model

            except openai.APIError as e:
                return e.code + ": \n" + e.message

            except AttributeError as e:
                return str(e)

    async def _generate_openai_response_stream(self, messages):
        # TODO: finish if I ever get a use case for streamed output
        # currently does not provide usage field for token usage reporting and provides no current benefit
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=api_keys.openai)  # TODO: put this somewhere better, may be a memory leak
        if self.model_name not in self.openai_models_available:
            logging.info("Error: model name not found in available OpenAI models.")
            return "Error: model name not found in available OpenAI models."
        else:
            completion = await client.chat.completions.create(
                messages=messages,
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty,
                stream=True
            )

            # Print the streamed output to the console
            for chunk in completion:
                print(chunk['choices'][0]['text'])

    async def _generate_local_response(self, prompt, message, context=None):
        if context is None:
            context = []
        url = 'http://localhost:5001/api/v1/generate'

        payload = {
            "n": 1,
            "max_context_length": 2048,
            "max_length": self.max_tokens,
            "rep_pen": 1.1,
            # "temperature": 0.44,
            "temperature": self.temperature,
            # "top_p": 0.5,
            "top_p": self.top_p,
            # "top_k": 0,
            "top_k": self.top_k,
            "top_a": 0.75,
            "typical": 0.19,
            "tfs": 0.97,
            "rep_pen_range": 1024,
            "rep_pen_slope": 0.7,
            "sampler_order": [6, 0, 1, 3, 4, 2, 5],
            "memory": prompt,
            "min_p": 0,
            "presence_penalty": 0,
            "genkey": "KCPP6857",
            "prompt": "" + context + ",\n now you respond: \n" + message + "\n",
            "quiet": False,
            "stop_sequence": ["You:"],
            "use_default_badwordsids": False
        }

        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
                async with session.post(url, json=payload) as response:
                    response_data = await response.text()
                    response_data = response_data.replace('{"results": [{"text": "\nresponse:',
                                                          '{"results": [{"text": "\\nresponse:')
                    json_data = json.loads(response_data)
                    response_text = json_data['results'][0]['text'].split(': ')

                    logging.info(response_text)
                    return '\n'.join(response_text)
        except aiohttp.ClientError as e:
            err_response = f"An error occurred: {e}"
            logging.info(err_response)
            return err_response

    async def _generate_anthropic_response(self, prompt, messages):
        client = anthropic.Anthropic(api_key=api_keys.anthropic)
        message = client.messages.create(
            system=prompt,
            model=self.model_name,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            max_tokens=self.max_tokens,
            messages=messages,
            stream=False
        )
        self.json_request = {
            "system": prompt,
            "model": self.model_name,
            "messages": messages,
            "options": {
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "top_p": self.top_p,
                "top_k": self.top_k,
            },
            "object": "chat.completion",
            "id": self.model_name,
        }
        return message.content[0].text
