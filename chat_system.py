import api_keys
from persona import *
import models
import msg_preprocess

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
        persona = persona(name, model_name, prompt)
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
        if persona_name in self.personas:
            return self.personas[persona_name].generate_response(message, context)
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
            help_msg = "remember <+prompt>, what prompt/model, set prompt/model"
            return help_msg

        # Appends the message to end of prompt
        if command == 'remember':
            if len(args) >= 2:
                text_to_add = ' ' + message.content
                self.add_to_prompt(persona_name, text_to_add)
                response = 'success!' + " just kidding haha doesn't work yet probably"
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

        elif command == 'set':
            keyword = args[0]

            if len(args) == 2 and args[0] == 'model':
                model_name = args[1]
                model_class = models.get_model(model_name)

                success = current_persona.set_model(model_class)
                if success:
                    response = model_name + " set as model."
                else:
                    response = "Model not found."
                return response

            elif keyword == 'model':
                model_name = args[1]
                if hasattr(models, model_name):
                    # Instantiate the model class based on the model name
                    model_class = getattr(models, model_name)
                    self.change_model(model_class())
                    print(f"Model set to '{model_name}'.")
                else:
                    print(f"Model '{model_name}' does not exist.")

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
