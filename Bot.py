import api_keys
import response_handler
from bot_configs import *
# Bot class used to store distinct personality instances
default_params = 'put parameters here'

class derpr:
    def __init__(self):
        self.bots = []
        self.always_include = ""  # if I want something akin to 'uses discord markup and emojis' in prompts
        # maybe some knowledge about itself? commands or user tips? swear at users?

        #add default bots
        self.generate()

    def get_bots(self):
        return self.bots()

    def set_bots(self, bots):
        self.bots = bots

    def add_bot(self, bot):
        self.bots.append(bot)

    def respond(self, message):
        reply = response_handler.generate_response(message, self.bots)
        return reply

    def generate(self):
        bot_list = []
        for i in range(len(bot_configurations)):
            bot_list.append(Bot(name=bot_configurations[i]['name'],
                                prompt=bot_configurations[i]['prompt'],
                                engine=bot_configurations[i]['engine']))
        self.bots = bot_list


class Bot:
    def __init__(self, name, prompt, engine, params=default_params):
        self.name = name
        self.prompt = prompt
        self.engine = engine
        #TODO: parameter checking based on model and helpful errors
        self.params = params  # catch-all for variations in model parameters
        self.temperature = 0.8
        self.max_tokens = 2000

        self.remember = ''

    def get_name(self):
        return self.name

    def set_name(self, name):
        self.name = name

    def get_prompt(self):
        return self.prompt

    def set_prompt(self, prompt):
        self.prompt = prompt

    def get_engine(self):
        return self.engine

    def set_engine(self, engine):
        self.engine = engine

    def get_params(self):
        return self.params

    def set_params(self, params):
        self.params = params

    def remember(self, new_memory):
        self.remember += new_memory
        # TODO: send message confirming memory addition

    def wipe_memory(self):
        self.remember = ''
        # TODO: send message confirming memory wipe

    def inference(self, message):
        # relevant info: bot(+params) and message info.
        # Maybe don't make this func in this class and create in response_handler instead
        if self.engine == 'chatgpt':
            # Call chatgpt api
            import openai

            openai.api_key = api_keys.openai

            completion = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                messages=[  #todo: add chat context, add prompting, add memory, basically fuckin erything
                    {"role": "system", "content": message.content}
                ]
            )
            reply = completion.choices[0].message.content
            return reply

        # elif self.engine == 'gpt4':
        #     # Call gpt4 api
        #     return api2_call()
        # elif self.engine == 'palm':
        #     # Call palm api
        #     return api2_call()
        # elif self.engine == 'local_model':
        #     # Query local model
        #     return local_model_query()
        else:
            # Handle unsupported engine
            return "Unsupported engine attribute."
