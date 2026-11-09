"""
Asistente guiado del botón «¿Necesitas ayuda?» (solo contenido y lógica, sin interfaz).

No es un chatbot ni usa servicios externos: son textos escritos por el equipo y una regla
sencilla que, con el estado de la sesión, sugiere el siguiente paso de USO del bot. Nunca
recomienda comprar, vender ni invertir. Para cambiar un texto, edítalo aquí.
"""
from __future__ import annotations

from dataclasses import dataclass, field

DISCLAIMER = "Simulación académica: no es asesoría de inversión."
LAB_SECTION = "Laboratorio de portafolios"


@dataclass(frozen=True)
class HelpTopic:
    slug: str  # identificador corto (clase CSS st-key-help_sec_<slug>)
    label: str  # texto EXACTO de la pestaña del menú
    path: str  # cómo llegar: «Menú → …»
    steps: tuple  # 2-3 pasos cortos
    faqs: tuple = field(default_factory=tuple)  # (pregunta, respuesta de máximo 2 líneas)


SECTIONS = (
    HelpTopic(
        "inicio", "Inicio", "Menú → Inicio",
        ("Lee el aviso amarillo: el bot sirve para mirar y comparar, no para decidir inversiones.",
         "Sigue los 5 pasos de «Cómo usar el bot», en orden.",
         "Abajo están las noticias de la semana, solo para informarte."),
        (("¿Qué hace este bot?", "Muestra cómo les ha ido a varias empresas y simula carteras con datos del pasado."),
         ("¿Por dónde empiezo?", "Por Tickers, si no sabes el código de la empresa; si ya lo sabes, por Preselección."),
         ("¿De dónde salen los datos y qué tan actuales son?",
          "De Yahoo Finance (precios), FRED (tasas) y noticias públicas. Los precios llegan con unos minutos de retraso."),
         ("¿Se guarda lo que hago?", "Solo mientras tengas la página abierta; si la recargas, empiezas de nuevo.")),
    ),
    HelpTopic(
        "tickers", "Tickers", "Menú → Tickers",
        ("Escribe el nombre de la empresa (por ejemplo, Coca-Cola).",
         "Elige la empresa en la lista.",
         "Pulsa «Usar … en Preselección» para llevar su código al análisis."),
        (("¿Qué es un ticker?", "Es el nombre corto de una empresa en la bolsa. Apple = AAPL, Coca-Cola = KO."),
         ("¿Por qué no encuentro una empresa colombiana?",
          "El directorio es de las bolsas de EE. UU. Algunas colombianas están allí, como Ecopetrol (EC) o Bancolombia (CIB)."),
         ("¿Qué es un ETF?", "Un fondo que junta muchas acciones y se negocia como si fuera una sola.")),
    ),
    HelpTopic(
        "preseleccion", "Preselección de activos", "Menú → Preselección de activos",
        ("En «Datos del activo a probar» escribe el ticker y pulsa «Descargar y limpiar».",
         "Abre «Análisis histórico» y «Pronóstico» para ver cómo se ha comportado.",
         "En «Comparación» pon varias empresas para compararlas entre sí."),
        (("¿Por qué me sale «no señal»?",
          "Porque no se cumplen todas las condiciones de la regla (ganancia y riesgo netos). Es normal: el bot no fuerza señales."),
         ("¿Qué frecuencia elijo?", "Semanal suele tener menos ruido que diaria. Mensual sirve para mirar periodos largos."),
         ("¿Qué es el VaR?", "La pérdida que, en un periodo malo normal, no se supera. Falla en 1 de cada 20 casos (95 %)."),
         ("¿Qué significa «dominado» en la comparación?",
          "Que otra empresa del grupo ganó igual o más y se movió igual o menos al mismo tiempo.")),
    ),
    HelpTopic(
        "tasas", "Tasas soberanas", "Menú → Tasas soberanas",
        ("Escoge un país en la lista.",
         "Mira su tasa actual y cómo ha cambiado en el último año.",
         "Úsala como referencia de una ganancia «sin riesgo» en el Laboratorio."),
        (("¿Qué es una tasa soberana?", "Lo que paga el gobierno de un país por pedir dinero prestado a 10 años."),
         ("¿Por qué no aparece mi país?", "FRED no publica esa tasa para todos los países; solo aparecen los que tienen dato."),
         ("¿Por qué el dato es de hace meses?", "Algunas series se publican cada trimestre o cada año; la fecha aparece al lado.")),
    ),
    HelpTopic(
        "lab", LAB_SECTION, "Menú → Laboratorio de portafolios",
        ("En «Supuestos de la simulación» elige la Fuente (Mercado real usa tus empresas) y tu perfil de riesgo.",
         "Abre los módulos en orden, del 1 al 9; cada uno tiene su «¿Cómo leo esto?».",
         "Termina en la Ficha técnica y en Exportar para guardar lo que calculaste."),
        (("¿Qué diferencia hay entre la GMV y la tangente?",
          "La GMV es la mezcla que menos se mueve. La tangente es la que más gana por cada unidad de riesgo."),
         ("¿Por qué veo «A» y «B»?",
          "Estás en el caso docente. Cambia la Fuente a Mercado real o escribe nombres en las casillas de las empresas."),
         ("¿Qué perfil de riesgo elijo?",
          "Es una decisión del equipo: Conservador prefiere ir a la segura y Agresivo acepta más subidas y bajadas."),
         ("¿Por qué dice «inviable»?", "Los límites de peso no dejan sumar 100 %. Amplía el peso máximo por empresa.")),
    ),
    HelpTopic(
        "insights", "DPST Insights", "Menú → DPST Insights",
        ("A la izquierda escoge un resultado que ya calculaste (o «Ninguno»).",
         "Pulsa una pregunta sugerida o escribe la tuya.",
         "Lee la explicación a la derecha, en palabras simples."),
        (("¿Es una inteligencia artificial?", "No. Es un motor local del bot con textos escritos por el equipo."),
         ("¿Me dice qué hacer con mi dinero?", "No. Solo explica resultados del bot; no es asesoría de inversión."),
         ("¿Por qué no aparece mi resultado?", "Primero hay que calcularlo en las otras pestañas; luego aparece en la lista.")),
    ),
)

