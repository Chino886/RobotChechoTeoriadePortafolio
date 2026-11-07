"""
Capa de interacción de la interfaz (solo presentación, no toca ningún cálculo).

- CSS: superficies de vidrio, menú tipo "segmented control" con píldora que se desliza,
  borde luminoso que sigue al cursor, revelado al hacer scroll, foco accesible.
- JS: paleta de comandos (Ctrl/⌘ + K), brillo que sigue al cursor, botones magnéticos,
  barra de progreso de scroll y un punto que sigue al mouse sobre la línea de la portada.

El JS se inyecta una sola vez en la página principal desde un componente de altura 0
(`streamlit.components.v1.html`). Solo cambia variables CSS y estilos en línea, y agrega
elementos propios al <body>; no modifica nodos que controla React. Si el navegador lo
bloquea, la app funciona igual sin los efectos.

Como el resto de la CSS del proyecto, apunta a atributos internos de Streamlit
(data-testid, st-key-*, react-aria) y puede requerir ajuste si cambia la versión.
"""
import html
import json

import streamlit as st
import streamlit.components.v1 as components

FX_CSS = """
<style>
::selection { background: rgba(52, 201, 160, 0.35); color: #E8EDF6; }
* { scrollbar-width: thin; scrollbar-color: rgba(148, 170, 210, 0.25) transparent; }

/* Menú superior: segmented control de vidrio con píldora deslizante. */
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] {
    background: rgba(14, 21, 38, 0.72) !important;
    backdrop-filter: blur(18px) saturate(160%); -webkit-backdrop-filter: blur(18px) saturate(160%);
    border: 1px solid rgba(148, 170, 210, 0.14) !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] {
    position: relative; isolation: isolate; background: transparent !important;
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] .react-aria-SelectionIndicator {
    display: block !important; top: 0 !important; bottom: 0 !important; height: auto !important;
    border-radius: 10px; z-index: -1;
    background: linear-gradient(180deg, rgba(52, 201, 160, 0.20), rgba(52, 201, 160, 0.10)) !important;
    box-shadow: inset 0 0 0 1px rgba(52, 201, 160, 0.35), 0 6px 18px rgba(52, 201, 160, 0.12);
    transition: translate 0.45s cubic-bezier(.2, .9, .25, 1), width 0.45s cubic-bezier(.2, .9, .25, 1) !important;
}
.st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"]:hover p { color: #E8EDF6 !important; }

/* Módulos del laboratorio: tarjetas de vidrio; la activa se enciende en verde. */
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] {
    position: relative; border: 1px solid rgba(148, 170, 210, 0.16) !important;
    background: rgba(18, 26, 43, 0.6) !important; backdrop-filter: blur(10px);
    transition: transform 0.35s cubic-bezier(.2, .8, .2, 1), border-color 0.25s, box-shadow 0.25s, background 0.25s !important;
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"]:hover {
    transform: translateY(-2px); border-color: rgba(52, 201, 160, 0.45) !important;
    box-shadow: 0 10px 26px rgba(0, 0, 0, 0.3) !important; background: rgba(18, 26, 43, 0.85) !important;
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] p { color: #C6D0E2 !important; font-weight: 600 !important; }
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"][aria-selected="true"] {
    background: linear-gradient(180deg, rgba(52, 201, 160, 0.22), rgba(52, 201, 160, 0.08)) !important;
    border-color: rgba(111, 227, 193, 0.7) !important;
    box-shadow: 0 0 0 3px rgba(52, 201, 160, 0.12), 0 10px 28px rgba(52, 201, 160, 0.18) !important;
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"][aria-selected="true"] p { color: #E8EDF6 !important; }

/* Pestañas internas de cada sección: subrayado verde que se desliza. */
[data-testid="stTabs"] .react-aria-SelectionIndicator { background-color: #34C9A0; }

/* Expanders y contenedores con borde: vidrio sutil. */
[data-testid="stExpander"] details {
    background: rgba(18, 26, 43, 0.55); backdrop-filter: blur(10px);
    transition: border-color 0.25s, background 0.25s;
}
[data-testid="stExpander"] details:hover { border-color: rgba(52, 201, 160, 0.35) !important; }
[data-testid="stExpander"] summary:hover p { color: #E8EDF6; }

/* Barra lateral de vidrio. */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(18, 26, 43, 0.92), rgba(10, 15, 28, 0.92)) !important;
    backdrop-filter: blur(16px);
}

/* Foco visible y anillo verde en entradas. */
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
    box-shadow: 0 0 0 3px rgba(52, 201, 160, 0.22) !important; border-color: #34C9A0 !important;
}
button:focus-visible, [role="tab"]:focus-visible, a:focus-visible {
    outline: 2px solid #34C9A0 !important; outline-offset: 2px;
}

/* Borde luminoso que sigue al cursor (variables --mx/--my las pone el JS). */
.dpst-card, [data-testid="stMetric"], [data-testid="stPlotlyChart"], [data-testid="stExpander"] details {
    position: relative;
}
.dpst-card::before, [data-testid="stMetric"]::before, [data-testid="stPlotlyChart"]::before, [data-testid="stExpander"] details::before {
    content: ""; position: absolute; inset: -1px; border-radius: inherit; padding: 1px; pointer-events: none;
    background: radial-gradient(260px circle at var(--mx, -999px) var(--my, -999px), rgba(111, 227, 193, 0.75), transparent 65%);
    -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
    -webkit-mask-composite: xor; mask-composite: exclude;
    opacity: 0; transition: opacity 0.3s; z-index: 2;
}
.dpst-card:hover::before, [data-testid="stMetric"]:hover::before, [data-testid="stPlotlyChart"]:hover::before,
[data-testid="stExpander"] details:hover::before { opacity: 1; }
.dpst-card { background-image: radial-gradient(420px circle at var(--mx, -999px) var(--my, -999px), rgba(52, 201, 160, 0.10), transparent 60%), linear-gradient(180deg, rgba(18, 26, 43, 0.85), rgba(18, 26, 43, 0.55)); }

/* Revelado suave al hacer scroll (solo navegadores que lo soportan). */
@keyframes dpst-reveal { from { opacity: 0.2; transform: translateY(22px) scale(0.985); } to { opacity: 1; transform: none; } }
@supports (animation-timeline: view()) {
    [data-testid="stMainBlockContainer"] [data-testid="stElementContainer"]:is(:has([data-testid="stPlotlyChart"]), :has([data-testid="stMetric"]), :has([data-testid="stDataFrame"]), :has(.dpst-card)),
    [data-testid="stMainBlockContainer"] [data-testid="stExpander"] {
        animation: dpst-reveal linear both; animation-timeline: view(); animation-range: entry 0% entry 40%;
    }
}

/* Ventana de bienvenida: fondo desenfocado y panel de vidrio. */
[data-testid="stDialog"] { background: rgba(5, 8, 16, 0.62) !important; backdrop-filter: blur(10px) saturate(140%); -webkit-backdrop-filter: blur(10px) saturate(140%); }
[data-testid="stDialog"] > div {
    background: linear-gradient(180deg, rgba(18, 26, 43, 0.96), rgba(12, 18, 32, 0.96)) !important;
    border: 1px solid rgba(148, 170, 210, 0.18); border-radius: 22px !important;
    box-shadow: 0 40px 100px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 255, 255, 0.05);
    animation: dpst-pop 0.35s cubic-bezier(.2, .9, .25, 1) both;
}
[data-testid="stDialog"] h2 p {
    font-family: 'Instrument Serif', Georgia, serif !important; font-weight: 400 !important; font-size: 2rem !important;
}
@keyframes dpst-pop { from { opacity: 0; transform: translateY(12px) scale(0.97); } to { opacity: 1; transform: none; } }
.dpst-intro-brand { display: flex; align-items: center; gap: 12px; padding-bottom: 0.7rem; }
.dpst-intro-brand .b { font-weight: 700; font-size: 1.15rem; letter-spacing: -0.01em; color: #E8EDF6; }
.dpst-intro-brand .s { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.72rem; letter-spacing: 0.06em; color: #8C99B3; }

/* Disclaimer: tarjeta centrada de vidrio. */
.st-key-dpst_gate {
    max-width: 780px; margin: 1.5rem auto 0; padding: 2rem 2.2rem;
    border-radius: 22px; border: 1px solid rgba(148, 170, 210, 0.16);
    background: radial-gradient(700px 260px at 100% 0%, rgba(52, 201, 160, 0.10), transparent 60%), rgba(18, 26, 43, 0.7);
    backdrop-filter: blur(14px); box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
    animation: dpst-pop 0.45s cubic-bezier(.2, .9, .25, 1) both;
}
.st-key-dpst_gate h3 { font-family: 'Instrument Serif', Georgia, serif !important; font-weight: 400 !important; font-size: 2.4rem !important; }
.st-key-dpst_gate [data-testid="stCheckbox"] { width: 100%; }
.st-key-dpst_gate [data-testid="stCheckbox"] label {
    padding: 0.7rem 0.9rem; border-radius: 12px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: rgba(10, 15, 28, 0.5); width: 100%; transition: border-color 0.2s, background 0.2s;
}
.st-key-dpst_gate [data-testid="stCheckbox"] label:hover { border-color: rgba(52, 201, 160, 0.45); }
.st-key-dpst_gate [data-testid="stCheckbox"] label:has(input:checked) { border-color: rgba(52, 201, 160, 0.55); background: rgba(52, 201, 160, 0.07); }
@media (max-width: 640px) { .st-key-dpst_gate { padding: 1.4rem 1.1rem; margin-top: 0.5rem; } }

/* Expanders principales: el abierto se resalta. */
[data-testid="stMainBlockContainer"] [data-testid="stExpander"] summary { padding-block: 0.85rem; }
[data-testid="stMainBlockContainer"] [data-testid="stExpander"] summary p { font-weight: 600; font-size: 1.02rem; }
[data-testid="stExpander"] details[open] {
    border-color: rgba(52, 201, 160, 0.32) !important;
    box-shadow: 0 14px 36px rgba(0, 0, 0, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.03);
}
[data-testid="stExpander"] details[open] > summary { border-bottom: 1px solid rgba(148, 170, 210, 0.10); }
[data-testid="stExpander"] details[open] > summary p { color: #E8EDF6; }
[data-testid="stExpander"] summary svg { transition: transform 0.3s cubic-bezier(.2, .8, .2, 1), color 0.2s; }
[data-testid="stExpander"] details[open] > summary svg { color: #34C9A0; }

/* Barra lateral: título serif y alertas más sobrias. */
[data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { font-family: 'Instrument Serif', Georgia, serif !important; font-weight: 400 !important; font-size: 1.7rem !important; }

/* Alertas en vidrio. */
[data-testid="stAlert"] > div { backdrop-filter: blur(8px); border: 1px solid rgba(148, 170, 210, 0.10); }

/* Casillas y radios con transición. */
[data-baseweb="checkbox"] span, [data-baseweb="radio"] div { transition: background-color 0.2s, border-color 0.2s, box-shadow 0.2s; }

/* Guía de Apple: respuesta al presionar (pointer-down), no al soltar. Los botones principales
   la reciben desde el resorte del JS, que también maneja su efecto magnético. */
[data-testid="stBaseButton-secondary"]:active, [data-testid="stBaseButton-tertiary"]:active,
.st-key-dpst_nav [role="tab"]:active, .st-key-lab_nav [role="tab"]:active,
[data-testid="stTabs"] [role="tab"]:active, [data-testid="stExpander"] summary:active, .dpst-card:active {
    transform: scale(0.97) !important; transition: transform 100ms ease-out !important;
}
html { font-optical-sizing: auto; }
.dpst-page-title { letter-spacing: -0.02em !important; }

/* Menos transparencia (ajuste del sistema): superficies sólidas, sin desenfoque. */
@media (prefers-reduced-transparency: reduce) {
    [data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stExpander"] details, [data-testid="stMetric"],
    [data-testid="stPlotlyChart"], [data-testid="stDialog"], [data-testid="stDialog"] > div, [data-testid="stAlert"] > div,
    .st-key-dpst_gate, .dpst-card, .st-key-lab_nav [role="tab"],
    .st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] {
        backdrop-filter: none !important; -webkit-backdrop-filter: none !important;
    }
    [data-testid="stExpander"] details, [data-testid="stMetric"], [data-testid="stPlotlyChart"], .dpst-card,
    .st-key-dpst_gate, [data-testid="stDialog"] > div, .st-key-lab_nav [role="tab"],
    .st-key-dpst_nav > [data-testid="stTabs"] > div > [role="tablist"] { background: #121A2B !important; }
    [data-testid="stDialog"] { background: rgba(5, 8, 16, 0.9) !important; }
}
/* Alto contraste (ajuste del sistema): bordes definidos y texto secundario más claro. */
@media (prefers-contrast: more) {
    [data-testid="stExpander"] details, [data-testid="stMetric"], [data-testid="stPlotlyChart"], .dpst-card,
    .st-key-dpst_gate, .st-key-lab_nav [role="tab"], [data-baseweb="input"], [data-baseweb="select"] > div {
        border-color: rgba(232, 237, 246, 0.55) !important;
    }
    .dpst-page-sub, .dpst-card .d, .dpst-hero .meta, [data-testid="stCaptionContainer"] { color: #C6D0E2 !important; }
}

/* Noticias de Inicio: recuadro grande que pasa solo. */
.dpst-news {
    display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(0, 1fr); gap: 14px; outline: none;
}
.dpst-news:focus-visible .nv-stage { box-shadow: 0 0 0 2px #34C9A0, 0 24px 60px rgba(0,0,0,.35); }
.dpst-news .nv-stage {
    position: relative; overflow: hidden; min-height: 390px; border-radius: 22px;
    border: 1px solid rgba(148, 170, 210, 0.16); touch-action: pan-y; cursor: grab;
    background: #0E1526; box-shadow: 0 24px 60px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255,255,255,.04);
}
.dpst-news .nv-stage.dragging { cursor: grabbing; }
.dpst-news .nv-glow {
    position: absolute; inset: -20%; pointer-events: none; transition: background 0.9s ease;
    background: radial-gradient(60% 60% at 85% 10%, rgba(52, 201, 160, 0.22), transparent 60%),
                radial-gradient(50% 60% at 0% 100%, rgba(106, 168, 255, 0.14), transparent 60%);
}
.dpst-news[data-tone="1"] .nv-glow {
    background: radial-gradient(60% 60% at 85% 10%, rgba(106, 168, 255, 0.24), transparent 60%),
                radial-gradient(50% 60% at 0% 100%, rgba(52, 201, 160, 0.12), transparent 60%);
}
.dpst-news[data-tone="2"] .nv-glow {
    background: radial-gradient(60% 60% at 85% 10%, rgba(111, 227, 193, 0.18), transparent 60%),
                radial-gradient(50% 60% at 0% 100%, rgba(245, 184, 75, 0.10), transparent 60%);
}
.dpst-news .nv-track { position: relative; display: flex; height: 100%; min-height: 390px; will-change: transform; }
.dpst-news .nv-slide {
    position: relative; flex: 0 0 100%; min-width: 0; display: flex; flex-direction: column; justify-content: flex-end;
    gap: 14px; padding: 2rem 2.2rem 4.6rem; user-select: none; -webkit-user-select: none;
}
.dpst-news .nv-mono {
    position: absolute; right: 1.2rem; top: -1.4rem; font-family: 'Instrument Serif', Georgia, serif;
    font-size: 15rem; line-height: 1; color: rgba(232, 237, 246, 0.05); pointer-events: none;
}
.dpst-news .nv-meta {
    display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-family: 'Geist Mono', ui-monospace, monospace;
    font-size: 0.74rem; letter-spacing: 0.08em; text-transform: uppercase; color: #8C99B3;
}
.dpst-news .nv-src { color: #BDEFDF; padding: 3px 10px; border-radius: 999px; background: rgba(52,201,160,.12); border: 1px solid rgba(52,201,160,.32); }
.dpst-news .nv-title {
    font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(1.8rem, 3.2vw, 3rem); line-height: 1.06;
    letter-spacing: -0.015em; color: #E8EDF6; text-wrap: balance; max-width: 30ch;
    display: -webkit-box; -webkit-line-clamp: 4; -webkit-box-orient: vertical; overflow: hidden;
}
.dpst-news .nv-link {
    align-self: flex-start; display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 999px;
    font-weight: 600; font-size: 0.92rem; color: #0A0F1C !important; text-decoration: none !important;
    background: linear-gradient(180deg, #6FE3C1, #22A883); box-shadow: 0 8px 22px rgba(52, 201, 160, 0.25);
    transition: transform .2s cubic-bezier(.2,.8,.2,1), box-shadow .2s;
}
.dpst-news .nv-link:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(52, 201, 160, 0.35); }
.dpst-news .nv-link:active { transform: scale(.97); transition-duration: 100ms; }
.dpst-news .nv-ui {
    position: absolute; left: 2.2rem; right: 1.2rem; bottom: 1.1rem; display: flex; align-items: center; justify-content: space-between; z-index: 2;
}
.dpst-news .nv-count { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.8rem; color: #8C99B3; font-variant-numeric: tabular-nums; }
.dpst-news .nv-count b { color: #E8EDF6; font-weight: 500; }
.dpst-news .nv-btns { display: flex; gap: 8px; }
.dpst-news .nv-btn {
    width: 38px; height: 38px; display: grid; place-items: center; border-radius: 999px; cursor: pointer; color: #E8EDF6;
    background: rgba(18, 26, 43, 0.7); border: 1px solid rgba(148, 170, 210, 0.2); backdrop-filter: blur(10px);
    transition: border-color .2s, background .2s, transform .1s ease-out;
}
.dpst-news .nv-btn:hover { border-color: #34C9A0; background: rgba(52, 201, 160, 0.14); }
.dpst-news .nv-btn:active { transform: scale(.92); }
.dpst-news .nv-btn svg { width: 16px; height: 16px; }
.dpst-news .nv-play .i-play, .dpst-news.paused .nv-play .i-pause { display: none; }
.dpst-news.paused .nv-play .i-play { display: block; }
.dpst-news .nv-progress { position: absolute; left: 0; right: 0; bottom: 0; height: 3px; background: rgba(148,170,210,.10); }
.dpst-news .nv-progress i { display: block; height: 100%; width: 100%; transform-origin: 0 50%; transform: scaleX(0);
    background: linear-gradient(90deg, #22A883, #6FE3C1); box-shadow: 0 0 10px rgba(52,201,160,.6); }
.dpst-news .nv-list {
    position: relative; list-style: none; margin: 0; padding: 6px; display: flex; flex-direction: column; gap: 4px; min-width: 0;
    border-radius: 22px; border: 1px solid rgba(148, 170, 210, 0.14); background: rgba(18, 26, 43, 0.55);
    backdrop-filter: blur(10px); max-height: 390px; overflow: auto;
}
.dpst-news .nv-row {
    position: relative; width: 100%; display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 12px; row-gap: 2px;
    text-align: left; padding: 11px 12px 13px; border-radius: 14px; border: 1px solid transparent; background: transparent;
    color: #AEB9CE; cursor: pointer; font: inherit; overflow: hidden;
    transition: background .25s, border-color .25s, color .25s, transform .1s ease-out;
}
.dpst-news .nv-row:hover { background: rgba(232, 237, 246, 0.04); color: #E8EDF6; }
.dpst-news .nv-row:active { transform: scale(.98); }
.dpst-news .nv-row.on { background: rgba(52, 201, 160, 0.10); border-color: rgba(52, 201, 160, 0.30); color: #E8EDF6; }
.dpst-news .nv-n { grid-row: span 2; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.75rem; color: #34C9A0; padding-top: 2px; }
.dpst-news .nv-rt { font-size: 0.9rem; font-weight: 500; line-height: 1.35; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
.dpst-news .nv-rs { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.7rem; color: #8C99B3; letter-spacing: .04em; }
.dpst-news .nv-bar { position: absolute; left: 12px; right: 12px; bottom: 5px; height: 2px; border-radius: 2px; background: transparent; }
.dpst-news .nv-row.on .nv-bar { background: rgba(148,170,210,.14); }
.dpst-news .nv-bar i { display: block; height: 100%; width: 100%; transform-origin: 0 50%; transform: scaleX(0); background: #34C9A0; border-radius: 2px; }
.dpst-news .nv-row:not(.on) .nv-bar i { transform: scaleX(0) !important; }
@media (max-width: 900px) {
    .dpst-news { grid-template-columns: minmax(0, 1fr); }
    .dpst-news .nv-list { max-height: none; flex-direction: row; overflow-x: auto; scroll-snap-type: x mandatory; }
    .dpst-news .nv-list li { flex: 0 0 min(78%, 300px); scroll-snap-align: start; }
}
@media (max-width: 560px) {
    .dpst-news .nv-stage, .dpst-news .nv-track { min-height: 320px; }
    .dpst-news .nv-slide { padding: 1.4rem 1.2rem 4.4rem; }
    .dpst-news .nv-ui { left: 1.2rem; right: 0.8rem; }
    .dpst-news .nv-mono { font-size: 10rem; }
}
@media (prefers-reduced-transparency: reduce) { .dpst-news .nv-list, .dpst-news .nv-btn { backdrop-filter: none; background: #121A2B; } }

/* ===== Piezas comunes ===== */
.dpst-ico { flex: none; }
.dpst-eyebrow {
    display: inline-flex; align-items: center; gap: 8px; color: #34C9A0;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.74rem; letter-spacing: 0.16em; text-transform: uppercase;
}
.dpst-label {
    display: flex; align-items: center; gap: 8px; margin: 1.6rem 0 0.7rem; color: #8C99B3;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.74rem; letter-spacing: 0.14em; text-transform: uppercase;
}
.dpst-label svg { color: #34C9A0; }
.dpst-empty {
    display: flex; gap: 16px; align-items: flex-start; padding: 1.3rem 1.4rem; border-radius: 18px;
    border: 1px dashed rgba(148, 170, 210, 0.28); background: rgba(18, 26, 43, 0.5);
}
.dpst-empty .ic {
    flex: none; width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; color: #6AA8FF;
    background: rgba(106, 168, 255, 0.10); border: 1px solid rgba(106, 168, 255, 0.28);
}
.dpst-empty.warn .ic { color: #F5B84B; background: rgba(245, 184, 75, 0.10); border-color: rgba(245, 184, 75, 0.3); }
.dpst-empty .t { font-weight: 600; color: #E8EDF6; margin-bottom: 2px; }
.dpst-empty .b { color: #AEB9CE; font-size: 0.93rem; line-height: 1.55; }

/* ===== Inicio: encabezado tipo terminal ===== */
.dpst-hero.dash { padding: 2rem 2rem 0; }
.dpst-hero.dash::after {
    content: ""; position: absolute; inset: 0; pointer-events: none; border-radius: inherit; opacity: 0.5;
    background-image: linear-gradient(rgba(148,170,210,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(148,170,210,.05) 1px, transparent 1px);
    background-size: 44px 44px; -webkit-mask-image: radial-gradient(80% 90% at 30% 20%, #000 20%, transparent 75%);
            mask-image: radial-gradient(80% 90% at 30% 20%, #000 20%, transparent 75%);
}
.dpst-hero.dash .h-grid { position: relative; z-index: 2; display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.05fr); gap: 1.6rem; align-items: stretch; }
.dpst-hero.dash .copy { max-width: none; display: flex; flex-direction: column; justify-content: center; align-items: flex-start; }
.dpst-hero.dash .brand { display: flex; align-items: center; gap: 18px; margin-top: 1rem; }
.dpst-hero.dash .brand svg { filter: drop-shadow(0 0 22px rgba(52, 201, 160, 0.35)); }
.dpst-hero.dash h1 {
    margin: 0 !important; font-size: clamp(4rem, 9vw, 7.4rem) !important; line-height: 0.9 !important; letter-spacing: -0.02em;
    background: linear-gradient(180deg, #FFFFFF 10%, #BDEFDF 70%, #6FE3C1); -webkit-background-clip: text; background-clip: text; color: transparent !important;
}
.dpst-hero.dash .sub { font-size: 1.3rem; margin-top: 0.8rem; color: #E8EDF6; font-weight: 500; letter-spacing: -0.01em; }
.dpst-hero.dash .meta { margin-top: 0.7rem; max-width: 46ch; line-height: 1.7; }
.dpst-hero.dash .spark { position: static; width: 100%; height: 100%; }
.dpst-hero.dash .dpst-tape { margin: 1.6rem -2rem 0; }
.dpst-chart {
    position: relative; display: flex; flex-direction: column; border-radius: 18px; overflow: hidden;
    border: 1px solid rgba(148, 170, 210, 0.16); background: linear-gradient(180deg, rgba(10, 15, 28, 0.72), rgba(14, 21, 38, 0.6));
    box-shadow: 0 20px 50px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.04); animation: dpst-rise .8s cubic-bezier(.2,.8,.2,1) .1s both;
}
.dpst-chart .c-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding: 0.9rem 1.1rem; border-bottom: 1px solid rgba(148, 170, 210, 0.10); flex-wrap: wrap; }
.dpst-chart .c-title { font-weight: 600; color: #E8EDF6; font-size: 0.98rem; }
.dpst-chart .c-badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.68rem; letter-spacing: .06em; }
.dpst-chart .c-badge.real { color: #BDEFDF; background: rgba(52, 201, 160, 0.12); border: 1px solid rgba(52, 201, 160, 0.35); }
.dpst-chart .c-badge.demo { color: #AEB9CE; background: rgba(148, 170, 210, 0.08); border: 1px solid rgba(148, 170, 210, 0.22); }
.dpst-chart .c-plot { position: relative; flex: 1; min-height: 210px; padding: 0.6rem 1rem 0.2rem 1rem; }
.dpst-chart .c-plot .grid line { stroke: rgba(148, 170, 210, 0.10); stroke-width: 1; vector-effect: non-scaling-stroke; }
.dpst-chart .c-y { position: absolute; right: 1.2rem; top: 0.6rem; bottom: 0.6rem; display: flex; flex-direction: column; justify-content: space-between; z-index: 2;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.68rem; color: #8C99B3; pointer-events: none; }
.dpst-chart .c-foot { display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap; padding: 0.7rem 1.1rem 0.9rem; border-top: 1px solid rgba(148, 170, 210, 0.10);
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.74rem; color: #8C99B3; }
.dpst-chart .c-foot b { color: #E8EDF6; font-weight: 600; font-size: 0.9rem; }
.dpst-chart .c-foot span:only-child { font-family: 'Geist', system-ui, sans-serif; font-size: 0.84rem; }

/* ===== Indicadores ===== */
.dpst-kpis { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; margin-top: 14px; }
.dpst-kpis .kpi {
    position: relative; padding: 1rem 1.1rem; border-radius: 16px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: linear-gradient(180deg, rgba(18, 26, 43, 0.85), rgba(14, 21, 38, 0.7)); min-width: 0;
    transition: border-color .25s, transform .4s cubic-bezier(.2,.8,.2,1); animation: dpst-rise .7s cubic-bezier(.2,.8,.2,1) both;
}
.dpst-kpis .kpi:hover { border-color: rgba(52, 201, 160, 0.4); transform: translateY(-3px); }
.dpst-kpis .k-top { display: flex; align-items: center; gap: 8px; }
.dpst-kpis .k-ic { width: 28px; height: 28px; border-radius: 8px; display: grid; place-items: center; color: #34C9A0; background: rgba(52, 201, 160, 0.10); }
.dpst-kpis .k-lab { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.7rem; letter-spacing: .12em; text-transform: uppercase; color: #8C99B3; }
.dpst-kpis .k-val { margin-top: 0.7rem; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 1.7rem; font-weight: 500; color: #E8EDF6; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.dpst-kpis .k-note { margin-top: 0.2rem; font-size: 0.8rem; line-height: 1.4; color: #8C99B3; overflow-wrap: anywhere; }
.dpst-kpis .kpi.good .k-ic { color: #34C9A0; }
.dpst-kpis .kpi.warn .k-ic { color: #F5B84B; background: rgba(245, 184, 75, 0.10); }
.dpst-kpis .kpi.good::after, .dpst-kpis .kpi.warn::after {
    content: ""; position: absolute; top: 1rem; right: 1rem; width: 8px; height: 8px; border-radius: 50%;
    background: #34C9A0; box-shadow: 0 0 10px #34C9A0; animation: dpst-pulse 2.4s infinite;
}
.dpst-kpis .kpi.warn::after { background: #F5B84B; box-shadow: 0 0 10px #F5B84B; }

/* ===== Accesos rápidos ===== */
.dpst-mods { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.dpst-mods .mod {
    position: relative; display: flex; flex-direction: column; align-items: flex-start; gap: 8px; text-align: left; cursor: pointer;
    padding: 1.15rem 1.15rem 1rem; border-radius: 18px; border: 1px solid rgba(148, 170, 210, 0.14); color: #E8EDF6; font: inherit;
    background: radial-gradient(240px 120px at 100% 0%, rgba(52, 201, 160, 0.10), transparent 70%), rgba(18, 26, 43, 0.75);
    transition: border-color .25s, transform .4s cubic-bezier(.2,.8,.2,1), box-shadow .3s; animation: dpst-rise .7s cubic-bezier(.2,.8,.2,1) both; overflow: hidden;
}
.dpst-mods .mod:hover { border-color: rgba(52, 201, 160, 0.5); transform: translateY(-4px); box-shadow: 0 16px 36px rgba(0, 0, 0, 0.35), 0 0 0 1px rgba(52,201,160,.12); }
.dpst-mods .mod:active { transform: scale(0.97); transition-duration: 100ms; }
.dpst-mods .m-ic { width: 44px; height: 44px; border-radius: 12px; display: grid; place-items: center; color: #6FE3C1;
    background: linear-gradient(180deg, rgba(52, 201, 160, 0.18), rgba(52, 201, 160, 0.06)); border: 1px solid rgba(52, 201, 160, 0.3);
    transition: transform .4s cubic-bezier(.2,.8,.2,1); }
.dpst-mods .mod:hover .m-ic { transform: rotate(-6deg) scale(1.06); }
.dpst-mods .m-name { font-weight: 600; font-size: 1.02rem; margin-top: 4px; }
.dpst-mods .m-desc { color: #94A1BA; font-size: 0.86rem; line-height: 1.45; flex: 1; }
.dpst-mods .m-go { display: inline-flex; align-items: center; gap: 6px; color: #34C9A0; font-weight: 600; font-size: 0.86rem; margin-top: 4px; }
.dpst-mods .m-go svg { transition: transform .3s cubic-bezier(.2,.8,.2,1); }
.dpst-mods .mod:hover .m-go svg { transform: translateX(4px); }

/* ===== Guía de uso: cinco pasos ===== */
.dpst-steps { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.dpst-card.step { display: flex; flex-direction: column; min-height: 0; padding: 1.1rem 1.1rem 1rem; }
.dpst-card.step .s-top { display: flex; align-items: center; justify-content: space-between; }
.dpst-card.step .s-num { font-family: 'Instrument Serif', Georgia, serif; font-size: 2.6rem; line-height: 1;
    background: linear-gradient(180deg, #6FE3C1, rgba(52, 201, 160, 0.35)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.dpst-card.step .s-ic { width: 38px; height: 38px; border-radius: 11px; display: grid; place-items: center; color: #6FE3C1;
    background: rgba(52, 201, 160, 0.10); border: 1px solid rgba(52, 201, 160, 0.28); transition: transform .4s cubic-bezier(.2,.8,.2,1); }
.dpst-card.step:hover .s-ic { transform: translateY(-2px) rotate(-6deg); }
.dpst-card.step .n { margin-top: 0.7rem; }
.dpst-card.step .d { flex: 1; }
.dpst-card.step .s-go {
    align-self: flex-start; margin-top: 0.9rem; display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px; border-radius: 999px;
    font: inherit; font-size: 0.8rem; font-weight: 600; color: #BDEFDF; cursor: pointer;
    background: rgba(52, 201, 160, 0.08); border: 1px solid rgba(52, 201, 160, 0.28); transition: background .2s, border-color .2s, transform .1s ease-out;
}
.dpst-card.step .s-go:hover { background: rgba(52, 201, 160, 0.18); border-color: #34C9A0; }
.dpst-card.step .s-go:active { transform: scale(0.96); }
.dpst-card.step .s-go svg { transition: transform .3s cubic-bezier(.2,.8,.2,1); }
.dpst-card.step .s-go:hover svg { transform: translateX(3px); }

/* ===== DPST Financial News ===== */
.dpst-newshead { margin-top: 2.2rem; }
.dpst-newshead .nh-title { font-family: 'Instrument Serif', Georgia, serif; font-size: clamp(2rem, 3.4vw, 2.8rem); line-height: 1.05; color: #E8EDF6; margin-top: 0.35rem; letter-spacing: -0.015em; }
.dpst-news .nv-slide.has-img { flex-direction: row; align-items: stretch; gap: 1.6rem; justify-content: flex-start; }
.dpst-news .nv-body { position: relative; z-index: 1; display: flex; flex-direction: column; justify-content: flex-end; gap: 12px; min-width: 0; flex: 1; }
.dpst-news .nv-slide.has-img .nv-body { justify-content: center; }
.dpst-news .nv-media { flex: 0 0 38%; max-width: 38%; border-radius: 16px; overflow: hidden; border: 1px solid rgba(148, 170, 210, 0.16); align-self: center; aspect-ratio: 4 / 3; background: #0A0F1C; }
.dpst-news .nv-media img { width: 100%; height: 100%; object-fit: cover; display: block; transition: transform 6s ease; }
.dpst-news .nv-slide:not([aria-hidden="true"]) .nv-media img { transform: scale(1.06); }
.dpst-news .nv-cat { color: #0A0F1C; background: linear-gradient(180deg, #6FE3C1, #22A883); padding: 3px 10px; border-radius: 999px; font-weight: 600; }
.dpst-news .nv-sum { color: #AEB9CE; font-size: 0.98rem; line-height: 1.55; max-width: 62ch;
    display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
.dpst-news .nv-slide.has-img .nv-title { font-size: clamp(1.5rem, 2.4vw, 2.3rem); }
.dpst-news .nv-pips { display: flex; gap: 6px; align-items: center; }
.dpst-news .nv-pip { width: 7px; height: 7px; padding: 0; border-radius: 999px; border: 0; cursor: pointer; background: rgba(232, 237, 246, 0.25);
    transition: width .35s cubic-bezier(.2,.9,.25,1), background .25s; }
.dpst-news .nv-pip:hover { background: rgba(232, 237, 246, 0.5); }
.dpst-news .nv-pip.on { width: 22px; background: #34C9A0; }

/* ===== Pie de Inicio ===== */
.st-key-dpst_home_footer { margin-top: 1.6rem; padding: 0.2rem 1.2rem 1.2rem; border-radius: 22px; border: 1px solid rgba(148, 170, 210, 0.12); background: rgba(14, 21, 38, 0.5); }
.dpst-version { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 0.4rem; }
.dpst-version .v { padding: 0.75rem 0.9rem; border-radius: 12px; border: 1px solid rgba(148, 170, 210, 0.12); background: rgba(10, 15, 28, 0.55); min-width: 0; }
.dpst-version .vl { display: block; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; letter-spacing: .12em; text-transform: uppercase; color: #8C99B3; }
.dpst-version .vv { display: block; margin-top: 3px; color: #E8EDF6; font-size: 0.88rem; overflow-wrap: anywhere; }

@media (max-width: 1100px) {
    .dpst-steps { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
    .dpst-hero.dash .h-grid { grid-template-columns: minmax(0, 1fr); }
    .dpst-kpis, .dpst-mods, .dpst-version { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .dpst-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .dpst-news .nv-slide.has-img { flex-direction: column; }
    .dpst-news .nv-media { flex: none; max-width: 100%; width: 100%; aspect-ratio: 16 / 7; }
}
@media (max-width: 560px) {
    .dpst-hero.dash { padding: 1.4rem 1.1rem 0; }
    .dpst-hero.dash .dpst-tape { margin: 1.4rem -1.1rem 0; }
    .dpst-hero.dash .brand svg { width: 52px; height: 52px; }
    .dpst-kpis, .dpst-mods, .dpst-steps, .dpst-version { grid-template-columns: minmax(0, 1fr); }
    .dpst-news .nv-pips { display: none; }
}
@media (prefers-reduced-motion: reduce) {
    .dpst-news .nv-media img { transition: none; transform: none !important; }
}

/* ===== Encabezado común de pantalla ===== */
.dpst-ph { margin: 0.4rem 0 0.4rem; }
.dpst-ph .dpst-page-title { margin-top: 0.35rem; }

/* ===== Tickers: screener ===== */
.st-key-tk_left {
    position: sticky; top: calc(env(safe-area-inset-top, 0px) + 90px);
    padding: 0.4rem 1.1rem 1.2rem; border-radius: 20px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: linear-gradient(180deg, rgba(18, 26, 43, 0.9), rgba(14, 21, 38, 0.75)); box-shadow: 0 20px 50px rgba(0,0,0,.3);
    animation: dpst-rise .6s cubic-bezier(.2,.8,.2,1) both;
}
.st-key-tk_left .dpst-label { margin: 1.1rem 0 0.4rem; }
.st-key-ticker_search input {
    padding-left: 2.4rem !important; font-size: 1rem !important;
    background: no-repeat 0.8rem 50% / 17px url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%2334C9A0' stroke-width='2' stroke-linecap='round'%3E%3Ccircle cx='11' cy='11' r='7'/%3E%3Cpath d='m20 20-3.5-3.5'/%3E%3C/svg%3E") !important;
}
.st-key-ticker_search [data-baseweb="input"] { min-height: 46px; }
.tk-count { margin: 0.9rem 0 0.4rem; padding: 0.9rem 1rem; border-radius: 14px; border: 1px solid rgba(52, 201, 160, 0.22);
    background: linear-gradient(180deg, rgba(52, 201, 160, 0.10), rgba(52, 201, 160, 0.03)); }
.tk-count .v { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 1.7rem; color: #E8EDF6; font-variant-numeric: tabular-nums; letter-spacing: -0.02em; }
.tk-count .l { margin-left: 8px; color: #8C99B3; font-size: 0.86rem; }
.tk-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: 0.55rem; }
.tk-chips .lab { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; letter-spacing: .1em; text-transform: uppercase; color: #8C99B3; margin-right: 2px; }
.tk-chips .chip { display: inline-flex; align-items: center; gap: 5px; padding: 3px 9px; border-radius: 999px; font-size: 0.78rem; color: #BDEFDF;
    background: rgba(52, 201, 160, 0.12); border: 1px solid rgba(52, 201, 160, 0.35); animation: dpst-rise .35s cubic-bezier(.2,.8,.2,1) both; }

.tk-bar { position: relative; display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 0.2rem 0.2rem 0.8rem; color: #AEB9CE; font-size: 0.95rem; }
.tk-bar .v { font-family: 'Geist Mono', ui-monospace, monospace; color: #34C9A0; font-weight: 600; font-size: 1.05rem; }
.tk-opts { position: relative; z-index: 20; }
.tk-opts > summary {
    list-style: none; display: inline-flex; align-items: center; gap: 8px; cursor: pointer; padding: 8px 14px; border-radius: 999px;
    color: #E8EDF6; font-weight: 600; font-size: 0.86rem; background: rgba(18, 26, 43, 0.8); border: 1px solid rgba(148, 170, 210, 0.2);
    transition: border-color .2s, background .2s, transform .1s ease-out; user-select: none;
}
.tk-opts > summary::-webkit-details-marker { display: none; }
.tk-opts > summary:hover, .tk-opts[open] > summary { border-color: #34C9A0; background: rgba(52, 201, 160, 0.12); }
.tk-opts > summary:active { transform: scale(.96); }
.tk-opts > summary svg { color: #34C9A0; }
.tk-opts-panel {
    position: absolute; right: 0; top: calc(100% + 10px); width: min(340px, 86vw); padding: 0.4rem 1rem 0.8rem; border-radius: 18px;
    background: rgba(14, 21, 38, 0.94); border: 1px solid rgba(148, 170, 210, 0.2); backdrop-filter: blur(18px) saturate(160%);
    box-shadow: 0 30px 70px rgba(0, 0, 0, 0.5); transform-origin: top right; animation: dpst-pop .25s cubic-bezier(.2,.9,.25,1) both;
}
.tk-opts-panel .og { padding: 0.7rem 0; border-bottom: 1px solid rgba(148, 170, 210, 0.10); }
.tk-opts-panel .og:last-child { border-bottom: 0; }
.tk-opts-panel .ot { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; letter-spacing: .12em; text-transform: uppercase; color: #8C99B3; margin-bottom: 0.45rem; }
.tk-opts-panel .ob { color: #C6D0E2; font-size: 0.86rem; line-height: 1.5; }
.tk-opts-panel ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; max-height: 180px; overflow: auto; }
.tk-opts-panel li { display: flex; align-items: center; justify-content: space-between; gap: 10px; color: #8C99B3; font-size: 0.85rem; }
.tk-opts-panel li b { font-family: 'Geist Mono', ui-monospace, monospace; color: #E8EDF6; font-weight: 500; }

.tk-table {
    max-height: 560px; overflow: auto; border-radius: 18px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: rgba(10, 15, 28, 0.6); box-shadow: 0 20px 50px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,.03);
}
.tk-table table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 0.92rem; }
.tk-table thead th {
    position: sticky; top: 0; z-index: 2; text-align: left; padding: 0.85rem 1rem; white-space: nowrap;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.7rem; font-weight: 500; letter-spacing: .12em; text-transform: uppercase; color: #8C99B3;
    background: rgba(18, 26, 43, 0.97); border-bottom: 1px solid rgba(148, 170, 210, 0.16); backdrop-filter: blur(8px);
}
.tk-table thead th[data-sort] { cursor: pointer; user-select: none; transition: color .2s; }
.tk-table thead th[data-sort]:hover { color: #E8EDF6; }
.tk-table thead th[data-sort]::after { content: "↕"; margin-left: 6px; opacity: .35; }
.tk-table thead th[data-dir="asc"]::after { content: "↑"; opacity: 1; color: #34C9A0; }
.tk-table thead th[data-dir="desc"]::after { content: "↓"; opacity: 1; color: #34C9A0; }
.tk-table tbody tr { cursor: pointer; transition: background .2s; animation: dpst-rise .45s cubic-bezier(.2,.8,.2,1) both; }
.tk-table tbody td { padding: 0.62rem 1rem; border-bottom: 1px solid rgba(148, 170, 210, 0.07); color: #C6D0E2; vertical-align: middle; }
.tk-table tbody tr:nth-child(even) td { background: rgba(232, 237, 246, 0.012); }
.tk-table tbody tr:hover td { background: rgba(52, 201, 160, 0.07); color: #E8EDF6; }
.tk-table tbody tr:active td { background: rgba(52, 201, 160, 0.14); }
.tk-table tbody tr.on td { background: rgba(52, 201, 160, 0.13); color: #E8EDF6; }
.tk-table tbody tr.on td:first-child { box-shadow: inset 3px 0 0 #34C9A0; }
.tk-table td.n, .tk-table th.n { width: 3.2rem; color: #5F6B85; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.75rem; }
.tk-table td.tk { white-space: nowrap; }
.tk-table td.tk b { font-family: 'Geist Mono', ui-monospace, monospace; font-weight: 600; color: #E8EDF6; letter-spacing: .02em; }
.tk-table td.em { min-width: 14rem; }
.tk-av { display: inline-grid; place-items: center; width: 28px; height: 28px; margin-right: 10px; border-radius: 9px; vertical-align: middle;
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.8rem; font-weight: 600; }
.tk-av.h0 { color: #6FE3C1; background: rgba(52, 201, 160, 0.14); border: 1px solid rgba(52, 201, 160, 0.3); }
.tk-av.h1 { color: #9CC4FF; background: rgba(106, 168, 255, 0.14); border: 1px solid rgba(106, 168, 255, 0.3); }
.tk-av.h2 { color: #7FD6E8; background: rgba(127, 214, 232, 0.12); border: 1px solid rgba(127, 214, 232, 0.28); }
.tk-ex { display: inline-block; padding: 2px 9px; border-radius: 7px; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.74rem; color: #AEB9CE;
    background: rgba(148, 170, 210, 0.08); border: 1px solid rgba(148, 170, 210, 0.16); white-space: nowrap; }
.tk-type { display: inline-flex; align-items: center; gap: 5px; padding: 3px 10px; border-radius: 999px; font-size: 0.78rem; font-weight: 500; white-space: nowrap; }
.tk-type.stock { color: #BDEFDF; background: rgba(52, 201, 160, 0.12); border: 1px solid rgba(52, 201, 160, 0.32); }
.tk-type.etf { color: #C9DCFF; background: rgba(106, 168, 255, 0.12); border: 1px solid rgba(106, 168, 255, 0.32); }
.tk-type.other { color: #E8EDF6; background: rgba(148, 170, 210, 0.10); border: 1px solid rgba(148, 170, 210, 0.24); }
.tk-sel { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; margin-top: 12px; padding: 0.9rem 1.1rem; border-radius: 16px;
    border: 1px solid rgba(52, 201, 160, 0.35); background: radial-gradient(400px 120px at 0% 0%, rgba(52,201,160,.14), transparent 70%), rgba(18, 26, 43, 0.8);
    animation: dpst-rise .4s cubic-bezier(.2,.8,.2,1) both; }
.tk-sel .tk-av { width: 40px; height: 40px; font-size: 1rem; margin-right: 0; }
.tk-sel .sx { flex: 1; min-width: 12rem; }
.tk-sel .st { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.66rem; letter-spacing: .12em; text-transform: uppercase; color: #34C9A0; }
.tk-sel .sn { color: #E8EDF6; font-size: 1rem; margin-top: 2px; }
.tk-sel .sn b { font-family: 'Geist Mono', ui-monospace, monospace; margin-right: 6px; }
@media (max-width: 900px) {
    .st-key-tk_left { position: static; }
    .tk-table { max-height: 460px; }
    .tk-table td.em { min-width: 10rem; }
}
@media (prefers-reduced-transparency: reduce) { .tk-opts-panel { backdrop-filter: none; background: #121A2B; } }

/* ===== Preselección: panel de estado ===== */
.ps-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.ps-head .dpst-label { margin-bottom: 0.7rem; }
.ps-focus { display: inline-flex; align-items: center; gap: 7px; padding: 6px 12px; border-radius: 999px; cursor: pointer; font: inherit; font-size: 0.8rem; font-weight: 600;
    color: #AEB9CE; background: rgba(18, 26, 43, 0.8); border: 1px solid rgba(148, 170, 210, 0.2); transition: color .2s, border-color .2s, background .2s, transform .1s ease-out; }
.ps-focus:hover { color: #E8EDF6; border-color: rgba(52, 201, 160, 0.5); }
.ps-focus:active { transform: scale(.96); }
.ps-focus[aria-pressed="true"] { color: #0A0F1C; background: linear-gradient(180deg, #6FE3C1, #22A883); border-color: transparent; }
.ps-status { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 10px; margin-bottom: 1.1rem; }
.ps-mod { position: relative; display: flex; align-items: center; gap: 10px; text-align: left; cursor: pointer; font: inherit; padding: 0.8rem 0.9rem; min-width: 0;
    border-radius: 14px; border: 1px solid rgba(148, 170, 210, 0.14); background: rgba(18, 26, 43, 0.75); color: #E8EDF6;
    transition: border-color .25s, transform .35s cubic-bezier(.2,.8,.2,1), background .25s; animation: dpst-rise .6s cubic-bezier(.2,.8,.2,1) both; }
.ps-mod:hover { transform: translateY(-2px); border-color: rgba(52, 201, 160, 0.45); }
.ps-mod:active { transform: scale(.97); }
.ps-ic { flex: none; width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; color: #8C99B3; background: rgba(148, 170, 210, 0.08); border: 1px solid rgba(148, 170, 210, 0.16); }
.ps-tx { display: flex; flex-direction: column; min-width: 0; }
.ps-n { font-weight: 600; font-size: 0.88rem; }
.ps-s { font-size: 0.74rem; color: #8C99B3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.ps-dot { position: absolute; top: 9px; right: 10px; width: 7px; height: 7px; border-radius: 50%; background: rgba(148, 170, 210, 0.35); }
.ps-mod.ok .ps-ic { color: #6FE3C1; background: rgba(52, 201, 160, 0.12); border-color: rgba(52, 201, 160, 0.32); }
.ps-mod.ok .ps-dot { background: #34C9A0; box-shadow: 0 0 8px #34C9A0; }
.ps-mod.ok .ps-s { color: #BDEFDF; }
.ps-mod.ready .ps-ic { color: #9CC4FF; background: rgba(106, 168, 255, 0.12); border-color: rgba(106, 168, 255, 0.32); }
.ps-mod.ready .ps-dot { background: #6AA8FF; box-shadow: 0 0 8px #6AA8FF; }
.ps-mod.wait .ps-dot { background: #F5B84B; }

/* ===== Preselección: módulos desplegables ===== */
.st-key-ps_modules > div > [data-testid="stElementContainer"] [data-testid="stExpander"] > details,
.st-key-ps_modules [data-testid="stExpander"] > details { border-radius: 18px !important; }
.st-key-ps_modules > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"] > [data-testid="stExpander"] > details > summary,
.st-key-ps_modules > [data-testid="stVerticalBlock"] > [data-testid="stExpander"] > details > summary { padding: 1rem 1.2rem !important; }
.st-key-ps_modules summary [data-testid="stExpanderIcon"], .st-key-ps_modules summary [data-testid="stIconMaterial"] { color: #34C9A0; }
.st-key-ps_modules details > summary { position: relative; }
.st-key-ps_modules details[open] > summary::after {
    content: "Abierto"; position: absolute; right: 3.2rem; top: 50%; transform: translateY(-50%);
    font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.64rem; letter-spacing: .12em; text-transform: uppercase;
    color: #BDEFDF; padding: 2px 8px; border-radius: 999px; background: rgba(52, 201, 160, 0.12); border: 1px solid rgba(52, 201, 160, 0.32);
}
.st-key-ps_modules details details[open] > summary::after { content: none; }
@keyframes dpst-acc { from { opacity: 0; transform: translateY(-6px); } to { opacity: 1; transform: none; } }
.st-key-ps_modules details[open] > [data-testid="stExpanderDetails"], .st-key-ps_modules details[open] > div { animation: dpst-acc .35s cubic-bezier(.2,.8,.2,1) both; }
.st-key-ps_modules [data-testid="stExpanderDetails"] .dpst-label:first-child { margin-top: 0.2rem; }
.st-key-ps_modules [data-testid="stPlotlyChart"] { animation: dpst-rise .6s cubic-bezier(.2,.8,.2,1) both; }
.st-key-ps_modules [data-testid="stTabs"] [role="tablist"] { gap: 4px; }
.st-key-ps_modules [data-testid="stTabs"] [role="tab"] { padding: 6px 12px; border-radius: 10px 10px 0 0; }
.st-key-ps_modules [data-testid="stTabs"] [role="tab"][aria-selected="true"] { background: rgba(52, 201, 160, 0.08); }
.st-key-ps_modules [data-testid="stMetric"] { border-left: 1px solid rgba(148, 170, 210, 0.14); }
.st-key-ps_modules [data-testid="stMetricDelta"] svg { display: inline; }
.st-key-ps_modules [data-baseweb="input"], .st-key-ps_modules [data-baseweb="select"] > div { min-height: 42px; }
.st-key-ps_modules [data-testid="stDateInput"] input { font-family: 'Geist Mono', ui-monospace, monospace; letter-spacing: .02em; }
.st-key-ps_modules [data-testid="stAlert"] { border-radius: 14px; }
[data-testid="stSpinner"] { color: #6FE3C1; }
[data-testid="stSpinner"] i { border-color: #34C9A0 rgba(52,201,160,.2) rgba(52,201,160,.2) !important; }
@media (max-width: 1100px) { .ps-status { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 700px) {
    .ps-status { grid-template-columns: minmax(0, 1fr); }
    .st-key-ps_modules details[open] > summary::after { content: none; }
}

/* ===== Tasas soberanas ===== */
.rs-status { display: flex; flex-wrap: wrap; gap: 8px; margin: 0.6rem 0 0.6rem; }
.rs-pill { display: inline-flex; align-items: center; gap: 7px; padding: 5px 12px; border-radius: 999px; font-size: 0.8rem; font-weight: 500;
    color: #C6D0E2; background: rgba(18, 26, 43, 0.85); border: 1px solid rgba(148, 170, 210, 0.18); }
.rs-pill svg { color: #6AA8FF; }
.rs-pill i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.rs-pill.ok { color: #BDEFDF; border-color: rgba(52, 201, 160, 0.4); background: rgba(52, 201, 160, 0.10); }
.rs-pill.ok i { background: #34C9A0; box-shadow: 0 0 8px #34C9A0; animation: dpst-pulse 2.4s infinite; }
.rs-pill.warn { color: #F7D08A; border-color: rgba(245, 184, 75, 0.4); background: rgba(245, 184, 75, 0.08); }
.rs-pill.warn i { background: #F5B84B; box-shadow: 0 0 8px #F5B84B; }
.rs-source { display: flex; gap: 10px; align-items: flex-start; padding: 0.8rem 1rem; border-radius: 14px; margin-bottom: 1rem;
    color: #94A1BA; font-size: 0.86rem; line-height: 1.55; background: rgba(14, 21, 38, 0.6); border: 1px solid rgba(148, 170, 210, 0.12); }
.rs-source svg { color: #6AA8FF; margin-top: 2px; }
.rs-nokey { display: flex; gap: 20px; align-items: flex-start; padding: 1.6rem 1.7rem; border-radius: 22px; margin-bottom: 14px;
    border: 1px dashed rgba(106, 168, 255, 0.45); background: radial-gradient(500px 200px at 0% 0%, rgba(106,168,255,.12), transparent 70%), rgba(14, 21, 38, 0.7);
    animation: dpst-rise .6s cubic-bezier(.2,.8,.2,1) both; }
.rs-nokey .nk-ic { flex: none; width: 60px; height: 60px; border-radius: 18px; display: grid; place-items: center; color: #9CC4FF;
    background: rgba(106, 168, 255, 0.12); border: 1px solid rgba(106, 168, 255, 0.35); }
.rs-nokey .nk-t { font-family: 'Instrument Serif', Georgia, serif; font-size: 1.9rem; line-height: 1.1; color: #E8EDF6; }
.rs-nokey .nk-b { color: #AEB9CE; margin-top: 0.4rem; }
.rs-nokey .nk-steps { margin: 0.9rem 0 0; padding-left: 1.2rem; color: #C6D0E2; font-size: 0.92rem; line-height: 1.75; }
.rs-nokey code { font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.82rem; color: #BDEFDF; background: rgba(52,201,160,.10); padding: 1px 6px; border-radius: 6px; }
.rs-nokey .nk-btn { display: inline-flex; align-items: center; gap: 8px; margin-top: 1rem; padding: 10px 16px; border-radius: 10px; font-weight: 600; font-size: 0.9rem;
    color: #0A0F1C !important; text-decoration: none !important; background: linear-gradient(180deg, #9CC4FF, #4F8FEA); box-shadow: 0 8px 22px rgba(106,168,255,.25);
    transition: transform .2s cubic-bezier(.2,.8,.2,1), box-shadow .2s; }
.rs-nokey .nk-btn:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(106,168,255,.35); }
.rs-nokey .nk-btn:active { transform: scale(.97); }
.rs-illus { padding: 1.1rem 1.3rem 1rem; border-radius: 20px; border: 1px solid rgba(148, 170, 210, 0.14); background: rgba(10, 15, 28, 0.6); animation: dpst-rise .7s cubic-bezier(.2,.8,.2,1) .1s both; }
.rs-illus .ri-head { display: flex; align-items: center; justify-content: space-between; gap: 10px; flex-wrap: wrap; margin-bottom: 0.4rem; }
.rs-illus .ri-t { font-weight: 600; color: #E8EDF6; }
.rs-illus > svg { width: 100%; height: auto; max-height: 280px; display: block; }
.rs-illus > svg .g line { stroke: rgba(148, 170, 210, 0.10); }
.rs-illus > svg .l { stroke-dasharray: 900; animation: dpst-draw 2s cubic-bezier(.6,.1,.2,1) .2s both; }
.rs-illus > svg circle { fill: #0A0F1C; stroke: #6AA8FF; stroke-width: 2.4; animation: dpst-fade .4s ease 1.8s both; }
.rs-illus .ri-x { display: flex; justify-content: space-between; padding: 0 2% 0 6%; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.72rem; color: #8C99B3; }
.rs-illus .ri-note { margin-top: 0.8rem; color: #94A1BA; font-size: 0.86rem; line-height: 1.55; }
.rs-illus .c-badge { display: inline-flex; align-items: center; gap: 6px; padding: 3px 10px; border-radius: 999px; font-family: 'Geist Mono', ui-monospace, monospace; font-size: 0.68rem;
    color: #F7D08A; background: rgba(245, 184, 75, 0.08); border: 1px solid rgba(245, 184, 75, 0.35); }
.rs-edus { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; }
.rs-edu { padding: 1rem 1.1rem; border-radius: 16px; border: 1px solid rgba(148, 170, 210, 0.14); background: rgba(18, 26, 43, 0.7);
    transition: border-color .25s, transform .35s cubic-bezier(.2,.8,.2,1); animation: dpst-rise .6s cubic-bezier(.2,.8,.2,1) both; }
.rs-edu:hover { border-color: rgba(106, 168, 255, 0.45); transform: translateY(-3px); }
.rs-edu .e-ic { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; color: #9CC4FF; background: rgba(106,168,255,.12); border: 1px solid rgba(106,168,255,.3); }
.rs-edu .e-t { margin-top: 0.7rem; font-weight: 600; color: #E8EDF6; font-size: 0.95rem; }
.rs-edu .e-d { margin-top: 0.3rem; color: #94A1BA; font-size: 0.85rem; line-height: 1.5; }
.st-key-rates_controls { padding: 0.3rem 1.2rem 1rem; border-radius: 20px; border: 1px solid rgba(148, 170, 210, 0.14);
    background: linear-gradient(180deg, rgba(18, 26, 43, 0.85), rgba(14, 21, 38, 0.7)); margin-bottom: 0.8rem; }
.st-key-rates_controls .dpst-label { margin-top: 0.9rem; }
.st-key-rates_controls [data-baseweb="tag"] { background: rgba(106, 168, 255, 0.16) !important; border: 1px solid rgba(106, 168, 255, 0.35); border-radius: 8px !important; }
.st-key-rates_kpis [data-testid="stMetricValue"] { font-size: 1.7rem; }
.rs-table { max-height: 420px; }
.rs-table td.num, .rs-table th.num { text-align: right; font-family: 'Geist Mono', ui-monospace, monospace; font-variant-numeric: tabular-nums; }
.rs-table tbody tr { cursor: default; }
@media (max-width: 1000px) { .rs-edus { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .rs-edus { grid-template-columns: minmax(0, 1fr); } .rs-nokey { flex-direction: column; } }

/* El componente invisible que carga los efectos no debe ocupar espacio. */
[data-testid="stElementContainer"]:has(> iframe[title="st.iframe"][height="0"]),
[data-testid="stElementContainer"]:has(iframe[height="0"]) { display: none; }

@media (prefers-reduced-motion: reduce) {
    [data-testid="stMainBlockContainer"] * { animation: none !important; }
}
</style>
"""

