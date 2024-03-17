import asyncio
import datetime
import logging
import os

import discord
from src import fake_discord, global_config
from src.chat_system import ChatSystem
from src.message_handler import *

intents = discord.Intents.all()
client = discord.Client(intents=intents)
guild = discord.Guild


@client.event
async def on_ready():
    print('Hello {0.user} !'.format(client))
    available_personas = ', '.join(list(bot.get_persona_list().keys()))
    presence_txt = f"as {available_personas} 👀"
    await client.change_presence(
        activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


@client.event
async def on_message(message):
    message_content = message.content
    message_author = message.author
    if DEBUG and ONLINE:
        print(f'{message_author}: {message_content}')

    if LOG_CHAT:
        # Log chat history
        chat_log = CHAT_LOG_LOCATION + message.guild.name + " #" + message.channel.name + ".txt"
        with open(chat_log, 'a', encoding='utf-8') as file:
            file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    if message.author.id is not client.user.id:
        # check message for instance of persona name
        for persona_name, persona in bot.get_persona_list().items():
            persona_mention = f"{persona_name}"
            if DEBUG:
                print('Checking for persona name: ' + persona_name)

            # drop all to lowercase for ease of processing - should not affect llm output
            if message_content.lower().startswith(persona_mention):
                # Send typing flag and begin message processing
                # TODO: typing doesn't last more than like 10s
                # Check message for dev commands
                if DEBUG:
                    print('Found persona name: ' + persona_name)

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

                if not ONLINE:
                    with open('../stuff/logs/local_guild #local_channel.txt', 'r') as file:
                        lines = file.readlines()
                        # Grabs last history_length number of messages from local chat history file and joins them
                        context = '/n'.join(lines[-1 * (GLOBAL_CONTEXT_LIMIT + 1):-1])

                # Check for dev commands
                dev_response = bot.bot_logic.preprocess_message(message)
                if dev_response is None:
                    # thread = threading.Thread(target=bot.generate_response(persona_name, message.content, channel, context), args=(message,))
                    # thread.start()
                    response = client.loop.create_task(bot.generate_response(persona_name, message.content, channel, context))
                else:
                    response = dev_response
                if response:  # TODO:fix
                    if ONLINE:
                        # await send_message(channel, message)
                        # Reset discord status to 'watching'
                        available_personas = ', '.join(list(bot.get_persona_list().keys()))
                        presence_txt = f"as {available_personas} 👀"
                        await client.change_presence(
                            activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))
                    else:
                        fake_discord.local_history_logger(persona_name, response)

# TODO: seems that this is part of some kind of extension to discord.py called discord.ext.commands
# @client.listen()
# async def on_message(msg):
#     print('ok it went')


async def send_message(channel, msg):
    # Split the response into multiple messages if it exceeds 2000 characters
    chunks = [msg[i:i + 2000] for i in range(0, len(msg), 2000)]
    for chunk in chunks:
        await channel.send(chunk)


if __name__ == "__main__":
    if not os.path.exists(CHAT_LOG_LOCATION):
        os.makedirs(CHAT_LOG_LOCATION)
        print("Logs folder created!")
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
