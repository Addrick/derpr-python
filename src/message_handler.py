import logging
import re

from src.engine import *
from src.persona import *


class BotLogic:
    def __init__(self, chat_system):
        self.persona_name = None
        self.message = None
        self.chat_system = chat_system
        self.current_persona = None
        self.koboldcpp_thread = None
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
            'start_koboldcpp': self._handle_start_koboldcpp,
            'stop_koboldcpp': self._handle_stop_koboldcpp,
            'check_koboldcpp': self._handle_check_koboldcpp,
            # Add additional commands as needed
        }

    def preprocess_message(self, message):
        logging.debug('Checking for dev commands...')
        self.message = message
        self.args = re.split(r'[ ]', message.content)
        # try:
        self.persona_name, command, self.args = self.args[0].lower(), self.args[1].lower(), self.args[2:]
        # except IndexError as e:
        #     self.persona_name, command = self.args[0].lower(), self.args[1].lower()
        self.current_persona = self.chat_system.personas.get(self.persona_name)
        handler = self.command_handlers.get(command)
        if handler:
            return handler()
        logging.info("No dev commands found.")
        return None

    def _handle_help(self):
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
                                                                 "start_koboldcpp, \n" \
                                                                 "stop_koboldcpp, \n" \
                                                                 "check_koboldcpp, \n" \
                                                                 "dump_last"
        return help_msg

    def _handle_remember(self):
        if len(self.args) >= 2:
            text_to_add = ' '.join(self.args[0:])
            new_prompt = self.current_persona.get_prompt() + ' ' + text_to_add
            self.current_persona.set_prompt(new_prompt)
            response = f'New prompt for {self.persona_name}: {self.current_persona.get_prompt()}'
            return response

    def _handle_add(self):
        new_persona_name = self.args[1]
        if len(self.args) <= 2:
            self.args.append('you are in character as ' + new_persona_name)
        prompt = ' '.join(self.args[2:])
        self.chat_system.add_persona(new_persona_name,
                                     DEFAULT_MODEL_NAME,
                                     prompt,
                                     context_limit=DEFAULT_CONTEXT_LIMIT,
                                     token_limit=1024,
                                     save_new=True)
        response = f"added '{new_persona_name}' with prompt: '{prompt}'"
        return response

    def _handle_delete(self):
        persona_to_delete = self.args[0]
        self.chat_system.delete_persona(persona_to_delete, save=True)
        response = persona_to_delete + " has been deleted."
        return response

    def _handle_what(self):
        if self.args[0] == 'prompt':
            prompt = self.current_persona.get_prompt()
            response = f"Prompt for '{self.persona_name}': {prompt}"
            return response
        elif self.args[0] == 'model':
            model_name = self.current_persona.get_model_name()
            response = f"{self.persona_name} is using {model_name}"
            return response
        elif self.args[0] == 'models':
            model_names = self.chat_system.check_model_available
            formatted_models = json.dumps(model_names, indent=2, ensure_ascii=False, separators=(',', ':')).replace(
                '\"', '')
            response = f"Available model options: {formatted_models}"
            return response
        elif self.args[0] == 'personas':
            personas = self.chat_system.get_persona_list()
            response = f"Available personas are: {personas}"
            return response
        elif self.args[0] == 'context':
            context = self.current_persona.get_context_length()
            response = f"{self.persona_name} currently looks back {context} previous messages for context."
            return response
        elif self.args[0] == 'tokens':
            token_limit = self.current_persona.get_response_token_limit()
            response = f"{self.persona_name} is limited to {token_limit} response tokens."
            return response

    def _handle_set(self):
        if self.args[0] == 'prompt':
            prompt = ' '.join(self.args[1:])
            self.current_persona.set_prompt(prompt)
            logging.info(f"Prompt set for '{self.persona_name}'.")
            logging.info(f"Updated save for '{self.persona_name}'.")
            self.chat_system.save_personas_to_file()
            response = 'Personas saved.'
            return response
        if self.args[0] == 'default_prompt':
            prompt = DEFAULT_PERSONA
            self.current_persona.set_prompt(prompt)
            logging.info(f"Prompt set for '{self.persona_name}'.")
            self.chat_system.save_personas_to_file()
            message = DEFAULT_WELCOME_REQUEST
            response = self.current_persona.generate_response(self.persona_name, message)
            return response
        elif self.args[0] == 'model':
            model_name = self.args[1]
            if self.chat_system.check_model_available(model_name):
                self.current_persona.set_model(model_name)
                return f"Model set to '{model_name}'."
            else:
                return f"Model '{model_name}' does not exist. Currently available models are: {self.chat_system.models_available}"
        elif self.args[0] == 'tokens':
            token_limit = self.args[1]
            self.current_persona.set_response_token_limit(token_limit)
            return f"Set token limit: '{token_limit}' response tokens."
        elif self.args[0] == 'context':
            context_limit = self.args[1]
            self.current_persona.set_context_length(context_limit)
            return f"Set context_limit for {self.persona_name}, now reading '{context_limit}' previous messages."

    def _handle_start_conversation(self):
        self.current_persona.set_context_length(0)
        self.current_persona.set_conversation_mode(True)
        return f"{self.persona_name}: Hello! Starting new conversation..."

    def _handle_check_koboldcpp(self):
        logging.info('checking if koboldcpp is running...')
        if self.koboldcpp_thread is not None:
            return self.koboldcpp_thread.isAlive()

    def _handle_stop_koboldcpp(self):
        logging.info('attempting to stop koboldcpp...')
        if self.koboldcpp_thread is not None:
            self.koboldcpp_thread.do_run = False
            self.koboldcpp_thread.join()
            return "koboldcpp process stopped"

    def _handle_start_koboldcpp(self):
        import threading
        self.koboldcpp_thread = threading.Thread(target=launch_koboldcpp)
        self.koboldcpp_thread.start()

        return "Starting koboldcpp..."

    def _handle_stop_conversation(self):
        self.current_persona.set_context_length(DEFAULT_CONTEXT_LIMIT)
        self.current_persona.set_conversation_mode(True)
        return f"{self.persona_name}: Goodbye! Resetting context length to {GLOBAL_CONTEXT_LIMIT} previous messages..."

    def _handle_dump_last(self):
        raw_json_response = self.current_persona.get_last_json()
        last_request = json.dumps(raw_json_response, indent=2, ensure_ascii=False, separators=(',', ':')).replace(
            "```", "").replace('\\n', '\n').replace('\\"', '\"')
        if len(last_request) + 6 > 2000:
            from src.utils import break_and_recombine_string
            formatted_string = break_and_recombine_string(last_request, 1993, '```')
            return f"{formatted_string}"
        return f"``` {last_request} ```"

    def _handle_save(self):
        self.chat_system.save_personas_to_file()
        response = 'Personas saved.'
        return response

    def _handle_update_models(self):
        from src.utils import get_model_list
        get_model_list(update=True)
        reply = f"Model names currently available: {self.chat_system.models_available}"
        return reply