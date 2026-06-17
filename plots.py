"""
plots.py — pure figure-building functions.

No Flask imports. No knowledge of HTTP request/response.
Every function takes a DataFrame (and parameters) and returns a Plotly Figure,
or raises ValueError for bad inputs.

The graphics blueprint is a thin HTTP adapter that calls these functions.
"""

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as scipy_stats

_PALETTE = px.colors.qualitative.Plotly


def _rgba(rgb_str: str, alpha: float) -> str:
    """Convert 'rgb(r,g,b)' to 'rgba(r,g,b,alpha)'."""
    return rgb_str.replace('rgb', 'rgba').replace(')', f',{alpha})')


def _clean_params(params: dict) -> dict:
    """Strip None/''/plot_type keys — safe to splat into px calls."""
    return {k: v for k, v in params.items() if v is not None and v != '' and k != 'plot_type'}


# ---------------------------------------------------------------------------
# House style — one consistent look applied to every figure.
#
# Sets only *ambient* properties (template, fonts, colourway, backgrounds,
# gridlines, title centring, legend/margins). It deliberately does NOT touch
# axis range / scaleanchor / constrain / dragmode or any per-trace property,
# because individual builders set those on purpose (e.g. the ROC's square
# aspect, the scatter's box-select dragmode). update_layout/update_xaxes only
# overwrite the keys passed, so applying this is additive: a builder that later
# sets an axis range or a trace colour still wins.
# ---------------------------------------------------------------------------

_FONT_FAMILY = "Inter, system-ui, -apple-system, Segoe UI, Roboto, sans-serif"
_GRID_COLOR = "rgba(0,0,0,0.07)"
_AXIS_LINE = "rgba(0,0,0,0.25)"
_INK = "#111827"


def _apply_house_style(fig: go.Figure) -> go.Figure:
    """Apply the shared ambient theme in-place and return the figure."""
    fig.update_layout(
        template="plotly_white",
        font=dict(family=_FONT_FAMILY, size=13, color=_INK),
        title=dict(x=0.5, xanchor="center", font=dict(size=17)),
        colorway=list(_PALETTE),
        paper_bgcolor="white",
        plot_bgcolor="white",
        margin=dict(l=60, r=30, t=64, b=56),
        legend=dict(
            bgcolor="rgba(255,255,255,0.6)",
            bordercolor="rgba(0,0,0,0.1)",
            borderwidth=1,
        ),
    )
    # Gridlines / axis lines. matches=False is implied; we only set appearance,
    # never range or scaleanchor, so builder-set axes are preserved.
    fig.update_xaxes(
        showgrid=True, gridwidth=1, gridcolor=_GRID_COLOR,
        zeroline=False, showline=True, linecolor=_AXIS_LINE, linewidth=1,
        ticks="outside", tickcolor=_AXIS_LINE, ticklen=4,
    )
    fig.update_yaxes(
        showgrid=True, gridwidth=1, gridcolor=_GRID_COLOR,
        zeroline=False, showline=True, linecolor=_AXIS_LINE, linewidth=1,
        ticks="outside", tickcolor=_AXIS_LINE, ticklen=4,
    )
    return fig


# ---------------------------------------------------------------------------
# Significance brackets (opt-in on box / violin / strip)
#
# Statistical choices, made deliberately for a clinical audience:
#   - Default test is Mann-Whitney U (nonparametric — no normality assumption,
#     the safest default for data of unknown distribution); Welch's t-test is
#     offered as an alternative.
#   - With >2 groups we run ALL pairwise comparisons and apply a Holm-Bonferroni
#     correction across them. Drawing every pairwise bracket uncorrected would
#     inflate the false-positive rate; Holm controls family-wise error while
#     being more powerful than plain Bonferroni.
#   - Brackets are annotated with significance stars (the Prism idiom) and carry
#     the corrected p-value + test name on hover; a caption states the method.
# ---------------------------------------------------------------------------

def _holm_bonferroni(pvals: list) -> list:
    """Holm-Bonferroni step-down correction. Returns adjusted p-values (capped at 1),
    preserving input order. NaNs pass through as 1.0 (treated as non-significant)."""
    m = len(pvals)
    clean = [(1.0 if (p is None or np.isnan(p)) else float(p)) for p in pvals]
    order = sorted(range(m), key=lambda k: clean[k])
    adj = [0.0] * m
    running = 0.0
    for rank, k in enumerate(order):
        val = min(1.0, clean[k] * (m - rank))
        running = max(running, val)  # enforce monotonic non-decreasing
        adj[k] = running
    return adj


def _stars(p: float) -> str:
    if p is None or np.isnan(p):
        return "ns"
    if p <= 1e-4:
        return "****"
    if p <= 1e-3:
        return "***"
    if p <= 1e-2:
        return "**"
    if p <= 5e-2:
        return "*"
    return "ns"


def _test_label(test: str) -> str:
    return {"ttest": "Welch t-test", "mannwhitney": "Mann-Whitney U"}.get(test, test)


def _add_significance_brackets(fig: go.Figure, df: pd.DataFrame, cat_col: str,
                               val_col: str, test: str = "mannwhitney",
                               max_brackets: int = 6, orientation: str = "v") -> go.Figure:
    """
    Overlay pairwise comparison brackets on a categorical box/violin/strip.

    cat_col is the grouping column, val_col the numeric column. When
    orientation == 'v' the categories sit on the x-axis and brackets stack
    upward in y; when 'h' the categories sit on the y-axis and brackets stack
    rightward in x. The geometry is mirrored accordingly.
    """
    from itertools import combinations

    horizontal = orientation == "h"
    sub = df[[cat_col, val_col]].copy()
    sub[val_col] = pd.to_numeric(sub[val_col], errors="coerce")
    sub = sub.dropna(subset=[val_col])

    # Category positions MUST match px's: we pin category_orders in the builder
    # to exactly this order, so full_cats[k] sits at position k.
    full_cats = [c for c in pd.unique(df[cat_col].dropna())]
    groups = {c: sub.loc[sub[cat_col] == c, val_col].to_numpy(dtype=float) for c in full_cats}
    testable = [c for c in full_cats if len(groups[c]) >= 2]
    if len(testable) < 2:
        return fig

    idx_of = {c: i for i, c in enumerate(full_cats)}
    pairs = list(combinations(testable, 2))

    results = []
    for a_name, b_name in pairs:
        a, b = groups[a_name], groups[b_name]
        try:
            if test == "ttest":
                _, p = scipy_stats.ttest_ind(a, b, equal_var=False)
            else:
                _, p = scipy_stats.mannwhitneyu(a, b, alternative="two-sided")
        except ValueError:
            p = np.nan
        results.append((idx_of[a_name], idx_of[b_name], a_name, b_name, p))

    corrected = _holm_bonferroni([r[4] for r in results])
    results = [(i, j, an, bn, corrected[k]) for k, (i, j, an, bn, _) in enumerate(results)]

    # Clutter control: all brackets when few pairs, else only significant ones.
    if len(results) > max_brackets:
        draw = [r for r in results if (r[4] is not None and not np.isnan(r[4]) and r[4] < 0.05)]
    else:
        draw = results
    if not draw:
        return fig

    all_v = sub[val_col]
    vmax, vmin = float(all_v.max()), float(all_v.min())
    vr = (vmax - vmin) or (abs(vmax) or 1.0)
    tick = 0.02 * vr
    step = 0.085 * vr
    base = vmax + 0.07 * vr

    # Narrow-span brackets sit closest to the data, reducing crossings.
    draw.sort(key=lambda r: abs(r[1] - r[0]))
    for k, (i, j, an, bn, p) in enumerate(draw):
        level = base + k * step  # distance out along the value axis
        hover = f"{an} vs {bn}<br>{_test_label(test)}: p = {p:.3g}"
        if horizontal:
            # categories on y, value (brackets) extend rightward in x
            fig.add_trace(go.Scatter(
                x=[level - tick, level, level, level - tick], y=[i, i, j, j],
                mode="lines", line=dict(color="rgba(17,24,39,0.65)", width=1.2),
                hovertext=hover, hoverinfo="text", showlegend=False, cliponaxis=False,
            ))
            fig.add_annotation(
                x=level + tick * 0.4, y=(i + j) / 2, text=_stars(p),
                showarrow=False, xanchor="left", font=dict(size=13, color="#111827"),
            )
        else:
            # categories on x, value (brackets) stack upward in y
            fig.add_trace(go.Scatter(
                x=[i, i, j, j], y=[level - tick, level, level, level - tick],
                mode="lines", line=dict(color="rgba(17,24,39,0.65)", width=1.2),
                hovertext=hover, hoverinfo="text", showlegend=False, cliponaxis=False,
            ))
            fig.add_annotation(
                x=(i + j) / 2, y=level + tick * 0.4, text=_stars(p),
                showarrow=False, yanchor="bottom", font=dict(size=13, color="#111827"),
            )

    note = f"{_test_label(test)}"
    if len(testable) > 2:
        note += ", Holm-corrected"
    fig.add_annotation(
        xref="paper", yref="paper", x=0.0, y=1.0, xanchor="left", yanchor="bottom",
        text=note, showarrow=False, font=dict(size=11, color="#6b7280"),
    )
    return fig


# ---------------------------------------------------------------------------
# Simple Plotly Express wrappers
# ---------------------------------------------------------------------------

def _orient_single(params: dict):
    """
    For single-variable distribution plots (histogram, ecdf): pop 'orientation'
    and, when horizontal, move the value column from x to y so it lies along the
    vertical axis. Returns cleaned px params.
    """
    p = _clean_params(params)
    orientation = (p.pop("orientation", "v") or "v")
    if orientation == "h" and p.get("x") is not None and p.get("y") is None:
        p["y"] = p.pop("x")
    return p


