"""
Análisis a fondo para DPST Financial Insights (motor local, sin IA externa).

Cada función lee SOLO valores que el bot ya calculó (activo descargado, comparación y lo que
anotaron las pantallas del laboratorio) y los relaciona: compara periodos, ordena activos,
mide diferencias y señala lo que llama la atención. Las cuentas que se hacen aquí son
comparaciones aritméticas entre esos valores (diferencias, cocientes, posiciones en un
ranking); no se reestima ningún modelo ni se inventan indicadores. Todo es descriptivo:
nada de esto es una recomendación de compra o venta.
"""
from __future__ import annotations

import math
import re
from statistics import median
from typing import Optional


def _p(x, d=2):
    return "—" if x is None else f"{x:.{d}%}"


def _n(x, d=3):
    return "—" if x is None else f"{x:,.{d}f}"


def _rank(rows, key, ticker, reverse=True):
    vals = sorted((r for r in rows if r.get(key) is not None), key=lambda r: r[key], reverse=reverse)
    for i, r in enumerate(vals, 1):
        if r["ticker"] == ticker:
            return i, len(vals)
    return None, len(vals)


def mentioned_tickers(question: str, asset: Optional[dict], comparison: Optional[dict]) -> "list[str]":
    """Tickers de la sesión que aparecen escritos en la pregunta (AAPL, ECOPETROL.CL…)."""
    known = set()
    if asset:
        known.add(asset["ticker"].upper())
    if comparison:
        known |= {r["ticker"].upper() for r in comparison["rows"]}
    words = set(re.findall(r"[A-Za-z0-9^][A-Za-z0-9.\-^=]*", question or ""))
    return [w.upper() for w in words if w.upper() in known]


# ---------------------------------------------------------------------------
# Piezas por tema
# ---------------------------------------------------------------------------
def asset_volatility(asset: dict) -> "list[str]":
    out = []
    v, rv = asset.get("vol"), asset.get("recent_vol")
    if v is not None and rv is not None and v > 0:
        ch = rv / v - 1
        trend = ("más agitado" if ch > 0.10 else "más tranquilo" if ch < -0.10 else "parecido")
        out.append(f"En la ventana reciente ({asset.get('n_recent')} rendimientos) la volatilidad anual es {_p(rv)} frente a "
                   f"{_p(v)} de toda la muestra ({ch:+.0%}): el último tramo ha sido {trend} que el promedio histórico."
                   + (" Ojo: la ventana reciente está incompleta (parcial)." if asset.get("partial") else ""))
    if asset.get("std") is not None and asset.get("min") is not None and asset["std"] > 0:
        z = asset["min"] / asset["std"]
        out.append(f"El peor periodo ({asset['min']:+.4f}) equivale a {abs(z):.1f} desviaciones estándar por debajo de cero"
                   + ("; en una normal eso sería rarísimo, señal de colas pesadas." if abs(z) > 4 else "."))
    k = asset.get("kurt")
    if k is not None:
        out.append(f"Exceso de curtosis {k:.2f}: " + (
            "las colas son mucho más pesadas que en una normal; σ subestima los días extremos." if k > 3 else
            "colas algo más pesadas que una normal." if k > 0.5 else "colas parecidas a una normal."))
    return out


def asset_return(asset: dict) -> "list[str]":
    out = []
    m, v = asset.get("mean"), asset.get("vol")
    if m is not None and v:
        out.append(f"Por cada punto de volatilidad anual, {asset['ticker']} rindió {m / v:.2f} puntos de media anual "
                   "(μ/σ, la misma idea de la RVR de la Comparación).")
    rm = asset.get("recent_mean")
    if m is not None and rm is not None:
        out.append(f"Media anual reciente {_p(rm)} frente a {_p(m)} histórica: el último tramo rindió "
                   + ("por encima" if rm > m else "por debajo") + " del promedio de toda la muestra.")
    med, mean_pp = asset.get("median"), asset.get("mean_pp")
    if med is not None and mean_pp is not None:
        out.append(f"La mediana por periodo ({med:+.5f}) es " + ("mayor" if med > mean_pp else "menor")
                   + f" que la media ({mean_pp:+.5f}): " + (
                       "unos pocos periodos muy malos bajan el promedio." if med > mean_pp else
                       "unos pocos periodos muy buenos suben el promedio."))
    s = asset.get("skew")
    if s is not None:
        out.append(f"Asimetría {s:+.2f}: " + ("las sorpresas grandes han sido más bien al alza." if s > 0.2 else
                                             "las sorpresas grandes han sido más bien a la baja." if s < -0.2 else
                                             "subidas y caídas extremas bastante equilibradas."))
    return out


