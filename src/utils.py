import openai

import engine
from global_config import *
from stuff import api_keys


def get_model_list(update=False):
    if update:
        print('Updating available models from API...')
        all_available_models = {'From OpenAI': refresh_available_openai_models(),
                                'From Google': refresh_available_google_models()}
        # refresh_available_local_models()
        print(all_available_models)
        return all_available_models
    else:
        # TODO: store these along with other persona info/maybe other stuff in a config file, allow update function to update config values
        all_available_models = {'From OpenAI': ['gpt-3.5-turbo-0613', 'gpt-3.5-turbo-instruct-0914', 'gpt-3.5-turbo-0301', 'gpt-3.5-turbo-instruct', 'gpt-3.5-turbo-16k', 'gpt-4-0613', 'gpt-3.5-turbo-16k-0613', 'gpt-4', 'gpt-3.5-turbo', 'gpt-4-0314'],
                                'From Google': ['text-bison-001']}
        # refresh_available_local_models()
        return all_available_models


# OpenAI
def refresh_available_openai_models():
    # openai.organization = "derpr"
    openai_models = openai.Model.list(api_key=api_keys.openai)
    trimmed_list = []
    for model in openai_models['data']:
        # trim list down to just gpt models; syntax is likely poor/incompatible for completion or edits
        if 'gpt-3' in model['id'] or 'gpt-4' in model['id']:
            trimmed_list.append(model['id'])

    if DEBUG:
        print(trimmed_list)
    # all_available_models['From OpenAI'] = trimmed_list
    return trimmed_list

# Google (lol)
def refresh_available_google_models():
    google_models = 'text-bison-001'  # basically only 1 model rn
    #  chat-bison uses different api syntax and isn't currently worth the time implementing because goog sucks
    # all_available_models['From Google'] = google_models
    return google_models

