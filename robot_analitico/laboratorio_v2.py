"""
Laboratorio de portafolios v2 (interfaz). Paquete docente v2: riesgo conjunto,
Markowitz, Black-Litterman, rebalanceo simulado, beta/CAPM y valoración,
más el panel de cotización en línea.

Solo presenta y conecta: los cálculos están en src/portfolio.py,
src/black_litterman.py, src/rebalance.py, src/capm.py y src/market.py, con
sus pruebas. Las decisiones financieras (universo, rf, gamma, cotas, views,
política de rebalanceo, benchmark, proyecciones) son del equipo: aquí son
entradas editables, con valores iniciales tomados del caso docente de
control y rotulados como tales.
"""
import hashlib
import json
import platform
import subprocess
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.black_litterman import View, absolute_total_to_excess, build_view_set, implied_prior, posterior
from src.capm import (
    beta_ols,
    cost_of_equity,
    discounted_cash_flow,
    equity_value,
    fcff,
    nominal_rate_to_other_currency,
    relever_beta,
    sml_required_return,
    stable_reinvestment_rate,
    unlever_beta,
    wacc,
)
from src.charts import DARK_LAYOUT, ELECTRIC_BLUE, NEON_GREEN, STAR_GOLD
from src.data import fetch_asset_data, resample_prices
from src.market import fetch_quote, format_age
from src.portfolio import (
    correlation_matrix,
    covariance_matrix,
    diagnose_covariance,
    drawdown_from_returns,
    efficient_frontier,
    max_expected_return,
    max_sharpe,
    min_variance,
    optimal_risky_share,
    optimal_risky_share_no_debt,
    personal_optimum,
    portfolio_return_series,
    portfolio_stats,
    random_portfolios,
    rf_per_period,
    risk_contributions,
    rolling_correlation,
    rolling_volatility,
    simple_returns_matrix,
    weighted_average_volatility,
)
from src.rebalance import Book, plan_rebalance

PAQUETE_DATA = Path(__file__).parent / "paquete_v2" / "data"

SOURCE_TWO = "Caso docente de dos activos (control)"
SOURCE_SYNTH = "Laboratorio sintético: 20 series del paquete"
SOURCE_MARKET = "Mercado: activos de la Comparación (Yahoo Finance)"

LAYOUT = dict(margin=dict(t=50, b=40, l=40, r=20), **DARK_LAYOUT)


# ---------------------------------------------------------------------------
# Datos de entrada
# ---------------------------------------------------------------------------

def _load_json(name: str) -> dict:
    return json.loads((PAQUETE_DATA / name).read_text())


class LabData:
    """mu y Sigma en la frecuencia nativa, más la muestra de retornos si existe."""

    def __init__(self, source, mu, sigma, periods_per_year, returns=None, n_before=None, label=""):
        self.source = source
        self.mu = mu
        self.sigma = sigma
        self.m = periods_per_year
        self.returns = returns
        self.n_before = n_before
        self.label = label


def _load_lab_data(source: str):
    if source == SOURCE_TWO:
        d = _load_json("dos_activos.json")
        mu = pd.Series(d["mu"], index=d["assets"])
        sigma = pd.DataFrame(d["Sigma"], index=d["assets"], columns=d["assets"])
        return LabData(source, mu, sigma, 1, label="Parámetros anuales dados por el caso (no hay serie de precios).")
    if source == SOURCE_SYNTH:
        prices = pd.read_csv(PAQUETE_DATA / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
        return prices, 252, "Calendario lunes-viernes didáctico (NO bursátil); 252 periodos por año como convención."
    result = st.session_state.get("comparison_result")
    if result is None or not getattr(result, "ok", False) or not result.common_prices:
        return None
    prices = pd.DataFrame(result.common_prices).sort_index()
    return prices, result.periods_per_year, (
        f"Precios de la sección Comparación: frecuencia {result.frequency}, moneda {result.base_currency}, "
        f"{result.common_start.date()} a {result.common_end.date()}."
    )


def _from_prices(source, prices, m, label, assets):
    sample = simple_returns_matrix(prices[assets])
    returns = sample.returns
    return LabData(source, returns.mean(), covariance_matrix(returns), m, returns, sample.n_before, label)


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------

def _pct(x, digits=2):
    return "N/D" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}%}"


def _explain(title: str, body: str):
    with st.expander(f"ℹ️ {title}"):
        st.markdown(body)


def _heatmap(matrix: pd.DataFrame, title: str, zmid=None, fmt=".2f"):
    fig = go.Figure(go.Heatmap(
        z=matrix.to_numpy(), x=list(matrix.columns), y=list(matrix.index), zmid=zmid,
        colorscale=[[0, "#2DE1FC"], [0.5, "#1A1F2B"], [1, "#00FFA3"]] if zmid is not None else "Teal",
        texttemplate="%{z:" + fmt + "}" if len(matrix) <= 12 else None, hoverongaps=False,
    ))
    fig.update_layout(title=title, height=420 if len(matrix) > 6 else 320, **LAYOUT)
    return fig


def _git_commit() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent, capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "no disponible"
    except Exception:
        return "no disponible"


# ---------------------------------------------------------------------------
# Cotización en línea (reloj de cotización)
# ---------------------------------------------------------------------------

def _render_live_quote():
    st.markdown("#### 📡 Cotización en línea (reloj de cotización)")
    st.caption(
        "Consulta la última barra de 1 minuto de Yahoo Finance. «Consultado ahora» no significa "
        "«negociado ahora»: Yahoo publica con retraso según la bolsa, y fuera de sesión se muestra el "
        "último dato disponible. No se guardan ni redistribuyen cotizaciones."
    )
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        ticker = st.text_input("Ticker a seguir", value="AAPL", key="lab_quote_ticker")
    with c2:
        every = st.number_input("Actualizar cada (s)", min_value=15, max_value=600, value=60, step=15, key="lab_quote_every")
    with c3:
        auto = st.toggle("Actualización automática", value=False, key="lab_quote_auto")

    @st.fragment(run_every=timedelta(seconds=int(every)) if auto else None)
    def _quote_panel():
        if not auto and not st.button("Consultar ahora", key="lab_quote_btn"):
            last = st.session_state.get("lab_last_quote")
            if last is None or last.ticker != (ticker or "").strip().upper():
                st.caption("Pulsa «Consultar ahora» o activa la actualización automática.")
                return
            q, repeated = last, None
        else:
            prev = st.session_state.get("lab_last_quote")
            q = fetch_quote(ticker)
            repeated = q.same_data_as(prev)
            if q.ok:
                st.session_state["lab_last_quote"] = q
        if not q.ok:
            st.error(f"{q.ticker}: {q.error}")
            return
        m1, m2, m3, m4 = st.columns(4)
        m1.metric(f"{q.ticker} ({q.currency or 'N/D'})", f"{q.price:,.4f}")
        m2.metric("Antigüedad del dato", format_age(q.age_seconds))
        m3.metric("Sesión", q.session)
        m4.metric("Bolsa", q.exchange or "N/D")
        st.caption(
            f"Tipo de precio: {q.price_type}. Última barra: {q.last_bar_at:%Y-%m-%d %H:%M} UTC · "
            f"recibido: {q.received_at:%Y-%m-%d %H:%M:%S} UTC · zona de la bolsa: {q.timezone or 'N/D'}."
            + (" · ⏸️ Dato repetido: no es una observación nueva." if repeated else "")
        )

    _quote_panel()


