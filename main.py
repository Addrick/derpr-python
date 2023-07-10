from response_handler import *
from Bot import *
import api_keys
import discord

API_TOKEN = api_keys.discord

intents = discord.Intents.all()
# intents.members = True
client = discord.Client(intents=intents)
guild = discord.Guild

derpr = derpr()


@client.event
async def on_ready():
    print('Hello {0.user} !'.format(client))
    await client.change_presence(activity=discord.Activity(name='👀', type=discord.ActivityType.watching))

@client.event
async def on_message(message):
    if message.author.id == client.user.id:
        return
    message_content = message.content
    message_author = message.author
    print(f'New message -> {message_author} said: {message_content}')

    # TODO: grab correct channel from message being replied to, this is the test channel
    channel = client.get_channel(message.channel.id)

    # TODO: evaluate functionality for using the reply function for high-rate messages
    #await.reply or soemthing

    # create response using current bot settings:
    derprs_reply = derpr.respond(message)
    # derprs_reply = generate_response(message_content)
    await channel.send(derprs_reply)

if __name__ == "__main__":
    client.run(API_TOKEN)