def histogram(df: pd.DataFrame, params: dict) -> go.Figure:
    return px.histogram(df, **_orient_single(params))


def _grouped_with_significance(px_fn, df: pd.DataFrame, params: dict):
    """
    Shared path for box/violin/strip: build the px figure, then optionally
    overlay pairwise significance brackets.

    Brackets are drawn only when 'show_significance' is set AND there is a
    grouping with no differing colour sub-grouping (nested positions would make
    pairwise brackets between categories ambiguous). Category order is pinned so
    the bracket positions align with px's categorical placement.

    Orientation: 'v' (default) puts the value on y and groups on x; 'h' puts the
    value on x and groups on y. We always treat `x` as the grouping column and
    `y` as the value column in the params (the natural authoring convention) and
    hand `orientation='h'` to px, which flips the axes for us. Brackets are then
    drawn along the matching axis.
    """
    p = _clean_params(params)
    show_sig = bool(p.pop("show_significance", False))
    sig_test = p.pop("sig_test", "mannwhitney") or "mannwhitney"
    orientation = (p.pop("orientation", "v") or "v")
    horizontal = orientation == "h"

    # Authoring convention: x = group, y = value (regardless of orientation).
    group_col, value_col, color_col = p.get("x"), p.get("y"), p.get("color")

    if horizontal:
        # px wants the value on the x-axis and the category on the y-axis.
        p["x"], p["y"] = value_col, group_col
        p["orientation"] = "h"

    can_bracket = (
        show_sig and group_col and value_col
        and group_col in df.columns and value_col in df.columns
        and (not color_col or color_col == group_col)
    )
    if can_bracket:
        # Pin category order so our integer positions match px's placement.
        cats = [c for c in pd.unique(df[group_col].dropna())]
        co = p.get("category_orders") or {}
        co.setdefault(group_col, cats)
        p["category_orders"] = co

    fig = px_fn(df, **p)
    if can_bracket:
        _add_significance_brackets(fig, df, group_col, value_col,
                                   test=sig_test, orientation=orientation)
    return fig, p


def box(df: pd.DataFrame, params: dict) -> go.Figure:
    fig, _ = _grouped_with_significance(px.box, df, params)
    return fig


def violin(df: pd.DataFrame, params: dict) -> go.Figure:
    fig, _ = _grouped_with_significance(px.violin, df, params)
    return fig


def strip(df: pd.DataFrame, params: dict) -> go.Figure:
    fig, _ = _grouped_with_significance(px.strip, df, params)
    # px.strip emits box-type traces; scope jitter to them so it doesn't hit
    # any significance-bracket scatter traces we may have added.
    fig.update_traces(jitter=0.3, selector=dict(type="box"))
    return fig


def ecdf(df: pd.DataFrame, params: dict) -> go.Figure:
    return px.ecdf(df, **_orient_single(params))


def line(df: pd.DataFrame, params: dict) -> go.Figure:
    return px.line(df, **_clean_params(params))


def bar(df: pd.DataFrame, params: dict) -> go.Figure:
    p = _clean_params(params)
    horizontal = (p.pop('orientation', 'v') or 'v') == 'h'
    x_col = p.get('x')
    y_col = p.get('y')
    color_col = p.get('color')
    group_cols = [x_col] + ([color_col] if color_col else [])
    if not y_col:
        agg_df = df.groupby(group_cols).size().reset_index(name='Count')
        value_col = 'Count'
    else:
        agg_df = df.groupby(group_cols, as_index=False)[y_col].sum()
        value_col = y_col
    # category = x_col, value = value_col. Swap axes for horizontal.
    if horizontal:
        p['x'], p['y'] = value_col, x_col
        p['orientation'] = 'h'
    else:
        p['x'], p['y'] = x_col, value_col
    return px.bar(agg_df, **p)


def scatter(df: pd.DataFrame, params: dict) -> go.Figure:
    p = _clean_params(params)
    show_marginals = params.get('show_marginals', False)
    marginal_type = params.get('marginal_type', 'violin')
    p.pop('show_marginals', None)
    p.pop('marginal_type', None)
    if show_marginals:
        p['marginal_x'] = marginal_type
        p['marginal_y'] = marginal_type
    fig = px.scatter(df, **p)
    fig.update_traces(
        marker=dict(size=8, opacity=0.72, line=dict(width=0.6, color='white')),
        selector=dict(mode='markers')
    )
    fig.update_layout(
        template='plotly_white', dragmode='select',
        plot_bgcolor='white', paper_bgcolor='white',
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.08)', zeroline=False)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.08)', zeroline=False)
    return fig


def regression_scatter(df: pd.DataFrame, x_col: str, y_col: str,
                       slope: float, intercept: float, r_squared: float) -> go.Figure:
    """Scatter of y vs x with the fitted least-squares line and its equation."""
    import plotly.graph_objects as go

    data = df[[x_col, y_col]].apply(pd.to_numeric, errors='coerce').dropna()
    xs = data[x_col].to_numpy(dtype=float)
    ys = data[y_col].to_numpy(dtype=float)

    fig = go.Figure()
    # Observed points
    fig.add_trace(go.Scatter(
        x=xs, y=ys, mode='markers', name='Observed',
        marker=dict(size=8, opacity=0.72, color='#2563eb',
                    line=dict(width=0.6, color='white')),
    ))
    # Fitted line spanning the observed x-range
    if xs.size >= 2:
        x_line = np.linspace(xs.min(), xs.max(), 100)
        y_line = slope * x_line + intercept
        sign = '+' if intercept >= 0 else '−'
        eqn = f"y = {slope:.4g}·x {sign} {abs(intercept):.4g}   (R² = {r_squared:.4f})"
        fig.add_trace(go.Scatter(
            x=x_line, y=y_line, mode='lines', name='Fitted line',
            line=dict(color='#dc2626', width=2.5),
            hovertemplate=eqn + '<extra></extra>',
        ))
        fig.add_annotation(
            xref='paper', yref='paper', x=0.02, y=0.98,
            text=eqn, showarrow=False, align='left',
            font=dict(size=12, color='#0b1f3a'),
            bgcolor='rgba(255,255,255,0.85)', bordercolor='#c9d6ea', borderwidth=1,
            borderpad=6,
        )

    fig.update_layout(
        title=f"{y_col} vs {x_col}", title_x=0.5,
        template='plotly_white', plot_bgcolor='white', paper_bgcolor='white',
        xaxis_title=x_col, yaxis_title=y_col,
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
    )
    fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.08)', zeroline=False)
    fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(0,0,0,0.08)', zeroline=False)
    return fig


# ---------------------------------------------------------------------------
# Custom figures
# ---------------------------------------------------------------------------

def qq(df: pd.DataFrame, params: dict) -> go.Figure:
    col = params.get('x')
    color_col = params.get('color') or None
    if not col or col not in df.columns:
        raise ValueError(f"Column '{col}' not found")
    groups = df[color_col].dropna().unique() if color_col and color_col in df.columns else [None]
    fig = go.Figure()
    for i, grp in enumerate(groups):
        subset = df[df[color_col] == grp][col].dropna() if grp is not None else df[col].dropna()
        if len(subset) < 3:
            continue
        (osm, osr), (slope, intercept, _) = scipy_stats.probplot(subset, dist='norm')
        name = str(grp) if grp is not None else col
        color = _PALETTE[i % len(_PALETTE)]
        fig.add_trace(go.Scatter(
            x=list(osm), y=list(osr), mode='markers', name=name,
            marker=dict(color=color, size=6, opacity=0.7)
        ))
        x_line = [min(osm), max(osm)]
        y_line = [slope * x + intercept for x in x_line]
        fig.add_trace(go.Scatter(
            x=x_line, y=y_line, mode='lines', showlegend=False,
            name=f'{name} (ref)', line=dict(color=color, width=1.5, dash='dash')
        ))
    fig.update_layout(
        xaxis_title='Theoretical Quantiles', yaxis_title='Sample Quantiles',
        title=f'QQ Plot — {col}'
    )
    return fig


def density(df: pd.DataFrame, params: dict) -> go.Figure:
    col = params.get('x')
    color_col = params.get('color') or None
    horizontal = (params.get('orientation') or 'v') == 'h'
    if not col or col not in df.columns:
        raise ValueError(f"Column '{col}' not found")
    groups = df[color_col].dropna().unique() if color_col and color_col in df.columns else [None]
    fig = go.Figure()
    for i, grp in enumerate(groups):
        subset = df[df[color_col] == grp][col].dropna() if grp is not None else df[col].dropna()
        if len(subset) < 3:
            continue
        kde = scipy_stats.gaussian_kde(subset)
        axis_vals = np.linspace(subset.min(), subset.max(), 300)
        dens_vals = kde(axis_vals)
        name = str(grp) if grp is not None else col
        color = _PALETTE[i % len(_PALETTE)]
        if horizontal:
            fig.add_trace(go.Scatter(
                x=list(dens_vals), y=list(axis_vals), mode='lines',
                name=name, fill='tozerox',
                line=dict(color=color), fillcolor=_rgba(color, 0.18)
            ))
        else:
            fig.add_trace(go.Scatter(
                x=list(axis_vals), y=list(dens_vals), mode='lines',
                name=name, fill='tozeroy',
                line=dict(color=color), fillcolor=_rgba(color, 0.18)
            ))
    if horizontal:
        fig.update_layout(xaxis_title='Density', yaxis_title=col, title=f'Density Plot — {col}')
    else:
        fig.update_layout(xaxis_title=col, yaxis_title='Density', title=f'Density Plot — {col}')
    return fig


