"""
DPST Financial Insights: asistente de interpretación (solo explica, no recomienda).

Motor local y determinista: no usa ningún servicio de IA externo (el proyecto no tiene uno).
Las respuestas combinan textos académicos fijos con los valores REALES que el bot ya calculó
en la sesión. Esos valores se anotan con record() en el mismo lugar donde la app los muestra
(nunca se recalculan aquí). Si no hay un resultado, la respuesta lo dice y explica el concepto
en general, sin inventar cifras.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

CTX_KEY = "insights_ctx"
HISTORY_KEY = "insights_history"


def record(state, key: str, label: str, values: dict) -> None:
    """Guarda una copia de lo que la app acaba de mostrar (para que el asistente lo explique)."""
    ctx = state.get(CTX_KEY) or {}
    ctx[key] = {"label": label, "values": values,
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    state[CTX_KEY] = ctx


@dataclass
class Answer:
    topic: str
    title: str
    simple: str = ""
    interpretation: str = ""
    indicator: "list[str]" = field(default_factory=list)
    limitations: "list[str]" = field(default_factory=list)
    example: str = ""
    sources: "list[str]" = field(default_factory=list)
    has_data: bool = False
    refused: bool = False
    analysis: "list[str]" = field(default_factory=list)  # lectura a fondo de los valores de la sesión
    followups: "list[str]" = field(default_factory=list)  # preguntas para seguir profundizando
    also: "list[str]" = field(default_factory=list)  # otros temas de la misma pregunta


def _norm(text: str) -> str:
    t = unicodedata.normalize("NFD", (text or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _p(x, d: int = 2) -> str:
    return "—" if x is None else f"{x:.{d}%}"


def _n(x, d: int = 3) -> str:
    return "—" if x is None else f"{x:,.{d}f}"


# ---------------------------------------------------------------------------
# Detección del tema (palabras clave en español, sin tildes)
# ---------------------------------------------------------------------------
TOPICS = {
    "summary": ("Resumen de tus resultados", ["resumen", "resume", "panorama", "analiza todo", "que me dicen mis",
                                              "conclusion", "en general", "todo lo que", "mis resultados"]),
    "compare": ("Comparación entre activos", ["compara", "comparar", "comparacion", " vs ", "versus", "diferencia entre",
                                              "cual es mas", "cual tiene"]),
    "sharpe": ("Sharpe Ratio", ["sharpe"]),
    "beta": ("Beta", ["beta", "capm", "sistematic", "mercado", "benchmark"]),
    "bl": ("Black-Litterman", ["black", "litterman", "view", "posterior", "prior"]),
    "frontier": ("Frontera eficiente", ["frontera", "eficiente"]),
    "markowitz": ("Resultados de Markowitz", ["markowitz", "gmv", "minima varianza", "tangente", "optimo", "pesos"]),
    "diversification": ("Diversificación", ["diversific", "correlacion", "covarianza", "combinar", "cartera"]),
    "forecast": ("Pronósticos", ["pronostic", "predic", "futuro", "intervalo", "proyecc", "horizonte"]),
    "rates": ("Tasas soberanas", ["tasa", "bono", "soberan", "fred", "libre de riesgo", "tesoro"]),
    "drawdown": ("Máxima caída (drawdown)", ["drawdown", "caida", "perdida maxima", "recuper"]),
    "volatility": ("Volatilidad", ["volatil", "riesgo", "desviacion", "sigma", "variabilidad"]),
    "return": ("Rentabilidad", ["rentab", "rendimiento", "retorno", "media", "ganancia", "gana"]),
}
SUGGESTIONS = [
    ("volatility", "¿Qué significa la volatilidad y cómo la interpreto?"),
    ("return", "¿Cómo interpreto la rentabilidad de este activo?"),
    ("sharpe", "¿Qué representa el Sharpe Ratio?"),
    ("beta", "¿Qué es la beta?"),
    ("frontier", "¿Cómo leo la frontera eficiente?"),
    ("diversification", "¿Qué significa diversificar?"),
    ("markowitz", "¿Cómo interpreto los resultados de Markowitz?"),
    ("bl", "¿Qué significan los resultados de Black-Litterman?"),
    ("forecast", "¿Cómo interpreto el pronóstico?"),
    ("rates", "¿Qué representan las tasas soberanas?"),
    ("summary", "Hazme un resumen de mis resultados"),
    ("compare", "Compara los activos de mi comparación"),
]
_ADVICE = re.compile(
    r"\b(compro|comprar|compre|compraria|vendo|vender|venda|venderia|invierto|invertiria|"
    r"(debo|deberia|conviene|vale la pena|me sirve) (comprar|vender|invertir|meter)|en (que|cual) (invierto|invertir|meto)|"
    r"recomiendas|recomiendame|recomendarias|me recomiendas|me aconsejas|que accion|mejor accion|"
    r"mejor inversion|donde pongo mi dinero|cuanto (invierto|debo invertir))\b")


def detect_topics(question: str) -> "list[str]":
    """Todos los temas de la pregunta, del más nombrado al menos (en empate, el orden de TOPICS)."""
    q = f" {_norm(question)} "
    scored = [(sum(1 for w in words if w in q), i, key) for i, (key, (_t, words)) in enumerate(TOPICS.items())]
    return [key for s, _i, key in sorted(scored, key=lambda x: (-x[0], x[1])) if s > 0]


def detect_topic(question: str) -> Optional[str]:
    topics = detect_topics(question)
    return topics[0] if topics else None


def is_advice_request(question: str) -> bool:
    return bool(_ADVICE.search(_norm(question)))


# ---------------------------------------------------------------------------
# Resultados disponibles para elegir («Resultado a explicar»)
# ---------------------------------------------------------------------------
def context_options(asset: Optional[dict], comparison: Optional[dict], ctx: dict) -> "list[tuple[str, str, str]]":
    """(id, etiqueta, tema) de cada resultado que hay en la sesión."""
    opts = []
    if asset:
        t = asset["ticker"]
        opts += [("asset_vol", f"Volatilidad anual de {t} (Análisis histórico)", "volatility"),
                 ("asset_ret", f"Rentabilidad media anual de {t} (Análisis histórico)", "return"),
                 ("asset_dd", f"Máxima caída de {t} (Análisis histórico)", "drawdown")]
    if comparison:
        opts.append(("cmp", f"Comparación de {len(comparison['rows'])} activos (riesgo-rentabilidad)", "volatility"))
    names = {"forecast": "forecast", "rates": "rates", "markowitz": "markowitz", "bl": "bl", "capm": "beta",
             "risk": "diversification"}
    for key, topic in names.items():
        if key in ctx:
            opts.append((key, ctx[key]["label"], topic))
    return opts


# ---------------------------------------------------------------------------
# Respuestas por tema
# ---------------------------------------------------------------------------
_COMMON_LIMITS = ["Son datos históricos: describen el pasado de la muestra y no garantizan lo que pasará.",
                  "Es un ejercicio académico; no es una recomendación de inversión."]


def _volatility(a: Answer, asset, comparison, ctx, sel):
    a.simple = ("La volatilidad mide cuánto se mueve el precio alrededor de su promedio. Mientras más alta, más grandes "
                "suelen ser las subidas y bajadas de un periodo a otro.")
    a.interpretation = ("En el bot es la desviación estándar de los log-rendimientos, llevada a un año (σ anual). Se usa "
                        "como medida de riesgo total: dos activos con la misma rentabilidad media no son iguales si uno "
                        "oscila mucho más que el otro.")
    if sel == "cmp" and comparison or (not asset and comparison):
        rows = sorted(comparison["rows"], key=lambda r: r["vol"])
        a.indicator = [f"Comparación ({comparison['window']}, moneda {comparison['currency']}): σ anual va de "
                       f"{_p(rows[0]['vol'])} ({rows[0]['ticker']}) a {_p(rows[-1]['vol'])} ({rows[-1]['ticker']})."]
        a.indicator += [f"{r['ticker']}: σ {_p(r['vol'])} · μ {_p(r['mean'])}" for r in rows[:5]]
        a.has_data, a.sources = True, ["Preselección → Comparación y preselección (tabla comparativa)"]
    elif asset:
        a.indicator = [f"σ anual de {asset['ticker']}: {_p(asset['vol'])} ({asset['n']} rendimientos, frecuencia "
                       f"{asset['freq']}, {asset['start']} → {asset['end']})."]
        a.has_data, a.sources = True, ["Preselección → Análisis histórico → Descriptivos"]
        lo, hi = asset["mean"] - asset["vol"], asset["mean"] + asset["vol"]
        a.example = (f"Ejemplo educativo: si los log-rendimientos fueran normales (es un supuesto del modelo, no un hecho), "
                     f"cerca de 2 de cada 3 años el log-rendimiento anual de {asset['ticker']} quedaría entre "
                     f"{_p(lo)} y {_p(hi)} (μ ± σ con los valores de arriba).")
    a.limitations = ["Depende de la ventana y la frecuencia elegidas: otra muestra da otra cifra.",
                     "Trata igual las subidas y las bajadas, y no captura bien caídas extremas (para eso está el drawdown).",
                     ] + _COMMON_LIMITS[:1]


def _return(a: Answer, asset, comparison, ctx, sel):
    a.simple = "La rentabilidad media dice cuánto subió (o bajó) el precio en promedio por año durante la muestra."
    a.interpretation = ("El bot usa la media de los log-rendimientos anualizada (μ). Es una cifra histórica: resume el "
                        "pasado y se compara siempre junto con su riesgo (σ), no sola.")
    if asset:
        a.indicator = [f"μ anual de {asset['ticker']}: {_p(asset['mean'])} con σ anual {_p(asset['vol'])} "
                       f"({asset['n']} rendimientos, {asset['start']} → {asset['end']})."]
        a.has_data, a.sources = True, ["Preselección → Análisis histórico → Descriptivos"]
        a.example = (f"Ejemplo educativo: un log-rendimiento anual de {_p(asset['mean'])} equivale a una variación simple "
                     f"de aproximadamente {_p(_exp(asset['mean']) - 1)} en un año (e^μ − 1).")
    elif comparison:
        rows = sorted(comparison["rows"], key=lambda r: r["mean"], reverse=True)
        a.indicator = [f"{r['ticker']}: μ {_p(r['mean'])} · σ {_p(r['vol'])}" for r in rows[:5]]
        a.has_data, a.sources = True, ["Preselección → Comparación y preselección"]
    a.limitations = ["Una media alta en el pasado no implica una media alta en el futuro.",
                     "La media logarítmica es menor que la media simple cuando hay volatilidad.", _COMMON_LIMITS[1]]


def _exp(x):
    import math
    return math.exp(x)


def _drawdown(a: Answer, asset, comparison, ctx, sel):
    a.simple = "La máxima caída (drawdown) es la peor bajada desde un máximo anterior hasta un mínimo posterior."
    a.interpretation = "Mide el peor tramo que habría vivido alguien que compró en un pico: complementa a la volatilidad."
    if asset:
        a.indicator = [f"Máxima caída de {asset['ticker']}: {_p(asset['dd'])} ({asset['start']} → {asset['end']})."]
        a.has_data, a.sources = True, ["Preselección → Análisis histórico"]
    a.limitations = ["Es un solo episodio de la muestra; otro periodo puede mostrar caídas mayores."] + _COMMON_LIMITS


def _sharpe(a: Answer, asset, comparison, ctx, sel):
    a.simple = "El Sharpe Ratio dice cuánto rendimiento extra (sobre la tasa libre de riesgo) se obtuvo por cada unidad de volatilidad."
    a.interpretation = ("Sharpe = (rendimiento − rf) / volatilidad. Sirve para comparar carteras con riesgos distintos: "
                        "a mayor Sharpe, más rendimiento en exceso por unidad de riesgo en la muestra.")
    if "markowitz" in ctx:
        v = ctx["markowitz"]["values"]
        a.indicator = [f"rf = {_p(v['rf_ea'])} EA (supuesto del laboratorio)."] + [
            f"{r['cartera']}: Sharpe por periodo {_n(r['sharpe'])} · rendimiento {_p(r['ret'])} · volatilidad {_p(r['vol'])}"
            for r in v["rows"] if r["sharpe"] is not None]
        a.has_data, a.sources = True, ["Laboratorio → Markowitz y fronteras (tabla de carteras)"]
    if "capm" in ctx:
        v = ctx["capm"]["values"]
        a.indicator += [f"{r['cartera']}: Sharpe {_n(r['sharpe'])} (desempeño frente a {v['bench']})"
                        for r in v["rows"] if r.get("sharpe") is not None]
        a.has_data = True
        a.sources.append("Laboratorio → Beta, CAPM y valoración (desempeño)")
    if not a.has_data:
        a.indicator = ["Aún no hay un Sharpe calculado en esta sesión: aparece en Laboratorio → Markowitz y fronteras "
                       "o en Beta, CAPM y valoración. Ojo: la RVR de la Comparación (μ/σ) no es un Sharpe porque no resta rf."]
    a.limitations = ["Depende de la rf supuesta, que es una decisión del equipo.",
                     "Supone que la volatilidad resume bien el riesgo (no distingue caídas extremas).",
                     "El «por periodo» y el anual no se comparan directamente."] + _COMMON_LIMITS[:1]


def _beta(a: Answer, asset, comparison, ctx, sel):
    a.simple = "La beta mide cuánto se mueve un activo o una cartera cuando se mueve el mercado (el benchmark)."
    a.interpretation = ("Beta 1: se mueve en promedio como el mercado; mayor que 1: amplifica sus movimientos; entre 0 y 1: "
                        "los suaviza; negativa: tiende a ir en contra. Es la sensibilidad al riesgo sistemático, el que no "
                        "se elimina diversificando (CAPM).")
    if "capm" in ctx:
        v = ctx["capm"]["values"]
        a.indicator = [f"Benchmark: {v['bench']} · ventana {v['window']}."] + [
            f"{r['cartera']}: beta {_n(r.get('beta'))} · R² {_n(r.get('r2'))}" for r in v["rows"] if r.get("beta") is not None]
        a.has_data, a.sources = True, ["Laboratorio → Beta, CAPM y valoración"]
    else:
        a.indicator = ["Aún no hay betas en esta sesión: se calculan en Laboratorio → Beta, CAPM y valoración."]
    a.limitations = ["Cambia con el benchmark, la frecuencia y la ventana elegidos.",
                     "Un R² bajo indica que la beta explica poco del movimiento del activo."] + _COMMON_LIMITS[:1]


def _frontier(a: Answer, asset, comparison, ctx, sel):
    a.simple = ("La frontera eficiente es la curva de carteras que, para cada nivel de riesgo, ofrecen el mayor "
                "rendimiento esperado posible con los activos y restricciones dados.")
    a.interpretation = ("Las carteras sobre la rama superior son «eficientes»: no hay otra con más rendimiento y el mismo "
                        "riesgo. La rama inferior (punteada) no es eficiente. El punto de mínima varianza (GMV) es el de "
                        "menor riesgo y la tangente es la que maximiza el Sharpe con la rf supuesta.")
    _markowitz_values(a, ctx)
    a.limitations = ["Usa μ y Σ estimados del pasado: pequeños errores en μ cambian mucho la frontera.",
                     "Depende de las cotas de peso y de los grupos definidos.",
                     "El mapa de la Comparación NO es una frontera de carteras: muestra activos sueltos."] + _COMMON_LIMITS[1:]


def _markowitz_values(a: Answer, ctx):
    if "markowitz" in ctx:
        v = ctx["markowitz"]["values"]
        a.indicator = [f"{v['n_assets']} activos · rf {_p(v['rf_ea'])} EA · frontera con {v['n_frontier']} puntos óptimos."]
        for r in v["rows"]:
            w = ", ".join(f"{k} {_p(x, 1)}" for k, x in (r.get("weights") or {}).items())
            a.indicator.append(f"{r['cartera']}: rendimiento {_p(r['ret'])} · volatilidad {_p(r['vol'])}"
                               + (f" · pesos: {w}" if w else "") + ("" if r["ok"] else f" ({r['estado']})"))
        a.has_data, a.sources = True, ["Laboratorio → Markowitz y fronteras"]
    else:
        a.indicator = ["Aún no hay resultados de Markowitz en esta sesión: abre Laboratorio → Markowitz y fronteras."]


def _markowitz(a: Answer, asset, comparison, ctx, sel):
    a.simple = "Markowitz busca la combinación de pesos que da el mejor equilibrio entre rendimiento esperado y riesgo."
    a.interpretation = ("GMV = la cartera de menor volatilidad; Tangente = la de mayor Sharpe; Óptimo personal = la que "
                        "maximiza μ − (γ/2)·σ² con la aversión al riesgo γ que eligió el equipo. Los pesos dicen qué parte "
                        "del dinero va a cada activo en ese modelo.")
    _markowitz_values(a, ctx)
    a.limitations = ["Muy sensible a la μ estimada: por eso existen Black-Litterman y los estimadores alternativos de Σ.",
                     "γ, las cotas y la rf son decisiones del equipo, no del bot."] + _COMMON_LIMITS


def _bl(a: Answer, asset, comparison, ctx, sel):
    a.simple = ("Black-Litterman parte de una expectativa «neutral» del mercado (prior) y la ajusta con las opiniones "
                "(views) del equipo, según la confianza que se les dé. El resultado es la posterior.")
    a.interpretation = ("Si la posterior de un activo sube frente al prior, las views lo empujaron hacia arriba; si casi no "
                        "cambia, las views tenían poca confianza o no lo afectaban. Con la posterior se recalculan los pesos.")
    if "bl" in ctx:
        v = ctx["bl"]["values"]
        a.indicator = [f"Views usadas: {v['n_views']} · τ = {_n(v['tau'], 3)} · δ = {_n(v['delta'], 2)}."] + [
            f"{r['activo']}: histórico {_p(r['hist'])} · prior π {_p(r['prior'])} · posterior {_p(r['post'])} (exceso anual)"
            for r in v["rows"]]
        a.has_data, a.sources = True, ["Laboratorio → Black-Litterman"]
    else:
        a.indicator = ["Aún no hay resultados de Black-Litterman en esta sesión: abre Laboratorio → Black-Litterman."]
    a.limitations = ["Las views, su confianza, τ y δ son decisiones del equipo: cambiarlas cambia la posterior.",
                     "Sigue dependiendo de Σ estimada con datos del pasado."] + _COMMON_LIMITS


def _diversification(a: Answer, asset, comparison, ctx, sel):
    a.simple = ("Diversificar es combinar activos que no se mueven igual, para que las caídas de uno se compensen en "
                "parte con otros.")
    a.interpretation = ("Mientras menor sea la correlación entre activos, más baja es la volatilidad de la cartera frente "
                        "al promedio ponderado de las volatilidades individuales. Esa diferencia es el efecto de la "
                        "diversificación.")
    if "risk" in ctx:
        v = ctx["risk"]["values"]
        a.indicator = [f"Volatilidad de la cartera: {_p(v['vol'])} · promedio ponderado de volatilidades: {_p(v['wavg_vol'])}"
                       f" · diferencia: {_p(v['wavg_vol'] - v['vol'])}.",
                       f"Correlaciones entre activos: de {_n(v['corr_min'], 2)} a {_n(v['corr_max'], 2)}.",
                       "Pesos: " + ", ".join(f"{k} {_p(x, 1)}" for k, x in v["weights"].items())]
        a.has_data, a.sources = True, ["Laboratorio → Riesgo conjunto"]
    else:
        a.indicator = ["Aún no hay una cartera en esta sesión: arma una en Laboratorio → Riesgo conjunto."]
    a.limitations = ["Las correlaciones cambian con el tiempo y suelen subir en crisis (ver Estrés).",
                     "Diversificar reduce el riesgo propio de cada activo, no el riesgo del mercado (beta)."] + _COMMON_LIMITS[1:]


def _forecast(a: Answer, asset, comparison, ctx, sel):
    a.simple = ("El pronóstico no dice un precio seguro: muestra un rango de precios posibles y su punto medio "
                "(mediana) para cada paso del horizonte.")
    a.interpretation = ("Con el modelo elegido, el precio en H queda dentro del intervalo 5%–95% en 90 de cada 100 "
                        "escenarios del modelo. La mediana es el valor central, no una promesa.")
    if "forecast" in ctx:
        v = ctx["forecast"]["values"]
        a.indicator = [f"{v['ticker']} · modelo {v['model']} · H = {v['h']} periodos ({v['freq']}).",
                       f"Precio de partida: {_n(v['p0'], 2)} · mediana en H: {_n(v['median'], 2)} · intervalo 5%–95%: "
                       f"{_n(v['q05'], 2)} a {_n(v['q95'], 2)}.",
                       f"Parámetros por periodo: media {v['mean_pp']:.6f}, sigma {v['std_pp']:.6f}."]
        a.has_data, a.sources = True, ["Preselección → Pronóstico"]
        a.example = ("Ejemplo educativo: que el intervalo sea ancho indica mucha incertidumbre del modelo, no que el "
                     "precio vaya a moverse exactamente hasta esos extremos.")
    else:
        a.indicator = ["Aún no hay un pronóstico en esta sesión: ábrelo en Preselección → Pronóstico."]
    a.limitations = ["Los modelos son homocedásticos (volatilidad constante) por alcance pedagógico.",
                     "Supone que los rendimientos futuros se parecen a los de la muestra.",
                     "El 5%–95% es del modelo: los eventos extremos reales pueden quedar fuera."] + _COMMON_LIMITS[1:]


def _rates(a: Answer, asset, comparison, ctx, sel):
    a.simple = "Una tasa soberana es lo que paga el gobierno de un país por pedir dinero prestado con bonos."
    a.interpretation = ("La tasa a 10 años es una referencia de rendimiento de bajo riesgo en ese país: resume expectativas "
                        "de inflación, crecimiento y riesgo país. En DPST sirve de punto de comparación (por ejemplo, para "
                        "pensar la tasa libre de riesgo del Laboratorio).")
    if "rates" in ctx:
        v = ctx["rates"]["values"]
        a.indicator = [f"{v['label']}: última tasa {v['last']:.2f}% ({v['date']}) · {v['n']} observaciones · serie FRED {v['id']}."]
        if v.get("chg12") is not None:
            a.indicator.append(f"Cambio en 12 meses (el mismo de la pantalla): {v['chg12']:+.2f} puntos porcentuales.")
        a.has_data, a.sources = True, ["Tasas soberanas (FRED)"]
    else:
        a.indicator = ["Aún no hay una tasa consultada en esta sesión: ábrela en Tasas soberanas (requiere la clave de FRED)."]
    a.limitations = ["Las series de FRED pueden tener rezago de publicación (mensual en muchos países).",
                     "Una tasa en moneda local incluye la inflación esperada de ese país: no se compara directo entre monedas.",
                     "No entra en la preselección ni en el laboratorio de forma automática."]


def _summary(a: Answer, asset, comparison, ctx, sel):
    a.simple = "Este es el panorama de lo que el bot ya calculó en tu sesión, leído en conjunto."
    a.interpretation = ("Mira primero el par riesgo-rentabilidad (σ y μ), después cómo se combinan los activos (correlación "
                        "y carteras de Markowitz/Black-Litterman) y por último la sensibilidad al mercado (beta) y los rangos "
                        "del pronóstico. Ningún número aislado basta para concluir.")
    a.indicator = [v["label"] + " · " + v["ts"] for v in ctx.values()] + (
        [f"Activo descargado: {asset['ticker']}"] if asset else []) + (
        [f"Comparación de {len(comparison['rows'])} activos"] if comparison else [])
    a.has_data = bool(a.indicator)
    a.sources = ["Todo lo calculado en esta sesión"]
    a.limitations = ["El resumen solo incluye los módulos que ya se abrieron en esta sesión."] + _COMMON_LIMITS


def _compare(a: Answer, asset, comparison, ctx, sel):
    a.simple = ("Comparar activos es mirar a la vez cuánto rindieron (μ) y cuánto oscilaron (σ): un activo es mejor que "
                "otro en el sentido de Markowitz solo si gana en las dos cosas (lo «domina»).")
    a.interpretation = ("La RVR (μ/σ) resume ambas en una sola cifra, y la máxima caída muestra el peor tramo vivido. "
                        "Los no dominados forman el borde del mapa riesgo-rentabilidad.")
    if comparison:
        a.indicator = [f"{r['ticker']}: μ {_p(r['mean'])} · σ {_p(r['vol'])} · RVR {_n(r.get('rvr'))}"
                       for r in sorted(comparison["rows"], key=lambda r: -(r.get("rvr") or -9))[:8]]
        a.has_data, a.sources = True, ["Preselección → Comparación y preselección"]
    else:
        a.indicator = ["Aún no hay una comparación en esta sesión: hazla en Preselección → Comparación y preselección."]
    a.limitations = ["Todos los activos se miden en la misma ventana común y moneda base: cambiar fechas cambia el ranking."] \
        + _COMMON_LIMITS


_BUILDERS = {"summary": _summary, "compare": _compare, "volatility": _volatility, "return": _return, "drawdown": _drawdown, "sharpe": _sharpe, "beta": _beta,
             "frontier": _frontier, "markowitz": _markowitz, "bl": _bl, "diversification": _diversification,
             "forecast": _forecast, "rates": _rates}


def answer(question: str, asset: Optional[dict], comparison: Optional[dict], ctx: dict,
           selected: Optional[tuple] = None, previous_topic: Optional[str] = None) -> Answer:
    """Respuesta organizada. `selected` = (id, etiqueta, tema) del resultado elegido, si hay."""
    if is_advice_request(question):
        return Answer(
            topic="advice", title="No doy recomendaciones de compra o venta", refused=True,
            simple=("DPST es un ejercicio académico: puedo explicarte qué significan los resultados (volatilidad, "
                    "rentabilidad, Sharpe, beta, frontera, pronósticos…), pero no decirte qué comprar, vender ni cuánto invertir."),
            interpretation="Esa decisión depende de tu situación personal y de un asesor habilitado.",
            limitations=["Ningún resultado del bot es una recomendación personalizada de inversión."],
            example="Prueba: «¿Qué significa la volatilidad de este activo?» o «¿Cómo leo la frontera eficiente?».")
    from src.insights_analysis import FOLLOWUPS, analyze, mentioned_tickers
    topics = detect_topics(question)
    tickers = mentioned_tickers(question, asset, comparison)
    q = _norm(question)
    if not topics and previous_topic and previous_topic in TOPICS and (
            len(q.split()) <= 6 or q.lstrip().startswith(("y ", "pero", "entonces", "por que", "como asi", "explica mas"))):
        topics = [previous_topic]  # pregunta de seguimiento («¿y la tangente?», «explica más»)
    if not topics and len(tickers) >= 2:
        topics = ["compare"]
    elif not topics and tickers:
        topics = ["volatility", "return"]
    topic = topics[0] if topics else None
    sel_id = None
    if selected:
        sel_id, _label, sel_topic = selected
        q = _norm(question)
        if topic is None or any(w in q for w in ("esta", "este", "esto", "resultado", "seleccion")):
            topic = topic or sel_topic
    if topic is None:
        return Answer(topic="help", title="¿Sobre qué resultado quieres saber?",
                      simple="Puedo explicar con los valores de tu sesión: " + ", ".join(t for t, _w in TOPICS.values()) + ".",
                      interpretation="Escribe tu pregunta con uno de esos temas o elige un resultado arriba.",
                      limitations=["Solo uso los resultados que ya calculó el bot en esta sesión."])
    a = Answer(topic=topic, title=TOPICS[topic][0])
    _BUILDERS[topic](a, asset, comparison, ctx, sel_id)
    if not a.has_data and not a.indicator:
        a.indicator = ["No hay un resultado de este tipo en la sesión; la explicación es general."]
    # Lectura a fondo: el tema principal y, si la pregunta nombra otros, también esos.
    a.analysis = analyze(topic, asset, comparison, ctx, tickers, question)
    for extra in [t for t in topics[1:3] if t != topic]:
        more = analyze(extra, asset, comparison, ctx, tickers, question)
        if more:
            a.also.append(TOPICS[extra][0])
            a.analysis += [f"[{TOPICS[extra][0]}] {x}" for x in more]
    seen = []
    for x in a.analysis:  # sin repetir frases cuando dos temas leen el mismo dato
        if x not in seen:
            seen.append(x)
    a.analysis = seen[:12]
    if a.analysis:
        a.has_data = True
    a.followups = [f for f in FOLLOWUPS.get(topic, []) if _norm(f) != _norm(question)][:3]
    if a.also:
        a.title += " · " + " · ".join(a.also)
    return a


# ---------------------------------------------------------------------------
# Presentación de la respuesta (HTML; el texto se escapa)
# ---------------------------------------------------------------------------
def answer_html(a: dict, icon_fn) -> str:
    """`a` es asdict(Answer) (así se guarda en el historial). icon_fn = src.ui_fx.icon."""
    from html import escape

    def sec(ic, title, body, cls=""):
        return (f'<div class="ins-sec {cls}"><div class="ins-st">{icon_fn(ic, 14)}<span>{escape(title)}</span></div>'
                f'{body}</div>')
    parts = [f'<div class="ins-ans{" refused" if a.get("refused") else ""}"><div class="ins-title">{escape(a["title"])}</div>']
    if a.get("simple"):
        parts.append(sec("info", "Explicación sencilla", f"<p>{escape(a['simple'])}</p>"))
    if a.get("interpretation"):
        parts.append(sec("trending", "Interpretación financiera", f"<p>{escape(a['interpretation'])}</p>"))
    if a.get("analysis") and not a.get("refused"):
        items = "".join(f"<li>{escape(x)}</li>" for x in a["analysis"])
        parts.append(sec("activity", "Análisis de tus resultados",
                         '<span class="ins-badge real">Calculado con tus valores</span>' + f"<ul>{items}</ul>", "ana"))
    if a.get("indicator") and not a.get("refused"):
        badge = ('<span class="ins-badge real">Valores reales de tu sesión</span>' if a.get("has_data")
                 else '<span class="ins-badge gen">Sin resultado en la sesión · explicación general</span>')
        items = "".join(f"<li>{escape(x)}</li>" for x in a["indicator"])
        parts.append(sec("database", "Indicador utilizado", f"{badge}<ul>{items}</ul>", "ind"))
    if a.get("limitations"):
        parts.append(sec("alert", "Limitaciones", "<ul>" + "".join(f"<li>{escape(x)}</li>" for x in a["limitations"]) + "</ul>",
                         "lim"))
    if a.get("example"):
        parts.append(sec("target", "Ejemplo educativo", f"<p>{escape(a['example'])}</p>", "ex"))
    if a.get("sources"):
        parts.append('<div class="ins-src">Fuente en DPST: ' + " · ".join(escape(s) for s in a["sources"]) + "</div>")
    parts.append("</div>")
    return "".join(parts)
