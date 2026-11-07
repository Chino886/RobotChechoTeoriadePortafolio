"""
Punto de entrada de la aplicación.
Robot analítico para la preselección de activos - Teoría Moderna de
Portafolios, Tech Business School - Universidad EIA.
"""
import base64
import json
from pathlib import Path

import feedparser
import pandas as pd
import requests
import streamlit as st
import yfinance as yf

from src import access_log
from src.analytics import (
    FREQUENCY_PERIODS_PER_YEAR,
    MIN_DIAGNOSTICS_N,
    descriptive_stats,
    drawdown_series,
    log_returns,
    max_drawdown,
    recent_window_stats,
    run_diagnostics,
)
from src.auth import is_auth_configured, require_login
from src.charts import forecast_chart, price_chart, return_chart, risk_return_map
from src.comparison import (
    MIN_COMPARISON_ASSETS,
    build_comparison,
    comparison_table,
    export_parameters,
    non_dominated_tickers,
    preselect_max_mean_under_risk_limit,
    preselect_max_rvr,
    preselect_min_vol_under_min_mean,
    preselect_non_dominated,
    processed_prices_export,
)
from src.data import FREQUENCY_RULES, fetch_asset_data, fetch_fx_to_usd, fetch_many, resample_prices
from src.market import fetch_quotes
from ayuda import AYUDA
from src.connectivity import run_checks
from src.tickers import fallback_tickers, fetch_us_tickers, search as search_tickers
from src.trace import git_commit
from src.risk_extras import expected_shortfall_fraction
from src.rates import fetch_bond_series, list_long_term_yield_countries, ping_fred, search_bond_series
from laboratorio_v2 import LAB_MODULES, render_portfolio_lab
from html import escape as html_escape

from src.ui_fx import (apply_ui_fx, empty_state_html, icon, news_carousel_html, page_header_html,
                       section_label_html)
from src.news_links import verify_items
from src.forecasting import (
    FORECAST_MODELS,
    WALKFORWARD_ORIGINS,
    forecast_path,
    max_valid_horizon,
    periods_until,
    terminal_distribution,
    walk_forward_validate,
)
from src.risk_rules import (
    DEFAULT_BR_MIN,
    DEFAULT_CB,
    DEFAULT_CS,
    DEFAULT_PL,
    DEFAULT_PU,
    RiskParameters,
    compute_var,
    evaluate_signal,
    terminal_probabilities,
)

# ---------------------------------------------------------------------------
# MODO DESARROLLO: mientras no tengan credenciales OIDC reales, dejen esto en
# True para poder probar el resto de la app (datos, análisis, forecasting,
# riesgo, comparación) sin quedar bloqueados por el login. Antes de la
# entrega final, si el profesor confirma que el login es obligatorio, pasen
# esto a False y usen las credenciales reales.
# ---------------------------------------------------------------------------
DEV_MODE = True

# ---------------------------------------------------------------------------
# IDENTIDAD DEL EQUIPO (RF-01)
# ---------------------------------------------------------------------------
SYSTEM_NAME = "Pre - Asset Allocation Analytic Bot"
BRAND_NAME = "DPST"  # nombre visual del bot; SYSTEM_NAME sigue siendo el nombre oficial del entregable
# Relativo a este archivo (no al directorio de trabajo): Streamlit Cloud corre la
# app desde la raíz del repo, no desde robot_analitico/.
LOGO_PATH = Path(__file__).parent / "static" / "logo.svg"
TEAM_NAME = "Equipo DPST"
MEMBERS = [
    "Sergio Delgado Laverde",
    "David Angel Perez",
    "Pedro Velez Uribe",
    "Tomás Giraldo Gomez",
]
VERSION = "2.0.0"
LAST_UPDATE = "2026-11-06"

EXECUTION_POLICY_SUMMARY = (
    "Piloto académico restringido. Preselección (v1): posición larga únicamente, "
    "rendimiento logarítmico exclusivo, puede emitir 'no señal' y no calcula "
    "portafolios, pesos, covarianzas ni frontera eficiente. El laboratorio v2 sí "
    "arma carteras, solo como simulación académica: no envía órdenes."
)

# Descripciones cortas de cada prueba de diagnóstico (sección 5.4), mostradas
# en la app para que quede claro qué mide cada una además del resultado.
DIAGNOSTIC_DESCRIPTIONS = {
    "Jarque-Bera (normalidad)": (
        "Compara la asimetría y la curtosis de los rendimientos con las que "
        "tendría una distribución normal perfecta. Entre más distintas sean, "
        "más alto sale el estadístico y más bajo el p-valor."
    ),
    "Ljung-Box (dependencia)": (
        "Revisa si los rendimientos de distintos días están correlacionados "
        "entre sí (autocorrelación) hasta cierto número de rezagos. Si hay un "
        "patrón que se repite en el tiempo, el estadístico sube y el p-valor "
        "baja."
    ),
    "Brown-Forsythe (homocedasticidad)": (
        "Divide la muestra en bloques cronológicos y compara si la "
        "volatilidad (varianza) es parecida entre esos bloques. Si algún "
        "bloque resulta mucho más volátil que otro, el estadístico sube y el "
        "p-valor baja."
    ),
    "ARCH-LM (varianza condicional)": (
        "Revisa si los periodos de alta volatilidad tienden a agruparse "
        "('volatility clustering'), es decir, si la varianza de hoy depende "
        "de la varianza de días recientes. Si existe ese patrón, el "
        "estadístico sube y el p-valor baja."
    ),
}

# Explicaciones cortas de cada criterio de preselección (RF-21, sección 5.8),
# mostradas justo debajo del selector para que quede claro qué hace cada uno.
CRITERION_EXPLANATIONS = {
    "Máxima media histórica bajo límite de riesgo": (
        "De los activos cuya volatilidad anualizada NO supera el límite que "
        "definas abajo, escoge el que tenga la media histórica anualizada "
        "más alta. Si ningún activo cumple ese límite de riesgo, no se "
        "selecciona ninguno."
    ),
    "Mínima volatilidad bajo media mínima": (
        "De los activos cuya media histórica anualizada sea al menos la que "
        "definas abajo, escoge el que tenga la menor volatilidad anualizada. "
        "Si ningún activo alcanza esa media mínima, no se selecciona "
        "ninguno."
    ),
    "Máxima razón individual media-volatilidad (RVR)": (
        "Calcula, para cada activo POR SEPARADO, su propia razón "
        "media anualizada / volatilidad anualizada (una especie de "
        "'rendimiento por unidad de riesgo' individual) y escoge el activo "
        "con el valor más alto. No combina ni pondera activos entre sí, solo "
        "compara activos individuales uno por uno."
    ),
    "Conjunto no dominado (media-volatilidad)": (
        "Un activo está 'dominado' cuando existe otro activo del lote con "
        "media igual o mayor Y volatilidad igual o menor al mismo tiempo (es "
        "decir, otro activo es mejor o igual en las dos cosas a la vez). "
        "Este criterio devuelve TODOS los activos que no están dominados por "
        "ningún otro, así que puede devolver varios, no necesariamente uno "
        "solo."
    ),
}

# Texto mínimo obligatorio (guía, sección 3.3). No reducir su alcance.
DISCLAIMER_TEXT = (
    "Esta aplicación fue desarrollada exclusivamente como actividad evaluativa del "
    "curso Teoría Moderna de Portafolios de Tech Business School - Universidad EIA. "
    "Sus datos, modelos y resultados tienen fines académicos y educativos. En ningún "
    "momento constituye asesoría financiera, recomendación de inversión ni una "
    "herramienta para tomar decisiones de inversión en la vida real. Es una "
    "herramienta académica que deberá revisarse, validarse y ajustarse, y puede "
    "contener errores, omisiones, rezagos o información incompleta. El sistema no "
    "ejecuta operaciones ni garantiza resultados."
)


INSTITUTION = "Tech Business School – Universidad EIA"
# Título del laboratorio v2 en el menú superior y en su página (el equipo lo va a renombrar).
LAB_TITLE = "Laboratorio de portafolios"

def _logo_b64() -> str:
    try:
        return base64.b64encode(LOGO_PATH.read_bytes()).decode()
    except OSError:
        return ""


# Estilo del menú superior (pestañas principales) y de las tarjetas de Inicio.
# Como el resto de la CSS, apunta a clases internas de Streamlit (st-key-*,
# data-testid, data-baseweb) y puede requerir ajuste si cambia la versión.
NAV_CSS = """
<style>
/* Menú superior: barra fija arriba con las pestañas principales (solo las
   del contenedor dpst_nav; las pestañas internas de cada sección no cambian). */
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] {
    position: sticky; top: 3.6rem; z-index: 99;
    background: rgba(10, 15, 28, 0.92); backdrop-filter: blur(8px);
    border: 1px solid rgba(255, 255, 255, 0.07); border-radius: 14px;
    padding: 0.35rem 0.5rem; gap: 0.35rem; margin-bottom: 0.8rem;
    display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap;
}
/* Marca a la izquierda de la barra (logo + DPST), las secciones a la derecha. */
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"]::before {
    content: "__BRAND__"; margin-right: auto; padding: 0.3rem 0.6rem 0.3rem 2.6rem;
    font-size: 1.3rem; font-weight: 800; letter-spacing: -0.01em; color: #E8EDF6;
    background: url("data:image/svg+xml;base64,__LOGO_B64__") no-repeat 0.4rem center / 1.9rem;
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] {
    padding: 0.55rem 1.1rem; border-radius: 10px; height: auto; transition: background 0.15s;
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"]:hover {
    background: rgba(255, 255, 255, 0.04);
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] p {
    font-size: 1.02rem; font-weight: 600; color: #AEB9CE;
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"][aria-selected="true"] {
    background: rgba(52, 201, 160, 0.12);
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"][aria-selected="true"] p {
    color: #34C9A0;
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] .react-aria-SelectionIndicator {
    display: none;
}

@media (max-width: 640px) {
    .st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] { position: static; }
}

/* Botones principales verde esmeralda con texto oscuro (como "Empezar ahora"). */
[data-testid="stBaseButton-primary"] {
    background: linear-gradient(180deg, #6FE3C1, #22A883); color: #0A0F1C; border: none; font-weight: 700;
    border-radius: 10px; box-shadow: 0 6px 20px rgba(52, 201, 160, 0.22);
    transition: transform 0.2s, box-shadow 0.2s, filter 0.2s;
}
[data-testid="stBaseButton-primary"] p { color: #0A0F1C; font-weight: 700; }
[data-testid="stBaseButton-primary"]:hover {
    filter: brightness(1.06); color: #0A0F1C; transform: translateY(-1px);
    box-shadow: 0 10px 28px rgba(52, 201, 160, 0.32);
}

/* Encabezado de cada página: título serif editorial con etiqueta mono. */
.dpst-page-title {
    margin: 0.4rem 0 0; font-family: 'Instrument Serif', Georgia, serif; font-weight: 400;
    font-size: 2.6rem; line-height: 1.05; letter-spacing: -0.01em; color: #E8EDF6;
}
.dpst-page-sub { color: #8C99B3; margin: 0.3rem 0 0.6rem; max-width: 70ch; }

/* Inicio: portada con gráfico animado */
@keyframes dpst-rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes dpst-draw { from { stroke-dashoffset: 1200; } to { stroke-dashoffset: 0; } }
@keyframes dpst-fade { from { opacity: 0; } to { opacity: 1; } }
@keyframes dpst-pulse { 50% { opacity: 0.35; } }
@keyframes dpst-tape { to { transform: translateX(-50%); } }

.dpst-hero {
    position: relative; overflow: hidden;
    padding: 2.2rem 2.2rem 0; border-radius: 22px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: radial-gradient(900px 340px at 100% 0%, rgba(52, 201, 160, 0.14), transparent 60%),
                radial-gradient(700px 300px at 0% 100%, rgba(106, 168, 255, 0.08), transparent 60%), #0E1526;
}
.dpst-hero .copy { position: relative; z-index: 2; max-width: 52%; animation: dpst-rise 0.8s cubic-bezier(.2,.8,.2,1) both; }
.dpst-hero h1 {
    margin: 0.7rem 0 0.2rem; font-family: 'Instrument Serif', Georgia, serif !important; font-weight: 400 !important;
    font-size: clamp(2.8rem, 6vw, 4.6rem) !important; line-height: 0.95; letter-spacing: -0.015em;
}
.dpst-hero .sub { font-size: 1.15rem; color: #C6D0E2; }
.dpst-hero .meta {
    color: #8C99B3; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.78rem;
    letter-spacing: 0.04em; margin-top: 0.8rem;
}
.dpst-hero .spark {
    position: absolute; right: 0; bottom: 3.4rem; width: 45%; height: 62%; z-index: 1; pointer-events: none;
}
.dpst-hero .spark .area { animation: dpst-fade 1.6s ease 0.6s both; }
.dpst-hero .spark .line { stroke-dasharray: 1200; animation: dpst-draw 2.2s cubic-bezier(.6,.1,.2,1) 0.2s both; }
.dpst-hero .spark .dot { animation: dpst-fade 0.4s ease 2.3s both; }
.dpst-hero .spark .halo { animation: dpst-pulse 2.4s ease-in-out 2.4s infinite; }
.dpst-tape {
    position: relative; z-index: 2; margin: 1.6rem -2.2rem 0; padding: 0.75rem 0; overflow: hidden;
    border-top: 1px solid rgba(148, 170, 210, 0.14); background: rgba(10, 15, 28, 0.55);
}
.dpst-tape .track {
    display: flex; gap: 2.4rem; width: max-content; animation: dpst-tape 40s linear infinite;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.78rem; letter-spacing: 0.12em;
    text-transform: uppercase; color: #8C99B3; white-space: nowrap;
}
.dpst-tape .track span::before { content: "▲"; color: #34C9A0; margin-right: 0.6rem; font-size: 0.7em; }
.dpst-pill {
    display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.3rem 0.8rem; border-radius: 999px;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.72rem; font-weight: 500; letter-spacing: 0.12em;
    color: #BDEFDF; background: rgba(52, 201, 160, 0.10); border: 1px solid rgba(52, 201, 160, 0.35);
}
.dpst-pill::before {
    content: ""; width: 7px; height: 7px; border-radius: 50%; background: #34C9A0;
    box-shadow: 0 0 10px #34C9A0; animation: dpst-pulse 2.4s infinite;
}
.dpst-notice {
    margin-top: 0.6rem; padding: 1.1rem 1.3rem; border-radius: 14px; border: 1px solid rgba(245, 184, 75, 0.35);
    background: rgba(245, 184, 75, 0.07); color: #E8EDF6;
}
.dpst-notice b { color: #F5B84B; }
.dpst-card {
    min-height: 200px; padding: 1.2rem 1.2rem; border-radius: 16px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: linear-gradient(180deg, rgba(18, 26, 43, 0.85), rgba(18, 26, 43, 0.55));
    backdrop-filter: blur(8px); position: relative; overflow: hidden;
    transition: border-color 0.3s, transform 0.4s cubic-bezier(.2,.8,.2,1), box-shadow 0.3s;
    animation: dpst-rise 0.7s cubic-bezier(.2,.8,.2,1) both;
}
.dpst-card::after {
    content: ""; position: absolute; inset: 0 0 auto 0; height: 2px;
    background: linear-gradient(90deg, transparent, #34C9A0, transparent); opacity: 0; transition: opacity 0.3s;
}
.dpst-card:hover {
    border-color: rgba(52, 201, 160, 0.45); transform: translateY(-4px);
    box-shadow: 0 14px 34px rgba(0, 0, 0, 0.35);
}
.dpst-card:hover::after { opacity: 1; }
.dpst-card .n { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.72rem; letter-spacing: 0.12em; color: #34C9A0; }
.dpst-card .t { font-family: 'Instrument Serif', Georgia, serif; font-size: 1.55rem; line-height: 1.1; margin: 0.5rem 0 0.4rem; color: #E8EDF6; }
.dpst-card .d { color: #94A1BA; font-size: 0.9rem; line-height: 1.5; }

@media (max-width: 760px) {
    .dpst-hero { padding: 1.6rem 1.2rem 0; }
    .dpst-hero .copy { max-width: 100%; }
    .dpst-hero .spark { width: 100%; height: 45%; opacity: 0.45; }
    .dpst-tape { margin: 1.4rem -1.2rem 0; }
}
@media (prefers-reduced-motion: reduce) {
    .dpst-tape .track, .dpst-pill::before, .dpst-hero .spark * { animation: none !important; }
    .dpst-hero .spark .line { stroke-dasharray: none; }
}
</style>
""".replace("__LOGO_B64__", _logo_b64()).replace("__BRAND__", BRAND_NAME)

