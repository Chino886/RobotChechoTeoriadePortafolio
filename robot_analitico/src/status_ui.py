"""
Estados de carga, conexión, actualización, error y vacío (solo presentación).

Los estados de conexión se anotan SOLO a partir de operaciones que la app ya hace (descargar un
activo, comparar, pedir una tasa a FRED, buscar noticias, probar conexiones). Aquí no se hace
ninguna llamada de red. Un servicio que no se ha usado en la sesión queda «Sin verificar».
Los detalles técnicos de los fallos van al registro (logging «dpst»), no a la pantalla.
"""
from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from html import escape
from typing import Optional

import streamlit as st

from src.ui_fx import icon

log = logging.getLogger("dpst")
STATE_KEY = "dpst_conn_state"

# estado → (texto, tono, ícono)
STATES = {
    "ok": ("Conectado", "good", "check"),
    "loading": ("Consultando", "info", "refresh"),
    "refreshing": ("Actualizando", "info", "refresh"),
    "offline": ("Sin conexión", "bad", "plug"),
    "error": ("Error", "bad", "alert"),
    "nodata": ("Datos no disponibles", "warn", "info"),
    "nokey": ("Falta configuración", "warn", "key"),
    "unverified": ("Sin verificar", "neutral", "clock"),
}
# servicio → (nombre visible, fuente, módulo donde se usa)
SERVICES = {
    "yahoo_hist": ("Yahoo Finance · históricos", "Yahoo Finance (yfinance)", "Preselección y Comparación"),
    "yahoo_quote": ("Yahoo Finance · cotización", "Yahoo Finance (1 minuto)", "Laboratorio · Cotización en línea"),
    "fred": ("FRED · tasas", "FRED (Reserva Federal de St. Louis)", "Tasas soberanas"),
    "google_news": ("Google News · RSS", "Google News", "Inicio · Noticias"),
    "alpha_vantage": ("Alpha Vantage · noticias", "Alpha Vantage", "Inicio · Noticias"),
    "yahoo_news": ("Yahoo Finance · noticias", "Yahoo Finance", "Inicio · Noticias de la empresa"),
    "nasdaq": ("NASDAQ Trader · directorio", "NASDAQ Trader", "Tickers"),
}
# nombres de la prueba «Comprobar conexiones reales» → servicio
CHECK_NAMES = {"Yahoo Finance · cotización (1 min)": "yahoo_quote", "Yahoo Finance · históricos": "yahoo_hist",
               "FRED · tasas": "fred", "Google News · RSS": "google_news", "Alpha Vantage · noticias": "alpha_vantage"}

_OFFLINE_HINTS = ("timeout", "timed out", "connection", "conexión", "resolve", "max retries", "proxy", "network",
                  "unreachable", "ssl", "curl: (", "tunnel", "failed to perform", "name or service", "temporarily")
_NODATA_HINTS = ("vacía", "vacia", "sin datos", "empty", "no data", "sin resultados", "inexistente", "no encontr")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def classify(detail: str) -> str:
    """Tipo de fallo a partir del mensaje original (que se conserva en el registro)."""
    d = (detail or "").lower()
    if any(h in d for h in _NODATA_HINTS):
        return "nodata"
    if any(h in d for h in _OFFLINE_HINTS):
        return "offline"
    if "api key" in d or "api_key" in d or "clave" in d:
        return "nokey"
    return "error"


def set_state(state, service: str, status: str, detail: str = "", when: Optional[str] = None) -> None:
    reg = dict(state.get(STATE_KEY) or {})
    prev = reg.get(service, {})
    reg[service] = {"status": status, "detail": detail, "when": when or now_utc(),
                    "last_ok": (when or now_utc()) if status == "ok" else prev.get("last_ok")}
    state[STATE_KEY] = reg


