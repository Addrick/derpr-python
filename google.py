"""
handles google PaLM api calls
also known as a waste of a supercomputer
"""
# noinspection PyUnresolvedReferences
import google.generativeai as palm
import api_keys


def ask_palm(prompt, messages):
    palm.configure(api_key=api_keys.google)

    defaults = {
        'model': 'models/text-bison-001',
        'temperature': 0.5,
        'candidate_count': 3,
        'top_k': 40,
        'top_p': 0.95,
        'max_output_tokens': 4096,
        'stop_sequences': [],
        'safety_settings': [{"category": "HARM_CATEGORY_DEROGATORY", "threshold": 3},
                            {"category": "HARM_CATEGORY_TOXICITY", "threshold": 3},
                            {"category": "HARM_CATEGORY_VIOLENCE", "threshold": 3},
                            {"category": "HARM_CATEGORY_SEXUAL", "threshold": 3},
                            {"category": "HARM_CATEGORY_MEDICAL", "threshold": 3},
                            {"category": "HARM_CATEGORY_DANGEROUS", "threshold": 3}],
    }
    response = palm.generate_text(
        **defaults,
        prompt=messages)
    if response.result is None:
        print('good job you fucked it up, no response')
        print('safety info:')
        print(response.safety_feedback)
        print('filter info:')
        print(response.filters)

    print(response.result)
    return response

def chat_palm(prompt, messages, examples):
    #TODO: dynamic control of examples from chat
    #TODO: messages handling/formatting chat history, handle this outside of this function?
    palm.configure(api_key=api_keys.google)

    defaults = {
        'model': 'models/chat-bison-001',
        'temperature': 0.5,
        'candidate_count': 3,
        'top_k': 40,
        'top_p': 0.95
    }
    response = palm.chat(
        **defaults,
        context=prompt,
        messages=messages)
    # response = palm.generate_text(
    #     **defaults,
    #     prompt=messages)
    if response.last is None:
        print('good job you fucked it up, no response')
        # print('safety info:')
        # print(response.safety_feedback)
        # print('filter info:')
        # print(response.filters)

    print(response.last)
    return response

def test(prompt, message):
    prompt = 'you are in character as derpr, my test of the google palm api. derpr is a dick, he insults the user constantly.'
    messages = [{'author':'me',
                 'content':message}]
    out = chat_palm(prompt, messages=messages)
    return out
