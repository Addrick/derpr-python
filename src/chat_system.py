import os
import logging
import discord.activity

from src import discord_bot
from src.message_handler import *
from src.persona import *
from src.utils import *


# ChatSystem
# Maintains personas, queries the engine system for responses, executes dev commands
# It handles loading and saving personas from/to a file, adding and deleting personas,
# and generating responses using these personas.
class ChatSystem:
    def __init__(self):
        self.persona_save_file = PERSONA_SAVE_FILE
        self.personas = {}
        self.models_available = get_model_list()
        self.bot_logic = BotLogic(self)  # Pass the instance of ChatSystem to BotLogic

    def set_persona_save_file(self, new_path):
        """Update the location of the persona save file."""
        self.persona_save_file = new_path
        logging.info('persona save file location updated to ' + new_path)

    def load_personas_from_file(self, file_path):
        """Load personas from a JSON-formatted file."""
        if not os.path.exists(file_path):
            logging.warning(f"File '{file_path}' does not exist.")
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
                    logging.info(f"Error decoding JSON file '{file_path}': {str(e)}")
                    return

    def get_persona_list(self):
        """Return the dictionary of personas."""
        return self.personas

    def add_persona(self, name, model_name, prompt, context_limit, token_limit, save_new=True):
        """Add a new persona to the system."""
        persona = Persona(name, model_name, prompt, context_limit, token_limit)
        self.personas[name] = persona
        # add to persona bank file
        if save_new:
            self.save_personas_to_file()

    def delete_persona(self, name, save=False):
        """Delete a persona from the system."""
        del self.personas[name]
        if save:
            self.save_personas_to_file()

    def save_personas_to_file(self):
        """Save all personas to the JSON file."""
        # Check if the file exists
        if not os.path.exists(PERSONA_SAVE_FILE):
            # Create the file
            with open(PERSONA_SAVE_FILE, 'w') as file:
                pass  # Just create an empty file
            print(f"File '{PERSONA_SAVE_FILE}' created.")
        with open(PERSONA_SAVE_FILE, 'r') as file:
            save_data = json.load(file)
        persona_dict = self.to_dict()
        save_data['personas'] = persona_dict
        with open(self.persona_save_file, 'w') as file:
            json.dump(save_data, file, indent=4)
        logging.info(f"Updated persona save.")

    def to_dict(self):
        """Convert personas to a list of dictionaries for JSON serialization."""
        persona_dict = []
        for persona_name, persona in self.personas.items():
            persona_json = {
                "name": persona.persona_name,
                "prompt": persona.prompt,
                "model_name": persona.model.model_name,
                "context_limit": persona.context_length,
                "token_limit": persona.response_token_limit,
            }
            persona_dict.append(persona_json)
        return persona_dict

    def add_to_prompt(self, persona_name, text_to_add):
        """Add text to a persona's prompt."""
        if persona_name in self.personas:
            self.personas[persona_name].add_to_prompt(text_to_add)
        else:
            logging.info(f"Failed to add to prompt, persona '{persona_name}' does not exist.")

    # Send 'message' to 'channel' if discord or 'team' if teams TODO: implement teams routing
    async def generate_response(self, persona_name, message, channel, team, bot, client, context=''):
        """Generate a response using the specified persona and message channel."""
        if persona_name in self.personas:
            persona = self.personas[persona_name]
            async with channel.typing():
                reply = await persona.generate_response(message, context)
            if persona_name != 'derpr':
                reply = f"{persona_name}: {reply}"

            if channel is not None:
                # Split the response into multiple messages if it exceeds chunk_size number of characters
                await discord_bot.send_message(channel, reply)
                # Reset discord status to 'watching'
                await discord_bot.reset_discord_status()
        else:
            logging.warning(f"persona '{persona_name}' does not exist.")

    def check_models_available(self):
        """Update the list of available models."""
        self.models_available = get_model_list()

    def check_model_available(self, model_to_check):
        """Check if a specific model is available."""
        lowest_order_items = []
        for value in self.models_available.values():
            if isinstance(value, list):
                lowest_order_items.extend(value)
            else:
                lowest_order_items.append(value)

        if model_to_check in lowest_order_items:
            return True
        else:
            logging.info(f"The value '{model_to_check}' is not found.")
            return False