# ---------------------------------------------------------------------------
# Pestañas
# ---------------------------------------------------------------------------

def _weights_editor(assets, key, default=None):
    default = default if default is not None else pd.Series(1 / len(assets), index=assets)
    df = pd.DataFrame({"activo": assets, "peso": [float(default.get(a, 0.0)) for a in assets]})
    edited = st.data_editor(df, key=f"{key}_{abs(hash(tuple(assets)))}", hide_index=True, disabled=["activo"],
                            column_config={"peso": st.column_config.NumberColumn("peso", format="%.4f", step=0.01)})
    return pd.Series(edited["peso"].to_numpy(dtype=float), index=edited["activo"])


def _tab_risk(lab: LabData):
    m = lab.m
    diag = diagnose_covariance(lab.sigma)
    corr = correlation_matrix(lab.sigma)
    st.markdown(
        f"**Muestra:** {len(lab.returns) if lab.returns is not None else 'parámetros dados'} observaciones comunes"
        + (f" (de {lab.n_before} antes de la máscara común)" if lab.n_before is not None else "")
        + f" · **Matriz:** {diag.status} · rango {diag.rank}/{diag.n_assets} · "
        f"condicionamiento {diag.condition_number:,.1f}"
    )
    if diag.zero_variance_assets:
        st.warning(f"Varianza cero (correlación indefinida): {', '.join(diag.zero_variance_assets)}")
    c1, c2 = st.columns(2)
    c1.plotly_chart(_heatmap(lab.sigma * m, "Covarianza anualizada (decimal²)", fmt=".4f"))
    c2.plotly_chart(_heatmap(corr, "Correlación (sin unidad)", zmid=0))

    st.markdown("**Prueba una cartera** (los pesos los eliges tú; deben sumar 1):")
    w = _weights_editor(list(lab.mu.index), "lab_risk_weights")
    if abs(w.sum() - 1) > 1e-6:
        st.error(f"Los pesos suman {w.sum():.4f}: una cartera necesita pesos que sumen 1.")
        return
    stats = portfolio_stats(w, lab.mu, lab.sigma)
    rc = risk_contributions(w, lab.sigma)
    a, b, c = st.columns(3)
    a.metric("Rendimiento esperado (anual)", _pct(stats.mean * m))
    b.metric("Volatilidad de la cartera (anual)", _pct(stats.volatility * np.sqrt(m)))
    c.metric("Promedio ponderado de volatilidades", _pct(weighted_average_volatility(w, lab.sigma) * np.sqrt(m)),
             help="NO es el riesgo de la cartera: ignora la diversificación por correlación.")
    if rc.zero_risk:
        st.info("La cartera no tiene riesgo estimado: las contribuciones no se calculan (no se divide por cero).")
    else:
        fig = go.Figure(go.Bar(x=list(rc.percent.index), y=rc.percent.to_numpy(),
                               marker_color=[NEON_GREEN if v >= 0 else ELECTRIC_BLUE for v in rc.percent]))
        fig.update_layout(title="Contribución de cada activo al riesgo (% de la volatilidad)", yaxis_tickformat=".0%", height=320, **LAYOUT)
        st.plotly_chart(fig)

    if lab.returns is not None and len(lab.returns) > 30:
        window = st.slider("Ventana móvil (observaciones)", 10, min(250, len(lab.returns) - 1), min(60, len(lab.returns) // 3),
                           key="lab_window")
        rp = portfolio_return_series(lab.returns, w)
        vol = rolling_volatility(pd.concat([lab.returns, rp], axis=1), window) * np.sqrt(m)
        fig = go.Figure()
        for col in vol.columns:
            is_p = col == "cartera"
            fig.add_trace(go.Scatter(x=vol.index, y=vol[col], name=col, mode="lines",
                                     line=dict(width=3 if is_p else 1, color=NEON_GREEN if is_p else None),
                                     opacity=1 if is_p else 0.45))
        fig.update_layout(title=f"Volatilidad móvil anualizada ({window} obs.) — cartera vs. activos", yaxis_tickformat=".0%",
                          height=360, **LAYOUT)
        st.plotly_chart(fig)
        c1, c2 = st.columns(2)
        assets = list(lab.returns.columns)
        x = c1.selectbox("Correlación móvil entre", assets, index=0, key="lab_rc_a")
        y = c2.selectbox("y", assets, index=min(1, len(assets) - 1), key="lab_rc_b")
        rcorr = rolling_correlation(lab.returns[x], lab.returns[y], window)
        dd = drawdown_from_returns(rp)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rcorr.index, y=rcorr, name=f"corr {x}-{y}", line=dict(color=ELECTRIC_BLUE)))
        fig.add_trace(go.Scatter(x=dd.index, y=dd, name="drawdown cartera", line=dict(color=NEON_GREEN), yaxis="y2"))
        fig.update_layout(title="Correlación móvil y caída desde el máximo (drawdown) de la cartera", height=340,
                          yaxis=dict(title="correlación", range=[-1, 1]),
                          yaxis2=dict(title="drawdown", overlaying="y", side="right", tickformat=".0%"), **LAYOUT)
        st.plotly_chart(fig)
        st.caption("Pesos constantes: equivale a rebalancear a esos pesos cada periodo, sin costos (mantener cantidades es otra contabilidad).")

    _explain("¿Qué significan la covarianza, la correlación y el riesgo de cartera?", """
- **Varianza / volatilidad:** cuánto se mueve el rendimiento de un activo alrededor de su promedio.
- **Covarianza (Σ):** si dos activos tienden a moverse juntos (positiva) o en sentido contrario (negativa). Se calcula
  con una muestra común de fechas: Σ = (R − μ)'(R − μ)/(T − 1).
- **Correlación:** la covarianza "normalizada" entre −1 y 1. Si un activo no se mueve (varianza 0), su correlación
  **no existe** (sale vacía, no se fuerza un número).
- **Riesgo de la cartera:** σ_p = √(w'Σw). Depende de las correlaciones, por eso es **menor** que el promedio
  ponderado de volatilidades cuando los activos no se mueven idénticos: eso es la diversificación.
- **Contribución al riesgo:** cuánto aporta cada activo a σ_p; suman exactamente σ_p. Una contribución negativa
  significa que ese activo cubre a los demás.
- **Matriz PSD / singular:** una covarianza válida es "semidefinida positiva". Si es singular (por ejemplo, dos
  activos idénticos) no tiene inversa y algunos cálculos analíticos no aplican; se informa, no se repara en silencio.
- **Retornos simples vs. logarítmicos:** para la cartera se usan retornos simples, porque R_p = Σ w_i R_i. Con +10 % y
  −10 % a partes iguales la cartera rinde 0 %, pero el promedio de los logaritmos da negativo: no son lo mismo.
""")


