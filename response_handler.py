from Bot import *

# let's just do chatgpt for now


def generate_response(message, bots):
    reply = "error"  # if nothing overwrites

    # determine which bot based on name TODO
    # bot = check_bot(message, bots)
    bot = bots[0]
    reply = check_cmds(bot, message)

    return reply


def check_bot(message, bots):
    #TODO: need to store list of bots somewhere and pass/edit them! in derpr class?
    # bots = ["derpr", "knowr"] #these need to refer to Bot objects

    for bot in bots:
        if message.startswith(bot):
            return bot
    pass

def check_cmds(bot, message):

    # first, pull any specific local bot commands
    # help, dump last, !! (or other isolated response cmd), set prompt, set engine, wipe memory, set context length,
    # 'remember'?, fuck off, preset personalities?

    if message.content.startswith("what prompt"):
        prompt = bot.get_prompt()
        # TODO: send message back to discord
        return prompt

    if message.content.startswith('help'):
        # this might show general commands and usages of the bot
        response = "Here are some commands you can use..."

    elif message.content.startswith('dump last query'):
        # this might output the last query sent to the bot
        response = "The last query was:..."

    elif message.content.startswith('!!'):
        # ignores chat context and only sends current message w/prompt
        # TODO: send message w/ context=0 or manually set to '' or soemthing
        print('shit dont work yet')

    elif message.content.startswith('set prompt'):
        # this could change the prompt for conversation with the bot
        new_prompt = message.content[11:]
        bot.set_prompt(new_prompt)

    elif message.content.startswith('set engine'):
        # this might switch the bot's functionality engine
        new_engine = message.content[10:]
        bot.set_engine(new_engine)
        reply = "engine set to " + new_engine
        return reply

    elif message.content.startswith('wipe memory'):
        # this would presumably delete all the memory the bot has stored
        bot.wipe_memory()

    elif message.content.startswith('set context length'):
        # this could be used to adjust the amount of prior messages the bot considers
        new_context_length = int(message.content[18:])
        bot.set_context_length(new_context_length)

    elif message.content.startswith('remember'):
        # this could make the bot remember certain things
        remember_this = message.content[9:]
        bot.remember(remember_this)

    # elif message.content.startswith('fuck off'):
    #     # this could make the bot stop interacting for a time or leave the channel
    #     bot.timeout()

    return
