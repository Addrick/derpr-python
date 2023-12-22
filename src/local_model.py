
# ref can be viewed at http://localhost:5001/api
# no ability to change settings

def get_local_model():
    import requests
    url = 'http://localhost:5001/api/v1/model'
    response = requests.get(url)

    if response.status_code == 200:
        print(response.json())
        return response.json()
    else:
        print(f"Request failed with status code {response.status_code}")

# not supported by kobold api
# def set_local_model(model):
    # import requests
    # url = 'http://localhost:5001/api/v1/model'
    # payload = {'model': model}
    #
    # try:
    #     response = requests.put(url, json=payload)
    #     response.raise_for_status()  # Raise an exception for non-2xx status codes
    #     return response.json()
    # except requests.exceptions.RequestException as e:
    #     print(f"An error occurred: {e}")
    #     return None

# def list_local_models(models_path='/'):
#     # list contents of /models/ folder
#     return