def asset_drawdown(asset: dict) -> "list[str]":
    dd, m = asset.get("dd"), asset.get("mean")
    out = []
    if dd is not None:
        need = 1 / (1 + dd) - 1 if dd > -1 else None
        if need is not None:
            out.append(f"Para recuperarse de una caída de {_p(dd)} el precio tendría que subir {_p(need)} desde el mínimo "
                       "(las pérdidas y las ganancias no son simétricas).")
        if m and m > 0 and need is not None:
            years = math.log(1 + need) / m
            out.append(f"Al ritmo de la media logarítmica histórica ({_p(m)} anual), eso serían unos {years:.1f} años: "
                       "es solo una cuenta ilustrativa, no una proyección.")
    return out


def asset_vs_peers(asset: Optional[dict], comparison: Optional[dict], tickers: "list[str]") -> "list[str]":
    if not comparison:
        return []
    rows = comparison["rows"]
    out = []
    targets = tickers or ([asset["ticker"]] if asset and any(r["ticker"] == asset["ticker"] for r in rows) else [])
    for t in targets[:3]:
        r = next((x for x in rows if x["ticker"].upper() == t.upper()), None)
        if not r:
            continue
        rv, n = _rank(rows, "vol", r["ticker"], reverse=False)
        rm, _ = _rank(rows, "mean", r["ticker"])
        rr, _ = _rank(rows, "rvr", r["ticker"])
        out.append(f"{r['ticker']} en la Comparación: puesto {rm} de {n} en media (μ {_p(r['mean'])}), {rv} de {n} en "
                   f"menor volatilidad (σ {_p(r['vol'])}) y {rr} de {n} en RVR ({_n(r.get('rvr'))})."
                   + (" Es un activo no dominado." if r["ticker"] in comparison.get("nd", ()) else
                      " Está dominado: otro activo del lote tiene a la vez más media y menos volatilidad."))
    return out


def comparison_overview(comparison: dict, focus: "list[str]" = ()) -> "list[str]":
    rows = comparison["rows"]
    if not rows:
        return []
    vols = [r["vol"] for r in rows]
    means = [r["mean"] for r in rows]
    best_rvr = max((r for r in rows if r.get("rvr") is not None), key=lambda r: r["rvr"], default=None)
    low_vol = min(rows, key=lambda r: r["vol"])
    hi_mean = max(rows, key=lambda r: r["mean"])
    nd = comparison.get("nd") or set()
    out = [f"{len(rows)} activos comparados ({comparison['window']}, {comparison['currency']}): σ anual entre "
           f"{_p(min(vols))} y {_p(max(vols))} (mediana {_p(median(vols))}); μ anual entre {_p(min(means))} y "
           f"{_p(max(means))} (mediana {_p(median(means))})."]
    out.append(f"Menor volatilidad: {low_vol['ticker']} ({_p(low_vol['vol'])}); mayor media: {hi_mean['ticker']} "
               f"({_p(hi_mean['mean'])})" + (f"; mejor RVR: {best_rvr['ticker']} ({_n(best_rvr['rvr'])})." if best_rvr else "."))
    if nd:
        out.append(f"{len(nd)} de {len(rows)} son no dominados ({', '.join(sorted(nd)[:8])}"
                   + ("…" if len(nd) > 8 else "") + "): forman el «borde» del mapa riesgo-rentabilidad.")
    if len(focus) >= 2:
        a, b = (next((r for r in rows if r["ticker"].upper() == t.upper()), None) for t in focus[:2])
        if a and b:
            out.append(f"{a['ticker']} vs {b['ticker']}: μ {_p(a['mean'])} vs {_p(b['mean'])} "
                       f"({a['mean'] - b['mean']:+.2%}), σ {_p(a['vol'])} vs {_p(b['vol'])} ({a['vol'] - b['vol']:+.2%}), "
                       f"RVR {_n(a.get('rvr'))} vs {_n(b.get('rvr'))}."
                       + ("" if a.get("dd") is None else f" Máx. caída {_p(a['dd'])} vs {_p(b['dd'])}."))
    return out


_PORTFOLIO_WORDS = {"gmv": ("minima varianza", "gmv", "minimo riesgo"), "tang": ("tangente", "maximo sharpe"),
                    "personal": ("personal", "optimo personal", "gamma"), "maximo": ("maximo rendimiento", "maximo retorno")}


