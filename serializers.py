"""
serializers.py — pure serialisation helpers.

No state, no Flask. These functions take plain Python/numpy/pandas objects
and return JSON-safe equivalents. Safe to import anywhere.
"""

import numpy as np
import pandas as pd


def json_safe(obj):
    """Recursively converts numpy/pandas types to JSON-serialisable Python types."""
    if isinstance(obj, pd.Series):
        return obj.to_dict()
    if isinstance(obj, pd.DataFrame):
        return obj.to_dict(orient="records")
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(x) for x in obj]
    return obj


def df_to_json(df: pd.DataFrame):
    """Converts a DataFrame to a JSON-serialisable dict for report tables."""
    if df is None or df.empty:
        return None
    df_copy = df.copy()
    for col in df_copy.columns:
        # Cover both classic object columns and pandas' StringDtype (newer pandas
        # may infer string columns as StringDtype, for which `dtype == 'object'`
        # is False). Stringify only the NON-NULL cells so missing values stay as
        # NA/None and are converted to JSON null by the replace() below — calling
        # .astype(str) on the whole column would turn NA into the literal '<NA>'
        # (and None into 'None'), defeating that conversion.
        if pd.api.types.is_object_dtype(df_copy[col]) or pd.api.types.is_string_dtype(df_copy[col]):
            mask = df_copy[col].notna()
            df_copy.loc[mask, col] = df_copy.loc[mask, col].astype(str)
    df_for_json = df_copy.astype(object).replace({
        pd.NA: None, np.nan: None, np.inf: "∞", -np.inf: "-∞"
    })
    if isinstance(df.index, pd.MultiIndex):
        df_for_json = df_for_json.reset_index()
    else:
        df_for_json = df_for_json.reset_index(drop=False)
    return {"headers": df_for_json.columns.tolist(), "data": df_for_json.values.tolist()}


def get_unique_col_name(df: pd.DataFrame, base_name: str) -> str:
    """Returns base_name if unused in df, otherwise base_name_1, _2, etc."""
    if base_name not in df.columns:
        return base_name
    i = 1
    while f"{base_name}_{i}" in df.columns:
        i += 1
    return f"{base_name}_{i}"


def serialize_model_result(res) -> dict:
    """Extracts standard attributes from a statsmodels/lifelines result object."""
    out = {
        "model_summary": str(res.summary()) if hasattr(res, "summary") else str(res),
        "aic": getattr(res, "aic", None),
        "bic": getattr(res, "bic", None),
        "llf": getattr(res, "llf", None),
        "nobs": getattr(res, "nobs", None),
        "converged": getattr(res, "converged", None),
        "n_iter": getattr(res, "n_iter", None),
        "nevents": getattr(res, "nevents", None),
        "params": None, "bse": None, "pvalues": None, "zvalues": None,
        "hazard_ratios": None, "conf_int": None, "hr_conf_int": None,
        "lrt_pvalues": None, "lrt_bse": None, "unique_times": None,
        "cum_baseline_hazard": None, "baseline_survival": None,
    }

    def _series(x):
        if x is None:
            return None
        s = x if isinstance(x, pd.Series) else pd.Series(x)
        result = {}
        for k, v in s.items():
            key = str(k)
            if pd.isna(v):
                result[key] = None
            elif isinstance(v, np.integer):
                result[key] = int(v)
            elif isinstance(v, np.floating):
                result[key] = float(v)
            elif isinstance(v, np.bool_):
                result[key] = bool(v)
            else:
                result[key] = v
        return result

    def _df(x):
        if x is None or not isinstance(x, pd.DataFrame):
            return None
        tmp = x.copy()
        tmp.index = tmp.index.map(str)
        if list(tmp.columns) == [0, 1] or list(map(str, tmp.columns)) == ["0", "1"]:
            tmp.columns = ["ci_lower", "ci_upper"]
        else:
            tmp.columns = [str(c) for c in tmp.columns]
        tmp.insert(0, "variable", tmp.index)
        tmp = tmp.replace({pd.NA: None, np.nan: None})
        return tmp.to_dict(orient="records")

    for field in ["params", "bse", "pvalues", "zvalues", "hazard_ratios", "lrt_pvalues", "lrt_bse"]:
        try:
            if hasattr(res, field):
                out[field] = _series(getattr(res, field))
        except Exception:
            pass

    for field in ["conf_int", "hr_conf_int"]:
        try:
            if hasattr(res, field):
                val = getattr(res, field)
                out[field] = _df(val() if callable(val) else val)
        except Exception:
            pass

    for field in ["unique_times", "cum_baseline_hazard", "baseline_survival"]:
        try:
            if hasattr(res, field):
                val = getattr(res, field)
                if val is not None:
                    out[field] = np.asarray(val).tolist()
        except Exception:
            pass

    # Pre-reduced, already-JSON-safe diagnostic payloads attached at fit time
    # (roc_data + cv_auc for logistic, diagnostic_data for OLS/logistic), plus
    # the model-kind tag the frontend switches on. These are plain dicts/lists
    # of floats bounded server-side, so they pass straight through.
    for field in ["model_kind", "outcome_name", "roc_data", "diagnostic_data"]:
        try:
            if hasattr(res, field):
                out[field] = getattr(res, field)
        except Exception:
            pass

    return out


def make_parquet_safe(df):
    """
    Return a copy of df whose object columns are safe to write to Parquet.

    Object columns may hold python datetime objects (common from Excel date
    parsing) or genuinely mixed types; pyarrow refuses both. Per object column:
      - all values are date/datetime → real datetime64 column (lossless),
      - otherwise → only stringify if pyarrow can't handle it as-is.

    Used by both session persistence (AppState.to_bytes) and the cross-process
    job hand-off (df_to_parquet), so a dataset with dates breaks neither path.
    """
    import datetime as _dt
    import pandas as pd

    out = df.copy()
    for col in out.columns:
        # Inspect object columns AND StringDtype columns. Under newer pandas a
        # string column is StringDtype, not object, so the old `!= object` skip
        # silently bypassed the datetime-coercion and Arrow-safety net for it.
        if not (pd.api.types.is_object_dtype(out[col]) or pd.api.types.is_string_dtype(out[col])):
            continue
        non_null = out[col].dropna()
        if non_null.empty:
            continue

        if all(isinstance(v, (_dt.date, _dt.datetime, pd.Timestamp)) for v in non_null):
            try:
                out[col] = pd.to_datetime(out[col], errors="coerce")
                continue
            except Exception:
                pass

        try:
            import pyarrow as _pa
            _pa.array(out[col].to_numpy(), from_pandas=True)
        except Exception:
            out[col] = out[col].astype(object).where(out[col].notna(), None)
            out[col] = out[col].map(lambda v: v if v is None else str(v))
    return out


def df_to_parquet(df) -> bytes:
    """Serialise a DataFrame to Parquet bytes for cross-process hand-off."""
    import io
    buf = io.BytesIO()
    make_parquet_safe(df).to_parquet(buf, index=False)
    return buf.getvalue()


def df_from_parquet(data: bytes):
    """Reconstruct a DataFrame from Parquet bytes."""
    import io
    import pandas as pd
    return pd.read_parquet(io.BytesIO(data))