_FX_JS = r"""
<script>
(function () {
  let P, D;
  try { P = window.parent; D = P.document; if (!D.body) return; } catch (e) { return; }
  const ITEMS = __ITEMS__;
  if (P.__dpstFx) { P.__dpstFx.items = ITEMS; return; }
  const fx = P.__dpstFx = { items: ITEMS };
  const reduce = P.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const isMac = /Mac|iPhone|iPad/.test(P.navigator.platform || P.navigator.userAgent);

  /* ---------- estilos de los elementos propios ---------- */
  const css = D.createElement('style');
  css.textContent = `
  #dpst-progress{position:fixed;top:0;left:0;height:2px;width:100%;z-index:1000002;pointer-events:none;
    transform-origin:0 50%;transform:scaleX(0);background:linear-gradient(90deg,#22A883,#6FE3C1,#6AA8FF);
    box-shadow:0 0 12px rgba(52,201,160,.6)}
  #dpst-k{position:fixed;z-index:1000001;right:calc(18px + env(safe-area-inset-right,0px));bottom:calc(18px + env(safe-area-inset-bottom,0px));
    display:flex;align-items:center;gap:10px;padding:10px 14px 10px 12px;border-radius:999px;cursor:pointer;
    font:500 13px Geist,Inter,system-ui,sans-serif;color:#E8EDF6;background:rgba(18,26,43,.78);
    border:1px solid rgba(148,170,210,.18);backdrop-filter:blur(16px) saturate(160%);-webkit-backdrop-filter:blur(16px) saturate(160%);
    box-shadow:0 12px 32px rgba(0,0,0,.35);transition:transform .25s cubic-bezier(.2,.8,.2,1),border-color .25s}
  #dpst-k:hover{transform:translateY(-2px);border-color:rgba(52,201,160,.5)}
  #dpst-k:active{transform:scale(.96);transition:transform 100ms ease-out}
  #dpst-k kbd{font:500 11px "Geist Mono",ui-monospace,monospace;padding:3px 7px;border-radius:6px;color:#BDEFDF;
    background:rgba(52,201,160,.12);border:1px solid rgba(52,201,160,.35)}
  #dpst-k svg{width:16px;height:16px}
  #dpst-cmd{position:fixed;inset:0;z-index:1000003;display:none;align-items:flex-start;justify-content:center;
    padding:12vh 16px 16px;background:rgba(5,8,16,.55);backdrop-filter:blur(6px);-webkit-backdrop-filter:blur(6px)}
  #dpst-cmd.open{display:flex}
  #dpst-cmd .box{width:min(620px,100%);border-radius:18px;overflow:hidden;background:rgba(14,21,38,.92);
    border:1px solid rgba(148,170,210,.18);box-shadow:0 30px 80px rgba(0,0,0,.55),inset 0 1px 0 rgba(255,255,255,.05);
    backdrop-filter:blur(24px) saturate(170%);-webkit-backdrop-filter:blur(24px) saturate(170%);will-change:transform,opacity,filter}
  #dpst-cmd .in{display:flex;align-items:center;gap:12px;padding:16px 18px;border-bottom:1px solid rgba(148,170,210,.12)}
  #dpst-cmd .in svg{width:18px;height:18px;flex:none;color:#8C99B3}
  #dpst-cmd input{flex:1;min-width:0;background:transparent;border:0;outline:0;color:#E8EDF6;font:400 16px Geist,Inter,system-ui,sans-serif}
  #dpst-cmd input::placeholder{color:#8C99B3}
  #dpst-cmd ul{list-style:none;margin:0;padding:8px;max-height:min(52vh,420px);overflow:auto}
  #dpst-cmd .grp{padding:10px 12px 6px;font:500 11px "Geist Mono",ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#8C99B3}
  #dpst-cmd li.it{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:11px 12px;border-radius:10px;
    cursor:pointer;color:#C6D0E2;font:500 14px Geist,Inter,system-ui,sans-serif}
  #dpst-cmd li.it .h{font:400 12px Geist,Inter,system-ui,sans-serif;color:#8C99B3}
  #dpst-cmd li.it.on{background:rgba(52,201,160,.14);color:#E8EDF6;box-shadow:inset 0 0 0 1px rgba(52,201,160,.3)}
  #dpst-cmd li.it.on .h{color:#BDEFDF}
  #dpst-cmd li.it .here{font:500 11px "Geist Mono",ui-monospace,monospace;letter-spacing:.08em;padding:2px 8px;border-radius:999px;
    color:#BDEFDF;background:rgba(52,201,160,.12);border:1px solid rgba(52,201,160,.35)}
  #dpst-cmd .empty{padding:22px 12px;color:#8C99B3;font:400 14px Geist,Inter,system-ui,sans-serif}
  #dpst-cmd .ft{display:flex;gap:16px;padding:10px 16px;border-top:1px solid rgba(148,170,210,.12);
    font:400 12px Geist,Inter,system-ui,sans-serif;color:#8C99B3}
  #dpst-cmd .ft kbd{font:500 11px "Geist Mono",ui-monospace,monospace;padding:2px 6px;border-radius:5px;
    border:1px solid rgba(148,170,210,.22);color:#C6D0E2;margin-right:4px}
  .dpst-cursor{position:absolute;z-index:3;pointer-events:none;opacity:0;transition:opacity .2s}
  .dpst-cursor .v{position:absolute;top:0;bottom:0;width:1px;left:0;background:linear-gradient(180deg,transparent,rgba(111,227,193,.5),transparent)}
  .dpst-cursor .d{position:absolute;width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:50%;background:#BDEFDF;
    box-shadow:0 0 0 5px rgba(52,201,160,.22),0 0 18px rgba(52,201,160,.8)}
  .dpst-hero:hover .dpst-cursor{opacity:1}
  @media (max-width:640px),(hover:none){#dpst-k kbd{display:none}}
  @media (prefers-reduced-transparency:reduce){#dpst-k,#dpst-cmd .box{background:#121A2B;backdrop-filter:none;-webkit-backdrop-filter:none}
    #dpst-cmd{background:rgba(5,8,16,.88);backdrop-filter:none;-webkit-backdrop-filter:none}}
  @media (prefers-contrast:more){#dpst-k,#dpst-cmd .box{border-color:rgba(232,237,246,.6)}#dpst-cmd li.it .h{color:#C6D0E2}}
  `;
  D.head.appendChild(css);

  /* ---------- barra de progreso de scroll ---------- */
  const bar = D.createElement('div'); bar.id = 'dpst-progress'; D.body.appendChild(bar);
  function progress() {
    const m = D.querySelector('[data-testid="stMain"]') || D.scrollingElement;
    if (!m) return;
    const max = m.scrollHeight - m.clientHeight;
    bar.style.transform = 'scaleX(' + (max > 0 ? Math.min(1, m.scrollTop / max) : 0) + ')';
  }
  D.addEventListener('scroll', progress, { capture: true, passive: true });

  /* ---------- brillo que sigue al cursor ---------- */
  const GLOW = '.dpst-card,[data-testid="stMetric"],[data-testid="stPlotlyChart"],[data-testid="stExpander"] details';
  let last = null;
  D.addEventListener('pointermove', function (e) {
    const t = e.target && e.target.closest ? e.target.closest(GLOW) : null;
    if (t) {
      const r = t.getBoundingClientRect();
      t.style.setProperty('--mx', (e.clientX - r.left) + 'px');
      t.style.setProperty('--my', (e.clientY - r.top) + 'px');
    }
    if (last && last !== t) { last.style.removeProperty('--mx'); last.style.removeProperty('--my'); }
    last = t;
    magnet(e); heroCursor(e);
  }, { passive: true });

  /* ---------- resortes (guía de Apple: damping ratio + response, sin duración fija) ----------
     stiffness = (2π / response)²,  damping = 4π·ζ / response  (masa 1). Cada canal (x, y, escala)
     es un resorte independiente y siempre parte del valor y la velocidad actuales, así que
     cualquier movimiento se puede interrumpir y redirigir sin saltos. */
  function Spring(value, zeta, response) {
    this.v = value; this.t = value; this.vel = 0;
    this.k = Math.pow(2 * Math.PI / response, 2); this.c = 4 * Math.PI * zeta / response;
  }
  Spring.prototype.step = function (dt) {
    // Subpasos de 1/600 s: con un paso grande la integración se vuelve inestable y "explota".
    const n = Math.max(1, Math.ceil(dt * 600)), h = dt / n;
    for (let i = 0; i < n; i++) {
      const a = -this.k * (this.v - this.t) - this.c * this.vel;
      this.vel += a * h; this.v += this.vel * h;
    }
    if (Math.abs(this.v - this.t) < 0.001 && Math.abs(this.vel) < 0.01) { this.v = this.t; this.vel = 0; return false; }
    return true;
  };
  const bodies = new Map();
  let rafOn = false, lastT = 0;
  function body(el) {
    let b = bodies.get(el);
    if (!b) { b = { x: new Spring(0, 1, 0.35), y: new Spring(0, 1, 0.35), s: new Spring(1, 1, 0.16) }; bodies.set(el, b); }
    return b;
  }
  function tick(now) {
    const dt = Math.min(0.032, (now - (lastT || now)) / 1000 || 0.016); lastT = now;
    let alive = false;
    bodies.forEach((b, el) => {
      const m1 = b.x.step(dt), m2 = b.y.step(dt), m3 = b.s.step(dt);
      if (!el.isConnected) { bodies.delete(el); return; }
      const rest = !m1 && !m2 && !m3 && b.x.v === 0 && b.y.v === 0 && b.s.v === 1;
      el.style.transform = rest ? '' : 'translate(' + b.x.v.toFixed(2) + 'px,' + b.y.v.toFixed(2) + 'px) scale(' + b.s.v.toFixed(4) + ')';
      if (m1 || m2 || m3) alive = true; else if (rest) bodies.delete(el);
    });
    if (alive) requestAnimationFrame(tick); else { rafOn = false; lastT = 0; }
  }
  const raf = P.requestAnimationFrame.bind(P);
  function requestAnimationFrame(cb) { return raf(cb); }
  function kick() { if (!rafOn) { rafOn = true; requestAnimationFrame(tick); } }

  /* ---------- botones principales: magnéticos y con respuesta al presionar ---------- */
  const PRIMARY = '[data-testid="stBaseButton-primary"]';
  let magEl = null;
  function magnet(e) {
    if (reduce || e.pointerType === 'touch') return;
    const btn = e.target && e.target.closest ? e.target.closest(PRIMARY) : null;
    if (magEl && magEl !== btn) { const o = body(magEl); o.x.t = 0; o.y.t = 0; o.s.t = 1; kick(); magEl = null; }
    if (!btn || btn.disabled) return;
    const r = btn.getBoundingClientRect(), o = body(btn);
    o.x.t = (e.clientX - r.left - r.width / 2) / r.width * 8;
    o.y.t = (e.clientY - r.top - r.height / 2) / r.height * 6;
    magEl = btn; kick();
  }
  D.addEventListener('pointerdown', e => {
    const btn = e.target && e.target.closest ? e.target.closest(PRIMARY) : null;
    if (!btn || btn.disabled) return;
    const o = body(btn); o.s.t = 0.96; kick();   // feedback en el instante del toque
  }, { passive: true });
  function release() { bodies.forEach(o => { o.s.t = 1; }); kick(); }
  D.addEventListener('pointerup', release, { passive: true });
  D.addEventListener('pointercancel', release, { passive: true });

  /* ---------- punto que sigue al mouse en la línea de la portada ---------- */
  function heroCursor(e) {
    const hero = e.target && e.target.closest ? e.target.closest('.dpst-hero') : null;
    if (!hero) return;
    const svg = hero.querySelector('svg.spark'), path = svg && svg.querySelector('path.line');
    if (!path) return;
    let cur = hero.querySelector('.dpst-cursor');
    if (!cur) { cur = D.createElement('div'); cur.className = 'dpst-cursor'; cur.innerHTML = '<div class="v"></div><div class="d"></div>'; hero.appendChild(cur); }
    const sr = svg.getBoundingClientRect(), hr = hero.getBoundingClientRect();
    const vb = svg.viewBox.baseVal, fx = (e.clientX - sr.left) / sr.width;
    if (fx < 0 || fx > 1) { cur.style.opacity = '0'; return; }
    cur.style.opacity = '';
    const target = fx * vb.width, L = path.getTotalLength();
    let lo = 0, hi = L, pt = path.getPointAtLength(0);
    for (let i = 0; i < 22; i++) { const mid = (lo + hi) / 2; pt = path.getPointAtLength(mid); if (pt.x < target) lo = mid; else hi = mid; }
    const x = sr.left - hr.left + (pt.x / vb.width) * sr.width, y = sr.top - hr.top + (pt.y / vb.height) * sr.height;
    cur.style.left = x + 'px'; cur.style.top = (sr.top - hr.top) + 'px'; cur.style.height = sr.height + 'px';
    cur.querySelector('.d').style.top = (y - (sr.top - hr.top)) + 'px';
  }

  /* ---------- accesos directos de Inicio: [data-dpst-go="Pestaña"] (+ data-dpst-open="Desplegable") ---------- */
  D.addEventListener('click', e => {
    const a = e.target && e.target.closest ? e.target.closest('[data-dpst-go]') : null;
    if (!a) return;
    e.preventDefault();
    const top = clickTab('.st-key-dpst_nav', a.dataset.dpstGo);
    const m = D.querySelector('[data-testid="stMain"]');
    if (m) m.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    const want = a.dataset.dpstOpen;
    if (top && want) setTimeout(() => {
      // El texto del resumen incluye el nombre del ícono de la flecha; se busca el título
      // dentro de él y, si hay varios, el más corto (p. ej. «Pronóstico» antes que «Pronóstico por canasta…»).
      const label = x => { const p = x.querySelector('[data-testid="stMarkdownContainer"]'); return (p ? p.textContent : x.textContent).trim(); };
      const sum = [...D.querySelectorAll('[data-testid="stExpander"] summary')]
        .filter(x => x.offsetParent !== null && label(x).startsWith(want))
        .sort((a, b) => label(a).length - label(b).length)[0];
      if (!sum) return;
      const det = sum.closest('details'); if (det && !det.open) sum.click();
      setTimeout(() => sum.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' }), 250);
    }, 400);
  });

  /* ---------- Tickers: ordenar la tabla y elegir una empresa con clic en la fila ----------
     Ordenar es solo visual (reordena las filas ya mostradas). El clic en una fila escribe esa
     empresa en la lista «Escoge una empresa» —el mismo control de siempre—, así la selección
     y el botón «Usar … en Preselección» funcionan exactamente igual que antes. */
  D.addEventListener('click', e => {
    const th = e.target && e.target.closest ? e.target.closest('.tk-table th[data-sort]') : null;
    if (th) {
      const tbody = th.closest('table').querySelector('tbody'), col = +th.dataset.sort;
      const dir = th.dataset.dir === 'asc' ? 'desc' : 'asc';
      th.closest('tr').querySelectorAll('th').forEach(x => delete x.dataset.dir); th.dataset.dir = dir;
      const rows = [...tbody.rows], val = r => (r.cells[col] ? r.cells[col].textContent.trim() : '');
      rows.sort((a, b) => val(a).localeCompare(val(b), 'es', { numeric: true }) * (dir === 'asc' ? 1 : -1));
      rows.forEach(r => { r.style.animation = 'none'; tbody.appendChild(r); });
      return;
    }
    const tr = e.target && e.target.closest ? e.target.closest('.tk-table tbody tr[data-t]') : null;
    if (!tr) return;
    const box = D.querySelector('.st-key-ticker_pick input');
    if (!box) return;
    const want = tr.dataset.t + ' — ';
    tr.closest('tbody').querySelectorAll('tr.on').forEach(x => x.classList.remove('on')); tr.classList.add('on');
    box.focus(); box.click();
    const setter = Object.getOwnPropertyDescriptor(P.HTMLInputElement.prototype, 'value').set;
    setter.call(box, tr.dataset.t); box.dispatchEvent(new P.Event('input', { bubbles: true }));
    let tries = 0;
    (function pick() {
      const opt = [...D.querySelectorAll('[role="option"]')].find(o => o.textContent.trim().startsWith(want));
      if (opt) { opt.click(); box.blur(); return; }
      if (++tries < 15) setTimeout(pick, 60);
    })();
  });

  /* ---------- Preselección: «Abrir un módulo a la vez» (apagado por defecto) ----------
     Al abrir un módulo, cierra los demás módulos principales con su propio clic (el mismo que
     haría el usuario); los desplegables internos de cada módulo no se tocan. */
  let psFocus = false;
  try { psFocus = P.localStorage.getItem('dpst_ps_focus') === '1'; } catch (err) {}
  const syncFocusBtn = () => D.querySelectorAll('[data-ps-focus]').forEach(b => b.setAttribute('aria-pressed', psFocus ? 'true' : 'false'));
  D.addEventListener('click', e => {
    const b = e.target && e.target.closest ? e.target.closest('[data-ps-focus]') : null;
    if (!b) return;
    psFocus = !psFocus; syncFocusBtn();
    try { P.localStorage.setItem('dpst_ps_focus', psFocus ? '1' : '0'); } catch (err) {}
  });
  const topModules = () => [...D.querySelectorAll('.st-key-ps_modules [data-testid="stExpander"] > details')]
    .filter(d => !d.parentElement.parentElement.closest('[data-testid="stExpander"]'));
  D.addEventListener('toggle', e => {
    const det = e.target;
    if (!psFocus || !det || det.tagName !== 'DETAILS' || !det.open) return;
    const mods = topModules(); if (!mods.includes(det)) return;
    mods.forEach(o => { if (o !== det && o.open) { const s = o.querySelector(':scope > summary'); if (s) s.click(); } });
  }, true);
  new P.MutationObserver(syncFocusBtn).observe(D.body, { childList: true, subtree: true });
  syncFocusBtn();

  /* ---------- carrusel de noticias de Inicio ----------
     Pasa solo cada N segundos (se pausa con el mouse encima, con el foco dentro, con el botón
     de pausa o si la pestaña no se ve). Se puede arrastrar 1:1 con el dedo o el mouse; al soltar
     se proyecta el impulso (fórmula de Apple, d = 0.998) para elegir la noticia y el resorte
     hereda la velocidad del gesto. En los bordes hay resistencia progresiva (rubber-band). */
  const NEWS = new Set();
  function rubber(over, dim) { const c = 0.55; return (over * dim * c) / (dim + c * Math.abs(over)); }
  function initNews(root) {
    if (root.__nv) return;
    const stage = root.querySelector('.nv-stage'), track = root.querySelector('.nv-track');
    const slides = [...root.querySelectorAll('.nv-slide')], rows = [...root.querySelectorAll('.nv-row')];
    const pips = [...root.querySelectorAll('.nv-pip')];
    const n = slides.length; if (!n || !stage || !track) return;
    const count = root.querySelector('.nv-count b'), prog = root.querySelector('.nv-progress i'), list = root.querySelector('.nv-list');
    const playBtn = root.querySelector('[data-play]');
    const s = root.__nv = { i: 0, x: new Spring(0, 1, 0.45), elapsed: 0, dur: +root.dataset.autoplay || 7000,
                            paused: false, hover: false, focus: false, drag: null, seen: true };
    const W = () => stage.clientWidth || 1;
    s.paint = () => { track.style.transform = 'translate3d(' + s.x.v.toFixed(2) + 'px,0,0)'; };
    function syncList() {
      const li = rows[s.i] && rows[s.i].parentElement; if (!li || !list) return;
      const horizontal = list.scrollWidth > list.clientWidth + 4 && getComputedStyle(list).flexDirection === 'row';
      if (horizontal) {
        if (li.offsetLeft < list.scrollLeft || li.offsetLeft + li.offsetWidth > list.scrollLeft + list.clientWidth)
          list.scrollTo({ left: li.offsetLeft - 6, behavior: reduce ? 'auto' : 'smooth' });
      } else if (li.offsetTop < list.scrollTop || li.offsetTop + li.offsetHeight > list.scrollTop + list.clientHeight) {
        list.scrollTo({ top: li.offsetTop - 6, behavior: reduce ? 'auto' : 'smooth' });
      }
    }
    s.go = (i, vel) => {
      s.i = ((i % n) + n) % n; s.elapsed = 0; s.x.t = -s.i * W();
      if (vel != null) s.x.vel = vel;
      if (reduce) { s.x.v = s.x.t; s.x.vel = 0; s.paint(); track.animate([{ opacity: 0.35 }, { opacity: 1 }], { duration: 220 }); }
      slides.forEach((el, k) => { if (k === s.i) el.removeAttribute('aria-hidden'); else el.setAttribute('aria-hidden', 'true'); });
      rows.forEach((el, k) => el.classList.toggle('on', k === s.i));
      pips.forEach((el, k) => { el.classList.toggle('on', k === s.i); el.setAttribute('aria-current', k === s.i ? 'true' : 'false'); });
      if (count) count.textContent = String(s.i + 1).padStart(2, '0');
      root.dataset.tone = String(s.i % 3);
      syncList();
    };
    root.addEventListener('click', e => {
      const go = e.target.closest('[data-go]'), nav = e.target.closest('[data-nav]'), play = e.target.closest('[data-play]');
      if (go || nav) s.hold = performance.now() + 9000;   // tras elegir a mano, espera antes de seguir solo
      if (go) s.go(+go.dataset.go);
      else if (nav) s.go(s.i + (+nav.dataset.nav));
      else if (play) {
        s.paused = !s.paused; root.classList.toggle('paused', s.paused);
        play.setAttribute('aria-label', s.paused ? 'Reanudar el paso automático' : 'Pausar el paso automático');
      }
    });
    root.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { e.preventDefault(); s.go(s.i + 1); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); s.go(s.i - 1); }
    });
    root.addEventListener('pointerenter', () => { s.hover = true; });
    root.addEventListener('pointerleave', () => { s.hover = false; });
    root.addEventListener('focusin', () => { s.focus = true; });
    root.addEventListener('focusout', e => { if (!root.contains(e.relatedTarget)) s.focus = false; });
    /* arrastre */
    stage.addEventListener('pointerdown', e => {
      if (e.button !== 0 || e.target.closest('.nv-btn')) return;
      s.drag = { id: e.pointerId, x0: e.clientX, y0: e.clientY, start: s.x.v, moved: false, hist: [{ x: e.clientX, t: performance.now() }] };
    });
    stage.addEventListener('pointermove', e => {
      const d = s.drag; if (!d || e.pointerId !== d.id) return;
      const dx = e.clientX - d.x0, dy = e.clientY - d.y0;
      if (!d.moved) {
        if (Math.abs(dx) < 10 || Math.abs(dx) < Math.abs(dy)) { if (Math.abs(dy) > 10) s.drag = null; return; }
        d.moved = true; stage.classList.add('dragging');
        try { stage.setPointerCapture(e.pointerId); } catch (err) {}
      }
      const min = -(n - 1) * W(); let x = d.start + dx;
      if (x > 0) x = rubber(x, W()); else if (x < min) x = min + rubber(x - min, W());
      s.x.v = s.x.t = x; s.x.vel = 0; s.paint();
      d.hist.push({ x: e.clientX, t: performance.now() }); if (d.hist.length > 6) d.hist.shift();
    });
    function endDrag(e) {
      const d = s.drag; if (!d || (e && e.pointerId !== d.id)) return;
      s.drag = null; stage.classList.remove('dragging');
      if (!d.moved) return;
      const a = d.hist[0], b = d.hist[d.hist.length - 1], dt = Math.max(1, b.t - a.t);
      const vel = (b.x - a.x) / dt * 1000;                                  // px/s
      const projected = s.x.v + (vel / 1000) * 0.998 / (1 - 0.998);        // dónde iba a parar
      const idx = Math.max(0, Math.min(n - 1, Math.round(-projected / W())));
      s.go(idx, vel);
      stage.addEventListener('click', ev => { ev.preventDefault(); ev.stopPropagation(); }, { capture: true, once: true });
    }
    stage.addEventListener('pointerup', endDrag);
    stage.addEventListener('pointercancel', endDrag);
    if (P.ResizeObserver) new P.ResizeObserver(() => { s.x.v = s.x.t = -s.i * W(); s.x.vel = 0; s.paint(); syncList(); }).observe(stage);
    if (P.IntersectionObserver) new P.IntersectionObserver(es => { s.seen = es[0].isIntersecting; }).observe(root);
    NEWS.add(root); s.go(0); s.x.v = s.x.t; s.paint();
    if (!newsOn) { newsOn = true; raf(newsTick); }
  }
  let newsOn = false, newsLast = 0;
  function newsTick(now) {
    const dt = Math.min(0.05, (now - (newsLast || now)) / 1000); newsLast = now;
    NEWS.forEach(root => {
      if (!root.isConnected) { NEWS.delete(root); return; }
      const s = root.__nv;
      if (!s.drag && s.x.step(dt)) s.paint();
      const visible = s.seen && root.offsetParent !== null && !D.hidden;
      if (visible && !s.paused && !s.hover && !s.focus && !s.drag && !(s.hold && now < s.hold)) {
        s.elapsed += dt * 1000;
        if (s.elapsed >= s.dur) s.go(s.i + 1);
      }
      const p = Math.min(1, s.elapsed / s.dur), sc = 'scaleX(' + p.toFixed(4) + ')';
      const bar = root.querySelector('.nv-progress i'); if (bar) bar.style.transform = sc;
      const rb = root.querySelector('.nv-row.on .nv-bar i'); if (rb) rb.style.transform = sc;
    });
    if (NEWS.size) raf(newsTick); else { newsOn = false; newsLast = 0; }
  }
  function scanNews() { D.querySelectorAll('.dpst-news').forEach(initNews); }
  let scanT = 0;
  new P.MutationObserver(() => { clearTimeout(scanT); scanT = setTimeout(scanNews, 150); }).observe(D.body, { childList: true, subtree: true });
  scanNews();

  /* ---------- paleta de comandos ---------- */
  const ico = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
  const chip = D.createElement('button'); chip.id = 'dpst-k'; chip.type = 'button';
  chip.setAttribute('aria-label', 'Abrir buscador de secciones');
  chip.innerHTML = ico + '<span>Ir a…</span><kbd>' + (isMac ? '⌘ K' : 'Ctrl K') + '</kbd>';
  D.body.appendChild(chip);
  const ov = D.createElement('div'); ov.id = 'dpst-cmd'; ov.setAttribute('role', 'dialog'); ov.setAttribute('aria-modal', 'true');
  ov.setAttribute('aria-label', 'Buscador de secciones');
  ov.innerHTML = '<div class="box"><div class="in">' + ico + '<input id="dpst-cmd-q" type="text" placeholder="Busca una sección o módulo…" autocomplete="off" aria-label="Buscar sección"></div>'
    + '<ul role="listbox"></ul><div class="ft"><span><kbd>↑↓</kbd>moverse</span><span><kbd>Enter</kbd>abrir</span><span><kbd>Esc</kbd>cerrar</span></div></div>';
  D.body.appendChild(ov);
  const q = ov.querySelector('input'), ul = ov.querySelector('ul');
  let sel = 0, shown = [], hereIdx = -1;

  const norm = s => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  function current() {
    const pick = s => { const a = D.querySelector(s + ' > [data-testid="stTabs"] > div > [role="tablist"] > [role="tab"][aria-selected="true"]'); return a ? a.textContent.trim() : null; };
    return { top: pick('.st-key-dpst_nav'), sub: pick('.st-key-lab_nav') };
  }
  function render() {
    const here = current();
    const term = norm(q.value.trim());
    shown = fx.items.filter(it => !term || norm(it.label + ' ' + it.group + ' ' + (it.hint || '')).includes(term));
    sel = Math.min(sel, Math.max(0, shown.length - 1));
    if (!shown.length) { ul.innerHTML = '<li class="empty">No hay secciones con «' + q.value.replace(/</g, '&lt;') + '». Prueba con otra palabra.</li>'; return; }
    let html = '', g = null; hereIdx = -1;
    shown.forEach((it, i) => {
      if (it.group !== g) { g = it.group; html += '<li class="grp" role="presentation">' + g + '</li>'; }
      const isHere = it.top === here.top && (it.sub ? it.sub === here.sub : true) && !(it.sub == null && here.top && fx.items.some(x => x.sub && x.top === here.top && x.sub === here.sub));
      if (isHere) hereIdx = i;
      const tag = isHere ? '<span class="here">Estás aquí</span>' : '<span class="h">' + (it.hint || '') + '</span>';
      html += '<li class="it' + (i === sel ? ' on' : '') + '" role="option" data-i="' + i + '" aria-selected="' + (i === sel) + '"' + (isHere ? ' aria-current="page"' : '') + '><span>' + it.label + '</span>' + tag + '</li>';
    });
    ul.innerHTML = html;
    const on = ul.querySelector('.on'); if (on) on.scrollIntoView({ block: 'nearest' });
  }
  const box = ov.querySelector('.box');
  let anim = null, scrimAnim = null, state = 'closed';
  function frames() {
    // Apple: los materiales se "materializan" (desenfoque + escala), no solo aparecen; con
    // movimiento reducido, solo un fundido corto.
    return reduce
      ? [[{ opacity: 0 }, { opacity: 1 }], { duration: 140, easing: 'linear', fill: 'both' }]
      : [[{ opacity: 0, transform: 'scale(.9)', filter: 'blur(10px)' }, { opacity: 1, transform: 'none', filter: 'blur(0)' }],
         { duration: 300, easing: 'cubic-bezier(.2,.9,.25,1)', fill: 'both' }];
  }
  function open() {
    if (state === 'open' || state === 'opening') return;
    if (state === 'closing' && anim) {          // interrumpido a mitad del cierre: se revierte desde donde va
      state = 'opening'; anim.reverse(); scrimAnim && scrimAnim.reverse(); q.focus(); return;
    }
    ov.classList.add('open'); q.value = ''; sel = 0; render();
    if (hereIdx > 0) { sel = hereIdx; render(); }   // abre con la sección actual seleccionada
    const c = chip.getBoundingClientRect(), r = box.getBoundingClientRect();   // sale desde el botón que lo abrió
    box.style.transformOrigin = (c.left + c.width / 2 - r.left) + 'px ' + (c.top + c.height / 2 - r.top) + 'px';
    const [kf, opt] = frames();
    anim = box.animate(kf, opt); scrimAnim = ov.animate([{ opacity: 0 }, { opacity: 1 }], { duration: opt.duration, fill: 'both' });
    state = 'opening'; anim.onfinish = () => { if (state === 'opening') state = 'open'; };
    setTimeout(() => q.focus(), 20);
  }
  function close() {
    if (state === 'closed' || state === 'closing' || !anim) { if (!anim) ov.classList.remove('open'); return; }
    state = 'closing'; anim.reverse(); scrimAnim && scrimAnim.reverse();   // mismo camino de vuelta
    anim.onfinish = () => { if (state === 'closing') { state = 'closed'; ov.classList.remove('open'); chip.focus({ preventScroll: true }); } };
  }
  function clickTab(scope, label) {
    const tabs = D.querySelectorAll(scope + ' > [data-testid="stTabs"] > div > [role="tablist"] > [role="tab"]');
    for (const t of tabs) { if (t.textContent.trim() === label) { t.click(); return t; } }
    return null;
  }
  function go(it) {
    close();
    const top = clickTab('.st-key-dpst_nav', it.top);
    if (it.sub) {
      setTimeout(() => {
        const t = clickTab('.st-key-lab_nav', it.sub);
        const box = D.querySelector('.st-key-lab_nav'), m = D.querySelector('[data-testid="stMain"]');
        if (!t || !box || !m) return;
        // Al hacer clic, la pestaña recibe el foco y el navegador la desplaza al borde de la
        // pantalla; además el módulo se monta un instante después. Por eso se coloca la
        // vista unas cuantas veces seguidas hasta que queda estable con los módulos arriba.
        let tries = 0;
        (function settle() {
          const y = box.getBoundingClientRect().top - m.getBoundingClientRect().top + m.scrollTop - 150;
          if (Math.abs(m.scrollTop - y) > 4) m.scrollTo({ top: Math.max(0, y), behavior: 'auto' });
          if (++tries < 6) setTimeout(settle, 180);
        })();
      }, 450);
    } else if (top) {
      const m = D.querySelector('[data-testid="stMain"]'); if (m) m.scrollTo({ top: 0, behavior: reduce ? 'auto' : 'smooth' });
    }
  }
  chip.addEventListener('click', open);
  ov.addEventListener('click', e => { if (e.target === ov) close(); const li = e.target.closest('li.it'); if (li) go(shown[+li.dataset.i]); });
  ul.addEventListener('mousemove', e => { const li = e.target.closest('li.it'); if (li && +li.dataset.i !== sel) { sel = +li.dataset.i; render(); } });
  q.addEventListener('input', () => { sel = 0; render(); });
  q.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(shown.length - 1, sel + 1); render(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); render(); }
    else if (e.key === 'Enter') { e.preventDefault(); if (shown[sel]) go(shown[sel]); }
    else if (e.key === 'Escape') { e.preventDefault(); close(); }
  });
  D.addEventListener('keydown', e => {
    if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); (state === 'open' || state === 'opening') ? close() : open(); }
    else if (e.key === 'Escape' && (state === 'open' || state === 'opening')) close();
  });
})();
</script>
"""