def _norm(text: str) -> str:
    import unicodedata
    t = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def markowitz_analysis(ctx: dict, question: str = "") -> "list[str]":
    v = (ctx.get("markowitz") or {}).get("values")
    if not v:
        return []
    out = []
    rows = {r["cartera"]: r for r in v["rows"] if r.get("ok")}
    q = _norm(question)
    wanted = [k for k, words in _PORTFOLIO_WORDS.items() if any(w in q for w in words)]
    if wanted:  # la pregunta nombra una cartera: solo esa (y la comparación con las demás)
        keep = {n: r for n, r in rows.items() if any(
            (k == "gmv" and "minima" in _norm(n)) or (k == "tang" and "tangente" in _norm(n))
            or (k == "personal" and "personal" in _norm(n)) or (k == "maximo" and "maximo" in _norm(n)) for k in wanted)}
        if keep:
            others = [r for n, r in rows.items() if n not in keep]
            for n, r in keep.items():
                for o in others[:3]:
                    if r.get("ret") is not None and o.get("ret") is not None:
                        out.append(f"{n} frente a {o['cartera']}: rendimiento {_p(r['ret'])} vs {_p(o['ret'])} "
                                   f"({r['ret'] - o['ret']:+.2%}), volatilidad {_p(r['vol'])} vs {_p(o['vol'])} "
                                   f"({r['vol'] - o['vol']:+.2%}).")
            rows = keep
    for name, r in rows.items():
        w = {k: x for k, x in (r.get("weights") or {}).items() if x is not None}
        if not w:
            continue
        top = sorted(w.items(), key=lambda kv: kv[1], reverse=True)
        used = sum(1 for x in w.values() if x > 0.01)
        hhi = sum(x * x for x in w.values())
        out.append(f"{name}: {used} de {len(w)} activos con más de 1 %; los mayores pesos son "
                   + ", ".join(f"{k} {x:.0%}" for k, x in top[:3] if x > 0.005)
                   + f". Concentración HHI {hhi:.2f} (≈ {1 / hhi:.1f} activos «efectivos»)." if hhi > 0 else "")
    names = list(rows)
    if len(names) >= 2 and not wanted:
        lo = min(rows.values(), key=lambda r: r["vol"] or 9)
        hi = max(rows.values(), key=lambda r: r["ret"] or -9)
        if lo is not hi and lo.get("vol") and hi.get("vol"):
            out.append(f"Pasar de {lo['cartera']} a {hi['cartera']} sube el rendimiento esperado de {_p(lo['ret'])} a "
                       f"{_p(hi['ret'])} ({hi['ret'] - lo['ret']:+.2%}) a cambio de más volatilidad: {_p(lo['vol'])} → "
                       f"{_p(hi['vol'])} ({hi['vol'] - lo['vol']:+.2%}). Esa es la disyuntiva que muestra la frontera.")
    tan = next((r for n, r in rows.items() if n.lower().startswith("tang")), None)
    if tan and tan.get("sharpe") is not None:
        out.append(f"La tangente tiene el mayor Sharpe por periodo ({_n(tan['sharpe'])}) con rf {_p(v['rf_ea'])} EA: "
                   "si cambia la rf, cambia la tangente.")
    return out


def bl_analysis(ctx: dict) -> "list[str]":
    v = (ctx.get("bl") or {}).get("values")
    if not v or not v.get("rows"):
        return []
    rows = v["rows"]
    deltas = sorted(((r["activo"], r["post"] - r["prior"]) for r in rows), key=lambda x: x[1])
    out = []
    if v["n_views"] == 0:
        out.append("Sin views, la posterior coincide con el prior: el modelo solo refleja el equilibrio de mercado.")
    else:
        up, down = deltas[-1], deltas[0]
        out.append(f"Las {v['n_views']} view(s) movieron más a {up[0]} ({up[1]:+.2%} frente al prior) y a {down[0]} "
                   f"({down[1]:+.2%}).")
        moved = sum(1 for _a, d in deltas if abs(d) > 0.001)
        out.append(f"{moved} de {len(rows)} activos cambiaron más de 0,1 punto: con τ = {_n(v['tau'], 3)}, "
                   + ("las views pesan poco frente al prior." if v["tau"] <= 0.05 else "las views pesan bastante."))
    gaps = sorted(((r["activo"], r["hist"] - r["prior"]) for r in rows), key=lambda x: abs(x[1]), reverse=True)
    if gaps:
        out.append(f"La mayor diferencia entre la media histórica y el prior está en {gaps[0][0]} ({gaps[0][1]:+.2%}): "
                   "por eso usar la media histórica directa en Markowitz da pesos tan distintos.")
    return out


