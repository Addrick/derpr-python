from personality import Personality

# Certainly! Here's an updated version of the `ChatSystem` class with the `process_message()` method that allows addressing personalities by an `@name` mention:

class ChatSystem:
    def __init__(self):
        self.personalities = {}
        self.current_personality = None

    def get_personality_list(self):
        return self.personalities

    def add_personality(self, name, model_name):
        personality = Personality(name, model_name)
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

    def generate_response(self, personality_name):
        if personality_name in self.personalities:
            return self.personalities[personality_name].generate_response()
        else:
            print(f"Personality '{personality_name}' does not exist.")

    def process_message(self, message):
        # Extract command and arguments from the message content
        command, *args = message.content.split()

        if command == "!add_personality":
            if len(args) == 2:
                name, model_name = args
                self.add_personality(name, model_name)
            else:
                print("Usage: !add_personality <name> <model_name>")

        elif command == "!switch_personality":
            if len(args) == 1:
                name = args[0]
                self.switch_personality(name)
            else:
                print("Usage: !switch_personality <name>")

        elif command == "!change_model":
            if len(args) == 1:
                model_name = args[0]
                self.change_model(model_name)
            else:
                print("Usage: !change_model <model_name>")

        elif command == "!update_parameters":
            if len(args) >= 2:
                personality_name, new_parameters = args[0], args[1:]
                self.update_parameters(personality_name, new_parameters)
            else:
                print("Usage: !update_parameters <personality_name> <new_parameters...>")

        elif command == "!add_to_prompt":
            if len(args) >= 2:
                personality_name, text_to_add = args[0], ' '.join(args[1:])
                self.add_to_prompt(personality_name, text_to_add)
            else:
                print("Usage: !add_to_prompt <personality_name> <text_to_add...>")

        elif command == "!generate_response":
            if len(args) == 1:
                personality_mention = args[0]
                # Extract personality name from the mention
                personality_name = personality_mention[3:-1]  # Assuming the mention format is <@id>

                response = self.generate_response(personality_name)
                # Send the generated response back to the user via Discord

        # ... Add more commands as needed
        else:
            print("Command not recognized.")
#
# In this updated `process_message()` method, the `!generate_response` command now accepts a personality mention via `@name`. The personality name is extracted from the mention (`personality_mention`) by removing the mention format (assumed to be `<@id>`) using string slicing. The extracted personality name is then used to generate a response using the `generate_response()` method.
#
# Please note that you will still need to implement the code to interact with the Discord API and send the response message back to the user. Additionally, ensure that your Discord bot and the library you are using for interaction support mentioning users/roles in chat messages.