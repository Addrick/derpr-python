# import asynctest
# from src.message_handler import *
# from src.chat_system import *
# from src.main import *


# TODO: these don't work, need to recreate more parts of the discord library or implement using fake_discord.py
# class TestMain(asynctest.TestCase):
#     async def setUp(self):
#         self.chat_system = ChatSystem()
#         self.bot = BotLogic(self.chat_system)
#         self.chat_system.load_personas_from_file('test_personas')
#         self.chat_system.set_persona_save_file('test_personas')
#         self.message = asynctest.Mock()
#         self.client = asynctest.Mock()
#         self.maxDiff = None
#         self.message.guild.name = 'test'
#         self.message.channel.name = 'test'
#         self.message.author.id = 'test'
#         self.client.user.id = 'test'
#
#         src.global_config.LOG_CHAT = False
#
#     async def test_handle_help(self):
#         self.message.content = 'testr help'
#         response = await on_message(self.message, log_chat=False)
#         self.assertTrue("Talk to a specific persona by starting your message with their name." in response)
#
#     async def test_handle_testr_test(self):
#         self.message.content = 'testr test'
#         response = await on_message(self.message, log_chat=False)
#         self.assertTrue("Success!" in response)
#
#
# if __name__ == '__main__':
#     asynctest.TestMain()
