import json
import logging
import os

from stuff import api_keys
from src.global_config import PERSONA_SAVE_FILE
import src.global_config
from src.message_handler import *
from src.persona import *
import openai
import anthropic
import anthropic.resources.messages

# get_model_list(update=False): If the update parameter is set to True, the function queries the API to update
# and print the list of available models from OpenAI and Google. If update is False, it will return the models
# saved in gloabl_config

def get_model_list(update=False):
    if update:
        logging.info('Updating available models from API...')
        all_available_models = {'From OpenAI': refresh_available_openai_models(),
                                'From Google': refresh_available_google_models(),
                                'From Anthropic': refresh_available_anthropic_models(),
                                'Local': ['local']
                                }
        logging.debug(all_available_models)
        save_models_to_file(all_available_models)
        return all_available_models
    else:
        return load_models_from_file()


# OpenAI
def refresh_available_openai_models():
    client = openai.OpenAI(api_key=api_keys.openai)
    openai_models = client.models.list()
    trimmed_list = [model.id for model in openai_models if 'gpt-3' in model.id or 'gpt-4' in model.id]
    logging.debug(trimmed_list)
    return trimmed_list


# Google (lol)
def refresh_available_google_models():
    # TODO: add functionality as there are new model(s) like gemini
    google_models = 'None supported'  # basically only 1 model rn
    #  chat-bison uses different api syntax and isn't currently worth the time implementing because goog sucks
    # all_available_models['From Google'] = google_models
    return google_models

def refresh_available_anthropic_models():
    # TODO: can't find api call, some other way to get this information dynamically?
    models = ["claude-3-opus-20240229",
              "claude-3-sonnet-20240229",
              "claude-3-haiku-20240307",
              "claude-2.1",
              "claude-2.0",
              "claude-instant-1.2"]
    return models


def load_models_from_file():
    if not os.path.exists(PERSONA_SAVE_FILE):
        logging.warning(f"File '{PERSONA_SAVE_FILE}' does not exist.")
        return
    with open(PERSONA_SAVE_FILE, "r") as file:
        data = json.load(file)
        return data['models']


def save_models_to_file(models_dict):
    with open(PERSONA_SAVE_FILE, 'r') as file:
        save_data = json.load(file)
    save_data['models'] = models_dict
    with open(PERSONA_SAVE_FILE, 'w') as file:
        json.dump(save_data, file, indent=4)
    logging.info(f"Updated persona save.")


def break_and_recombine_string(input_string, substring_length, bumper_string):
    substrings = [input_string[i:i + substring_length] for i in range(0, len(input_string), substring_length)]
    formatted_substrings = [bumper_string + substring + bumper_string for substring in substrings]
    combined_string = ' '.join(formatted_substrings)
    return combined_string


def split_string_by_limit(input_string, char_limit):
    words = input_string.split(" ")
    current_line = ""
    result = []

    for word in words:
        # Check if adding the next word would exceed the limit
        if len(current_line) + len(word) + 1 > char_limit:
            result.append(current_line.strip())
            current_line = word
        else:
            current_line += " " + word

    # Add the last line if there's any content left
    if current_line:
        result.append(current_line.strip())

    return result
