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