def paired(df: pd.DataFrame, params: dict) -> go.Figure:
    col1 = params.get('x')
    col2 = params.get('y')
    color_col = params.get('color') or None
    if not col1 or not col2 or col1 not in df.columns or col2 not in df.columns:
        raise ValueError("Both columns must be specified and present in the data")
    cols = [col1, col2] + ([color_col] if color_col and color_col in df.columns else [])
    paired_df = df[cols].dropna()
    fig = go.Figure()
    if color_col and color_col in paired_df.columns:
        for i, grp in enumerate(paired_df[color_col].unique()):
            sub = paired_df[paired_df[color_col] == grp]
            color = _PALETTE[i % len(_PALETTE)]
            for _, row in sub.iterrows():
                fig.add_trace(go.Scatter(
                    x=[col1, col2], y=[row[col1], row[col2]],
                    mode='lines+markers', showlegend=False,
                    line=dict(color=color, width=1), marker=dict(size=6, color=color)
                ))
            fig.add_trace(go.Scatter(
                x=[None], y=[None], mode='lines', name=str(grp),
                line=dict(color=color, width=2)
            ))
    else:
        for _, row in paired_df.iterrows():
            fig.add_trace(go.Scatter(
                x=[col1, col2], y=[row[col1], row[col2]],
                mode='lines+markers', showlegend=False,
                line=dict(color='rgba(70,130,180,0.5)', width=1),
                marker=dict(size=6, color='steelblue')
            ))
    fig.update_layout(
        xaxis_title='Measurement', yaxis_title='Value',
        title=f'Paired Plot — {col1} vs {col2}'
    )
    return fig


def _km_estimate(T, E):
    """
    Kaplan-Meier estimate for one group from event times T and event flags E
    (1 = event, 0 = censored). Returns a dict with the step coordinates, a
    correct Greenwood 95% CI, the at-risk count entering each event time, the
    censoring times, and the median survival (np.nan if not reached).

    Bounded by the number of unique times, so the serialised curve stays small
    regardless of N.
    """
    T = np.asarray(T, dtype=float)
    E = np.asarray(E, dtype=float)
    order = np.argsort(T, kind="mergesort")
    T, E = T[order], E[order]
    n0 = len(T)

    uniq = np.unique(T)
    times = [0.0]
    surv = [1.0]
    lower = [1.0]
    upper = [1.0]
    risk_at = []          # (time, n_at_risk_entering)
    surv_at_event = {}    # time -> S(t) for placing censoring marks / median

    S = 1.0
    cum_var = 0.0         # running Greenwood sum  Σ d / (n (n-d))
    median = np.nan

    for t in uniq:
        at_risk = int(np.sum(T >= t))          # entering time t
        d = int(np.sum(E[T == t] == 1))        # events at t
        risk_at.append((float(t), at_risk))
        if at_risk > 0 and d > 0:
            S *= (1.0 - d / at_risk)
            if at_risk - d > 0:
                cum_var += d / (at_risk * (at_risk - d))
        # Log-transformed Greenwood 95% CI (matches lifelines / R survfit
        # default): CI on log(-log S), back-transformed, so it stays in [0,1].
        if 0.0 < S < 1.0 and cum_var > 0:
            se_loglog = np.sqrt(cum_var) / np.log(S)
            c = 1.96 * se_loglog
            lo = S ** np.exp(c)
            hi = S ** np.exp(-c)
        else:
            lo = hi = S
        times.append(float(t))
        surv.append(float(S))
        lower.append(float(max(0.0, min(lo, hi))))
        upper.append(float(min(1.0, max(lo, hi))))
        surv_at_event[float(t)] = float(S)
        if np.isnan(median) and S <= 0.5:
            median = float(t)

    # Censoring times (E == 0), with the survival level at each for plotting.
    cens_t = T[E == 0]
    cens_times, cens_surv = [], []
    for ct in cens_t:
        # survival just after the most recent event time <= ct
        prior = [tt for tt in surv_at_event if tt <= ct]
        s_level = surv_at_event[max(prior)] if prior else 1.0
        cens_times.append(float(ct))
        cens_surv.append(float(s_level))

    return {
        "times": times, "surv": surv, "lower": lower, "upper": upper,
        "risk_at": risk_at, "cens_times": cens_times, "cens_surv": cens_surv,
        "median": median, "n": n0,
    }


def _logrank_p(groups_TE):
    """
    Multi-group log-rank test. groups_TE is a list of (T, E) arrays. Returns
    (chi2, df, p) or None if fewer than two groups. Validated against lifelines.
    """
    if len(groups_TE) < 2:
        return None
    all_T = np.concatenate([np.asarray(T, float) for T, _ in groups_TE])
    all_E = np.concatenate([np.asarray(E, float) for _, E in groups_TE])
    event_times = np.unique(all_T[all_E == 1])
    if len(event_times) == 0:
        return None

    k = len(groups_TE)
    O = np.zeros(k)            # observed events per group
    Ehat = np.zeros(k)         # expected events per group
    # Variance-covariance for groups 0..k-2 (drop last for full rank).
    V = np.zeros((k - 1, k - 1))

    Ts = [np.asarray(T, float) for T, _ in groups_TE]
    Es = [np.asarray(E, float) for _, E in groups_TE]

    for t in event_times:
        n_j = np.array([np.sum(Ts[j] >= t) for j in range(k)], dtype=float)
        d_j = np.array([np.sum((Ts[j] == t) & (Es[j] == 1)) for j in range(k)], dtype=float)
        n = n_j.sum()
        d = d_j.sum()
        if n <= 1:
            continue
        O += d_j
        Ehat += d * n_j / n
        # Hypergeometric variance contribution.
        factor = d * (n - d) / (n * n * (n - 1))
        for a in range(k - 1):
            for b in range(k - 1):
                cov = factor * (n * (n_j[a] if a == b else 0.0) - n_j[a] * n_j[b])
                V[a, b] += cov

    diff = (O - Ehat)[:k - 1]
    try:
        chi2 = float(diff @ np.linalg.solve(V, diff))
    except np.linalg.LinAlgError:
        return None
    dfree = k - 1
    p = float(scipy_stats.chi2.sf(chi2, dfree))
    return chi2, dfree, p


def kaplan_meier(df: pd.DataFrame, time_col: str, event_col: str, group_col: str = None,
                 show_risk_table: bool = True, show_censoring: bool = True,
                 show_median: bool = True) -> go.Figure:
    """
    Publication-grade Kaplan-Meier curve: stepped survival with a Greenwood 95%
    CI band, censoring tick marks, median-survival reference lines, an at-risk
    table beneath the axis, and (for >1 group) a log-rank p-value. No lifelines
    dependency. All series are bounded by the number of unique times.
    """
    if not time_col or time_col not in df.columns:
        raise ValueError(f"Survival time column '{time_col}' not found")
    if not event_col or event_col not in df.columns:
        raise ValueError(f"Event/status column '{event_col}' not found")

    if group_col and group_col in df.columns:
        groups = [g for g in pd.unique(df[group_col].dropna())]
    else:
        groups = [None]

    # Gather per-group estimates.
    ests, names, colors, groups_TE = [], [], [], []
    for i, grp in enumerate(groups):
        sub = (df[df[group_col] == grp] if grp is not None else df)[[time_col, event_col]].dropna()
        if sub.empty:
            continue
        T = sub[time_col].to_numpy(dtype=float)
        E = sub[event_col].astype(float).to_numpy()
        ests.append(_km_estimate(T, E))
        names.append(str(grp) if grp is not None else "Overall")
        colors.append(_PALETTE[i % len(_PALETTE)])
        groups_TE.append((T, E))
    if not ests:
        raise ValueError("No data to plot after dropping missing values")

    # Risk-table time ticks: evenly spaced across the observed range.
    t_max = max(max(e["times"]) for e in ests)
    n_ticks = 6
    risk_ticks = [round(x, 2) for x in np.linspace(0, t_max, n_ticks)]

    # Build the figure, with a risk-table subplot if requested.
    if show_risk_table:
        fig = make_subplots(
            rows=2, cols=1, shared_xaxes=True,
            row_heights=[0.76, 0.24], vertical_spacing=0.06,
        )
        curve_row = 1
    else:
        fig = go.Figure()
        curve_row = None

    def _add(trace, row):
        if row is None:
            fig.add_trace(trace)
        else:
            fig.add_trace(trace, row=row, col=1)

    for est, name, color in zip(ests, names, colors):
        # CI band.
        _add(go.Scatter(
            x=est["times"] + est["times"][::-1],
            y=est["upper"] + est["lower"][::-1],
            fill="toself", fillcolor=_rgba(color, 0.15),
            line=dict(width=0), showlegend=False, hoverinfo="skip", name=f"{name} CI",
        ), curve_row)
        # Step curve.
        _add(go.Scatter(
            x=est["times"], y=est["surv"], mode="lines", name=name,
            line=dict(shape="hv", color=color, width=2),
            hovertemplate="t=%{x}<br>S=%{y:.3f}<extra>" + name + "</extra>",
        ), curve_row)
        # Censoring marks (thin vertical ticks), capped for very large N.
        if show_censoring and est["cens_times"]:
            ct, cs = est["cens_times"], est["cens_surv"]
            if len(ct) > 400:
                idx = np.linspace(0, len(ct) - 1, 400).astype(int)
                ct = [ct[k] for k in idx]; cs = [cs[k] for k in idx]
            _add(go.Scatter(
                x=ct, y=cs, mode="markers", name=f"{name} censored",
                marker=dict(symbol="line-ns", size=8, color=color,
                            line=dict(width=1.4, color=color)),
                showlegend=False, hoverinfo="skip",
            ), curve_row)
        # Median survival reference lines.
        if show_median and not np.isnan(est["median"]):
            m = est["median"]
            _add(go.Scatter(
                x=[0, m, m], y=[0.5, 0.5, 0.0], mode="lines",
                line=dict(color=color, width=1, dash="dot"),
                showlegend=False, hoverinfo="skip", name=f"{name} median",
            ), curve_row)

    # Log-rank annotation (>1 group).
    lr = _logrank_p(groups_TE) if len(groups_TE) > 1 else None
    title = "Kaplan-Meier Survival Curve"
    if lr is not None:
        _, _, p = lr
        ptxt = "p < 0.001" if p < 1e-3 else f"p = {p:.3f}"
        fig.add_annotation(
            xref="paper", yref="paper", x=0.98, y=0.98, xanchor="right", yanchor="top",
            text=f"Log-rank {ptxt}", showarrow=False,
            font=dict(size=12, color="#111827"),
            bgcolor="rgba(255,255,255,0.85)", bordercolor="rgba(0,0,0,0.15)", borderwidth=1,
        )

    # Risk-table cells: n-at-risk per group at each tick (subjects with T >= tt).
    if show_risk_table:
        row_y = list(range(len(ests)))[::-1]  # first group on top
        for (T, _E), name, color, y in zip(groups_TE, names, colors, row_y):
            for tt in risk_ticks:
                n_risk = int(np.sum(np.asarray(T, float) >= tt))
                fig.add_annotation(
                    x=tt, y=y, xref="x2", yref="y2", text=str(n_risk),
                    showarrow=False, font=dict(size=11, color="#374151"),
                )
        fig.update_yaxes(
            tickmode="array", tickvals=row_y, ticktext=names,
            range=[-0.6, len(ests) - 0.4], showgrid=False, zeroline=False,
            title_text="At risk", row=2, col=1,
        )
        fig.update_xaxes(range=[0, t_max * 1.02], tickvals=risk_ticks, row=2, col=1,
                         title_text=time_col)
        fig.update_xaxes(range=[0, t_max * 1.02], row=1, col=1)
        fig.update_yaxes(title_text="Survival Probability", range=[0, 1.05], row=1, col=1)
    else:
        fig.update_xaxes(title_text=time_col, range=[0, t_max * 1.02])
        fig.update_yaxes(title_text="Survival Probability", range=[0, 1.05])

    fig.update_layout(title=title, height=620 if show_risk_table else 480)
    _apply_house_style(fig)
    if show_risk_table:
        # House style turns gridlines on for every axis; keep them off the table.
        fig.update_xaxes(showgrid=False, row=2, col=1)
        fig.update_yaxes(showgrid=False, row=2, col=1)
    return fig


