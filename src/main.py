import asyncio
import datetime
import logging
import os
import sys

import discord
from src import fake_discord, global_config
from src.chat_system import ChatSystem
from src.message_handler import *

# Configure logging
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger(__name__)

intents = discord.Intents.all()
client = discord.Client(intents=intents)
guild = discord.Guild


@client.event
async def on_ready():
    logger.info('Hello {0.user} !'.format(client))
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))


@client.event
async def on_message(message, log_chat=True):
    if ONLINE:
        logger.info(f'{message.author}: {message.content}')

    if log_chat:
        # Log chat history
        chat_log = CHAT_LOG_LOCATION + message.guild.name + " #" + message.channel.name + ".txt"
        with open(chat_log, 'a', encoding='utf-8') as file:
            file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    if message.author.id is not client.user.id:
        # check message for instance of persona name
        for persona_name, persona in bot.get_persona_list().items():
            persona_mention = f"{persona_name}"
            logger.debug('Checking for persona name: ' + persona_name)
            if (message.content.lower().startswith(persona_mention) or
                    message.channel.name.startswith(persona_mention)):
                if message.channel.name.startswith(persona_mention):
                    message.content = persona_mention + " " + message.content
                # Check message for dev commands
                logger.info('Found persona name: ' + persona_name)
                # Gather context and set status for discord
                if ONLINE:
                    async with message.channel.typing():
                        # Gather context (message history) from discord
                        channel = client.get_channel(message.channel.id)
                        context = [
                            f"{msg.created_at.strftime('%Y-%m-%d, %H:%M:%S')}, {msg.author.name}: {msg.content}"
                            async for
                            msg in channel.history(limit=global_config.GLOBAL_CONTEXT_LIMIT)]
                        # Change discord status to 'streaming <persona>...'
                        activity = discord.Activity(
                            type=discord.ActivityType.streaming,
                            name=persona_name + '...',
                            url='https://www.twitch.tv/discordmakesmedothis')
                        await client.change_presence(activity=activity)
                else:
                    context = fake_discord.local_history_reader()

                # Message processing starts
                # Check for dev commands
                dev_response = bot.bot_logic.preprocess_message(message)
                if dev_response is None:
                    response = client.loop.create_task(bot.generate_response(persona_name, message.content, channel, bot, client, context))
                else:
                    if ONLINE:
                        await send_message(channel, dev_response)
                        await reset_discord_status(bot, client)
                    else:
                        fake_discord.local_history_logger(persona_name, dev_response)


async def reset_discord_status(bot, client):
    # Reset discord status to 'watching'
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))


async def send_message(channel, msg):
    # Split the response into multiple messages if it exceeds 2000 characters
    chunks = [msg[i:i + 2000] for i in range(0, len(msg), 2000)]
    for chunk in chunks:
        await channel.send(chunk)


if __name__ == "__main__":
    if not os.path.exists(CHAT_LOG_LOCATION):
        os.makedirs(CHAT_LOG_LOCATION)
        logger.info("Logs folder created!")
    bot = ChatSystem()
    bot.load_personas_from_file(PERSONA_SAVE_FILE)

    if ONLINE:
        # Initiate discord
        client.run(api_keys.discord)
    else:
        client = fake_discord.Client()
        while 1:
            message = input("Enter a message: ")
            # # Create a simulated message object
            current_time = datetime.datetime.now().time()
            simulated_message = fake_discord.StrippedMessage(message, author=fake_discord.User(),
                                                             channel=fake_discord.Channel(),
                                                             guild=fake_discord.Guild(),
                                                             timestamp=current_time)

            # Process the message using your existing bot's message processing logic
            asyncio.run(on_message(simulated_message))