def _tab_markowitz(lab: LabData, rf_ea: float, gamma: float, bounds):
    m = lab.m
    rf = rf_per_period(rf_ea, m)
    with st.spinner("Optimizando..."):
        gmv = min_variance(lab.mu, lab.sigma, bounds)
        tangent = max_sharpe(lab.mu, lab.sigma, rf, bounds)
        personal = personal_optimum(lab.mu, lab.sigma, gamma, bounds)
        top = max_expected_return(lab.mu, bounds, lab.sigma)
        frontier = efficient_frontier(lab.mu, lab.sigma, bounds, n_points=30)
        cloud = random_portfolios(lab.mu, lab.sigma, bounds, n=1500)

    ann_mu, ann_vol = (lambda x: x * m), (lambda x: x * np.sqrt(m))
    fig = go.Figure()
    if not cloud.empty:
        fig.add_trace(go.Scatter(x=ann_vol(cloud["volatilidad"]), y=ann_mu(cloud["media"]), mode="markers", name="Carteras al azar (ilustrativas)",
                                 marker=dict(size=3, color="rgba(230,230,230,0.18)"), hoverinfo="skip"))
    for branch, color, dash in (("eficiente", NEON_GREEN, None), ("no eficiente", ELECTRIC_BLUE, "dot")):
        part = frontier[(frontier["rama"] == branch) & (frontier["estado"] == "óptimo")]
        if not part.empty:
            fig.add_trace(go.Scatter(x=ann_vol(part["volatilidad"]), y=ann_mu(part["objetivo"]), mode="lines",
                                     name=f"Frontera {branch}", line=dict(color=color, width=3, dash=dash)))
    if tangent.ok:
        ys = np.linspace(0, 1, 20)
        fig.add_trace(go.Scatter(x=ann_vol(ys * tangent.volatility), y=[ann_mu(rf + y * (tangent.mean - rf)) for y in ys],
                                 mode="lines", name="CAL (rf → tangente, sin deuda)", line=dict(color=STAR_GOLD, dash="dash")))
    for res, symbol, color in ((gmv, "diamond", ELECTRIC_BLUE), (tangent, "star", STAR_GOLD),
                               (personal, "circle", "#FF6B6B"), (top, "triangle-up", NEON_GREEN)):
        if res.ok:
            fig.add_trace(go.Scatter(x=[ann_vol(res.volatility)], y=[ann_mu(res.mean)], mode="markers", name=res.name,
                                     marker=dict(size=15, symbol=symbol, color=color, line=dict(width=1, color="white"))))
    for asset in lab.mu.index:
        fig.add_trace(go.Scatter(x=[ann_vol(np.sqrt(lab.sigma.loc[asset, asset]))], y=[ann_mu(lab.mu[asset])], mode="markers+text",
                                 text=[asset], textposition="top center", showlegend=False,
                                 marker=dict(size=7, color="rgba(230,230,230,0.7)")))
    fig.update_layout(title="Frontera de mínima varianza calculada por optimización", xaxis_title="Volatilidad anualizada",
                      yaxis_title="Rendimiento esperado anualizado", xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=520, **LAYOUT)
    st.plotly_chart(fig)

    rows = []
    for res in (gmv, tangent, personal, top):
        sharpe = (res.mean - rf) / res.volatility if res.ok and res.volatility > 0 else np.nan
        row = {"cartera": res.name, "estado": res.status, "rendimiento anual": ann_mu(res.mean) if res.ok else np.nan,
               "volatilidad anual": ann_vol(res.volatility) if res.ok else np.nan,
               "Sharpe (por periodo)": sharpe, "cotas activas": ", ".join(res.active_bounds) or "ninguna"}
        if res.ok:
            row.update({a: res.weights[a] for a in lab.mu.index})
        rows.append(row)
    table = pd.DataFrame(rows).set_index("cartera")
    st.dataframe(table.style.format({c: "{:.2%}" for c in ["rendimiento anual", "volatilidad anual", *lab.mu.index]} | {"Sharpe (por periodo)": "{:.3f}"},
                                    na_rep="—"))
    for res in (gmv, tangent, personal, top):
        if not res.ok:
            st.warning(f"**{res.name}:** {res.status}. {res.message}")
    st.caption(f"Solver: {gmv.solver}. Residual de presupuesto de la GMV: {gmv.budget_residual:.1e}. "
               f"rf del periodo = (1 + {rf_ea:.2%})^(1/{m}) − 1 = {rf:.6f}.")

    if tangent.ok:
        y_free = optimal_risky_share(rf, tangent.mean, tangent.volatility, gamma)
        y_nodebt = optimal_risky_share_no_debt(rf, tangent.mean, tangent.volatility, gamma)
        st.markdown(
            f"**Línea de asignación de capital (CAL):** con γ = {gamma:g}, la fracción óptima en la tangente sería "
            f"y* = {y_free:.2f}" + (" (pide endeudarse)" if y_free > 1 else "") +
            f"; sin deuda ni cortos en el activo libre de riesgo, y = {y_nodebt:.2f}. "
            "Ojo: si se prohíbe deuda, recortar y no prueba que la tangente siga siendo la mejor; por eso también se "
            "muestra el óptimo personal resuelto directamente dentro de las cotas."
        )

    _explain("¿Qué significa cada cartera y cada línea?", """
- **Frontera eficiente (verde):** para cada rendimiento objetivo, la cartera de **menor riesgo posible** dentro de las
  reglas de pesos. Se calcula resolviendo una optimización por cada punto, no con la nube de puntos.
- **Frontera no eficiente (azul punteada):** la parte de abajo de la curva: mismo riesgo pero **menos** rendimiento.
  Nadie racional elegiría esas carteras; se muestra para entender la forma completa.
- **Nube gris:** carteras al azar que cumplen las reglas. Sirve para ver el "espacio posible", pero no prueba dónde
  está la frontera.
- **Mínima varianza global (rombo):** la cartera de menor riesgo de todas. Solo depende de Σ y de las cotas, **no** de
  los rendimientos esperados.
- **Tangente (estrella):** la de mayor **Sharpe** (rendimiento extra sobre la tasa libre de riesgo por unidad de riesgo).
  Es la que toca la línea que sale de rf. No es automáticamente la mejor para ti.
- **Óptimo personal (círculo):** la que maximiza tu utilidad U = w'μ − (γ/2)·w'Σw. **γ (aversión al riesgo) la decide el
  equipo**: γ alto castiga más el riesgo y lleva hacia la mínima varianza; γ bajo, hacia el máximo rendimiento.
- **Máximo rendimiento esperado (triángulo):** el mayor w'μ posible; suele concentrarse en un solo activo. Sin límites a
  los pesos sería **no acotado** (apalancamiento infinito).
- **CAL (línea dorada):** combinaciones entre el activo libre de riesgo y la tangente. Su pendiente es el Sharpe.
- **Estados:** "inviable" = las reglas no se pueden cumplir; "no acotado" = sin límite; "premio no positivo" = ninguna
  cartera supera rf. Son situaciones distintas y se muestran tal cual.
- **CML y SML:** la CML supone un portafolio de mercado eficiente (equilibrio); con un universo limitado se muestra la
  CAL. La SML usa **beta** en el eje horizontal y está en la pestaña de CAPM.
""")
    return {"gmv": gmv, "tangent": tangent, "personal": personal, "top": top}


