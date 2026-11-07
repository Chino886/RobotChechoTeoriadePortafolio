"""
Vista visual de «Comparación y preselección de activos» (solo presentación).

Todo sale del ComparisonResult que ya calculó src/comparison.py (AssetSummary: media y
volatilidad anualizadas, RVR, cuantiles q05/q95, drawdown máximo, último precio) y de sus
precios procesados de la ventana común. Aquí no se recalcula ninguna métrica ni se cambia
la dominancia o la regla de preselección: solo se dibujan.
"""
from __future__ import annotations

from html import escape
from typing import Iterable, Optional

import pandas as pd
import plotly.graph_objects as go

from src.charts import DARK_LAYOUT
from src.dashboard import spark_data, spark_svg

# Paleta de series: tonos medios que se leen en tema claro y oscuro (azules, celeste, turquesa…).
SERIES_COLORS = ["#2563EB", "#0EA5E9", "#14B8A6", "#F59E0B", "#8B5CF6", "#EF4444", "#EC4899", "#22C55E",
                 "#64748B", "#F97316"]
PERIODS = ["1M", "3M", "6M", "1A", "Todo"]
_PERIOD_OFFSETS = {"1M": pd.DateOffset(months=1), "3M": pd.DateOffset(months=3), "6M": pd.DateOffset(months=6),
                   "1A": pd.DateOffset(years=1)}


def _pct(x: Optional[float], digits: int = 2) -> str:
    return "—" if x is None else f"{x:.{digits}%}"


def _num(x: Optional[float], digits: int = 2) -> str:
    return "—" if x is None else f"{x:,.{digits}f}"


def color_for(i: int) -> str:
    return SERIES_COLORS[i % len(SERIES_COLORS)]


def avatar(ticker: str, i: int) -> str:
    return (f'<span class="cmp-av" style="--c:{color_for(i)}" aria-hidden="true">'
            f'{escape((ticker or "?")[:2])}</span>')


def status_badges(ticker: str, non_dominated: "set[str]", selected: Iterable[str], starred: Optional[str]) -> str:
    out = []
    if ticker in (selected or []):
        out.append('<span class="cmp-b sel" title="Elegido por el criterio de la pestaña Preselección">Preseleccionado</span>')
    if ticker in non_dominated:
        out.append('<span class="cmp-b nd" title="Ningún otro activo del lote tiene a la vez media ≥ y volatilidad ≤">No dominado</span>')
    if starred and ticker == starred:
        out.append('<span class="cmp-b star" title="Tu elección marcada en el Mapa histórico">★ Tu elección</span>')
    return "".join(out) or '<span class="cmp-b dom">Dominado</span>'


def _state(ticker, non_dominated, selected, starred) -> str:
    tags = []
    if ticker in (selected or []):
        tags.append("sel")
    tags.append("nd" if ticker in non_dominated else "dom")
    if starred and ticker == starred:
        tags.append("star")
    return " ".join(tags)


