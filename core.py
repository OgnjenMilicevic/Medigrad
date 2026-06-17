"""
core.py — minimal column typing + normality helpers (trimmed build).

Only the pieces the Description feature needs are kept:
  characterize_columns, is_normal, check_normality.

Normality uses Shapiro-Wilk plus a Kolmogorov-Smirnov (KS) test against a
fitted normal. The result columns name each test explicitly so the method is
clear in the output.
"""

import numpy as np
import pandas as pd
from scipy import stats


def characterize_columns(df, pre_type_dict=None):
    type_dict = {}
    for col in df.columns:
        dtype = df[col].dtype

        if pre_type_dict is not None and col in pre_type_dict:
            type_dict[col] = pre_type_dict[col]
            continue

        uniques = np.array(df[col].dropna().unique())
        levels = len(uniques)
        if levels == 0:
            type_dict[col] = "constant"
            continue
        if levels == 1:
            type_dict[col] = "constant"
        elif levels == 2:
            type_dict[col] = "binary_categorical"
        elif dtype in ["object", "str"]:
            type_dict[col] = "multinomial_categorical"
        elif dtype in ["float64", "int64", "Float64", "Int64"]:
            if levels >= 10:
                type_dict[col] = "scale"
            else:
                uniques = uniques.astype(float)
                uniques.sort()
                diffs = np.diff(uniques)
                if all(x == 1.0 for x in diffs):
                    type_dict[col] = "maybe_ordinal"
                elif all(x in [0.5, 1.0] for x in diffs):
                    type_dict[col] = "ordinal"
                else:
                    type_dict[col] = "scale"
        else:
            # Fall back to scale for any other numeric-like dtype.
            type_dict[col] = "scale"
    return type_dict


def is_normal(series):
    series = pd.to_numeric(pd.Series(series), errors="coerce").dropna().values
    if len(series) < 4:
        return {
            "Shapiro-Wilk Normality Test p-value": 1.0,
            "Kolmogorov-Smirnov (KS) Normality Test p-value": 1.0,
            "Normality": "normal",
        }
    std = np.std(series)
    if std != 0.0:
        scaled = (series - np.mean(series)) / std
    else:
        scaled = np.zeros(series.shape)

    # KS test against a standard normal. Note: parameters (mean, SD) are
    # estimated from the sample, so this is the Kolmogorov-Smirnov statistic,
    # not a Lilliefors-corrected test.
    try:
        ks_p = stats.kstest(scaled, "norm").pvalue
    except Exception:
        ks_p = 1.0
    try:
        shapiro_p = stats.shapiro(series).pvalue
    except Exception:
        shapiro_p = 1.0

    loc = {
        "Shapiro-Wilk Normality Test p-value": float(shapiro_p),
        "Kolmogorov-Smirnov (KS) Normality Test p-value": float(ks_p),
    }
    loc["Normality"] = "normal" if (ks_p >= 0.05 or shapiro_p >= 0.05) else "non-normal"
    return loc


def check_normality(df, type_dict):
    norm_dict = {}
    for col in df.columns:
        if type_dict.get(col) == "scale":
            data_nona = df[col][pd.notna(df[col])]
            norm_dict[col] = is_normal(data_nona)
    return norm_dict