def correlation_heatmap(matrix_table: dict, method_name: str) -> go.Figure:
    """Builds a correlation heatmap from a matrix_table dict (the format correlation.py returns)."""
    headers = matrix_table['headers'][1:]  # drop empty first col
    values = [
        [row[i + 1] if row[i + 1] is not None else 0 for i in range(len(headers))]
        for row in matrix_table['data']
    ]
    fig = px.imshow(
        values, x=headers, y=headers,
        color_continuous_scale='RdBu_r', zmin=-1, zmax=1,
        text_auto='.2f',
        title=f'Correlation Heatmap — {method_name}'
    )
    _apply_house_style(fig)
    # Gridlines are wrong over a heatmap's cells — house style turns them on by
    # default, so switch them back off here.
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=False)
    return fig


def _numeric_columns(df: pd.DataFrame, requested) -> list:
    """Resolve a column selection to those present and numeric; default to all numeric."""
    requested = [c for c in (requested or []) if c]   # drop '' from empty multiselects
    if requested:
        cols = [c for c in requested if c in df.columns]
    else:
        cols = list(df.columns)
    out = []
    for c in cols:
        s = pd.to_numeric(df[c], errors='coerce')
        if s.notna().sum() >= 2:
            out.append(c)
    return out


def corr_heatmap(df: pd.DataFrame, params: dict) -> go.Figure:
    """
    Correlation heatmap directly from a DataFrame (Graphic-menu entry point).

    Distinct from correlation_heatmap(matrix_table, ...), which serves the
    correlation *analysis*. Params: columns (multi-select; default all numeric),
    method ('pearson' | 'spearman' | 'kendall'). Optionally clustered ordering.
    """
    method = (params.get('method') or 'pearson').lower()
    if method not in ('pearson', 'spearman', 'kendall'):
        method = 'pearson'
    cols = _numeric_columns(df, params.get('columns'))
    if len(cols) < 2:
        raise ValueError("Need at least two numeric columns for a correlation heatmap")

    num = df[cols].apply(pd.to_numeric, errors='coerce')
    corr = num.corr(method=method)

    # Optional clustered ordering (groups correlated variables visually).
    if params.get('cluster'):
        order = _cluster_order(corr.values)
        corr = corr.iloc[order, :].iloc[:, order]

    labels = list(corr.columns)
    fig = px.imshow(
        corr.values, x=labels, y=labels,
        color_continuous_scale='RdBu_r', zmin=-1, zmax=1,
        text_auto='.2f',
        title=f'Correlation Heatmap — {method.capitalize()}',
    )
    fig.update_traces(
        hovertemplate='%{y} vs %{x}<br>r = %{z:.3f}<extra></extra>'
    )
    _apply_house_style(fig)
    fig.update_xaxes(showgrid=False, tickangle=45)
    fig.update_yaxes(showgrid=False, autorange='reversed')
    fig.update_layout(height=max(360, 60 + 28 * len(labels)))
    return fig


def _cluster_order(matrix: np.ndarray) -> list:
    """
    Order rows/cols so correlated variables sit together, using average-linkage
    hierarchical clustering on a correlation distance (1 - |r|). Falls back to
    the identity order if SciPy's clustering isn't available.
    """
    try:
        from scipy.cluster.hierarchy import linkage, leaves_list
        from scipy.spatial.distance import squareform
        dist = 1.0 - np.abs(matrix)
        np.fill_diagonal(dist, 0.0)
        # Symmetrize defensively, then condense.
        dist = (dist + dist.T) / 2.0
        condensed = squareform(dist, checks=False)
        Z = linkage(condensed, method='average')
        return list(leaves_list(Z))
    except Exception:
        return list(range(matrix.shape[0]))


def scatter_matrix(df: pd.DataFrame, params: dict) -> go.Figure:
    """
    Scatter-plot matrix (pairplot) for exploring several variables at once.

    Params: columns (multi-select; default all numeric, capped for readability),
    color (optional grouping). Diagonal shows histograms.
    """
    cols = _numeric_columns(df, params.get('columns'))
    if len(cols) < 2:
        raise ValueError("Need at least two numeric columns for a scatter matrix")
    # A matrix grows as k^2 panels; cap to keep it legible and bounded.
    MAX_DIMS = 6
    truncated = len(cols) > MAX_DIMS
    cols = cols[:MAX_DIMS]

    color = params.get('color')
    color = color if (color and color in df.columns) else None

    use_cols = cols + ([color] if color and color not in cols else [])
    sub = df[use_cols].copy()
    for c in cols:
        sub[c] = pd.to_numeric(sub[c], errors='coerce')
    sub = sub.dropna(subset=cols)
    if sub.empty:
        raise ValueError("No complete numeric rows to plot")

    fig = px.scatter_matrix(sub, dimensions=cols, color=color)
    fig.update_traces(diagonal_visible=False, showupperhalf=False,
                      marker=dict(size=4, opacity=0.55, line=dict(width=0.3, color='white')))
    note = f"  (first {MAX_DIMS} numeric columns)" if truncated else ""
    fig.update_layout(title=f"Scatter Matrix{note}",
                      height=170 * len(cols) + 120, width=170 * len(cols) + 120)
    return _apply_house_style(fig)