def asset_panel_html(result, names: "dict[str, str]", non_dominated: "set[str]", selected: "list[str]",
                     starred: Optional[str], criterion: str) -> str:
    """Tarjetas de los activos comparados, con sus métricas originales y su estado de selección."""
    cards = []
    prices = result.common_prices or {}
    for i, s in enumerate(result.summaries):
        name = names.get(s.ticker, "")
        spark = spark_svg(spark_data(prices.get(s.ticker)), f"{s.ticker}: precio procesado en la ventana común")
        cards.append(
            f'<article class="cmp-card" data-t="{escape(s.ticker)}" data-state="{_state(s.ticker, non_dominated, selected, starred)}" '
            f'data-mean="{s.mean_annual}" data-vol="{s.vol_annual}" data-rvr="{"" if s.rvr is None else s.rvr}" '
            f'data-dd="{s.max_dd}" style="--i:{min(i, 24)}">'
            f'<div class="cc-top">{avatar(s.ticker, i)}<div class="cc-id"><b>{escape(s.ticker)}</b>'
            f'<span title="{escape(name)}">{escape(name) or "—"}</span></div>'
            f'<div class="cc-px"><b>{_num(s.last_price)}</b><span>{escape(result.base_currency or s.currency or "")}</span></div></div>'
            f'{spark}'
            '<dl class="cc-m">'
            f'<div><dt title="Media histórica logarítmica anualizada">μ anual</dt><dd>{_pct(s.mean_annual)}</dd></div>'
            f'<div><dt title="Volatilidad histórica anualizada">σ anual</dt><dd>{_pct(s.vol_annual)}</dd></div>'
            f'<div><dt title="Razón individual media / volatilidad">RVR</dt><dd>{_num(s.rvr, 3)}</dd></div>'
            f'<div><dt title="Máxima caída (drawdown)">Máx. caída</dt><dd>{_pct(s.max_dd)}</dd></div>'
            '</dl>'
            f'<div class="cc-b">{status_badges(s.ticker, non_dominated, selected, starred)}</div></article>'
        )
    n_sel, n_nd = len(selected or []), len(non_dominated)
    chips = [("all", f"Todos · {len(result.summaries)}"), ("sel", f"Preseleccionados · {n_sel}"),
             ("nd", f"No dominados · {n_nd}"), ("dom", f"Dominados · {len(result.summaries) - n_nd}")]
    chip_html = "".join(f'<button type="button" class="dash-chip" data-val="{k}" aria-pressed="{"true" if k == "all" else "false"}">'
                        f'{escape(t)}</button>' for k, t in chips)
    sorts = [("", "Orden original"), ("mean", "μ anual (mayor primero)"), ("vol", "σ anual (menor primero)"),
             ("rvr", "RVR (mayor primero)"), ("dd", "Máx. caída (menor primero)")]
    sort_html = "".join(f'<option value="{k}">{escape(t)}</option>' for k, t in sorts)
    crit = (f'<div class="cmp-crit">Criterio activo en <b>Preselección</b>: {escape(criterion)}</div>' if criterion else "")
    return (
        '<section class="cmp-panel">'
        f'<div class="cmp-tools"><div class="dash-chips" role="group" data-cmp-filter>{chip_html}</div>'
        f'<label class="cmp-sort">Ordenar <select data-cmp-sort>{sort_html}</select></label></div>{crit}'
        f'<div class="cmp-cards">{"".join(cards)}</div>'
        '<div class="cmp-none" hidden>No hay activos con este filtro.</div></section>'
    )


def _bar(value: Optional[float], lo: float, hi: float, tone: str) -> str:
    """Barra de diferencia visual dentro de la celda (relativa al mínimo y máximo del lote)."""
    if value is None:
        return ""
    span = (hi - lo) or 1.0
    if lo < 0 < hi:  # barra divergente desde el cero
        zero = -lo / span * 100
        w = abs(value) / span * 100
        left = zero if value >= 0 else zero - w
    else:
        left, w = 0.0, (value - lo) / span * 100 if hi != lo else 100.0
        w = max(w, 3.0)
    return f'<span class="cmp-bar {tone}{" neg" if value < 0 else ""}" style="left:{left:.1f}%;width:{w:.1f}%"></span>'