def _views_editor(assets, default_views):
    st.markdown("**Opiniones (views) del equipo.** Déjalo vacío si no hay evidencia: no se inventa convicción.")
    df = pd.DataFrame(default_views, columns=["id", "tipo", "activo", "contra", "Q", "Q es", "omega", "confianza", "vence", "tesis"])
    df = df.astype({"id": "object", "tipo": "object", "activo": "object", "contra": "object", "Q es": "object", "tesis": "object",
                    "Q": "float64", "omega": "float64", "confianza": "float64"})
    df["vence"] = pd.to_datetime(df["vence"])
    edited = st.data_editor(
        df, key="lab_bl_views", num_rows="dynamic", hide_index=True,
        column_config={
            "tipo": st.column_config.SelectboxColumn("tipo", options=["absoluta", "relativa"], required=True),
            "activo": st.column_config.SelectboxColumn("activo", options=assets, required=True),
            "contra": st.column_config.SelectboxColumn("contra (solo relativa)", options=assets),
            "Q": st.column_config.NumberColumn("Q (decimal)", format="%.4f"),
            "Q es": st.column_config.SelectboxColumn("Q es", options=["exceso", "total"]),
            "omega": st.column_config.NumberColumn("Ω varianza (opcional)", format="%.6f"),
            "confianza": st.column_config.NumberColumn("confianza 0-1 (si no hay Ω)", min_value=0.0, max_value=1.0, format="%.2f"),
            "vence": st.column_config.DateColumn("vence"),
        },
    )
    return edited


