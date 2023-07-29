import models

DEBUG = 1

class Persona:
    def __init__(self, name, model, prompt):
        self.name = name
        self.model = model
        self.prompt = prompt
        # self.parameters = {}
        self.context = []

    def update_prompt(self, message):
        self.prompt += message

    def get_prompt(self):
        return self.prompt

    def set_model(self, model):
        # model = models.get_model(model_name)
        if not model:
            return False
        else:
            self.model = model
            return True

    def get_model_name(self):
        return self.model.model_name

    # def update_parameters(self, new_parameters):
    #     self.parameters.update(new_parameters)

    def generate_response(self, message, context):
        if DEBUG:
            print('Querying response as ' + self.name + '...')
        response = self.model.generate_response(self.prompt, message, context)
        self.context.append(self.prompt)
        self.context.append(response)
        return response
