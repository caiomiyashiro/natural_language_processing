import json      # loading credentials
import pandas as pd
import numpy as np
import emoji
import re
from snorkel.labeling import PandasLFApplier, labeling_function

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

def get_lf_outputs(df:pd.DataFrame) -> np.ndarray:
    # Define labels
    TRUE_PRICE = 1
    NOT_TRUE_PRICE = 0
    ABSTAIN = -1

    @labeling_function()
    def lf_contains_emoji(x):
        # Return a label of NOT_TRUE_PRICE if text contains emoji - indicates a shop selling, otherwise TRUE_PRICE
        return NOT_TRUE_PRICE if len(emoji.emoji_list(x['description'])) > 0 else TRUE_PRICE

    @labeling_function()
    def lf_contains_link(x):
        # Return a label of NOT_TRUE_PRICE if "http" in text, otherwise TRUE_PRICE
        return NOT_TRUE_PRICE if "http" in x['description'].lower() else TRUE_PRICE

    @labeling_function()
    def lf_contains_shop_words(x):
        # Return a label of NOT_TRUE_PRICE if  using traditional shop wordings, otherwise TRUE_PRICE
        match = re.search('juros\w+|parcela\w+|boleto\s+|orçamento', x['description'].lower())
        return NOT_TRUE_PRICE if "http" is not None else TRUE_PRICE  

    lfs = [lf_contains_emoji, lf_contains_link, lf_contains_shop_words]
    applier = PandasLFApplier(lfs=lfs)
    L_train = applier.apply(df=df)
    return L_train