def forest_plot(model_payload: dict) -> go.Figure | None:
    """
    Build a forest plot from a serialized regression result (the dict produced
    by serializers.serialize_model_result). Pure: consumes plain JSON-safe data,
    no statsmodels objects.

    Chooses the estimate scale from model_kind:
      - 'ols' / 'mixed' → coefficients (β), reference line at 0, linear axis
      - 'logit'         → odds ratios = exp(β), reference at 1, log axis
      - 'cox'           → hazard ratios (already exp scale), reference at 1, log axis

    Returns None when there is nothing meaningful to draw (failed model, no
    predictors, intercept only).
    """
    kind = (model_payload or {}).get('model_kind')
    if kind not in ('ols', 'mixed', 'logit', 'cox'):
        return None

    _INTERCEPTS = {'const', 'Intercept', 'intercept'}

    def _ci_map(records):
        """[{variable, ci_lower, ci_upper}, ...] → {variable: (lower, upper)}."""
        out = {}
        for r in records or []:
            name = r.get('variable')
            if name is None:
                continue
            out[str(name)] = (r.get('ci_lower'), r.get('ci_upper'))
        return out

    if kind == 'cox':
        estimates = model_payload.get('hazard_ratios') or {}
        ci_map = _ci_map(model_payload.get('hr_conf_int'))
        ref, use_log = 1.0, True
        x_title = 'Hazard Ratio (95% CI)'
        transform = lambda v: v
    elif kind == 'logit':
        estimates = model_payload.get('params') or {}
        ci_map = _ci_map(model_payload.get('conf_int'))
        ref, use_log = 1.0, True
        x_title = 'Odds Ratio (95% CI)'
        transform = lambda v: float(np.exp(v))
    else:  # ols / mixed
        estimates = model_payload.get('params') or {}
        ci_map = _ci_map(model_payload.get('conf_int'))
        ref, use_log = 0.0, False
        x_title = 'Coefficient (β, 95% CI)'
        transform = lambda v: v

    names, est, lower, upper, colors, hovers = [], [], [], [], [], []
    SIG, NONSIG = '#2563eb', '#9ca3af'

    for name, raw in estimates.items():
        if str(name) in _INTERCEPTS or raw is None:
            continue
        try:
            point = transform(float(raw))
        except (TypeError, ValueError, OverflowError):
            continue
        if not np.isfinite(point):
            continue

        lo_raw, hi_raw = ci_map.get(str(name), (None, None))
        lo = hi = None
        if lo_raw is not None and hi_raw is not None:
            try:
                lo, hi = transform(float(lo_raw)), transform(float(hi_raw))
                if not (np.isfinite(lo) and np.isfinite(hi)):
                    lo = hi = None
            except (TypeError, ValueError, OverflowError):
                lo = hi = None

        # Significant when the CI excludes the reference line.
        significant = lo is not None and (lo > ref or hi < ref)
        names.append(str(name))
        est.append(point)
        lower.append(lo if lo is not None else point)
        upper.append(hi if hi is not None else point)
        colors.append(SIG if significant else NONSIG)
        if lo is not None:
            hovers.append(f"{name}<br>{point:.3g} ({lo:.3g}, {hi:.3g})")
        else:
            hovers.append(f"{name}<br>{point:.3g}")

    if not names:
        return None

    # Log axis is safe only with strictly positive whisker endpoints.
    if use_log and any(l <= 0 for l in lower):
        use_log = False

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=est, y=names, mode='markers',
        marker=dict(size=9, color=colors, line=dict(width=0.5, color='white')),
        error_x=dict(
            type='data', symmetric=False,
            array=[u - e for u, e in zip(upper, est)],
            arrayminus=[e - l for l, e in zip(lower, est)],
            color='rgba(75,85,99,0.55)', thickness=1.4, width=4,
        ),
        hovertext=hovers, hoverinfo='text', showlegend=False,
    ))
    fig.add_vline(x=ref, line_dash='dash', line_color='rgba(0,0,0,0.45)', line_width=1.2)

    outcome = model_payload.get('outcome_name')
    title = f"Forest Plot — {outcome}" if outcome else "Forest Plot"
    fig.update_layout(
        title=title,
        xaxis_title=x_title,
        yaxis=dict(autorange='reversed'),
        height=max(220, 70 + 40 * len(names)),
        margin=dict(l=10, r=20, t=60, b=40),
    )
    if use_log:
        fig.update_xaxes(type='log')
    return _apply_house_style(fig)


def roc_plot(roc_data: dict) -> go.Figure | None:
    """
    Build an ROC curve from the small dict produced by
    regression.roc_curve_data: {fpr, tpr, auc, n_pos, n_neg}. Pure — no
    per-observation data, no statsmodels objects.

    Returns None when there is nothing to draw.
    """
    if not roc_data:
        return None
    fpr = roc_data.get('fpr') or []
    tpr = roc_data.get('tpr') or []
    if len(fpr) < 2 or len(tpr) < 2:
        return None

    auc = roc_data.get('auc')
    auc_txt = f"AUC = {auc:.3f}" if isinstance(auc, (int, float)) else "AUC = n/a"
    # If a cross-validated AUC was attached at fit time, show it too: the plain
    # AUC is apparent (in-sample, optimistic); CV-AUC is the honest estimate.
    cv = roc_data.get('cv_auc')
    if isinstance(cv, (int, float)):
        auc_txt = f"AUC = {auc:.3f} (apparent)<br>CV-AUC = {cv:.3f}" if isinstance(auc, (int, float)) else f"CV-AUC = {cv:.3f}"

    fig = go.Figure()
    # Chance diagonal.
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1], mode='lines', name='Chance',
        line=dict(color='rgba(0,0,0,0.35)', width=1.2, dash='dash'),
        hoverinfo='skip', showlegend=False,
    ))
    # ROC curve, filled to the diagonal-free baseline for a clear read.
    fig.add_trace(go.Scatter(
        x=fpr, y=tpr, mode='lines', name='ROC',
        line=dict(color=_PALETTE[0], width=2.5, shape='hv'),
        fill='tozeroy', fillcolor=_rgba(_PALETTE[0], 0.12),
        hovertemplate='FPR %{x:.3f}<br>TPR %{y:.3f}<extra></extra>',
        showlegend=False,
    ))
    fig.add_annotation(
        x=0.97, y=0.05, xref='x', yref='y', xanchor='right', yanchor='bottom',
        text=auc_txt, showarrow=False,
        font=dict(size=14, color='#111827'),
        bgcolor='rgba(255,255,255,0.85)', bordercolor='rgba(0,0,0,0.15)', borderwidth=1,
    )
    fig.update_layout(
        title='ROC Curve',
        xaxis=dict(title='False Positive Rate (1 − Specificity)', range=[0, 1], constrain='domain'),
        yaxis=dict(title='True Positive Rate (Sensitivity)', range=[0, 1.02],
                   scaleanchor='x', scaleratio=1),
        margin=dict(l=10, r=20, t=60, b=40),
        height=460,
    )
    _apply_house_style(fig)
    # Re-assert the unit-square aspect that house style intentionally leaves
    # alone. update_*axes merge per-key, so titles set above are preserved.
    fig.update_xaxes(range=[0, 1], constrain='domain')
    fig.update_yaxes(range=[0, 1.02], scaleanchor='x', scaleratio=1)
    return fig


