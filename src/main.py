import logging
import os
import sys
from datetime import datetime

from src import fake_discord, global_config
from src.chat_system import ChatSystem
from src.discord_bot import client, on_message, on_ready
from src.global_config import *

import stuff.api_keys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    if not os.path.exists(CHAT_LOG_LOCATION):
        os.makedirs(CHAT_LOG_LOCATION)
        logger.info("Logs folder created!")

    if ONLINE:
        # Initiate discord
        client.run(stuff.api_keys.discord)

    else:
        client = fake_discord.Client()
        while 1:
            message = input("Enter a message: ")
            # Create a simulated message object
            current_time = datetime.datetime.now().time()
            simulated_message = fake_discord.StrippedMessage(message, author=fake_discord.User(),
                                                             channel=fake_discord.Channel(),
                                                             guild=fake_discord.Guild(),
                                                             timestamp=current_time)

            # Process the message using your existing bot's message processing logic
            on_message(simulated_message)