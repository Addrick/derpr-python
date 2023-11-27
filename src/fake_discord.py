#     StrippedMessage.__init__: Initializes a new StrippedMessage instance with the provided message content, timestamp, channel, guild, and author information.
#     Guild.__init__: Initializes a new Guild instance with an optional name, defaulting to 'local_guild'.
#     User.__init__: Initializes a new User instance with an optional name 'admin' and an id of 1 by default.
#     Channel.__init__: Initializes a new Channel instance with an optional name, defaulting to 'local_channel'.

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