def _tab_black_litterman(lab: LabData, rf_ea: float, gamma: float, bounds):
    m = lab.m
    rf = rf_per_period(rf_ea, m)
    assets = list(lab.mu.index)
    is_control = lab.source == SOURCE_TWO
    ctrl = _load_json("black_litterman_control.json")
    st.caption("Todo en **excesos** sobre rf, en la frecuencia de los datos." +
               (" Valores iniciales tomados de black_litterman_control.json (sintético, no opinión del equipo)." if is_control else ""))
    c1, c2, c3 = st.columns(3)
    delta = c1.number_input("δ (aversión implícita del mercado de referencia)", min_value=0.01,
                            value=float(ctrl["delta"]), step=0.5, key="lab_bl_delta")
    tau = c2.number_input("τ (incertidumbre del prior)", min_value=0.001, value=float(ctrl["tau"]), step=0.01, format="%.3f", key="lab_bl_tau")
    c3.metric("rf del periodo", f"{rf:.6f}")

    st.markdown("**Cartera de referencia w_ref** (capitalización o referencia estratégica documentada — decisión del equipo):")
    ref_default = pd.Series(ctrl["w_ref"], index=ctrl["assets"]) if is_control else pd.Series(1 / len(assets), index=assets)
    if not is_control:
        st.caption("Inicial 1/N solo como marcador: un universo parcial no es el «mercado».")
    w_ref = _weights_editor(assets, "lab_bl_wref", ref_default)
    if abs(w_ref.sum() - 1) > 1e-6:
        st.error(f"w_ref suma {w_ref.sum():.4f}; debe sumar 1.")
        return None

    if is_control:
        Q, Om = ctrl["Q"], ctrl["Omega"]
        default_views = [
            ["V1", "absoluta", "A", None, Q[0], "exceso", Om[0][0], None, None, ctrl["descripcion"][0]],
            ["V2", "relativa", "A", "B", Q[1], "exceso", Om[1][1], None, None, ctrl["descripcion"][1]],
        ]
    else:
        default_views = []
    edited = _views_editor(assets, default_views)

    views = []
    for _, r in edited.dropna(subset=["id", "activo", "Q"]).iterrows():
        if r["tipo"] == "relativa":
            if pd.isna(r.get("contra")) or r["contra"] == r["activo"]:
                st.warning(f"View {r['id']}: una relativa necesita un activo «contra» distinto.")
                continue
            p_row = {r["activo"]: 1.0, r["contra"]: -1.0}
        else:
            p_row = {r["activo"]: 1.0}
        q = float(r["Q"])
        if not pd.isna(r.get("Q es")) and r.get("Q es") == "total":
            q = absolute_total_to_excess(q, rf, p_row_sum=sum(p_row.values()))
        omega = None if pd.isna(r.get("omega")) else float(r["omega"])
        conf = None if pd.isna(r.get("confianza")) else float(r["confianza"])
        exp = r.get("vence")
        exp = None if exp is None or pd.isna(exp) else pd.Timestamp(exp).date()
        views.append(View(str(r["id"]), p_row, q, omega=omega, confidence=conf, expires_at=exp, thesis=str(r.get("tesis") or "")))

    try:
        prior = implied_prior(lab.sigma, w_ref, delta)
        vs = build_view_set(views, assets, lab.sigma, tau, as_of=date.today())
        res = posterior(lab.sigma, prior, tau, vs)
    except ValueError as exc:
        st.error(str(exc))
        return None
    for vid, reason in vs.excluded.items():
        st.warning(f"View {vid} excluida: {reason}")
    for w in vs.warnings:
        st.warning(w)

    hist_excess = lab.mu - rf
    comp = pd.DataFrame({"histórico (exceso)": hist_excess, "prior π": res.prior, "posterior BL": res.posterior}) * m
    st.markdown(f"**Expectativas anualizadas en exceso** · views usadas: {res.n_views}")
    st.dataframe(comp.style.format("{:.2%}"))
    if res.view_residuals is not None:
        st.caption("Residual P·μ_BL − Q por view (anual): " + ", ".join(f"{k}: {v * m:+.2%}" for k, v in res.view_residuals.items()))

    def opt(mu_excess, sigma, label):
        return personal_optimum(mu_excess + rf, sigma, gamma, bounds), label

    cases = [opt(lab.mu - rf, lab.sigma, "Histórico"), opt(res.prior, lab.sigma, "Prior (sin views)"),
             opt(res.posterior, lab.sigma, "Posterior BL (Σ fija)"),
             opt(res.posterior, res.sigma_predictive, "Posterior BL (Σ predictiva)")]
    rows = {}
    for r_, label in cases:
        if r_.ok:
            rows[label] = r_.weights
        else:
            st.warning(f"{label}: {r_.status}. {r_.message}")
    if rows:
        wdf = pd.DataFrame(rows).T
        fig = go.Figure()
        for asset in wdf.columns:
            fig.add_trace(go.Bar(name=asset, x=list(wdf.index), y=wdf[asset]))
        fig.update_layout(barmode="stack", title=f"Pesos del óptimo personal (γ = {gamma:g}) según la expectativa usada",
                          yaxis_tickformat=".0%", height=380, **LAYOUT)
        st.plotly_chart(fig)
        st.caption("La comparación principal cambia solo μ (misma Σ y mismas cotas). La variante con Σ predictiva = Σ + M se "
                   "muestra aparte porque mezcla incertidumbre de la media con riesgo.")

    _explain("¿Qué significa Black-Litterman?", """
- **Idea:** en vez de confiar ciegamente en los rendimientos históricos (muy ruidosos), se parte de un **prior**: los
  rendimientos que "justificarían" una cartera de referencia, π = δ·Σ·w_ref. Luego se **mezclan** con las opiniones del
  equipo según cuánta confianza tengan. El resultado es la **posterior**, que después se optimiza igual que en Markowitz.
- **δ:** aversión al riesgo implícita de la cartera de referencia. **γ** es la del inversionista (otra cosa).
- **τ:** cuánta incertidumbre hay sobre el prior. Escala la matriz B = τ·Σ.
- **View absoluta:** "A rendirá 3 % en exceso". **View relativa:** "A rendirá 1 punto menos que B". Si escribes una
  absoluta en rendimiento **total**, se convierte a exceso restando rf.
- **Ω (omega):** la incertidumbre de cada view (varianza). Ω grande ⇒ la view casi no mueve nada; Ω = 0 ⇒ certeza
  total (la posterior cumple la view exactamente). **Confianza 0 excluye la view**, no la vuelve certeza.
- **M:** incertidumbre que queda sobre la **media** después de las views (no es riesgo de los retornos). **Σ predictiva**
  = Σ + M se usa solo como variante etiquetada.
- **Controles:** sin views la posterior es igual al prior; si una view dice exactamente lo que el prior ya implica, nada
  cambia. Las views vencidas, repetidas o contradictorias se excluyen o se advierten.
""")
    return res


