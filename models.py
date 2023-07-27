import api_keys
import openai
import google.generativeai as palm


# TODO: logits! openAI only I think
# TODO: context is not yet implemented

class Gpt3Turbo:
    def __init__(self, model_name="gpt-3.5-turbo", temperature=0.8, max_tokens=100, top_p=1.0):
        self.api_key = api_keys.openai
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

    def generate_response(self, prompt, message, context):
        openai.api_key = self.api_key
        completion = openai.ChatCompletion.create(
            # messages=[ {"role": "system", "content": "You are a helpful assistant."},
            # {"role": "user", "content": "Who won the world series in 2020?"},
            # {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
            # {"role": "user", "content": "Where was it played?"} ]
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": context},
                {"role": "user", "content": message.content}
            ],
            model=self.model_name,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            top_p=self.top_p,
            frequency_penalty=0,
            presence_penalty=0
        )
        return completion.choices[0].message.content


class PalmPersonality:
    def __init__(self, api_key, model_name='models/chat-bison-001', temperature=0.8, max_tokens=100, top_p=1.0):
        self.api_key = api_key
        self.model_name = model_name
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p

    def generate_response(self, prompt, messages=[], examples=[]):
        palm.configure(api_key=api_keys.google)

        defaults = {
            'model': self.model_name,
            'temperature': self.temperature,
            # todo: idk maybe have it generate multiple ones and autopick the best or some shit,
            #  or at least guard against empty responses
            'candidate_count': 1,
            'top_k': 40,
            'top_p': 0.95,
        }
        context = ""
        # TODO: prolly not here, add command to store message as example
        messages.append("NEXT REQUEST")
        response = palm.chat(
            **defaults,
            context=context,
            examples=examples,
            messages=messages
        )
        if response.last is None:
            print('good job you fucked it up, no response')
            # print('safety info:') #for ext completion rather than chat
            # print(response.safety_feedback)
            print('filter info:')
            print(response.filters)
            # Response of the AI to your most recent request to console
            print(response.last)

        return response.last[0]