def _logo_svg(size: int = 44, gradient_id: str = "logoGrad") -> str:
    """
    SVG del logo (static/logo.svg) con tamaño y id de gradiente ajustables:
    si se inserta dos veces en la página, cada copia necesita su propio id.
    Devuelve 💠 si el archivo no está, para no romper el encabezado.
    """
    try:
        svg = LOGO_PATH.read_text()
    except OSError:
        return "💠"
    return (
        svg.replace('width="44" height="44"', f'width="{size}" height="{size}"')
        .replace("logoGrad", gradient_id)
    )


def render_header() -> None:
    st.set_page_config(page_title=SYSTEM_NAME, page_icon="📊", layout="wide", initial_sidebar_state="collapsed")
    # Estilo visual (tema oscuro fintech). OJO: esta CSS apunta a atributos
    # internos de Streamlit (data-testid), que no son API oficial; si se
    # actualiza la versión de Streamlit puede requerir ajuste.
    st.markdown(
        """
        <style>
        /* Tipografía Inter (sitio web moderno) importada desde Google Fonts vía
           @import (debe ir primero en el bloque). Requiere internet para cargar
           la fuente; si falla, el navegador usa el fallback sans-serif y la app
           no se rompe. Los selectores [class*="css"] y [data-testid="..."] apuntan
           a clases internas no oficiales de Streamlit, igual que la CSS de bordes
           redondeados de abajo, y pueden necesitar ajuste si cambia la versión. */
        @import url('https://fonts.googleapis.com/css2?family=Geist:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&family=Instrument+Serif:ital@0;1&display=swap');

        /* Tokens de diseño (azul noche + esmeralda). Si cambian colores, cámbienlos aquí
           y en .streamlit/config.toml / src/charts.py. */
        :root {
            --dpst-bg: #0A0F1C; --dpst-surface: #121A2B; --dpst-ink: #E8EDF6; --dpst-muted: #8C99B3;
            --dpst-line: rgba(148, 170, 210, 0.14); --dpst-accent: #34C9A0; --dpst-accent-2: #6AA8FF;
            --dpst-display: 'Instrument Serif', 'Iowan Old Style', Georgia, serif;
            --dpst-body: 'Geist', 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            --dpst-mono: 'Geist Mono', ui-monospace, 'SFMono-Regular', Menlo, monospace;
        }

        html, body, [class*="css"], [data-testid="stAppViewContainer"],
        [data-testid="stSidebar"], [data-testid="stMarkdownContainer"],
        [data-testid="stCaptionContainer"], .stButton button, .stSelectbox, .stTextInput input, .stTextArea textarea {
            font-family: var(--dpst-body) !important;
        }

        /* Fondo con dos halos suaves (verde arriba a la derecha, azul a la izquierda). */
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(1000px 520px at 100% -10%, rgba(52, 201, 160, 0.09), transparent 60%),
                radial-gradient(800px 600px at -10% 40%, rgba(106, 168, 255, 0.06), transparent 60%),
                var(--dpst-bg);
        }
        [data-testid="stHeader"] { background: rgba(10, 15, 28, 0.6); backdrop-filter: blur(12px); }

        h1, h2, h3 {
            font-family: var(--dpst-body) !important;
            font-weight: 600 !important;
            letter-spacing: -0.02em;
        }

        /* Números alineados en tablas, métricas y código. */
        [data-testid="stMetricValue"], [data-testid="stDataFrame"], [data-testid="stTable"], code {
            font-family: var(--dpst-mono) !important; font-variant-numeric: tabular-nums;
        }
        [data-testid="stMetric"] {
            padding: 0.9rem 1.1rem; border-radius: 14px; border: 1px solid var(--dpst-line);
            background: rgba(18, 26, 43, 0.6); backdrop-filter: blur(8px);
            transition: border-color 0.25s, transform 0.25s;
        }
        [data-testid="stMetric"]:hover { border-color: rgba(52, 201, 160, 0.45); transform: translateY(-2px); }
        [data-testid="stMetricLabel"] p {
            font-family: var(--dpst-mono) !important; text-transform: uppercase; letter-spacing: 0.1em;
            font-size: 0.72rem !important; color: var(--dpst-muted) !important;
        }

        /* Gráficos y tablas dentro de una tarjeta de vidrio. */
        [data-testid="stPlotlyChart"] {
            padding: 0.4rem; border-radius: 16px; border: 1px solid var(--dpst-line);
            background: rgba(18, 26, 43, 0.55);
        }
        [data-testid="stDataFrame"], [data-testid="stTable"] {
            border-radius: 14px; border: 1px solid var(--dpst-line); overflow: hidden;
        }

        /* Botones secundarios: píldora con borde que se enciende al pasar el mouse. */
        [data-testid="stBaseButton-secondary"] {
            border-radius: 10px; border: 1px solid var(--dpst-line); background: rgba(232, 237, 246, 0.03);
            transition: border-color 0.2s, background 0.2s, transform 0.2s;
        }
        [data-testid="stBaseButton-secondary"]:hover {
            border-color: var(--dpst-accent); color: var(--dpst-ink); background: rgba(52, 201, 160, 0.08);
            transform: translateY(-1px);
        }
        [data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] { border-radius: 10px !important; }
        [data-testid="stAlert"] { border-radius: 12px; }

        @media (prefers-reduced-motion: reduce) {
            *, *::before, *::after { animation: none !important; transition: none !important; }
        }

        /* Esquinas redondeadas en todos los bloques; el borde sutil solo en los
           expanders (en cada elemento se veía recargado). Los st.container con
           borde ya traen el suyo de Streamlit. */
        [data-testid="stVerticalBlock"] > div {
            border-radius: 12px;
        }
        [data-testid="stExpander"] details {
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.08);
        }
        /* Los bloques <style> como este dejan un contenedor vacío que suma espacio. */
        [data-testid="stElementContainer"]:has(style) {
            display: none;
        }
        [data-testid="stMainBlockContainer"] {
            padding-top: 3.5rem;
            padding-bottom: 3rem;
        }
        [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"] {
            gap: 1.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(NAV_CSS, unsafe_allow_html=True)


def render_sidebar_style() -> None:
    """
    Estilo del sidebar (tema oscuro fintech) y encabezado de marca, para que
    el login simulado y la sección de noticias se vean como una tarjeta.
    Como la CSS del encabezado, apunta a atributos internos de Streamlit
    (data-testid / data-baseweb) y puede requerir ajuste si cambia la versión.
    """
    st.markdown(
        """
        <style>
        [data-testid="stSidebar"] {
            background-color: #121A2B;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }
        [data-testid="stSidebar"] [data-baseweb="input"],
        [data-testid="stSidebar"] [data-baseweb="base-input"] {
            border-radius: 10px;
        }
        .brand-sidebar-card {
            padding: 0.9rem 1rem;
            margin-bottom: 0.5rem;
            border-radius: 12px 12px 0 0;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-bottom: 2px solid #34C9A0;
            background: linear-gradient(135deg, rgba(52, 201, 160, 0.12), rgba(106, 168, 255, 0.06));
            font-size: 1.25rem;
            font-weight: 700;
            color: #E8EDF6;
            display: flex;
            align-items: center;
            gap: 10px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # La marca ya está en el menú superior; el sidebar queda para sesión y noticias.


def render_disclaimer_gate(user_name: str, user_email: str) -> None:
    """
    Bloquea el análisis hasta que el usuario acepte, por separado, la
    autorización de privacidad y el disclaimer académico (sección 3.3).
    Detiene la ejecución (st.stop) si falta alguna de las dos.

    La primera vez que ambos consentimientos quedan aceptados en esta
    sesión del navegador, registra el acceso (nombre, correo autoinformados
    y ambos consentimientos, con fecha/hora UTC) en un archivo local -
    `data/access_log.sqlite3`, ver `src/access_log.py` -. El curso no
    suministró base de datos, sink ni gestor de secretos institucional
    (sección 7.1, punto 46 de la guía); este registro local es la evidencia
    parcial que se implementó ante esa ausencia. No sustituye el modelo
    completo de sesión/auditoría/purga de la Fase 9 (ver TRACEABILITY.md,
    RF-02, RNF-03).
    """
    if st.session_state.get("terms_accepted", False):
        return

    with st.container(key="dpst_gate"):
        st.markdown('<span class="dpst-pill">PASO 2 DE 2 · CONSENTIMIENTO</span>', unsafe_allow_html=True)
        st.subheader("Antes de continuar")
        st.warning(DISCLAIMER_TEXT)

        privacy_ok = st.checkbox(
            "Autorizo el tratamiento de mis datos según el aviso de "
            "privacidad del piloto académico (Ley 1581 de 2012).",
            value=False, key="consent_privacy",
        )
        disclaimer_ok = st.checkbox(
            "He leído y acepto el disclaimer académico anterior.",
            value=False, key="consent_disclaimer",
        )

        accept_clicked = st.button(
            "Aceptar y continuar",
            type="primary",
            disabled=not (privacy_ok and disclaimer_ok),
        )

    if not accept_clicked:
        st.session_state["access_logged"] = False
        st.stop()

    access_log.log_access(user_name, user_email, privacy_ok, disclaimer_ok)
    st.session_state["access_logged"] = True
    st.session_state["terms_accepted"] = True
    st.rerun()


def render_historical_analysis() -> None:
    """
    Análisis histórico de un activo (RF-09 a RF-12): rendimientos
    logarítmicos, gráficos, descriptivos y drawdown.
    """
    result = st.session_state.get("asset_result")
    frequency = st.session_state.get("asset_frequency")
    if result is None or not result.ok:
        return

    st.caption(f"{result.ticker} · requisitos RF-09 a RF-12")

    prices = result.prices["adjusted_close"]
    returns = log_returns(prices)

    if len(returns) < 2:
        st.warning("Muestra insuficiente para calcular estadísticas (se necesitan al menos 2 rendimientos).")
        return

    periods_per_year = FREQUENCY_PERIODS_PER_YEAR.get(frequency, 252)

    st.latex(r"g_t = \ln\left(\frac{P_t}{P_{t-1}}\right)")

    tab_price, tab_returns, tab_stats, tab_diag = st.tabs(
        ["Precio", "Rendimientos", "Descriptivos", "Diagnósticos"]
    )

    with tab_price:
        st.plotly_chart(
            price_chart(prices, result.ticker, result.currency, frequency, result.source),
            use_container_width=True,
        )
        st.caption(
            f"Último precio: {prices.iloc[-1]:.4f} ({prices.index[-1].date()}) · "
            f"Fuente: {result.source} · Moneda: {result.currency or 'N/D'}"
        )
        with st.expander("Ver datos en tabla (alternativa accesible al gráfico)"):
            st.dataframe(prices.tail(30).rename("precio_ajustado"))

    with tab_returns:
        st.plotly_chart(return_chart(returns, result.ticker, frequency), use_container_width=True)
        st.caption(f"Último log-rendimiento: {returns.iloc[-1]:.6f} ({returns.index[-1].date()})")
        st.info(
            "**¿Qué es un rendimiento logarítmico?** Es la variación del precio "
            "entre un periodo y el anterior, calculada con el logaritmo natural: "
            "g_t = ln(P_t / P_{t-1}). Un valor de 0.02 equivale aproximadamente a "
            "una subida de 2% respecto al periodo anterior, y uno de -0.02 a una "
            "caída de aproximadamente 2%. Se usa el logaritmo en vez del "
            "porcentaje simple porque los rendimientos logarítmicos de varios "
            "periodos se pueden sumar directamente para obtener el rendimiento "
            "acumulado, y porque sus propiedades estadísticas son las que asumen "
            "los modelos de esta guía (RF-10)."
        )
        with st.expander("Ver datos en tabla (alternativa accesible al gráfico)"):
            st.dataframe(returns.tail(30).rename("log_rendimiento"))

    with tab_stats:
        stats = descriptive_stats(returns, periods_per_year)
        recent_stats, is_partial = recent_window_stats(returns, periods_per_year)

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Muestra completa**")
            st.write(
                {
                    "n": stats.n,
                    "media": stats.mean,
                    "mediana": stats.median,
                    "varianza": stats.variance,
                    "desv. estándar": stats.std,
                    "mínimo": stats.minimum,
                    "P25": stats.p25,
                    "P75": stats.p75,
                    "máximo": stats.maximum,
                    "asimetría (Fisher)": stats.skewness,
                    "exceso de curtosis (Fisher)": stats.excess_kurtosis,
                    "media anualizada": stats.mean_annualized,
                    "volatilidad anualizada": stats.std_annualized,
                    "percentil (midrank) del último g_t": stats.last_return_percentile,
                }
            )
        with col2:
            label = "Ventana reciente" + (" (PARCIAL, T < m)" if is_partial else "")
            st.markdown(f"**{label}**")
            st.write(
                {
                    "n": recent_stats.n,
                    "media": recent_stats.mean,
                    "desv. estándar": recent_stats.std,
                    "media anualizada": recent_stats.mean_annualized,
                    "volatilidad anualizada": recent_stats.std_annualized,
                }
            )

        dd = drawdown_series(prices)
        st.metric("Máxima caída histórica (drawdown)", f"{max_drawdown(prices):.2%}")
        st.line_chart(dd, height=200)

    with tab_diag:
        st.markdown(
            "Contrastes de los supuestos que sustentan el uso de modelos "
            "**homocedásticos** (sección 5.4 de la guía). Ningún rechazo "
            "bloquea el análisis: se muestran como advertencias informativas, "
            "nunca como error."
        )
        st.caption(
            "**Regla de aceptación/rechazo (para las cuatro pruebas):** cada "
            "una compara su p-valor contra alfa = 5%. Si el p-valor es MENOR "
            "que 5%, se rechaza la hipótesis nula (el supuesto no se cumple "
            "en esta muestra, ícono ⚠️); si es mayor o igual, no se rechaza "
            "(el supuesto es razonable con esta muestra, ícono ✅)."
        )
        if len(returns) < MIN_DIAGNOSTICS_N:
            st.info(
                f"Muestra insuficiente para diagnósticos confiables "
                f"(hay {len(returns)} rendimientos, se recomiendan al menos "
                f"{MIN_DIAGNOSTICS_N}). No se muestran los contrastes."
            )
        else:
            for diag in run_diagnostics(returns):
                icon = "⚠️" if diag.reject else "✅"
                with st.expander(f"{icon} {diag.name}", expanded=diag.reject):
                    st.write(f"**¿Qué revisa esta prueba?** {DIAGNOSTIC_DESCRIPTIONS.get(diag.name, '')}")
                    st.write(f"**Hipótesis nula:** {diag.hypothesis}")
                    st.write(f"**Parámetros:** {diag.parameters}")
                    col_a, col_b = st.columns(2)
                    col_a.metric("Estadístico", f"{diag.statistic:.4f}")
                    col_b.metric("p-valor", f"{diag.p_value:.4f}")
                    if diag.reject:
                        st.warning(diag.interpretation)
                    else:
                        st.success(diag.interpretation)


def render_forecast() -> None:
    """
    Pronóstico homocedástico multihorizonte y validación walk-forward
    (RF-13 a RF-15, secciones 5.5 y 8.1 de la guía).
    """
    result = st.session_state.get("asset_result")
    frequency = st.session_state.get("asset_frequency")
    if result is None or not result.ok:
        return

    prices = result.prices["adjusted_close"]
    returns = log_returns(prices)
    if len(returns) < 2:
        return

    p0 = float(prices.iloc[-1])
    last_date = prices.index[-1]
    periods_per_year = FREQUENCY_PERIODS_PER_YEAR[frequency]
    h_max = max_valid_horizon(len(returns), periods_per_year)
    if h_max < 1:
        st.warning(
            "La muestra disponible no alcanza para validar ningún horizonte H con la "
            "regla de suficiencia de la sección 5.5 (T >= max(2m,5H)+H+9). "
            "Elijan un rango de fechas más amplio."
        )
        return

    st.caption(f"{result.ticker} · requisitos RF-13 a RF-15")
    st.caption(
        "Piloto académico: los modelos son homocedásticos por alcance pedagógico. "
        "Si los diagnósticos de la pestaña anterior muestran volatilidad variable o "
        "colas gruesas, los resultados siguientes se mantienen homocedásticos de "
        "todas formas y deben leerse como condicionales a ese supuesto."
    )

    col_model, col_h_mode = st.columns(2)
    with col_model:
        model_label = st.selectbox("Modelo", list(FORECAST_MODELS.keys()), key="forecast_model")
    with col_h_mode:
        h_mode = st.radio(
            "Definir horizonte H como", ["Cantidad de periodos", "Fecha objetivo"],
            horizontal=True, key="forecast_h_mode",
        )

    if h_mode == "Cantidad de periodos":
        st.caption(
            f"H máximo admitido con los datos actuales: {h_max} periodo(s) "
            "(límite justificado por la regla de suficiencia walk-forward de la "
            "sección 5.5: T >= max(2m,5H)+H+9 — RF-04)."
        )
        horizon = st.number_input(
            f"H (en periodos de frecuencia '{frequency}')", min_value=1, max_value=h_max,
            value=min(10, h_max), step=1, key="forecast_h_periods",
        )
    else:
        target_date = st.date_input(
            "Fecha objetivo", value=last_date + pd.Timedelta(days=14), key="forecast_target_date",
        )
        horizon = periods_until(last_date, target_date, frequency)
        if horizon <= 0:
            st.warning("La fecha objetivo debe ser posterior a la última fecha con dato.")
            return
        if horizon > h_max:
            st.warning(
                f"La fecha objetivo implica H={horizon}, que supera el límite H_max={h_max} "
                "admitido por la regla de suficiencia walk-forward de la sección 5.5 "
                "(T >= max(2m,5H)+H+9). Elijan una fecha objetivo más cercana."
            )
            return
        st.caption(
            f"H convertido a {horizon} periodo(s) de frecuencia '{frequency}' entre "
            f"{last_date.date()} y {target_date}."
        )

    horizon = int(horizon)
    fit_fn = FORECAST_MODELS[model_label]
    model = fit_fn(returns)
    dist = terminal_distribution(model, p0, horizon)
    steps = forecast_path(model, p0, horizon)

    st.latex(r"P_H = P_0 \cdot \exp(g_{1} + g_{2} + \dots + g_{H}), \quad g_{1}+\dots+g_{H} \sim \mathcal{N}(m_H,\, v_H)")
    st.write(
        f"**Modelo:** {dist.model_name} · **Parámetros (por periodo, de la muestra de entrenamiento):** "
        f"media = {dist.mean_per_period:.6f}, sigma = {dist.std_per_period:.6f}, "
        f"n = {model.n_train} · **Supuesto:** homocedástico, sin autocorrelación."
    )
    if dist.is_deterministic:
        st.info(
            "Varianza predictiva igual a cero (rama determinista, sección 5.4.1): "
            "todos los cuantiles coinciden con la mediana."
        )

    tab_traj, tab_terminal, tab_wf, tab_risk = st.tabs(
        ["Trayectoria 1..H", "Distribución terminal", "Validación walk-forward", "Riesgo y niveles"]
    )

    with tab_traj:
        st.plotly_chart(forecast_chart(prices, steps, result.ticker, frequency), use_container_width=True)
        st.dataframe(
            pd.DataFrame(
                {
                    "paso (k)": [s.step for s in steps],
                    "m_k": [s.m_k for s in steps],
                    "v_k": [s.v_k for s in steps],
                    "mediana": [s.median_price for s in steps],
                    "media": [s.mean_price for s in steps],
                    "Q05": [s.q05_price for s in steps],
                    "Q95": [s.q95_price for s in steps],
                }
            ).set_index("paso (k)")
        )

    with tab_terminal:
        target_label = (last_date + pd.tseries.offsets.BDay(horizon)).date() if frequency == "Diaria" else None
        st.write(f"**Horizonte H = {horizon}** periodo(s)" + (f" · fecha objetivo aprox.: {target_label}" if target_label else ""))
        col1, col2, col3 = st.columns(3)
        col1.metric("Mediana P_H", f"{dist.median_price:.4f}")
        col2.metric("Media P_H", f"{dist.mean_price:.4f}")
        col3.metric("P(P_H > P0)", f"{dist.prob_above_entry:.2%}")
        col4, col5, col6 = st.columns(3)
        col4.metric("Q05 P_H", f"{dist.q05_price:.4f}")
        col5.metric("Q95 P_H", f"{dist.q95_price:.4f}")
        col6.metric("m_H / v_H", f"{dist.m_h:.6f} / {dist.v_h:.6f}")

    with tab_wf:
        st.caption(
            f"Ventana expansiva, últimos {WALKFORWARD_ORIGINS} orígenes consecutivos, "
            "reestimación solo con datos disponibles en cada origen (sin look-ahead). "
            "Objetivo: rendimiento logarítmico acumulado a H."
        )
        wf = walk_forward_validate(returns, fit_fn, model_label, horizon, periods_per_year)
        if not wf.ok:
            st.warning(f"Validación insuficiente (no señal sustentada): {wf.reason}")
        else:
            col_a, col_b, col_c, col_d = st.columns(4)
            col_a.metric("RMSE (log-espacio)", f"{wf.rmse:.6f}")
            col_b.metric("MAE (log-espacio)", f"{wf.mae:.6f}")
            col_c.metric("Cobertura IC 90%", f"{wf.coverage_90:.0%}")
            col_d.metric(
                "Exactitud direccional",
                f"{wf.directional_accuracy:.0%}" if wf.directional_accuracy is not None else "N/D",
                help="N/D si el modelo no define una dirección (p.ej. caminata aleatoria, m_H=0).",
            )
            st.dataframe(
                pd.DataFrame(
                    {
                        "origen (índice)": [o.origin_index for o in wf.origins],
                        "n entrenamiento": [o.n_train for o in wf.origins],
                        "pronóstico (m_H)": [o.forecast_cum_return for o in wf.origins],
                        "Q05": [o.q05_cum_return for o in wf.origins],
                        "Q95": [o.q95_cum_return for o in wf.origins],
                        "real (acumulado)": [o.actual_cum_return for o in wf.origins],
                        "dentro IC 90%": [o.in_interval_90 for o in wf.origins],
                        "dirección correcta": [
                            "N/D" if o.direction_correct is None else o.direction_correct for o in wf.origins
                        ],
                    }
                ).set_index("origen (índice)")
            )

    with tab_risk:
        st.caption(
            "VaR, probabilidades, entrada, stop-loss y take-profit comparten el mismo "
            f"modelo ({dist.model_name}) y el mismo horizonte (H={horizon}) que las "
            "pestañas anteriores (RF-16 a RF-18, secciones 5.6 y 5.7)."
        )

        col_cap, col_conf, col_brmin = st.columns(3)
        with col_cap:
            capital = st.number_input(
                "Capital a invertir", min_value=0.0, value=10000.0, step=100.0, key="risk_capital",
            )
        with col_conf:
            confidence_label = st.selectbox(
                "Nivel de confianza del VaR", ["95%", "99%"], key="risk_confidence",
            )
            confidence = 0.95 if confidence_label == "95%" else 0.99
        with col_brmin:
            br_min = st.number_input(
                "BR_min (beneficio/riesgo neto mínimo)", min_value=0.0, value=DEFAULT_BR_MIN,
                step=0.1, key="risk_br_min",
            )

        col_cb, col_cs = st.columns(2)
        with col_cb:
            c_b = st.number_input(
                "Costo de compra c_b (fracción, ej. 0.001 = 0.1%)", min_value=0.0, value=DEFAULT_CB,
                step=0.001, format="%.4f", key="risk_cb",
            )
        with col_cs:
            c_s = st.number_input(
                "Costo de venta c_s (fracción, ej. 0.001 = 0.1%)", min_value=0.0, max_value=0.999,
                value=DEFAULT_CS, step=0.001, format="%.4f", key="risk_cs",
            )

        params = RiskParameters(p_l=DEFAULT_PL, p_u=DEFAULT_PU, br_min=br_min, c_b=c_b, c_s=c_s)

        st.markdown(f"**VaR paramétrico individual ({confidence_label}, RF-16)**")
        var_result = compute_var(model, p0, horizon, confidence, capital)
        es_fraction = expected_shortfall_fraction(model, horizon, confidence)
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        col_v1.metric(f"VaR fraccional ({confidence_label})", f"{var_result.var_fraction:.4%}")
        col_v2.metric("VaR en unidades monetarias", f"{var_result.var_dollar:,.2f}")
        col_v3.metric(f"Pérdida esperada ES ({confidence_label})", f"{es_fraction:.4%}",
                      help="Expected Shortfall: pérdida promedio en los casos en que se supera el VaR, con el mismo "
                           "modelo y horizonte. Siempre es mayor o igual que el VaR.")
        col_v4.metric("ES en unidades monetarias", f"{es_fraction * capital:,.2f}")

        st.divider()
        st.markdown(f"**Entrada, stop-loss y take-profit (p_L={params.p_l:.0%}, p_U={params.p_u:.0%}, RF-17)**")
        signal = evaluate_signal(model, p0, horizon, params)
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        col_s1.metric("Entrada (E = P0)", f"{signal.entry:.4f}")
        col_s2.metric("Stop-loss (SL_H)", f"{signal.sl_h:.4f}")
        col_s3.metric("Take-profit (TP_H)", f"{signal.tp_h:.4f}")
        col_s4.metric("Precio de equilibrio (P_BE)", f"{signal.p_be:.4f}")

        col_n1, col_n2, col_n3 = st.columns(3)
        col_n1.metric("Riesgo neto (D_neto)", f"{signal.d_neto:.4f}" if signal.d_neto is not None else "N/D")
        col_n2.metric("Beneficio neto (U_neto)", f"{signal.u_neto:.4f}" if signal.u_neto is not None else "N/D")
        col_n3.metric("BR_neto", f"{signal.br_neto:.4f}" if signal.br_neto is not None else "N/D")
        if signal.br_bruta is not None:
            st.caption(f"BR_bruta (sin costos, referencia): {signal.br_bruta:.4f}")

        if signal.ok:
            st.success("Señal sustentada: se cumplen todas las condiciones de la sección 5.7.")
        else:
            st.warning("No señal (nunca se fuerza una señal). Motivos:")
            for reason in signal.reasons:
                st.write(f"- {reason}")

        st.divider()
        st.markdown("**Probabilidades terminales frente a P_BE (RF-18)**")
        term_probs = terminal_probabilities(model, p0, horizon, signal.p_be)
        col_p1, col_p2, col_p3 = st.columns(3)
        col_p1.metric("Pr(ganar)", f"{term_probs.prob_win:.2%}")
        col_p2.metric("Pr(perder)", f"{term_probs.prob_lose:.2%}")
        col_p3.metric("Pr(neutral)", f"{term_probs.prob_neutral:.2%}" if term_probs.is_deterministic else "N/A")
        if term_probs.is_deterministic:
            st.info(
                "Rama determinista (v_H=0): la probabilidad se concentra por completo "
                "en un único desenlace (ganar, perder o neutral)."
            )


def render_comparison() -> None:
    """
    Comparación de N activos, mapa histórico rendimiento-riesgo, dominancia,
    preselección transparente y exportación (RF-19 a RF-22, sección 5.8).

    Vista independiente del análisis de un solo activo de arriba. No calcula
    pesos, covarianzas, correlaciones conjuntas ni frontera eficiente: es una
    preselección de activos individuales.
    """
    st.caption("Requisitos RF-19 a RF-22")
    st.caption(
        "Vista independiente del análisis de un solo activo. Acepta un mínimo "
        f"simultáneo de {MIN_COMPARISON_ASSETS} activos válidos. No calcula pesos, "
        "covarianzas, correlaciones conjuntas ni frontera eficiente: es una preselección "
        "de activos individuales, no asset allocation."
    )

    default_tickers = (
        "AAPL, MSFT, AMZN, GOOGL, META, NVDA, JPM, JNJ, XOM, PG, "
        "KO, PEP, WMT, HD, COST, UNH, V, MA, CAT, MCD"
    )
    tickers_text = st.text_area(
        "Tickers a comparar (sepáralos por coma o por línea; agrega o borra los que quieras)",
        value=default_tickers,
        key="comparison_tickers_text",
        height=80,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        start_date = st.date_input("Fecha inicial", value=pd.Timestamp("2023-01-01"), key="comparison_start")
    with col2:
        end_date = st.date_input("Fecha final", value=pd.Timestamp.today(), key="comparison_end")
    with col3:
        frequency = st.selectbox("Frecuencia", list(FREQUENCY_RULES.keys()), key="comparison_frequency")

    if st.button("Comparar activos"):
        raw_tickers = [
            t.strip().upper() for chunk in tickers_text.split(",") for t in chunk.split("\n")
        ]
        tickers, seen = [], set()
        for t in raw_tickers:
            if t and t not in seen:
                tickers.append(t)
                seen.add(t)

        if len(tickers) < 2:
            st.error("Escribe al menos 2 tickers para comparar.")
        else:
            with st.spinner(f"Descargando y comparando {len(tickers)} activos..."):
                assets = fetch_many(tickers, start_date, end_date, frequency)

                # Conversión de monedas (RF-20 ampliado): se descarga el tipo
                # de cambio de cada moneda distinta a USD presente entre los
                # activos válidos, para poder compararlos a todos en USD.
                currencies_needed = {
                    (a.currency or "").upper()
                    for a in assets.values()
                    if getattr(a, "ok", False) and a.currency and a.currency.upper() != "USD"
                }
                fx_rates = {}
                fx_errors = []
                for currency in currencies_needed:
                    fx_result = fetch_fx_to_usd(currency, start_date, end_date)
                    st.write(
                        f"DEBUG {currency}: ok={fx_result.ok}, ticker_usado={fx_result.ticker}, "
                        f"error={fx_result.error}, "
                        f"n_filas={0 if fx_result.prices is None else len(fx_result.prices)}"
                    )
                    if fx_result.prices is not None and not fx_result.prices.empty:
                        st.write("Primeras fechas:", fx_result.prices.index.min(), "- Últimas:", fx_result.prices.index.max())
                        st.dataframe(fx_result.prices.head(3))
                    if fx_result.ok and fx_result.prices is not None:
                        fx_result.prices = resample_prices(fx_result.prices, frequency)
                        fx_rates[currency] = fx_result.prices["adjusted_close"]
                    else:
                        fx_errors.append(f"{currency}->USD: {fx_result.error or 'sin datos'}")

                periods_per_year = FREQUENCY_PERIODS_PER_YEAR.get(frequency, 252)
                result = build_comparison(assets, frequency, periods_per_year, fx_rates=fx_rates)
            if fx_errors:
                st.warning(
                    "No se pudo obtener el tipo de cambio para: " + "; ".join(fx_errors) +
                    ". Los activos en esas monedas quedarán excluidos de la comparación."
                )
            st.session_state["comparison_result"] = result

    result = st.session_state.get("comparison_result")
    if result is None:
        return

    if not result.ok:
        st.error(f"No se pudo construir la comparación: {result.reason}")
        if result.excluded:
            with st.expander(f"Activos excluidos ({len(result.excluded)})"):
                for e in result.excluded:
                    st.write(f"- **{e.ticker}**: {e.reason}")
        return

    n_valid = len(result.summaries)
    if n_valid < MIN_COMPARISON_ASSETS:
        st.warning(
            f"Hay {n_valid} activo(s) válido(s) en esta comparación; la guía exige que la "
            f"vista acepte al menos {MIN_COMPARISON_ASSETS} simultáneamente. Agrega más "
            "tickers válidos para cumplir ese mínimo."
        )
    else:
        st.success(f"{n_valid} activos válidos comparados (mínimo exigido: {MIN_COMPARISON_ASSETS}).")

    st.caption(
        f"Moneda base: {result.base_currency} · Frecuencia: {result.frequency} · "
        f"Ventana común: {result.common_start.date()} a {result.common_end.date()} "
        f"({result.n_common} observaciones de precio). Las coordenadas del mapa son "
        "históricas y NO cambian con el horizonte H del pronóstico."
    )

    if result.excluded:
        with st.expander(f"Activos excluidos de esta comparación ({len(result.excluded)})"):
            for e in result.excluded:
                st.write(f"- **{e.ticker}**: {e.reason}")

    non_dominated = non_dominated_tickers(result.summaries)
    table = comparison_table(result, non_dominated)

    tab_table, tab_map, tab_select, tab_export = st.tabs(
        ["Tabla comparativa", "Mapa histórico", "Preselección", "Exportar"]
    )

    with tab_table:
        st.dataframe(table)

    with tab_map:
        st.markdown("**Marca tu elección final**")
        starred = st.selectbox(
            "¿Cuál de estos activos elegiste como tu preselección final?",
            ["(Ninguno)"] + [s.ticker for s in result.summaries],
            key="comparison_starred_ticker",
        )
        starred_value = None if starred == "(Ninguno)" else starred
        st.plotly_chart(
            risk_return_map(result.summaries, non_dominated, starred_value), use_container_width=True
        )
        st.caption(
            "Rombos verdes = activos NO dominados (ningún otro activo del lote ofrece a la "
            "vez media igual o mayor y volatilidad igual o menor). Esto no es una frontera "
            "eficiente de portafolios ni una recomendación de la mejor inversión universal. "
            "La estrella blanca solo marca tu elección personal; no es un criterio de preselección."
        )

    with tab_select:
        st.write(
            "Regla de preselección transparente (RF-21). El resultado se expresa como "
            "'mejor según este criterio y estos parámetros', nunca como la mejor inversión "
            "en términos absolutos."
        )
        st.write("")
        selection_mode = st.radio(
            "¿Cómo quieres elegir el activo preseleccionado?",
            ["Por perfil de riesgo (recomendado)", "Manual (elijo el criterio yo mismo)"],
            horizontal=True,
            key="comparison_selection_mode",
        )
        st.write("")

        if selection_mode == "Por perfil de riesgo (recomendado)":
            risk_profile_explanations = {
                "Conservador": (
                    "Prioriza la estabilidad: elige el activo con menor volatilidad "
                    "entre los que no han tenido rendimiento promedio negativo."
                ),
                "Moderado": (
                    "Busca equilibrio: elige el activo que más rendimiento ha dado "
                    "por cada unidad de volatilidad (mayor razón media-volatilidad)."
                ),
                "Agresivo": (
                    "Prioriza el rendimiento: elige el activo con mayor media histórica "
                    "aceptando una volatilidad anualizada de hasta 40%."
                ),
            }
            col_profile, _ = st.columns([2, 1])
            with col_profile:
                risk_profile = st.selectbox(
                    "¿Qué tan arriesgado quieres ser?",
                    list(risk_profile_explanations.keys()),
                    index=1,
                    key="comparison_risk_profile",
                )
            with st.container(border=True):
                st.markdown(f"**Perfil {risk_profile}**")
                st.caption(risk_profile_explanations[risk_profile])

            if risk_profile == "Conservador":
                selected = preselect_min_vol_under_min_mean(result.summaries, min_mean=0.0)
            elif risk_profile == "Moderado":
                selected = preselect_max_rvr(result.summaries)
            else:
                selected = preselect_max_mean_under_risk_limit(result.summaries, risk_limit=0.40)
        else:
            criterion = st.selectbox(
                "Criterio",
                [
                    "Máxima media histórica bajo límite de riesgo",
                    "Mínima volatilidad bajo media mínima",
                    "Máxima razón individual media-volatilidad (RVR)",
                    "Conjunto no dominado (media-volatilidad)",
                ],
                key="comparison_criterion",
            )
            st.caption(CRITERION_EXPLANATIONS[criterion])

            if criterion == "Máxima media histórica bajo límite de riesgo":
                risk_limit = st.number_input(
                    "Límite de riesgo (volatilidad anualizada máxima aceptable)",
                    min_value=0.0, value=0.30, step=0.01, format="%.4f", key="comparison_risk_limit",
                )
                selected = preselect_max_mean_under_risk_limit(result.summaries, risk_limit)
            elif criterion == "Mínima volatilidad bajo media mínima":
                min_mean = st.number_input(
                    "Media histórica anualizada mínima aceptable",
                    value=0.0, step=0.01, format="%.4f", key="comparison_min_mean",
                )
                selected = preselect_min_vol_under_min_mean(result.summaries, min_mean)
            elif criterion == "Máxima razón individual media-volatilidad (RVR)":
                selected = preselect_max_rvr(result.summaries)
            else:
                selected = preselect_non_dominated(result.summaries)

        if selected:
            tie_note = " (empate)" if len(selected) > 1 else ""
            st.success(f"Mejor según este criterio: {', '.join(selected)}{tie_note}")
        else:
            st.warning("Ningún activo cumple este criterio con los parámetros elegidos.")

    with tab_export:
        st.write("Descarga los datos procesados de esta comparación (RF-22).")
        params = export_parameters(result)
        col_e1, col_e2, col_e3 = st.columns(3)
        with col_e1:
            st.download_button(
                "Precios procesados (CSV)",
                data=processed_prices_export(result).to_csv(index=False),
                file_name="precios_procesados.csv",
                mime="text/csv",
            )
        with col_e2:
            st.download_button(
                "Tabla comparativa (CSV)",
                data=table.reset_index().to_csv(index=False),
                file_name="tabla_comparativa.csv",
                mime="text/csv",
            )
        with col_e3:
            st.download_button(
                "Parámetros (JSON)",
                data=json.dumps(params, indent=2, ensure_ascii=False),
                file_name="parametros_comparacion.json",
                mime="application/json",
            )
def render_sovereign_rates() -> None:
    """
    Tasas de bonos soberanos a 10 años por país, vía la API de FRED.
    Vista de referencia macroeconómica, independiente de la comparación de
    activos de arriba: no entra en el mapa de dominancia ni en la
    preselección (RF-19 a RF-22), es solo información de contexto.
    """
    st.caption(
        "Fuente: FRED (Federal Reserve Economic Data, Banco de la Reserva "
        "Federal de St. Louis). La lista de países se pide en vivo a FRED: aparecen "
        "los que tienen la tasa a 10 años de la OCDE o, si no, la de bonos del gobierno del FMI."
    )

    try:
        fred_api_key = st.secrets.get("FRED_API_KEY")
    except Exception:  # sin secrets.toml, st.secrets lanza en vez de devolver None
        fred_api_key = None
    if not fred_api_key:
        st.info(
            "Esta vista necesita una API key gratuita de FRED configurada en "
            "los secretos de la app (FRED_API_KEY) para funcionar."
        )
        return

    try:
        countries = _fred_countries(fred_api_key)
    except Exception as exc:
        countries = []
        st.error(f"No se pudo obtener de FRED la lista de países: {exc}")
    if not countries:
        _render_rates_free_search(fred_api_key)
        return

    labels = [c["label"] for c in countries]
    by_label = {c["label"]: c for c in countries}
    default = labels.index("Colombia") if "Colombia" in labels else 0
    col_c, col_s, col_e = st.columns([2, 1, 1])
    with col_c:
        label = st.selectbox(
            f"País ({len(countries)} con dato en FRED)", labels, index=default, key="rates_country",
            format_func=lambda x: f"{x} · datos hasta {by_label[x]['observation_end'][:4]}"
            if _is_stale(by_label[x]["observation_end"]) else x,
            help="Los países que tienen en FRED una tasa de bonos del gobierno. Escoge uno y aparece su tasa.",
        )
    with col_s:
        rates_start = st.date_input("Fecha inicial", value=pd.Timestamp("2015-01-01"), key="rates_start")
    with col_e:
        rates_end = st.date_input("Fecha final", value=pd.Timestamp.today(), key="rates_end")

    _render_rate_series(fred_api_key, by_label[label], label, rates_start, rates_end)


def _render_rate_series(fred_api_key: str, info: dict, label: str, rates_start, rates_end) -> None:
    """Tasa actual, cambio en 12 meses, gráfica y tabla de la serie elegida."""
    with st.spinner(f"Descargando de FRED la tasa de {label}..."):
        try:
            series = _fred_series(fred_api_key, info["id"], rates_start, rates_end)
        except Exception as exc:
            st.error(f"Error al descargar la serie: {exc}")
            return
    if series.empty:
        st.warning(f"FRED no tiene observaciones de {label} entre esas fechas (último dato: {info['observation_end']}).")
        return

    m1, m2, m3 = st.columns(3)
    rate_name = "Tasa a 10 años" if info["source"] == "OCDE" else "Tasa de bonos del gobierno"
    m1.metric(f"{rate_name} · {label}", f"{series.iloc[-1]:.2f}%")
    m2.metric("Fecha del último dato", str(series.index[-1].date()))
    year_ago = series[series.index <= series.index[-1] - pd.DateOffset(years=1)]
    if not year_ago.empty:
        m3.metric("Cambio en 12 meses", f"{series.iloc[-1] - year_ago.iloc[-1]:+.2f} p.p.")
    st.line_chart(series.rename(f"{label} (%)"), height=280)
    st.caption(f"Fuente: {info['source']} vía FRED, {info['detail']}; serie {info['frequency']} en % anual. "
               f"Código **{info['id']}** — {info['title']}.")
    if _is_stale(info["observation_end"]):
        st.warning(f"El último dato de {label} en FRED es de {info['observation_end'][:7]}: es una referencia histórica, "
                   "no la tasa actual.")
    with st.expander("Ver datos en tabla"):
        st.dataframe(series.rename("tasa_%"))


def _is_stale(observation_end: str, years: int = 2) -> bool:
    """True si el último dato de la serie tiene más de `years` años."""
    try:
        return pd.Timestamp(observation_end) < pd.Timestamp.today() - pd.DateOffset(years=years)
    except (ValueError, TypeError):
        return True


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _fred_countries(api_key: str, version: int = 3) -> "list[dict]":  # version: invalida la caché vieja
    return list_long_term_yield_countries(api_key)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fred_series(api_key: str, series_id: str, start, end) -> pd.Series:
    return fetch_bond_series(api_key, series_id, start, end)


def _render_rates_free_search(fred_api_key: str) -> None:
    """Respaldo si FRED no entrega la lista de países: búsqueda por texto como antes."""
    country_query = st.text_input(
        "País (en inglés suele funcionar mejor, ej. 'Colombia', 'United States', 'Brazil')",
        value="Colombia",
        key="rates_country_query",
    )

    if st.button("Buscar tasa", key="rates_search_button"):
        with st.spinner(f"Buscando series de FRED para '{country_query}'..."):
            try:
                results = search_bond_series(fred_api_key, country_query)
            except Exception as exc:
                st.error(f"Error al consultar FRED: {exc}")
                results = []
        st.session_state["rates_search_results"] = results

    results = st.session_state.get("rates_search_results", [])
    if not results:
        return

    options = {f"{r['id']} — {r['title']}": r["id"] for r in results}
    selected_label = st.selectbox(
        "Elige la serie exacta (verifica que el título sea el país correcto)",
        list(options.keys()),
        key="rates_selected_series",
    )
    series_id = options[selected_label]
    col1, col2 = st.columns(2)
    with col1:
        rates_start = st.date_input("Fecha inicial", value=pd.Timestamp("2015-01-01"), key="rates_start_free")
    with col2:
        rates_end = st.date_input("Fecha final", value=pd.Timestamp.today(), key="rates_end_free")
    try:
        series = _fred_series(fred_api_key, series_id, rates_start, rates_end)
    except Exception as exc:
        st.error(f"Error al descargar la serie: {exc}")
        return
    if series.empty:
        st.warning("No se encontraron observaciones válidas para ese rango de fechas.")
        return
    st.line_chart(series, height=250)
    st.metric("Última tasa disponible", f"{series.iloc[-1]:.2f}%", help=f"Fecha: {series.index[-1].date()}")


def render_portfolio_forecast() -> None:
    """
    Pronóstico individual por activo para una canasta con montos invertidos en
    USD (ampliación de RF-13 a RF-18): cada activo se pronostica por separado
    con su propio historial — no es un portafolio combinado, no hay pesos
    conjuntos, covarianzas ni frontera eficiente, solo una lista de
    pronósticos independientes, uno por activo. Para cada activo se muestran
    ambos modelos (caminata aleatoria y lognormal con deriva), el VaR del
    monto invertido, la validación histórica walk-forward del modelo para ese
    activo, y la señal de entrada/salida con costos (reutilizando las mismas
    fórmulas de las pestañas de Pronóstico y Riesgo de arriba).
    """
    st.caption(
        "Cada activo se pronostica por separado con su propio historial — no es "
        "un portafolio combinado (no hay correlaciones conjuntas ni frontera "
        "eficiente). Para cada uno se muestran los dos modelos, el VaR del "
        "monto invertido, qué tan confiable ha sido el modelo históricamente "
        "con ese activo (walk-forward), y si hay una señal de entrada sustentada."
    )

    default_text = "AAPL, 10\nGOOGL, 50\nGXTESCOL, 40"
    basket_text = st.text_area(
        "Un activo por línea: TICKER, monto en USD invertido",
        value=default_text,
        key="portfolio_forecast_text",
        height=100,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        pf_start = st.date_input("Fecha inicial", value=pd.Timestamp("2023-01-01"), key="pf_start")
    with col2:
        pf_end = st.date_input("Fecha final", value=pd.Timestamp.today(), key="pf_end")
    with col3:
        pf_frequency = st.selectbox("Frecuencia", list(FREQUENCY_RULES.keys()), key="pf_frequency")

    pf_horizon = st.number_input(
        f"Plazo H (en periodos de frecuencia '{pf_frequency}')",
        min_value=1, value=10, step=1, key="pf_horizon",
    )

    col_conf, col_cb, col_cs, col_brmin = st.columns(4)
    with col_conf:
        pf_confidence_label = st.selectbox("Nivel de confianza del VaR", ["95%", "99%"], key="pf_confidence")
        pf_confidence = 0.95 if pf_confidence_label == "95%" else 0.99
    with col_cb:
        pf_c_b = st.number_input(
            "Costo de compra c_b", min_value=0.0, value=DEFAULT_CB, step=0.001,
            format="%.4f", key="pf_cb",
        )
    with col_cs:
        pf_c_s = st.number_input(
            "Costo de venta c_s", min_value=0.0, value=DEFAULT_CS, step=0.001,
            format="%.4f", key="pf_cs",
        )
    with col_brmin:
        pf_br_min = st.number_input(
            "BR_min (beneficio/riesgo neto mínimo)", min_value=0.0, value=DEFAULT_BR_MIN,
            step=0.1, key="pf_br_min",
        )

    c_help1, c_help2 = st.columns(2)
    c_help1.caption("¿Qué significa cada opción?", help=AYUDA["canasta_parametros"])
    c_help2.caption("¿Cómo leo los resultados?", help=AYUDA["canasta_resultados"])

    if st.button("Pronosticar canasta"):
        entries = []
        for line in basket_text.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split(",")]
            if len(parts) != 2:
                st.warning(f"Línea ignorada (formato esperado 'TICKER, monto'): '{line}'")
                continue
            ticker_raw, amount_raw = parts
            try:
                amount = float(amount_raw)
            except ValueError:
                st.warning(f"Monto inválido en la línea '{line}', se ignora.")
                continue
            if amount <= 0:
                st.warning(f"El monto debe ser positivo en la línea '{line}', se ignora.")
                continue
            entries.append((ticker_raw.upper(), amount))

        if not entries:
            st.error("No hay activos válidos para pronosticar.")
            return

        horizon = int(pf_horizon)
        periods_per_year = FREQUENCY_PERIODS_PER_YEAR[pf_frequency]
        risk_params = RiskParameters(
            p_l=DEFAULT_PL, p_u=DEFAULT_PU, br_min=pf_br_min, c_b=pf_c_b, c_s=pf_c_s,
        )

        board_rows = []  # tablero de señales: una fila por activo y modelo
        with st.spinner(f"Descargando y pronosticando {len(entries)} activo(s)..."):
            for entry_idx, (ticker, amount) in enumerate(entries):
                asset = fetch_asset_data(ticker, pf_start, pf_end)
                if not asset.ok or asset.prices is None:
                    st.error(f"**{ticker}**: {asset.error or 'sin datos'}")
                    continue
                asset.prices = resample_prices(asset.prices, pf_frequency)
                if asset.prices.empty:
                    st.error(f"**{ticker}**: sin observaciones tras remuestrear.")
                    continue

                prices = asset.prices["adjusted_close"]
                returns = log_returns(prices)
                if len(returns) < 2:
                    st.error(f"**{ticker}**: muestra insuficiente para calcular rendimientos.")
                    continue

                p0 = float(prices.iloc[-1])
                last_date = prices.index[-1]
                h_max = max_valid_horizon(len(returns), periods_per_year)
                currency_note = (
                    f" (precio cotizado en {asset.currency})"
                    if asset.currency and asset.currency.upper() != "USD"
                    else ""
                )

                st.markdown(f"### {ticker} — ${amount:,.2f} invertidos{currency_note}")
                st.caption(f"Precio actual (último dato: {last_date.date()}): {p0:,.4f}")

                for model_label, fit_fn in FORECAST_MODELS.items():
                    model = fit_fn(returns)
                    dist = terminal_distribution(model, p0, horizon)

                    value_median = amount * (dist.median_price / p0)
                    value_mean = amount * (dist.mean_price / p0)
                    value_q05 = amount * (dist.q05_price / p0)
                    value_q95 = amount * (dist.q95_price / p0)

                    var_result = compute_var(model, p0, horizon, pf_confidence, amount)
                    es_fraction = expected_shortfall_fraction(model, horizon, pf_confidence)
                    wf = walk_forward_validate(returns, fit_fn, model_label, horizon, periods_per_year)
                    signal = evaluate_signal(model, p0, horizon, risk_params)
                    probs = terminal_probabilities(model, p0, horizon, signal.p_be)

                    suficiencia_nota = (
                        ""
                        if h_max >= horizon
                        else (
                            f" Este plazo (H={horizon}) supera el límite de suficiencia "
                            f"walk-forward de la sección 5.5 para este activo (H_max={h_max} "
                            "con los datos actuales) — el pronóstico puntual igual se calcula."
                        )
                    )

                    if wf.ok:
                        wf_texto = (
                            f"con los últimos {wf.n_origins} orígenes de prueba: error "
                            f"promedio (RMSE) {wf.rmse:.6f}, cobertura real del intervalo "
                            f"90% = {wf.coverage_90:.1%}"
                            + (
                                f", acierto de dirección = {wf.directional_accuracy:.1%}"
                                if wf.directional_accuracy is not None
                                else ", acierto de dirección no definido (modelo sin deriva)"
                            )
                        )
                    else:
                        wf_texto = f"validación insuficiente — {wf.reason}"

                    if signal.ok:
                        signal_texto = (
                            f"✅ Señal sustentada — entrada: {signal.entry:.4f}, "
                            f"stop-loss: {signal.sl_h:.4f}, take-profit: {signal.tp_h:.4f}, "
                            f"BR_neto: {signal.br_neto:.2f}"
                        )
                    else:
                        signal_texto = "❌ No hay señal sustentada: " + "; ".join(signal.reasons)
                    board_rows.append({
                        "activo": ticker, "modelo": model_label, "último dato": str(last_date.date()), "P0": p0,
                        "entrada": signal.entry, "stop-loss": signal.sl_h, "take-profit": signal.tp_h,
                        "equilibrio (P_BE)": signal.p_be, "BR_neto": signal.br_neto,
                        f"VaR {pf_confidence_label}": var_result.var_fraction, f"ES {pf_confidence_label}": es_fraction,
                        "señal": "sustentada" if signal.ok else "no hay señal",
                        "motivo": "" if signal.ok else "; ".join(signal.reasons),
                    })

                    with st.expander(f"Modelo: {model_label}{suficiencia_nota}"):
                        st.markdown(
                            f"- Valor esperado (mediana): ${value_median:,.2f} · "
                            f"(media): ${value_mean:,.2f}\n"
                            f"- Rango 90% de confianza: entre ${value_q05:,.2f} y ${value_q95:,.2f}\n"
                            f"- Probabilidad de terminar por encima de lo invertido: "
                            f"{dist.prob_above_entry:.1%}\n"
                            f"- VaR ({pf_confidence_label}): pérdida máxima esperada de "
                            f"${var_result.var_dollar:,.2f} ({var_result.var_fraction:.1%} "
                            "del monto invertido)\n"
                            f"- Pérdida esperada (ES, {pf_confidence_label}): ${es_fraction * amount:,.2f} "
                            f"({es_fraction:.1%}), pérdida promedio cuando se supera el VaR\n"
                            f"- Validación histórica (walk-forward): {wf_texto}\n"
                            f"- {signal_texto}\n"
                            f"- Probabilidad de ganar/perder frente al punto de equilibrio "
                            f"(con costos c_b={pf_c_b}, c_s={pf_c_s}): "
                            f"{probs.prob_win:.1%} ganar / {probs.prob_lose:.1%} perder"
                        )
                        steps = forecast_path(model, p0, horizon)
                        fig = forecast_chart(prices, steps, ticker, pf_frequency)
                        st.plotly_chart(
                            fig, use_container_width=True,
                            key=f"pf_chart_{entry_idx}_{model_label}",
                        )

                st.divider()

        if board_rows:
            st.markdown("### Tablero de señales de la canasta")
            board = pd.DataFrame(board_rows)
            st.dataframe(board.style.format(
                {c: "{:,.4f}" for c in ["P0", "entrada", "stop-loss", "take-profit", "equilibrio (P_BE)"]}
                | {"BR_neto": "{:.2f}", f"VaR {pf_confidence_label}": "{:.2%}", f"ES {pf_confidence_label}": "{:.2%}"},
                na_rep="—"), hide_index=True)
            st.caption(
                f"Construcción: para cada activo y modelo, entrada E = P0 (último cierre); stop-loss y take-profit son los "
                f"cuantiles p_L = {DEFAULT_PL:.0%} y p_U = {DEFAULT_PU:.0%} del precio a H = {horizon} periodos; P_BE incluye "
                f"los costos c_b = {pf_c_b} y c_s = {pf_c_s}. Hay señal solo si SL < E < TP, el beneficio y el riesgo netos "
                f"son positivos y BR_neto ≥ {pf_br_min}. Límites: modelos homocedásticos con datos históricos; posición "
                "larga únicamente; el bot **no ejecuta órdenes** ni recomienda operar."
            )
            st.download_button("Descargar tablero (CSV)", board.to_csv(index=False).encode("utf-8"),
                               file_name="tablero_senales.csv", mime="text/csv", key="pf_board_csv")

NEWS_CACHE_TTL_SECONDS = 1800  # 30 min: evita repetir llamadas externas en cada interacción
# Alpha Vantage gratuito permite ~25 consultas/día: su caché dura más.
ALPHA_VANTAGE_CACHE_TTL_SECONDS = 3 * 3600
NEWS_PANEL_ITEMS = 15  # todas las que se muestran en la pantalla principal
GENERAL_NEWS_QUERY = "economía mercados financieros bolsa de valores"
GENERAL_NEWS_TOPIC = "economy_macro"  # un solo tema: varios a la vez se combinan como "Y"
# Pestaña «Mercados» de Inicio: misma conexión de Google News, otra búsqueda. No usa Alpha Vantage
# para no gastar su cupo diario gratuito.
MARKETS_NEWS_QUERY = "bolsa de valores acciones Wall Street mercados"


def _format_news_date(raw) -> str:
    """Normaliza las fechas de las tres fuentes a 'AAAA-MM-DD HH:MM'; si no se puede, deja el texto original."""
    if not raw:
        return "fecha N/D"
    try:
        return pd.to_datetime(raw).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(raw)


@st.cache_data(ttl=NEWS_CACHE_TTL_SECONDS, show_spinner=False)
def get_google_news_rss(query: str, max_items: int = 5) -> "list[dict]":
    """
    Noticias de Google News (RSS en español, edición Colombia), en el orden
    de relevancia de Google y limitadas a la última semana. Devuelve [] si falla.
    """
    try:
        url = (
            f"https://news.google.com/rss/search?q={requests.utils.quote(query + ' when:7d')}"
            "&hl=es-419&gl=CO&ceid=CO:es"
        )
        feed = feedparser.parse(url)
        items = []
        for entry in feed.entries[:max_items]:
            publisher = entry.get("source", {}).get("title", "Google News")
            title = entry.title
            # Google agrega " - <medio>" al final del título; el medio ya se muestra aparte.
            suffix = f" - {publisher}"
            if title.endswith(suffix):
                title = title[: -len(suffix)]
            items.append(
                {"title": title, "link": entry.link, "publisher": publisher, "published": entry.published}
            )
        return items
    except Exception:
        return []


# Temas de Alpha Vantage (campo "topics" de cada noticia) en español, para la etiqueta de la tarjeta.
AV_TOPIC_LABELS = {
    "economy_macro": "Economía", "economy_monetary": "Política monetaria", "economy_fiscal": "Política fiscal",
    "financial_markets": "Mercados", "finance": "Finanzas", "earnings": "Resultados", "ipo": "Salidas a bolsa",
    "mergers_and_acquisitions": "Fusiones", "technology": "Tecnología", "energy_transportation": "Energía",
    "manufacturing": "Industria", "real_estate": "Finca raíz", "retail_wholesale": "Comercio",
    "life_sciences": "Salud", "blockchain": "Blockchain",
}


def _av_topic_label(topics) -> str:
    """Tema más relevante de la noticia según Alpha Vantage; '' si no trae."""
    try:
        best = max(topics or [], key=lambda t: float(t.get("relevance_score", 0)))
        return AV_TOPIC_LABELS.get(best.get("topic", ""), "")
    except (ValueError, TypeError, AttributeError):
        return ""


@st.cache_data(ttl=ALPHA_VANTAGE_CACHE_TTL_SECONDS, show_spinner=False)
def _fetch_alpha_vantage(tickers: "str | None", topics: "str | None", max_items: int) -> dict:
    """
    Consulta NEWS_SENTIMENT ordenado por relevancia. Devuelve
    {"items": [...], "status": motivo}; nunca lanza excepción.
    """
    try:
        api_key = st.secrets.get("ALPHA_VANTAGE_API_KEY")
    except Exception:  # sin secrets.toml, st.secrets lanza en vez de devolver None
        api_key = None
    if not api_key:
        return {"items": [], "status": "sin API key (ALPHA_VANTAGE_API_KEY)"}
    params = {"function": "NEWS_SENTIMENT", "apikey": api_key, "limit": max_items, "sort": "RELEVANCE"}
    if tickers:
        params["tickers"] = tickers
    elif topics:
        params["topics"] = topics
    try:
        data = requests.get("https://www.alphavantage.co/query", params=params, timeout=10).json()
    except Exception:
        return {"items": [], "status": "error de conexión"}
    if "Note" in data or "Information" in data:
        return {"items": [], "status": "límite de consultas alcanzado"}
    if "feed" not in data:
        return {"items": [], "status": "respuesta inesperada"}
    items = [
        {
            "title": item["title"],
            "link": item["url"],
            "publisher": item["source"],
            "published": item["time_published"],
            # Campos que ya trae la misma respuesta; solo se muestran en la tarjeta de Inicio.
            "summary": item.get("summary") or "",
            "image": item.get("banner_image") or "",
            "category": _av_topic_label(item.get("topics")),
        }
        for item in data["feed"][:max_items]
    ]
    return {"items": items, "status": "ok" if items else "sin resultados"}


def get_alpha_vantage_news(
    tickers: "str | None", topics: "str | None", max_items: int = 5
) -> "list[dict]":
    """
    Noticias de Alpha Vantage. Sin API key, con límite excedido
    ('Note'/'Information') o ante cualquier fallo devuelve [] en silencio:
    la fuente simplemente se omite.
    """
    return _fetch_alpha_vantage(tickers, topics, max_items)["items"]


@st.cache_data(ttl=NEWS_CACHE_TTL_SECONDS, show_spinner=False)
def _get_yfinance_news(ticker: str, max_items: int = 3) -> "list[dict]":
    """Noticias de Yahoo Finance vía yfinance (clave 'content'). Devuelve [] si falla."""
    try:
        items = []
        for raw in (yf.Ticker(ticker).news or [])[:max_items]:
            content = raw.get("content") or {}
            title = content.get("title")
            link = (content.get("canonicalUrl") or {}).get("url")
            if not title or not link:
                continue
            thumb = content.get("thumbnail") or {}
            resolutions = thumb.get("resolutions") or []
            items.append(
                {
                    "title": title,
                    "link": link,
                    "publisher": (content.get("provider") or {}).get("displayName", "Yahoo Finance"),
                    "published": content.get("pubDate"),
                    # Campos que ya trae la misma respuesta; solo se muestran en la tarjeta de Inicio.
                    "summary": content.get("summary") or "",
                    "image": thumb.get("originalUrl") or (resolutions[0].get("url") if resolutions else "") or "",
                }
            )
        return items
    except Exception:
        return []


MILESTONE_TOP_MOVES = 3  # mayores subidas y caídas de un día que se listan


def _collect_news(ticker: "str | None", markets: bool = False) -> "list[tuple[str, list[dict]]]":
    """
    Noticias por fuente: del activo si se pasa un ticker, o generales de
    economía y mercados si no. Se pide siempre la cantidad del panel y el
    sidebar muestra solo las primeras, así ambas vistas comparten la misma
    consulta en caché (y no gastan cupo extra de Alpha Vantage).
    """
    if markets:
        return [("Google News", get_google_news_rss(MARKETS_NEWS_QUERY, max_items=NEWS_PANEL_ITEMS))]
    if ticker:
        return [
            ("Yahoo Finance", _get_yfinance_news(ticker, max_items=NEWS_PANEL_ITEMS)),
            ("Google News", get_google_news_rss(ticker, max_items=NEWS_PANEL_ITEMS)),
            ("Alpha Vantage", get_alpha_vantage_news(tickers=ticker, topics=None, max_items=NEWS_PANEL_ITEMS)),
        ]
    return [
        ("Google News", get_google_news_rss(GENERAL_NEWS_QUERY, max_items=NEWS_PANEL_ITEMS)),
        ("Alpha Vantage", get_alpha_vantage_news(tickers=None, topics=GENERAL_NEWS_TOPIC, max_items=NEWS_PANEL_ITEMS)),
    ]


LINK_CHECK_TTL_SECONDS = 6 * 3600  # un enlace verificado no se vuelve a probar en 6 horas
LINK_CHECK_EXTRA = 3  # se prueban algunos de más por fuente, por si varios están rotos


@st.cache_data(ttl=LINK_CHECK_TTL_SECONDS, show_spinner=False)
def _verified_news(items: "tuple[tuple[str, str, str, str], ...]") -> "tuple[list[dict], list[dict]]":
    """Prueba los enlaces en paralelo (src/news_links.py) y separa los que abren de los que no."""
    keys = ("title", "link", "publisher", "published", "summary", "image", "category")
    news = [dict(zip(keys, item)) for item in items]  # tuplas de 4 (antes) o de 7 campos
    return verify_items(news, max_workers=16)


NEWS_HOME_ITEMS = 6  # noticias por pestaña en Inicio
NEWS_MAX_AGE_DAYS = 7  # solo noticias de la última semana: las viejas suelen tener enlaces que ya no abren


def _is_recent(raw, days: int = NEWS_MAX_AGE_DAYS) -> bool:
    """True si la fecha de la noticia es de los últimos `days` días (o si no trae fecha legible)."""
    try:
        when = pd.to_datetime(raw, utc=True)
    except Exception:
        return True
    if pd.isna(when):
        return True
    return when >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=days)


def _merged_recent_news(ticker: "str | None", limit: int, markets: bool = False) -> "tuple[list[dict], int]":
    """Une las fuentes, quita repetidas y viejas, verifica enlaces y devuelve (noticias, ocultas)."""
    seen, pool = set(), []
    for source, items in _collect_news(ticker, markets):
        for item in items:
            key = str(item.get("title", "")).strip().lower()
            if key and key not in seen and _is_recent(item.get("published")):
                seen.add(key)
                pool.append({**item, "source": source})
    candidates = tuple((str(i.get("title", "")), str(i.get("link", "")), str(i.get("publisher", "")),
                        str(i.get("published", "")), str(i.get("summary", "") or ""), str(i.get("image", "") or ""),
                        str(i.get("category", "") or "")) for i in pool[: limit + LINK_CHECK_EXTRA * 2])
    kept, hidden = _verified_news(candidates) if candidates else ([], [])
    return kept[:limit], len(hidden)


def _show_news(items: "list[dict]", hidden: int, empty_text: str) -> None:
    if not items:
        st.info(empty_text)
        return
    for item in items:
        title = str(item.get("title", "")).replace("[", "(").replace("]", ")")
        st.markdown(f"- [{title}]({item.get('link', '')})  \n  <span style='color:#8B93A7'>"
                    f"{item.get('publisher', 'N/D')} · {_format_news_date(item.get('published'))}</span>",
                    unsafe_allow_html=True)
    if hidden:
        st.caption(f"Se ocultaron {hidden} noticia(s) cuyo enlace no abría.")


def _show_news_carousel(items: "list[dict]", hidden: int, empty_text: str, label: str) -> None:
    """Las mismas noticias de `_show_news`, en un recuadro grande que pasa solo (ver src/ui_fx.py)."""
    if not items:
        st.markdown(empty_state_html("news", "Sin noticias por ahora", html_escape(empty_text) +
                                     " Las fuentes se vuelven a consultar en unos minutos."), unsafe_allow_html=True)
        return
    st.markdown(news_carousel_html(items, label, _format_news_date), unsafe_allow_html=True)
    if hidden:
        st.caption(f"Se ocultaron {hidden} noticia(s) cuyo enlace no abría.")


def render_news_home() -> None:
    """Noticias de la semana en Inicio: economía en general y la empresa que se esté mirando."""
    st.markdown('<div class="dpst-newshead"><div class="dpst-eyebrow">' + icon("news", 15) +
                '<span>DPST FINANCIAL NEWS</span></div><div class="nh-title">Mercado en movimiento</div></div>',
                unsafe_allow_html=True)
    st.markdown("#### Noticias de la semana", help=(
        "Noticias de los últimos 7 días, tomadas de Google News, Yahoo Finance y Alpha Vantage.\n\n"
        "- Solo aparecen las que tienen un enlace que **sí abre**.\n"
        "- Son para informarse: el bot **no** las usa para hacer cálculos."))
    try:
        result = st.session_state.get("asset_result")
        ticker = result.ticker if result is not None and result.ok else None
        tab_general, tab_markets, tab_asset = st.tabs(
            ["Economía", "Mercados", f"Empresa: {ticker}" if ticker else "Empresa"])
        with tab_general:
            with st.spinner("Buscando noticias..."):
                items, hidden = _merged_recent_news(None, NEWS_HOME_ITEMS)
            _show_news_carousel(items, hidden, "No se encontraron noticias económicas en este momento.", "Economía")
        with tab_markets:
            with st.spinner("Buscando noticias de mercados..."):
                items, hidden = _merged_recent_news(None, NEWS_HOME_ITEMS, markets=True)
            _show_news_carousel(items, hidden, "No se encontraron noticias de mercados en este momento.", "Mercados")
        with tab_asset:
            if not ticker:
                st.markdown(empty_state_html(
                    "tag", "Elige una empresa",
                    "Escoge una empresa en <b>Preselección de activos</b> y aquí verás sus noticias."),
                    unsafe_allow_html=True)
            else:
                with st.spinner(f"Buscando noticias de {ticker}..."):
                    items, hidden = _merged_recent_news(ticker, NEWS_HOME_ITEMS)
                _show_news_carousel(items, hidden, f"No se encontraron noticias recientes de {ticker}.", ticker)
    except Exception:
        st.info("No se pudieron cargar las noticias en este momento.")


# dismissible=False: sin X ni Esc. Si se pudiera cerrar así, la app quedaría
# en blanco (todo lo demás está detenido con st.stop hasta que se responda).
@st.dialog("Antes de entrar", dismissible=False)
def render_intro_alert():
    st.markdown(
        f'<div class="dpst-intro-brand">{_logo_svg(40, "logoGradIntro")}'
        f'<div><div class="b">{BRAND_NAME}</div><div class="s">{INSTITUTION}</div></div></div>',
        unsafe_allow_html=True,
    )
    st.write(
        "Esta app está hecha para mirar comportamientos históricos y "
        "de pronóstico de activos individuales con fines académicos. "
        "**No se hace responsable por el mal uso que se le dé.**"
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Continuar", type="primary", use_container_width=True):
            st.session_state["intro_ack"] = True
            st.rerun()
    with col2:
        if st.button("Cancelar", use_container_width=True):
            st.session_state["intro_cancelled"] = True
            st.rerun()


def main() -> None:
    # Estilos primero, para que la ventana de bienvenida y el disclaimer ya salgan con el diseño.
    render_header()
    render_sidebar_style()
    apply_ui_fx(_command_items())

    if st.session_state.get("intro_cancelled", False):
        st.info("Saliste de la aplicación. Puedes cerrar esta pestaña.")
        st.stop()

    if not st.session_state.get("intro_ack", False):
        render_intro_alert()
        st.stop()

    if DEV_MODE:
        st.sidebar.warning("MODO DESARROLLO: login OIDC desactivado temporalmente.")
        user_name = st.sidebar.text_input("Nombre (simulado)", value="Estudiante Demo")
        user_email = st.sidebar.text_input("Correo (simulado)", value="demo@eia.edu.co")
    else:
        if not is_auth_configured():
            st.error(
                "Autenticación OIDC no configurada todavía.\n\n"
                "1. Copien `.streamlit/secrets.toml.example` a `.streamlit/secrets.toml`.\n"
                "2. Completen las credenciales de Google/Microsoft que entregue el curso "
                "por el LMS.\n\n"
                "La app se detiene aquí a propósito: no debe quedar disponible sin login real."
            )
            st.stop()

        user = require_login()  # detiene la ejecución si no hay sesión activa
        user_name, user_email = getattr(user, "name", "?"), getattr(user, "email", "?")

    render_disclaimer_gate(user_name, user_email)

    # Menú superior. Se usan pestañas (y no páginas de st.navigation) para que
    # los datos escritos en una sección no se borren al pasar a otra.
    with st.container(key="dpst_nav"):
        tab_home, tab_tickers, tab_pre, tab_rates, tab_lab = st.tabs(
            ["Inicio", "Tickers", "Preselección de activos", "Tasas soberanas", LAB_TITLE]
        )
        with tab_home:
            render_home(user_name, user_email)
        with tab_tickers:
            render_tickers_page()
        with tab_pre:
            render_preselection_page()
        with tab_rates:
            _page_title("Tasas de bonos soberanos",
                        "Referencia macroeconómica por país (FRED). No entra en la preselección ni en el laboratorio.")
            render_sovereign_rates()
        with tab_lab:
            _page_title(LAB_TITLE,
                        "Carteras simuladas con los modelos del avance 2.")
            render_portfolio_lab()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _ticker_directory() -> "tuple[pd.DataFrame, bool]":
    """(directorio, True si es el completo de NASDAQ Trader; False si es la lista de respaldo)."""
    try:
        return fetch_us_tickers(), True
    except Exception:
        return fallback_tickers(), False


def _use_ticker(ticker: str) -> None:
    st.session_state["asset_ticker"] = ticker
    st.session_state["ticker_chosen_msg"] = ticker


TICKER_TABLE_ROWS = 300  # filas que se muestran (igual que antes)
_TYPE_STYLE = {"Acción": ("stock", "chart"), "Fondo (ETF)": ("etf", "layers")}


def _ticker_avatar(ticker: str) -> str:
    """Ícono genérico con la inicial del ticker (no es el logo de la empresa: no se inventan identidades)."""
    hue = sum(ord(c) for c in ticker) % 3  # tres tonos de la paleta, siempre el mismo para el mismo ticker
    return f'<span class="tk-av h{hue}" aria-hidden="true">{html_escape(ticker[:1] or "?")}</span>'


def _tickers_table_html(rows: pd.DataFrame, selected: "str | None") -> str:
    """Tabla del screener: mismas columnas y datos de la búsqueda (ticker, empresa, bolsa, tipo)."""
    body = []
    for i, (t, e, b, k) in enumerate(zip(rows["ticker"], rows["empresa"], rows["bolsa"], rows["tipo"])):
        cls, ic = _TYPE_STYLE.get(k, ("other", "tag"))
        on = ' class="on" aria-selected="true"' if t == selected else ""
        delay = f' style="animation-delay:{min(i, 24) * 0.018:.3f}s"'
        body.append(
            f'<tr{on}{delay} data-t="{html_escape(t)}"><td class="n">{i + 1}</td>'
            f'<td class="tk">{_ticker_avatar(t)}<b>{html_escape(t)}</b></td>'
            f'<td class="em">{html_escape(e)}</td>'
            f'<td><span class="tk-ex">{html_escape(b)}</span></td>'
            f'<td><span class="tk-type {cls}">{icon(ic, 13)}{html_escape(k)}</span></td></tr>'
        )
    head = ('<thead><tr><th class="n">#</th><th data-sort="1">Ticker</th><th data-sort="2">Empresa</th>'
            '<th data-sort="3">Bolsa</th><th data-sort="4">Tipo</th></tr></thead>')
    return f'<div class="tk-table" role="region" aria-label="Resultados de la búsqueda"><table>{head}<tbody>{"".join(body)}</tbody></table></div>'


def _tickers_options_html(found: pd.DataFrame, complete: bool, n_directory: int) -> str:
    """Panel desplegable de opciones: fuente del directorio, tipos y bolsas de los resultados actuales."""
    source = (f"{n_directory:,} empresas y fondos · directorio público de NASDAQ Trader (diario)" if complete
              else "Lista corta de empresas conocidas (no se pudo cargar el directorio completo)")
    by_ex = found["bolsa"].value_counts() if not found.empty else pd.Series(dtype=int)
    by_type = found["tipo"].value_counts() if not found.empty else pd.Series(dtype=int)
    ex_rows = "".join(f'<li><span class="tk-ex">{html_escape(str(ex))}</span><b>{int(c):,}</b></li>' for ex, c in by_ex.items())
    ty_rows = "".join(
        f'<li><span class="tk-type {_TYPE_STYLE.get(str(k), ("other", "tag"))[0]}">'
        f'{icon(_TYPE_STYLE.get(str(k), ("other", "tag"))[1], 13)}{html_escape(str(k))}</span><b>{int(c):,}</b></li>'
        for k, c in by_type.items())
    return (
        '<details class="tk-opts"><summary>' + icon("sliders", 15) + '<span>Opciones</span></summary>'
        '<div class="tk-opts-panel">'
        f'<div class="og"><div class="ot">Fuente del directorio</div><div class="ob">{html_escape(source)}</div></div>'
        f'<div class="og"><div class="ot">Tipo de activo en los resultados</div><ul>{ty_rows or "<li>—</li>"}</ul></div>'
        f'<div class="og"><div class="ot">Bolsa en los resultados</div><ul>{ex_rows or "<li>—</li>"}</ul></div>'
        '</div></details>'
    )


def render_tickers_page() -> None:
    st.markdown(page_header_html("Screener de empresas", "Tickers",
                                 "Busca el código de cualquier empresa para usarlo en el bot.", "tag"),
                unsafe_allow_html=True)
    st.markdown("**¿Qué es un ticker?**", help=(
        "Es el **nombre corto** con el que una empresa aparece en la bolsa de valores.\n\n"
        "- Apple → **AAPL**\n- Coca-Cola → **KO**\n- Ecopetrol (en Nueva York) → **EC**\n\n"
        "El bot necesita ese código para buscar los precios de la empresa."))
    with st.spinner("Cargando el directorio de empresas..."):
        directory, complete = _ticker_directory()

    left, main = st.columns([1, 2.6], gap="medium")
    with left:
        with st.container(key="tk_left"):
            st.markdown(section_label_html("Buscar", "search"), unsafe_allow_html=True)
            text = st.text_input("Escribe el nombre de la empresa o su ticker", placeholder="Ej: coca cola, apple, tesla",
                                 key="ticker_search")
            st.markdown(section_label_html("Filtros", "sliders"), unsafe_allow_html=True)
            kind = st.selectbox("Tipo", ["Todos", "Acción", "Fondo (ETF)"], key="ticker_kind", help=(
                "- **Acción:** una parte de una empresa.\n- **Fondo (ETF):** una canasta de muchas acciones que se "
                "compra como si fuera una sola."))
            found = search_tickers(directory, text, kind)
            chips = []
            if (text or "").strip():
                chips.append(f'{icon("search", 12)}«{html_escape(text.strip())}»')
            if kind != "Todos":
                chips.append(f'{icon("sliders", 12)}{html_escape(kind)}')
            st.markdown(
                f'<div class="tk-count"><span class="v">{len(found):,}</span><span class="l">resultado(s)</span>'
                + (f'<div class="tk-chips"><span class="lab">Filtros activos</span>'
                   + "".join(f'<span class="chip">{c}</span>' for c in chips) + "</div>" if chips
                   else '<div class="tk-chips"><span class="lab">Sin filtros: todo el directorio</span></div>')
                + "</div>", unsafe_allow_html=True)
            if complete:
                st.caption(f"{len(directory):,} empresas y fondos de las bolsas de Estados Unidos (directorio público de "
                           "NASDAQ Trader, se actualiza cada día).")
            else:
                st.warning("No se pudo cargar el directorio completo en este momento; se muestra una lista corta de "
                           "empresas conocidas.")
            options = found.head(TICKER_TABLE_ROWS)
            ticker = None
            if not found.empty:
                st.markdown(section_label_html("Seleccionar", "check"), unsafe_allow_html=True)
                labels = [f"{t} — {e}" for t, e in zip(options["ticker"], options["empresa"])]
                pick = st.selectbox("Escoge una empresa", labels, key="ticker_pick")
                ticker = options["ticker"].iloc[labels.index(pick)]
                st.button(f"Usar {ticker} en Preselección de activos", type="primary", on_click=_use_ticker,
                          args=(ticker,), key="ticker_use", use_container_width=True)
            chosen = st.session_state.pop("ticker_chosen_msg", None)
            if chosen:
                st.success(f"Listo: **{chosen}** quedó escrito en **Preselección de activos** → Datos del activo. Ve a "
                           "esa pestaña y pulsa «Descargar y limpiar».")
    with main:
        with st.container(key="tk_main"):
            more = f" · se muestran los primeros {TICKER_TABLE_ROWS}" if len(found) > TICKER_TABLE_ROWS else ""
            st.markdown(
                f'<div class="tk-bar"><div><span class="v">{len(found):,}</span> resultado(s){more}</div>'
                f'{_tickers_options_html(found, complete, len(directory))}</div>', unsafe_allow_html=True)
            if found.empty:
                st.markdown(empty_state_html("search", "No hay empresas con esa búsqueda",
                                             "Prueba con otra palabra, con el ticker (por ejemplo <b>AAPL</b>) o cambia "
                                             "el filtro de <b>Tipo</b> a «Todos»."), unsafe_allow_html=True)
            else:
                st.markdown(_tickers_table_html(options, ticker), unsafe_allow_html=True)
                if ticker:
                    row = options[options["ticker"] == ticker].iloc[0]
                    cls, ic = _TYPE_STYLE.get(row["tipo"], ("other", "tag"))
                    st.markdown(
                        f'<div class="tk-sel">{_ticker_avatar(ticker)}<div class="sx"><div class="st">Empresa seleccionada'
                        f'</div><div class="sn"><b>{html_escape(ticker)}</b> {html_escape(row["empresa"])}</div></div>'
                        f'<span class="tk-ex">{html_escape(row["bolsa"])}</span>'
                        f'<span class="tk-type {cls}">{icon(ic, 13)}{html_escape(row["tipo"])}</span></div>',
                        unsafe_allow_html=True)
                with st.expander("Ver como tabla de datos (ordenar, buscar dentro y descargar)", icon=":material/table:"):
                    st.dataframe(options, hide_index=True, height=320,
                                 column_config={"ticker": "Ticker", "empresa": "Empresa", "bolsa": "Bolsa", "tipo": "Tipo"})


def _command_items() -> "list[dict]":
    """Entradas del buscador Ctrl/⌘ + K: secciones del menú superior y módulos del laboratorio."""
    sections = [
        ("Inicio", "Guía de uso, noticias de la semana"),
        ("Tickers", "Buscar el código de una empresa"),
        ("Preselección de activos", "Un activo, pronóstico y comparación"),
        ("Tasas soberanas", "Bonos del gobierno por país (FRED)"),
        (LAB_TITLE, "Carteras simuladas del avance 2"),
    ]
    items = [{"group": "Secciones", "label": name, "top": name, "hint": hint} for name, hint in sections]
    items += [{"group": LAB_TITLE, "label": module, "top": LAB_TITLE, "sub": module, "hint": "Módulo"}
              for module in LAB_MODULES]
    return items


def _page_title(title: str, subtitle: str) -> None:
    st.markdown(
        f'<div class="dpst-page-title">{title}</div><div class="dpst-page-sub">{subtitle}</div>',
        unsafe_allow_html=True,
    )


HOME_STEPS = [
    ("1", "Busca la empresa", "En **Tickers** escribe el nombre de la empresa (por ejemplo, Coca-Cola) y copia su código."),
    ("2", "Mírala por dentro", "En **Preselección de activos** pon el código, pulsa «Descargar y limpiar» y abre "
     "«Análisis histórico» para ver cómo le ha ido."),
    ("3", "Mira qué podría pasar", "En **Pronóstico** el bot muestra un rango de precios posibles y cuánto podrías perder "
     "en un mal escenario."),
    ("4", "Compara varias", "En **Comparación** pones varias empresas y el bot te dice cuáles tienen mejor relación entre "
     "lo que ganan y lo que arriesgan."),
    ("5", "Arma una cartera", "En **Laboratorio de portafolios** el bot reparte el dinero entre varias empresas para "
     "arriesgar menos."),
]

# Cinta de la portada: los modelos que trae el bot (texto informativo, no son cotizaciones).
HERO_TAPE = ["Markowitz", "Frontera eficiente", "Black-Litterman", "CAPM y beta", "VaR",
             "Rebalanceo", "Backtest", "Ledoit-Wolf", "EWMA", "Valoración FCFF"]

# Línea decorativa de la portada (ilustrativa, no son datos de ningún activo).
_HERO_SPARK = (
    "M0,173.5 L15,173.7 L30,182.2 L45,164.3 L60,162.5 L75,161.8 L90,145.7 L105,153.0 L120,153.6 "
    "L135,155.6 L150,130.0 L165,133.5 L180,123.5 L195,143.3 L210,136.4 L225,112.3 L240,139.2 L255,135.5 "
    "L270,122.3 L285,117.9 L300,100.0 L315,92.3 L330,105.5 L345,87.3 L360,88.3 L375,86.7 L390,76.8 "
    "L405,87.4 L420,83.5 L435,93.2 L450,79.6 L465,80.3 L480,72.6 L495,74.6 L510,64.8 L525,55.9 "
    "L540,75.7 L555,72.5 L570,64.3 L585,56.8 L600,41.1"
)


def _hero_spark_svg() -> str:
    return (
        '<svg class="spark" viewBox="0 0 610 200" preserveAspectRatio="none" aria-hidden="true">'
        '<defs><linearGradient id="dpstSparkFill" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#34C9A0" stop-opacity="0.28"/>'
        '<stop offset="100%" stop-color="#34C9A0" stop-opacity="0"/></linearGradient></defs>'
        f'<path class="area" d="{_HERO_SPARK} L600,200 L0,200 Z" fill="url(#dpstSparkFill)"/>'
        f'<path class="line" d="{_HERO_SPARK}" fill="none" stroke="#34C9A0" stroke-width="2.2" '
        'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        '<circle class="halo" cx="600" cy="41.1" r="9" fill="#34C9A0" fill-opacity="0.25"/>'
        '<circle class="dot" cx="600" cy="41.1" r="4" fill="#BDEFDF"/>'
        "</svg>"
    )


def _md_bold(text: str) -> str:
    """**texto** → <b>texto</b> para las tarjetas en HTML."""
    import re
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


# Accesos rápidos de Inicio: pestaña de destino, ícono y descripción (los módulos no cambian).
HOME_MODULES = [
    ("Tickers", "tag", "Busca el código de cualquier empresa o fondo de las bolsas de EE. UU."),
    ("Preselección de activos", "chart", "Descarga un activo, mira su historia, su pronóstico y compáralo con otros."),
    ("Tasas soberanas", "landmark", "Tasas de los bonos del gobierno por país, desde FRED."),
    (LAB_TITLE, "layers", "Arma carteras simuladas: Markowitz, Black-Litterman, rebalanceo y más."),
]
# Paso de la guía → (pestaña, desplegable que se abre, ícono, texto corto del botón).
HOME_STEP_TARGETS = {
    "1": ("Tickers", None, "search", "Ir a Tickers"),
    "2": ("Preselección de activos", "Datos del activo a probar", "chart", "Ir a Datos del activo"),
    "3": ("Preselección de activos", "Pronóstico", "trending", "Ir a Pronóstico"),
    "4": ("Preselección de activos", "Comparación y preselección de activos", "scale", "Ir a Comparación"),
    "5": (LAB_TITLE, None, "wallet", "Ir al Laboratorio"),
}


def _session_tickers() -> "list[str]":
    """Activos que el usuario ya descargó en esta sesión (Datos del activo y Comparación)."""
    seen = []
    result = st.session_state.get("asset_result")
    if result is not None and getattr(result, "ok", False):
        seen.append(result.ticker)
    comparison = st.session_state.get("comparison_result")
    summaries = (getattr(comparison, "summaries", None) or []) if getattr(comparison, "ok", False) else []
    for summary in summaries:
        if summary.ticker not in seen:
            seen.append(summary.ticker)
    return seen


def _configured_keys() -> "dict[str, bool]":
    """Qué claves de API están configuradas en los secretos (no se muestran sus valores)."""
    out = {}
    for name, key in (("FRED", "FRED_API_KEY"), ("Alpha Vantage", "ALPHA_VANTAGE_API_KEY")):
        try:
            out[name] = bool(st.secrets.get(key))
        except Exception:
            out[name] = False
    return out


def _home_kpis_html() -> str:
    """Indicadores de la portada. Solo información que ya existe en la app o en esta sesión."""
    tickers = _session_tickers()
    keys = _configured_keys()
    log = st.session_state.get("conn_check_log") or []
    if log:
        last_time = str(log[-1].get("hora (UTC)", ""))
        last_batch = [r for r in log if str(r.get("hora (UTC)", ""))[:16] == last_time[:16]] or log[-1:]
        ok = sum(1 for r in last_batch if r.get("estado") == "conectado")
        conn_value = f"{ok} / {len(last_batch)}"
        conn_note = f"servicios conectados · última prueba {last_time[11:16]} UTC"
        conn_tone = "good" if ok == len(last_batch) else "warn"
    else:
        n_keys = sum(keys.values())
        conn_value = f"{n_keys} / {len(keys)}"
        conn_note = "claves de API configuradas · " + " · ".join(
            f"{name} {'✓' if has else '—'}" for name, has in keys.items())
        conn_tone = "good" if n_keys == len(keys) else "warn"
    commit = git_commit()
    short = commit[:7] if commit and commit != "no disponible" else "N/D"
    if tickers:
        assets_note = ", ".join(tickers[:6]) + ("…" if len(tickers) > 6 else "")
    else:
        assets_note = "en esta sesión · descarga uno en Preselección"
    tiles = [
        ("database", "Activos analizados", str(len(tickers)), assets_note, "neutral"),
        ("layers", "Modelos disponibles", str(len(HERO_TAPE)), f"en {len(LAB_MODULES)} módulos del laboratorio", "neutral"),
        ("clock", "Última actualización", LAST_UPDATE, f"versión {VERSION} · commit {short}", "neutral"),
        ("plug", "Estado de conexión", conn_value, conn_note, conn_tone),
    ]
    cells = "".join(
        f'<div class="kpi {tone}" style="animation-delay:{0.06 * i:.2f}s"><div class="k-top">'
        f'<span class="k-ic">{icon(ic, 16)}</span><span class="k-lab">{lab}</span></div>'
        f'<div class="k-val">{html_escape(val)}</div><div class="k-note">{html_escape(note)}</div></div>'
        for i, (ic, lab, val, note, tone) in enumerate(tiles)
    )
    return f'<div class="dpst-kpis">{cells}</div>'


def _hero_chart_html() -> str:
    """
    Panel derecho de la portada. Si el usuario ya descargó un activo, dibuja su precio
    ajustado real (los mismos datos de Preselección). Si no, la línea es ilustrativa y se rotula así.
    """
    result = st.session_state.get("asset_result")
    series = None
    if result is not None and getattr(result, "ok", False) and result.prices is not None and len(result.prices.columns):
        col = "adjusted_close" if "adjusted_close" in result.prices.columns else result.prices.columns[0]
        series = result.prices[col].dropna()
    grid = "".join(f'<line x1="0" x2="610" y1="{y}" y2="{y}"/>' for y in (40, 90, 140, 190))
    if series is not None and len(series) >= 2:
        step = max(1, len(series) // 120)
        pts = series.iloc[::step]
        if pts.index[-1] != series.index[-1]:
            pts = pd.concat([pts, series.iloc[-1:]])
        lo, hi = float(pts.min()), float(pts.max())
        span = (hi - lo) or 1.0
        xs = [600 * i / (len(pts) - 1) for i in range(len(pts))]
        ys = [20 + 170 * (1 - (float(v) - lo) / span) for v in pts]
        path = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in zip(xs, ys))
        ccy = result.currency or ""
        head_title = f"{html_escape(result.ticker)} · precio ajustado"
        badge = f'<span class="c-badge real">{icon("check", 12)}Datos reales · {html_escape(result.source)}</span>'
        foot = (f'<div class="c-foot"><span><b>{float(series.iloc[-1]):,.2f}</b> {html_escape(ccy)} · último dato '
                f'{series.index.max().date()}</span><span>{len(series)} observaciones · '
                f'{series.index.min().date()} → {series.index.max().date()}</span></div>')
        axis = f'<div class="c-y"><span>{hi:,.2f}</span><span>{lo:,.2f}</span></div>'
        end_x, end_y = xs[-1], ys[-1]
    else:
        path = _HERO_SPARK
        head_title = "Vista ilustrativa"
        badge = f'<span class="c-badge demo">{icon("info", 12)}Ilustrativo · no son datos de mercado</span>'
        foot = ('<div class="c-foot"><span>Descarga un activo en <b>Preselección de activos</b> y aquí verás '
                'su precio real.</span></div>')
        axis = ""
        end_x, end_y = 600, 41.1
    return (
        f'<div class="dpst-chart"><div class="c-head"><span class="c-title">{head_title}</span>{badge}</div>'
        f'<div class="c-plot">{axis}<svg class="spark" viewBox="0 0 610 200" preserveAspectRatio="none" aria-hidden="true">'
        '<defs><linearGradient id="dpstSparkFill" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0%" stop-color="#34C9A0" stop-opacity="0.32"/>'
        '<stop offset="100%" stop-color="#34C9A0" stop-opacity="0"/></linearGradient>'
        '<filter id="dpstGlow" x="-5%" y="-20%" width="110%" height="140%"><feGaussianBlur stdDeviation="3" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
        f'<g class="grid">{grid}</g>'
        f'<path class="area" d="{path} L600,200 L0,200 Z" fill="url(#dpstSparkFill)"/>'
        f'<path class="line" d="{path}" fill="none" stroke="#34C9A0" stroke-width="2.2" filter="url(#dpstGlow)" '
        'stroke-linejoin="round" stroke-linecap="round" vector-effect="non-scaling-stroke"/>'
        f'<circle class="halo" cx="{end_x:.1f}" cy="{end_y:.1f}" r="9" fill="#34C9A0" fill-opacity="0.25"/>'
        f'<circle class="dot" cx="{end_x:.1f}" cy="{end_y:.1f}" r="4" fill="#BDEFDF"/>'
        f'</svg></div>{foot}</div>'
    )


def _home_hero_html() -> str:
    tape = "".join(f"<span>{item}</span>" for item in HERO_TAPE * 2)
    return (
        '<div class="dpst-hero dash"><div class="h-grid"><div class="copy">'
        '<span class="dpst-pill">PRESELECCIÓN ACADÉMICA</span>'
        f'<div class="brand">{_logo_svg(72, "logoGradHero")}<h1>{BRAND_NAME}</h1></div>'
        f'<div class="sub">{SYSTEM_NAME}</div>'
        f'<div class="meta">{TEAM_NAME} · {INSTITUTION} · Teoría Moderna de Portafolios · versión {VERSION}</div>'
        f'</div>{_hero_chart_html()}</div>'
        f'<div class="dpst-tape" aria-hidden="true"><div class="track">{tape}</div></div></div>'
    )


def _home_modules_html() -> str:
    cards = "".join(
        f'<button type="button" class="mod" data-dpst-go="{html_escape(tab)}" style="animation-delay:{0.06 * i:.2f}s">'
        f'<span class="m-ic">{icon(ic, 22)}</span><span class="m-name">{html_escape(tab)}</span>'
        f'<span class="m-desc">{html_escape(desc)}</span><span class="m-go">Entrar {icon("arrow", 15)}</span></button>'
        for i, (tab, ic, desc) in enumerate(HOME_MODULES)
    )
    return f'{section_label_html("Accesos rápidos", "bolt")}<div class="dpst-mods">{cards}</div>'


def _home_steps_html() -> str:
    cards = []
    for i, (num, title, desc) in enumerate(HOME_STEPS):
        tab, open_, ic, go_text = HOME_STEP_TARGETS.get(num, ("Inicio", None, "info", "Ir a Inicio"))
        attrs = f' data-dpst-go="{html_escape(tab)}"' + (f' data-dpst-open="{html_escape(open_)}"' if open_ else "")
        cards.append(
            f'<div class="dpst-card step" style="animation-delay:{0.08 * i:.2f}s">'
            f'<div class="s-top"><span class="s-num">{int(num):02d}</span><span class="s-ic">{icon(ic, 20)}</span></div>'
            f'<div class="n">Paso {num}</div><div class="t">{title}</div><div class="d">{_md_bold(desc)}</div>'
            f'<button type="button" class="s-go"{attrs}>{html_escape(go_text)} {icon("arrow", 14)}</button></div>'
        )
    return f'<div class="dpst-steps">{"".join(cards)}</div>'


def render_home(user_name: str, user_email: str) -> None:
    """
    Portada tipo dashboard: encabezado DPST con gráfica (real si ya hay un activo descargado),
    indicadores de la sesión, accesos a los módulos, guía de uso, noticias y pie. Conserva todo
    el contenido de la portada anterior; solo cambia la presentación.
    """
    st.markdown(_home_hero_html(), unsafe_allow_html=True)
    st.markdown(_home_kpis_html(), unsafe_allow_html=True)
    st.markdown(
        '<div class="dpst-notice"><b>Este bot no te dice en qué invertir.</b> '
        "Te ayuda a <b>mirar y comparar</b> empresas con datos del pasado, como ejercicio de una clase de la "
        "universidad. No es una recomendación, no compra ni vende nada y no garantiza ganancias.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(_home_modules_html(), unsafe_allow_html=True)
    st.markdown("#### Cómo usar el bot", help=(
        "Sigue los pasos en orden. Cada vez que veas un **?** junto a un título o una casilla, pon el mouse encima: "
        "aparece una explicación corta."))
    st.markdown(_home_steps_html(), unsafe_allow_html=True)
    st.caption("Las **Tasas soberanas** muestran cuánto paga el gobierno de cada país por prestarle dinero: sirven "
               "de punto de comparación.")
    render_news_home()
    with st.container(key="dpst_home_footer"):
        st.markdown(section_label_html("Información del piloto", "shield"), unsafe_allow_html=True)
        with st.expander("Disclaimer académico completo", icon=":material/gavel:"):
            st.write(DISCLAIMER_TEXT)
        with st.expander("Equipo y política de uso", icon=":material/group:"):
            for member in MEMBERS:
                st.write(f"- {member}")
            st.info(EXECUTION_POLICY_SUMMARY)
        with st.expander("Comprobar conexiones reales (evidencia de la prueba P2-3)", icon=":material/lan:"):
            render_connection_check()
        commit = git_commit()
        short = commit[:7] if commit and commit != "no disponible" else "N/D"
        chips = [("Versión", VERSION), ("Commit", short), ("Última actualización", LAST_UPDATE),
                 ("Sesión iniciada como", f"{user_name} ({user_email})")]
        st.markdown(
            '<div class="dpst-version">' + "".join(
                f'<div class="v"><span class="vl">{lab}</span><span class="vv">{html_escape(val)}</span></div>'
                for lab, val in chips) + "</div>",
            unsafe_allow_html=True,
        )
    if not DEV_MODE and st.button("Cerrar sesión"):
        st.logout()


def _secret(name: str):
    try:
        return st.secrets.get(name)
    except Exception:  # sin secrets.toml, st.secrets lanza en vez de devolver None
        return None


def _connection_checks() -> dict:
    """Una consulta real y pequeña a cada fuente externa del bot."""
    def yahoo_quote():
        q = fetch_quotes(["SPY"])[0]
        if not q.ok:
            return False, q.error or "sin dato"
        when = q.last_bar_at.strftime("%Y-%m-%d %H:%M UTC") if q.last_bar_at else "hora no informada"
        return True, f"SPY {q.price:,.2f} {q.currency or ''} · última barra {when} · {q.session}"

    def yahoo_history():
        today = pd.Timestamp.today().normalize()
        res = fetch_asset_data("SPY", today - pd.Timedelta(days=30), today)
        if not res.ok:
            return False, res.error or "sin datos"
        return True, f"SPY: {len(res.prices)} cierres diarios, último {res.prices.index.max().date()}"

    def fred():
        key = _secret("FRED_API_KEY")
        if not key:
            return False, "sin FRED_API_KEY en los secretos de la app"
        return True, f"búsqueda respondió ({ping_fred(key):,} series de bonos)"

    def google_news():
        items = get_google_news_rss("economía Colombia", 3)
        return (True, f"{len(items)} noticias recibidas") if items else (False, "sin respuesta o sin noticias")

    def alpha_vantage():
        status = _fetch_alpha_vantage(None, GENERAL_NEWS_TOPIC, 3)["status"]
        return status == "ok", status

    return {"Yahoo Finance · cotización (1 min)": yahoo_quote, "Yahoo Finance · históricos": yahoo_history,
            "FRED · tasas": fred, "Google News · RSS": google_news, "Alpha Vantage · noticias": alpha_vantage}


def render_connection_check() -> None:
    """Botón que consulta cada fuente real y acumula el resultado con su hora (consultas sucesivas)."""
    st.caption(
        "Cada clic hace una consulta real a cada fuente y deja una fila con la hora, el resultado y el tiempo. "
        "Para la evidencia de P2-3: hagan al menos dos consultas separadas por unos minutos, descarguen el CSV "
        "y tomen captura. Se guarda solo en esta sesión del navegador."
    )
    if st.button("Probar conexiones ahora", type="primary", key="conn_check_run"):
        with st.spinner("Consultando cada fuente..."):
            st.session_state.setdefault("conn_check_log", []).extend(run_checks(_connection_checks()))
    log = st.session_state.get("conn_check_log", [])
    if log:
        df = pd.DataFrame(log)
        st.dataframe(df, hide_index=True)
        st.download_button("Descargar evidencia (CSV)", df.to_csv(index=False).encode("utf-8"),
                           file_name="evidencia_conexiones.csv", mime="text/csv", key="conn_check_csv")


def _need_asset() -> bool:
    """True si ya hay un activo descargado; si no, deja un aviso dentro de la sección."""
    result = st.session_state.get("asset_result")
    if result is None or not result.ok:
        st.info("Primero descarga un activo en **Datos del activo a probar**.")
        return False
    return True


def render_asset_data() -> None:
    """Datos: probar un activo (RF-05 a RF-07)."""
    st.caption("Requisitos RF-05 a RF-07")
    col1, col2, col3, col4 = st.columns([1, 1, 1, 1.4])
    with col1:
        st.session_state.setdefault("asset_ticker", "AAPL")
        ticker_input = st.text_input(
            "Ticker", key="asset_ticker",
            help="El código corto de la empresa en la bolsa. Ejemplo: Apple = **AAPL**, Coca-Cola = **KO**. "
                 "Si no lo sabes, búscalo en la pestaña **Tickers**.")
    with col2:
        start_date = st.date_input("Fecha inicial", value=pd.Timestamp("2023-01-01"))
    with col3:
        end_date = st.date_input("Fecha final", value=pd.Timestamp.today())
    with col4:
        frequency = st.selectbox("Frecuencia (Semanal recomendada: menos ruido que Diaria)",
                                 list(FREQUENCY_RULES.keys()))

    if st.button("Descargar y limpiar", type="primary"):
        with st.spinner("Descargando..."):
            result = fetch_asset_data(ticker_input, start_date, end_date)
            if result.ok:
                result.prices = resample_prices(result.prices, frequency)
        if result.ok:
            st.session_state["asset_result"] = result
            st.session_state["asset_frequency"] = frequency
        else:
            st.session_state.pop("asset_result", None)
            st.error(f"{result.ticker}: {result.error}")

    # El resumen queda visible aunque se abran o cierren otras secciones.
    result = st.session_state.get("asset_result")
    if result is not None and result.ok:
        st.success(
            f"{result.ticker}: {len(result.prices)} observaciones · "
            f"fuente: {result.source} · moneda: {result.currency or 'N/D'} · "
            f"zona horaria: {result.timezone or 'N/D'} · "
            f"último dato: {result.prices.index.max().date()} · "
            f"frecuencia: {st.session_state.get('asset_frequency')}"
        )
        if result.dropped_rows:
            st.warning(
                f"Se descartaron {result.dropped_rows} filas inválidas "
                "(faltantes o precios no positivos)."
            )
        with st.expander("Ver últimos 20 datos"):
            st.dataframe(result.prices.tail(20))


def render_preselection_page() -> None:
    """
    Preselección (v1): cada bloque es desplegable para no tener que bajar
    tanto; se abre solo lo que se esté mostrando.
    """
    _page_title("Preselección de activos",
                "Abre solo la sección que vas a mostrar. Los datos se conservan al cerrar y abrir.")
    with st.expander("Datos del activo a probar", expanded=True):
        render_asset_data()
    result = st.session_state.get("asset_result")  # leído después de una posible descarga
    ticker = f" · {result.ticker}" if result is not None and result.ok else ""
    with st.expander(f"Análisis histórico{ticker}"):
        if _need_asset():
            render_historical_analysis()
    with st.expander(f"Pronóstico{ticker}"):
        if _need_asset():
            render_forecast()
    with st.expander("Comparación y preselección de activos"):
        render_comparison()
    with st.expander("Pronóstico por canasta de inversión (USD por activo)"):
        render_portfolio_forecast()


if __name__ == "__main__":
    main()
