import os
import re

from src.persona import *
from src.utils import *
from src.global_config import *
from src.utils import break_and_recombine_string
from src.message_handler import *


# ChatSystem
# Maintains personas, queries the engine system for responses, executes dev commands
class ChatSystem:
    def __init__(self):
        self.personas = {}
        self.models_available = get_model_list()
        self.bot_logic = BotLogic(self)  # Pass the instance of ChatSystem to BotLogic

    def load_personas_from_file(self, file_path):
        if not os.path.exists(file_path):
            print(f"File '{file_path}' does not exist.")
            return
        with open(file_path, "r") as file:
            persona_data = json.load(file)
            for persona in persona_data['personas']:
                try:
                    name = persona["name"]
                    model_name = persona["model_name"]
                    prompt = persona["prompt"]
                    context_limit = persona["context_limit"]
                    token_limit = persona["token_limit"]
                    self.add_persona(name, model_name, prompt, context_limit, token_limit, save_new=False)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON file '{file_path}': {str(e)}")
                    return

    def get_persona_list(self):
        return self.personas

    def add_persona(self, name, model_name, prompt, context_limit, token_limit, save_new=True):
        persona = Persona(name, model_name, prompt, context_limit, token_limit)
        self.personas[name] = persona
        # add to persona bank file
        if save_new:
            self.save_personas_to_file(PERSONA_SAVE_FILE)

    def delete_persona(self, name, save=False):
        del self.personas[name]
        if save:
            self.save_personas_to_file(PERSONA_SAVE_FILE)

    def save_personas_to_file(self, file_path=PERSONA_SAVE_FILE):
        persona_dict = self.to_dict()
        with open(file_path, "w") as file:
            file.write(json.dumps(persona_dict))
        if DEBUG:
            print(f"Updated persona save.")

    def to_dict(self):
        persona_dict = {'personas': []}
        for persona_name, persona in self.personas.items():
            persona_json = {
                "name": persona.persona_name,
                "prompt": persona.prompt,
                "model_name": persona.model.model_name,
                "context_limit": persona.context_length,
                "token_limit": persona.response_token_limit,
            }
            persona_dict['personas'].append(persona_json)
        return persona_dict

    def add_to_prompt(self, persona_name, text_to_add):
        if persona_name in self.personas:
            self.personas[persona_name].add_to_prompt(text_to_add)
            # self.save_personas_to_file(PERSONA_SAVE_FILE)
        else:
            print(f"persona '{persona_name}' does not exist.")

    def generate_response(self, persona_name, message, context=''):
        if persona_name in self.personas:
            persona = self.personas[persona_name]
            reply = persona.generate_response(message, context)
            if persona_name != 'derpr':
                reply = f"{persona_name}: {reply}"
            return reply
        else:
            print(f"persona '{persona_name}' does not exist.")

    def check_models_available(self):
        self.models_available = utils.get_model_list()

    def check_model_available(self, model_to_check):
        lowest_order_items = []
        for value in self.models_available.values():
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