def comparison_table_html(result, names: "dict[str, str]", non_dominated: "set[str]", selected: "list[str]",
                          starred: Optional[str]) -> str:
    """Tabla comparativa con barras de diferencia; mismos valores de comparison_table()."""
    S = result.summaries
    cols = {
        "mean": [s.mean_annual for s in S], "vol": [s.vol_annual for s in S],
        "rvr": [s.rvr for s in S if s.rvr is not None], "dd": [s.max_dd for s in S],
        "q05": [s.q05 for s in S], "q95": [s.q95 for s in S],
    }
    rng = {k: (min(v), max(v)) if v else (0.0, 1.0) for k, v in cols.items()}
    best = {"mean": max(cols["mean"]) if cols["mean"] else None, "vol": min(cols["vol"]) if cols["vol"] else None,
            "rvr": max(cols["rvr"]) if cols["rvr"] else None, "dd": max(cols["dd"]) if cols["dd"] else None}

    def cell(key, v, fmt, tone):
        b = ' class="best" title="Mejor valor del lote en esta columna"' if v is not None and best.get(key) == v else ""
        return (f'<td data-v="{"" if v is None else v}"{b}><span class="cmp-cell">{_bar(v, *rng[key], tone)}'
                f'<span class="cmp-val">{fmt(v)}</span></span></td>')

    rows = []
    for i, s in enumerate(S):
        rows.append(
            f'<tr data-state="{_state(s.ticker, non_dominated, selected, starred)}">'
            f'<td class="a" data-v="{escape(s.ticker)}">{avatar(s.ticker, i)}<span class="cmp-an"><b>{escape(s.ticker)}</b>'
            f'<span>{escape(names.get(s.ticker, "")) or "—"}</span></span></td>'
            f'<td data-v="{s.last_price}" class="num">{_num(s.last_price)}</td>'
            + cell("mean", s.mean_annual, _pct, "mean") + cell("vol", s.vol_annual, _pct, "vol")
            + cell("rvr", s.rvr, lambda v: _num(v, 3), "rvr") + cell("dd", s.max_dd, _pct, "dd")
            + f'<td data-v="{s.q05}" class="num">{s.q05:.4f}</td><td data-v="{s.q95}" class="num">{s.q95:.4f}</td>'
            f'<td data-v="{s.n}" class="num">{s.n}</td>'
            f'<td class="st">{status_badges(s.ticker, non_dominated, selected, starred)}</td></tr>'
        )
    head = ''.join(f'<th data-sort="{i}"{(" title=" + chr(34) + escape(tip) + chr(34)) if tip else ""}>{escape(h)}</th>'
                   for i, (h, tip) in enumerate([
                       ("Activo", ""), ("Último precio", f"En {result.base_currency or 'moneda base'}"),
                       ("μ anual", "Media histórica logarítmica anualizada"), ("σ anual", "Volatilidad histórica anualizada"),
                       ("RVR", "Razón individual media / volatilidad"), ("Máx. caída", "Drawdown máximo"),
                       ("q05", "Cuantil 5% del log-rendimiento por periodo"), ("q95", "Cuantil 95% del log-rendimiento por periodo"),
                       ("n", "Rendimientos en la ventana común"), ("Estado", "")]))
    return (f'<div class="cmp-table" role="region" aria-label="Tabla comparativa"><table><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def period_slice(prices: pd.Series, period: str) -> pd.Series:
    s = prices.dropna()
    if period in _PERIOD_OFFSETS and len(s):
        s = s[s.index >= s.index.max() - _PERIOD_OFFSETS[period]]
    return s


def evolution_figure(result, tickers: "list[str]", period: str, mode: str) -> go.Figure:
    """Evolución de los precios procesados de la ventana común: variación % desde el inicio del periodo o precio."""
    fig = go.Figure()
    order = [s.ticker for s in result.summaries]
    pct = mode != "Precio"
    for t in tickers:
        series = (result.common_prices or {}).get(t)
        if series is None:
            continue
        s = period_slice(series, period)
        if len(s) < 2:
            continue
        y = s / float(s.iloc[0]) - 1.0 if pct else s
        i = order.index(t) if t in order else 0
        fig.add_trace(go.Scatter(
            x=s.index, y=y, mode="lines", name=t,
            line=dict(color=color_for(i), width=2, dash="solid" if i < len(SERIES_COLORS) else "dot"),
            hovertemplate=(f"<b>{t}</b> · %{{x|%Y-%m-%d}}<br>" + ("Variación: %{y:+.2%}" if pct else "Precio: %{y:,.2f}")
                           + "<extra></extra>"),
        ))
    fig.update_layout(
        height=480, margin=dict(t=30, b=40, l=50, r=20),
        hovermode="x unified" if len(tickers) <= 8 else "closest",
        legend=dict(orientation="h", yanchor="top", y=-0.12, x=0, title_text=""),
        yaxis=dict(tickformat="+.0%" if pct else ",.2f",
                   title="Variación desde el inicio del periodo" if pct else f"Precio procesado ({result.base_currency or ''})"),
        **DARK_LAYOUT,
    )
    if pct:
        fig.add_hline(y=0, line=dict(color="rgba(140,153,179,0.6)", width=1, dash="dot"))
    return fig


def _hbar(summaries, values, title: str, fmt: str, tone_colors, highlight: "set[str]", note: str) -> go.Figure:
    pairs = [(s.ticker, v) for s, v in zip(summaries, values) if v is not None]
    fig = go.Figure(go.Bar(
        x=[v for _, v in pairs], y=[t for t, _ in pairs], orientation="h",
        marker=dict(color=[tone_colors[0] if t in highlight else tone_colors[1] for t, _ in pairs]),
        hovertemplate="<b>%{y}</b><br>" + title + ": %{x:" + fmt + "}<extra></extra>",
        texttemplate="%{x:" + fmt + "}", textposition="outside", cliponaxis=False,
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16)), height=max(260, 26 * len(pairs) + 90),
        margin=dict(t=50, b=30, l=10, r=40), showlegend=False, xaxis=dict(tickformat=fmt, title=note),
        yaxis=dict(autorange="reversed", automargin=True), bargap=0.32, **DARK_LAYOUT,
    )
    return fig