def _tab_rebalance(rf_ea: float):
    ctrl = _load_json("rebalanceo_control.json")
    st.caption("Simulación contable (paper trading): no hay bróker ni órdenes reales. Valores iniciales de "
               "rebalanceo_control.json (sintético). La política la define el equipo.")
    assets = ctrl["assets"]
    base = pd.DataFrame({
        "activo": assets, "cantidad": ctrl["cantidades"], "precio anterior": ctrl["precios_iniciales"],
        "precio nuevo": ctrl["precios_nuevos"], "peso objetivo": ctrl["pesos_objetivo"],
    })
    edited = st.data_editor(base, key="lab_reb_book", num_rows="dynamic", hide_index=True)
    c1, c2, c3, c4 = st.columns(4)
    cash = c1.number_input("Caja inicial", value=float(ctrl["caja"]), step=100.0, key="lab_reb_cash")
    cost = c2.number_input("Costo por nominal negociado", value=float(ctrl["costo_por_nominal"]), min_value=0.0, step=0.0005,
                           format="%.4f", key="lab_reb_cost")
    band = c3.number_input("Banda de no operación (deriva máx.)", value=0.05, min_value=0.0, max_value=1.0, step=0.01,
                           format="%.2f", key="lab_reb_band", help="Valor de ejemplo: la banda es decisión del equipo.")
    fractional = c4.toggle("Fracciones de unidad", value=bool(ctrl["fracciones"]), key="lab_reb_frac")
    edited = edited.dropna(subset=["activo"])
    if edited.empty:
        return
    idx = edited["activo"].astype(str)
    q = pd.Series(edited["cantidad"].to_numpy(dtype=float), index=idx)
    p0 = pd.Series(edited["precio anterior"].to_numpy(dtype=float), index=idx)
    p1 = pd.Series(edited["precio nuevo"].to_numpy(dtype=float), index=idx)
    target = pd.Series(edited["peso objetivo"].to_numpy(dtype=float), index=idx)
    if (p0 <= 0).any() or (p1 <= 0).any():
        st.error("Los precios deben ser positivos.")
        return
    book = Book(quantities=q, cash=cash, currency=ctrl["moneda"])
    w_before_prices = book.weights(p0)
    w_now = book.weights(p1)
    drift = (w_now - target).abs().max()
    a, b, c = st.columns(3)
    a.metric("Patrimonio antes", f"{book.equity(p1):,.2f} {ctrl['moneda']}")
    b.metric("Deriva máxima vs. objetivo", _pct(drift))
    c.metric("Decisión según banda", "Rebalancear" if drift > band else "Abstenerse")
    st.dataframe(pd.DataFrame({"peso con precios anteriores": w_before_prices, "peso con precios nuevos (deriva)": w_now,
                               "objetivo": target}).style.format("{:.2%}"))
    if drift <= band:
        st.info(f"La deriva ({drift:.2%}) está dentro de la banda ({band:.2%}): la política indica **no operar**. "
                "Abstenerse es una decisión válida y queda registrada.")
    try:
        plan = plan_rebalance(book, p1, target, cost, fractional=fractional)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.markdown("**Si se rebalancea:**" if drift <= band else "**Operaciones simuladas:**")
    st.dataframe(pd.DataFrame({
        "operación (valor)": plan.trades_value, "operación (unidades)": plan.trades_quantity,
        "cantidad final": plan.new_book.quantities, "peso final": plan.weights_after,
    }).style.format({"operación (valor)": "{:+,.2f}", "operación (unidades)": "{:+,.4f}", "cantidad final": "{:,.4f}", "peso final": "{:.2%}"}))
    a, b, c, d = st.columns(4)
    a.metric("Nominal negociado", f"{plan.traded_notional:,.2f}")
    b.metric("Costos", f"{plan.costs:,.2f}")
    c.metric("Rotación (turnover)", _pct(plan.turnover))
    d.metric("Caja final", f"{0.0 if abs(plan.cash_after) < 0.005 else plan.cash_after:,.2f}")
    if plan.cash_after < -1e-9:
        st.error("La operación dejaría caja negativa: no se permite deuda no autorizada.")
    st.caption(f"Patrimonio después de costos: {plan.equity_after:,.2f} (= {plan.equity_before:,.2f} − {plan.costs:,.2f}). "
               "La evaluación temporal (walk-forward con varias estrategias) está pendiente.")

    _explain("¿Qué significa rebalancear y cómo se decide?", """
- **Deriva:** si no haces nada, los pesos cambian solos porque cada activo rinde distinto: w_nuevo = w_anterior·(1+R_i)/(1+R_p).
- **Rebalancear:** comprar y vender para volver a los pesos objetivo. Cuesta dinero (comisiones), así que no siempre conviene.
- **Política del equipo:** una **regla periódica** (cada X días) y/o una **regla por umbral** (si la deriva supera una
  banda, o si hay un evento: noticia, cambio de riesgo, vencimiento de una view). Fuera de eso, **abstenerse** también es
  una decisión correcta.
- **Costos:** se cobran sobre el valor real de cada compra y venta (nominal negociado), y los pesos objetivo se aplican
  sobre el patrimonio que queda después de pagarlos.
- **Turnover:** ½·Σ|Δw|, qué porcentaje de la cartera "rotó".
- **Caja:** nunca puede quedar negativa (eso sería endeudarse sin autorización). Con unidades enteras sobra algo de caja.
- **Eventos repetidos** no generan una segunda operación, y datos viejos o precios desincronizados **suspenden** la decisión.
""")


