import discord

from stuff import api_keys
from src.chat_system import *

# main
# TODO: fix things breaking if name is not first word
# TODO: make 'ignore own message' a flag to allow for persona conversations
# TODO: print persona details cmd ('what personas' extension)
# TODO: derpr should say what personas are available and be like a receptionist (maybe?)
# TODO: short responses are preferred, but token limits usually cut off the message partway
# TODO: allow response to all messages matching bot name
# TODO: set flag/toggle for checking entire message or just first word for name call
# TODO: dynamic context: allow for 'wipe memory' command, need some kind of loop that tracks the beginning of convo
# TODO: dump_last says 200 response tokens, probably wrong so why is it wrong
# TODO: start/stop system to sleep personas
# TODO: personal messages break due to lack of channel or guild name (both?)
# TODO: important: tokenizer request
# TODO:

API_TOKEN = api_keys.discord
DEBUG = 1
GLOBAL_CONTEXT_LIMIT = 10

intents = discord.Intents.all()
# intents.members = True
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

    if DEBUG:
        message_content = message.content
        message_author = message.author
        print(f'{message_author}: {message_content}')

    # Log chat history
    chat_log = "./logs/" + message.guild.name + " #" + message.channel.name + ".txt"
    with open(chat_log, 'a', encoding='utf-8') as file:
        file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    # Don't reply to self
    if message.author.id is not client.user.id:
        # check message for instance of persona name
        # TODO: make name caps-agnostic
        for persona_name, persona in bot.get_persona_list().copy().items():
            persona_mention = f"{persona_name}"
            if DEBUG:
                print('Checking for persona name: ' + persona_name)

            if message_content.lower().startswith(persona_mention):

                # Check message for dev commands
                if DEBUG:
                    print('Found persona name: ' + persona_name)
                    print('Checking for dev commands...')

                # Gather context (message history)
                channel = client.get_channel(message.channel.id)
                history = [f"{message.created_at.strftime('%Y-%m-%d, %H:%M:%S')}, {message.author.name}: {message.content}" async for
                           message in channel.history(limit=GLOBAL_CONTEXT_LIMIT)]
                reversed_history = history[::-1]  # Reverse the history list
                # TODO: text embedding this as a proper json object and series of messages in the api instead of dumping it all as a single block
                context = " \n".join(reversed_history[:-1])

                # Set the bot's activity to indicate operation
                # TODO: set a timeout or better yet a way to detect errors and report that
                activity = discord.Activity(
                    type=discord.ActivityType.streaming,
                    name=persona_name + '...',
                    url='https://www.twitch.tv/discordmakesmedothis'
                )
                await client.change_presence(activity=activity)
                async with message.channel.typing():
                    dev_response = bot.preprocess_message(message)
                    if dev_response is None:
                        context = 'Most recent chat history: \n' + context
                        response = bot.generate_response(persona_name, message, context)
                    elif dev_response == 'new_prompt_set': # todo cut out middleman, get response from preprocess?
                        message.content = 'you are in character as ' + persona_name + '. Welcome to the chat, please describe your typical behavior and disposition for us:'
                        response = bot.generate_response(persona_name, message, context)
                    else:
                        response = dev_response
                    if response:
                        # response = response.replace('\ufeff', '')
                        # Split the response into multiple messages if it exceeds 2000 characters
                        chunks = [response[i:i + 2000] for i in range(0, len(response), 2000)]
                        for chunk in chunks:
                            await channel.send(chunk)
                            print(chunk)

                available_personas = ', '.join(list(bot.get_persona_list().keys()))
                presence_txt = f"as {available_personas} 👀"
                await client.change_presence(
                    activity=discord.Activity(name=presence_txt, type=discord.ActivityType.watching))


if __name__ == "__main__":
    if not os.path.exists("./logs"):
        os.makedirs("./logs")
        print("Logs folder created!")

    bot = ChatSystem()
    # Add some default personas
    bot.load_personas_from_file('personas')

    client.run(API_TOKEN)
