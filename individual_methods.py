"""
individual_methods.py — basic statistical tests (trimmed build).

This trimmed edition exposes only the core tests:
  correlation (pearson, spearman), independent & paired t-tests,
  Mann-Whitney U, Wilcoxon signed-rank, one-way ANOVA, Kruskal-Wallis,
  chi-square, and Fisher exact.

All helpers are self-contained — no dependency on diagnostics, regression,
factor analysis, questionnaire, mediation, power, or robust modules.

Each method has the signature  method(payload: dict, df: DataFrame) -> dict
and returns {'tables': {name: {'headers': [...], 'data': [[...], ...]}}}.
"""

from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats


# ---------------------------------------------------------------------------
# Formatting / table helpers
# ---------------------------------------------------------------------------

def format_p(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    if p < 0.001:
        return "p<0,001"
    return f"p={str(round(float(p), 3)).replace('.', ',')}"


def _round(v, decimals=4):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    return round(float(v), decimals)


def _format_p(p):
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return None
    if p < 0.001:
        return f"{p:.2e}"
    return round(float(p), 4)


def _table(headers, rows):
    return {"headers": headers, "data": rows}


def _series_summary(s):
    s = pd.to_numeric(pd.Series(s), errors='coerce').dropna()
    return {
        'n': int(s.shape[0]),
        'mean': None if s.empty else round(float(s.mean()), 6),
        'std': None if s.empty else round(float(s.std(ddof=1)) if s.shape[0] > 1 else 0.0, 6),
        'median': None if s.empty else round(float(s.median()), 6),
        'min': None if s.empty else round(float(s.min()), 6),
        'max': None if s.empty else round(float(s.max()), 6),
    }


def _json_table_from_df(df: pd.DataFrame):
    if df is None:
        return None
    df = df.copy().astype(object).replace({
        pd.NA: None,
        np.nan: None,
        np.inf: '∞',
        -np.inf: '-∞'
    })
    for bad_col in ['index', 'level_0']:
        if bad_col in df.columns:
            df = df.drop(columns=[bad_col])
    return {'headers': df.columns.tolist(), 'data': df.values.tolist()}


def _single_row_table(mapping):
    df = pd.DataFrame([mapping])
    return {'headers': df.columns.tolist(), 'data': df.values.tolist()}


def _ensure_two_groups(series):
    groups = pd.Series(series).dropna().unique().tolist()
    if len(groups) != 2:
        raise ValueError(f'Expected exactly 2 groups, found {len(groups)}.')
    return groups


def _coerce_bool(v, default=None):
    if v is None or v == '':
        return default
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in ('true', '1', 'yes'):
        return True
    if s in ('false', '0', 'no'):
        return False
    return default


# ---------------------------------------------------------------------------
# Effect size + post-hoc helpers (inlined, no external module)
# ---------------------------------------------------------------------------

def _cohens_d(group_a, group_b):
    a, b = np.asarray(group_a, dtype=float), np.asarray(group_b, dtype=float)
    na, nb = len(a), len(b)
    if na + nb - 2 <= 0:
        return 0.0
    pooled_std = np.sqrt(((na - 1) * a.var(ddof=1) + (nb - 1) * b.var(ddof=1)) / (na + nb - 2))
    if pooled_std < 1e-12:
        return 0.0
    return float((a.mean() - b.mean()) / pooled_std)


def _hedges_g(group_a, group_b):
    d = _cohens_d(group_a, group_b)
    n = len(group_a) + len(group_b)
    correction = 1 - 3 / (4 * (n - 2) - 1) if n > 3 else 1
    return d * correction


def _effect_label(val, thresholds=(0.2, 0.5, 0.8)):
    s, m, l = thresholds
    v = abs(val)
    if v >= l:
        return "Large"
    if v >= m:
        return "Medium"
    if v >= s:
        return "Small"
    return "Negligible"


def _effect_sizes_two_groups(group_a, group_b):
    d = _cohens_d(group_a, group_b)
    g = _hedges_g(group_a, group_b)
    rows = [
        ["Cohen's d", _round(d), _effect_label(d)],
        ["Hedges' g", _round(g), _effect_label(g)],
        ["N (group a)", len(group_a), ""],
        ["N (group b)", len(group_b), ""],
    ]
    return _table(["Metric", "Value", "Interpretation"], rows)


def _eta_squared_from_f(f_stat, df_between, df_within):
    return (f_stat * df_between) / (f_stat * df_between + df_within)


def _omega_squared_from_f(f_stat, df_between, df_within, n_total):
    return (df_between * (f_stat - 1)) / (df_between * (f_stat - 1) + n_total)


def _correct_pvalues(pvalues, method='holm'):
    pvals = np.asarray(pvalues, dtype=float)
    n = len(pvals)
    if n == 0:
        return pvals
    if method == 'bonferroni':
        return np.minimum(pvals * n, 1.0)
    if method == 'holm':
        order = np.argsort(pvals)
        sorted_p = pvals[order]
        adjusted = np.zeros(n)
        cummax = 0.0
        for i in range(n):
            val = sorted_p[i] * (n - i)
            cummax = max(cummax, val)
            adjusted[order[i]] = min(cummax, 1.0)
        return adjusted
    if method == 'fdr_bh':
        order = np.argsort(pvals)
        sorted_p = pvals[order]
        adjusted = np.zeros(n)
        cummin = 1.0
        for i in range(n - 1, -1, -1):
            val = sorted_p[i] * n / (i + 1)
            cummin = min(cummin, val)
            adjusted[order[i]] = min(cummin, 1.0)
        return adjusted
    raise ValueError(f"Unknown correction method: {method}.")


def _tukey_hsd(data, value_col, group_col):
    groups = sorted(data[group_col].unique())
    if len(groups) < 3:
        raise ValueError("Tukey HSD requires 3+ groups.")
    group_arrays = [data.loc[data[group_col] == g, value_col].values for g in groups]
    result = stats.tukey_hsd(*group_arrays)
    rows = []
    for i in range(len(groups)):
        for j in range(i + 1, len(groups)):
            p = result.pvalue[i, j]
            d = _cohens_d(group_arrays[i], group_arrays[j])
            diff = group_arrays[i].mean() - group_arrays[j].mean()
            rows.append([
                str(groups[i]), str(groups[j]),
                _round(diff), _format_p(p),
                _round(d), _effect_label(d),
                "Significant" if p < 0.05 else "Not significant",
            ])
    return _table(
        ["Group A", "Group B", "Mean Diff", "p (Tukey)", "Cohen's d", "Effect", "Conclusion"],
        rows,
    )


def _pairwise_tests(data, value_col, group_col, test_func, correction='holm'):
    groups = sorted(data[group_col].unique())
    if len(groups) < 3:
        raise ValueError("Post-hoc tests require 3+ groups.")
    pairs = list(combinations(groups, 2))
    results = []
    for g1, g2 in pairs:
        a = data.loc[data[group_col] == g1, value_col].values
        b = data.loc[data[group_col] == g2, value_col].values
        stat, p = test_func(a, b)
        d = _cohens_d(a, b)
        results.append({"group_a": str(g1), "group_b": str(g2),
                        "stat": stat, "p_raw": p, "d": d})
    raw_ps = [r["p_raw"] for r in results]
    adjusted = _correct_pvalues(raw_ps, method=correction)
    rows = []
    for i, r in enumerate(results):
        rows.append([
            r["group_a"], r["group_b"],
            _round(r["stat"]), _format_p(r["p_raw"]), _format_p(adjusted[i]),
            _round(r["d"]), _effect_label(r["d"]),
            "Significant" if adjusted[i] < 0.05 else "Not significant",
        ])
    return _table(
        ["Group A", "Group B", "Statistic", "p (raw)", f"p ({correction})",
         "Cohen's d", "Effect", "Conclusion"],
        rows,
    )


def _pairwise_mannwhitney(data, value_col, group_col, correction='holm'):
    def _test(a, b):
        return stats.mannwhitneyu(a, b, alternative='two-sided')
    return _pairwise_tests(data, value_col, group_col, _test, correction)


def _prepare_group_and_numeric_matrix(df, group_col, value_cols):
    if isinstance(value_cols, str):
        value_cols = [value_cols]
    needed = [group_col] + list(value_cols)
    data = df.loc[:, needed].copy().dropna()
    if data.empty:
        raise ValueError('No complete rows remain after removing missing values.')
    non_numeric = []
    for col in value_cols:
        coerced = pd.to_numeric(data[col], errors='coerce')
        if coerced.isna().any():
            non_numeric.append(col)
        else:
            data[col] = coerced
    if non_numeric:
        raise ValueError('These columns must be numeric: ' + ', '.join(non_numeric))
    group_counts = data[group_col].value_counts()
    if group_counts.shape[0] < 2:
        raise ValueError('At least 2 groups are required.')
    return data, group_counts


def _group_summary_univariate(data, group_col, value_col):
    return (
        data.groupby(group_col)[value_col]
        .agg(['count', 'mean', 'std', 'median', 'min', 'max'])
        .reset_index()
    )


# ---------------------------------------------------------------------------
# Correlation
# ---------------------------------------------------------------------------

def pearson(payload, df):
    x, y = payload['variable_1'], payload['variable_2']
    data = df[[x, y]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 3:
        raise ValueError('Pearson correlation needs at least 3 complete pairs.')
    r, p = stats.pearsonr(data[x], data[y])
    return {'tables': {
        'Pearson Correlation': _single_row_table({
            'variable_1': x, 'variable_2': y, 'n': len(data),
            'r': round(float(r), 6), 'p_value': format_p(p)})
    }}


def spearman(payload, df):
    x, y = payload['variable_1'], payload['variable_2']
    data = df[[x, y]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 3:
        raise ValueError('Spearman correlation needs at least 3 complete pairs.')
    rho, p = stats.spearmanr(data[x], data[y])
    return {'tables': {
        'Spearman Correlation': _single_row_table({
            'variable_1': x, 'variable_2': y, 'n': len(data),
            'rho': round(float(rho), 6), 'p_value': format_p(p)})
    }}


# ---------------------------------------------------------------------------
# t-tests + nonparametric counterparts
# ---------------------------------------------------------------------------

def ttest_ind(payload, df):
    group_col, value_col = payload['variable_1'], payload['variable_2']
    equal_var = _coerce_bool(payload.get('equal_var'), True)
    data = df[[group_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors='coerce')
    data = data.dropna()
    groups = _ensure_two_groups(data[group_col])
    a = data.loc[data[group_col] == groups[0], value_col]
    b = data.loc[data[group_col] == groups[1], value_col]
    stat, p = stats.ttest_ind(a, b, equal_var=equal_var)
    summary = pd.DataFrame([
        {'group': str(groups[0]), **_series_summary(a)},
        {'group': str(groups[1]), **_series_summary(b)},
    ])
    return {'tables': {
        'Independent t-test': _single_row_table({
            'group_column': group_col, 'value_column': value_col,
            'group_a': str(groups[0]), 'group_b': str(groups[1]),
            't_stat': round(float(stat), 6), 'p_value': format_p(p),
            'equal_var': equal_var}),
        'Group Summary': _json_table_from_df(summary),
        'Effect Sizes': _effect_sizes_two_groups(a.values, b.values),
    }}


def ttest_paired(payload, df):
    x, y = payload['variable_1'], payload['variable_2']
    data = df[[x, y]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 2:
        raise ValueError('Paired t-test needs at least 2 complete pairs.')
    stat, p = stats.ttest_rel(data[x], data[y])
    return {'tables': {
        'Paired t-test': _single_row_table({
            'variable_1': x, 'variable_2': y, 'n_pairs': len(data),
            't_stat': round(float(stat), 6), 'p_value': format_p(p)}),
        'Paired Summary': _json_table_from_df(pd.DataFrame([
            {'variable': x, **_series_summary(data[x])},
            {'variable': y, **_series_summary(data[y])}]))
    }}


def mannwhitney(payload, df):
    group_col, value_col = payload['variable_1'], payload['variable_2']
    data = df[[group_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors='coerce')
    data = data.dropna()
    groups = _ensure_two_groups(data[group_col])
    a = data.loc[data[group_col] == groups[0], value_col]
    b = data.loc[data[group_col] == groups[1], value_col]
    alt = payload.get('alternative', 'two-sided') or 'two-sided'
    stat, p = stats.mannwhitneyu(a, b, alternative=alt)
    return {'tables': {
        'Mann-Whitney U': _single_row_table({
            'group_column': group_col, 'value_column': value_col,
            'group_a': str(groups[0]), 'group_b': str(groups[1]),
            'u_stat': round(float(stat), 6), 'p_value': format_p(p),
            'alternative': alt}),
        'Group Summary': _json_table_from_df(pd.DataFrame([
            {'group': str(groups[0]), **_series_summary(a)},
            {'group': str(groups[1]), **_series_summary(b)}]))
    }}


def wilcoxon(payload, df):
    x, y = payload['variable_1'], payload['variable_2']
    zero_method = payload.get('zero_method', 'wilcox') or 'wilcox'
    alt = payload.get('alternative', 'two-sided') or 'two-sided'
    data = df[[x, y]].apply(pd.to_numeric, errors='coerce').dropna()
    if len(data) < 1:
        raise ValueError('Wilcoxon test needs at least 1 complete pair.')
    stat, p = stats.wilcoxon(data[x], data[y], zero_method=zero_method, alternative=alt)
    return {'tables': {
        'Wilcoxon Signed-Rank': _single_row_table({
            'variable_1': x, 'variable_2': y, 'n_pairs': len(data),
            'w_stat': round(float(stat), 6), 'p_value': format_p(p),
            'alternative': alt, 'zero_method': zero_method})
    }}


# ---------------------------------------------------------------------------
# ANOVA + Kruskal-Wallis
# ---------------------------------------------------------------------------

def anova(payload, df):
    group_col, value_col = payload['group_column'], payload['value_column']
    data, group_counts = _prepare_group_and_numeric_matrix(df, group_col, [value_col])
    groups = [g[value_col].values for _, g in data.groupby(group_col) if len(g) > 0]
    if len(groups) < 2:
        raise ValueError('ANOVA needs at least 2 groups.')
    stat, p = stats.f_oneway(*groups)
    n_groups = len(groups)
    n_total = len(data)
    df_between = n_groups - 1
    df_within = n_total - n_groups
    eta2 = _eta_squared_from_f(stat, df_between, df_within)
    omega2 = _omega_squared_from_f(stat, df_between, df_within, n_total)
    out = {'tables': {
        'One-way ANOVA': _single_row_table({
            'group_column': group_col, 'value_column': value_col,
            'group_count': int(group_counts.shape[0]), 'rows_used': n_total,
            'f_stat': round(float(stat), 6), 'p_value': format_p(p),
            'eta_squared': round(float(eta2), 6),
            'omega_squared': round(float(omega2), 6)}),
        'Group Summary': _json_table_from_df(_group_summary_univariate(data, group_col, value_col))
    }}
    # Auto post-hoc (Tukey HSD) when significant and 3+ groups
    if p < 0.05 and n_groups >= 3:
        try:
            out['tables']['Post-Hoc'] = _tukey_hsd(data, value_col, group_col)
        except Exception:
            pass
    return out


def kruskal(payload, df):
    group_col, value_col = payload['group_column'], payload['value_column']
    data = df[[group_col, value_col]].copy()
    data[value_col] = pd.to_numeric(data[value_col], errors='coerce')
    data = data.dropna()
    grouped = [g[value_col].values for _, g in data.groupby(group_col) if len(g) > 0]
    if len(grouped) < 2:
        raise ValueError('Kruskal-Wallis needs at least 2 groups.')
    stat, p = stats.kruskal(*grouped)
    out = {'tables': {
        'Kruskal-Wallis': _single_row_table({
            'group_column': group_col, 'value_column': value_col,
            'group_count': len(grouped), 'h_stat': round(float(stat), 6),
            'p_value': format_p(p)}),
        'Group Summary': _json_table_from_df(
            data.groupby(group_col)[value_col]
            .agg(['count', 'mean', 'std', 'median', 'min', 'max']).reset_index())
    }}
    # Auto post-hoc (pairwise Mann-Whitney, Holm correction)
    if p < 0.05 and len(grouped) >= 3:
        try:
            out['tables']['Post-Hoc'] = _pairwise_mannwhitney(data, value_col, group_col, correction='holm')
        except Exception:
            pass
    return out


# ---------------------------------------------------------------------------
# Chi-square + Fisher exact
# ---------------------------------------------------------------------------

def chi_square(payload, df):
    x, y = payload['variable_1'], payload['variable_2']
    correction = _coerce_bool(payload.get('correction'), True)
    data = df[[x, y]].dropna()
    table = pd.crosstab(data[x], data[y])
    chi2, p, dof, expected = stats.chi2_contingency(table, correction=correction)
    expected_df = pd.DataFrame(expected, index=table.index, columns=table.columns)
    return {'tables': {
        'Contingency Table': _json_table_from_df(table.reset_index()),
        'Expected Counts': _json_table_from_df(expected_df.reset_index()),
        'Chi-square Test': _single_row_table({
            'variable_1': x, 'variable_2': y, 'chi2': round(float(chi2), 6),
            'dof': int(dof), 'p_value': format_p(p), 'correction': correction})
    }}


def fisher_exact(payload, df):
    x, y = payload['variable_1'], payload['variable_2']
    alt = payload.get('alternative', 'two-sided') or 'two-sided'
    data = df[[x, y]].dropna()
    table = pd.crosstab(data[x], data[y])
    if table.shape != (2, 2):
        raise ValueError(f'Fisher exact test requires a 2x2 table, got {table.shape[0]}x{table.shape[1]}.')
    odds, p = stats.fisher_exact(table.values, alternative=alt)
    return {'tables': {
        'Contingency Table': _json_table_from_df(table.reset_index()),
        'Fisher Exact Test': _single_row_table({
            'variable_1': x, 'variable_2': y, 'odds_ratio': round(float(odds), 6),
            'p_value': format_p(p), 'alternative': alt})
    }}


# ---------------------------------------------------------------------------
# Simple linear regression
# ---------------------------------------------------------------------------

def linear_regression(payload, df):
    """Simple (one-predictor) ordinary least-squares linear regression.

    payload: predictor_variable (x), outcome_variable (y).
    Returns a model summary, a coefficient table with 95% CIs, and a scatter
    plot of the data with the fitted regression line.
    """
    import plots

    x_col = payload.get('predictor_variable') or payload.get('variable_1')
    y_col = payload.get('outcome_variable') or payload.get('variable_2')
    if not x_col or not y_col:
        raise ValueError('Both a predictor (x) and an outcome (y) variable are required.')

    data = df[[x_col, y_col]].apply(pd.to_numeric, errors='coerce').dropna()
    n = len(data)
    if n < 3:
        raise ValueError('Linear regression needs at least 3 complete pairs.')

    x = data[x_col].to_numpy(dtype=float)
    y = data[y_col].to_numpy(dtype=float)

    res = stats.linregress(x, y)
    slope, intercept = float(res.slope), float(res.intercept)
    r, p = float(res.rvalue), float(res.pvalue)
    slope_se = float(res.stderr)
    intercept_se = float(getattr(res, 'intercept_stderr', np.nan))
    r_squared = r * r
    df_resid = n - 2

    # 95% confidence intervals for the coefficients (t-based)
    t_crit = stats.t.ppf(0.975, df_resid) if df_resid > 0 else np.nan
    slope_lo, slope_hi = slope - t_crit * slope_se, slope + t_crit * slope_se
    if np.isfinite(intercept_se):
        int_lo, int_hi = intercept - t_crit * intercept_se, intercept + t_crit * intercept_se
        int_t = intercept / intercept_se if intercept_se else np.nan
        int_p = 2 * stats.t.sf(abs(int_t), df_resid) if np.isfinite(int_t) else None
    else:
        int_lo = int_hi = int_t = int_p = None

    # Adjusted R-squared (1 predictor)
    adj_r2 = 1 - (1 - r_squared) * (n - 1) / df_resid if df_resid > 0 else None

    model_table = _single_row_table({
        'outcome': y_col,
        'predictor': x_col,
        'n': n,
        'r': round(r, 6),
        'r_squared': round(r_squared, 6),
        'adj_r_squared': None if adj_r2 is None else round(adj_r2, 6),
        'p_value': format_p(p),
        'std_err_slope': round(slope_se, 6),
    })

    coef_rows = [
        ['Intercept', _round(intercept), _round(intercept_se) if np.isfinite(intercept_se) else None,
         _round(int_t) if int_t is not None else None,
         format_p(int_p) if int_p is not None else None,
         _round(int_lo) if int_lo is not None else None,
         _round(int_hi) if int_hi is not None else None],
        [f'Slope ({x_col})', _round(slope), _round(slope_se),
         _round(slope / slope_se) if slope_se else None,
         format_p(p), _round(slope_lo), _round(slope_hi)],
    ]
    coef_table = _table(
        ['Term', 'Coefficient', 'Std. Error', 't', 'p-value', '95% CI Lower', '95% CI Upper'],
        coef_rows,
    )

    result = {'tables': {
        'Linear Regression': model_table,
        'Coefficients': coef_table,
    }}

    # Scatter with fitted line
    try:
        fig = plots.regression_scatter(data, x_col, y_col, slope, intercept, r_squared)
        result['plotly_figures'] = {'Regression Plot': fig.to_dict()}
    except Exception:
        pass

    return result


# ---------------------------------------------------------------------------
# McNemar test (paired / related categorical counterpart to chi-square)
# ---------------------------------------------------------------------------

def mcnemar(payload, df):
    """McNemar's test for paired nominal data (a 2x2 table of the same
    subjects measured twice, or two raters on the same cases).

    payload: variable_1, variable_2 (the two paired binary measurements),
             method ('exact' | 'chi2'), correction (bool, for chi2).
    """
    x, y = payload['variable_1'], payload['variable_2']
    method = (payload.get('method') or 'exact').strip().lower()
    correction = _coerce_bool(payload.get('correction'), True)

    data = df[[x, y]].dropna()
    table = pd.crosstab(data[x], data[y])
    if table.shape != (2, 2):
        raise ValueError(
            f'McNemar test requires a 2x2 table (each variable must have exactly '
            f'2 categories); got {table.shape[0]}x{table.shape[1]}.'
        )

    # Discordant pairs are the off-diagonal cells.
    b = int(table.iloc[0, 1])
    c = int(table.iloc[1, 0])
    n_discordant = b + c

    if method == 'exact':
        # Exact test: binomial on the discordant pairs (p = 0.5).
        method_label = 'Exact (binomial)'
        if n_discordant == 0:
            stat_value, p = 0.0, 1.0
            stat_name = 'b+c (discordant)'
        else:
            res = stats.binomtest(min(b, c), n_discordant, 0.5, alternative='two-sided')
            p = float(res.pvalue)
            stat_value = n_discordant
            stat_name = 'b+c (discordant)'
    else:
        # Chi-square version, optionally with Edwards/Yates continuity correction.
        method_label = 'Chi-square' + (' (continuity corrected)' if correction else '')
        stat_name = 'chi-square'
        if n_discordant == 0:
            stat_value, p = 0.0, 1.0
        else:
            if correction:
                stat_value = (abs(b - c) - 1) ** 2 / n_discordant
            else:
                stat_value = (b - c) ** 2 / n_discordant
            p = float(stats.chi2.sf(stat_value, df=1))

    return {'tables': {
        'Paired Contingency Table': _json_table_from_df(table.reset_index()),
        "McNemar's Test": _single_row_table({
            'variable_1': x,
            'variable_2': y,
            'method': method_label,
            'discordant_b': b,
            'discordant_c': c,
            stat_name: round(float(stat_value), 6),
            'p_value': format_p(p),
        }),
    }}


# ---------------------------------------------------------------------------
# One-sample tests (t-test + nonparametric sign test)
# ---------------------------------------------------------------------------

def ttest_one_sample(payload, df):
    """One-sample t-test: is the mean of a variable different from a
    hypothesized population value (popmean)?"""
    col = payload.get('variable_1') or payload.get('value_column')
    if not col:
        raise ValueError('A variable is required.')
    try:
        popmean = float(payload.get('popmean', 0))
    except (TypeError, ValueError):
        raise ValueError('The hypothesized value (popmean) must be a number.')
    alt = payload.get('alternative', 'two-sided') or 'two-sided'

    s = pd.to_numeric(df[col], errors='coerce').dropna()
    n = len(s)
    if n < 2:
        raise ValueError('One-sample t-test needs at least 2 non-missing values.')

    stat, p = stats.ttest_1samp(s, popmean, alternative=alt)
    mean = float(s.mean())
    sd = float(s.std(ddof=1))
    se = sd / np.sqrt(n) if n > 0 else np.nan
    # 95% CI for the mean
    t_crit = stats.t.ppf(0.975, n - 1)
    ci_lo, ci_hi = mean - t_crit * se, mean + t_crit * se
    # Cohen's d (one-sample): (mean - popmean) / sd
    d = (mean - popmean) / sd if sd > 1e-12 else 0.0

    return {'tables': {
        'One-sample t-test': _single_row_table({
            'variable': col,
            'hypothesized_value': popmean,
            'n': n,
            'mean': round(mean, 6),
            'std': round(sd, 6),
            't_stat': round(float(stat), 6),
            'p_value': format_p(p),
            'alternative': alt,
            'ci95_lower': round(float(ci_lo), 6),
            'ci95_upper': round(float(ci_hi), 6),
            "cohens_d": round(float(d), 6),
        }),
    }}


def sign_test_one_sample(payload, df):
    """One-sample sign test: nonparametric alternative to the one-sample
    t-test. Tests whether the median differs from a hypothesized value by
    counting how many observations fall above vs. below it (ties dropped),
    evaluated with an exact binomial test (p = 0.5)."""
    col = payload.get('variable_1') or payload.get('value_column')
    if not col:
        raise ValueError('A variable is required.')
    try:
        median0 = float(payload.get('median', payload.get('popmean', 0)))
    except (TypeError, ValueError):
        raise ValueError('The hypothesized median must be a number.')
    alt = payload.get('alternative', 'two-sided') or 'two-sided'

    s = pd.to_numeric(df[col], errors='coerce').dropna()
    if len(s) < 1:
        raise ValueError('Sign test needs at least 1 non-missing value.')

    diffs = s - median0
    n_pos = int((diffs > 0).sum())
    n_neg = int((diffs < 0).sum())
    n_ties = int((diffs == 0).sum())
    n_eff = n_pos + n_neg
    if n_eff == 0:
        raise ValueError('All values equal the hypothesized median; the sign test is undefined.')

    # Exact binomial test on the smaller count (number of "+" successes).
    if alt == 'two-sided':
        res = stats.binomtest(min(n_pos, n_neg), n_eff, 0.5, alternative='two-sided')
    elif alt in ('greater', 'larger'):
        # median > median0  => more positives
        res = stats.binomtest(n_pos, n_eff, 0.5, alternative='greater')
    elif alt in ('less', 'smaller'):
        res = stats.binomtest(n_pos, n_eff, 0.5, alternative='less')
    else:
        res = stats.binomtest(min(n_pos, n_neg), n_eff, 0.5, alternative='two-sided')
    p = float(res.pvalue)

    return {'tables': {
        'One-sample Sign Test': _single_row_table({
            'variable': col,
            'hypothesized_median': median0,
            'n_used': n_eff,
            'n_above': n_pos,
            'n_below': n_neg,
            'n_ties': n_ties,
            'sample_median': round(float(s.median()), 6),
            'p_value': format_p(p),
            'alternative': alt,
            'method': 'Exact (binomial)',
        }),
    }}


# ---------------------------------------------------------------------------
# Diagnostic test evaluation (sensitivity / specificity / predictive values)
# ---------------------------------------------------------------------------

def _wilson_ci(k, n, z=1.959963984540054):
    """Wilson score interval for a proportion k/n (95% by default)."""
    if n == 0:
        return (None, None)
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * np.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _fmt_pct(p):
    return None if p is None else round(float(p) * 100.0, 2)


def diagnostic_test(payload, df):
    """Evaluate a binary diagnostic/screening test against a gold standard.

    Builds a 2x2 table of test result (positive/negative) vs. true disease
    status (present/absent) and reports sensitivity, specificity, predictive
    values, likelihood ratios, and accuracy — each with a 95% Wilson CI.

    If a prevalence is supplied, PPV and NPV are recomputed for that prevalence
    via Bayes' theorem (the sample's own PPV/NPV only hold at the sample
    prevalence, which is usually not the real-world prevalence).

    payload:
      test_variable      column holding the test result
      disease_variable   column holding the true status (gold standard)
      test_positive      the value in test_variable that means "positive"
      disease_positive   the value in disease_variable that means "present"
      prevalence         optional float in (0,1) for adjusted PPV/NPV
    """
    test_col = payload.get('test_variable')
    dis_col = payload.get('disease_variable')
    if not test_col or not dis_col:
        raise ValueError('Both a test-result variable and a disease-status variable are required.')
    test_pos = payload.get('test_positive')
    dis_pos = payload.get('disease_positive')
    if test_pos in (None, '') or dis_pos in (None, ''):
        raise ValueError('Specify which value counts as a positive test and which as disease present.')

    data = df[[test_col, dis_col]].dropna()
    if data.empty:
        raise ValueError('No complete rows after removing missing values.')

    # Compare as strings so numeric/categorical codings both work.
    t_pos = data[test_col].astype(str) == str(test_pos)
    d_pos = data[dis_col].astype(str) == str(dis_pos)

    tp = int((t_pos & d_pos).sum())
    fp = int((t_pos & ~d_pos).sum())
    fn = int((~t_pos & d_pos).sum())
    tn = int((~t_pos & ~d_pos).sum())

    n_dis = tp + fn          # truly diseased
    n_well = fp + tn         # truly well
    if n_dis == 0 or n_well == 0:
        raise ValueError(
            'The gold standard must contain both diseased and non-diseased cases. '
            'Check the "disease present" value is correct.'
        )

    sens = tp / n_dis
    spec = tn / n_well
    sens_lo, sens_hi = _wilson_ci(tp, n_dis)
    spec_lo, spec_hi = _wilson_ci(tn, n_well)

    # Predictive values at the SAMPLE prevalence (raw, from the 2x2 table).
    n_test_pos = tp + fp
    n_test_neg = tn + fn
    ppv = tp / n_test_pos if n_test_pos else None
    npv = tn / n_test_neg if n_test_neg else None
    ppv_lo, ppv_hi = _wilson_ci(tp, n_test_pos) if n_test_pos else (None, None)
    npv_lo, npv_hi = _wilson_ci(tn, n_test_neg) if n_test_neg else (None, None)

    # Likelihood ratios.
    lr_pos = (sens / (1 - spec)) if spec < 1 else None
    lr_neg = ((1 - sens) / spec) if spec > 0 else None

    accuracy = (tp + tn) / (tp + fp + fn + tn)
    sample_prev = n_dis / (n_dis + n_well)

    contingency = {
        'headers': ['', 'Disease +', 'Disease −', 'Total'],
        'data': [
            ['Test +', tp, fp, tp + fp],
            ['Test −', fn, tn, fn + tn],
            ['Total', n_dis, n_well, n_dis + n_well],
        ],
    }

    metrics_rows = [
        ['Sensitivity', _fmt_pct(sens), _fmt_pct(sens_lo), _fmt_pct(sens_hi)],
        ['Specificity', _fmt_pct(spec), _fmt_pct(spec_lo), _fmt_pct(spec_hi)],
        ['PPV (at sample prevalence)', _fmt_pct(ppv), _fmt_pct(ppv_lo), _fmt_pct(ppv_hi)],
        ['NPV (at sample prevalence)', _fmt_pct(npv), _fmt_pct(npv_lo), _fmt_pct(npv_hi)],
        ['Accuracy', _fmt_pct(accuracy), None, None],
    ]
    metrics = {
        'headers': ['Metric', 'Value (%)', '95% CI Lower (%)', '95% CI Upper (%)'],
        'data': metrics_rows,
    }

    lr_table = _single_row_table({
        'LR+ (positive likelihood ratio)': None if lr_pos is None else round(lr_pos, 4),
        'LR− (negative likelihood ratio)': None if lr_neg is None else round(lr_neg, 4),
        'sample_prevalence (%)': _fmt_pct(sample_prev),
    })

    tables = {
        'Diagnostic 2x2 Table': contingency,
        'Diagnostic Metrics': metrics,
        'Likelihood Ratios': lr_table,
    }

    # Prevalence-adjusted predictive values via Bayes' theorem.
    prev_raw = payload.get('prevalence', None)
    if prev_raw not in (None, ''):
        try:
            prev = float(prev_raw)
        except (TypeError, ValueError):
            raise ValueError('Prevalence must be a number between 0 and 1.')
        if not (0.0 < prev < 1.0):
            raise ValueError('Prevalence must be strictly between 0 and 1 (e.g. 0.02 for 2%).')

        ppv_adj_den = sens * prev + (1 - spec) * (1 - prev)
        npv_adj_den = spec * (1 - prev) + (1 - sens) * prev
        ppv_adj = (sens * prev) / ppv_adj_den if ppv_adj_den > 0 else None
        npv_adj = (spec * (1 - prev)) / npv_adj_den if npv_adj_den > 0 else None

        tables['Predictive Values at Given Prevalence'] = _single_row_table({
            'assumed_prevalence (%)': _fmt_pct(prev),
            'PPV (adjusted) (%)': _fmt_pct(ppv_adj),
            'NPV (adjusted) (%)': _fmt_pct(npv_adj),
        })

    return {'tables': tables}


# ---------------------------------------------------------------------------
# One-way (1D) chi-square goodness-of-fit test
# ---------------------------------------------------------------------------

def _parse_number_list(text, what="values"):
    """Parse a comma/space/semicolon/newline separated list of numbers."""
    if text is None:
        return []
    if isinstance(text, (list, tuple)):
        raw = list(text)
    else:
        import re as _re
        raw = [t for t in _re.split(r'[,;\s]+', str(text).strip()) if t != '']
    out = []
    for tok in raw:
        try:
            out.append(float(tok))
        except (TypeError, ValueError):
            raise ValueError(f"Could not read '{tok}' as a number in the {what}.")
    return out


def chi_square_gof(payload, df):
    """One-dimensional chi-square goodness-of-fit test.

    Two input modes (auto-detected from what the user supplied):

    A) Column mode: a categorical column is supplied; observed counts are the
       category frequencies.
    B) Manual mode: the user types observed frequencies directly.

    Expected frequencies are supplied either way. They may be given as:
      - counts that sum to the same total as observed, or
      - proportions / ratios (any positive numbers) that are rescaled to the
        observed total automatically, or
      - left blank, meaning a uniform (equal) expected distribution.
    """
    mode = (payload.get('mode') or '').strip().lower()
    category_labels = None

    # ---- Determine observed counts -------------------------------------
    column = payload.get('variable_1') or payload.get('column')
    observed_text = payload.get('observed')

    if mode == 'column' or (not mode and column):
        if not column:
            raise ValueError('Select a column for column mode.')
        s = df[column].dropna()
        if s.empty:
            raise ValueError('The selected column has no non-missing values.')
        vc = s.value_counts()
        # Deterministic ordering: by label so it lines up with expected entry.
        try:
            vc = vc.sort_index()
        except Exception:
            pass
        category_labels = [str(i) for i in vc.index.tolist()]
        observed = vc.to_numpy(dtype=float)
        source = f"column '{column}'"
    else:
        observed = np.array(_parse_number_list(observed_text, "observed frequencies"))
        if observed.size == 0:
            raise ValueError('Enter the observed frequencies (or choose a column).')
        if np.any(observed < 0):
            raise ValueError('Observed frequencies cannot be negative.')
        # Optional user-supplied category names (comma/semicolon/newline list).
        labels_text = payload.get('category_labels') or payload.get('categories_names')
        if labels_text:
            import re as _re
            if isinstance(labels_text, (list, tuple)):
                user_labels = [str(x).strip() for x in labels_text if str(x).strip() != '']
            else:
                user_labels = [t.strip() for t in _re.split(r'[,;\n]+', str(labels_text)) if t.strip() != '']
            if len(user_labels) not in (0, observed.size):
                raise ValueError(
                    f'You gave {len(user_labels)} category name(s) but there are '
                    f'{observed.size} observed value(s). They must match.'
                )
            category_labels = user_labels if user_labels else [f"Cat {i+1}" for i in range(observed.size)]
        else:
            category_labels = [f"Cat {i+1}" for i in range(observed.size)]
        source = "entered observed frequencies"

    k = observed.size
    if k < 2:
        raise ValueError('Goodness-of-fit needs at least 2 categories.')

    # ---- Determine expected counts -------------------------------------
    expected_text = payload.get('expected')
    exp_list = _parse_number_list(expected_text, "expected frequencies")
    total = float(observed.sum())

    if len(exp_list) == 0:
        # Blank => uniform expectation.
        expected = np.full(k, total / k, dtype=float)
        expected_desc = "uniform (equal across categories)"
    else:
        if len(exp_list) != k:
            raise ValueError(
                f'You gave {len(exp_list)} expected value(s) but there are {k} '
                f'categories. They must match.'
            )
        exp_arr = np.array(exp_list, dtype=float)
        if np.any(exp_arr < 0):
            raise ValueError('Expected frequencies cannot be negative.')
        exp_sum = exp_arr.sum()
        if exp_sum <= 0:
            raise ValueError('Expected frequencies must sum to a positive number.')
        # If expected don't already sum to the observed total (within rounding),
        # treat them as proportions/ratios and rescale to the observed total.
        if abs(exp_sum - total) > 1e-6:
            expected = exp_arr / exp_sum * total
            expected_desc = "rescaled from supplied ratios/proportions to the observed total"
        else:
            expected = exp_arr
            expected_desc = "as supplied (counts)"

    # ---- Run the test ---------------------------------------------------
    stat, p = stats.chisquare(f_obs=observed, f_exp=expected)
    dof = k - 1

    # Cramér's V for goodness-of-fit (effect size): sqrt(chi2 / (N*(k-1)))
    cramers_v = float(np.sqrt(stat / (total * (k - 1)))) if total > 0 and k > 1 else None

    # Assumption note (Cochran's rule of thumb).
    min_expected = float(np.min(expected))
    n_small = int(np.sum(expected < 5))
    assumption = "OK"
    if min_expected < 1:
        assumption = "Violated: an expected count is below 1."
    elif n_small > 0:
        pct_small = 100.0 * n_small / k
        if pct_small > 20:
            assumption = f"Caution: {n_small}/{k} expected counts are below 5 (>20%)."
        else:
            assumption = f"Note: {n_small} expected count(s) below 5."

    # ---- Build output tables -------------------------------------------
    detail_rows = []
    for i in range(k):
        o = float(observed[i])
        e = float(expected[i])
        contrib = (o - e) ** 2 / e if e > 0 else None
        detail_rows.append([
            category_labels[i],
            round(o, 4),
            round(e, 4),
            round(o - e, 4),
            None if contrib is None else round(contrib, 4),
        ])
    detail_table = _table(
        ['Category', 'Observed', 'Expected', 'Obs − Exp', '(O−E)²/E'],
        detail_rows,
    )

    summary_table = _single_row_table({
        'source': source,
        'categories': k,
        'N': round(total, 4),
        'expected_basis': expected_desc,
        'chi_square': round(float(stat), 6),
        'df': dof,
        'p_value': format_p(p),
        "cramers_v": None if cramers_v is None else round(cramers_v, 4),
        'expected_count_assumption': assumption,
    })

    return {'tables': {
        'Chi-square Goodness-of-Fit': summary_table,
        'Observed vs Expected': detail_table,
    }}


# ---------------------------------------------------------------------------
# Registry — only the basic tests
# ---------------------------------------------------------------------------

METHODS = {
    'pearson': pearson,
    'spearman': spearman,
    'ttest-ind': ttest_ind,
    'ttest_ind': ttest_ind,
    'ttest-paired': ttest_paired,
    'ttest_paired': ttest_paired,
    'ttest-one-sample': ttest_one_sample,
    'ttest_one_sample': ttest_one_sample,
    'sign-test': sign_test_one_sample,
    'sign_test': sign_test_one_sample,
    'mannwhitney': mannwhitney,
    'wilcoxon': wilcoxon,
    'anova': anova,
    'kruskal': kruskal,
    'chi-square': chi_square,
    'chi_square': chi_square,
    'chi-square-gof': chi_square_gof,
    'chi_square_gof': chi_square_gof,
    'fisher-exact': fisher_exact,
    'fisher_exact': fisher_exact,
    'linear-regression': linear_regression,
    'linear_regression': linear_regression,
    'mcnemar': mcnemar,
    'diagnostic-test': diagnostic_test,
    'diagnostic_test': diagnostic_test,
}
