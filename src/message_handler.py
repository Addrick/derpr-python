import os
import re
from persona import *
import utils
from global_config import *
from src.utils import break_and_recombine_string

# TODO: make use of the class structure instead of passing everything into a million static functions
class BotLogic:
    def __init__(self, chat_system):
        self.chat_system = chat_system
        self.command_handlers = {
            'help': self._handle_help,
            'update_models': self._handle_update_models,
            'remember': self._handle_remember,
            'save': self._handle_save,
            'add': self._handle_add,
            'delete': self._handle_delete,
            'what': self._handle_what,
            'set': self._handle_set,
            'hello': self._handle_start_conversation,
            'goodbye': self._handle_start_conversation,
            'dump_last': self._handle_dump_last,
            # Add additional commands as needed
        }

    def preprocess_message(self, message):
        if DEBUG:
            print('Checking for dev commands...')
        args = re.split(r'[ ,]', message.content)
        persona_name, command, args = args[0], args[1].lower(), args[2:]
        current_persona = self.chat_system.personas.get(persona_name)
        handler = self.command_handlers.get(command)
        if handler:
            return handler(persona_name, current_persona, message, args)
        if DEBUG:
            print("No commands found.")
        return None

    def _handle_help(self, persona_name, current_persona, message, args):
        # TODO: autogenerate from functions?
        help_msg = "" \
                   "Talk to a specific persona by starting your message with their name. \n \n" \
                   "Currently active personas: \n" + \
                   ', '.join(self.chat_system.personas.keys()) + "\n" \
                                                                 "Bot commands: \n" \
                                                                 "hello (start new conversation), \n" \
                                                                 "goodbye (end conversation), \n" \
                                                                 "remember <+prompt>, \n" \
                                                                 "what prompt/model/personas/context/tokens, \n" \
                                                                 "set prompt/model/context/tokens, \n" \
                                                                 "add <persona>, \n" \
                                                                 "delete <persona>, \n" \
                                                                 "save, \n" \
                                                                 "update_models, \n" \
                                                                 "dump_last"
        return help_msg

    def _handle_remember(self, persona_name, current_persona, message, args):
        if len(args) >= 2:
            text_to_add = ' ' + message.content
            self.add_to_prompt(persona_name, text_to_add)
            response = 'success!' + " just kidding haha doesn't work yet probably never tested it"
            return response

    def _handle_add(self, persona_name, current_persona, message, args):
        new_persona_name = args[0]
        if len(args) <= 2:
            args.append('you are in character as ' + new_persona_name)
        prompt = ' '.join(args[1:])
        self.chat_system.add_persona(new_persona_name,
                                     DEFAULT_MODEL_NAME,
                                     prompt,
                                     context_limit=DEFAULT_CONTEXT_LIMIT,
                                     token_limit=1024)
        response = f"added '{new_persona_name}' with prompt: '{prompt}"
        self.chat_system.save_personas_to_file()
        # message = DEFAULT_WELCOME_REQUEST
        # response = self.chat_system.generate_response(persona_name, message)
        return response

    def _handle_delete(self, persona_name, current_persona, message, args):
        persona_to_delete = args[0]  # handle case where persona does not exist
        self.chat_system.delete_persona(persona_to_delete, save=True)
        response = persona_name + " has been deleted."
        return response

    def _handle_what(self, persona_name, current_persona, message, args):
        if args[0] == 'prompt':
            prompt = current_persona.get_prompt()
            response = f"Prompt for '{persona_name}': {prompt}"
            return response
        elif args[0] == 'model':
            model_name = current_persona.get_model_name()
            response = f"{persona_name} is using {model_name}"
            return response
        elif args[0] == 'models':
            model_names = self.models_available
            formatted_models = json.dumps(model_names, indent=2, ensure_ascii=False, separators=(',', ':')).replace(
                '\"', '')
            response = f"Available model options: {formatted_models}"
            return response
        elif args[0] == 'personas':
            personas = self.get_persona_list()
            response = f"Available personas are: {personas}"
            return response
        elif args[0] == 'context':
            context = current_persona.get_context_length()
            response = f"{persona_name} currently looks back {context} previous messages for context."
            return response
        elif args[0] == 'tokens':
            token_limit = current_persona.get_response_token_limit()
            response = f"{persona_name} is limited to {token_limit} response tokens."
            return response

    def _handle_set(self, persona_name, current_persona, message, args):
        if args[0] == 'prompt':
            prompt = ' '.join(args[1:])
            current_persona.set_prompt(prompt)
            print(f"Prompt set for '{persona_name}'.")
            print(f"Updated save for '{persona_name}'.")
            self.chat_system.save_personas_to_file()
            response = 'Personas saved.'  # flag to save once back in main.py
            return response
        # sets prompt to the default rude concierge derpr persona
        if args[0] == 'default_prompt':
            prompt = DEFAULT_PERSONA
            current_persona.set_prompt(prompt)
            print(f"Prompt set for '{persona_name}'.")
            self.save_personas_to_file()
            message = DEFAULT_WELCOME_REQUEST
            response = self.generate_response(persona_name, message)
            return response
        elif args[0] == 'model':
            model_name = args[1]
            if self.chat_system.check_model_available(model_name):
                current_persona.set_model(model_name)
                return f"Model set to '{model_name}'."
            else:
                return f"Model '{model_name}' does not exist. Currently available models are: {self.models_available}"
        elif args[0] == 'tokens':
            token_limit = args[1]
            current_persona.set_response_token_limit(token_limit)
            return f"Set token limit: '{token_limit}' response tokens."
        elif args[0] == 'context':
            context_limit = args[1]
            current_persona.set_context_length(context_limit)
            return f"Set context_limit for {persona_name}, now reading '{context_limit}' previous messages."

    def _handle_start_conversation(self, persona_name, current_persona, message, args):
        # Set context to 0, increment by 1 each message received
        current_persona.set_context_length(0)
        current_persona.set_conversation_mode(True)
        return f"{persona_name}: Hello! Starting new conversation..."

    def _handle_stop_conversation(self, persona_name, current_persona, message, args):
        # Set context to 0, increment by 1 each message received
        current_persona.set_context_length(DEFAULT_CONTEXT_LIMIT)
        current_persona.set_conversation_mode(True)
        return f"{persona_name}: Goodbye! Resetting context length to {GLOBAL_CONTEXT_LIMIT} previous messages..."

    @staticmethod
    def _handle_dump_last(persona_name, current_persona, message, args):
        # TODO: send this to a special dev channel or thread rather than spam main convo
        # also this hackjob number counting shit is bound to cause problems eventually
        raw_json_response = current_persona.get_last_json()
        last_request = json.dumps(raw_json_response, indent=2, ensure_ascii=False, separators=(',', ':')).replace(
            "```", "").replace('\\n', '\n').replace('\\"', '\"')
        if len(last_request) + 6 > 2000:
            formatted_string = break_and_recombine_string(last_request, 1993, '```')
            return f"{formatted_string}"
        return f"``` {last_request} ```"

    def _handle_save(self, persona_name, current_persona, message, args):
        self.chat_system.save_personas_to_file()
        response = 'Personas saved.'  # flag to save once back in main.py
        return response

    @staticmethod
    def _handle_update_models(persona_name, current_persona, message, args):
        utils.get_model_list(update=True)
        response = 'updated models'
        return response
