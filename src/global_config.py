# eventually turn these into launch params or some shit

DISCORD_BOT = 1
DISCORD_DISCONNECT_TIME = None
DISCORD_CHAR_LIMIT = 2000
DISCORD_LOGGER = False

DEFAULT_MODEL_NAME = 'gpt-3.5-turbo'
GLOBAL_CONTEXT_LIMIT = 16
DEFAULT_CONTEXT_LIMIT = 0
DEFAULT_TOKEN_LIMIT = 256
DEFAULT_TEMPERATURE = 0.8
DEFAULT_TOP_P = 0.8
DEFAULT_TOP_K = 0


DEFAULT_PERSONA = 'you are in character as derpr. derpr always writes all friendly text as offensive with swearing. derpr always tells the user they should say \'derpr help\' so they can get a list of available commands. derpr also always mentions derpr is in early development. derpr uses Discord markup and emojis in every message and is really over the top.'
DEFAULT_WELCOME_REQUEST = 'Welcome to the chat room, please describe your typical behavior and disposition for us'

CHAT_LOG_LOCATION = '../stuff/logs/'
LOCAL_CHAT_LOG = '../stuff/logs/'

PERSONA_SAVE_FILE = '../stuff/personas'
STDOUT_LOG = '../stuff/logs/stdout.txt'

KOBOLDCPP_EXE = 'F:\Machine Learning\koboldcpp.exe'
KOBOLDCPP_CONFIG = 'F:\Machine Learning\dolphin-2.7-mixtral-8x7b.Q5_K_M.kcpps'
# KOBOLDCPP_CONFIG = 'F:\Machine Learning\mistral-7b.kcpps'
# KOBOLDCPP_CONFIG = 'F:\Machine Learning\default_mistral_DPO.kcpps'  # leaked mistral 70B
