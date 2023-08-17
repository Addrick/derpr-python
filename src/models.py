from src import api_keys
import openai
import google.generativeai as palm
import inspect
import sys


class LanguageModel:
    def __init__(self, model_name='basemodel', temperature=0.8, max_tokens=128, top_p=1.0):
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


class Gpt3Turbo(LanguageModel):
    def __init__(self, model_name="gpt-3.5-turbo", temperature=.8, max_tokens=200, top_p=1.0):
        super().__init__(model_name, temperature, max_tokens, top_p)
        self.api_key = api_keys.openai
        self.frequency_penalty = 0
        self.presence_penalty = 0

    def generate_response(self, prompt, message, context):
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": context},
            {"role": "user", "content": message.content}]
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

# https://developers.generativeai.google/guide/safety_setting
class PalmBison(LanguageModel):
    def __init__(self, model_name='palm-chat', temperature=0.8, max_tokens=200, top_p=1.0):
        super().__init__(model_name, temperature, max_tokens, top_p)
        self.api_key = api_keys.google

    def generate_response(self, prompt, message, context=[], examples=[]):
        palm.configure(api_key=self.api_key)
        context.append("NEXT REQUEST")
        # Build chat completion request for text completion model:
        persona_name = message.split()[0] # name should be first word of latest message

        chat_request = f"you are in character as {persona_name}. {persona_name} is chatting with others, here is the most recent conversation: \n{context}\n Now, respond to the chat request as {persona_name}: "
        completion = self._create_completion(prompt=chat_request)
        return completion

    def _create_completion(self, prompt):
        defaults = {
            'model': 'models/text-bison-001',
            'temperature': self.temperature,
            'candidate_count': 1,
            'top_k': 40,
            'top_p': 0.95,
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
            print('good job, no response')
            print('filter info:')
            print(completion.filters)
            print(completion.last)
        self.json_response = completion
        return completion.last[0]


def get_available_chat_models():
    model_list = []
    module = sys.modules[__name__]
    classes = inspect.getmembers(module, inspect.isclass)
    for _, model_class in classes:
        if issubclass(model_class, LanguageModel):
            model_instance = model_class()
            if hasattr(model_instance, "model_name"):
                if model_instance.model_name != 'basemodel':
                    model_list.append(model_instance.model_name.lower())

    # alternate method that utilizes teh model_name field and queries the API directly for all available models
    # OpenAI:
    openai_models = openai.Model.list()
    for model in openai_models['data']:
        # trim list down to just gpt models; syntax is likely poor/incompatible for completion or edits
        if 'gpt-3' in model['id'] or 'gpt-4' in model['id']:
            print(model['id'])

    return model_list


# def get_available_models():
#     model_list = []
#     for _, model in inspect.getmembers(sys.modules[__name__]):
#         if inspect.isclass(model) and model != BaseModel:
#             model_list.append(model.__name__)
#     return model_list


def get_model(model_name):
    module = sys.modules['models']
    classes = inspect.getmembers(module, inspect.isclass)
    for _, model_class in classes:
        if _ == model_name:
            return model_class()
    return False


