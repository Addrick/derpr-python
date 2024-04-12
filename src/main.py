import logging

from src import fake_discord, global_config, discord_bot
from src.discord_bot import *
from src.global_config import *

import stuff.api_keys

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(message)s',
                    datefmt='[%Y-%m-%d] %H:%M:%S')
logger = logging.getLogger(__name__)


if __name__ == "__main__":
    if not os.path.exists(CHAT_LOG_LOCATION):
        os.makedirs(CHAT_LOG_LOCATION)
        logger.warning("Logs folder created!")

    if DISCORD_BOT:

        # Initiate discord
        client.run(stuff.api_keys.discord, log_level=logging.WARN)
        # Redirect console output to discord for remote monitoring
        # discord_console = discord_bot.DiscordConsoleOutput()
        # sys.stdout = discord_console
        # sys.stderr = discord_console
        # sys.excepthook = discord_console.discord_excepthook


    else:
        from datetime import datetime
        client = fake_discord.Client()
        while 1:
            message = input("Enter a message: ")
            # Create a simulated message object
            current_time = datetime.now().time()
            simulated_message = fake_discord.StrippedMessage(message, author=fake_discord.User(),
                                                             channel=fake_discord.Channel(),
                                                             guild=fake_discord.Guild(),
                                                             timestamp=current_time)

            # Process the message using your existing bot's message processing logic
            on_message(simulated_message)
