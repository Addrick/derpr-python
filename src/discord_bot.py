import asyncio
import datetime
import logging
import re
from contextlib import redirect_stdout

import discord
from aiohttp import ClientConnectorError
from discord import HTTPException
from discord.ext import commands
from src import fake_discord, global_config, message_handler, utils
from src.chat_system import ChatSystem
from src.global_config import *
from src.message_handler import BotLogic

intents = discord.Intents.all()
client = discord.Client(intents=intents)
guild = discord.Guild

bot = ChatSystem()
bot.load_personas_from_file(PERSONA_SAVE_FILE)

debug_channel = client.get_channel(1222358674127982622)


@client.event
async def on_ready():
    logger = logging.getLogger()
    if global_config.DISCORD_LOGGER:
        logger.addHandler(DiscordLogHandler())
    logging.info('Hello {0.user} !'.format(client))
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))


@client.event
async def on_message(message, log_chat=True):
    # ignored
    if message.channel.id == 1222358674127982622:
        return

    logging.debug(f'{message.author}: {message.content}')

    if log_chat:
        # Log chat history
        chat_log = CHAT_LOG_LOCATION + message.guild.name + " #" + message.channel.name + ".txt"
        with open(chat_log, 'a', encoding='utf-8') as file:
            file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    if message.author.id is not client.user.id:
        # check message for instance of persona name
        for persona_name, persona in bot.get_persona_list().items():
            persona_mention = f"{persona_name}"
            logging.debug('Checking for persona name: ' + persona_name)
            if (message.content.lower().startswith(persona_mention) or
                    message.channel.name.startswith(persona_mention)):
                if message.channel.name.startswith(persona_mention):
                    message.content = persona_mention + " " + message.content
                # Check message for dev commands
                logging.debug('Found persona name: ' + persona_name)
                # Gather context and set status for discord
                if DISCORD_BOT:
                    async with message.channel.typing():
                        # Gather context (message history) from discord
                        # Pulls a list of length GLOBAL_CONTEXT_LIMIT, is pruned later
                        # Formats each message to put it into the state that preprocess_message expects, with persona name first
                        # If preprocess_message with check_only=True returns True, the message is skipped as it is identified as a dev command
                        # If a message begins with derpr: <persona_name> ``` the message is considered a dev message response and also skipped
                        channel = client.get_channel(message.channel.id)
                        context = []
                        history = channel.history(before=message, limit=global_config.GLOBAL_CONTEXT_LIMIT)
                        async for msg in history:
                            if msg.author is not client.user.id and msg.channel.name.startswith(persona_mention):
                                msg.content = persona_mention + " " + msg.content
                            if bot.bot_logic.preprocess_message(msg, check_only=True) or msg.content.startswith('derpr: ' + persona_mention + ': ```'):
                                continue
                            else:
                                context.append(f"{msg.created_at.strftime('%Y-%m-%d, %H:%M:%S')}, {msg.author.name}: {msg.content}")
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
                    response = client.loop.create_task(
                        bot.generate_response(persona_name, message.content, channel, bot, client, context))
                else:
                    if DISCORD_BOT:
                        await send_dev_message(channel, dev_response)
                        # await send_message(channel, 'fack')
                        await reset_discord_status()
                    else:
                        fake_discord.local_history_logger(persona_name, dev_response)
                    if dev_response == f'App restarting...':
                        restart_app()
                    if dev_response == f'App stopping...':
                        stop_app()


class DiscordConsoleOutput:
    def __init__(self):
        pass

    def write(self, msg):
        asyncio.ensure_future(send_dev_message(debug_channel, msg))

    def flush(self):
        pass

    def discord_excepthook(self, type, value, traceback):
        if issubclass(type, ConnectionError):
            asyncio.create_task(on_disconnect())
        else:
            error_report = f'Error logged: \n {type} \n {value} \n {traceback}'
            asyncio.create_task(send_dev_message(debug_channel, error_report))


def on_disconnect():
    if global_config.DISCORD_DISCONNECT_TIME is None:
        global_config.DISCORD_DISCONNECT_TIME = datetime.datetime.now()
    else:
        pass


# @client.event
# async def on_connect():
#     if global_config.DISCORD_DISCONNECT_TIME is not None:
#         time_offline = datetime.datetime.now() - global_config.DISCORD_DISCONNECT_TIME
#         global_config.DISCORD_DISCONNECT_TIME = None
#         offline_message = f"The bot was offline for: {time_offline}"
#         asyncio.create_task(debug_channel.send(offline_message))


class DiscordLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.debug_channel = client.get_channel(1222358674127982622)

    def emit(self, record):
        log_message = self.format(record)
        if 'ClientConnectorError' in log_message or 'We are being rate limited.' in log_message:
            return  # Do not send message if log_message contains discord connection/rate limit errors
        asyncio.create_task(send_dev_message(self.debug_channel, log_message))


# Reset discord name and status to default
async def reset_discord_status():
    # Set name to derpr
    await client.user.edit(username='derpr')
    # Reset discord status to 'watching'
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))


async def send_dev_message(channel, msg: str):
    # Escape discord code formatting instances
    # msg.replace("```", "\```")
    formatted_msg = re.sub('```','`\u200B``', msg)
    # Split the response into multiple messages if it exceeds 2000 characters
    chunks = utils.split_string_by_limit(formatted_msg, DISCORD_CHAR_LIMIT)
    for chunk in chunks:
        try:
            await channel.send(f"```{chunk}```")
        except HTTPException as e:
            # TODO: set up fallback logging
            # print(f"An error occurred: {e}")
            pass


async def send_message(channel, msg):
    # Set name to currently speaking persona
    # await client.user.edit(username=persona_name) #  This doesn't work as name changes are rate limited to 2/hour

    # Split the response into multiple messages if it exceeds 2000 characters
    # chunks = [msg[i:i + 2000] for i in range(0, len(msg), 2000)]
    chunks = utils.split_string_by_limit(msg, DISCORD_CHAR_LIMIT)
    for chunk in chunks:
        await channel.send(f"{chunk}")
