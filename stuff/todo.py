# derpr todo:

# before leaving:
# - kobold errors to discord
# - maybe all errors
# Ability to update from GitHub and restart
# Config for a faster local model

# Features:
# TODO: TIME based memory instead of message #s or 'start conversation' system
# TODO: make tiny gui for easier parameter tuning
# TODO: add multiple hyperparameter fields for personas to account for differences in models (ie openai_temp vs local_model_x_temp. Wonder if some kind of crude modifiers can work)
# TODO: create new TODOs via chat interface (dev command to write to this file? need to make .txt for security)
# TODO: Create chat channel in herp for error/console dumping; add try/except to message processors
# TODO: Add multiple configs for koboldcpp, remote program handling needs work (start/stop, errors, check status)
# TODO: dev command to cancel a generation and dump partial replyasd

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