def capm_analysis(ctx: dict) -> "list[str]":
    v = (ctx.get("capm") or {}).get("values")
    if not v:
        return []
    rows = [r for r in v["rows"] if r.get("beta") is not None]
    out = []
    for r in rows:
        b = r["beta"]
        kind = "agresiva (amplifica al mercado)" if b > 1.05 else "defensiva (se mueve menos que el mercado)" if b < 0.95 else "parecida al mercado"
        out.append(f"{r['cartera']}: beta {_n(b, 2)} → {kind}; si {v['bench']} se moviera 10 %, el modelo esperaría "
                   f"≈ {10 * b:.1f} % en la cartera." + (f" R² {_n(r.get('r2'), 2)}: " + (
                       "la beta explica buena parte del movimiento." if (r.get("r2") or 0) > 0.6 else
                       "la beta explica poco; hay mucho riesgo propio.") if r.get("r2") is not None else ""))
    return out


def risk_analysis(ctx: dict) -> "list[str]":
    v = (ctx.get("risk") or {}).get("values")
    if not v:
        return []
    out = []
    if v.get("wavg_vol"):
        gain = 1 - v["vol"] / v["wavg_vol"]
        out.append(f"La diversificación reduce la volatilidad en {gain:.0%}: la cartera tiene {_p(v['vol'])} frente a "
                   f"{_p(v['wavg_vol'])} si no hubiera beneficio de combinar (promedio ponderado).")
    if v.get("corr_max") is not None:
        out.append(f"Correlaciones entre {_n(v['corr_min'], 2)} y {_n(v['corr_max'], 2)}"
                   + (f"; el par más parecido es {v['pair_max']} y el menos, {v['pair_min']}." if v.get("pair_max") else ".")
                   + (" Correlaciones altas (≥ 0,8) aportan poca diversificación." if v["corr_max"] >= 0.8 else ""))
    w = v.get("weights") or {}
    if w:
        top = max(w.items(), key=lambda kv: kv[1])
        out.append(f"El mayor peso es {top[0]} ({top[1]:.0%}); con {len(w)} activos el reparto igual sería {1 / len(w):.0%} cada uno.")
    return out


def forecast_analysis(ctx: dict) -> "list[str]":
    v = (ctx.get("forecast") or {}).get("values")
    if not v or not v.get("p0"):
        return []
    p0 = v["p0"]
    lo, mid, hi = v["q05"] / p0 - 1, v["median"] / p0 - 1, v["q95"] / p0 - 1
    width = (v["q95"] - v["q05"]) / v["median"] if v["median"] else None
    out = [f"Frente al precio de partida, la mediana en H implica {mid:+.1%} y el intervalo 5 %–95 % va de {lo:+.1%} a {hi:+.1%}.",
           f"El intervalo es asimétrico: hay más espacio hacia arriba ({hi:+.1%}) que hacia abajo ({lo:+.1%}) porque el modelo "
           "es log-normal (el precio no puede bajar de cero)." if hi > -lo else
           "El intervalo es casi simétrico alrededor de la mediana."]
    if width is not None:
        out.append(f"El ancho del intervalo es {width:.0%} de la mediana: " + (
            "mucha incertidumbre, el horizonte o la volatilidad son altos." if width > 0.5 else "incertidumbre moderada."))
    if v.get("std_pp") and v.get("h"):
        out.append(f"La incertidumbre crece con la raíz del horizonte: σ por periodo {v['std_pp']:.4f} × √{v['h']} ≈ "
                   f"{v['std_pp'] * math.sqrt(v['h']):.3f} en log al final.")
    return out


def rates_analysis(ctx: dict) -> "list[str]":
    v = (ctx.get("rates") or {}).get("values")
    if not v:
        return []
    out = [f"{v['label']}: {v['last']:.2f} % al {v['date']}."]
    if v.get("chg12") is not None:
        c = v["chg12"]
        out.append(f"En 12 meses cambió {c:+.2f} puntos: " + (
            "subida de tasas, los bonos ya emitidos valen menos (precio y tasa van en sentido contrario)." if c > 0.25 else
            "bajada de tasas, los bonos ya emitidos valen más." if c < -0.25 else "prácticamente estable."))
    mk = (ctx.get("markowitz") or {}).get("values")
    if mk and mk.get("rf_ea") is not None:
        out.append(f"La rf que usa el Laboratorio es {_p(mk['rf_ea'])} EA; esta tasa es {v['last'] / 100 - mk['rf_ea']:+.2%} "
                   "frente a ese supuesto (si es de otro país o moneda, no se compara directamente).")
    return out


