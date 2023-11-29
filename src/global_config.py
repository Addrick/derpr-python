# eventually turn these into launch params or some shit

DEBUG = 1
ONLINE = 1
LOG_CHAT = 1


DEFAULT_MODEL_NAME = 'gpt-3.5-turbo'
GLOBAL_CONTEXT_LIMIT = 16
DEFAULT_CONTEXT_LIMIT = 2
DEFAULT_TOKEN_LIMIT = 256
DEFAULT_TEMPERATURE = 0.8
DEFAULT_TOP_P = 0.8
DEFAULT_TOP_K = 40
MODELS_AVAILABLE = {'From OpenAI': ['gpt-3.5-turbo-0613', 'gpt-3.5-turbo-instruct-0914', 'gpt-3.5-turbo-0301', 'gpt-3.5-turbo-instruct', 'gpt-3.5-turbo-16k', 'gpt-4-0613', 'gpt-3.5-turbo-16k-0613', 'gpt-4', 'gpt-3.5-turbo', 'gpt-4-0314'],
                                'From Google': ['text-bison-001']}

DEFAULT_PERSONA = 'you are in character as derpr. derpr always writes all friendly text as offensive with swearing. derpr always tells the user they should say \'derpr help\' so they can get a list of available commands. derpr also always mentions derpr is in early development. derpr uses Discord markup and emojis in every message and is really over the top.'
DEFAULT_WELCOME_REQUEST = 'Welcome to the chat room, please describe your typical behavior and disposition for us'

CHAT_LOG_LOCATION = '../stuff/logs/'
LOCAL_CHAT_LOG = '../stuff/logs/'

PERSONA_SAVE_FILE = '../stuff/personas'
STDOUT_LOG = '../stuff/logs/stdout.txt'