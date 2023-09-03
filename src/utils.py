from openai import Model

import engine
from global_config import *
from stuff import api_keys

all_available_models = {'From OpenAI': '', 'From Google': ''}
def refresh_model_list():
    refresh_available_openai_models()
    refresh_available_google_models()
    # refresh_available_local_models()

# OpenAI
def refresh_available_openai_models():
    openai_models = Model.list(api_key=api_keys.openai)
    trimmed_list = []
    for model in openai_models['data']:
        # trim list down to just gpt models; syntax is likely poor/incompatible for completion or edits
        if 'gpt-3' in model['id'] or 'gpt-4' in model['id']:
            trimmed_list.append(model['id'])

    if DEBUG:
        print(trimmed_list)
    all_available_models['From OpenAI'] = trimmed_list
    return trimmed_list

# Google (lol)
def refresh_available_google_models():
    google_models = 'text-bison-001'  # basically only 1 model rn
    #  chat-bison uses different api syntax and isn't currently worth the time implementing because it sucks
    all_available_models['From Google'] = google_models
    return google_models

def check_model_available(model_to_check):
    lowest_order_items = []
    for value in engine.models_available.values():
        if isinstance(value, list):
            lowest_order_items.extend(value)
        else:
            lowest_order_items.append(value)

    if model_to_check in lowest_order_items:
        if DEBUG:
            print(f"The value '{model_to_check}' exists.")
        return True
    else:
        if DEBUG:
            print(f"The value '{model_to_check}' is not found.")
        return False

