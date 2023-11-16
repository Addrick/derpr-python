# derpr todo:

# Features:
# TODO: modify: add option to locate name anywhere in message for reply rather than first word only?
# TODO: modify: make 'ignore own message' a flag to allow for persona conversations (+commands to modify in-chat)
# TODO: print persona details cmd ('what personas' extension?)
# TODO: derpr persona should reset after some length of time or at least on restart. He's the concierge
# TODO: automated test of sorts that queries openAI for basic question and prints response to terminal
# TODO: better logging/errors
# TODO: add temperature customizing commands
# TODO: tokenizer request
# TODO: better persona management: start/stop system to sleep personas
# TODO: add personal messages: currently break due to lack of channel or guild name (both?)
# TODO: add a persona prompt log - keep losing personas and wanting old versions back
# TODO: derpr should say what personas are available and be like a receptionist (maybe?)

# Bugfixes:
# TODO: remove name from message, remove 'derpr' from own chat history. Perhaps just do a replace all derpr to {persona}
# TODO: persona save file can overwrite itself and lose info with an unclean operation
# TODO: dump_last says 200 response tokens, probably wrong so why is it wrong (fixed?)
# TODO: add error handling for bad responses from OpenAI: take the error message and attempt to send the error to testr, maybe add some context and additional info like 'if this is randomly mid-conversation just try again'
# TODO: developer commands end up in message history, usually don't want this

# big bug:
# gpt4 has relatively long queries. current program behavior locks up while waiting for the api response and discord gets mad.
# no noticeable effects from chat-end but seems like a significant operational issue given the long errors I get
# [2023-10-20 02:33:48] [WARNING ] discord.gateway: Shard ID None heartbeat blocked for more than 10 seconds.

# Inefficiencies:
#

# General
# TODO: short responses are preferred, but token limits usually cut off the message partway
# TODO: more dynamic context: allow for 'wipe memory' command, kind of loop that tracks the beginning of convo


#
# ideas, maybe bad ones:
#
# by default, add 'respond concisely as <name>' to end of request, add new dev command for 'concise on/off'
# maybe a whole suite of options? maybe toggle with emoji reactions! lol