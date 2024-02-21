# derpr todo:

#dump: remake 'testr test' to just find 'test' in chat as a solo word/message and convert testr to something bettr

# Maybe Features:
# TODO: create new TODOs via chat interface
# TODO: Better persona management:
# change settings for all personas
# better save format?
# start/sleep
# don't resave all personas on each update
# print all personas w/info with one command
# record token usage
# ui to help modify personas or view info like messages as they are being generated

# TODO: try out various processing tricks like using LLM queries to evaluate the start/end of conversations or other lofty things
# TODO: modify: add option to locate name anywhere in message for reply rather than first word only?
# TODO: modify: make 'ignore other persona messages' a flag to allow for persona conversations (+commands to modify in-chat)
# TODO: print persona details cmd ('what personas' extension?)
# TODO: automated test of sorts that queries openAI for basic question and prints response to terminal (months later asking... is this testr test?)
# TODO: better logging/errors
# TODO: add temperature customizing commands
# TODO: tokenizer request
# TODO: add personal messages: currently break due to lack of channel or guild name (both?)
# TODO: add a persona prompt log - keep losing personas and wanting old versions back
# TODO: derpr should say what personas are available and be like a receptionist (maybe?)
# TODO: derpr persona should reset after some length of time or at least on restart. He's the concierge
# TODO: easier way to write gpt-3.5-turbo  (ie 'gpt3'==)
# TODO: new function to handle when derpr responds (include @derpr and every-message options)
# TODO: saving personas leaves 'in streaming...'; probably true for others too

# ASYNC OVERHAUL
# todo: fixes typing issues, allows for more agile program logic
# seems to require converting all relevant methods to become async except the top (on_message)
# will allow printing responses (somewhere) as they come in
# can cancel an in-progress request if off base or done
# using stream: NOT using async for this will allow blocking of the loop while tokens are loaded. In times of extreme lag this could be cool/useful, since it will 'stop typing'. This might be super rarely useful though

# PERSONA OVERHAUL
# TODO: persona-specific context
# TODO: 'reset/wipe/etc' can be done by setting context to 0 and then iterating a counter on each reply. Store iteration variable in persona or somewhere else?
# TODO: make small list of defaults (derpr, arbitr, testr) and encode these in global_config. Saving personas in file is generally unimportant at this stage

# Bugfixes:
# TODO: developer commands end up in message history, usually don't want this
# TODO: all persona settings except prompt are lost UNLESS prompt is also changed. Need to add a method to all these updates to resave
# TODO: developer commands end up in message history, usually don't want this. Maybe worth adding feature later to hide these form the next query
# TODO: <persona> save should be more closely localized - need handler code to more intelligently deal with save data
# TODO: gpt4 has long queries. current program behavior locks up while waiting for the api response and discord gets mad.
    # should be able to do this by making the API call async. https://github.com/openai/openai-python#async-usage
    # no noticeable effects from chat-end except not being sure if an answer is ever coming but can be handled better
    # [2023-10-20 02:33:48] [WARNING ] discord.gateway: Shard ID None heartbeat blocked for more than 10 seconds.
# TODO(BIG): filter history/context for dev commands so they don't pollute input (check each history line with preprocess()?)

# Inefficiencies:
# saving personas rewrites entire file

# General (potential tricks for better LLM outputs, code restructure, etc)
# TODO: TEST CASES!
# TODO: remove name from message, remove 'derpr' from own chat history. Perhaps just do a replace all derpr to {persona} (...why?)
# TODO: overflow into ideas.txt
# OpenAI has a new Assistants API that is basically what I'm doing here. Since this is meant to be engine-agnostic idk if it's worth but there are code and file analysis tools present now

#
# ideas, maybe bad ones:
## TODO: add error handling for bad responses from OpenAI: take the error message and attempt to send the error to testr, maybe add some context and additional info like 'if this is randomly mid-conversation just try again'
# TODO: by default, add 'respond concisely as <name>' to end of request, add new dev command for 'concise on/off'
# maybe a whole suite of options? maybe toggle with emoji reactions! lol

# what is desired handling here?
# only prompts save by default, but saving prompts also will save anything else that has been changed.
# autosave all changes? probably simplest solution but inelegant
# save nothing, add 'save_defaults' and use that file as purely default configs?
# Current behavior: only save on manual command. More advanced handling might require