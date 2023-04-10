import json      # loading credentials

def get_credentials(source:str):
    f = open('parameters.json')
    return json.load(f)[source]

def create_url_pars(base_url:str, query_params:dict) -> str:
    query_pars = "?"
    for k, v in query_params.items():
        if v is not None and not k.startswith('__'):
            query_pars += f'{k}={v}&'
    if len(query_params) > 0:
        query_pars = query_pars[:-1] # remove last &
    else:
        query_pars = ""
    base_url = base_url + query_pars
    return base_url
