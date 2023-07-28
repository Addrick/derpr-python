
class Personality:
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

    # def update_parameters(self, new_parameters):
    #     self.parameters.update(new_parameters)

    def generate_response(self, message, context):
        response = self.model.generate_response(self.prompt, message, context)
        self.context.append(self.prompt)
        self.context.append(response)
        self.prompt = ""  # Reset prompt for the next conversation
        return response
