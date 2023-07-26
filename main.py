import discord

import api_keys
from Bot import *
from chat_system import ChatSystem
import personality

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
        file.write(f'{message.author.name}): {message.content}\n')

    if message.author.id == client.user.id:
        return

    message_content = message.content
    message_author = message.author
    print(f'New message -> {message_author} said: {message_content}')
    channel = client.get_channel(message.channel.id)

    # TODO: Evaluate functionality for using the reply function instead of just sending a message

    # Create response using the current bot settings
    response = ""
    for personality_name, personality in bot.get_personality_list().items():
        personality_mention = f"{personality_name}"
        if personality_mention in message_content:
            if DEBUG:
                print('checking for personality name... ' + personality_name)
            response = bot.generate_response(personality_name)
            break

    if response:
        #TODO: add logic to route message back to correct server/channel
        await channel.send(response)
        print(response)

if __name__ == "__main__":
    bot = ChatSystem()
    # Add some default personalities
    bot.add_personality("testr", "default_model")
    # ChatSystem.add_personality("personality1", "model1")
    # ChatSystem.add_personality("personality2", "model2")

    client.run(API_TOKEN)
