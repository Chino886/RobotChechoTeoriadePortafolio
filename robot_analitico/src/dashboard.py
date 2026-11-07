"""
Dashboard personalizable de Inicio (solo presentación).

No calcula ni descarga nada: recibe lo que la app ya tiene en la sesión (activo descargado,
comparación, cotizaciones, registro de conexiones, backtest) y lo arma en HTML. Las preferencias
de cada persona (qué tarjetas ver, su orden y los activos favoritos) se guardan en el navegador
(localStorage, igual que el tema y «Abrir un módulo a la vez») desde src/ui_fx.py.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import escape
from typing import Optional

from src.ui_fx import icon, section_label_html

# Orden y visibilidad iniciales («Restaurar distribución original» vuelve aquí).
KPI_DEFAULT_ORDER = ["assets", "ret", "vol", "models", "last", "update", "conn", "cmp", "dd"]
KPI_DEFAULT_HIDDEN = ["dd"]
ACTIVITY_KEY = "dpst_activity"
ACTIVITY_MAX = 30
SPARK_POINTS = 60


@dataclass
class Kpi:
    id: str
    icon: str
    label: str
    value: str
    note: str
    tip: str
    tone: str = "neutral"  # neutral | good | warn | empty
    spark: Optional[dict] = None  # salida de spark_data()
    go: Optional[str] = None  # pestaña a la que lleva el clic
    open: Optional[str] = None  # desplegable que se abre al llegar


@dataclass
class TrackedAsset:
    ticker: str
    origin: str  # de dónde viene el dato en la sesión
    source: str = ""
    currency: str = ""
    last_price: Optional[float] = None
    last_date: str = ""
    mean_annual: Optional[float] = None
    vol_annual: Optional[float] = None
    spark: Optional[dict] = None
    origins: list = field(default_factory=list)


@dataclass
class Service:
    name: str
    state: str  # ok | fail | idle
    detail: str
    when: str = ""


def spark_data(series, points: int = SPARK_POINTS) -> Optional[dict]:
    """Submuestrea una serie real (índice de fechas) para el minigráfico; None si no alcanza."""
    if series is None:
        return None
    s = series.dropna()
    if len(s) < 2:
        return None
    step = max(1, len(s) // points)
    pos = list(range(0, len(s), step))
    if pos[-1] != len(s) - 1:
        pos.append(len(s) - 1)  # siempre termina en el último dato real
    sub = s.iloc[pos]
    intraday = any(getattr(i, "hour", 0) or getattr(i, "minute", 0) for i in sub.index)
    dates = [(i.strftime("%Y-%m-%d %H:%M") if intraday else str(i.date())) if hasattr(i, "date") else str(i)
             for i in sub.index]
    return {"v": [round(float(x), 4) for x in sub], "d": dates}


def spark_svg(spark: Optional[dict], label: str) -> str:
    """Minigráfico SVG; los valores viajan en data-* para el tooltip al pasar el mouse."""
    if not spark or len(spark.get("v", [])) < 2:
        return ""
    vals = spark["v"]
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    xs = [100 * i / (len(vals) - 1) for i in range(len(vals))]
    ys = [3 + 26 * (1 - (v - lo) / span) for v in vals]
    line = "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in zip(xs, ys))
    up = vals[-1] >= vals[0]
    payload = escape(json.dumps(spark, separators=(",", ":")), quote=True)
    return (
        f'<svg class="dash-spark {"up" if up else "down"}" viewBox="0 0 100 32" preserveAspectRatio="none" role="img" '
        f'aria-label="{escape(label)}" data-spark="{payload}">'
        f'<path class="a" d="{line} L100,32 L0,32 Z"/><path class="l" d="{line}" vector-effect="non-scaling-stroke"/></svg>'
    )


def _pct(x: Optional[float]) -> str:
    return "—" if x is None else f"{x:.2%}"


def kpi_html(k: Kpi, i: int) -> str:
    nav = ""
    if k.go:
        nav = f' data-dash-go="{escape(k.go)}"' + (f' data-dash-open="{escape(k.open)}"' if k.open else "")
    spark = spark_svg(k.spark, f"{k.label}: minigráfico") if k.spark else ""
    return (
        f'<article class="dash-kpi {k.tone}" data-kpi="{k.id}"{nav} tabindex="0" style="--i:{i}">'
        '<div class="dk-edit" aria-hidden="true">'
        f'<button type="button" class="dk-mv" data-mv="-1" title="Mover antes" aria-label="Mover {escape(k.label)} antes">‹</button>'
        f'<span class="dk-grip" title="Arrastra para cambiar el orden">⠿</span>'
        f'<button type="button" class="dk-mv" data-mv="1" title="Mover después" aria-label="Mover {escape(k.label)} después">›</button>'
        f'<button type="button" class="dk-eye" title="Mostrar u ocultar" aria-label="Mostrar u ocultar {escape(k.label)}"></button>'
        '</div>'
        f'<div class="dk-top"><span class="dk-ic">{icon(k.icon, 16)}</span><span class="dk-lab">{escape(k.label)}</span>'
        f'<span class="dash-tip" tabindex="0" role="button" aria-label="Qué es: {escape(k.tip)}" data-tip="{escape(k.tip)}">?</span></div>'
        f'<div class="dk-val">{escape(k.value)}</div><div class="dk-note">{escape(k.note)}</div>{spark}</article>'
    )


def assets_html(assets: "list[TrackedAsset]") -> str:
    rows = []
    for a in assets:
        stats = []
        if a.mean_annual is not None:
            stats.append(f'<span title="Media anualizada de los log-rendimientos">μ {_pct(a.mean_annual)}</span>')
        if a.vol_annual is not None:
            stats.append(f'<span title="Volatilidad anualizada">σ {_pct(a.vol_annual)}</span>')
        price = (f'<b>{a.last_price:,.2f}</b> {escape(a.currency)}' if a.last_price is not None else "")
        when = f'<span class="da-when">{escape(a.last_date)}</span>' if a.last_date else ""
        rows.append(
            f'<li class="dash-asset" data-asset="{escape(a.ticker)}" data-origin="session">'
            f'<span class="da-av">{escape(a.ticker[:1])}</span>'
            f'<span class="da-id"><b>{escape(a.ticker)}</b><span class="da-or">{escape(" · ".join(a.origins or [a.origin]))}</span></span>'
            f'{spark_svg(a.spark, a.ticker + ": precio")}'
            f'<span class="da-px">{price}{when}</span><span class="da-st">{"".join(stats)}</span>'
            f'<button type="button" class="dash-fav" data-fav="{escape(a.ticker)}" data-fav-name="" aria-pressed="false" '
            f'title="Marcar como favorito" aria-label="Marcar {escape(a.ticker)} como favorito">{icon("star", 16)}</button></li>'
        )
    empty = ('<li class="dash-empty" data-empty="session">Aún no hay activos en esta sesión. Descárgalo en '
             '<button type="button" class="dash-link" data-dpst-go="Preselección de activos" '
             'data-dpst-open="Datos del activo a probar">Preselección</button> o márcalo con ★ en '
             '<button type="button" class="dash-link" data-dpst-go="Tickers">Tickers</button>.</li>')
    return f'<ul class="dash-assets">{"".join(rows) or ""}{empty}</ul>'


ACTIVITY_KINDS = [("all", "Todos"), ("asset", "Activos"), ("cmp", "Comparación"), ("lab", "Laboratorio"),
                  ("conn", "Conexiones")]


def activity_html(events: "list[dict]") -> str:
    items = []
    for e in reversed(events):
        nav = f' data-dpst-go="{escape(e["go"])}"' + (f' data-dpst-open="{escape(e["open"])}"' if e.get("open") else "")
        items.append(
            f'<li class="dash-ev {escape(e["kind"])}" data-kind="{escape(e["kind"])}">'
            f'<span class="de-ic">{icon(e.get("icon", "activity"), 15)}</span>'
            f'<span class="de-tx"><b>{escape(e["title"])}</b><span>{escape(e["detail"])}</span></span>'
            f'<time datetime="{escape(e["ts"])}">{escape(e["ts"][11:16])} UTC</time>'
            f'<button type="button" class="de-go"{nav} aria-label="Abrir {escape(e["title"])}">{icon("arrow", 14)}</button></li>'
        )
    empty = ('<li class="dash-empty">Todavía no hay análisis en esta sesión. Cuando descargues un activo, compares, '
             'consultes cotizaciones o pruebes las conexiones, aparecerán aquí con su hora.</li>')
    return f'<ul class="dash-evs">{"".join(items) or empty}</ul>'


def services_html(services: "list[Service]") -> str:
    labels = {"ok": "Conectado", "fail": "Falló", "idle": "Sin probar"}
    cells = "".join(
        f'<li class="dash-svc {s.state}" data-tip="{escape(s.detail)}" tabindex="0">'
        f'<span class="ds-dot" aria-hidden="true"></span><span class="ds-n">{escape(s.name)}</span>'
        f'<span class="ds-s">{labels.get(s.state, s.state)}{(" · " + escape(s.when)) if s.when else ""}</span></li>'
        for s in services
    )
    return f'<ul class="dash-svcs">{cells}</ul>'


def _chips(kinds, group: str) -> str:
    return (f'<div class="dash-chips" role="group" data-filter="{group}">' + "".join(
        f'<button type="button" class="dash-chip" data-val="{k}" aria-pressed="{"true" if k == "all" else "false"}">{escape(t)}</button>'
        for k, t in kinds) + "</div>")


def dashboard_html(kpis: "list[Kpi]", assets: "list[TrackedAsset]", events: "list[dict]",
                   services: "list[Service]", status_line: str) -> str:
    """HTML completo del dashboard. El orden/visibilidad guardados se aplican en el navegador."""
    by_id = {k.id: k for k in kpis}
    ordered = [by_id[i] for i in KPI_DEFAULT_ORDER if i in by_id] + [k for k in kpis if k.id not in KPI_DEFAULT_ORDER]
    cards = "".join(kpi_html(k, i) for i, k in enumerate(ordered))
    defaults = escape(json.dumps({"order": KPI_DEFAULT_ORDER, "hidden": KPI_DEFAULT_HIDDEN}), quote=True)
    tools = (
        '<div class="dash-tools">'
        f'<button type="button" class="dash-btn" data-dash-edit aria-pressed="false">{icon("sliders", 15)}<span>Personalizar</span></button>'
        f'<button type="button" class="dash-btn ghost" data-dash-reset title="Vuelve al orden y las tarjetas iniciales">'
        f'{icon("refresh", 15)}<span>Restaurar distribución original</span></button></div>'
    )
    return (
        f'<section class="dpst-dash" data-defaults="{defaults}">'
        f'<div class="dash-head"><div>{section_label_html("Mi dashboard", "activity")}'
        f'<div class="dash-status">{status_line}</div></div>{tools}</div>'
        '<div class="dash-hint" role="note">Modo personalizar: arrastra las tarjetas (o usa ‹ ›) para cambiar el orden y '
        'toca el ojo para mostrarlas u ocultarlas. Se guarda en este navegador.</div>'
        f'<div class="dash-kpis">{cards}</div>'
        '<div class="dash-grid">'
        f'<div class="dash-panel"><div class="dp-head"><span class="dp-t">{icon("star", 15)}Activos seguidos</span>'
        f'{_chips([("all", "Todos"), ("fav", "Favoritos"), ("session", "En la sesión")], "assets")}</div>'
        f'{assets_html(assets)}</div>'
        f'<div class="dash-panel"><div class="dp-head"><span class="dp-t">{icon("history", 15)}Últimos análisis</span>'
        f'{_chips(ACTIVITY_KINDS, "events")}</div>{activity_html(events)}</div>'
        '</div>'
        f'<div class="dash-panel conn"><div class="dp-head"><span class="dp-t">{icon("plug", 15)}Estado de conexiones</span>'
        '<button type="button" class="dash-btn ghost sm" data-dpst-go="Inicio" '
        'data-dpst-open="Comprobar conexiones reales">' + icon("refresh", 14) + '<span>Probar conexiones</span></button></div>'
        f'{services_html(services)}</div>'
        '</section>'
    )


# ---------------------------------------------------------------------------
# Registro de análisis de la sesión: detecta resultados nuevos en session_state
# (mismo objeto = mismo análisis) y anota la hora en que aparecieron. No recalcula nada.
# ---------------------------------------------------------------------------

def _now_iso(now=None) -> str:
    return (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def track_activity(state, lab_title: str, now=None) -> "list[dict]":
    seen = state.get("dpst_activity_seen") or {}
    events = list(state.get(ACTIVITY_KEY) or [])
    ts = _now_iso(now)

    def add(key, sig, event):
        if sig is None or seen.get(key) == sig:
            return
        seen[key] = sig
        events.append({"ts": ts, **event})

    res = state.get("asset_result")
    if res is not None and getattr(res, "ok", False) and getattr(res, "prices", None) is not None:
        freq = state.get("asset_frequency") or ""
        add("asset", id(res), {
            "kind": "asset", "icon": "database", "title": f"Activo descargado · {res.ticker}",
            "detail": f"{len(res.prices)} observaciones" + (f" · {freq}" if freq else "")
                      + f" · último dato {res.prices.index.max().date()}",
            "go": "Preselección de activos", "open": "Análisis histórico"})
    cmp_ = state.get("comparison_result")
    if cmp_ is not None and getattr(cmp_, "ok", False):
        tickers = [s.ticker for s in (cmp_.summaries or [])]
        add("cmp", id(cmp_), {
            "kind": "cmp", "icon": "scale", "title": f"Comparación · {len(tickers)} activos",
            "detail": ", ".join(tickers[:6]) + ("…" if len(tickers) > 6 else "")
                      + (f" · moneda {cmp_.base_currency}" if cmp_.base_currency else ""),
            "go": "Preselección de activos", "open": "Comparación y preselección de activos"})
    log = state.get("conn_check_log") or []
    if log:
        last = str(log[-1].get("hora (UTC)", ""))[:16]
        batch = [r for r in log if str(r.get("hora (UTC)", ""))[:16] == last] or log[-1:]
        ok = sum(1 for r in batch if r.get("estado") == "conectado")
        add("conn", len(log), {
            "kind": "conn", "icon": "plug", "title": "Prueba de conexiones",
            "detail": f"{ok} de {len(batch)} servicios conectados", "go": "Inicio",
            "open": "Comprobar conexiones reales"})
    qlog = state.get("lab_quote_log") or []
    if qlog:
        last_q = qlog[-1].get("consulta")
        batch = [r for r in qlog if r.get("consulta") == last_q] or qlog[-1:]
        add("quotes", len(qlog), {
            "kind": "lab", "icon": "clock", "title": "Cotización en línea",
            "detail": ", ".join(str(r.get("ticker")) for r in batch[:6]) + ("…" if len(batch) > 6 else ""),
            "go": lab_title})
    bt = state.get("lab_bt_result")
    if bt:
        cols = list(bt[1]) if len(bt) > 1 else []
        add("bt", id(bt[0]), {
            "kind": "lab", "icon": "history", "title": "Backtest walk-forward",
            "detail": f"{len(cols)} activos: " + ", ".join(map(str, cols[:6])) + ("…" if len(cols) > 6 else ""),
            "go": lab_title})
    events = events[-ACTIVITY_MAX:]
    state["dpst_activity_seen"] = seen
    state[ACTIVITY_KEY] = events
    return events
