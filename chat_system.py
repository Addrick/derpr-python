import json

import api_keys
from persona import *
import models

DEBUG = 1


# ChatSystem
# Maintains personas, responsible for executing dev commands
class ChatSystem:
    def __init__(self):
        self.personas = {}
        self.models_available = []
        self.update_models()

    def update_models(self):
        self.models_available = models.get_available_models()

    def get_persona_list(self):
        return self.personas

    def add_persona(self, name, model_name, prompt):
        persona = Persona(name, model_name, prompt)
        self.personas[name] = persona

    def update_parameters(self, persona_name, new_parameters):
        if persona_name in self.personas:
            self.personas[persona_name].update_parameters(new_parameters)
        else:
            print(f"persona '{persona_name}' does not exist.")

    def add_to_prompt(self, persona_name, text_to_add):
        if persona_name in self.personas:
            self.personas[persona_name].add_to_prompt(text_to_add)
        else:
            print(f"persona '{persona_name}' does not exist.")

    def generate_response(self, persona_name, message, context):
        clean_context = context.replace("\n", " ")
        if persona_name in self.personas:
            return f"{persona_name}: {self.personas[persona_name].generate_response(message, clean_context, )}"
        else:
            print(f"persona '{persona_name}' does not exist.")

    # Checks for keywords at the start of a message, reroutes to internal program settings
    # Returns True if dev command is executed, used to skip chat request in main.py loop
    # Commands use the format `derpr <command> <arguments...>`. For example:
    #
    # - To add a persona: `derpr add persona <name> <prompt>`
    # - To change the model: `<persona_name> change model <model_name>` TODO: fuckit-style guessing for close matches
    # - To update parameters: `<persona_name> update parameters <persona_name> <new_parameters...>` TODO:
    # - To set a prompt: `<persona_name> set prompt <prompt>`
    #
    # TODO: finish: remember,
    def preprocess_message(self, message):
        # Extract the command and arguments from the message content
        persona_name = message.content.split()[0]
        command, *args = message.content.split()[1:]
        current_persona = self.personas[persona_name]

        if command == 'help':
            help_msg = "remember <+prompt>, what prompt/model/personas, set prompt/model/token_limit, dump last"
            return help_msg

        # Appends the message to end of prompt
        if command == 'remember':
            if len(args) >= 2:
                text_to_add = ' ' + message.content
                self.add_to_prompt(persona_name, text_to_add)
                response = 'success!' + " just kidding haha doesn't work yet probably"
                return response

        elif command == 'add':
            keyword = args[0]

            if keyword == 'persona':
                persona_name = args[1]
                prompt = ' '.join(args[1:])
                self.add_persona(persona_name, models.Gpt3Turbo(), prompt)
                response = f"Ziggy added '{persona_name}': {prompt}"
                return response

        elif command == 'what':
            keyword = args[0]

            if keyword == 'prompt':
                prompt = current_persona.get_prompt()
                response = f"Prompt for '{persona_name}': {prompt}"
                return response
            if keyword == 'model':
                model_name = current_persona.get_model_name()
                response = f"{persona_name} is using {model_name}"
                return response
            if keyword == 'models':
                model_names = models.get_available_models()
                response = f"Available model options are: {model_names}"
                return response
            if keyword == 'personas':
                personas = self.get_persona_list()
                response = f"Available personas are: {personas}"
                return response

        elif command == 'set':
            keyword = args[0]

            if keyword == 'prompt':
                # TODO: add some prompt buffs like 'you're in character as x', maybe test first
                prompt = ''.join(args[1:])
                current_persona.set_prompt(prompt)
                print(f"Prompt set for '{persona_name}'.")
                return 'new_prompt_set'
            elif keyword == 'model':
                model_name = args[1]
                if hasattr(models, model_name):
                    # Instantiate the model class based on the model name
                    model_class = getattr(models, model_name)
                    current_persona.set_model(model_class())
                    return f"Model set to '{model_name}'."
                else:
                    return f"Model '{model_name}' does not exist."
            elif keyword == 'token_limit':
                token_limit = args[1]
                existing_prompt = current_persona.get_prompt()
                # success = current_persona.set_response_token_limit(int(token_limit))
                self.add_persona(persona_name, models.Gpt3Turbo(), existing_prompt, token_limit=token_limit)
                # if success:
                #     return f"Set token limit: '{token_limit}' response tokens."
                return f"Set token limit: '{token_limit}' response tokens."
                # else:
                #     return f"Failed to set token limit: '{token_limit}'."

        elif command == 'dump_last':
            raw_json_response = current_persona.get_last_json()
            return f"{json.dumps(raw_json_response, indent=4)}"

        # elif command == 'update':
        #     if len(args) >= 2 and args[0] == 'parameters':
        #         persona_name, new_parameters = args[1], args[2:]
        #         self.update_parameters(persona_name, new_parameters)
        #     else:
        #         print("Usage: update parameters <persona_name> <new_parameters...>")

        # elif command == 'add':
        #     if len(args) >= 2 and args[0] == 'persona':
        #         name, prompt = args[1], args[2]
        #         self.add_persona(name, prompt)
        #         return 'success!' + " just kidding haha doesn't work yet"
        #     else:
        #         print("Usage: add persona <name> <prompt>")

        # ... Add more commands as needed
        else:
            if DEBUG:
                print("No commands found.")