def sync_from_checks(state, log_rows: "list[dict]") -> None:
    """La prueba real de conexiones es la evidencia más fuerte: su último resultado manda."""
    seen = {}
    for r in log_rows or []:
        key = CHECK_NAMES.get(r.get("servicio"))
        if key:
            seen[key] = r
    for key, r in seen.items():
        ok = r.get("estado") == "conectado"
        cur = (state.get(STATE_KEY) or {}).get(key, {})
        when = str(r.get("hora (UTC)", ""))[:16] + " UTC"
        if cur.get("when", "") <= when:
            set_state(state, key, "ok" if ok else classify(str(r.get("detalle", ""))), str(r.get("detalle", "")), when)


def get_state(state, service: str) -> dict:
    return (state.get(STATE_KEY) or {}).get(service) or {"status": "unverified", "detail": "", "when": ""}


# ---------------------------------------------------------------------------
# Componentes visuales
# ---------------------------------------------------------------------------
def pill_html(status: str, extra: str = "") -> str:
    text, tone, ic = STATES.get(status, STATES["unverified"])
    return (f'<span class="ds-pill {tone}{" spin" if status in ("loading", "refreshing") else ""}">{icon(ic, 12)}'
            f'{escape(text)}{(" · " + escape(extra)) if extra else ""}</span>')


def skeleton_html(kind: str = "chart", label: str = "") -> str:
    """Esqueleto animado mientras se consulta (no muestra cifras)."""
    if kind == "table":
        body = '<div class="sk-row head"></div>' + "".join('<div class="sk-row"></div>' for _ in range(6))
    elif kind == "cards":
        body = '<div class="sk-cards">' + "".join('<div class="sk-card"><i></i><b></b><s></s></div>' for _ in range(4)) + "</div>"
    elif kind == "news":
        body = '<div class="sk-news"><div class="sk-img"></div><div class="sk-lines"><b></b><s></s><s></s><s class="short"></s></div></div>'
    else:  # chart / resultados
        body = ('<div class="sk-chart"><div class="sk-title"></div><svg viewBox="0 0 400 120" preserveAspectRatio="none">'
                '<path d="M0 95 C 40 80, 70 88, 110 70 S 170 40, 210 55 S 290 30, 330 38 S 380 20, 400 24" /></svg></div>')
    lab = (f'<div class="sk-label">{icon("refresh", 14)}<span>{escape(label)}</span>'
           '<span class="sk-dots"><i></i><i></i><i></i></span></div>') if label else ""
    return f'<div class="dpst-skel {kind}" role="status" aria-live="polite">{lab}{body}</div>'


@contextmanager
def loading(kind: str, label: str, service: Optional[str] = None):
    """Muestra un esqueleto mientras corre el bloque (la misma consulta de siempre) y lo quita al terminar."""
    ph = st.empty()
    if service:
        cur = get_state(st.session_state, service)
        set_state(st.session_state, service, "refreshing" if cur.get("status") == "ok" else "loading", label)
    ph.markdown(skeleton_html(kind, label), unsafe_allow_html=True)
    try:
        yield ph
    finally:
        ph.empty()


def error_card_html(module: str, what: str, missing: str, action: str, tone: str = "error",
                    action_html: str = "") -> str:
    """Mensaje de error claro: qué pasó, en qué módulo, qué faltó y qué hacer."""
    ic = {"error": "alert", "warn": "info", "offline": "plug"}.get(tone, "alert")
    return (
        f'<div class="ds-err {tone}" role="alert"><div class="de-ic">{icon(ic, 18)}</div><div class="de-b">'
        f'<div class="de-t">{escape(what)}</div>'
        f'<div class="de-m"><span>Módulo</span>{escape(module)}</div>'
        f'<div class="de-m"><span>No se cargó</span>{escape(missing)}</div>'
        f'<div class="de-a">{icon("arrow", 13)}<span>{escape(action)}</span></div>{action_html}</div></div>'
    )


def show_error(module: str, what: str, missing: str, action: str, technical: str = "", tone: str = "error",
               action_html: str = "") -> None:
    if technical:
        log.warning("[%s] %s | %s", module, what, technical)  # el detalle técnico queda en el registro
    st.markdown(error_card_html(module, what, missing, action, tone, action_html), unsafe_allow_html=True)


