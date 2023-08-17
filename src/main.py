import discord
from stuff import api_keys
from src.chat_system import *
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

    if DEBUG:
        message_content = message.content
        message_author = message.author
        print(f'{message_author}: {message_content}')

    # Log chat history
    chat_log = CHAT_LOG_LOCATION + message.guild.name + " #" + message.channel.name + ".txt"
    with open(chat_log, 'a', encoding='utf-8') as file:
        file.write(f'{message.created_at} {message.author.name}: {message.content}\n')

    # Don't reply to self
    if message.author.id is not client.user.id:
        # check message for instance of persona name
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
                # TODO: test embedding this as a separated json object/series of messages in the api instead of dumping it all as a single block in a one 'user content' field
                context = " \n".join(reversed_history[:-1])

                # Set the bot's activity to indicate operation
                # TODO: set a timeout or better yet a way to detect errors and report that
                activity = discord.Activity(
                    type=discord.ActivityType.streaming,
                    name=persona_name + '...',
                    url='https://www.twitch.tv/discordmakesmedothis'
                )
                # Change discord status to 'streaming <persona>...'
                # Discord doesn't let you do a whole lot with bot custom statuses
                await client.change_presence(activity=activity)
                # Send typing flag and begin message processing
                async with message.channel.typing():
                    # Check for dev commands
                    dev_response = bot.preprocess_message(message)
                    if dev_response is None:
                        context = 'recent chat history: \n' + context
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
    bot.load_personas_from_file('personas')

    client.run(api_keys.discord)