def _tab_capm(lab: LabData):
    params = _load_json("caso_alimentos_parametros.json")
    r = pd.read_csv(PAQUETE_DATA / "caso_alimentos_retornos.csv").set_index("anio")
    st.markdown(f"#### Caso docente congelado: {params['empresa']}")
    st.caption("Tasas y datos del caso (Restrepo Montoya, 2026). Son insumos congelados para reproducir el caso, "
               "no cotizaciones actuales. Seis observaciones sirven de control aritmético, no de precisión real.")
    beta_c = beta_ols(r["comparable"], r["referencia"], rf=params["rf_USD"])
    beta_u = unlever_beta(beta_c.beta, params["de_comparable"], params["tax_supuesto"], params["beta_deuda_supuesto"])
    beta_l = relever_beta(beta_u, params["de_empresa"], params["tax_supuesto"], params["beta_deuda_supuesto"])
    ke = cost_of_equity(params["rf_USD"], beta_l, params["erp_madura"], params["proxy_pais"], params["lambda"])
    ke_cop = nominal_rate_to_other_currency(ke.ke, params["inflacion_COL"], params["inflacion_USA"])
    st.dataframe(pd.DataFrame([
        ["Beta del comparable (OLS de excesos vs. referencia)", f"{beta_c.beta:.4f}",
         f"n={beta_c.n}, EE={beta_c.std_error:.3f}, IC95 [{beta_c.ci95[0]:.2f}, {beta_c.ci95[1]:.2f}], R²={beta_c.r_squared:.2f}; Cov/Var={beta_c.beta_cov_ratio:.4f}"],
        ["Beta desapalancada (D/E comparable)", f"{beta_u:.4f}", f"D/E={params['de_comparable']}, t={params['tax_supuesto']:.0%}, β_deuda={params['beta_deuda_supuesto']}"],
        ["Beta reapalancada (D/E de la empresa)", f"{beta_l:.4f}", f"D/E={params['de_empresa']}"],
        ["Ke USD base = rf + β·ERP", _pct(ke.base), f"rf={params['rf_USD']:.2%}, ERP={params['erp_madura']:.2%}"],
        ["+ prima país λ·CRP (mostrada aparte)", _pct(ke.country_premium), f"λ={params['lambda']}, proxy país={params['proxy_pais']:.2%}"],
        ["Ke USD", _pct(ke.ke), ""],
        ["Ke COP (paridad de inflación)", _pct(ke_cop), f"(1+Ke_USD)(1+{params['inflacion_COL']:.1%})/(1+{params['inflacion_USA']:.1%}) − 1"],
    ], columns=["concepto", "valor", "detalle"]), hide_index=True)

    st.markdown("**WACC y valoración (DCF)**")
    c1, c2, c3 = st.columns(3)
    kd = c1.number_input("Kd efectiva anual", value=float(params["kd_EA"]), step=0.005, format="%.4f", key="lab_val_kd",
                         help="Del caso: 13,5 %. El equipo debe confirmar que está en COP, igual que los flujos.")
    de = c2.number_input("D/E para los pesos del WACC", value=float(params["de_empresa"]), step=0.05, key="lab_val_de")
    g = c3.number_input("g terminal (nominal COP)", value=float(params["g_terminal"]), step=0.005, format="%.4f", key="lab_val_g")
    w = wacc(ke_cop, kd, params["tax_supuesto"], de)
    st.metric("WACC (COP)", _pct(w), help="E/(D+E)·Ke_COP + D/(D+E)·Kd·(1−t)")

    st.warning("⚠️ **Proyección pendiente del equipo.** La tabla parte del año 0 del caso repetido sin crecimiento solo para "
               "que el cálculo corra. Reemplácenla con su proyección de 5 años (ventas, márgenes, CAPEX y capital de trabajo).")
    proj = pd.DataFrame({"año": [1, 2, 3, 4, 5], "EBIT": [params["ebit0"]] * 5, "D&A": [params["depreciacion0"]] * 5,
                         "CAPEX": [params["depreciacion0"]] * 5, "ΔNWC": [0.0] * 5})
    proj = st.data_editor(proj, key="lab_val_proj", hide_index=True, disabled=["año"])
    flows = [fcff(e, params["tax_supuesto"], d, c, n) for e, d, c, n in proj[["EBIT", "D&A", "CAPEX", "ΔNWC"]].to_numpy()]
    try:
        dcf = discounted_cash_flow(flows, w, g)
    except ValueError as exc:
        st.error(str(exc))
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Valor de la empresa (EV)", f"{dcf.enterprise_value:,.0f}")
    c2.metric("Peso del valor terminal", _pct(dcf.terminal_share))
    c3.metric("Patrimonio (EV − deuda financiera)", f"{equity_value(dcf.enterprise_value, 0, 0, params['deuda_financiera']):,.0f}",
              help="Sin caja excedente ni activos no operativos (no vienen en los datos del caso cargados).")
    st.caption("COP millones. FCFF = EBIT·(1−t) + D&A − CAPEX − ΔNWC; TV = FCFF₆/(WACC − g) con FCFF₆ = FCFF₅·(1+g).")
    roic = st.number_input("ROIC estable para revisar la reinversión (opcional, decisión del equipo)", value=0.0, step=0.01,
                           format="%.3f", key="lab_val_roic")
    if roic > 0:
        need = stable_reinvestment_rate(g, roic)
        st.info(f"Crecer al {g:.2%} con ROIC {roic:.2%} exige reinvertir {need:.1%} del NOPAT cada año. "
                "Si la proyección no lo hace, el crecimiento terminal no es coherente.")

    if lab.source == SOURCE_MARKET and lab.returns is not None:
        st.markdown("#### Beta de los activos frente a un benchmark")
        bench = st.text_input("Ticker del benchmark (decisión del equipo; ej. ^GSPC, ^COLCAP)", value="", key="lab_beta_bench")
        if bench.strip():
            result = st.session_state.get("comparison_result")
            asset = fetch_asset_data(bench, result.common_start, result.common_end + pd.Timedelta(days=1))
            if not asset.ok:
                st.error(f"{bench}: {asset.error}")
            else:
                prices = resample_prices(asset.prices, result.frequency)["adjusted_close"]
                if prices.index.tz is not None:
                    prices.index = prices.index.tz_localize(None)
                mret = prices.pct_change(fill_method=None)
                rows = []
                for a in lab.returns.columns:
                    b = beta_ols(lab.returns[a], mret)
                    rows.append({"activo": a, "beta": b.beta, "EE": b.std_error, "R²": b.r_squared, "n": b.n, "estado": b.status})
                betas = pd.DataFrame(rows).set_index("activo")
                st.dataframe(betas.style.format({"beta": "{:.3f}", "EE": "{:.3f}", "R²": "{:.2f}"}, na_rep="—"))
                st.caption(f"Beta frente a {bench.upper()} (sensibilidad a esa referencia, no automáticamente al «mercado» teórico); "
                           "rf constante = 0 en esta tabla porque se usa la misma muestra para todos.")

    erp = params["erp_madura"]
    xs = np.linspace(0, 2, 20)
    fig = go.Figure(go.Scatter(x=xs, y=[sml_required_return(params["rf_USD"], x, erp) for x in xs], name="SML",
                               line=dict(color=NEON_GREEN)))
    for label, b in (("Comparable", beta_c.beta), ("Empresa (reapalancada)", beta_l), ("Desapalancada", beta_u)):
        fig.add_trace(go.Scatter(x=[b], y=[sml_required_return(params["rf_USD"], b, erp)], mode="markers+text", text=[label],
                                 textposition="top left", marker=dict(size=11, color=STAR_GOLD), showlegend=False))
    fig.update_layout(title="SML del caso (USD, sin prima país)", xaxis_title="Beta", yaxis_title="Rendimiento requerido",
                      yaxis_tickformat=".0%", height=360, **LAYOUT)
    st.plotly_chart(fig)

    _explain("¿Qué significan beta, CAPM, Hamada, Ke, WACC y DCF?", """
- **Beta (β):** cuánto se mueve un activo cuando se mueve el benchmark. β = 1,5 ⇒ si el mercado sube 1 %, el activo
  tiende a subir 1,5 %. Se estima con una regresión de excesos sobre rf; un benchmark que no se mueve deja β indefinida.
- **SML (línea del mercado de valores):** rendimiento **requerido** = rf + β·ERP. El eje es β, no la volatilidad total.
- **Hamada:** la beta de una empresa con deuda (apalancada) es mayor que la de su negocio puro. Se **desapalanca** la
  beta del comparable con su D/E y se **reapalanca** con la D/E de la empresa, con el mismo supuesto de deuda.
- **Ke (costo del patrimonio):** rf + β·ERP, y la **prima país** se suma aparte una sola vez. Para pasar de USD a COP se
  usa la paridad de inflación (no se suman inflaciones, y no es una predicción de la TRM).
- **WACC:** costo promedio de financiarse = peso del patrimonio·Ke + peso de la deuda·Kd·(1−t).
- **FCFF y DCF:** el flujo de caja libre para la empresa se descuenta al WACC; después del año 5, un **valor terminal**
  con crecimiento g, que solo existe si WACC > g. Si el terminal pesa mucho en el EV, el resultado depende mucho de g.
- **EV → patrimonio:** al valor de la empresa se le resta la deuda financiera (y se suma caja excedente si la hay).
""")


