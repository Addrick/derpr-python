#     StrippedMessage.__init__: Initializes a new StrippedMessage instance with the provided message content, timestamp, channel, guild, and author information.
#     Guild.__init__: Initializes a new Guild instance with an optional name, defaulting to 'local_guild'.
#     User.__init__: Initializes a new User instance with an optional name 'admin' and an id of 1 by default.
#     Channel.__init__: Initializes a new Channel instance with an optional name, defaulting to 'local_channel'.
from src.global_config import GLOBAL_CONTEXT_LIMIT


class StrippedMessage:
    def __init__(self, content, timestamp, channel, guild, author):
        self.content = content
        self.created_at = timestamp
        self.channel = channel
        self.guild = guild
        self.author = author


class Guild:
    def __init__(self, name='local_guild'):
        self.name = name


class User:
    def __init__(self, name='local'):
        self.name = name
        self.id = name


class Channel:
    def __init__(self, name='local_channel'):
        self.name = name


class Client:
    def __init__(self, name='local_client'):
        self.id = name
        self.user = User(name=name)


def local_history_reader():
    with open('../stuff/logs/local_guild #local_channel.txt', 'r') as file:
        lines = file.readlines()
        # Grabs last history_length number of messages from local chat history file and joins them
        context = '/n'.join(lines[-1 * (GLOBAL_CONTEXT_LIMIT + 1):-1])


def local_history_logger(persona_name, response):
    import datetime
    with open('../stuff/logs/local_guild #local_channel.txt', 'a', encoding='utf-8') as file:
        current_time = datetime.datetime.now().time()
        response = '\n' + persona_name + ': ' + str(current_time) + ' ' + response

        file.write(response)