def apply_ui_fx(items: "list[dict]") -> None:
    """
    Inyecta la capa de interacción. `items` son las entradas de la paleta de comandos:
    dicts con `group`, `label`, `top` (texto exacto de la pestaña del menú superior),
    opcionalmente `sub` (texto exacto de la pestaña del laboratorio) y `hint`.
    """
    st.markdown(FX_CSS, unsafe_allow_html=True)
    payload = json.dumps(items, ensure_ascii=False).replace("</", "<\\/")
    components.html(_FX_JS.replace("__ITEMS__", payload), height=0)


NEWS_AUTOPLAY_MS = 7000  # tiempo que se muestra cada noticia antes de pasar a la siguiente


def _safe_link(url: str) -> str:
    url = str(url or "").strip()
    return html.escape(url, quote=True) if url.lower().startswith(("http://", "https://")) else ""


def news_carousel_html(items: "list[dict]", label: str, format_date) -> str:
    """
    Recuadro grande de noticias que pasan solas (carrusel). Usa las mismas noticias ya
    verificadas por la app: título, enlace, medio y fecha, más resumen, imagen y tema
    cuando la fuente los trae (Yahoo Finance y Alpha Vantage). Nada se inventa: si un
    campo no viene, no se muestra. La etiqueta de categoría es la de la fuente o, si no
    trae, la de la pestaña. Sin JavaScript se ve la primera noticia y la lista completa.
    El HTML no lleva líneas en blanco para que Markdown no lo parta.
    """
    slides, rows, dots = [], [], []
    n = len(items)
    tab_label = html.escape(label)
    for i, item in enumerate(items):
        title = html.escape(str(item.get("title", "")).strip() or "Noticia sin título")
        publisher = html.escape(str(item.get("publisher", "")).strip() or "Medio N/D")
        when = html.escape(format_date(item.get("published")))
        link = _safe_link(item.get("link", ""))
        image = _safe_link(item.get("image", ""))
        category = html.escape(str(item.get("category", "") or "").strip()) or tab_label
        summary = " ".join(str(item.get("summary", "") or "").split())
        summary = html.escape(summary[:260].rsplit(" ", 1)[0] + "…" if len(summary) > 260 else summary)
        mono = publisher[:1].upper() if publisher[:1].isalnum() else "N"
        hidden_attr = ' aria-hidden="true"' if i else ""
        cta = (f'<a class="nv-link" href="{link}" target="_blank" rel="noopener noreferrer">'
               f'Leer la noticia completa<span aria-hidden="true">↗</span></a>') if link else ""
        media = (f'<div class="nv-media"><img src="{image}" alt="" loading="lazy" referrerpolicy="no-referrer" '
                 f'onerror="this.closest(\'.nv-media\').remove()"></div>') if image else \
            f'<div class="nv-mono" aria-hidden="true">{mono}</div>'
        slides.append(
            f'<article class="nv-slide{" has-img" if image else ""}" data-i="{i}" aria-roledescription="noticia" '
            f'aria-label="{i + 1} de {n}"{hidden_attr}>{media}<div class="nv-body">'
            f'<div class="nv-meta"><span class="nv-cat">{category}</span><span class="nv-src">{publisher}</span>'
            f'<span class="nv-dot">·</span><span>{when}</span></div>'
            f'<div class="nv-title">{title}</div>'
            + (f'<div class="nv-sum">{summary}</div>' if summary else "")
            + f'{cta}</div></article>'
        )
        rows.append(
            f'<li><button type="button" class="nv-row{" on" if i == 0 else ""}" data-go="{i}" aria-label="Ver noticia {i + 1}: {title}">'
            f'<span class="nv-n">{i + 1:02d}</span><span class="nv-rt">{title}</span>'
            f'<span class="nv-rs">{publisher} · {category}</span><span class="nv-bar"><i></i></span></button></li>'
        )
        dots.append(f'<button type="button" class="nv-pip{" on" if i == 0 else ""}" data-go="{i}" '
                    f'aria-label="Ir a la noticia {i + 1}"></button>')
    controls = (
        '<div class="nv-ui">'
        f'<span class="nv-count"><b>01</b> / {n:02d}</span>'
        f'<span class="nv-pips">{"".join(dots)}</span>'
        '<span class="nv-btns">'
        '<button type="button" class="nv-btn" data-nav="-1" aria-label="Noticia anterior">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m15 18-6-6 6-6"/></svg></button>'
        '<button type="button" class="nv-btn nv-play" data-play aria-label="Pausar el paso automático">'
        '<svg class="i-pause" viewBox="0 0 24 24" fill="currentColor"><rect x="6" y="5" width="4" height="14" rx="1"/><rect x="14" y="5" width="4" height="14" rx="1"/></svg>'
        '<svg class="i-play" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5.5v13l11-6.5z"/></svg></button>'
        '<button type="button" class="nv-btn" data-nav="1" aria-label="Noticia siguiente">'
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="m9 18 6-6-6-6"/></svg></button>'
        '</span></div>'
    )
    return (
        f'<div class="dpst-news" data-autoplay="{NEWS_AUTOPLAY_MS}" tabindex="0" role="region" '
        f'aria-roledescription="carrusel" aria-label="Noticias: {tab_label}">'
        f'<div class="nv-stage"><div class="nv-glow" aria-hidden="true"></div>'
        f'<div class="nv-track">{"".join(slides)}</div>{controls}'
        f'<div class="nv-progress" aria-hidden="true"><i></i></div></div>'
        f'<ol class="nv-list">{"".join(rows)}</ol></div>'
    )


