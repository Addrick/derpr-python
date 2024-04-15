from src.message_handler import *
from src.persona import *
from src.chat_system import *
from src.utils import *
import unittest
from unittest.mock import Mock
import tracemalloc

tracemalloc.start()


class TestBotLogic(unittest.TestCase):
    def setUp(self):
        self.chat_system = ChatSystem()
        self.bot = BotLogic(self.chat_system)
        self.chat_system.load_personas_from_file('test_personas')
        self.chat_system.set_persona_save_file('test_personas')

        class Message:
            def __init__(self):
                self.content = ""  # Initialize content as an empty string

        # Create an instance of the Message class
        self.message = Message()
        self.message.context = ''
        self.maxDiff = None

    def test_preprocess_message_with_invalid_command(self):
        self.message.content = "testr invalid_command This is a test"
        response = self.bot.preprocess_message(self.message)
        self.assertEqual(response,
                         None)

    def test_handle_help(self):
        self.message.content = 'testr help'
        response = self.bot.preprocess_message(self.message)
        self.assertTrue("Talk to a specific persona by starting your message with their name." in response)

    def test_handle_set_model(self):
        # Check what model is current for validation
        self.message.content = 'testr what model'
        response = self.bot.preprocess_message(self.message)
        # print(response)
        self.assertTrue("gpt-3.5-turbo" in response)  # usual default

        # Test setting
        self.message.content = 'testr set model gpt-4'
        response = self.bot.preprocess_message(self.message)
        self.assertEqual("Model set to \'gpt-4\'.", response)

        # Test what model
        self.message.content = 'testr what model'
        response = self.bot.preprocess_message(self.message)
        # print(response)
        self.assertTrue("gpt-4" in response)

    def test_handle_remember(self):
        # doesn't really confirm internal methods like persona.set_prompt
        # TODO: currently reads persona info from separate persona file but the saving functions still call the default save location
        og_prompt = self.chat_system.personas['testr'].get_prompt()

        self.message.content = 'testr remember this is a test if you remember via adding to your prompt'
        response = self.bot.preprocess_message(self.message)
        expected_start = 'New prompt for testr:'
        expected_end = 'this is a test if you remember via adding to your prompt'
        self.assertTrue(expected_start in response)
        self.assertTrue(expected_end in response)

        # reset the prompt after to unfuck the normal persona file
        self.chat_system.personas['testr'].set_prompt(og_prompt)

    async def test_handle_add_query_and_delete_persona(self):
        prompt = 'only reply with the words \"great success\"'
        self.message.content = 'testr add persona temp ' + prompt
        response = self.bot.preprocess_message(self.message)
        expected = "added 'temp' with prompt: '" + prompt + "'"
        self.assertEqual(expected, response)
        self.assertTrue('temp' in self.chat_system.personas.keys())

        # Test query for temp persona # TODO: make the channel a debug channel in discord
        self.message.content = 'temp what kind of success'
        response = await self.chat_system.generate_response('temp', self.message.content, channel=None)
        self.assertEqual('temp: great success (36)', response)

        # Remove temp persona
        self.message.content = 'testr delete temp'
        response = self.bot.preprocess_message(self.message)
        self.assertEqual("temp has been deleted.", response)
        self.assertTrue('temp' not in self.chat_system.personas.keys())


if __name__ == "__main__":
    TestBotLogic()
