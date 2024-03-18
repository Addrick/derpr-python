# derpr todo:

#dump: remake 'testr test' to just find 'test' in chat as a solo word/message and convert testr to something bettr
# TODO: make tiny gui for easier parameter tuning
# TODO: BUG super long generation times from local models cause asyncio.exceptions.TimeoutError

# Maybe Features:
# TODO: fix 'is typing...' behavior to persist longer while request is generating
# TODO: add multiple hyperparameter fields for personas to account for differences in models (ie openai_temp vs local_temp)
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
# TODO: add temperature customizing commands
# TODO: add personal messages: currently break due to lack of channel or guild name (both?)
# TODO: add a persona prompt log - keep losing personas and wanting old versions back
# TODO: derpr persona should reset after some length of time or at least on restart.
# TODO: easier way to write gpt-3.5-turbo  (ie 'gpt3'==)
# TODO: new function to handle when derpr responds (include @derpr and every-message options)

# Bugfixes:
# TODO: developer commands end up in message history, usually don't want this
# TODO: all persona settings except prompt are lost UNLESS prompt is also changed. Need to add a method to all these updates to resave. Kind of like this now as I usually don't want permanent changes but still seems not ideal behavior
# TODO(BIG): filter history/context for dev commands so they don't pollute input (check each history line with preprocess()?)

# Inefficiencies:
# saving personas rewrites entire file
