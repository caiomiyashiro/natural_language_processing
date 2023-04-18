import pandas as pd
import numpy as np
from snorkel.labeling import PandasLFApplier

def get_lf_outputs(df:pd.DataFrame, lfs:list) -> np.ndarray:
    applier = PandasLFApplier(lfs=lfs)
    L_train = applier.apply(df=df)
    return L_train