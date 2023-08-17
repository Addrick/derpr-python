import os

from persona import *
import models

DEBUG = 1


# ChatSystem
# Maintains personas, responsible for executing dev commands
class ChatSystem:
    def __init__(self):
        self.personas = {}
        self.models_available = []
        self.check_models_available()

    def load_personas_from_file(self, file_path):
        if not os.path.exists(file_path):
            print(f"File '{file_path}' does not exist.")
            return

        with open(file_path, "r") as file:
            persona_data = json.load(file)
            for persona in persona_data['personas']:
                try:
                    # for persona_data in personas_data:
                    name = persona["name"]
                    model_name = persona["model_name"]
                    prompt = persona["prompt"]
                    context_limit = persona["context_limit"]
                    token_limit = persona["token_limit"]
                    if hasattr(models, model_name):
                        # Instantiate the model class based on the model name
                        model_class = getattr(models, model_name)
                        f"Model set to '{model_name}'."
                    else:
                        f"Model '{model_name}' does not exist, using GPT3Turbo."
                        model_class = models.Gpt3Turbo()
                    self.add_persona(name, model_class, prompt, context_limit, token_limit)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON file '{file_path}': {str(e)}")
                    return

    def get_persona_list(self):
        return self.personas

    def add_persona(self, name, model_name, prompt, context_limit, token_limit):
        persona = Persona(name, model_name, prompt, context_limit, token_limit)
        self.personas[name] = persona
        # add to persona bank file
        self.serialize('personas')

    def serialize(self, file_path):
        persona_dict = self.to_dict()

        with open(file_path, "w") as file:
            file.write(json.dumps(persona_dict))

    def to_dict(self):
        persona_dict = {'personas': [] }
        for persona_name, persona in self.personas.items():
            persona_json = {
            "name": persona.name,
            "prompt": persona.prompt,
            "model_name": persona.model.model_name,
            "context_limit": persona.context_length,
            "token_limit": persona.response_token_limit,
            }
            persona_dict['personas'].append(persona_json)
        return persona_dict

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
        # clean_context = context.replace("\n", " ")
        if persona_name in self.personas:
            return f"{persona_name}: {self.personas[persona_name].generate_response(message, context, )}"
        else:
            print(f"persona '{persona_name}' does not exist.")

    def check_models_available(self):
        self.models_available = [model.lower() for model in models.get_available_chat_models()]

    # TODO: finish: remember, find other commands to use
    def preprocess_message(self, message):
        # Extract the command and arguments from the message content
        persona_name = message.content.split()[0].lower()
        command, *args = message.content.split()[1:]
        current_persona = self.personas[persona_name]

        if command == 'help':
            help_msg = "remember <+prompt>, " \
                       "what prompt/model/personas/context/token_limit, " \
                       "set prompt/model/context_limit/token_limit, " \
                       "dump last"
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

            # TODO: make this easier to remember/use, not repeat bot name
            if keyword == 'persona':
                persona_name = args[1]
                prompt = ' '.join(args[1:])
                self.add_persona(persona_name, models.Gpt3Turbo(), prompt, context_limit=4, token_limit=256)
                response = f"added '{persona_name}': {prompt}"
                return response

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
                model_names = models.get_available_chat_models()
                response = f"Available model options are: {model_names}"
                return response
            elif keyword == 'personas':
                personas = self.get_persona_list()
                response = f"Available personas are: {personas}"
                return response
            elif keyword == 'context':
                context = current_persona.get_context_length()
                response = f"{persona_name} currently looks back {context} previous messages for context."
                return response
            elif keyword == 'token_limit':
                token_limit = current_persona.get_response_token_limit()
                response = f"{persona_name} is limited to {token_limit} response tokens."
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
                existing_context = current_persona.get_context_length()
                self.add_persona(persona_name, models.Gpt3Turbo(), existing_prompt, existing_context,
                                 token_limit=token_limit)
                return f"Set token limit: '{token_limit}' response tokens."
            elif keyword == 'context':
                context_limit = args[1]
                return f"Set context_limit for {persona_name}, now reading '{context_limit}' previous messages."

        elif command == 'dump_last':
            # TODO: send this to a special dev channel or thread rather than spam main convo
            # also this hackjob number counting shit is bound to cause problems eventually
            raw_json_response = current_persona.get_last_json()
            last_request = json.dumps(raw_json_response, indent=2, ensure_ascii=False, separators=(',', ':')).replace("```", "").replace('\\n', '\n').replace('\\"', '\"')
            if len(last_request) + 6 > 2000:
                formatted_string = break_and_recombine_string(last_request, 1993, '```')
                return f"{formatted_string}"
            return f"``` {last_request} ```"

        else:
            if DEBUG:
                print("No commands found.")

def break_and_recombine_string(input_string, substring_length, bumper_string):
    substrings = [input_string[i:i+substring_length] for i in range(0, len(input_string), substring_length)]
    formatted_substrings = [bumper_string + substring + bumper_string for substring in substrings]
    combined_string = ' '.join(formatted_substrings)
    return combined_string