def sorted_summaries(summaries, key, reverse: bool):
    """Solo cambia el orden de presentación; los que no tienen valor (p. ej. RVR None) van al final."""
    known = [s for s in summaries if key(s) is not None]
    return sorted(known, key=key, reverse=reverse) + [s for s in summaries if key(s) is None]


def mean_bar_figure(summaries, highlight: "set[str]") -> go.Figure:
    S = sorted_summaries(summaries, lambda s: s.mean_annual, True)
    return _hbar(S, [s.mean_annual for s in S], "Media anualizada (μ)", ".2%", ("#2563EB", "#93C5FD"), highlight,
                 "media histórica logarítmica anualizada")


def risk_bar_figures(summaries, highlight: "set[str]") -> "list[go.Figure]":
    by_vol = sorted_summaries(summaries, lambda s: s.vol_annual, False)
    by_rvr = sorted_summaries(summaries, lambda s: s.rvr, True)
    by_dd = sorted_summaries(summaries, lambda s: s.max_dd, True)
    return [
        _hbar(by_vol, [s.vol_annual for s in by_vol], "Volatilidad anualizada (σ)", ".2%", ("#0EA5E9", "#BAE6FD"),
              highlight, "menor = más estable"),
        _hbar(by_rvr, [s.rvr for s in by_rvr], "RVR (μ / σ)", ".3f", ("#1D4ED8", "#A5B4FC"), highlight,
              "media por unidad de volatilidad"),
        _hbar(by_dd, [s.max_dd for s in by_dd], "Máxima caída (drawdown)", ".2%", ("#DC2626", "#FCA5A5"), highlight,
              "más cerca de 0 = caída menor"),
    ]


def quantile_figure(summaries, highlight: "set[str]") -> go.Figure:
    """Rango q05–q95 del log-rendimiento por periodo de cada activo (valores ya calculados)."""
    S = sorted_summaries(summaries, lambda s: s.q95 - s.q05, False)
    fig = go.Figure()
    for s in S:
        c = "#2563EB" if s.ticker in highlight else "#94A3B8"
        fig.add_trace(go.Scatter(x=[s.q05, s.q95], y=[s.ticker, s.ticker], mode="lines+markers",
                                 line=dict(color=c, width=4), marker=dict(size=9, color=c), showlegend=False,
                                 hovertemplate=f"<b>{s.ticker}</b><br>q05: {s.q05:.4f}<br>q95: {s.q95:.4f}<extra></extra>"))
    fig.add_vline(x=0, line=dict(color="rgba(140,153,179,0.6)", width=1, dash="dot"))
    fig.update_layout(title=dict(text="Rango típico por periodo (q05 a q95 del log-rendimiento)", font=dict(size=16)),
                      height=max(280, 26 * len(S) + 90), margin=dict(t=50, b=30, l=10, r=20),
                      yaxis=dict(autorange="reversed", automargin=True), xaxis=dict(tickformat=".3f"), **DARK_LAYOUT)
    return fig