# Ayuda por módulo del Laboratorio, en el mismo orden que LAB_MODULES / MODULE_TITLES.
LAB_MODULE_HELP = (
    (("Mira los dos cuadros de colores: muestran si las empresas se mueven juntas.",
      "En «Prueba una cartera» escribe pesos que sumen 1 y mira su riesgo."),
     (("¿Qué es la correlación?", "Un número entre −1 y 1: 1 = se mueven igual, 0 = no tienen que ver, −1 = al revés."),
      ("¿Por qué mezclar empresas baja el riesgo?", "Porque cuando una baja, otra puede no bajar o subir y compensar."),
      ("¿Qué es la volatilidad?", "Qué tanto sube y baja el valor. Más volatilidad = más montaña rusa."))),
    (("Escribe cuánto caería una empresa de golpe y mira cuánto perdería la cartera.",
      "Revisa el escenario inverso: qué tendría que pasar para perder lo máximo que aceptas."),
     (("¿Qué es una prueba de estrés?", "Imaginar algo malo (una caída fuerte) y medir cuánto perdería la cartera."),
      ("¿Qué es la pérdida esperada (ES)?", "Cuando sí pasa algo malo, cuánto se pierde en promedio."),
      ("¿Por qué hay varios estimadores?", "Son formas distintas de medir el riesgo; si coinciden, el resultado es más confiable."))),
    (("Mira la gráfica: arriba y a la izquierda es mejor (más ganancia, menos riesgo).",
      "En la tabla de la izquierda ves cuánto va a cada empresa en cada cartera."),
     (("¿Qué diferencia hay entre la GMV y la tangente?",
       "La GMV es la mezcla que menos se mueve. La tangente es la que más gana por cada unidad de riesgo."),
      ("¿Qué es la frontera eficiente?", "La curva de las mejores mezclas: ninguna otra gana más con el mismo riesgo."),
      ("¿Qué es el óptimo personal?", "La mezcla que mejor encaja con el perfil de riesgo que elegiste arriba."))),
    (("Deja vacía la tabla de opiniones si el equipo no tiene una opinión con evidencia.",
      "Si agregan una, mira cómo cambian las expectativas y los pesos."),
     (("¿Qué es Black-Litterman?", "Un método que mezcla lo que «espera el mercado» con las opiniones del equipo."),
      ("¿Qué es una view?", "Una opinión del equipo, por ejemplo «A ganará 2 % más que B», con su nivel de confianza."),
      ("¿Qué pasa si la opinión es poco segura?", "Casi no cambia nada: el resultado se queda cerca de lo del mercado."))),
    (("Mira cuánto se desacomodó la cartera cuando cambiaron los precios.",
      "Revisa las operaciones simuladas y lo que cuestan."),
     (("¿Qué es rebalancear?", "Volver a la mezcla elegida cuando unos precios suben y otros bajan."),
      ("¿Por qué no rebalancear todos los días?", "Cada operación cuesta; a veces el beneficio no alcanza a cubrirlo."),
      ("¿El bot hace operaciones de verdad?", "No. Es una simulación: no envía órdenes a ningún intermediario."))),
    (("Elige la ventana y cada cuánto se decide, y pulsa «Ejecutar backtest».",
      "Compara las reglas con la referencia simple 1/N."),
     (("¿Qué es un backtest?", "Probar una regla con datos del pasado, usando en cada momento solo lo que ya se sabía."),
      ("¿Por qué comparar con 1/N?", "Repartir igual es la regla más simple; una regla buena debería superarla."),
      ("¿Que funcione en el pasado garantiza algo?", "No. Solo dice cómo le habría ido; el futuro puede ser distinto."))),
    (("Escribe un benchmark (por ejemplo ^GSPC) para ver la beta de cada empresa.",
      "Mira la SML: los puntos arriba de la línea ganaron más de lo que su riesgo pedía."),
     (("¿Qué es la beta?", "Qué tanto se mueve una empresa cuando se mueve el mercado. Beta 1,5 = se mueve 1,5 veces."),
      ("¿Qué es el CAPM?", "Una fórmula de cuánto debería ganar algo según su beta: tasa segura + beta × prima."),
      ("¿Qué es el WACC?", "Lo que le cuesta a una empresa conseguir dinero de sus dueños y de los bancos."))),
    (("Escoge la cartera de la que quieres ver la ficha.",
      "Lee su rentabilidad por periodos, su composición y su riesgo; puedes descargarla."),
     (("¿Qué es la ficha técnica?", "La hoja de vida de la cartera, con la estructura que usan los fondos en Colombia."),
      ("¿Por qué dice «No aplica»?", "Porque es una simulación: no hay comisiones, custodio ni calificación reales."),
      ("¿Por qué sale «N/D»?", "Esa ventana necesita más historia de la que hay en los datos elegidos."))),
    (("Revisa que diga «Traza verificada».",
      "Descarga la traza (JSON) y el snapshot (CSV) para respaldar los resultados."),
     (("¿Para qué sirve exportar?", "Para que cualquiera pueda comprobar de dónde salió cada resultado."),
      ("¿Qué es la traza?", "Un archivo con la fuente, las fechas, los supuestos y los resultados del análisis."))),
)

