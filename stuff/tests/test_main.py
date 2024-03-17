from unittest import TestCase
from src.message_handler import *
from src.persona import *
from src.chat_system import *
from src.utils import *
from src.main import *
import unittest
from unittest.mock import Mock


class Test(TestCase):
    def setUp(self):
        self.chat_system = ChatSystem()
        self.bot = BotLogic(self.chat_system)
        self.chat_system.load_personas_from_file('test_personas')
        self.chat_system.set_persona_save_file('test_personas')
        self.message = Mock()
        self.maxDiff = None

    # Tests functioning of dev commands and responses
    async def test_handle_help(self):
        self.message.content = 'testr help'
        response = await on_message(self.message)
        self.assertTrue("Talk to a specific persona by starting your message with their name." in response)

    # Tests functioning of API call to testr (should be gpt-3.5-turbo), can fail if chatgpt is feeling sassy
    async def test_handle_testr_test(self):
        self.message.content = 'testr test'
        response = await on_message(self.message)
        self.assertTrue("Success!" in response)

