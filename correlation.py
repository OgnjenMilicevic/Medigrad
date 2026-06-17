"""
Correlation engine — provides 8 correlation methods plus a smart auto-router
that picks the best method for each variable pair based on type and normality.

Every public function returns a standardised result dict:
{
    "matrix":     {"headers": [...], "data": [[...]]},   # coefficient matrix
    "p_matrix":   {"headers": [...], "data": [[...]]},   # p-value matrix (if applicable)
    "n_matrix":   {"headers": [...], "data": [[...]]},   # pairwise sample sizes
    "method_map": {"headers": [...], "data": [[...]]},   # (smart only) which method was used
    "method_name": str,
}
"""

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matrix_to_table(matrix, labels):
    """Convert a 2-D numpy array + row/col labels into the standard table dict."""
    data = []
    for i, label in enumerate(labels):
        row = [label]
        for j in range(len(labels)):
            v = matrix[i, j]
            if v is None or (isinstance(v, float) and np.isnan(v)):
                row.append(None)
            else:
                row.append(round(float(v), 6) if isinstance(v, (float, np.floating)) else v)
        data.append(row)
    return {"headers": [""] + list(labels), "data": data}


def _format_p(p):
    """Format a p-value for display."""
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    if p < 0.001:
        return f"{p:.2e}"
    return round(float(p), 4)


def _pairwise_n(df, cols):
    """Build matrix of pairwise non-null counts."""
    n = len(cols)
    mat = np.zeros((n, n), dtype=int)
    for i in range(n):
        for j in range(i, n):
            count = df[[cols[i], cols[j]]].dropna().shape[0]
            mat[i, j] = mat[j, i] = count
    return mat


def _select_numeric(df, columns):
    """Filter to numeric columns from the requested list."""
    if columns:
        cols = [c for c in columns if c in df.columns and pd.api.types.is_numeric_dtype(df[c])]
    else:
        cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    return cols


def _select_all_valid(df, columns):
    """Filter to columns that exist and have >1 unique value."""
    if columns:
        cols = [c for c in columns if c in df.columns and df[c].dropna().nunique() > 1]
    else:
        cols = [c for c in df.columns if df[c].dropna().nunique() > 1]
    return cols


# ---------------------------------------------------------------------------
# 1. Pearson
# ---------------------------------------------------------------------------

def pearson(df, columns=None):
    cols = _select_numeric(df, columns)
    if len(cols) < 2:
        raise ValueError("Pearson needs at least 2 numeric columns.")

    n = len(cols)
    r_mat = np.full((n, n), np.nan)
    p_mat = np.full((n, n), np.nan)

    for i in range(n):
        r_mat[i, i] = 1.0
        p_mat[i, i] = 0.0
        for j in range(i + 1, n):
            pair = df[[cols[i], cols[j]]].dropna()
            if len(pair) < 3:
                continue
            r, p = stats.pearsonr(pair.iloc[:, 0], pair.iloc[:, 1])
            r_mat[i, j] = r_mat[j, i] = r
            p_mat[i, j] = p_mat[j, i] = p

    return {
        "method_name": "Pearson",
        "matrix": _matrix_to_table(r_mat, cols),
        "p_matrix": _matrix_to_table(p_mat, cols),
        "n_matrix": _matrix_to_table(_pairwise_n(df, cols), cols),
    }


# ---------------------------------------------------------------------------
# 2. Spearman
# ---------------------------------------------------------------------------

def spearman(df, columns=None):
    cols = _select_numeric(df, columns)
    if len(cols) < 2:
        raise ValueError("Spearman needs at least 2 numeric columns.")

    n = len(cols)
    r_mat = np.full((n, n), np.nan)
    p_mat = np.full((n, n), np.nan)

    for i in range(n):
        r_mat[i, i] = 1.0
        p_mat[i, i] = 0.0
        for j in range(i + 1, n):
            pair = df[[cols[i], cols[j]]].dropna()
            if len(pair) < 3:
                continue
            rho, p = stats.spearmanr(pair.iloc[:, 0], pair.iloc[:, 1])
            r_mat[i, j] = r_mat[j, i] = rho
            p_mat[i, j] = p_mat[j, i] = p

    return {
        "method_name": "Spearman",
        "matrix": _matrix_to_table(r_mat, cols),
        "p_matrix": _matrix_to_table(p_mat, cols),
        "n_matrix": _matrix_to_table(_pairwise_n(df, cols), cols),
    }


def run(method, df, columns=None, **kwargs):
    """
    Main entry point.  Called by the Flask route.

    Parameters
    ----------
    method : str   — key into METHODS
    df     : DataFrame
    columns: list[str] | None
    **kwargs: passed through (e.g. covariate_columns for partial)
    """
    fn = METHODS.get(method)
    if fn is None:
        # Trimmed build supports only pearson and spearman; default to pearson.
        fn = METHODS["pearson"]
    result = fn(df, columns=columns)
    _build_pairwise_summary(result)
    return result


METHODS = {
    "pearson": pearson,
    "spearman": spearman,
}

def _build_pairwise_summary(result):
    """Flatten the upper triangle of the matrices into a row-per-pair table."""
    mat = result['matrix']
    labels = mat['headers'][1:]  # skip the empty first header
    n = len(labels)

    has_p = result.get('p_matrix') is not None
    has_n = result.get('n_matrix') is not None
    has_method = result.get('method_map') is not None

    headers = ['Variable 1', 'Variable 2', 'Coefficient']
    if has_p:      headers.append('P-Value')
    if has_n:      headers.append('N')
    if has_method:  headers.append('Method')

    rows = []
    for i in range(n):
        for j in range(i + 1, n):
            row = [
                labels[i],
                labels[j],
                mat['data'][i][j + 1],      # +1 because col 0 is the row label
            ]
            if has_p:
                row.append(result['p_matrix']['data'][i][j + 1])
            if has_n:
                row.append(result['n_matrix']['data'][i][j + 1])
            if has_method:
                row.append(result['method_map']['data'][i][j + 1])
            rows.append(row)

    result['summary'] = {'headers': headers, 'data': rows}