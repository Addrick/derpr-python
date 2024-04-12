import requests


# ref can be viewed at
# http://localhost:5001/api
# https://lite.koboldai.net/koboldcpp_api#/
# no ability to change settings?

class LocalModel:
    BASE_URL = "http://localhost:5001"  # Replace with your API base URL

    def __init__(self):
        pass

    def get_max_context_length(self):
        url = f"{self.BASE_URL}/api/v1/config/max_context_length"
        response = requests.get(url)
        return response.json()

    def get_max_length(self):
        url = f"{self.BASE_URL}/api/v1/config/max_length"
        response = requests.get(url)
        return response.json()

    def generate_text(self, prompt):
        url = f"{self.BASE_URL}/api/v1/generate"
        data = {"prompt": prompt}
        response = requests.post(url, json=data)
        return response.json()

    def get_api_version(self):
        url = f"{self.BASE_URL}/api/v1/info/version"
        response = requests.get(url)
        return response.json()

    def get_model_string(self):
        url = f"{self.BASE_URL}/api/v1/model"
        response = requests.get(url)
        return response.json()

    def get_true_max_context_length(self):
        url = f"{self.BASE_URL}/api/extra/true_max_context_length"
        response = requests.get(url)
        return response.json()

    def get_backend_version(self):
        url = f"{self.BASE_URL}/api/extra/version"
        response = requests.get(url)
        return response.json()

    def get_preloaded_story(self):
        url = f"{self.BASE_URL}/api/extra/preloadstory"
        response = requests.get(url)
        return response.json()

    def get_performance_info(self):
        url = f"{self.BASE_URL}/api/extra/perf"
        response = requests.get(url)
        return response.json()

    def generate_text_stream(self, prompt):
        url = f"{self.BASE_URL}/api/extra/generate/stream"
        data = {"prompt": prompt}
        response = requests.post(url, json=data, stream=True)
        return response.json()

    def poll_generation_results(self):
        url = f"{self.BASE_URL}/api/extra/generate/check"
        response = requests.get(url)
        return response.text

    def poll_generation_results_multiuser(self, user_id):
        # TODO: find how to set or get this value since it appears necessary for polling generation results w/current config
        url = f"{self.BASE_URL}/api/extra/generate/check"
        data = {"user_id": user_id}
        response = requests.get(url, json=data)
        return response.text

    def token_count(self, text):
        url = f"{self.BASE_URL}/api/extra/tokencount"
        data = {"text": text}
        response = requests.post(url, json=data)
        return response.json()

    def abort_generation(self):
        url = f"{self.BASE_URL}/api/extra/abort"
        response = requests.post(url)
        return response.json()

    def get_image_generation_models(self):
        url = f"{self.BASE_URL}/sdapi/v1/sd-models"
        response = requests.get(url)
        return response.json()

    def get_image_generation_config(self):
        url = f"{self.BASE_URL}/sdapi/v1/options"
        response = requests.get(url)
        return response.json()

    def get_supported_samplers(self):
        url = f"{self.BASE_URL}/sdapi/v1/samplers"
        response = requests.get(url)
        return response.json()

    def generate_image_from_text(self, prompt):
        url = f"{self.BASE_URL}/sdapi/v1/txt2img"
        data = {"prompt": prompt}
        response = requests.post(url, json=data)
        return response.json()

    def generate_image_caption(self, image_path):
        url = f"{self.BASE_URL}/sdapi/v1/interrogate"
        data = {"image_path": image_path}
        response = requests.post(url, json=data)
        return response.json()

    def generate_text_completions(self, prompt):
        url = f"{self.BASE_URL}/v1/completions"
        data = {"prompt": prompt}
        response = requests.post(url, json=data)
        return response.json()

    def generate_chat_completions(self, messages):
        url = f"{self.BASE_URL}/v1/chat/completions"
        data = {"messages": messages}
        response = requests.post(url, json=data)
        return response.json()

    def get_available_models(self):
        url = f"{self.BASE_URL}/v1/models"
        response = requests.get(url)
        return response.json()
