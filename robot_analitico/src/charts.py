"""
Visualizaciones (RF-09, RF-14) y mapa histórico rendimiento-riesgo
(RF-19 a RF-21).

Este archivo cubre los gráficos de precio y rendimiento del análisis de un
solo activo (Fase 4), la trayectoria de pronóstico (Fase 6) y el mapa
histórico rendimiento-riesgo de la comparación de N activos (Fase 8).
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio

# Paleta (tema azul noche + esmeralda, alineada con .streamlit/config.toml): verde
# jade suave (no neón) para que se lea bien al proyectar sobre fondo oscuro.
ACCENT_EMERALD = "#34C9A0"  # líneas principales
SKY_BLUE = "#6AA8FF"  # bandas, áreas y series secundarias
STAR_WHITE = "#F5F7FB"  # elección marcada por el usuario en el mapa; también la CAL
# Nombres anteriores, conservados para no romper importaciones existentes.
ACCENT_GOLD = ACCENT_EMERALD
ELECTRIC_BLUE = SKY_BLUE

_GRID = "rgba(148, 170, 210, 0.10)"
_AXIS_FONT = dict(family="Geist Mono, ui-monospace, monospace", color="#8C99B3", size=11)

# Plantilla "dpst": ejes, leyenda, tooltip y serie de colores. Va en una plantilla (y no
# en DARK_LAYOUT) para que las llamadas que pasan su propio xaxis/yaxis no choquen.
_template = go.layout.Template()
_template.layout = go.Layout(
    title_font=dict(family="Instrument Serif, Georgia, serif", size=22, color="#E8EDF6"),
    colorway=[ACCENT_EMERALD, SKY_BLUE, "#F5B84B", "#FF7A7A", "#B794F6", "#7FD6E8", "#E8EDF6"],
    xaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID, linecolor=_GRID, tickfont=_AXIS_FONT),
    yaxis=dict(gridcolor=_GRID, zerolinecolor=_GRID, linecolor=_GRID, tickfont=_AXIS_FONT),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color="#AEB9CE")),
    hoverlabel=dict(bgcolor="#121A2B", bordercolor=ACCENT_EMERALD,
                    font=dict(family="Geist Mono, monospace", color="#E8EDF6")),
)
# Línea guía vertical al pasar el cursor (todas las gráficas).
_template.layout.xaxis.update(showspikes=True, spikemode="across", spikesnap="cursor", spikethickness=1,
                              spikecolor="rgba(111, 227, 193, 0.45)", spikedash="dot")
_template.data.scatter = [go.Scatter(line=dict(width=2.2))]
pio.templates["dpst"] = _template

# Barra de herramientas de Plotly (zoom, desplazar, restaurar vista, descargar PNG) en español.
PLOTLY_CONFIG = {
    "displaylogo": False,
    "locale": "es",
    "scrollZoom": False,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
    "toImageButtonOptions": {"format": "png", "filename": "dpst_grafico", "scale": 2},
}

PRESELECTION_CHART_HEIGHT = 460  # precio, rendimientos y pronóstico: gráficas más grandes

DARK_LAYOUT = dict(
    template="plotly_dark+dpst",
    paper_bgcolor="rgba(0,0,0,0)",  # transparente: la tarjeta del gráfico pone el fondo
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Geist, Inter, sans-serif", color="#E8EDF6", size=13),
)


def price_chart(prices, ticker: str, currency: str, frequency: str, source: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=prices.index, y=prices.values, mode="lines", name=ticker, line=dict(color=ACCENT_GOLD))
    )
    fig.update_layout(
        title=f"Precio ajustado - {ticker} ({frequency}, fuente: {source})",
        xaxis_title="Fecha",
        yaxis_title=f"Precio ajustado ({currency or 'N/D'})",
        margin=dict(t=60, b=40, l=40, r=20),
        height=PRESELECTION_CHART_HEIGHT,
        hovermode="x unified",
        **DARK_LAYOUT,
    )
    return fig


def return_chart(returns, ticker: str, frequency: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(x=returns.index, y=returns.values, mode="lines", name=ticker, line=dict(color=ACCENT_GOLD))
    )
    fig.update_layout(
        title=f"Rendimiento logarítmico - {ticker} ({frequency})",
        xaxis_title="Fecha",
        yaxis_title="g_t (log-rendimiento)",
        margin=dict(t=60, b=40, l=40, r=20),
        height=PRESELECTION_CHART_HEIGHT,
        hovermode="x unified",
        **DARK_LAYOUT,
    )
    return fig


def _future_dates(last_date, frequency: str, horizon: int) -> pd.DatetimeIndex:
    """Fechas aproximadas de los próximos `horizon` periodos, solo para el eje del gráfico."""
    if frequency == "Semanal":
        return pd.date_range(start=last_date, periods=horizon + 1, freq="W")[1:]
    if frequency == "Mensual":
        return pd.date_range(start=last_date, periods=horizon + 1, freq="ME")[1:]
    return pd.bdate_range(start=last_date, periods=horizon + 1)[1:]  # Diaria (y default)


def forecast_chart(prices, steps, ticker: str, frequency: str, history_window: int = 60) -> go.Figure:
    """
    Trayectoria de pronóstico (RF-14): cola del histórico + mediana pronosticada
    + banda del intervalo 5%-95% para cada paso de 1 a H.
    """
    fig = go.Figure()
    hist = prices.tail(history_window)
    fig.add_trace(
        go.Scatter(x=hist.index, y=hist.values, mode="lines", name="Histórico", line=dict(color=ACCENT_GOLD))
    )

    future_dates = _future_dates(hist.index[-1], frequency, len(steps))
    medians = [s.median_price for s in steps]
    q05s = [s.q05_price for s in steps]
    q95s = [s.q95_price for s in steps]

    fig.add_trace(
        go.Scatter(x=future_dates, y=q95s, mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip")
    )
    fig.add_trace(
        go.Scatter(
            x=future_dates, y=q05s, mode="lines", line=dict(width=0), fill="tonexty",
            name="Intervalo 5%-95% (pronóstico)", fillcolor="rgba(106, 168, 255, 0.18)",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=future_dates, y=medians, mode="lines", name="Mediana pronosticada",
            line=dict(dash="dash", color=ACCENT_GOLD),
        )
    )
    fig.update_layout(
        title=f"Pronóstico - {ticker} ({frequency})",
        xaxis_title="Fecha",
        yaxis_title="Precio",
        margin=dict(t=60, b=40, l=40, r=20),
        height=PRESELECTION_CHART_HEIGHT,
        hovermode="x unified",
        **DARK_LAYOUT,
    )
    return fig


def risk_return_map(summaries, non_dominated, starred_ticker: "str | None" = None) -> go.Figure:
    """
    Mapa histórico rendimiento-riesgo (RF-19/RF-20, sección 5.8): volatilidad
    anualizada en X, media histórica logarítmica anualizada en Y. Las
    coordenadas son históricas (no dependen de H) y se etiqueta cada punto.
    Los activos no dominados se resaltan; esto NO es una frontera eficiente
    de portafolios ni una recomendación de la mejor inversión universal.

    `starred_ticker` (opcional) marca con una estrella el activo que el
    usuario eligió; es solo visual y se dibuja encima de su punto normal.
    """
    dominated = [s for s in summaries if s.ticker not in non_dominated]
    frontier = [s for s in summaries if s.ticker in non_dominated]

    fig = go.Figure()
    if dominated:
        fig.add_trace(
            go.Scatter(
                x=[s.vol_annual for s in dominated],
                y=[s.mean_annual for s in dominated],
                mode="markers+text",
                text=[s.ticker for s in dominated],
                textposition="top center",
                name="Dominado",
                hovertemplate="<b>%{text}</b><br>Volatilidad σ: %{x:.2%}<br>Media ḡ: %{y:.2%}<extra>%{fullData.name}</extra>",
                marker=dict(size=10, color="rgba(106, 168, 255, 0.55)"),
            )
        )
    if frontier:
        fig.add_trace(
            go.Scatter(
                x=[s.vol_annual for s in frontier],
                y=[s.mean_annual for s in frontier],
                mode="markers+text",
                text=[s.ticker for s in frontier],
                textposition="top center",
                name="No dominado",
                hovertemplate="<b>%{text}</b><br>Volatilidad σ: %{x:.2%}<br>Media ḡ: %{y:.2%}<extra>%{fullData.name}</extra>",
                marker=dict(size=13, color=ACCENT_GOLD, symbol="diamond"),
            )
        )
    starred = [s for s in summaries if starred_ticker is not None and s.ticker == starred_ticker]
    if starred:
        fig.add_trace(
            go.Scatter(
                x=[starred[0].vol_annual],
                y=[starred[0].mean_annual],
                mode="markers+text",
                text=[starred[0].ticker],
                textposition="bottom center",
                name="Tu elección",
                hovertemplate="<b>%{text}</b><br>Volatilidad σ: %{x:.2%}<br>Media ḡ: %{y:.2%}<extra>%{fullData.name}</extra>",
                marker=dict(size=18, symbol="star", color=STAR_WHITE),
            )
        )
    fig.update_layout(
        title="Mapa histórico rendimiento-riesgo (no es frontera eficiente de portafolios)",
        xaxis_title="Volatilidad histórica anualizada (σ)",
        yaxis_title="Media histórica logarítmica anualizada (ḡ)",
        margin=dict(t=60, b=40, l=40, r=20),
        height=PRESELECTION_CHART_HEIGHT,
        xaxis_tickformat=".1%",
        yaxis_tickformat=".1%",
        legend=dict(orientation="h", yanchor="top", y=-0.14, x=0),
        **DARK_LAYOUT,
    )
    return fig


# ---------------------------------------------------------------------------
# Capa común de interacción y estilo para TODAS las gráficas (solo presentación).
# No toca x, y, z ni ninguna serie: solo tooltips, ejes, leyenda, selector de periodo,
# colores de signo en barras sin color propio, tamaño y márgenes.
# ---------------------------------------------------------------------------
POSITIVE = "#16A34A"  # verde: resultados positivos
NEGATIVE = "#E5484D"  # rojo: resultados negativos

_RANGE_BUTTONS = [dict(count=1, label="1M", step="month", stepmode="backward"),
                  dict(count=6, label="6M", step="month", stepmode="backward"),
                  dict(count=1, label="1A", step="year", stepmode="backward"),
                  dict(count=1, label="YTD", step="year", stepmode="todate"),
                  dict(step="all", label="Todo")]


def _is_dates(values) -> bool:
    if values is None or len(values) < 2:
        return False
    v = values[0]
    if str(getattr(v, "dtype", "")).startswith("datetime64") or type(v).__name__ == "datetime64":
        return True
    return isinstance(v, (pd.Timestamp,)) or hasattr(v, "year") or (
        isinstance(v, str) and len(v) >= 10 and v[4] == "-" and v[7] == "-")


def _fmt_from_axis(axis) -> str:
    tf = getattr(axis, "tickformat", None) or ""
    if "%" in tf:
        return ".2%"
    return ",.4~f"


def polish(fig: go.Figure) -> go.Figure:
    """Aplica la identidad visual e interacción DPST a una figura ya construida (mismos datos)."""
    lay = fig.layout
    x_fmt = _fmt_from_axis(lay.xaxis)
    y_fmts = {"y": _fmt_from_axis(lay.yaxis), "y2": _fmt_from_axis(lay["yaxis2"] if "yaxis2" in lay else None)}
    time_axis = False
    span_days = 0
    unified = "unified" in str(lay.hovermode or "")
    n_named = 0
    for tr in fig.data:
        kind = tr.type
        if getattr(tr, "showlegend", None) is not False and getattr(tr, "name", None):
            n_named += 1
        if kind in ("scatter", "scattergl", "bar"):
            horiz = kind == "bar" and getattr(tr, "orientation", None) == "h"
            xs = tr.y if horiz else tr.x
            dates = _is_dates(list(xs) if xs is not None else None)
            y_fmt = y_fmts.get(getattr(tr, "yaxis", None) or "y", y_fmts["y"])
            if dates and not horiz:
                time_axis = True
                try:
                    d = pd.to_datetime(pd.Series(list(xs)))
                    span_days = max(span_days, (d.max() - d.min()).days)
                except (ValueError, TypeError):
                    pass
            if tr.hovertemplate is None and tr.hoverinfo != "skip":
                head = ("<b>%{text}</b><br>" if tr.text is not None and not tr.name else
                        "<b>%{fullData.name}</b><br>" if tr.name else "")
                if horiz:
                    tr.hovertemplate = head + "%{y}: %{x:" + x_fmt + "}<extra></extra>"
                else:
                    xpart = "" if (unified and dates) else "%{x|%Y-%m-%d}" if dates else ("%{x:" + x_fmt + "}" if tr.x is not None and len(tr.x) and
                                                          isinstance(tr.x[0], (int, float)) else "%{x}") + ("" if (unified and dates) else " · ")
                    tr.hovertemplate = head + xpart + "%{y:" + y_fmt + "}<extra></extra>"
            if kind == "bar" and tr.marker.color is None and getattr(fig.layout, "barmode", None) not in ("stack", "relative"):
                vals = tr.x if horiz else tr.y
                try:
                    nums = [float(v) for v in vals]
                except (TypeError, ValueError):
                    nums = []
                if nums and min(nums) < 0 < max(nums) and len(fig.data) == 1:
                    tr.marker.color = [POSITIVE if v >= 0 else NEGATIVE for v in nums]
            if kind in ("scatter", "scattergl") and tr.mode and "markers" in tr.mode and tr.marker.line.width is None:
                tr.marker.line.width = 1
                tr.marker.line.color = "rgba(255,255,255,0.65)"
        elif kind == "heatmap" and tr.hovertemplate is None:
            tr.hovertemplate = "<b>%{y} · %{x}</b><br>%{z:,.4f}<extra></extra>"
    upd = dict(dragmode="zoom", hoverlabel=dict(namelength=-1),
               modebar=dict(bgcolor="rgba(0,0,0,0)", color="rgba(140,153,179,0.85)", activecolor="#2563EB"),
               legend=dict(itemclick="toggle", itemdoubleclick="toggleothers"))
    if lay.legend.orientation is None and n_named > 1:
        upd["legend"].update(orientation="h", yanchor="top", y=-0.16, x=0)
    if lay.height is None:
        upd["height"] = 420
    fig.update_layout(**upd)
    fig.update_xaxes(automargin=True, title_standoff=10)
    fig.update_yaxes(automargin=True, title_standoff=10)
    if lay.title.text and (lay.title.font.size is None or lay.title.font.size > 18):
        fig.update_layout(title_font_size=18, title_x=0, title_xanchor="left")
    if time_axis:
        fig.update_xaxes(hoverformat="%Y-%m-%d")  # fecha exacta en el encabezado del tooltip
    if time_axis and span_days > 45 and lay.xaxis.rangeselector.buttons in (None, ()):
        fig.update_xaxes(rangeselector=dict(
            buttons=_RANGE_BUTTONS, x=0, xanchor="left", y=1.02, yanchor="bottom",
            bgcolor="rgba(18,26,43,0.9)", activecolor="rgba(52,201,160,0.35)", bordercolor="rgba(148,170,210,0.2)",
            borderwidth=1, font=dict(color="#E8EDF6", size=11)))
        if (lay.margin.t or 0) < 70:
            fig.update_layout(margin_t=max(lay.margin.t or 0, 70) + (24 if lay.title.text else 0))
    return fig
