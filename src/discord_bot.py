import asyncio
import datetime
import logging

import discord
from src import local_terminal, global_config
from src.app_manager import restart_app, stop_app
from src.chat_system import ChatSystem
from src.global_config import *
from src.utils.messages import send_dev_message

# Summary:
# This code implements a Discord bot using the discord.py library. The bot manages multiple personas,
# responds to messages, and handles various commands. It includes features like logging, context
# gathering, and dynamic status updates. The bot uses an external ChatSystem for generating responses.

# Declare all discort intents and instantiating Discord client - declaring 'all' intents for simplicity while testing
intents = discord.Intents.all()
client = discord.Client(intents=intents)
guild = discord.Guild

# Import ChatSystem for use of core bot logic
bot = ChatSystem()
# bot.load_personas_from_file(PERSONA_SAVE_FILE)

# Discord channel to dump log messages for remote debugging
debug_channel = client.get_channel(1222358674127982622)


# Connects to discord, sets up logging and sets status to list of available personas
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
    # ignore debug channel
    if message.channel.id == 1222358674127982622:
        return

    logging.debug(f'{message.author}: {message.content}')

    if log_chat:
        # Log chat history to local text file
        chat_log = CHAT_LOG_LOCATION + message.guild.name + " #" + message.channel.name + ".txt"
        with open(chat_log, 'a', encoding='utf-8') as file:
            file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    # check new discord message for instance of persona name
    if message.author.id is not client.user.id:
        # check for persona mention in message
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
                        # Pulls a list of length GLOBAL_CONTEXT_LIMIT, is pruned later based on persona context setting #TODO: can make this more efficient by pulling the persona context limit here
                        # Formats each message to put it into the state that preprocess_message expects, with persona name first
                        # If preprocess_message with check_only=True returns True, the message is skipped as it is identified as a dev command
                        # If a message begins with derpr: <persona_name> ``` the message is considered a dev message response and also skipped
                        channel = client.get_channel(message.channel.id)
                        context = []
                        history = channel.history(before=message, limit=global_config.GLOBAL_CONTEXT_LIMIT)
                        async for msg in history:
                            if msg.author is not client.user.id and msg.channel.name.startswith(persona_mention):
                                msg.content = persona_mention + " " + msg.content
                            is_previous_dev_response = 'derpr: ' + persona_mention + ' `​``' in msg.content  # zero-width space is a hack used in dev commands to escape internal code commenting
                            if bot.bot_logic.preprocess_message(msg, check_only=True) or is_previous_dev_response:
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
                    context = local_terminal.local_history_reader()

                # Message processing starts
                # Check for dev commands
                dev_response = bot.bot_logic.preprocess_message(message)
                if dev_response is None:
                    # If no dev response found, process as a bot request
                    response = client.loop.create_task(
                        bot.generate_response(persona_name, message.content, channel=channel, bot=bot, client=client, context=context))
                else:  # If dev message found, send it now and reset status
                    if DISCORD_BOT:
                        await send_dev_message(channel, dev_response)
                        await reset_discord_status()
                    else:  # local terminal operation if discord_bot=false TODO: move all local logic to its own file
                        local_terminal.local_history_logger(persona_name, dev_response)
                    if dev_response == f'App restarting...':  # hooks to start/stop koboldcpp TODO: move out of discord file
                        restart_app()
                    if dev_response == f'App stopping...':
                        stop_app()

# Module to forward console messages to discord
class DiscordConsoleOutput:
    def __init__(self):
        self.DISCORD_DISCONNECT_TIME = None

    def write(self, msg):
        asyncio.ensure_future(send_dev_message(debug_channel, msg))

    def flush(self):
        pass

    def discord_excepthook(self, type, value, traceback):
        if issubclass(type, ConnectionError):
            asyncio.create_task(self.on_disconnect())
        else:
            error_report = f'Error logged: \n {type} \n {value} \n {traceback}'
            asyncio.create_task(send_dev_message(debug_channel, error_report))

    def on_disconnect(self):  # Disconnects must be handled as a special case so it does not flood the channel on reconnect and cause another disconnect
        if self.DISCORD_DISCONNECT_TIME is None:
            self.DISCORD_DISCONNECT_TIME = datetime.datetime.now()
        else:
            pass


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
    """# Set name to derpr"""
    await client.user.edit(username='derpr')
    # Reset discord status to 'watching'
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))