def session_summary(asset, comparison, ctx) -> "list[str]":
    """Panorama de todo lo que hay en la sesión."""
    out = []
    if asset:
        out.append(f"Activo descargado: {asset['ticker']} ({asset['start']} a {asset['end']}, {asset['freq']}): μ anual "
                   f"{_p(asset['mean'])}, σ anual {_p(asset['vol'])}, máxima caída {_p(asset['dd'])}.")
        out += asset_volatility(asset)[:1]
    if comparison:
        out += comparison_overview(comparison)[:2]
    out += markowitz_analysis(ctx)[:2] + bl_analysis(ctx)[:1] + capm_analysis(ctx)[:1] + risk_analysis(ctx)[:1]
    out += forecast_analysis(ctx)[:1] + rates_analysis(ctx)[:1]
    return out


def analyze(topic: str, asset, comparison, ctx, tickers: "list[str]", question: str = "") -> "list[str]":
    focus_asset = asset if (not tickers or (asset and asset["ticker"].upper() in tickers)) else None
    if topic == "volatility":
        return (asset_volatility(focus_asset) if focus_asset else []) + asset_vs_peers(asset, comparison, tickers) \
            + (comparison_overview(comparison, tickers)[:1] if comparison and not focus_asset else []) + risk_analysis(ctx)[:1]
    if topic == "return":
        return (asset_return(focus_asset) if focus_asset else []) + asset_vs_peers(asset, comparison, tickers)
    if topic == "drawdown":
        return asset_drawdown(focus_asset) if focus_asset else []
    if topic in ("markowitz", "frontier", "sharpe"):
        return markowitz_analysis(ctx, question) + (capm_analysis(ctx) if topic == "sharpe" else [])
    if topic == "bl":
        return bl_analysis(ctx)
    if topic == "beta":
        return capm_analysis(ctx)
    if topic == "diversification":
        return risk_analysis(ctx) + (comparison_overview(comparison)[:1] if comparison else [])
    if topic == "forecast":
        return forecast_analysis(ctx)
    if topic == "rates":
        return rates_analysis(ctx)
    if topic == "compare":
        return comparison_overview(comparison, tickers) + asset_vs_peers(asset, comparison, tickers) if comparison else []
    if topic == "summary":
        return session_summary(asset, comparison, ctx)
    return []


FOLLOWUPS = {
    "volatility": ["¿Qué significa la máxima caída?", "¿Qué significa diversificar?", "¿Cómo interpreto el pronóstico?"],
    "return": ["¿Qué significa la volatilidad y cómo la interpreto?", "¿Qué representa el Sharpe Ratio?"],
    "drawdown": ["¿Qué significa la volatilidad y cómo la interpreto?", "¿Qué significa diversificar?"],
    "sharpe": ["¿Cómo interpreto los resultados de Markowitz?", "¿Qué es la beta?"],
    "beta": ["¿Qué representa el Sharpe Ratio?", "¿Qué significa diversificar?"],
    "frontier": ["¿Cómo interpreto los resultados de Markowitz?", "¿Qué significan los resultados de Black-Litterman?"],
    "markowitz": ["¿Cómo leo la frontera eficiente?", "¿Qué significan los resultados de Black-Litterman?", "¿Qué es la beta?"],
    "bl": ["¿Cómo interpreto los resultados de Markowitz?", "¿Qué representa el Sharpe Ratio?"],
    "diversification": ["¿Qué es la beta?", "¿Cómo interpreto los resultados de Markowitz?"],
    "forecast": ["¿Qué significa la volatilidad y cómo la interpreto?", "Hazme un resumen de mis resultados"],
    "rates": ["¿Qué representa el Sharpe Ratio?", "Hazme un resumen de mis resultados"],
    "compare": ["¿Cómo leo la frontera eficiente?", "¿Qué significa diversificar?"],
    "summary": ["¿Qué significa la volatilidad y cómo la interpreto?", "¿Cómo interpreto los resultados de Markowitz?"],
}