def _binned_trend(x, y, n_bins: int = 12):
    """Coarse monotone-x trend (binned means) — a LOWESS stand-in with no extra deps."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    if len(x) < 4:
        return None
    order = np.argsort(x)
    x, y = x[order], y[order]
    edges = np.linspace(x[0], x[-1], min(n_bins, len(x)) + 1)
    bx, by = [], []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        m = (x >= lo) & (x <= hi if i == len(edges) - 2 else x < hi)
        if m.any():
            bx.append(float(x[m].mean()))
            by.append(float(y[m].mean()))
    return (bx, by) if len(bx) >= 2 else None


def diagnostic_panel(diag: dict) -> go.Figure | None:
    """
    Four-panel OLS regression diagnostics from the bounded dict produced by
    regression.ols_diagnostic_data:
        (1) Residuals vs Fitted   (2) Normal QQ of standardised residuals
        (3) Scale-Location        (4) Residuals vs Leverage (+ Cook's contours)
    Pure — consumes plain arrays, no statsmodels objects.
    """
    if not diag:
        return None
    fitted = diag.get("fitted") or []
    resid = diag.get("resid") or []
    if len(fitted) < 3 or len(resid) < 3:
        return None

    std_resid = diag.get("std_resid") or []
    leverage = diag.get("leverage") or []
    cooks = diag.get("cooks") or []
    qt = diag.get("qq_theoretical") or []
    qs = diag.get("qq_sample") or []

    pt = dict(size=6, color=_PALETTE[0], opacity=0.6, line=dict(width=0.4, color='white'))
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Residuals vs Fitted", "Normal Q–Q",
            "Scale–Location", "Residuals vs Leverage",
        ),
        horizontal_spacing=0.12, vertical_spacing=0.16,
    )

    # (1) Residuals vs Fitted, with a zero line and a binned trend.
    fig.add_trace(go.Scatter(x=fitted, y=resid, mode='markers', marker=pt,
                             hoverinfo='skip', showlegend=False), row=1, col=1)
    fig.add_hline(y=0, line_dash='dash', line_color='rgba(0,0,0,0.4)', row=1, col=1)
    tr = _binned_trend(fitted, resid)
    if tr:
        fig.add_trace(go.Scatter(x=tr[0], y=tr[1], mode='lines',
                                 line=dict(color='#dc2626', width=1.6),
                                 hoverinfo='skip', showlegend=False), row=1, col=1)

    # (2) Normal Q–Q with a 45° reference through the quantiles.
    if len(qt) >= 3 and len(qs) >= 3:
        fig.add_trace(go.Scatter(x=qt, y=qs, mode='markers', marker=pt,
                                 hoverinfo='skip', showlegend=False), row=1, col=2)
        lo = min(min(qt), min(qs)); hi = max(max(qt), max(qs))
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode='lines',
                                 line=dict(color='rgba(0,0,0,0.4)', width=1.2, dash='dash'),
                                 hoverinfo='skip', showlegend=False), row=1, col=2)

    # (3) Scale-Location: sqrt(|standardised residual|) vs fitted.
    if std_resid:
        sl = list(np.sqrt(np.abs(np.asarray(std_resid, dtype=float))))
        fig.add_trace(go.Scatter(x=fitted, y=sl, mode='markers', marker=pt,
                                 hoverinfo='skip', showlegend=False), row=2, col=1)
        tr2 = _binned_trend(fitted, sl)
        if tr2:
            fig.add_trace(go.Scatter(x=tr2[0], y=tr2[1], mode='lines',
                                     line=dict(color='#dc2626', width=1.6),
                                     hoverinfo='skip', showlegend=False), row=2, col=1)

    # (4) Residuals vs Leverage with Cook's-distance contours.
    if leverage and std_resid:
        sizes = None
        if cooks:
            c = np.asarray(cooks, dtype=float)
            cmax = c.max() if c.size and c.max() > 0 else 1.0
            sizes = list(6 + 14 * np.sqrt(np.clip(c / cmax, 0, 1)))
        marker4 = dict(color=_PALETTE[0], opacity=0.6, line=dict(width=0.4, color='white'))
        if sizes:
            marker4['size'] = sizes
        else:
            marker4['size'] = 6
        fig.add_trace(go.Scatter(
            x=leverage, y=std_resid, mode='markers', marker=marker4,
            hovertemplate='leverage %{x:.3f}<br>std resid %{y:.2f}<extra></extra>',
            showlegend=False), row=2, col=2)
        fig.add_hline(y=0, line_dash='dash', line_color='rgba(0,0,0,0.4)', row=2, col=2)

        # Cook's distance contours at 0.5 and 1.0: std_resid = ±sqrt(D*p*(1-h)/h)
        p = max(int(diag.get("n_params", 2)), 1)
        lev_arr = np.asarray(leverage, dtype=float)
        h_max = min(float(lev_arr.max()) if lev_arr.size else 0.2, 0.99)
        h_grid = np.linspace(max(float(lev_arr.min()), 1e-3), max(h_max, 1e-2), 50)
        for D, dash in [(0.5, 'dot'), (1.0, 'dash')]:
            with np.errstate(divide='ignore', invalid='ignore'):
                band = np.sqrt(D * p * (1 - h_grid) / h_grid)
            for sign in (1, -1):
                fig.add_trace(go.Scatter(
                    x=list(h_grid), y=list(sign * band), mode='lines',
                    line=dict(color='rgba(220,38,38,0.5)', width=1, dash=dash),
                    hoverinfo='skip', showlegend=False), row=2, col=2)

    fig.update_xaxes(title_text='Fitted values', row=1, col=1)
    fig.update_yaxes(title_text='Residuals', row=1, col=1)
    fig.update_xaxes(title_text='Theoretical quantiles', row=1, col=2)
    fig.update_yaxes(title_text='Std. residuals', row=1, col=2)
    fig.update_xaxes(title_text='Fitted values', row=2, col=1)
    fig.update_yaxes(title_text='√|Std. residuals|', row=2, col=1)
    fig.update_xaxes(title_text='Leverage', row=2, col=2)
    fig.update_yaxes(title_text='Std. residuals', row=2, col=2)

    _apply_house_style(fig)

    subtitle = ""
    if diag.get("sampled"):
        kept = diag.get("n_influential_kept", 0)
        subtitle = (f"  (showing {diag.get('n_shown')} of {diag.get('n_obs')} points; "
                    f"all {kept} high-influence points retained)")
    fig.update_layout(
        title=f"Regression Diagnostics{subtitle}",
        height=720, margin=dict(l=10, r=20, t=70, b=40),
    )
    return fig


def estimation_plot(df: pd.DataFrame, params: dict) -> go.Figure:
    """
    Two-group estimation (Cumming-style) plot.

    Left panel: the raw data of both groups (jittered) with each group's mean
    and a gapped 95% CI. Right panel: the bootstrap distribution of the mean
    DIFFERENCE (test − control) on its own axis centred at zero, with the
    observed difference and its 95% CI. This is the modern, journal-preferred
    way to compare two groups: it shows the effect size and its uncertainty
    directly rather than only a p-value.

    Params: y (value column, required), x (group column, required), and
    optionally control (which group level is the reference). Bootstrap is
    reduced server-side to a density curve, so the payload is bounded
    regardless of the number of resamples.
    """
    y_col = params.get('y')
    g_col = params.get('x')
    if not y_col or y_col not in df.columns:
        raise ValueError(f"Value column '{y_col}' not found")
    if not g_col or g_col not in df.columns:
        raise ValueError(f"Group column '{g_col}' not found")

    sub = df[[y_col, g_col]].dropna()
    sub = sub[pd.to_numeric(sub[y_col], errors='coerce').notna()]
    sub[y_col] = pd.to_numeric(sub[y_col])
    groups = list(pd.unique(sub[g_col]))
    if len(groups) < 2:
        raise ValueError("Estimation plot needs at least two groups in the grouping column")

    # Choose control + test. Honour an explicit control; else first two seen.
    # The control may arrive as a string (from a dropdown) while the group
    # values are numeric, so match by string form rather than identity.
    control = params.get('control')
    control_match = None
    if control is not None and str(control) != '':
        for g in groups:
            if str(g) == str(control):
                control_match = g
                break
    if control_match is not None:
        control = control_match
        test = next(g for g in groups if g != control)
    else:
        control, test = groups[0], groups[1]

    c_vals = sub.loc[sub[g_col] == control, y_col].to_numpy(dtype=float)
    t_vals = sub.loc[sub[g_col] == test, y_col].to_numpy(dtype=float)
    if len(c_vals) < 2 or len(t_vals) < 2:
        raise ValueError("Each group needs at least two observations")

    c_mean, t_mean = float(c_vals.mean()), float(t_vals.mean())
    obs_diff = t_mean - c_mean

    # --- Bootstrap the mean difference with a BCa interval. -----------------
    # BCa (bias-corrected and accelerated) is more accurate than the percentile
    # interval for skewed bootstrap distributions, and is the dabest standard.
    # We use scipy's well-tested implementation (which does the two-sample
    # jackknife for the acceleration correctly) rather than hand-rolling it,
    # and fall back to the percentile interval if BCa degenerates (e.g. a
    # zero-variance group makes the acceleration undefined).
    B = 5000
    ci_method = "BCa"

    def _diff(x, y, axis=-1):
        return np.mean(x, axis=axis) - np.mean(y, axis=axis)

    try:
        res = scipy_stats.bootstrap(
            (t_vals, c_vals), _diff, method="BCa",
            n_resamples=B, confidence_level=0.95,
            vectorized=True, random_state=np.random.default_rng(0),
        )
        ci_low = float(res.confidence_interval.low)
        ci_high = float(res.confidence_interval.high)
        diff_boot = np.asarray(res.bootstrap_distribution, dtype=float)
        if not (np.isfinite(ci_low) and np.isfinite(ci_high)):
            raise ValueError("non-finite BCa interval")
    except Exception:
        # Percentile fallback (also recomputes the distribution deterministically).
        ci_method = "percentile"
        rng = np.random.default_rng(0)
        c_boot = rng.choice(c_vals, size=(B, len(c_vals)), replace=True).mean(axis=1)
        t_boot = rng.choice(t_vals, size=(B, len(t_vals)), replace=True).mean(axis=1)
        diff_boot = t_boot - c_boot
        ci_low, ci_high = (float(v) for v in np.percentile(diff_boot, [2.5, 97.5]))

    # CI of each group mean (gapped error bars on the left panel). BCa one-sample
    # where possible, percentile fallback per group.
    def _mean_ci(arr):
        try:
            r = scipy_stats.bootstrap(
                (arr,), lambda a, axis=-1: np.mean(a, axis=axis), method="BCa",
                n_resamples=B, confidence_level=0.95,
                vectorized=True, random_state=np.random.default_rng(0),
            )
            lo, hi = float(r.confidence_interval.low), float(r.confidence_interval.high)
            if np.isfinite(lo) and np.isfinite(hi):
                return (lo, hi)
        except Exception:
            pass
        bs = np.random.default_rng(0).choice(arr, size=(B, len(arr)), replace=True).mean(axis=1)
        return tuple(float(v) for v in np.percentile(bs, [2.5, 97.5]))
    c_ci = _mean_ci(c_vals)
    t_ci = _mean_ci(t_vals)

    color_c, color_t = _PALETTE[0], _PALETTE[1]

    fig = make_subplots(
        rows=1, cols=2, column_widths=[0.62, 0.38],
        horizontal_spacing=0.16,
        subplot_titles=("Raw data", "Mean difference (95% CI)"),
    )

    # ---- Left: raw jittered points + mean ± CI for each group ----
    jitter_rng = np.random.default_rng(1)  # visual jitter only; independent of CI
    for i, (name, vals, col, mean, ci) in enumerate([
        (str(control), c_vals, color_c, c_mean, c_ci),
        (str(test), t_vals, color_t, t_mean, t_ci),
    ]):
        jitter = (jitter_rng.random(len(vals)) - 0.5) * 0.35
        fig.add_trace(go.Scatter(
            x=np.full(len(vals), i) + jitter, y=vals, mode='markers',
            marker=dict(size=6, color=col, opacity=0.55, line=dict(width=0.4, color='white')),
            name=name, hoverinfo='y', showlegend=False,
        ), row=1, col=1)
        # Mean dot + gapped CI whisker, offset slightly to the right of the cloud.
        fig.add_trace(go.Scatter(
            x=[i + 0.30], y=[mean], mode='markers',
            marker=dict(size=10, color=col, symbol='circle'),
            error_y=dict(type='data', symmetric=False,
                         array=[ci[1] - mean], arrayminus=[mean - ci[0]],
                         color=col, thickness=1.6, width=6),
            hoverinfo='y', showlegend=False,
        ), row=1, col=1)

    # ---- Right: bootstrap density of the difference + observed dot/CI ----
    # Guard against a degenerate (zero-variance) bootstrap distribution, which
    # would make the KDE singular.
    if float(np.std(diff_boot)) > 0:
        kde = scipy_stats.gaussian_kde(diff_boot)
        y_grid = np.linspace(diff_boot.min(), diff_boot.max(), 200)
        dens = kde(y_grid)
        dens = dens / dens.max() * 0.34  # scale to a readable half-violin width
        fig.add_trace(go.Scatter(
            x=dens, y=y_grid, mode='lines', fill='tozerox',
            line=dict(color=color_t, width=1), fillcolor=_rgba(color_t, 0.18),
            hoverinfo='skip', showlegend=False,
        ), row=1, col=2)
    fig.add_trace(go.Scatter(
        x=[0], y=[obs_diff], mode='markers',
        marker=dict(size=11, color=color_t),
        error_y=dict(type='data', symmetric=False,
                     array=[ci_high - obs_diff], arrayminus=[obs_diff - ci_low],
                     color=color_t, thickness=1.8, width=8),
        hovertext=[f"Δ = {obs_diff:.4g}<br>95% CI [{ci_low:.4g}, {ci_high:.4g}] ({ci_method})"],
        hoverinfo='text', showlegend=False,
    ), row=1, col=2)
    fig.add_hline(y=0, line_dash='dash', line_color='rgba(0,0,0,0.45)', row=1, col=2)

    # Axis cosmetics.
    fig.update_xaxes(
        tickmode='array', tickvals=[0, 1], ticktext=[str(control), str(test)],
        range=[-0.5, 1.6], row=1, col=1,
    )
    fig.update_yaxes(title_text=str(y_col), row=1, col=1)
    fig.update_xaxes(showticklabels=False, range=[-0.05, 0.45], row=1, col=2)
    fig.update_yaxes(title_text=f"{test} − {control}", row=1, col=2)

    note = ""
    if len(groups) > 2:
        note = f"  (comparing '{test}' vs '{control}'; other groups omitted)"
    fig.update_layout(
        title=f"Estimation Plot — {y_col} by {g_col}{note}",
        height=480,
    )
    return _apply_house_style(fig)


def logit_diagnostic_panel(diag: dict) -> go.Figure | None:
    """
    Four-panel logistic-regression diagnostics from the bounded dict produced by
    regression.logit_diagnostic_data:
        (1) Deviance residuals vs linear predictor
        (2) Normal Q–Q of deviance residuals
        (3) Calibration curve (observed vs predicted, binned)
        (4) Residuals vs Leverage (+ Cook's-distance contours)
    Pure — consumes plain arrays, no statsmodels objects.
    """
    if not diag:
        return None
    linpred = diag.get("linpred") or []
    dev = diag.get("resid_dev") or []
    if len(linpred) < 3 or len(dev) < 3:
        return None

    leverage = diag.get("leverage") or []
    cooks = diag.get("cooks") or []
    qt = diag.get("qq_theoretical") or []
    qs = diag.get("qq_sample") or []
    calib = diag.get("calibration") or {}

    pt = dict(size=6, color=_PALETTE[0], opacity=0.6, line=dict(width=0.4, color='white'))
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            "Deviance Residuals vs Linear Predictor", "Normal Q–Q (deviance resid)",
            "Calibration", "Residuals vs Leverage",
        ),
        horizontal_spacing=0.12, vertical_spacing=0.16,
    )

    # (1) Deviance residuals vs linear predictor, zero line + binned trend.
    fig.add_trace(go.Scatter(x=linpred, y=dev, mode='markers', marker=pt,
                             hoverinfo='skip', showlegend=False), row=1, col=1)
    fig.add_hline(y=0, line_dash='dash', line_color='rgba(0,0,0,0.4)', row=1, col=1)
    tr = _binned_trend(linpred, dev)
    if tr:
        fig.add_trace(go.Scatter(x=tr[0], y=tr[1], mode='lines',
                                 line=dict(color='#dc2626', width=1.6),
                                 hoverinfo='skip', showlegend=False), row=1, col=1)

    # (2) Normal Q–Q of deviance residuals (≈ normal when well-specified).
    if len(qt) >= 3 and len(qs) >= 3:
        fig.add_trace(go.Scatter(x=qt, y=qs, mode='markers', marker=pt,
                                 hoverinfo='skip', showlegend=False), row=1, col=2)
        lo = min(min(qt), min(qs)); hi = max(max(qt), max(qs))
        fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode='lines',
                                 line=dict(color='rgba(0,0,0,0.4)', width=1.2, dash='dash'),
                                 hoverinfo='skip', showlegend=False), row=1, col=2)

    # (3) Calibration: binned observed event rate vs mean predicted probability,
    # with the 45° line of perfect calibration. Points near the diagonal = well
    # calibrated; systematic deviation = mis-calibration.
    cpred = calib.get("pred") or []
    cobs = calib.get("obs") or []
    if len(cpred) >= 2 and len(cobs) >= 2:
        fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode='lines',
                                 line=dict(color='rgba(0,0,0,0.4)', width=1.2, dash='dash'),
                                 hoverinfo='skip', showlegend=False), row=2, col=1)
        fig.add_trace(go.Scatter(
            x=cpred, y=cobs, mode='lines+markers',
            line=dict(color='#dc2626', width=1.6),
            marker=dict(size=8, color='#dc2626'),
            hovertemplate='predicted %{x:.3f}<br>observed %{y:.3f}<extra></extra>',
            showlegend=False), row=2, col=1)
        fig.update_xaxes(range=[-0.02, 1.02], row=2, col=1)
        fig.update_yaxes(range=[-0.02, 1.02], row=2, col=1)

    # (4) Residuals vs Leverage with Cook's-distance contours (same as OLS).
    lev_finite = [v for v in leverage if v == v]  # drop NaN
    if lev_finite and dev:
        sizes = None
        if cooks and any(c == c for c in cooks):
            c = np.asarray(cooks, dtype=float)
            c = np.where(np.isfinite(c), c, 0.0)
            cmax = c.max() if c.size and c.max() > 0 else 1.0
            sizes = list(6 + 14 * np.sqrt(np.clip(c / cmax, 0, 1)))
        marker4 = dict(color=_PALETTE[0], opacity=0.6, line=dict(width=0.4, color='white'),
                       size=(sizes if sizes else 6))
        fig.add_trace(go.Scatter(
            x=leverage, y=dev, mode='markers', marker=marker4,
            hovertemplate='leverage %{x:.3f}<br>deviance resid %{y:.2f}<extra></extra>',
            showlegend=False), row=2, col=2)
        fig.add_hline(y=0, line_dash='dash', line_color='rgba(0,0,0,0.4)', row=2, col=2)

        p = max(int(diag.get("n_params") or 2), 1)
        lev_arr = np.asarray(lev_finite, dtype=float)
        h_max = min(float(lev_arr.max()) if lev_arr.size else 0.2, 0.99)
        h_grid = np.linspace(max(float(lev_arr.min()), 1e-3), max(h_max, 1e-2), 50)
        for D, dash in [(0.5, 'dot'), (1.0, 'dash')]:
            with np.errstate(divide='ignore', invalid='ignore'):
                band = np.sqrt(D * p * (1 - h_grid) / h_grid)
            for sign in (1, -1):
                fig.add_trace(go.Scatter(
                    x=list(h_grid), y=list(sign * band), mode='lines',
                    line=dict(color='rgba(220,38,38,0.5)', width=1, dash=dash),
                    hoverinfo='skip', showlegend=False), row=2, col=2)

    fig.update_xaxes(title_text="Linear predictor", row=1, col=1)
    fig.update_yaxes(title_text="Deviance residual", row=1, col=1)
    fig.update_xaxes(title_text="Mean predicted probability", row=2, col=1)
    fig.update_yaxes(title_text="Observed event rate", row=2, col=1)
    fig.update_xaxes(title_text="Leverage", row=2, col=2)

    note = "Logistic diagnostics"
    if diag.get("sampled"):
        note += f" · showing {diag.get('n_shown')} of {diag.get('n_obs')} points (extremes kept)"
    fig.update_layout(
        title=note,
        height=480,
    )
    return _apply_house_style(fig)


def bland_altman(df: pd.DataFrame, params: dict) -> go.Figure:
    """
    Bland-Altman (Tukey mean-difference) plot for method-comparison / agreement.

    Plots the difference between two paired measurements against their mean,
    with the mean bias and the 95% limits of agreement (bias ± 1.96·SD). This
    is the standard way to assess whether a new method agrees with a reference,
    and is almost never available in general plotting tools.

    Params: x (method A column), y (method B column). Points outside the limits
    of agreement are always retained when subsampling large datasets, since
    those are the clinically important disagreements.
    """
    a_col, b_col = params.get('x'), params.get('y')
    if not a_col or a_col not in df.columns:
        raise ValueError(f"Method A column '{a_col}' not found")
    if not b_col or b_col not in df.columns:
        raise ValueError(f"Method B column '{b_col}' not found")

    sub = df[[a_col, b_col]].copy()
    sub[a_col] = pd.to_numeric(sub[a_col], errors='coerce')
    sub[b_col] = pd.to_numeric(sub[b_col], errors='coerce')
    sub = sub.dropna()
    if len(sub) < 2:
        raise ValueError("Need at least two paired numeric observations")

    a = sub[a_col].to_numpy(dtype=float)
    b = sub[b_col].to_numpy(dtype=float)
    means = (a + b) / 2.0
    diffs = a - b

    bias = float(np.mean(diffs))
    sd = float(np.std(diffs, ddof=1)) if len(diffs) > 1 else 0.0
    loa_hi = bias + 1.96 * sd
    loa_lo = bias - 1.96 * sd

    # Proportional bias: regress the differences on the means. If the slope is
    # significant, the bias depends on magnitude, so flat bias/LoA lines are
    # misleading — Bland & Altman prescribe a fitted bias line with LoA at
    # ±1.96·SD of the REGRESSION RESIDUALS (parallel to the fitted line). We
    # auto-detect significance (p < 0.05) but let the caller force either mode.
    prop_param = params.get('proportional_bias', 'auto')
    slope = intercept = res_sd = slope_p = None
    if len(diffs) >= 3 and np.ptp(means) > 0:
        lr = scipy_stats.linregress(means, diffs)
        slope, intercept, slope_p = float(lr.slope), float(lr.intercept), float(lr.pvalue)
        resid = diffs - (intercept + slope * means)
        res_sd = float(np.std(resid, ddof=2)) if len(resid) > 2 else 0.0

    if prop_param is True:
        use_proportional = slope is not None
    elif prop_param in (False, 'off', 'flat'):
        use_proportional = False
    else:  # 'auto'
        use_proportional = slope is not None and slope_p is not None and slope_p < 0.05

    # Bound the scatter: keep out-of-LoA points always, sample the rest.
    n = len(diffs)
    cap = 5000
    idx = np.arange(n)
    if n > cap:
        outside = np.where((diffs > loa_hi) | (diffs < loa_lo))[0]
        rng = np.random.default_rng(0)
        room = max(cap - len(outside), 0)
        inside = np.setdiff1d(np.arange(n), outside)
        if room and len(inside) > room:
            inside = np.sort(rng.choice(inside, size=room, replace=False))
        idx = np.sort(np.concatenate([outside, inside]))

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=means[idx], y=diffs[idx], mode='markers',
        marker=dict(size=7, color=_PALETTE[0], opacity=0.6, line=dict(width=0.4, color='white')),
        hovertemplate='mean %{x:.3g}<br>diff %{y:.3g}<extra></extra>', showlegend=False,
    ))
    x0, x1 = float(means.min()), float(means.max())
    if use_proportional:
        # Fitted bias line and LoA parallel to it (±1.96·SD of residuals).
        xs = np.array([x0, x1])
        bias_line = intercept + slope * xs
        for ys, label, dash, col in [
            (bias_line, f"Bias {slope:+.3g}·mean {intercept:+.3g}", 'solid', '#2563eb'),
            (bias_line + 1.96 * res_sd, "+1.96 SD (resid)", 'dash', '#dc2626'),
            (bias_line - 1.96 * res_sd, "−1.96 SD (resid)", 'dash', '#dc2626'),
        ]:
            fig.add_trace(go.Scatter(
                x=xs, y=ys, mode='lines', line=dict(color=col, width=1.4, dash=dash),
                hoverinfo='skip', showlegend=False,
            ))
            fig.add_annotation(x=x1, y=float(ys[-1]), text=label, showarrow=False,
                               xanchor='right', yanchor='bottom',
                               font=dict(size=11, color=col))
        fig.add_annotation(
            xref='paper', yref='paper', x=0.0, y=1.0, xanchor='left', yanchor='bottom',
            text=f"Proportional bias: slope p = {slope_p:.3g}", showarrow=False,
            font=dict(size=11, color='#6b7280'),
        )
    else:
        for y_val, label, dash, col in [
            (bias, f"Bias {bias:.3g}", 'solid', '#2563eb'),
            (loa_hi, f"+1.96 SD {loa_hi:.3g}", 'dash', '#dc2626'),
            (loa_lo, f"−1.96 SD {loa_lo:.3g}", 'dash', '#dc2626'),
        ]:
            fig.add_hline(y=y_val, line_dash=dash, line_color=col, line_width=1.4)
            fig.add_annotation(x=x1, y=y_val, text=label, showarrow=False,
                               xanchor='right', yanchor='bottom',
                               font=dict(size=11, color=col))
    fig.add_hline(y=0, line_color='rgba(0,0,0,0.25)', line_width=1)

    fig.update_layout(
        title=f"Bland-Altman — {a_col} vs {b_col}",
        xaxis_title=f"Mean of {a_col} and {b_col}",
        yaxis_title=f"Difference ({a_col} − {b_col})",
        height=480,
    )
    return _apply_house_style(fig)


def raincloud(df: pd.DataFrame, params: dict) -> go.Figure:
    """
    Raincloud plot: a half-violin (distribution shape) + box (summary) + jittered
    raw points, per group. Shows the full distribution honestly — shape, summary,
    and every observation at once.

    Params: y (value, required), x (group, optional), orientation ('v' default
    or 'h'). Points per group are capped for bounded payload while preserving the
    violin shape.
    """
    y_col = params.get('y')
    g_col = params.get('x')
    horizontal = (params.get('orientation') or 'v') == 'h'
    if not y_col or y_col not in df.columns:
        raise ValueError(f"Value column '{y_col}' not found")

    cols = [y_col] + ([g_col] if g_col and g_col in df.columns else [])
    sub = df[cols].copy()
    sub[y_col] = pd.to_numeric(sub[y_col], errors='coerce')
    sub = sub.dropna(subset=[y_col])
    if sub.empty:
        raise ValueError("No numeric values to plot")

    groups = [g for g in pd.unique(sub[g_col].dropna())] if (g_col and g_col in sub.columns) else [None]
    rng = np.random.default_rng(0)
    cap = 2000

    fig = go.Figure()
    for i, grp in enumerate(groups):
        vals = (sub.loc[sub[g_col] == grp, y_col] if grp is not None else sub[y_col]).to_numpy(dtype=float)
        if len(vals) == 0:
            continue
        if len(vals) > cap:  # preserve violin shape, bound payload
            vals = rng.choice(vals, size=cap, replace=False)
        color = _PALETTE[i % len(_PALETTE)]
        name = str(grp) if grp is not None else str(y_col)
        cat = [name] * len(vals)
        jitter = (rng.random(len(vals)) - 0.5) * 0.14
        pts_offset = np.full(len(vals), i, dtype=float) + 0.28 + jitter

        # Three explicit layers per group (the violin's own internal box is
        # hidden under the fill on a one-sided violin, so the box is separate):
        #   half-violin on the category-low side, narrow box, then jittered rain.
        if horizontal:
            # value on x, category on y
            fig.add_trace(go.Violin(
                y=cat, x=vals, name=name, side='negative', width=0.9, orientation='h',
                points=False, box_visible=False, meanline_visible=False,
                line_color=color, fillcolor=_rgba(color, 0.35),
                scalemode='width', spanmode='hard', showlegend=False,
            ))
            fig.add_trace(go.Box(
                y=cat, x=vals, name=name, width=0.12, orientation='h',
                boxpoints=False, line=dict(color=color, width=1.4),
                fillcolor='rgba(255,255,255,0.65)', whiskerwidth=0.4,
                showlegend=False, offsetgroup=name,
            ))
            fig.add_trace(go.Scatter(
                y=pts_offset, x=vals, mode='markers', name=name,
                marker=dict(size=4, color=color, opacity=0.5, line=dict(width=0.3, color='white')),
                hoverinfo='x', showlegend=False,
            ))
        else:
            # value on y, category on x
            fig.add_trace(go.Violin(
                x=cat, y=vals, name=name, side='negative', width=0.9,
                points=False, box_visible=False, meanline_visible=False,
                line_color=color, fillcolor=_rgba(color, 0.35),
                scalemode='width', spanmode='hard', showlegend=False,
            ))
            fig.add_trace(go.Box(
                x=cat, y=vals, name=name, width=0.12,
                boxpoints=False, line=dict(color=color, width=1.4),
                fillcolor='rgba(255,255,255,0.65)', whiskerwidth=0.4,
                showlegend=False, offsetgroup=name,
            ))
            fig.add_trace(go.Scatter(
                x=pts_offset, y=vals, mode='markers', name=name,
                marker=dict(size=4, color=color, opacity=0.5, line=dict(width=0.3, color='white')),
                hoverinfo='y', showlegend=False,
            ))

    cat_array = [str(g) if g is not None else str(y_col) for g in groups]
    title = f"Raincloud — {y_col}" + (f" by {g_col}" if (g_col and g_col in sub.columns) else "")
    layout = dict(title=title, violingap=0.25, violinmode='overlay', boxmode='overlay', height=480)
    if horizontal:
        layout['xaxis_title'] = str(y_col)
        layout['yaxis'] = dict(categoryorder='array', categoryarray=cat_array)
    else:
        layout['yaxis_title'] = str(y_col)
        layout['xaxis'] = dict(categoryorder='array', categoryarray=cat_array)
    fig.update_layout(**layout)
    return _apply_house_style(fig)


# ---------------------------------------------------------------------------
# Dispatch table — maps plot_type string → builder function
# ---------------------------------------------------------------------------

_BUILDERS = {
    'histogram': histogram,
    'box':       box,
    'violin':    violin,
    'scatter':   scatter,
    'bar':       bar,
    'line':      line,
    'strip':     strip,
    'ecdf':      ecdf,
    'qq':        qq,
    'density':   density,
    'paired':    paired,
    'estimation': estimation_plot,
    'bland_altman': bland_altman,
    'raincloud': raincloud,
    'corr_heatmap': corr_heatmap,
    'scatter_matrix': scatter_matrix,
}


def build_plot(df: pd.DataFrame, params: dict) -> go.Figure:
    """
    Main entry point for the graphics blueprint.
    Dispatches on params['plot_type'] and returns a Plotly Figure.
    Raises ValueError for unknown or missing plot types.
    """
    plot_type = params.get('plot_type')
    builder = _BUILDERS.get(plot_type)
    if builder is None:
        raise ValueError(f"Unknown plot type: '{plot_type}'")
    fig = builder(df, params)
    # House style is applied AFTER the builder so its ambient defaults (fonts,
    # backgrounds, gridlines) are consistent across every menu plot. Builders
    # that set axis ranges / dragmode / per-trace styling are unaffected,
    # because house style never touches those keys.
    _apply_house_style(fig)
    return fig
