from personality import Personality

DEBUG = 1

# ChatSystem
# Maintains personalities, responsible for executing dev commands
class ChatSystem:
    def __init__(self):
        self.personalities = {}
        self.current_personality = None

    def get_personality_list(self):
        return self.personalities

    def add_personality(self, name, model_name, prompt):
        personality = Personality(name, model_name, prompt)
        self.personalities[name] = personality

    def switch_personality(self, name):
        if name in self.personalities:
            self.current_personality = self.personalities[name]
        else:
            print(f"Personality '{name}' does not exist.")

    def change_model(self, model_name):
        if self.current_personality:
            self.current_personality.change_model(model_name)
        else:
            print("No current personality. Please switch to a personality first.")

    def update_parameters(self, personality_name, new_parameters):
        if personality_name in self.personalities:
            self.personalities[personality_name].update_parameters(new_parameters)
        else:
            print(f"Personality '{personality_name}' does not exist.")

    def add_to_prompt(self, personality_name, text_to_add):
        if personality_name in self.personalities:
            self.personalities[personality_name].add_to_prompt(text_to_add)
        else:
            print(f"Personality '{personality_name}' does not exist.")

    def generate_response(self, personality_name, message, context):
        if personality_name in self.personalities:
            return self.personalities[personality_name].generate_response(message, context)
        else:
            print(f"Personality '{personality_name}' does not exist.")

    # Checks for keywords at the start of a message, reroutes to internal program settings
    # Returns True if dev command is executed, used to skip chat request in main.py loop
    # Commands use the format `derpr <command> <arguments...>`. For example:
    #
    # - To add a personality: `derpr add personality <name> <prompt>`
    # - To change the model: `derpr change model <model_name>` TODO: fuckit-style guessing for close matches
    # - To update parameters: `derpr update parameters <personality_name> <new_parameters...>` TODO:
    # - To add to the prompt: `derpr set prompt <personality_name> <prompt>`
    #
    # TODO: stop message processing after this, or do something else (ie 'describe yourself')
    def preprocess_message(self, message):
        # Extract the command and arguments from the message content
        personality_name = message.content.split()[0]
        command, *args = message.content.split()[1:]

        # Appends the message to end of prompt
        if command == 'remember':
            if len(args) >= 2:
                text_to_add = ' ' + message.content
                self.add_to_prompt(personality_name, text_to_add)
                return 'implement me'
            else:
                print("Usage: set <keyword> <arguments...>")

        if command == 'what':
            keyword = args[0]

            if keyword == 'prompt':

                if personality_name in self.personalities:
                    personality = self.personalities[personality_name]
                    prompt = personality.get_prompt()
                    response = f"Prompt for '{personality_name}': {prompt}"
                    return response

                else:
                    print(f"Personality '{personality_name}' does not exist.")
            else:
                print("Usage: what <keyword> <arguments...>")

        elif command == 'change':
            if len(args) == 1 and args[0] == 'model':
                model_name = args[1]
                self.change_model(model_name)
                return 'implement me'
            else:
                print("Usage: change model <model_name>")

        elif command == 'update':
            if len(args) >= 2 and args[0] == 'parameters':
                personality_name, new_parameters = args[1], args[2:]
                self.update_parameters(personality_name, new_parameters)
            else:
                print("Usage: update parameters <personality_name> <new_parameters...>")

        elif command == 'add':
            if len(args) >= 2 and args[0] == 'personality':
                name, prompt = args[1], args[2]
                self.add_personality(name, prompt)
                return 'implement me'
            else:
                print("Usage: add personality <name> <prompt>")

        # ... Add more commands as needed
        else:
            if DEBUG:
                print("No commands found.")
