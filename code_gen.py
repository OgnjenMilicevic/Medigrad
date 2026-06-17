"""
code_gen.py — produce the equivalent Python (pandas/scipy) code for an
analysis, shown in the app's "Python Code" learning panel.

The goal is pedagogical: a student picks a test in the UI and can see exactly
how the same result would be obtained in code. Snippets assume:
    import pandas as pd
    from scipy import stats
    df = pd.read_csv("your_data.csv")
"""

import json


def _col(name):
    return repr(name)


def generate(method, payload):
    """Return a Python snippet string for the given method + parameters,
    or a generic comment if we don't have a template."""
    p = payload or {}
    v1 = p.get('variable_1')
    v2 = p.get('variable_2')
    gc = p.get('group_column')
    vc = p.get('value_column')

    header = (
        "import pandas as pd\n"
        "from scipy import stats\n\n"
        'df = pd.read_csv("your_data.csv")\n'
    )

    if method in ('pearson', 'spearman'):
        fn = 'pearsonr' if method == 'pearson' else 'spearmanr'
        cols = p.get('columns') or []
        if isinstance(cols, (list, tuple)) and len(cols) >= 2:
            x_col, y_col = cols[0], cols[1]
        else:
            x_col, y_col = (v1 or 'col_x'), (v2 or 'col_y')
        return header + (
            f"x = df[{_col(x_col)}]\n"
            f"y = df[{_col(y_col)}]\n"
            f"r, p = stats.{fn}(x.dropna(), y.dropna())\n"
            f"print(r, p)"
        )

    if method in ('ttest_ind', 'ttest-ind'):
        eq = p.get('equal_var', True)
        eq = False if str(eq).lower() in ('false', '0', 'no') else True
        return header + (
            f"groups = df[{_col(v1)}].dropna().unique()\n"
            f"a = df.loc[df[{_col(v1)}] == groups[0], {_col(v2)}]\n"
            f"b = df.loc[df[{_col(v1)}] == groups[1], {_col(v2)}]\n"
            f"t, p = stats.ttest_ind(a, b, equal_var={eq})\n"
            f"print(t, p)"
        )

    if method in ('ttest_paired', 'ttest-paired'):
        return header + (
            f"t, p = stats.ttest_rel(df[{_col(v1)}], df[{_col(v2)}])\n"
            f"print(t, p)"
        )

    if method in ('ttest_one_sample', 'ttest-one-sample'):
        mu = p.get('popmean', 0)
        alt = p.get('alternative', 'two-sided')
        return header + (
            f"t, p = stats.ttest_1samp(df[{_col(v1)}].dropna(), {mu!r}, "
            f"alternative={alt!r})\n"
            f"print(t, p)"
        )

    if method in ('sign_test', 'sign-test'):
        med = p.get('median', p.get('popmean', 0))
        return header + (
            f"import numpy as np\n"
            f"diffs = df[{_col(v1)}].dropna() - {med!r}\n"
            f"n_pos = int((diffs > 0).sum())\n"
            f"n_neg = int((diffs < 0).sum())\n"
            f"res = stats.binomtest(min(n_pos, n_neg), n_pos + n_neg, 0.5)\n"
            f"print(res.pvalue)"
        )

    if method == 'mannwhitney':
        alt = p.get('alternative', 'two-sided')
        return header + (
            f"groups = df[{_col(v1)}].dropna().unique()\n"
            f"a = df.loc[df[{_col(v1)}] == groups[0], {_col(v2)}]\n"
            f"b = df.loc[df[{_col(v1)}] == groups[1], {_col(v2)}]\n"
            f"u, p = stats.mannwhitneyu(a, b, alternative={alt!r})\n"
            f"print(u, p)"
        )

    if method == 'wilcoxon':
        return header + (
            f"w, p = stats.wilcoxon(df[{_col(v1)}], df[{_col(v2)}])\n"
            f"print(w, p)"
        )

    if method == 'anova':
        return header + (
            f"groups = [g[{_col(vc)}].values for _, g in df.groupby({_col(gc)})]\n"
            f"f, p = stats.f_oneway(*groups)\n"
            f"print(f, p)"
        )

    if method == 'kruskal':
        return header + (
            f"groups = [g[{_col(vc)}].values for _, g in df.groupby({_col(gc)})]\n"
            f"h, p = stats.kruskal(*groups)\n"
            f"print(h, p)"
        )

    if method in ('chi_square', 'chi-square'):
        corr = p.get('correction', True)
        corr = False if str(corr).lower() in ('false', '0', 'no') else True
        return header + (
            f"table = pd.crosstab(df[{_col(v1)}], df[{_col(v2)}])\n"
            f"chi2, p, dof, expected = stats.chi2_contingency(table, correction={corr})\n"
            f"print(chi2, p, dof)"
        )

    if method in ('fisher_exact', 'fisher-exact'):
        alt = p.get('alternative', 'two-sided')
        return header + (
            f"table = pd.crosstab(df[{_col(v1)}], df[{_col(v2)}])\n"
            f"odds, p = stats.fisher_exact(table.values, alternative={alt!r})\n"
            f"print(odds, p)"
        )

    if method in ('chi_square_gof', 'chi-square-gof'):
        if p.get('mode') == 'manual':
            obs = p.get('observed', '')
            exp = p.get('expected', '')
            obs_list = [x.strip() for x in str(obs).replace(';', ',').split(',') if x.strip()]
            code = header.replace('df = pd.read_csv("your_data.csv")\n', '')
            code += f"observed = [{', '.join(obs_list)}]\n"
            if str(exp).strip():
                exp_list = [x.strip() for x in str(exp).replace(';', ',').split(',') if x.strip()]
                code += (
                    f"expected_ratio = [{', '.join(exp_list)}]\n"
                    f"total = sum(observed)\n"
                    f"expected = [e / sum(expected_ratio) * total for e in expected_ratio]\n"
                    f"chi2, p = stats.chisquare(observed, expected)\n"
                )
            else:
                code += "chi2, p = stats.chisquare(observed)  # uniform expected\n"
            code += "print(chi2, p)"
            return code
        else:
            col = p.get('variable_1')
            return header + (
                f"observed = df[{_col(col)}].value_counts().sort_index()\n"
                f"chi2, p = stats.chisquare(observed)  # uniform expected\n"
                f"print(chi2, p)"
            )

    if method in ('mcnemar',):
        meth = p.get('method', 'exact')
        return header + (
            f"table = pd.crosstab(df[{_col(v1)}], df[{_col(v2)}])\n"
            f"b, c = table.iloc[0, 1], table.iloc[1, 0]\n"
            + (
                "res = stats.binomtest(min(b, c), b + c, 0.5)\n"
                "print(res.pvalue)"
                if meth == 'exact' else
                "chi2 = (abs(b - c) - 1) ** 2 / (b + c)  # continuity corrected\n"
                "p = stats.chi2.sf(chi2, df=1)\n"
                "print(chi2, p)"
            )
        )

    if method in ('linear_regression', 'linear-regression'):
        y = p.get('outcome_variable')
        x = p.get('predictor_variable')
        return header + (
            f"x = df[{_col(x)}]\n"
            f"y = df[{_col(y)}]\n"
            f"res = stats.linregress(x, y)\n"
            f"print('slope', res.slope, 'intercept', res.intercept)\n"
            f"print('r^2', res.rvalue ** 2, 'p', res.pvalue)"
        )

    if method in ('diagnostic_test', 'diagnostic-test'):
        tv = p.get('test_variable'); dv = p.get('disease_variable')
        tp = p.get('test_positive'); dp = p.get('disease_positive')
        return header + (
            f"tp = ((df[{_col(tv)}] == {tp!r}) & (df[{_col(dv)}] == {dp!r})).sum()\n"
            f"fp = ((df[{_col(tv)}] == {tp!r}) & (df[{_col(dv)}] != {dp!r})).sum()\n"
            f"fn = ((df[{_col(tv)}] != {tp!r}) & (df[{_col(dv)}] == {dp!r})).sum()\n"
            f"tn = ((df[{_col(tv)}] != {tp!r}) & (df[{_col(dv)}] != {dp!r})).sum()\n"
            f"sensitivity = tp / (tp + fn)\n"
            f"specificity = tn / (tn + fp)\n"
            f"print('sensitivity', sensitivity, 'specificity', specificity)"
        )

    if method == 'describe':
        return header + "print(df.describe(include='all'))"

    return (
        "# A code template for this analysis isn't available yet.\n"
        f"# Method: {method}\n"
        f"# Parameters: {json.dumps(p, ensure_ascii=False)}"
    )
