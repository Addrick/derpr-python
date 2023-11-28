import os
import re

from persona import *
# import models
import utils
from global_config import *
from src.utils import break_and_recombine_string


# ChatSystem
# Maintains personas, queries the engine system for responses, executes dev commands
class ChatSystem:
    def __init__(self):
        self.personas = {}
        self.models_available = utils.get_model_list()

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
        # clean_context = context.replace("\n", " ")
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

    def preprocess_message(self, message):
        if DEBUG:
            print('Checking for dev commands...')
        # Extract the command and arguments from the message content
        persona_name = re.split(r'[ ,]', message.content)[0].lower()
        command, *args = re.split(r'[ ,]', message.content)[1:]
        current_persona = self.personas[persona_name]

        # TODO: add !! command or some kind of equivalent (send message w/o context)
        # this would use alternate logic to set context_limit = 0 or maybe overwrite context var, remove !! from msg
        if command == 'help':
            help_msg = "" \
                       "Talk to a specific persona by starting your message with their name. \n \n" \
                       "Currently active personas: \n" + \
                       ', '.join(self.personas.keys()) + "\n" \
                                                         "Bot commands: \n" \
                                                         "remember <+prompt>, \n" \
                                                         "what prompt/model/personas/context/tokens, \n" \
                                                         "set prompt/model/context/tokens, \n" \
                                                         "dump_last"
            return help_msg

        # Appends the message to end of prompt
        if command == 'remember':
            if len(args) >= 2:
                text_to_add = ' ' + message.content
                self.add_to_prompt(persona_name, text_to_add)
                response = 'success!' + " just kidding haha doesn't work yet probably never tested it"
                return response

        if command == 'save':
            self.save_personas_to_file()
            response = 'Personas saved.'
            return response

        # Add new persona
        elif command == 'add':
            keyword = args[0]
            if keyword == 'persona':
                persona_name = args[1]
                prompt = ' '.join(args[1:])
                self.add_persona(persona_name, DEFAULT_MODEL_NAME, prompt, context_limit=4, token_limit=1024)
                # response = f"added '{persona_name}'"
                message = DEFAULT_WELCOME_REQUEST
                response = self.generate_response(persona_name, message)
                return response

        # Query config
        elif command == 'what':
            keyword = args[0]

            if keyword == 'prompt':
                prompt = current_persona.get_prompt()
                response = f"Prompt for '{persona_name}': {prompt}"
                return response
            elif keyword == 'model':
                model_name = current_persona.get_model_name()
                response = f"{persona_name} is using {model_name}"
                return response
            elif keyword == 'models':
                model_names = self.models_available
                formatted_models = json.dumps(model_names, indent=2, ensure_ascii=False, separators=(',', ':')).replace(
                    '\"', '')
                response = f"Available model options: {formatted_models}"
                return response
            elif keyword == 'personas':
                personas = self.get_persona_list()
                response = f"Available personas are: {personas}"
                return response
            elif keyword == 'context':
                context = current_persona.get_context_length()
                response = f"{persona_name} currently looks back {context} previous messages for context."
                return response
            elif keyword == 'tokens':
                token_limit = current_persona.get_response_token_limit()
                response = f"{persona_name} is limited to {token_limit} response tokens."
                return response

        # Set config
        elif command == 'set':
            keyword = args[0]

            if keyword == 'prompt':
                prompt = ' '.join(args[1:])
                current_persona.set_prompt(prompt)
                print(f"Prompt set for '{persona_name}'.")
                self.save_personas_to_file()
                print(f"Updated save for '{persona_name}'.")
                message = DEFAULT_WELCOME_REQUEST
                response = self.generate_response(persona_name, message)
                return response
            # sets prompt to the default rude concierge derpr persona
            if keyword == 'default_prompt':
                prompt = DEFAULT_PERSONA
                current_persona.set_prompt(prompt)
                print(f"Prompt set for '{persona_name}'.")
                self.save_personas_to_file()
                message = DEFAULT_WELCOME_REQUEST
                response = self.generate_response(persona_name, message)
                return response
            elif keyword == 'model':
                model_name = args[1]
                if self.check_model_available(model_name):
                    current_persona.set_model(model_name)
                    return f"Model set to '{model_name}'."
                else:
                    return f"Model '{model_name}' does not exist. Currently available models are: {self.models_available}"
            elif keyword == 'tokens':
                token_limit = args[1]
                current_persona.set_response_token_limit(token_limit)
                return f"Set token limit: '{token_limit}' response tokens."
            elif keyword == 'context':
                context_limit = args[1]
                current_persona.set_context_length(context_limit)
                return f"Set context_limit for {persona_name}, now reading '{context_limit}' previous messages."

        # dumps a reconstruction of all raw fields sent to model for last completion request
        elif command == 'dump_last':
            # TODO: send this to a special dev channel or thread rather than spam main convo
            # also this hackjob number counting shit is bound to cause problems eventually
            raw_json_response = current_persona.get_last_json()
            last_request = json.dumps(raw_json_response, indent=2, ensure_ascii=False, separators=(',', ':')).replace(
                "```", "").replace('\\n', '\n').replace('\\"', '\"')
            if len(last_request) + 6 > 2000:
                formatted_string = break_and_recombine_string(last_request, 1993, '```')
                return f"{formatted_string}"
            return f"``` {last_request} ```"

        # TODO: add a function to call get_model_list(update=True). Current list is hardcoded in utils.py

        else:
            if DEBUG:
                print("No commands found.")


