import discord

import api_keys
import chat_system
from chat_system import ChatSystem
import personality
import models

API_TOKEN = api_keys.discord
DEBUG = 1

intents = discord.Intents.all()
# intents.members = True
client = discord.Client(intents=intents)
guild = discord.Guild

# derpr = derpr()


@client.event
async def on_ready():
    print('Hello {0.user} !'.format(client))
    await client.change_presence(activity=discord.Activity(name='👀', type=discord.ActivityType.watching))


@client.event
async def on_message(message):
    # Log chat history
    chat_log = message.guild.name + " #" + message.channel.name + ".txt"
    with open(chat_log, 'a') as file:
        file.write(f'{message.author.name}: {message.content}\n')

    if message.author.id == client.user.id:
        return

    if DEBUG:
        message_content = message.content
        message_author = message.author
        print(f'New message -> {message_author} said: {message_content}')

    # TODO: Evaluate functionality for using the reply function instead of just sending a message

    # Check message for dev commands
    bot.preprocess_message(message)

    # Gather context
    channel = client.get_channel(message.channel.id)
    channel = client.get_channel(message.channel.id)
    # Read the last 10 lines from the history.txt file
    with open(chat_log, "r") as file:
        lines = file.readlines()
        context = "".join(lines[-10:])

    # Create response using the current bot settings
    response = ""
    for personality_name, personality in bot.get_personality_list().items():
        personality_mention = f"{personality_name}"
        if DEBUG:
            print('checking for personality name: ' + personality_name)
        if personality_mention in message_content:
            # TODO: handle multiple personalities in one message
            # TODO: send 'is typing...' status
            # TODO:
            if DEBUG:
                print('found personality name: ' + personality_name)
            response = bot.generate_response(personality_name, message, context)
            break

    if response:
        await channel.send(response)
        print(response)

if __name__ == "__main__":
    bot = ChatSystem()
    # Add some default personalities
    bot.add_personality("testr", models.Gpt3Turbo())
    # ChatSystem.add_personality("personality1", "model1")
    # ChatSystem.add_personality("personality2", "model2")

    client.run(API_TOKEN)