# ---------------------------------------------------------------------------
# Piezas comunes del diseño (mismos íconos, encabezados y estados en todas las pantallas)
# ---------------------------------------------------------------------------

# Íconos de trazo (24 × 24, línea 1.8), dibujados para el bot: mismo grosor y esquinas en todas partes.
ICONS = {
    "home": '<path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/>',
    "search": '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    "tag": '<path d="M20.6 13.4 13.4 20.6a2 2 0 0 1-2.8 0L3 13V3h10l7.6 7.6a2 2 0 0 1 0 2.8z"/><circle cx="7.5" cy="7.5" r="1.5"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m7 14 4-4 3 3 5-6"/>',
    "landmark": '<path d="M3 21h18M5 21v-9m4 9v-9m6 9v-9m4 9v-9M2 10l10-6 10 6z"/>',
    "layers": '<path d="m12 2 10 5-10 5L2 7z"/><path d="m2 17 10 5 10-5"/><path d="m2 12 10 5 10-5"/>',
    "trending": '<path d="m3 17 6-6 4 4 8-8"/><path d="M14 7h7v7"/>',
    "scale": '<path d="M12 3v18M7 21h10M5 7h14M5 7l-3 7a3.5 3.5 0 0 0 6 0zM19 7l-3 7a3.5 3.5 0 0 0 6 0z"/>',
    "basket": '<path d="M3 9h18l-2 11H5z"/><path d="m8 9 4-6 4 6M9 13v4m3-4v4m3-4v4"/>',
    "database": '<ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3"/>',
    "news": '<path d="M4 4h13v16H6a2 2 0 0 1-2-2z"/><path d="M17 8h3v10a2 2 0 0 1-2 2M8 8h5M8 12h5M8 16h3"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/><path d="m9 12 2 2 4-4"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4-6"/>',
    "plug": '<path d="M9 2v5M15 2v5M6 7h12v4a6 6 0 0 1-12 0zM12 17v5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5h.01"/>',
    "arrow": '<path d="M5 12h14M13 6l6 6-6 6"/>',
    "external": '<path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/>',
    "activity": '<path d="M3 12h4l3-8 4 16 3-8h4"/>',
    "alert": '<path d="M12 3 2 21h20z"/><path d="M12 10v5M12 18h.01"/>',
    "curve": '<path d="M3 21C5 12 10 6 21 3"/><circle cx="8" cy="13" r="1.4"/><circle cx="14" cy="7.5" r="1.4"/>',
    "sliders": '<path d="M4 6h10M18 6h2M4 12h3M11 12h9M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="9" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
    "refresh": '<path d="M20 11a8 8 0 0 0-14.5-4.5L4 8M4 3.5V8h4.5M4 13a8 8 0 0 0 14.5 4.5L20 16M20 20.5V16h-4.5"/>',
    "history": '<path d="M3 12a9 9 0 1 0 2.6-6.4L3 8M3 3v5h5M12 7v5l3 2"/>',
    "target": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/>',
    "file": '<path d="M14 3H6a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V8z"/><path d="M14 3v5h5M8 13h8M8 17h6"/>',
    "download": '<path d="M12 3v12M7 10l5 5 5-5M4 21h16"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "calendar": '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
    "globe": '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3.2 3 14.8 0 18M12 3c-3 3.2-3 14.8 0 18"/>',
    "cpu": '<rect x="6" y="6" width="12" height="12" rx="2"/><path d="M10 10h4v4h-4zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4"/>',
    "wallet": '<path d="M3 7a2 2 0 0 1 2-2h13v4"/><path d="M3 7v11a2 2 0 0 0 2 2h15V9H5a2 2 0 0 1-2-2z"/><circle cx="16" cy="14.5" r="1.2"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "key": '<circle cx="7.5" cy="15.5" r="4.5"/><path d="m10.7 12.3 9.3-9.3M17 6l3 3M14.5 8.5l2 2"/>',
    "check": '<path d="m5 12 4 4 10-10"/>',
    "lock": '<rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/>',
}


