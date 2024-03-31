import asyncio
import datetime
from contextlib import redirect_stdout

import discord
from discord.ext import commands

from src import fake_discord, global_config
from src.chat_system import ChatSystem
from src.message_handler import *

intents = discord.Intents.all()
client = discord.Client(intents=intents)
guild = discord.Guild

bot = ChatSystem()
bot.load_personas_from_file(PERSONA_SAVE_FILE)


@client.event
async def on_ready():
    logging.info('Hello {0.user} !'.format(client))
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))


@client.event
async def on_command_error(ctx, error):
    if isinstance(error):
        await ctx.send("Something broke. ¯\_(ツ)_/¯")


@client.event
async def on_message(message, log_chat=True):
    # message.breakstuff
    if DISCORD_BOT:
        logging.info(f'{message.author}: {message.content}')

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
                logging.info('Found persona name: ' + persona_name)
                # Gather context and set status for discord
                if DISCORD_BOT:
                    async with message.channel.typing():
                        # Gather context (message history) from discord
                        # TODO: Need to flag and ignore dev commands as well as bot responses to them.
                        #  Can maybe send dev response as a reply or thread to dev command and ignore both more easily
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
                    response = client.loop.create_task(
                        bot.generate_response(persona_name, message.content, channel, bot, client, context))
                else:
                    if DISCORD_BOT:
                        await send_message(channel, dev_response)
                        # await send_message(channel, 'fack')
                        await reset_discord_status()
                    else:
                        fake_discord.local_history_logger(persona_name, dev_response)
                    if dev_response == f'App restarting...':
                        restart_app()
                    if dev_response == f'App stopping...':
                        stop_app()


import io
import sys


class DiscordOutput:
    def __init__(self, channel):
        self.channel = channel
        self.buffer = io.StringIO()

    def write(self, msg):
        self.buffer.write(msg)

    def flush(self):
        output = self.buffer.getvalue()
        chunks = [output[i:i + 2000] for i in range(0, len(output), 2000)]
        for chunk in chunks:
            self.channel.send(chunk)
        self.buffer.close()


async def send_to_discord(channel, func):
    output = DiscordOutput(channel)
    sys.stdout = output
    func()
    sys.stdout = sys.__stdout__


async def send_message_to_discord_instead():
    with io.StringIO() as buf, redirect_stdout(buf):
        print('it now prints to Discord')
        await send_to_discord(1222358674127982622, lambda: print(buf.getvalue()))


# Usage

async def reset_discord_status():
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