GLOSSARY = (
    ("Ticker", "Código corto de una empresa en la bolsa (Apple = AAPL)."),
    ("Volatilidad", "Qué tanto sube y baja el valor de algo."),
    ("Correlación", "Si dos empresas se mueven juntas (1), sin relación (0) o al revés (−1)."),
    ("Sharpe", "Ganancia extra por cada unidad de riesgo. Más alto es mejor."),
    ("Beta", "Qué tanto se mueve una empresa cuando se mueve el mercado."),
    ("Cartera", "Varias empresas juntas, con una parte del dinero en cada una."),
)

# Palabras que el asistente nunca usa: es una guía de uso, no una recomendación de inversión.
FORBIDDEN = ("compre", "venda", "compra ya", "la mejor inversión", "te recomiendo", "recomendamos",
             "deberías invertir", "invierte en", "garantiza ganancias")

PROBLEM_STATES = ("offline", "error", "nokey", "limit", "nodata")


def section_by_label(label: str) -> HelpTopic:
    return next((s for s in SECTIONS if s.label == label), SECTIONS[0])


def next_steps(*, has_asset: bool, has_comparison: bool, lab_uses_market: bool, markowitz_done: bool,
               issues: "list[tuple[str, str, str]]" = ()) -> "list[str]":
    """
    Siguiente paso de USO según el estado de la sesión (máximo 3: primero el paso principal y luego hasta 2 avisos).
    `issues`: avisos del Centro de estados como (servicio, estado visible, qué significa y cómo resolverlo).
    """
    out = []
    if not has_comparison and not has_asset:
        out.append("Ve a **Preselección de activos → Comparación** y descarga tus empresas "
                   "(si no sabes sus códigos, búscalos primero en **Tickers**).")
    elif not has_comparison:
        out.append("Para armar una cartera necesitas varias empresas: ve a **Preselección de activos → Comparación**.")
    elif not lab_uses_market:
        out.append("Ya tienes empresas: en el **Laboratorio**, en Supuestos → **Fuente**, elige **Mercado real** "
                   "para usarlas.")
    elif not markowitz_done:
        out.append("En el **Laboratorio** abre **3 · Markowitz y fronteras** para ver la mejor mezcla según el riesgo.")
    else:
        out.append("Mira la **Ficha técnica** (Laboratorio → 8 · Ficha técnica) o lee el resumen en **DPST Insights**.")
    out += [f"Hay un aviso en **{svc}** ({status}): {why}" for svc, status, why in issues][:2]
    return out[:3]