def icon(name: str, size: int = 18, cls: str = "dpst-ico") -> str:
    """SVG en línea de ICONS; hereda el color del texto (currentColor)."""
    body = ICONS.get(name, ICONS["info"])
    return (f'<svg class="{cls}" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{body}</svg>')


def page_header_html(eyebrow: str, title: str, subtitle: str, icon_name: str) -> str:
    """Encabezado común de cada pantalla: etiqueta con ícono, título serif y subtítulo."""
    return (f'<div class="dpst-ph"><div class="dpst-eyebrow">{icon(icon_name, 15)}<span>{html.escape(eyebrow)}</span></div>'
            f'<div class="dpst-page-title">{html.escape(title)}</div>'
            f'<div class="dpst-page-sub">{html.escape(subtitle)}</div></div>')


def section_label_html(text: str, icon_name: str) -> str:
    """Rótulo pequeño en mayúsculas con ícono, para separar bloques dentro de una pantalla."""
    return f'<div class="dpst-label">{icon(icon_name, 14)}<span>{html.escape(text)}</span></div>'


def empty_state_html(icon_name: str, title: str, body_html: str, tone: str = "info") -> str:
    """Estado vacío o aviso de conexión con ícono, título y texto (el texto lo pone la app, ya escapado)."""
    return (f'<div class="dpst-empty {tone}"><div class="ic">{icon(icon_name, 22)}</div>'
            f'<div class="tx"><div class="t">{html.escape(title)}</div><div class="b">{body_html}</div></div></div>')