def _tab_export(lab: LabData, rf_ea, gamma, bounds, results):
    asset_order = list(lab.mu.index)
    if lab.returns is not None:
        snapshot_bytes = lab.returns.to_csv().encode()
    else:
        snapshot_bytes = json.dumps({"mu": lab.mu.tolist(), "Sigma": lab.sigma.values.tolist()}).encode()
    trace = {
        "schema": "bot-portafolios/trace/v2",
        "analysis_id": str(uuid.uuid4()),
        "snapshot_sha256": hashlib.sha256(snapshot_bytes).hexdigest(),
        "code_commit": _git_commit(),
        "dependencies": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "source": lab.source,
        "rights": "Datos sintéticos/caso docente o Yahoo Finance (uso académico; no redistribuir cotizaciones).",
        "calculated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frequency_periods_per_year": lab.m,
        "return_convention": "simple (capa de cartera); logs solo en la capa individual v1",
        "annualization": "mu*m, sigma*sqrt(m) (convención aritmética)",
        "asset_order": asset_order,
        "common_rows": None if lab.returns is None else len(lab.returns),
        "rows_before_mask": lab.n_before,
        "parameters": {"rf_EA": rf_ea, "gamma": gamma, "bounds": bounds},
        "solver": results["gmv"].solver if results else None,
        "results": {k: {"status": r.status, "weights": None if r.weights is None else r.weights.round(10).to_dict(),
                        "mean_period": r.mean, "vol_period": r.volatility, "active_bounds": r.active_bounds}
                    for k, r in (results or {}).items()},
        "student_decision": None,
        "status": "ejecucion_laboratorio",
    }
    st.json(trace, expanded=False)
    st.download_button("Descargar traza (JSON)", json.dumps(trace, indent=2, ensure_ascii=False, default=str),
                       file_name=f"traza_{trace['analysis_id'][:8]}.json", mime="application/json")
    st.caption("La traza conecta fuente → muestra → parámetros → resultado → commit. La decisión del estudiante "
               "(`student_decision`) la completa el equipo; la app no la llena.")


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def render_portfolio_lab() -> None:
    st.divider()
    st.subheader("Laboratorio de portafolios (v2)")
    st.caption(
        "Asignación de capital: riesgo conjunto, Markowitz, Black-Litterman, rebalanceo simulado, beta/CAPM y "
        "valoración. Simulación académica: no envía órdenes ni constituye recomendación de inversión."
    )
    _explain("Qué es este laboratorio y qué decide el equipo", """
La v1 analiza activos **uno por uno**. Este laboratorio arma **carteras**: combina activos con pesos y estudia su riesgo
conjunto, elige carteras con distintos criterios, actualiza expectativas con opiniones, simula rebalanceos y calcula el
costo de capital y el valor de una empresa.

**La app calcula; las decisiones financieras son del equipo.** Los valores iniciales de las cajas vienen del **caso
docente de control** (por ejemplo rf = 3 %, γ = 5, pesos entre 0 y 1) y están para reproducir ese caso, no porque sean
los correctos para ustedes. Pendientes del equipo: mandato (moneda, horizonte, pérdida tolerable), universo, benchmark,
tasa libre de riesgo, γ, límites de pesos, cartera de referencia y views de Black-Litterman, política de rebalanceo y
proyección de la valoración.

**Tres relojes:** la **cotización** cambia cada minuto (panel de abajo); la **estimación** (μ, Σ, correlaciones, beta)
usa barras completas históricas y no tiene que cambiar con cada precio; la **decisión** (frontera, pesos, rebalanceo)
solo cambia cuando la política del equipo lo indica.
""")

    _render_live_quote()
    st.markdown("---")

    source = st.radio("Fuente de datos del laboratorio", [SOURCE_TWO, SOURCE_SYNTH, SOURCE_MARKET], key="lab_source")
    if source == SOURCE_TWO:
        lab = _load_lab_data(source)
        st.info("📘 **Caso docente de control.** Parámetros anuales dados (μ, Σ): sirve para reconstruir los cálculos a mano.")
    else:
        loaded = _load_lab_data(source)
        if loaded is None:
            st.warning("Primero ejecuta la sección **Comparación de activos** (arriba) para traer precios reales de Yahoo Finance.")
            return
        prices, m, label = loaded
        if source == SOURCE_SYNTH:
            st.warning("🧪 **MODO LABORATORIO SINTÉTICO.** Series generadas para practicar: **no son cotizaciones reales**.")
        else:
            st.success("📈 **MODO MERCADO.** Precios históricos de Yahoo Finance traídos en la sección Comparación.")
        all_assets = list(prices.columns)
        chosen = st.multiselect("Universo (decisión del equipo)", all_assets, default=all_assets, key=f"lab_universe_{source}")
        if len(chosen) < 2:
            st.error("Elige al menos 2 activos para formar una cartera.")
            return
        try:
            lab = _from_prices(source, prices, m, label, chosen)
        except ValueError as exc:
            st.error(str(exc))
            return
    st.caption(lab.label + (" Frecuencia nativa: anual." if lab.m == 1 else f" Frecuencia nativa: {lab.m} periodos por año."))

    with st.container(border=True):
        st.markdown("**⚙️ Supuestos financieros (decisión del equipo; iniciales = caso docente de control)**")
        ctrl = _load_json("dos_activos.json")
        c1, c2, c3, c4 = st.columns(4)
        rf_ea = c1.number_input("Tasa libre de riesgo (efectiva anual)", value=float(ctrl["rf"]), step=0.005, format="%.4f", key="lab_rf")
        gamma = c2.number_input("γ aversión al riesgo", value=float(ctrl["gamma"]), min_value=0.1, step=0.5, key="lab_gamma")
        lo = c3.number_input("Peso mínimo por activo", value=float(ctrl["bounds"][0][0]), step=0.05, format="%.2f", key="lab_lo",
                             help="Negativo = se permiten cortos (decisión del equipo).")
        hi = c4.number_input("Peso máximo por activo", value=float(ctrl["bounds"][0][1]), step=0.05, format="%.2f", key="lab_hi")
    bounds = [(lo, hi)] * len(lab.mu)

    tabs = st.tabs(["Riesgo conjunto", "Markowitz y fronteras", "Black-Litterman", "Rebalanceo", "Beta, CAPM y valoración", "Exportar"])
    results = None
    with tabs[0]:
        _tab_risk(lab)
    with tabs[1]:
        results = _tab_markowitz(lab, rf_ea, gamma, bounds)
    with tabs[2]:
        _tab_black_litterman(lab, rf_ea, gamma, bounds)
    with tabs[3]:
        _tab_rebalance(rf_ea)
    with tabs[4]:
        _tab_capm(lab)
    with tabs[5]:
        _tab_export(lab, rf_ea, gamma, bounds, results)
