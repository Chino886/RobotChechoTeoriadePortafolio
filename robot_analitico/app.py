"""
Punto de entrada de la aplicación.
Robot analítico para la preselección de activos - Teoría Moderna de
Portafolios, Tech Business School - Universidad EIA.
"""
import json

import pandas as pd
import streamlit as st

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
from src.rates import fetch_bond_series, search_bond_series
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
TEAM_NAME = "Equipo DPST"
MEMBERS = [
    "Sergio Delgado Laverde",
    "David Angel Perez",
    "Pedro Velez Uribe",
    "Tomás Giraldo Gomez",
]
VERSION = "0.1.0"
LAST_UPDATE = "2026-09-14"

EXECUTION_POLICY_SUMMARY = (
    "Piloto académico restringido. Posición larga únicamente. Rendimiento "
    "logarítmico exclusivo. El sistema puede emitir 'no señal'. No calcula "
    "portafolios, pesos, covarianzas ni frontera eficiente. Ver la vista "
    "Metodología para la política de ejecución completa."
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


def render_header() -> None:
    st.set_page_config(page_title=SYSTEM_NAME, page_icon="📊", layout="wide")
    st.title(f"📊 {SYSTEM_NAME}")
    st.caption(f"{TEAM_NAME} · versión {VERSION} · última actualización {LAST_UPDATE}")
    with st.expander("Equipo e identidad"):
        for member in MEMBERS:
            st.write(f"- {member}")
        st.info(EXECUTION_POLICY_SUMMARY)


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
    st.subheader("Antes de continuar")
    st.warning(DISCLAIMER_TEXT)

    privacy_ok = st.checkbox(
        "Autorizo el tratamiento de mis datos según el aviso de privacidad del "
        "piloto académico (Ley 1581 de 2012).",
        value=False,
        key="consent_privacy",
    )
    disclaimer_ok = st.checkbox(
        "He leído y acepto el disclaimer académico anterior.",
        value=False,
        key="consent_disclaimer",
    )

    if not (privacy_ok and disclaimer_ok):
        st.session_state["access_logged"] = False
        st.stop()

    if not st.session_state.get("access_logged", False):
        access_log.log_access(user_name, user_email, privacy_ok, disclaimer_ok)
        st.session_state["access_logged"] = True


def render_historical_analysis() -> None:
    """
    Análisis histórico de un activo (RF-09 a RF-12): rendimientos
    logarítmicos, gráficos, descriptivos y drawdown.
    """
    result = st.session_state.get("asset_result")
    frequency = st.session_state.get("asset_frequency")
    if result is None or not result.ok:
        return

    st.divider()
    st.subheader(f"Análisis histórico de {result.ticker} (RF-09 a RF-12)")

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

    st.divider()
    st.subheader(f"Pronóstico de {result.ticker} (RF-13 a RF-15)")
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
        col_v1, col_v2 = st.columns(2)
        col_v1.metric(f"VaR fraccional ({confidence_label})", f"{var_result.var_fraction:.4%}")
        col_v2.metric("VaR en unidades monetarias", f"{var_result.var_dollar:,.2f}")

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
    st.divider()
    st.subheader("Comparación de activos (RF-19 a RF-22)")
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
        st.plotly_chart(risk_return_map(result.summaries, non_dominated), use_container_width=True)
        st.caption(
            "Rombos rojos = activos NO dominados (ningún otro activo del lote ofrece a la "
            "vez media igual o mayor y volatilidad igual o menor). Esto no es una frontera "
            "eficiente de portafolios ni una recomendación de la mejor inversión universal."
        )

    with tab_select:
        st.write(
            "Regla de preselección transparente (RF-21). El resultado se expresa como "
            "'mejor según este criterio y estos parámetros', nunca como la mejor inversión "
            "en términos absolutos."
        )
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
    st.divider()
    st.subheader("Tasas de bonos soberanos por país (referencia, vía FRED)")
    st.caption(
        "Fuente: FRED (Federal Reserve Economic Data, Banco de la Reserva "
        "Federal de St. Louis). Se busca en vivo la serie real que corresponde "
        "al país indicado — nunca se asume un código de serie de antemano."
    )

    fred_api_key = st.secrets.get("FRED_API_KEY")
    if not fred_api_key:
        st.info(
            "Esta vista necesita una API key gratuita de FRED configurada en "
            "los secretos de la app (FRED_API_KEY) para funcionar."
        )
        return

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
        rates_start = st.date_input("Fecha inicial", value=pd.Timestamp("2015-01-01"), key="rates_start")
    with col2:
        rates_end = st.date_input("Fecha final", value=pd.Timestamp.today(), key="rates_end")

    if st.button("Traer serie histórica", key="rates_fetch_button"):
        with st.spinner("Descargando de FRED..."):
            try:
                series = fetch_bond_series(fred_api_key, series_id, rates_start, rates_end)
            except Exception as exc:
                st.error(f"Error al descargar la serie: {exc}")
                series = pd.Series(dtype=float)
        if series.empty:
            st.warning("No se encontraron observaciones válidas para ese rango de fechas.")
        else:
            st.line_chart(series, height=250)
            st.metric(
                "Última tasa disponible",
                f"{series.iloc[-1]:.2f}%",
                help=f"Fecha: {series.index[-1].date()}",
            )
            with st.expander("Ver datos en tabla"):
                st.dataframe(series.rename("tasa_%"))
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
    st.divider()
    st.subheader("Pronóstico por canasta de inversión (monto en USD por activo)")
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

    with st.expander(
        "ℹ️ Más información: qué significan estos parámetros y cómo funcionan los modelos"
    ):
        st.markdown(
            "#### Parámetros de entrada\n\n"
            "**Nivel de confianza del VaR (95% o 99%)**\n"
            "- Define qué tan \"exigente\" es la medida de pérdida máxima esperada "
            "(VaR). Con **95%**, el VaR es la pérdida que solo se superaría en 5 "
            "de cada 100 escenarios; con **99%**, la que solo se superaría en 1 "
            "de cada 100.\n"
            "- Por eso el VaR al 99% siempre sale **más alto** que al 95%: al "
            "querer cubrir casi todos los escenarios, incluidos los más extremos "
            "y raros, la pérdida que se toma como referencia es mayor.\n"
            "- Usa 95% para una visión de riesgo \"normal\" y 99% si quieres ser "
            "más prudente o te preocupan las caídas fuertes.\n\n"
            "**Costo de compra (c_b) y costo de venta (c_s)**\n"
            "- Representan la comisión o costo de transacción que pagas al "
            "comprar y al vender, expresado como **fracción del precio**. Por "
            "ejemplo, 0.001 = 0.1% y 0.005 = 0.5%.\n"
            "- Pon **0** si no quieres considerar comisiones, o el valor real "
            "que cobra tu bróker (si cobra 0.25% por operación, escribe 0.0025).\n"
            "- Estos costos suben el precio que el activo debe alcanzar para que "
            "no pierdas dinero (punto de equilibrio) y reducen el beneficio neto "
            "de la señal.\n\n"
            "**BR_min (beneficio/riesgo neto mínimo)**\n"
            "- Es cuánto beneficio esperado exiges **por cada unidad de riesgo** "
            "antes de considerar que hay una \"señal\" válida de entrada. Se "
            "compara con el BR_neto calculado (ganancia potencial hasta el "
            "take-profit dividida entre la pérdida potencial hasta el stop-loss, "
            "ya descontados los costos).\n"
            "- Ejemplos: **BR_min = 1** significa que exiges al menos empatar "
            "beneficio con riesgo (arriesgar $1 para ganar como mínimo $1). "
            "**BR_min = 2** significa que exiges el doble de beneficio que de "
            "riesgo (arriesgar $1 para ganar como mínimo $2).\n"
            "- Mientras más alto lo pongas, más estricto es el filtro y menos "
            "señales aparecerán.\n\n"
            "#### Cómo funcionan los modelos de pronóstico\n\n"
            "**Caminata aleatoria (sin deriva)**\n"
            "- Asume que el precio **no tiene una tendencia predecible**: cada "
            "movimiento futuro es tan probable hacia arriba como hacia abajo.\n"
            "- Solo usa qué tan **volátil** ha sido el activo históricamente para "
            "estimar qué tan amplio es el rango de precios posibles.\n"
            "- Es el modelo más **conservador/neutral**: no le da ventaja ni a la "
            "subida ni a la bajada.\n\n"
            "**Lognormal (con deriva)**\n"
            "- Además de la volatilidad histórica, asume que la **tendencia "
            "promedio** que ha tenido el activo en el pasado (subida o bajada "
            "promedio) va a continuar.\n"
            "- Es más **optimista** si el activo ha subido mucho históricamente, y "
            "más **pesimista** si ha bajado.\n\n"
            "⚠️ Ninguno de los dos modelos garantiza el futuro: son supuestos "
            "estadísticos simplificados, con fines académicos. Comparar ambos "
            "ayuda a ver qué tanto depende el resultado de suponer (o no) que la "
            "tendencia pasada se mantiene."
        )

    with st.expander("¿Qué significa cada resultado? (guía de lectura)"):
        st.markdown(
            "Para cada activo de la canasta se muestran dos modelos (caminata "
            "aleatoria y lognormal con deriva). Todos los valores en dólares se "
            "refieren al **monto que invertiste en ese activo**, proyectado al "
            "final del plazo H.\n\n"
            "**Valor esperado (mediana y media)**\n"
            "- *Mediana*: el valor \"típico\" al final del plazo. Hay un 50% de "
            "probabilidad de terminar por encima y un 50% por debajo de ese monto.\n"
            "- *Media*: el promedio de todos los escenarios posibles. Como los "
            "precios no pueden bajar de cero pero sí subir mucho, la media suele "
            "quedar algo por encima de la mediana; la mediana es la referencia "
            "más realista para un escenario normal.\n\n"
            "**Rango 90% de confianza**\n"
            "- Según el modelo, hay un 90% de probabilidad de que el valor final "
            "quede entre esos dos montos: solo un 5% de los escenarios termina por "
            "debajo del mínimo y un 5% por encima del máximo. Un rango amplio "
            "indica un activo volátil y un pronóstico más incierto.\n\n"
            "**Probabilidad de terminar por encima de lo invertido**\n"
            "- Probabilidad de que al final del plazo el precio sea mayor que el "
            "precio actual, es decir, de que la inversión valga más que hoy. No "
            "descuenta comisiones (eso se mide más abajo con el punto de "
            "equilibrio P_BE).\n\n"
            "**VaR (Valor en Riesgo)**\n"
            "- Pérdida máxima que no debería superarse en el plazo H con el nivel "
            "de confianza elegido (95% o 99%). Por ejemplo, un VaR 95% de $100 "
            "significa que solo en 5 de cada 100 escenarios se perdería más de "
            "$100. Se muestra en dólares y como porcentaje del monto invertido. "
            "No es la peor pérdida posible: es un umbral estadístico.\n\n"
            "**Validación histórica (walk-forward)**\n"
            "- Se \"retrocede en el tiempo\": en varios puntos del pasado se "
            "estima el modelo solo con los datos disponibles en ese momento (sin "
            "mirar el futuro), se pronostica H periodos hacia adelante y se "
            "compara con lo que realmente ocurrió. Así se mide qué tan confiable "
            "ha sido el modelo con ese activo.\n"
            "- *RMSE*: error promedio del pronóstico del rendimiento acumulado "
            "(logarítmico) en el plazo H. Mientras más pequeño, más cerca "
            "estuvieron los pronósticos de la realidad.\n"
            "- *Cobertura del intervalo 90%*: porcentaje de veces en que el valor "
            "real cayó dentro del rango 90% pronosticado. Lo ideal es que esté "
            "cerca de 90%; si es mucho menor, el modelo subestima el riesgo.\n"
            "- *Acierto de dirección*: porcentaje de veces en que el modelo "
            "acertó si el precio subiría o bajaría. Por encima de 50% aporta algo "
            "más que el azar. En la caminata aleatoria sin deriva no se define, "
            "porque ese modelo no predice ninguna dirección.\n"
            "- Si la muestra no alcanza, se declara *validación insuficiente* y "
            "el resultado debe tomarse con mucha cautela.\n\n"
            "**Señal de entrada/salida**\n"
            "- *Entrada (E)*: precio actual al que se compraría (posición larga).\n"
            "- *Stop-loss (SL)*: precio de salida para cortar pérdidas; corresponde "
            "al escenario pesimista (percentil 5%) del precio al final del plazo.\n"
            "- *Take-profit (TP)*: precio objetivo para tomar ganancias; corresponde "
            "al escenario optimista (percentil 95%) del precio al final del plazo.\n"
            "- *BR_neto*: relación beneficio/riesgo **después de costos** de compra "
            "(c_b) y venta (c_s): cuánto se podría ganar hasta el take-profit por "
            "cada dólar que se arriesga hasta el stop-loss. Un BR_neto de 2 "
            "significa que la ganancia potencial duplica la pérdida potencial.\n"
            "- ✅ *Señal sustentada*: se cumplen todas las condiciones (SL < E < TP, "
            "el punto de equilibrio con costos P_BE queda por debajo del TP, "
            "ganancia y riesgo netos positivos, y BR_neto ≥ BR_min). ❌ Si falla "
            "alguna, se indica el motivo y no se recomienda entrar.\n"
            "- *Probabilidad de ganar/perder*: probabilidad de que el precio final "
            "quede por encima o por debajo del punto de equilibrio P_BE, que ya "
            "incluye las comisiones de compra y venta.\n\n"
            "⚠️ Son estimaciones estadísticas basadas en el historial de precios; "
            "no garantizan resultados futuros ni constituyen una recomendación de "
            "inversión."
        )

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

        with st.spinner(f"Descargando y pronosticando {len(entries)} activo(s)..."):
            for ticker, amount in entries:
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
                    wf = walk_forward_validate(returns, fit_fn, model_label, horizon, periods_per_year)
                    signal = evaluate_signal(model, p0, horizon, risk_params)
                    probs = terminal_probabilities(model, p0, horizon, signal.p_be)

                    suficiencia_nota = (
                        ""
                        if h_max >= horizon
                        else (
                            f" ⚠️ Este plazo (H={horizon}) supera el límite de suficiencia "
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
                            f"- Validación histórica (walk-forward): {wf_texto}\n"
                            f"- {signal_texto}\n"
                            f"- Probabilidad de ganar/perder frente al punto de equilibrio "
                            f"(con costos c_b={pf_c_b}, c_s={pf_c_s}): "
                            f"{probs.prob_win:.1%} ganar / {probs.prob_lose:.1%} perder"
                        )

                st.divider()

def main() -> None:
    render_header()

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

    st.success(f"Sesión iniciada como {user_name} ({user_email})")

    st.divider()
    st.subheader("Datos: probar un activo (RF-05 a RF-07)")

    col1, col2, col3 = st.columns(3)
    with col1:
        ticker_input = st.text_input("Ticker", value="AAPL")
    with col2:
        start_date = st.date_input("Fecha inicial", value=pd.Timestamp("2023-01-01"))
    with col3:
        end_date = st.date_input("Fecha final", value=pd.Timestamp.today())

    frequency = st.selectbox("Frecuencia", list(FREQUENCY_RULES.keys()))

    if st.button("Descargar y limpiar"):
        with st.spinner("Descargando..."):
            result = fetch_asset_data(ticker_input, start_date, end_date)
            if result.ok:
                result.prices = resample_prices(result.prices, frequency)

        if result.ok:
            st.session_state["asset_result"] = result
            st.session_state["asset_frequency"] = frequency
            st.success(
                f"{result.ticker}: {len(result.prices)} observaciones · "
                f"fuente: {result.source} · moneda: {result.currency or 'N/D'} · "
                f"zona horaria: {result.timezone or 'N/D'} · "
                f"último dato: {result.prices.index.max().date()}"
            )
            if result.dropped_rows:
                st.warning(
                    f"Se descartaron {result.dropped_rows} filas inválidas "
                    "(faltantes o precios no positivos)."
                )
            st.dataframe(result.prices.tail(20))
        else:
            st.session_state.pop("asset_result", None)
            st.error(f"{result.ticker}: {result.error}")

    render_historical_analysis()
    render_forecast()
    render_comparison()
    render_portfolio_forecast()
    render_sovereign_rates()

    if not DEV_MODE and st.button("Cerrar sesión"):
        st.logout()
if __name__ == "__main__":
    main()
