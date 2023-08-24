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
    def __init__(self, name='admin', id=1):
        self.name = name
        self.id = id


class Channel:
    def __init__(self, name='local_channel'):
        self.name = name
