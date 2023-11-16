import asyncio

import discord

from src import fake_discord, global_config
from stuff import api_keys
from chat_system import *
from global_config import *

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


@client.event
async def on_message(message):
    message_content = message.content
    message_author = message.author
    if DEBUG:
        print(f'{message_author}: {message_content}')

    if LOG_CHAT:
        # Log chat history
        chat_log = CHAT_LOG_LOCATION + message.guild.name + " #" + message.channel.name + ".txt"
        with open(chat_log, 'a', encoding='utf-8') as file:
            file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    # Don't reply to self
    # if client.user is None:
    #     client_id = 0
    # else:
    #     client_id = client.user.id
    if message.author.id is not client.user.id:
        # check message for instance of persona name
        for persona_name, persona in bot.get_persona_list().copy().items():
            persona_mention = f"{persona_name}"
            if DEBUG:
                print('Checking for persona name: ' + persona_name)

            if message_content.lower().startswith(persona_mention):
                # Send typing flag and begin message processing
                # TODO: typing doesn't last more than like 1s
                # TODO: this is broken with offline mode and will break the whole thing probably
                async with message.channel.typing():

                    # Check message for dev commands
                    if DEBUG:
                        print('Found persona name: ' + persona_name)
                        print('Checking for dev commands...')

                    # Gather context and set status for discord
                    if ONLINE:
                        # Gather context (message history) from discord
                        channel = client.get_channel(message.channel.id)
                        history = [
                            f"{message.created_at.strftime('%Y-%m-%d, %H:%M:%S')}, {message.author.name}: {message.content}"
                            async for
                            message in channel.history(limit=global_config.GLOBAL_CONTEXT_LIMIT)]
                        reversed_history = history[::-1]  # Reverse the history list
                        # TODO: test embedding this as a separated json object/series of messages in the api instead of
                        #  dumping it all as a single block in a one 'user content' field
                        #  TODO: persona-specific context
                        #   limits currently have no affect, might be same for token_limit
                        context = " \n".join(reversed_history[:-1])

                        # TODO: set a timeout or better yet a way to detect errors and report that
                        # Change discord status to 'streaming <persona>...'
                        # Discord doesn't let you do a whole lot with bot custom statuses
                        activity = discord.Activity(
                            type=discord.ActivityType.streaming,
                            name=persona_name + '...',
                            url='https://www.twitch.tv/discordmakesmedothis')
                        await client.change_presence(activity=activity)

                    if not ONLINE:
                        import readline

                        # Get the total number of history items
                        history_length = readline.get_current_history_length()

                        if GLOBAL_CONTEXT_LIMIT > history_length:
                            GLOBAL_CONTEXT_LIMIT = history_length
                        # Iterate over the history items and print them
                        for i in range(1, GLOBAL_CONTEXT_LIMIT + 1):
                            history_item = readline.get_history_item(i)
                            context.append(history_item)
                        print('Warning: no context found')
                        context = ''

                    # Check for dev commands
                    dev_response = bot.preprocess_message(message)
                    if dev_response is None:
                        context = 'recent chat history: \n' + context
                        response = bot.generate_response(persona_name, message.content, context)
                    else:
                        response = dev_response
                    if response:
                        if ONLINE:
                            # Split the response into multiple messages if it exceeds 2000 characters
                            chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
                            for chunk in chunks:
                                await channel.send(chunk)
                                print(chunk)

                            available_personas = ', '.join(list(bot.get_persona_list().keys()))
                            presence_txt = f"as {available_personas} 👀"
                            await client.change_presence(
                                activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))
                        else:
                            print(response)


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
        while 1:
            message = input("Enter a message: ")
            # # Create a simulated message object
            current_time = 0  # Todo
            simulated_message = fake_discord.StrippedMessage(message, author=fake_discord.User(),
                                                             channel=fake_discord.Channel(),
                                                             guild=fake_discord.Guild(),
                                                             timestamp=current_time)

            # Process the message using your existing bot's message processing logic
            asyncio.run(on_message(simulated_message))
