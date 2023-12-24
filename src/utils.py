import openai

import engine
from src import global_config
from stuff import api_keys


# get_model_list(update=False): If the update parameter is set to True, the function queries the API to update
# and print the list of available models from OpenAI and Google. If update is False, it will return the models
# saved in gloabl_config
def get_model_list(update=False):
    if update:
        print('Updating available models from API...')
        all_available_models = {'From OpenAI': refresh_available_openai_models(),
                                'From Google': refresh_available_google_models(),
                                'Local': 'local'
                                }
        print(all_available_models)
        global_config.MODELS_AVAILABLE = all_available_models
        return all_available_models
    else:
        return global_config.MODELS_AVAILABLE


# OpenAI
def refresh_available_openai_models():
    # openai.organization = "derpr"
    openai_models = openai.Model.list(api_key=api_keys.openai)
    trimmed_list = []
    for model in openai_models['data']:
        # trim list down to just gpt models; syntax is likely poor/incompatible for completion or edits
        if 'gpt-3' in model['id'] or 'gpt-4' in model['id']:
            trimmed_list.append(model['id'])

    if global_config.DEBUG:
        print(trimmed_list)
    # all_available_models['From OpenAI'] = trimmed_list
    return trimmed_list


# Google (lol)
def refresh_available_google_models():
    google_models = 'text-bison-001'  # basically only 1 model rn
    #  chat-bison uses different api syntax and isn't currently worth the time implementing because goog sucks
    # all_available_models['From Google'] = google_models
    return google_models


def break_and_recombine_string(input_string, substring_length, bumper_string):
    substrings = [input_string[i:i + substring_length] for i in range(0, len(input_string), substring_length)]
    formatted_substrings = [bumper_string + substring + bumper_string for substring in substrings]
    combined_string = ' '.join(formatted_substrings)
    return combined_string