def session_summary(state, *, service_names: dict, state_labels: dict, reasons: dict, conn_key: str,
                    ctx_key: str, market_source: str) -> dict:
    """Lee el estado de sesión de Streamlit y lo resume para next_steps (sin red)."""
    asset = state.get("asset_result")
    comp = state.get("comparison_result")
    issues = []
    for svc, info in (state.get(conn_key) or {}).items():
        status = (info or {}).get("status")
        if status in PROBLEM_STATES:
            issues.append((service_names.get(svc, (svc,))[0], state_labels.get(status, (status,))[0],
                           reasons.get(status, "")))
    return {
        "has_asset": bool(asset is not None and getattr(asset, "ok", False)),
        "has_comparison": bool(comp is not None and getattr(comp, "ok", False)),
        "lab_uses_market": state.get("lab_source") == market_source,
        "markowitz_done": "markowitz" in (state.get(ctx_key) or {}) and state.get("lab_source") == market_source,
        "issues": issues,
    }


def next_target(*, has_asset: bool, has_comparison: bool, lab_uses_market: bool, markowitz_done: bool,
                **_ignored) -> "tuple[str, str, str | None, str | None]":
    """
    Botón «Ir a…» de la sugerencia principal: (texto, pestaña del menú, desplegable o None,
    módulo del laboratorio o None). Usa los mismos criterios que next_steps.
    """
    if not has_comparison:
        return ("Ir a Comparación", "Preselección de activos", "Comparación", None)
    if not lab_uses_market:
        return ("Ir al Laboratorio", LAB_SECTION, None, None)
    if not markowitz_done:
        return ("Ir a Markowitz", LAB_SECTION, None, "3 · Markowitz y fronteras")
    return ("Ir a la Ficha técnica", LAB_SECTION, None, "8 · Ficha técnica")
