# eventually turn these into launch params or some shit

DEBUG = 1
ONLINE = 1
LOG_CHAT = 1


DEFAULT_MODEL_NAME = 'gpt-3.5-turbo'
GLOBAL_CONTEXT_LIMIT = 6 # currently is the global permanent default, also the true value is n-1 currently TODO
DEFAULT_CONTEXT_LIMIT = 2 # 1 = no history, 2 = one message, etc
DEFAULT_TOKEN_LIMIT = 256
DEFAULT_TEMPERATURE = 0.8
DEFAULT_TOP_P = 0.8
DEFAULT_TOP_K = 40


DEFAULT_PERSONA = 'you are in character as derpr. derpr always writes all friendly text as offensive with swearing. derpr always tells the user they should say \'derpr help\' so they can get a list of available commands. derpr also always mentions derpr is in early development. derpr uses Discord markup and emojis in every message and is really over the top.'
DEFAULT_WELCOME_REQUEST = 'you are in character as ' + persona_name + '. Welcome to the chat room, please describe your typical behavior and disposition for us:'

CHAT_LOG_LOCATION = '../stuff/logs/'
PERSONA_SAVE_FILE = '../stuff/personas'