def fetch_error(module: str, what: str, missing: str, technical: str, service: Optional[str] = None,
                nodata_action: str = "", offline_action: str = "Revisa tu conexión a internet y vuelve a intentarlo en unos minutos.",
                other_action: str = "Vuelve a intentarlo; si sigue fallando, avisa al equipo (el detalle quedó en el registro).") -> str:
    """Muestra el error de una consulta según su tipo y actualiza el estado del servicio. Devuelve el tipo."""
    kind = classify(technical)
    if service:
        set_state(st.session_state, service, kind, technical)
    action = {"nodata": nodata_action or "Revisa los datos de entrada (ticker, fechas) y vuelve a consultar.",
              "offline": offline_action, "nokey": "Configura la clave de API en los secretos de la app."}.get(kind, other_action)
    show_error(module, what, missing, action, technical, "warn" if kind == "nodata" else
               ("offline" if kind == "offline" else "error"))
    return kind


def data_stamp_html(source: str, consulted: str, last_data: str = "", status: str = "ok", extra: str = "") -> str:
    """Franja de actualización: fuente, fecha de consulta, último dato y estado."""
    cells = [("Fuente", source), ("Consultado", consulted or "—")]
    if last_data:
        cells.append(("Último dato", last_data))
    if extra:
        cells.append(("Detalle", extra))
    return ('<div class="ds-stamp">' + pill_html(status) + "".join(
        f'<span class="dst"><b>{escape(k)}</b>{escape(v)}</span>' for k, v in cells) + "</div>")


def status_center_html(state) -> str:
    """Pastilla fija con el resumen de conexiones y su panel con el detalle de cada servicio."""
    rows, counts = [], {"good": 0, "bad": 0, "warn": 0}
    for key, (name, source, module) in SERVICES.items():
        s = get_state(state, key)
        status = s.get("status", "unverified")
        tone = STATES.get(status, STATES["unverified"])[1]
        counts[tone] = counts.get(tone, 0) + 1
        when = s.get("when") or ""
        note = {"unverified": "Aún no se ha usado ni probado en esta sesión.",
                "ok": "Respondió con datos en la última consulta."}.get(status, "")
        rows.append(
            f'<li class="sc-row {tone}"><span class="sc-dot"></span><div class="sc-b"><b>{escape(name)}</b>'
            f'<span>{escape(module)} · {escape(source)}</span>'
            f'<span class="sc-w">{("Última consulta: " + escape(when)) if when else escape(note)}'
            f'{(" · último éxito " + escape(s["last_ok"])) if s.get("last_ok") and status != "ok" else ""}</span></div>'
            f'{pill_html(status)}</li>')
    n_ok, n_bad, n_warn = counts["good"], counts["bad"], counts["warn"]
    tone = "bad" if n_bad else ("warn" if n_warn else ("good" if n_ok else "neutral"))
    summary = (f"{n_ok} conectada{'s' if n_ok != 1 else ''}" + (f" · {n_bad} con error" if n_bad else "")
               + (f" · {n_warn} sin datos" if n_warn else "")) if (n_ok or n_bad or n_warn) else "Sin verificar"
    return (
        f'<details class="ds-center {tone}" id="ds-center"><summary title="Estado de las conexiones">'
        f'<span class="sc-dot"></span><span class="sc-s">{escape(summary)}</span><span class="sc-run">Actualizando…</span></summary>'
        '<div class="sc-panel"><div class="sc-h"><b>Estado de conexiones</b><span>Solo se marca «Conectado» lo que respondió '
        'en esta sesión.</span></div>'
        f'<ul>{"".join(rows)}</ul>'
        '<button type="button" class="dash-btn ghost sm" data-dpst-go="Inicio" data-dpst-open="Comprobar conexiones reales">'
        + icon("refresh", 14) + '<span>Probar todas las conexiones</span></button></div></details>'
    )
