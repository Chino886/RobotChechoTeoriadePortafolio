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
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.black_litterman import View, ViewSet, absolute_total_to_excess, build_view_set, implied_prior, posterior
from src.capm import (
    beta_ols,
    cost_of_equity,
    discounted_cash_flow,
    nominal_rate_to_other_currency,
    portfolio_beta,
    relever_beta,
    sml_required_return,
    unlever_beta,
    wacc,
)
from src.backtest import ALL_STRATEGIES, ESTIMATORS, BacktestConfig, select_by_validation, walk_forward
from src.charts import DARK_LAYOUT, ELECTRIC_BLUE, ACCENT_GOLD, NEGATIVE, PLOTLY_CONFIG, POSITIVE, STAR_WHITE, polish
from src.data import fetch_asset_data, resample_prices
from src.data_quality import (
    FX_TICKER_COP_PER_USD,
    SUPPORTED_BASES,
    calendar_report,
    convert_prices_base,
    gap_safe_simple_returns,
    last_bar_age,
)
from ayuda import AYUDA
from src.estimators import ewma_covariance, ledoit_wolf
from src.factsheet import NOT_APPLICABLE, build_factsheet, to_markdown
from src.performance import capm_required_return, historical_erp, performance_table
from src.market import fetch_quotes, format_age
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
    cml_expected_return,
    portfolio_return_series,
    portfolio_stats,
    random_portfolios,
    rf_per_period,
    risk_contributions,
    rolling_correlation,
    rolling_volatility,
    weighted_average_volatility,
)
from src.rebalance import ACTION_REBALANCE, Book, RebalancePolicy, plan_rebalance, simulate_policy
from src.stress import (
    concentration,
    correlation_breakdown,
    historical_es,
    historical_var,
    individual_shocks,
    joint_worst_historical,
    parametric_es,
    parametric_var,
    reverse_stress,
    worst_historical_portfolio_period,
)
from src.trace import build_trace, export_bundle, snapshot_csv, verify_bundle
from src.valuation import Scenario, budget_target, iterate_capital_structure, project, reinvestment_check, value_firm

PAQUETE_DATA = Path(__file__).parent / "paquete_v2" / "data"

SOURCE_TWO = "Caso docente de dos activos (control)"
SOURCE_SYNTH = "Laboratorio sintético: 20 series del paquete"
SOURCE_MARKET = "Mercado: activos de la Comparación (Yahoo Finance)"
# Identidad para la ficha técnica (la misma de app.py).
BRAND = "DPST"
TEAM = "Equipo DPST"
INSTITUTION = "Tech Business School – Universidad EIA"

LAYOUT = dict(margin=dict(t=50, b=40, l=40, r=20), **DARK_LAYOUT)


# ---------------------------------------------------------------------------
# Datos de entrada
# ---------------------------------------------------------------------------

def _load_json(name: str) -> dict:
    return json.loads((PAQUETE_DATA / name).read_text())


class LabData:
    """mu y Sigma en la frecuencia nativa, más la muestra de retornos si existe."""

    def __init__(self, source, mu, sigma, periods_per_year, returns=None, n_before=None, label="",
                 frequency=None, calendar=None, gap_removed=0, last_date=None, currency=None, fx_note=None):
        self.source = source
        self.mu = mu
        self.sigma = sigma
        self.m = periods_per_year
        self.returns = returns
        self.n_before = n_before
        self.label = label
        self.frequency = frequency
        self.calendar = calendar
        self.gap_removed = gap_removed
        self.last_date = last_date
        self.currency = currency  # moneda base de los precios (None = sin moneda: caso docente o sintético)
        self.fx_note = fx_note  # cómo se convirtió a la moneda base, si hubo conversión


def _load_lab_data(source: str):
    if source == SOURCE_TWO:
        d = _load_json("dos_activos.json")
        mu = pd.Series(d["mu"], index=d["assets"])
        sigma = pd.DataFrame(d["Sigma"], index=d["assets"], columns=d["assets"])
        return LabData(source, mu, sigma, 1, label="Parámetros anuales dados por el caso (no hay serie de precios).")
    if source == SOURCE_SYNTH:
        prices = pd.read_csv(PAQUETE_DATA / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
        return prices, 252, "Calendario lunes-viernes didáctico (NO bursátil); 252 periodos por año como convención.", "Diaria"
    result = st.session_state.get("comparison_result")
    if result is None or not getattr(result, "ok", False) or not result.common_prices:
        return None
    prices = pd.DataFrame(result.common_prices).sort_index()
    return prices, result.periods_per_year, (
        f"Precios de cierre ajustado (auto_adjust=True: incluye dividendos y splits) de la sección Comparación: "
        f"frecuencia {result.frequency}, moneda {result.base_currency}, {result.common_start.date()} a {result.common_end.date()}."
    ), result.frequency


@st.cache_data(ttl=3600, show_spinner=False)
def _fx_cop_per_usd(start, end) -> pd.Series:
    """COP por 1 USD (USDCOP=X, Yahoo Finance) entre esas fechas; vacía si no hay dato."""
    data = fetch_asset_data(FX_TICKER_COP_PER_USD, start, end)
    if not data.ok or data.prices is None:
        return pd.Series(dtype=float)
    fx = data.prices["adjusted_close"].copy()
    if fx.index.tz is not None:
        fx.index = fx.index.tz_localize(None)
    return fx


def _to_base_currency(prices: pd.DataFrame, from_ccy: str, base: str) -> "tuple[pd.DataFrame, str]":
    """Pasa los precios de la Comparación a la moneda base elegida; devuelve (precios, nota para pantalla y traza)."""
    if from_ccy == base:
        return prices, f"Precios en {base} tal como vienen de la Comparación (sin conversión)."
    if from_ccy not in SUPPORTED_BASES:
        raise ValueError(f"La Comparación está en {from_ccy}; solo se convierte entre USD y COP.")
    start = prices.index.min() - pd.Timedelta(days=10)  # margen para tener un FX previo al primer precio
    fx = _fx_cop_per_usd(start, prices.index.max() + pd.Timedelta(days=1))
    if fx.empty:
        raise ValueError(f"No se pudo descargar {FX_TICKER_COP_PER_USD} de Yahoo Finance para convertir a {base}.")
    out, dropped = convert_prices_base(prices, from_ccy, base, fx)
    op = "P_COP = P_USD · FX" if base == "COP" else "P_USD = P_COP / FX"
    note = (f"Convertido {from_ccy} → {base} con {FX_TICKER_COP_PER_USD} (COP por USD): {op}, con el último FX "
            f"publicado en o antes de cada fecha; así 1 + R_COP = (1 + R_USD)(1 + R_FX).")
    if dropped:
        note += f" Se descartaron {dropped} fecha(s) sin FX previo."
    return out, note


def _from_prices(source, prices, m, label, assets, frequency):
    """
    Rendimientos simples sin rellenar huecos; los que cruzan un intervalo
    anormal se anulan; después se aplica la máscara común (guía 3.2).
    """
    sub = prices[assets].sort_index()
    raw, removed = gap_safe_simple_returns(sub, frequency)
    returns = raw.dropna(how="any")
    if len(returns) < 2:
        raise ValueError("No quedan observaciones comunes suficientes tras la limpieza.")
    return LabData(source, returns.mean(), covariance_matrix(returns), m, returns, len(raw), label,
                   frequency=frequency, calendar=calendar_report(sub, frequency), gap_removed=removed,
                   last_date=sub.index[-1])


# ---------------------------------------------------------------------------
# Utilidades de presentación
# ---------------------------------------------------------------------------

def _pct(x, digits=2):
    return "N/D" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{digits}%}"


def _explain(title: str, body: str):
    """Línea corta con un signo de interrogación: la explicación aparece al poner el mouse encima."""
    st.caption(title, help=body)


# Pestañas del laboratorio como botones en cuadrícula con borde verde. Apunta a clases
# internas de Streamlit (st-key-*, data-testid) y puede requerir ajuste si cambia la versión.
# Módulos del laboratorio (pestañas). También alimentan el buscador Ctrl/⌘ + K de app.py.
LAB_MODULES = ["Riesgo conjunto", "Estrés y estimadores", "Markowitz y fronteras", "Black-Litterman",
               "Rebalanceo", "Backtest", "Beta, CAPM y valoración", "Ficha técnica", "Exportar"]

LAB_NAV_CSS = """
<style>
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] {
    display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.7rem;
    border: none; box-shadow: none; margin-bottom: 1rem; overflow: visible;
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] {
    height: auto; min-height: 3.4rem; padding: 0.75rem 0.9rem; justify-content: center; text-align: center;
    border: 1px solid rgba(var(--dp-accent-rgb), 0.55); border-radius: 12px;
    background: linear-gradient(180deg, rgba(var(--dp-accent-rgb), 0.08), rgba(var(--dp-accent-rgb), 0.02));
    transition: background 0.15s, transform 0.15s, box-shadow 0.15s;
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"]:hover {
    background: rgba(var(--dp-accent-rgb), 0.16); transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(var(--dp-accent-rgb), 0.15);
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"] p {
    font-size: 0.98rem; font-weight: 700; color: var(--dp-accent-ink); white-space: normal;
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"][aria-selected="true"] {
    background: linear-gradient(180deg, var(--dp-accent-hi), var(--dp-accent-lo)); border-color: var(--dp-accent-hi);
    box-shadow: 0 4px 18px rgba(var(--dp-accent-rgb), 0.25);
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] > [data-testid="stTab"][aria-selected="true"] p {
    color: var(--dp-on-accent);
}
.st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] .react-aria-SelectionIndicator { display: none; }
@media (max-width: 760px) {
    .st-key-lab_nav > [data-testid="stTabs"] > div > [role="tablist"] { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
</style>
"""


def _cov_corr_help(cov: pd.DataFrame, corr: pd.DataFrame) -> str:
    """Explicación sencilla de las tablas de colores, con un ejemplo de los dos primeros activos en pantalla."""
    a, b = cov.index[0], cov.index[1]
    rho = float(corr.loc[a, b])
    if rho > 0.7:
        reading = "se mueven casi igual, así que juntarlas protege poco"
    elif rho > 0.3:
        reading = "suelen moverse juntas, pero no siempre: juntarlas protege algo"
    elif rho > -0.3:
        reading = "casi no tienen que ver una con otra: juntarlas protege bastante"
    else:
        reading = "cuando una sube la otra suele bajar: se compensan"
    return f"{AYUDA['cov_corr']}\n\n**En estos datos:** {a} y {b} tienen correlación {rho:.2f}, o sea que {reading}."


def _heatmap(matrix: pd.DataFrame, title: str, zmid=None, fmt=".2f"):
    z = matrix.to_numpy()
    fig = go.Figure(go.Heatmap(
        z=z, x=list(matrix.columns), y=list(matrix.index), zmid=zmid,
        # El centro de la escala es casi transparente: deja ver el fondo, así se lee igual en tema claro y oscuro.
        colorscale=([[0, "#6AA8FF"], [0.5, "rgba(148,170,210,0.10)"], [1, "#34C9A0"]] if zmid is not None
                    else [[0, "rgba(52,201,160,0.08)"], [1, "#34C9A0"]]),
        hoverongaps=False,
    ))
    if len(matrix) <= 12:
        # Números oscuros sobre los cuadros claros y claros sobre los oscuros, para que se lean al proyectar.
        lo_, hi_ = np.nanmin(z), np.nanmax(z)
        if zmid is not None:
            half = max(abs(lo_ - zmid), abs(hi_ - zmid)) or 1.0
            pos = lambda v: (v - zmid + half) / (2 * half)  # noqa: E731
        else:
            pos = lambda v: (v - lo_) / ((hi_ - lo_) or 1.0)  # noqa: E731
        for i, row in enumerate(matrix.index):
            for j, col in enumerate(matrix.columns):
                v = z[i, j]
                if np.isnan(v):
                    continue
                p_ = pos(v)
                dark = p_ > 0.7 or (zmid is not None and p_ < 0.2)
                fig.add_annotation(x=col, y=row, text=f"<b>{format(v, fmt)}</b>", showarrow=False,
                                   font=dict(color="#0A0F1C" if dark else "#E8EDF6", size=14))
    fig.update_layout(title=title, height=420 if len(matrix) > 6 else 320, **LAYOUT)
    # Se lee como una tabla: el primer activo arriba, así la diagonal va de arriba-izquierda a abajo-derecha.
    fig.update_yaxes(autorange="reversed")
    return fig


# ---------------------------------------------------------------------------
# Cotización en línea (reloj de cotización)
# ---------------------------------------------------------------------------

def _render_live_quote():
    st.markdown("#### Cotización en línea (reloj de cotización)")
    st.caption(
        "Consulta la última barra de 1 minuto de Yahoo Finance. «Consultado ahora» no significa "
        "«negociado ahora»: Yahoo publica con retraso según la bolsa, y fuera de sesión se muestra el "
        "último dato disponible. No se guardan ni redistribuyen cotizaciones."
    )
    c1, c2, c3 = st.columns([2, 1, 1])
    with c1:
        raw = st.text_input("Tickers a seguir (separados por coma, hasta 20)", value="AAPL", key="lab_quote_tickers")
    with c2:
        every = st.number_input("Actualizar cada (s)", min_value=15, max_value=600, value=60, step=15, key="lab_quote_every")
    with c3:
        auto = st.toggle("Actualización automática", value=False, key="lab_quote_auto")
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()][:20]

    @st.fragment(run_every=timedelta(seconds=int(every)) if auto else None)
    def _quote_panel():
        clicked = st.button("Consultar ahora", key="lab_quote_btn")
        previous = st.session_state.get("lab_last_quotes", {})
        if auto or clicked:
            quotes = fetch_quotes(tickers)
            current = {q.ticker: q for q in quotes}
            st.session_state["lab_last_quotes"] = {**previous, **{t: q for t, q in current.items() if q.ok}}
            st.session_state["lab_quote_log"] = (st.session_state.get("lab_quote_log", []) + [
                {"consulta": q.received_at, "ticker": q.ticker, "precio": q.price, "última barra": q.last_bar_at,
                 "repetido": q.same_data_as(previous.get(q.ticker)), "estado": "ok" if q.ok else q.error}
                for q in quotes])[-200:]
        else:
            current = {t: previous[t] for t in tickers if t in previous}
            if not current:
                st.caption("Pulsa «Consultar ahora» o activa la actualización automática.")
                return
        rows = []
        for t in tickers:
            q = current.get(t)
            if q is None:
                continue
            if not q.ok:
                rows.append({"ticker": t, "precio": None, "moneda": None, "antigüedad": None, "sesión": None, "bolsa": None,
                             "última barra (UTC)": None, "estado": f"❌ {q.error}"})
                continue
            rows.append({"ticker": t, "precio": q.price, "moneda": q.currency, "antigüedad": format_age(q.age_seconds),
                         "sesión": q.session, "bolsa": q.exchange, "última barra (UTC)": q.last_bar_at.strftime("%Y-%m-%d %H:%M"),
                         "estado": "⏸️ repetido" if (auto or clicked) and q.same_data_as(previous.get(t)) else "✅ ok"})
        st.dataframe(pd.DataFrame(rows).set_index("ticker"))
        first = next((current[t] for t in tickers if t in current and current[t].ok and current[t].bars is not None), None)
        if first is not None:
            fig = go.Figure(go.Scatter(x=first.bars.index, y=first.bars.values, mode="lines", line=dict(color=ACCENT_GOLD),
                                       name=first.ticker))
            fig.update_layout(title=f"{first.ticker}: barras de 1 minuto (la última puede estar incompleta)", height=300, **LAYOUT)
            st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
            st.caption(f"Tipo de precio: {first.price_type}. Recibido: {first.received_at:%Y-%m-%d %H:%M:%S} UTC · "
                       f"zona de la bolsa: {first.timezone or 'N/D'}.")
        log = st.session_state.get("lab_quote_log", [])
        if log:
            with st.expander(f"Registro de consultas de esta sesión ({len(log)}) — evidencia de consultas sucesivas"):
                st.dataframe(pd.DataFrame(log))

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
    if lab.calendar is not None:
        age = last_bar_age(pd.DatetimeIndex([lab.last_date]))
        issues = lab.calendar
        with st.expander(f"Calidad del dato: {len(issues)} observación(es) · {lab.gap_removed} rendimiento(s) anulados por huecos · "
                         f"último dato hace {age:.1f} días"):
            st.caption("Un hueco mayor al normal para la frecuencia no se convierte en un rendimiento de un periodo: se anula "
                       "antes de la máscara común. También se reportan fechas duplicadas, precios no positivos y precios estancados.")
            if issues.empty:
                st.success("Sin huecos, duplicados ni precios estancados.")
            else:
                st.dataframe(issues)
    c1, c2 = st.columns(2)
    c1.plotly_chart(polish(_heatmap(lab.sigma * m, "Covarianza anualizada (decimal²)", fmt=".4f")), config=PLOTLY_CONFIG)
    c2.plotly_chart(polish(_heatmap(corr, "Correlación (sin unidad)", zmid=0)), config=PLOTLY_CONFIG)
    _explain("¿Cómo leo estas tablas de colores?", _cov_corr_help(lab.sigma * m, corr))

    st.markdown("**Prueba una cartera** (los pesos los eliges tú; deben sumar 1):")
    w = _weights_editor(list(lab.mu.index), "lab_risk_weights")
    if abs(w.sum() - 1) > 1e-6:
        st.error(f"Los pesos suman {w.sum():.4f}: una cartera necesita pesos que sumen 1.")
        return None
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
                               marker_color=[POSITIVE if v >= 0 else NEGATIVE for v in rc.percent]))
        fig.update_layout(title="Contribución de cada activo al riesgo (% de la volatilidad)", yaxis_tickformat=".0%", height=320, **LAYOUT)
        st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)

    _explain("¿Qué significa cada número?", AYUDA["indicadores"])
    conc = concentration(w)
    a, b, c, d = st.columns(4)
    a.metric("Concentración (HHI)", f"{conc.hhi:.3f}", help="Σw². 1/N = lo más diversificado posible; 1 = un solo activo.")
    b.metric("N efectivo de activos", f"{conc.effective_n:.1f}", help="1/HHI: cuántos activos 'iguales' equivale la cartera.")
    c.metric("Mayor peso", f"{conc.max_asset}: {conc.max_weight:.0%}")
    d.metric("VaR paramétrico 95 % (1 periodo)", _pct(parametric_var(stats.mean, stats.volatility, 0.95)),
             help="Pérdida que no se supera con 95 % de confianza en un periodo, suponiendo normalidad.")
    if lab.returns is not None:
        rp_hist = portfolio_return_series(lab.returns, w)
        st.caption(f"VaR histórico 95 % / 99 % (1 periodo): {_pct(historical_var(rp_hist, 0.95))} / "
                   f"{_pct(historical_var(rp_hist, 0.99))} · VaR paramétrico 99 %: "
                   f"{_pct(parametric_var(stats.mean, stats.volatility, 0.99))}.")
        st.caption(f"Pérdida esperada (ES, promedio de las pérdidas peores que el VaR) 95 %: histórica "
                   f"{_pct(historical_es(rp_hist, 0.95))}, paramétrica {_pct(parametric_es(stats.mean, stats.volatility, 0.95))} · "
                   f"99 %: histórica {_pct(historical_es(rp_hist, 0.99))}, paramétrica "
                   f"{_pct(parametric_es(stats.mean, stats.volatility, 0.99))}.")

    if lab.returns is not None and len(lab.returns) > 30:
        window = st.slider("Ventana móvil (observaciones)", 10, min(250, len(lab.returns) - 1), min(60, len(lab.returns) // 3),
                           key="lab_window")
        rp = portfolio_return_series(lab.returns, w)
        vol = rolling_volatility(pd.concat([lab.returns, rp], axis=1), window) * np.sqrt(m)
        fig = go.Figure()
        for col in vol.columns:
            is_p = col == "cartera"
            fig.add_trace(go.Scatter(x=vol.index, y=vol[col], name=col, mode="lines",
                                     line=dict(width=3 if is_p else 1, color=ACCENT_GOLD if is_p else None),
                                     opacity=1 if is_p else 0.45))
        fig.update_layout(title=f"Volatilidad móvil anualizada ({window} obs.) — cartera vs. activos", yaxis_tickformat=".0%",
                          height=360, **LAYOUT)
        st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
        c1, c2 = st.columns(2)
        assets = list(lab.returns.columns)
        x = c1.selectbox("Correlación móvil entre", assets, index=0, key="lab_rc_a")
        y = c2.selectbox("y", assets, index=min(1, len(assets) - 1), key="lab_rc_b")
        rcorr = rolling_correlation(lab.returns[x], lab.returns[y], window)
        dd = drawdown_from_returns(rp)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rcorr.index, y=rcorr, name=f"corr {x}-{y}", line=dict(color=ELECTRIC_BLUE)))
        fig.add_trace(go.Scatter(x=dd.index, y=dd, name="drawdown cartera", line=dict(color=ACCENT_GOLD), yaxis="y2"))
        fig.update_layout(title="Correlación móvil y caída desde el máximo (drawdown) de la cartera", height=340,
                          yaxis=dict(title="correlación", range=[-1, 1]),
                          yaxis2=dict(title="drawdown", overlaying="y", side="right", tickformat=".0%"), **LAYOUT)
        st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
        st.caption("Pesos constantes: equivale a rebalancear a esos pesos cada periodo, sin costos (mantener cantidades es otra contabilidad).")

    _explain("¿Qué es el riesgo de una cartera?", AYUDA["riesgo_cartera"])
    return w


def _tab_stress(lab: LabData, w, bounds, groups):
    if w is None:
        st.info("Define una cartera válida en la pestaña «Riesgo conjunto» (pesos que sumen 1).")
        return
    m = lab.m
    st.markdown("#### Escenarios de estrés sobre la cartera de «Riesgo conjunto»")
    st.caption("Los tamaños de los shocks y el límite de pérdida del mandato son decisiones del equipo; los valores de las "
               "cajas son solo ejemplos para explorar.")
    c1, c2, c3 = st.columns(3)
    shock = c1.number_input("Shock individual (caída de un activo)", value=-0.20, max_value=0.0, step=0.05, format="%.2f", key="lab_st_shock",
                            help="Cuánto cae un activo de golpe (−0,20 = −20 %). Elijan un tamaño plausible para su universo.")
    rho = c2.number_input("Ruptura: correlación forzada", value=0.90, min_value=-0.99, max_value=1.0, step=0.05, format="%.2f", key="lab_st_rho",
                          help="En crisis las correlaciones suben: 0,9 simula que casi todo se mueve junto.")
    loss_limit = c3.number_input("Pérdida máxima del mandato (escenario inverso)", value=0.10, min_value=0.001, step=0.01,
                                 format="%.3f", key="lab_st_loss",
                                 help="La pérdida que el mandato no tolera en un periodo (0,10 = 10 %). Es decisión del equipo.")

    ind = individual_shocks(w, shock).sort_values(ascending=False)
    fig = go.Figure(go.Bar(x=list(ind.index), y=ind.to_numpy(), marker_color=[NEGATIVE if v > 0 else POSITIVE for v in ind]))  # es una pérdida: positiva = rojo
    fig.update_layout(title=f"Pérdida de la cartera si cada activo, por separado, cae {abs(shock):.0%}", yaxis_tickformat=".1%",
                      height=300, **LAYOUT)
    st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)

    base_vol = portfolio_stats(w, lab.mu, lab.sigma).volatility
    rows = []
    if lab.returns is not None:
        joint, worst = joint_worst_historical(w, lab.returns)
        rows.append(["Conjunto adverso: todos en su peor periodo histórico a la vez", _pct(joint),
                     "Cota pesimista: en la muestra no ocurrieron el mismo día."])
        loss_day, when = worst_historical_portfolio_period(w, lab.returns)
        rows.append(["Peor periodo real de la cartera en la muestra", _pct(loss_day), f"{pd.Timestamp(when).date()}"])
    try:
        broken = correlation_breakdown(lab.sigma, rho)
        vol_b = portfolio_stats(w, lab.mu, broken).volatility
        rows.append([f"Ruptura de correlaciones (todas = {rho:.2f})", f"σ {_pct(base_vol * np.sqrt(m))} → {_pct(vol_b * np.sqrt(m))}",
                     f"VaR 99 % de 1 periodo: {_pct(parametric_var(0, base_vol, 0.99))} → {_pct(parametric_var(0, vol_b, 0.99))}"])
    except ValueError as exc:
        rows.append(["Ruptura de correlaciones", "no válida", str(exc)])
    st.dataframe(pd.DataFrame(rows, columns=["escenario", "resultado", "detalle"]), hide_index=True)

    try:
        rs = reverse_stress(w, lab.sigma, loss_limit)
        st.markdown(f"**Escenario inverso:** para perder **{loss_limit:.1%}** en un periodo, la combinación de movimientos más "
                    f"probable (dada la covarianza estimada) es la de la tabla. Equivale a un movimiento de **{rs.mahalanobis:.1f} "
                    "desviaciones** conjuntas: más de 3 es muy raro bajo normalidad, pero las crisis lo superan.")
        st.dataframe(rs.shocks.rename("shock por activo").to_frame().T.style.format("{:+.2%}"))
    except ValueError as exc:
        st.warning(str(exc))

    if lab.returns is not None and len(lab.returns) > len(lab.mu) + 2:
        st.markdown("#### Estimadores alternativos de Σ")
        lam = st.number_input("λ de EWMA (decisión del equipo; 0,94 es la convención RiskMetrics para datos diarios)",
                              value=0.94, min_value=0.5, max_value=0.999, step=0.01, format="%.3f", key="lab_ewma_lambda")
        lw = ledoit_wolf(lab.returns)
        variants = {"Muestral": lab.sigma, f"Ledoit-Wolf (intensidad {lw.intensity:.2f})": lw.sigma,
                    f"EWMA (λ = {lam:.3f})": ewma_covariance(lab.returns, lam)}
        rows, weights = [], {}
        for name, sig in variants.items():
            diag = diagnose_covariance(sig)
            res = min_variance(lab.mu, sig, bounds, groups=groups)
            rows.append({"estimador": name, "condicionamiento": diag.condition_number,
                         "vol. GMV anual": res.volatility * np.sqrt(m) if res.ok else np.nan,
                         "concentración GMV (HHI)": concentration(res.weights).hhi if res.ok else np.nan})
            if res.ok:
                weights[name] = res.weights
        st.dataframe(pd.DataFrame(rows).set_index("estimador").style.format(
            {"condicionamiento": "{:,.1f}", "vol. GMV anual": "{:.2%}", "concentración GMV (HHI)": "{:.3f}"}, na_rep="—"))
        if weights:
            wdf = pd.DataFrame(weights).T
            fig = go.Figure([go.Bar(name=a, x=list(wdf.index), y=wdf[a]) for a in wdf.columns])
            fig.update_layout(barmode="stack", title="Pesos de la mínima varianza según el estimador de Σ", yaxis_tickformat=".0%",
                              height=340, **LAYOUT)
            st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
        st.caption("La estabilidad de cada estimador en el tiempo (rotación) se compara en la pestaña «Backtest». "
                   "λ debe elegirse sin mirar el tramo de prueba final.")

    _explain("¿Qué es una prueba de estrés?", AYUDA["estres"])


@st.cache_data(show_spinner=False, max_entries=20)
def _cached_frontier(mu: pd.Series, sigma: pd.DataFrame, bounds: tuple, groups: tuple, max_target=None) -> pd.DataFrame:
    """La frontera es lo más costoso (una optimización por punto): se reutiliza mientras no cambien datos ni cotas."""
    return efficient_frontier(mu, sigma, list(bounds), n_points=30, groups=[(list(g), c) for g, c in groups] or None,
                              max_target=max_target)


def _tab_markowitz(lab: LabData, rf_ea: float, gamma: float, bounds, groups=None, max_target=None):
    m = lab.m
    rf = rf_per_period(rf_ea, m)
    with st.spinner("Optimizando..."):
        gmv = min_variance(lab.mu, lab.sigma, bounds, groups=groups)
        tangent = max_sharpe(lab.mu, lab.sigma, rf, bounds, groups=groups)
        personal = personal_optimum(lab.mu, lab.sigma, gamma, bounds, groups=groups)
        top = max_expected_return(lab.mu, bounds, lab.sigma, groups=groups)
        frontier = _cached_frontier(lab.mu, lab.sigma, tuple(bounds), tuple((tuple(g), c) for g, c in (groups or [])), max_target)
        cloud = random_portfolios(lab.mu, lab.sigma, bounds, n=1500) if not groups else pd.DataFrame()

    ann_mu, ann_vol = (lambda x: x * m), (lambda x: x * np.sqrt(m))
    fig = go.Figure()
    if not cloud.empty:
        fig.add_trace(go.Scatter(x=ann_vol(cloud["volatilidad"]), y=ann_mu(cloud["media"]), mode="markers",
                                 name=cloud.attrs.get("etiqueta", "Carteras al azar (ilustrativas)"),
                                 marker=dict(size=3, color="rgba(230,230,230,0.18)"), hoverinfo="skip"))
    for branch, color, dash in (("eficiente", ACCENT_GOLD, None), ("no eficiente", ELECTRIC_BLUE, "dot")):
        part = frontier[(frontier["rama"] == branch) & (frontier["estado"] == "óptimo")]
        if not part.empty:
            fig.add_trace(go.Scatter(x=ann_vol(part["volatilidad"]), y=ann_mu(part["objetivo"]), mode="lines",
                                     name=f"Frontera {branch}", line=dict(color=color, width=3, dash=dash)))
    if tangent.ok:
        ys = np.linspace(0, 1, 20)
        fig.add_trace(go.Scatter(x=ann_vol(ys * tangent.volatility), y=[ann_mu(rf + y * (tangent.mean - rf)) for y in ys],
                                 mode="lines", name="CAL (rf → tangente, sin deuda)", line=dict(color=STAR_WHITE, dash="dash")))
    show_cml = st.toggle("Mostrar CML aproximada (proxy de mercado = 1/N del universo; decisión del equipo)", value=False,
                         key="lab_cml")
    if show_cml:
        proxy = pd.Series(1 / len(lab.mu), index=lab.mu.index)
        ps = portfolio_stats(proxy, lab.mu, lab.sigma)
        if ps.volatility > 0:
            x_max = max(ps.volatility, np.sqrt(np.diag(lab.sigma.to_numpy())).max())
            xs = np.linspace(0, x_max, 20)
            label = "1/N del universo (proxy provisional del equipo)"
            fig.add_trace(go.Scatter(x=ann_vol(xs), y=[ann_mu(cml_expected_return(rf, ps.mean, ps.volatility, x, label)) for x in xs],
                                     mode="lines", name="CML aproximada (proxy 1/N)", line=dict(color="#FF6B6B", dash="dot")))
            fig.add_trace(go.Scatter(x=[ann_vol(ps.volatility)], y=[ann_mu(ps.mean)], mode="markers", name="Proxy de mercado (1/N)",
                                     marker=dict(size=11, symbol="x", color="#FF6B6B")))
    for res, symbol, color in ((gmv, "diamond", ELECTRIC_BLUE), (tangent, "star", STAR_WHITE),
                               (personal, "circle", "#FF6B6B"), (top, "triangle-up", ACCENT_GOLD)):
        if res.ok:
            fig.add_trace(go.Scatter(x=[ann_vol(res.volatility)], y=[ann_mu(res.mean)], mode="markers", name=res.name,
                                     marker=dict(size=15, symbol=symbol, color=color, line=dict(width=1, color="white"))))
    for asset in lab.mu.index:
        fig.add_trace(go.Scatter(x=[ann_vol(np.sqrt(lab.sigma.loc[asset, asset]))], y=[ann_mu(lab.mu[asset])], mode="markers+text",
                                 text=[asset], textposition="top center", showlegend=False,
                                 marker=dict(size=7, color="rgba(230,230,230,0.7)")))
    fig.update_layout(title="Frontera de mínima varianza calculada por optimización", xaxis_title="Volatilidad anualizada",
                      yaxis_title="Rendimiento esperado anualizado", xaxis_tickformat=".0%", yaxis_tickformat=".0%", height=520, **LAYOUT)
    st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
    if frontier.empty:
        st.warning(f"Frontera no dibujada: {frontier.attrs.get('estado', 'sin datos')}")

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
               f"rf del periodo = (1 + {rf_ea:.2%})^(1/{m}) − 1 = {rf:.6f}."
               + (" Con topes por sector activos no se dibuja la nube al azar (no respetaría esos topes)." if groups else ""))

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

    _explain("¿Cómo leo esta gráfica?", AYUDA["markowitz"])
    return {"gmv": gmv, "tangent": tangent, "personal": personal, "top": top}


def _views_editor(assets, default_views):
    st.markdown("**Opiniones (views) del equipo.** Déjalo vacío si no hay evidencia: no se inventa convicción.")
    cols = ["id", "tipo", "activo", "contra", "Q", "Q es", "omega", "confianza", "conocida desde", "vence", "tesis", "fuente",
            "publicada", "autor", "evidencia contraria"]
    df = pd.DataFrame([v + [None] * (len(cols) - len(v)) for v in default_views], columns=cols)
    df = df.astype({c: "object" for c in ["id", "tipo", "activo", "contra", "Q es", "tesis", "fuente", "autor", "evidencia contraria"]}
                   | {"Q": "float64", "omega": "float64", "confianza": "float64"})
    df["vence"] = pd.to_datetime(df["vence"])
    df["publicada"] = pd.to_datetime(df["publicada"])
    df["conocida desde"] = pd.to_datetime(df["conocida desde"])
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
            "conocida desde": st.column_config.DateColumn("conocida desde", help="Antes de esta fecha la view no se usa (sin look-ahead)."),
            "publicada": st.column_config.DateColumn("publicada"),
            "autor": st.column_config.TextColumn("autor (estudiante)"),
        },
    )
    return edited


def _tab_black_litterman(lab: LabData, rf_ea: float, gamma: float, bounds, groups=None):
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
    _explain("¿Qué pongo aquí?", AYUDA["bl_parametros"])

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
            ["V1", "absoluta", "A", None, Q[0], "exceso", Om[0][0], None, None, None, ctrl["descripcion"][0]],
            ["V2", "relativa", "A", "B", Q[1], "exceso", Om[1][1], None, None, None, ctrl["descripcion"][1]],
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
        known = r.get("conocida desde")
        known = None if known is None or pd.isna(known) else pd.Timestamp(known).date()
        views.append(View(str(r["id"]), p_row, q, omega=omega, confidence=conf, expires_at=exp, thesis=str(r.get("tesis") or ""),
                          author="" if pd.isna(r.get("autor")) else str(r.get("autor")), known_at=known))
    incomplete = [str(r["id"]) for _, r in edited.dropna(subset=["id", "activo", "Q"]).iterrows()
                  if any(pd.isna(r.get(c)) or str(r.get(c)).strip() == "" for c in ("fuente", "publicada", "autor", "evidencia contraria"))]
    if incomplete and not is_control:
        st.warning("Registro incompleto (fuente, fecha de publicación, autor o evidencia contraria) en: " + ", ".join(incomplete)
                   + ". La guía exige registrarlos para cada view.")

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

    st.session_state["lab_view_ids"] = list(vs.used)
    st.session_state["lab_views"] = views  # para el rebalanceo y el backtest (cada una se usa solo mientras rige)
    st.session_state["lab_bl_params"] = {"delta": delta, "tau": tau, "w_ref": w_ref}

    def opt(mu_excess, sigma, label):
        return personal_optimum(mu_excess + rf, sigma, gamma, bounds, groups=groups), label

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
        st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
        st.caption("La comparación principal cambia solo μ (misma Σ y mismas cotas). La variante con Σ predictiva = Σ + M se "
                   "muestra aparte porque mezcla incertidumbre de la media con riesgo.")

    if res.n_views:
        st.markdown("**Sensibilidad:** ¿cuánto cambian la posterior y los pesos si las views son más o menos inciertas, o si τ cambia?")
        rows = []
        for label, k_omega, k_tau in (("Ω × 0,25 (más confianza)", 0.25, 1), ("Base", 1, 1), ("Ω × 4 (menos confianza)", 4, 1),
                                      ("τ × 0,5", 1, 0.5), ("τ × 2", 1, 2)):
            scaled = ViewSet(P=vs.P, Q=vs.Q, Omega=vs.Omega * k_omega, used=vs.used)
            try:
                alt = posterior(lab.sigma, res.prior, tau * k_tau, scaled)
            except ValueError:
                continue
            o = personal_optimum(alt.posterior + rf, lab.sigma, gamma, bounds, groups=groups)
            row = {"escenario": label} | {f"μ {a}": alt.posterior[a] * m for a in assets}
            if o.ok:
                row |= {f"w {a}": o.weights[a] for a in assets}
            rows.append(row)
        sens = pd.DataFrame(rows).set_index("escenario")
        st.dataframe(sens.style.format("{:.2%}", na_rep="—"))

    _explain("¿Qué es Black-Litterman?", AYUDA["bl"])
    return res


def _tab_rebalance(lab: LabData, gamma: float, bounds, groups=None):
    ctrl = _load_json("rebalanceo_control.json")
    st.caption("Simulación contable (paper trading): no hay bróker ni órdenes reales. Valores iniciales de "
               "rebalanceo_control.json (sintético). La política la define el equipo.")
    assets = ctrl["assets"]
    base = pd.DataFrame({
        "activo": assets, "cantidad": ctrl["cantidades"], "precio anterior": ctrl["precios_iniciales"],
        "precio nuevo": ctrl["precios_nuevos"], "peso objetivo": ctrl["pesos_objetivo"],
    })
    edited = st.data_editor(base, key="lab_reb_book", num_rows="dynamic", hide_index=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    cash = c1.number_input("Caja inicial", value=float(ctrl["caja"]), step=100.0, key="lab_reb_cash",
                           help="Efectivo disponible antes de operar.")
    cost = c2.number_input("Costo por nominal negociado", value=float(ctrl["costo_por_nominal"]), min_value=0.0, step=0.0005,
                           format="%.4f", key="lab_reb_cost", help="Comisión como fracción de cada compra o venta (0,001 = 0,1 %).")
    band = c3.number_input("Banda de no operación (deriva máx.)", value=0.05, min_value=0.0, max_value=1.0, step=0.01,
                           format="%.2f", key="lab_reb_band", help="Valor de ejemplo: la banda es decisión del equipo.")
    cash_min = c4.number_input("Caja mínima", value=0.0, min_value=0.0, step=50.0, key="lab_reb_cashmin",
                               help="Efectivo que siempre se deja aparte; los pesos objetivo se aplican al resto.")
    fractional = c5.toggle("Fracciones de unidad", value=bool(ctrl["fracciones"]), key="lab_reb_frac")
    _explain("¿Qué pongo aquí?", AYUDA["rebalanceo_parametros"])
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
        plan = plan_rebalance(book, p1, target, cost, fractional=fractional, cash_minimum=cash_min)
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
               "La comparación de estrategias en el tiempo está en la pestaña «Backtest».")

    if lab.returns is not None and len(lab.returns) > 60:
        _policy_simulation(lab, gamma, bounds, groups, cost, band, cash_min)

    _explain("¿Qué es rebalancear?", AYUDA["rebalanceo"])


def _policy_simulation(lab: LabData, gamma, bounds, groups, cost, band, cash_min):
    st.markdown("#### Simular la política en el tiempo (con reestimación y libro de eventos)")
    st.caption("Cada periodo es un evento de precio; el vencimiento o la entrada en vigencia de una view registrada en "
               "Black-Litterman es un evento de información. En cada decisión se reestiman μ y Σ SOLO con la ventana "
               "conocida en esa fecha. Los parámetros son decisión del equipo (los valores iniciales son ejemplos).")
    n_total = len(lab.returns)
    c1, c2, c3, c4 = st.columns(4)
    window = c1.number_input("Ventana de estimación (obs.)", min_value=len(lab.mu) + 5, max_value=max(n_total // 2, len(lab.mu) + 6),
                             value=min(120, max(n_total // 2, len(lab.mu) + 6)), step=10, key="lab_pol_window")
    horizon = c2.number_input("Periodos a simular (los últimos)", min_value=10, max_value=max(n_total - int(window) - 1, 11),
                              value=min(250, max(n_total - int(window) - 1, 11)), step=10, key="lab_pol_h")
    every = c3.number_input("Regla periódica: cada (días, 0 = no)", min_value=0, value=30, step=5, key="lab_pol_days")
    wait = c4.number_input("Espera mínima entre operaciones (días)", min_value=0, value=5, step=1, key="lab_pol_wait")
    c1, c2, c3 = st.columns(3)
    max_turn = c1.number_input("Rotación máxima por decisión (0 = sin tope)", min_value=0.0, value=0.0, step=0.05,
                               format="%.2f", key="lab_pol_turn")
    use_cb = c2.toggle("Regla costo-beneficio (P85)", value=False, key="lab_pol_cb",
                       help="No operar si la mejora de utilidad estimada no supera los costos más un margen.")
    margin = c3.number_input("Margen costo-beneficio (utilidad por periodo)", value=0.0, step=0.0001, format="%.5f",
                             key="lab_pol_margin", disabled=not use_cb)
    info_events = st.toggle("Las views que vencen o entran en vigencia disparan revisión", value=True, key="lab_pol_info")
    rule = st.radio("Objetivo recalculado en cada decisión", ["1/N", "GMV", "Óptimo personal", "BL posterior"], horizontal=True,
                    key="lab_pol_target")
    _explain("¿Qué significa cada regla?", AYUDA["politica"])
    views = st.session_state.get("lab_views", []) if rule == "BL posterior" else []
    bl = st.session_state.get("lab_bl_params", {})
    w_ref = bl.get("w_ref")
    if w_ref is not None and list(w_ref.index) != list(lab.returns.columns):
        w_ref = None
    policy = RebalancePolicy(cost_rate=cost, weight_band=band if band > 0 else None, calendar_days=int(every) or None,
                             min_days_between=int(wait), max_turnover=max_turn or None, cash_minimum=cash_min,
                             information_events=info_events, cost_benefit_margin=margin if use_cb else None)
    try:
        run = simulate_policy(lab.returns, policy, rule=rule, window=int(window), horizon=int(horizon), gamma=gamma,
                              bounds=bounds, groups=groups, views=views, bl_delta=bl.get("delta", 3.0),
                              bl_tau=bl.get("tau", 0.05), rf_period=0.0, w_ref=w_ref)
    except ValueError as exc:
        st.error(str(exc))
        return
    log = pd.DataFrame([{
        "evento": d.event_id, "acción": d.action, "disparador": d.trigger, "motivo": d.reason,
        "ventana": f"{pd.Timestamp(d.window[0]).date()} a {pd.Timestamp(d.window[1]).date()}" if d.window else "",
        "pesos teóricos": ", ".join(f"{k} {v:.0%}" for k, v in d.theoretical.items()) if d.theoretical is not None else "",
        "pesos realizados": ", ".join(f"{k} {v:.0%}" for k, v in d.realized.items()) if d.realized is not None else "",
        "costos": d.plan.costs if d.plan is not None and d.action == ACTION_REBALANCE else 0.0,
    } for d in run.log])
    trades = log[log["acción"] == ACTION_REBALANCE]
    st.session_state["lab_rebalance_ids"] = trades["evento"].tolist()
    st.session_state["lab_trigger_ids"] = [d.event_id for d in run.log if d.action == ACTION_REBALANCE and d.event_id.startswith("view-")]
    last_prices = run.prices.iloc[-1]
    hold = run.initial_book.equity(last_prices)
    final = run.rebalancer.book.equity(last_prices)
    a, b, c, d = st.columns(4)
    a.metric("Operaciones", len(trades))
    b.metric("Abstenciones / suspensiones / duplicados", f"{(log['acción'] != ACTION_REBALANCE).sum()}")
    c.metric("Costos totales", f"{trades['costos'].sum():,.2f}")
    d.metric("Patrimonio final vs. no operar", f"{final:,.0f}", delta=f"{final - hold:,.0f}")
    with st.expander("Ver el libro de eventos completo (ventana, pesos teóricos y realizados, motivo)"):
        st.dataframe(log.style.format({"costos": "{:,.2f}"}), hide_index=True)
    st.caption(f"Capital inicial 10.000 comprado a los pesos objetivo del {pd.Timestamp(run.prices.index[0]).date()} "
               "(sin costo, base común). Precios reconstruidos con los rendimientos de la muestra.")


def _tab_backtest(lab: LabData, rf_ea: float, gamma: float, bounds, groups=None):
    if lab.returns is None:
        st.info("El backtest necesita una serie de rendimientos: elige el laboratorio sintético o los datos de mercado.")
        return
    n = len(lab.returns)
    st.caption("Compara estrategias con el mismo universo, periodo, frecuencia de rebalanceo y costos. En cada fecha solo "
               "se usa información anterior (sin mirar el futuro). Elijan los parámetros mirando la **validación**; la "
               "**prueba final** se mira al final, una vez.")
    c1, c2, c3, c4 = st.columns(4)
    window = c1.number_input("Ventana de estimación (obs.)", min_value=len(lab.mu) + 5, max_value=max(n - 20, len(lab.mu) + 6),
                             value=min(max(120, len(lab.mu) + 5), max(n - 20, len(lab.mu) + 6)), step=10, key="lab_bt_window")
    every = c2.number_input("Rebalancear cada (periodos)", min_value=1, value=21 if lab.m >= 52 else 3, step=1, key="lab_bt_every")
    cost = c3.number_input("Costo por nominal negociado", min_value=0.0, value=0.001, step=0.0005, format="%.4f", key="lab_bt_cost")
    share = c4.slider("Fracción para validación", 0.2, 0.8, 0.5, 0.05, key="lab_bt_share")
    strategies = st.multiselect("Estrategias", ALL_STRATEGIES, default=ALL_STRATEGIES, key="lab_bt_strats")
    c1, c2, c3 = st.columns([2, 1, 1])
    estimators = c1.multiselect("Estimadores de Σ a comparar (candidatos del equipo)", ESTIMATORS, default=["muestral"],
                                key="lab_bt_estimators")
    lam = c2.number_input("λ de EWMA", value=0.94, min_value=0.5, max_value=0.999, step=0.01, format="%.3f", key="lab_bt_lambda")
    criterion = c3.selectbox("Criterio de selección en validación", ["Sharpe anual", "rendimiento anual (CAGR)", "máximo drawdown"],
                             key="lab_bt_criterion")
    views = st.session_state.get("lab_views", [])
    bl = st.session_state.get("lab_bl_params", {})
    w_ref = bl.get("w_ref")
    if w_ref is not None and list(w_ref.index) != list(lab.returns.columns):
        w_ref = None
    st.caption(f"Black-Litterman usará {len(views)} view(s) registrada(s) en su pestaña, cada una solo entre su fecha "
               "«conocida desde» y su vencimiento." if views else
               "Sin views registradas: Black-Litterman usa solo el prior (con γ = δ y w_ref = 1/N coincide con 1/N, y se rotula así).")
    _explain("¿Qué pongo aquí?", AYUDA["backtest_parametros"])
    if not strategies or not estimators:
        return
    if st.button("Ejecutar backtest", key="lab_bt_run", type="primary"):
        cfg = BacktestConfig(window=int(window), rebalance_every=int(every), cost_rate=cost, rf_period=rf_per_period(rf_ea, lab.m),
                             gamma=gamma, bounds=bounds, periods_per_year=lab.m, validation_share=share, groups=groups,
                             ewma_lambda=lam, views=views or None, bl_delta=bl.get("delta", 3.0), bl_tau=bl.get("tau", 0.05),
                             w_ref=w_ref)
        with st.spinner("Simulando..."):
            try:
                st.session_state["lab_bt_result"] = (walk_forward(lab.returns, cfg, strategies, estimators),
                                                     tuple(lab.returns.columns))
            except ValueError as exc:
                st.error(str(exc))
                return
    stored = st.session_state.get("lab_bt_result")
    if not stored or stored[1] != tuple(lab.returns.columns):
        st.caption("Pulsa «Ejecutar backtest» (puede tardar unos segundos con muchos activos).")
        return
    res = stored[0]
    fig = go.Figure()
    for name, run in res.runs.items():
        fig.add_trace(go.Scatter(x=run.wealth.index, y=run.wealth, mode="lines", name=name))
    fig.add_vline(x=res.test_start, line=dict(color=STAR_WHITE, dash="dash"))
    fig.add_annotation(x=res.test_start, y=1, yref="paper", text="inicio prueba final", showarrow=False, font=dict(color=STAR_WHITE))
    fig.update_layout(title="Valor neto de costos (empieza en 1)", height=420, **LAYOUT)
    st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
    pct_cols = ["rendimiento anual (CAGR)", "volatilidad anual", "máximo drawdown", "rendimiento acumulado",
                "rotación media por decisión", "costos totales", "cambio medio de pesos objetivo"]
    st.dataframe(res.metrics.style.format({c: "{:.2%}" for c in pct_cols} | {"Sharpe anual": "{:.2f}"}, na_rep="—"))
    try:
        pick = select_by_validation(res, criterion=criterion, higher_is_better=True)
        st.success(f"**Elegido en validación ({criterion}):** {pick.chosen}. {pick.note}")
        sel = pd.DataFrame({"validación": pick.validation_metrics, "prueba final (sin reajustar)": pick.test_metrics}).loc[
            ["rendimiento anual (CAGR)", "volatilidad anual", "Sharpe anual", "máximo drawdown"]]
        st.dataframe(sel.style.format("{:.2%}", subset=pd.IndexSlice[["rendimiento anual (CAGR)", "volatilidad anual", "máximo drawdown"], :])
                     .format("{:.2f}", subset=pd.IndexSlice[["Sharpe anual"], :]))
    except ValueError as exc:
        st.warning(str(exc))
    _explain("¿Qué significa cada número?", AYUDA["indicadores"])
    for name, run in res.runs.items():
        if run.failures:
            st.warning(f"{name}: {len(run.failures)} fecha(s) sin solución del optimizador; se conservó la cartera anterior. "
                       f"Primera: {run.failures[0]}")
    st.caption("Reporten también las variantes que probaron y los resultados adversos: elegir solo la que mejor lució "
               "después de verla es sobreajuste. Un backtest ganador no prueba causalidad ni que se repita.")
    _explain("¿Qué es un backtest?", AYUDA["backtest"])


def _benchmark_returns(lab: LabData, bench: str) -> "pd.Series | None":
    """Rendimientos simples del benchmark en la frecuencia y la moneda base del laboratorio."""
    result = st.session_state.get("comparison_result")
    asset = fetch_asset_data(bench, result.common_start, result.common_end + pd.Timedelta(days=1))
    if not asset.ok:
        st.error(f"{bench}: {asset.error}")
        return None
    prices = resample_prices(asset.prices, result.frequency)[["adjusted_close"]]
    if prices.index.tz is not None:
        prices.index = prices.index.tz_localize(None)
    bench_ccy = str(asset.currency or lab.currency or "USD").upper()
    if lab.currency and bench_ccy != lab.currency:
        try:
            prices, note = _to_base_currency(prices, bench_ccy, lab.currency)
        except ValueError as exc:
            st.error(f"El benchmark está en {bench_ccy} y la cartera en {lab.currency}: {exc}")
            return None
        st.caption(f"Benchmark: {note}")
    return prices["adjusted_close"].pct_change(fill_method=None)


PORTFOLIO_NAMES = {"gmv": "Mínima varianza (GMV)", "tangent": "Tangente (máximo Sharpe)", "personal": "Óptimo personal",
                   "top": "Máximo rendimiento esperado"}


def _portfolio_series(lab: LabData, results) -> "dict[str, pd.Series]":
    """Rendimientos históricos (pesos constantes) de cada cartera óptima válida y de 1/N."""
    out = {}
    for key, name in PORTFOLIO_NAMES.items():
        res = (results or {}).get(key)
        if res is not None and res.ok:
            out[name] = portfolio_return_series(lab.returns, res.weights)
    n = lab.returns.shape[1]
    out["1/N (referencia simple)"] = portfolio_return_series(lab.returns, pd.Series(1.0 / n, index=lab.returns.columns))
    return out


def _capm_and_performance(lab: LabData, results, betas: pd.Series, mret: pd.Series, rf_ea: float, bench_name: str):
    """Rendimiento requerido por CAPM (SML) por activo y cartera, y desempeño frente al benchmark."""
    if betas.empty:
        return
    m = lab.m
    rf_p = rf_per_period(rf_ea, m)
    common = mret.reindex(lab.returns.index)
    st.markdown("**Rendimiento requerido por CAPM y línea del mercado de títulos (SML)**")
    erp_mode = st.radio("Prima de mercado (ERP) — decisión del equipo",
                        ["Histórica del benchmark en esta ventana", "Escrita por el equipo"], horizontal=True,
                        key="lab_capm_erp_mode")
    if erp_mode == "Escrita por el equipo":
        erp = st.number_input("ERP anual", value=0.0, step=0.005, format="%.4f", key="lab_capm_erp",
                              help="Prima esperada del mercado sobre rf; el equipo la justifica (fuente, periodo, moneda).")
    else:
        erp = historical_erp(common, rf_p, m)
        st.caption(f"ERP histórica de {bench_name} = (media de su rendimiento − rf del periodo) × {m} = **{erp:.2%}** anual "
                   "en la misma muestra. Es una estimación del pasado, no una predicción.")
    rows = []
    for a, b in betas.items():
        rows.append({"activo o cartera": a, "beta": b, "requerido CAPM": capm_required_return(rf_ea, b, erp),
                     "esperado histórico (μ·m)": float(lab.mu[a] * m)})
    port_betas = {}
    for key, name in PORTFOLIO_NAMES.items():
        res = (results or {}).get(key)
        if res is None or not res.ok:
            continue
        try:
            pb = portfolio_beta(res.weights, betas)
        except ValueError:
            continue
        port_betas[name] = pb
        rows.append({"activo o cartera": name, "beta": pb, "requerido CAPM": capm_required_return(rf_ea, pb, erp),
                     "esperado histórico (μ·m)": float(res.weights @ lab.mu * m)})
    capm_df = pd.DataFrame(rows)
    capm_df["diferencia (esperado − requerido)"] = capm_df["esperado histórico (μ·m)"] - capm_df["requerido CAPM"]
    st.dataframe(capm_df.style.format({c: "{:.2%}" for c in capm_df.columns if c not in ("activo o cartera", "beta")}
                                      | {"beta": "{:.3f}"}), hide_index=True)
    xs = np.linspace(min(0.0, capm_df["beta"].min() - 0.2), max(2.0, capm_df["beta"].max() + 0.2), 30)
    fig = go.Figure(go.Scatter(x=xs, y=[capm_required_return(rf_ea, x, erp) for x in xs], name="SML", line=dict(color=ACCENT_GOLD)))
    is_port = capm_df["activo o cartera"].isin(port_betas.keys())
    fig.add_trace(go.Scatter(x=capm_df.loc[~is_port, "beta"], y=capm_df.loc[~is_port, "esperado histórico (μ·m)"],
                             mode="markers+text", text=capm_df.loc[~is_port, "activo o cartera"], textposition="top center",
                             name="activos (esperado histórico)", marker=dict(size=9, color=ELECTRIC_BLUE)))
    fig.add_trace(go.Scatter(x=capm_df.loc[is_port, "beta"], y=capm_df.loc[is_port, "esperado histórico (μ·m)"],
                             mode="markers", name="carteras", marker=dict(size=12, symbol="star", color=STAR_WHITE),
                             text=capm_df.loc[is_port, "activo o cartera"], hovertemplate="%{text}<extra></extra>"))
    fig.update_layout(title=f"SML: rf = {rf_ea:.2%}, ERP = {erp:.2%}, proxy de mercado = {bench_name}",
                      xaxis_title="Beta", yaxis_title="Rendimiento anual", yaxis_tickformat=".0%", height=380, **LAYOUT)
    st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
    st.caption(f"Declarado: proxy de mercado {bench_name}, rf = {rf_ea:.2%} EA (supuestos del laboratorio), ventana "
               f"{lab.returns.index[0].date()} a {lab.returns.index[-1].date()}, frecuencia {lab.frequency}. Un punto sobre la SML "
               "rindió en la muestra más de lo que su beta exige; no implica que lo siga haciendo.")

    st.markdown(f"**Desempeño frente al benchmark {bench_name} (misma muestra y frecuencia)**")
    table = performance_table(_portfolio_series(lab, results) | {f"Benchmark {bench_name}": common}, common, rf_p, m)
    show = table.rename(columns={"n": "n", "ann_return": "rendimiento anual", "ann_vol": "volatilidad anual", "sharpe": "Sharpe",
                                 "beta": "beta", "r_squared": "R²", "systematic_share": "riesgo sistemático",
                                 "idiosyncratic_share": "riesgo no sistemático", "treynor": "Treynor",
                                 "jensen_alpha": "alfa de Jensen", "tracking_error": "error de seguimiento",
                                 "information_ratio": "razón de información"})
    pct = ["rendimiento anual", "volatilidad anual", "riesgo sistemático", "riesgo no sistemático", "Treynor",
           "alfa de Jensen", "error de seguimiento"]
    st.dataframe(show.style.format({c: "{:.2%}" for c in pct if c in show} | {c: "{:.3f}" for c in
                                   ("Sharpe", "beta", "R²", "razón de información") if c in show}, na_rep="—"))
    _explain("¿Qué significa cada indicador?", AYUDA["desempeno"])


def _market_betas(lab: LabData, results, rf_ea: float = 0.0):
    """Betas de los activos reales (OLS y Cov/Var), beta de cada cartera y Hamada sobre un activo."""
    st.markdown("#### Beta de los activos frente a un benchmark")
    bench = st.text_input("Ticker del benchmark (decisión del equipo; ej. ^GSPC, ^COLCAP)", value="", key="lab_beta_bench")
    if not bench.strip():
        return
    mret = _benchmark_returns(lab, bench.strip())
    if mret is None:
        return
    fits = {a: beta_ols(lab.returns[a], mret) for a in lab.returns.columns}
    table = pd.DataFrame({
        "beta (OLS)": {a: f.beta for a, f in fits.items()},
        "beta (Cov/Var)": {a: f.beta_cov_ratio for a, f in fits.items()},
        "diferencia": {a: f.beta - f.beta_cov_ratio for a, f in fits.items()},
        "alfa (por periodo)": {a: f.alpha for a, f in fits.items()},
        "EE": {a: f.std_error for a, f in fits.items()},
        "R²": {a: f.r_squared for a, f in fits.items()},
        "riesgo sistemático": {a: f.r_squared for a, f in fits.items()},
        "riesgo no sistemático": {a: 1 - f.r_squared for a, f in fits.items()},
        "n": {a: f.n for a, f in fits.items()},
        "estado": {a: f.status for a, f in fits.items()},
    })
    table.index.name = "activo"
    st.dataframe(table.style.format({"beta (OLS)": "{:.4f}", "beta (Cov/Var)": "{:.4f}", "diferencia": "{:.1e}",
                                     "alfa (por periodo)": "{:.6f}", "EE": "{:.3f}", "R²": "{:.2f}",
                                     "riesgo sistemático": "{:.1%}", "riesgo no sistemático": "{:.1%}"}, na_rep="—"))
    st.caption(f"Beta frente a {bench.strip().upper()} en {lab.currency or 'la moneda de la Comparación'} (sensibilidad a esa "
               "referencia, no automáticamente al «mercado» teórico). La beta sale por dos caminos —pendiente de la regresión "
               "OLS y Cov(activo, benchmark)/Var(benchmark)— que deben coincidir (P2-31); la columna «diferencia» lo muestra. "
               "rf = 0 en esta tabla porque se usa la misma muestra para todos. **Riesgo sistemático = R²**: parte de la "
               "varianza del activo que explica el benchmark (β²σ²_m/σ²); el resto (1 − R²) es no sistemático y se puede "
               "diversificar.")
    st.session_state["lab_bench_returns"] = mret
    st.session_state["lab_bench_name"] = bench.strip().upper()

    ok = {a: f.beta for a, f in fits.items() if f.status == "ok"}
    betas = pd.Series(ok, dtype=float)

    st.markdown("**Beta de cada cartera (suma ponderada de las betas de arriba)**")
    if not results:
        st.info("Abre el módulo «Markowitz y fronteras» para calcular las carteras.")
    else:
        names = {"gmv": "Mínima varianza (GMV)", "tangent": "Tangente (máximo Sharpe)", "personal": "Óptimo personal",
                 "top": "Máximo rendimiento esperado"}
        rows = []
        for key, name in names.items():
            res = results.get(key)
            if res is None or not res.ok:
                rows.append({"cartera": name, "beta de cartera": None, "nota": "sin cartera válida"})
                continue
            try:
                rows.append({"cartera": name, "beta de cartera": portfolio_beta(res.weights, betas), "nota": ""})
            except ValueError as exc:
                rows.append({"cartera": name, "beta de cartera": None, "nota": str(exc)})
        st.dataframe(pd.DataFrame(rows).style.format({"beta de cartera": "{:.4f}"}, na_rep="—"), hide_index=True)
        st.caption("β_cartera = Σ wᵢ βᵢ (guía, sección 8; P102 y P104). Solo vale si todas las betas salen de la misma muestra, "
                   "el mismo benchmark y la misma convención de rendimientos, como en esta tabla; si se cambia alguno, hay "
                   "que recalcular todas.")

    _capm_and_performance(lab, results, betas, mret, rf_ea, bench.strip().upper())

    st.markdown("**Hamada sobre un activo real: desapalancar y reapalancar**")
    if betas.empty:
        st.info("Ningún activo tiene beta calculable con este benchmark.")
        return
    c1, c2, c3, c4, c5 = st.columns(5)
    asset = c1.selectbox("Activo", list(betas.index), key="lab_hamada_asset")
    de_now = c2.number_input("D/E actual (decisión del equipo)", value=0.0, min_value=0.0, step=0.05, format="%.4f",
                             key="lab_hamada_de", help="Deuda/patrimonio actual de esa empresa, de sus estados financieros.")
    tax = c3.number_input("Impuesto (decisión del equipo)", value=0.0, min_value=0.0, max_value=1.0, step=0.01,
                          format="%.4f", key="lab_hamada_tax", help="Tasa marginal de impuestos de esa empresa (0,35 = 35 %).")
    beta_d = c4.number_input("Beta de la deuda (decisión del equipo)", value=0.0, step=0.05, format="%.4f",
                             key="lab_hamada_bd", help="0 = la deuda no tiene riesgo sistemático.")
    de_target = c5.number_input("D/E objetivo (decisión del equipo)", value=0.0, min_value=0.0, step=0.05, format="%.4f",
                                key="lab_hamada_target", help="Estructura de capital a la que se reapalanca.")
    b_l = float(betas[asset])
    b_u = unlever_beta(b_l, de_now, tax, beta_d)
    b_new = relever_beta(b_u, de_target, tax, beta_d)
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Beta observada de {asset} (βL)", f"{b_l:.4f}")
    m2.metric("Beta desapalancada (βU)", f"{b_u:.4f}")
    m3.metric(f"Beta reapalancada a D/E = {de_target:g}", f"{b_new:.4f}")
    st.caption("βU = [βL + β_deuda·(1 − t)·D/E] / [1 + (1 − t)·D/E] y βL' = βU + (βU − β_deuda)·(1 − t)·D/E' (Hamada). "
               "Los cuatro valores son del equipo y dependen de cada empresa: no se usan los del caso Alimentos. Con todo "
               "en 0 la beta no cambia.")


def _tab_capm(lab: LabData, results=None, rf_ea: float = 0.0):
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

    st.markdown("#### Proyección y valoración del caso (5 años)")
    st.info("**Pendiente de confirmar:** la regla del caso que usa `capacidad_ventas` y `capex_venta_adicional` para "
            "calcular el CAPEX y la depreciación está en el PDF del caso, que no está en el repositorio. Mientras el "
            "equipo la confirma, el CAPEX y la depreciación de cada año se escriben a mano en la tabla.")
    _explain("¿Qué pongo aquí?", AYUDA["valoracion_entradas"])
    c1, c2, c3 = st.columns(3)
    kd = c1.number_input("Kd efectiva anual", value=float(params["kd_EA"]), step=0.005, format="%.4f", key="lab_val_kd",
                         help="Del caso: 13,5 %. El equipo debe confirmar que está en COP, igual que los flujos.")
    de = c2.number_input("D/E para los pesos del WACC", value=float(params["de_empresa"]), step=0.05, key="lab_val_de")
    g = c3.number_input("g terminal (nominal COP)", value=float(params["g_terminal"]), step=0.005, format="%.4f", key="lab_val_g")

    st.markdown("**Supuestos por año (entradas del equipo; los valores iniciales repiten el año 0 del caso)**")
    years = [1, 2, 3, 4, 5]
    inputs = pd.DataFrame({
        "año": years, "crecimiento ventas": [0.0] * 5, "costo variable %": [params["costo_variable"]] * 5,
        "gastos fijos": [float(params["gastos_fijos"])] * 5, "CAPEX": [float(params["depreciacion0"])] * 5,
        "depreciación": [float(params["depreciacion0"])] * 5, "deuda": [float(params["deuda_financiera"])] * 5,
    })
    inputs = st.data_editor(inputs, key="lab_val_inputs", hide_index=True, disabled=["año"],
                            column_config={"crecimiento ventas": st.column_config.NumberColumn(format="%.4f"),
                                           "costo variable %": st.column_config.NumberColumn(format="%.4f")})
    st.markdown("**Escenarios (magnitudes del equipo; 0 = sin escenario)**")
    c1, c2, c3, c4 = st.columns(4)
    fx = c1.number_input("Choque FX sobre insumos", value=0.0, step=0.05, format="%.2f", key="lab_val_fx",
                         help="0,20 = el dólar sube 20 % y encarece la parte importada del costo variable.")
    share = c2.number_input("Participación importada del costo", value=0.0, min_value=0.0, max_value=1.0, step=0.05,
                            format="%.2f", key="lab_val_share")
    lag = c3.number_input("Rezago para trasladar a precios (días)", value=60, min_value=0, max_value=365, step=15,
                          key="lab_val_lag", help="El caso menciona un rezago de 60 días en el margen.")
    kd_shift = c4.number_input("Cambio de Kd (tasa variable)", value=0.0, step=0.005, format="%.4f", key="lab_val_kdshift")
    scenario = Scenario(fx_shock=fx, imported_share=share, pass_through_lag_days=lag, kd_shift=kd_shift)
    try:
        proj = project(params, inputs["crecimiento ventas"].astype(float).tolist(), inputs["CAPEX"].astype(float).tolist(),
                       inputs["depreciación"].astype(float).tolist(), variable_cost=inputs["costo variable %"].astype(float).tolist(),
                       fixed_costs=inputs["gastos fijos"].astype(float).tolist(), debt=inputs["deuda"].astype(float).tolist(),
                       scenario=scenario)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.caption(f"Control: el año 0 reproduce EBIT₀ = {proj.table.loc[0, 'EBIT']:,.0f} (el caso dice {params['ebit0']:,.0f}).")
    show = ["ventas", "EBIT", "EBITDA", "NOPAT", "ΔNWC", "CAPEX", "FCFF", "intereses", "utilidad neta", "FCFE", "deuda/EBITDA"]
    st.dataframe(proj.table[show].style.format("{:,.0f}", subset=[c for c in show if c != "deuda/EBITDA"])
                 .format("{:.2f}", subset=["deuda/EBITDA"]))
    for note in proj.notes:
        st.error(note)

    kd_eff = kd + kd_shift
    w = wacc(ke_cop, kd_eff, params["tax_supuesto"], de)
    c1, c2, c3 = st.columns(3)
    c1.metric("WACC (COP)", _pct(w), help="E/(D+E)·Ke_COP + D/(D+E)·Kd·(1−t)")
    try:
        val = value_firm(proj, w, ke_cop, g)
    except ValueError as exc:
        st.error(str(exc))
        return
    c2.metric("Valor de la empresa (EV)", f"{val.enterprise_value:,.0f}")
    c3.metric("Peso del valor terminal", _pct(val.terminal_share))
    c1, c2, c3 = st.columns(3)
    c1.metric("Patrimonio por FCFF (EV − deuda)", f"{val.equity_fcff:,.0f}")
    c2.metric("Patrimonio por FCFE a Ke", f"{val.equity_fcfe:,.0f}")
    c3.metric("Diferencia (FCFE − FCFF)", f"{val.difference:,.0f}")
    st.caption("COP millones. " + val.explanation)

    gap = budget_target(proj, ke_cop, params["patrimonio_libros"])
    st.markdown(f"**Meta presupuestal (P113-P114):** Ke × patrimonio en libros = {ke_cop:.2%} × {params['patrimonio_libros']:,.0f} "
                f"= **{gap.required_net_income:,.0f}** de utilidad neta, que exige un EBIT de {gap.required_ebit:,.0f} en el año 1. "
                "Es una meta contable del caso, no la rentabilidad exigida de mercado.")
    st.dataframe(gap.gap_by_year.rename("brecha de EBIT (requerido − proyectado)").to_frame().T.style.format("{:,.0f}"))

    if st.toggle("Iterar D/E con el patrimonio estimado (P108, P119)", value=False, key="lab_val_iterate"):
        try:
            steps = iterate_capital_structure(params, proj, beta_u, g, start_de=de)
            st.dataframe(pd.DataFrame([vars(x) for x in steps]).style.format(
                {"debt_to_equity": "{:.4f}", "beta_levered": "{:.4f}", "ke_cop": "{:.2%}", "wacc": "{:.2%}", "equity": "{:,.0f}"}),
                hide_index=True)
            st.caption("Cada iteración: D/E = deuda / patrimonio estimado → se reapalanca β → Ke y WACC nuevos → se revalora.")
        except ValueError as exc:
            st.error(str(exc))

    grid = {}
    flows = proj.table.loc[1:, "FCFF"].tolist()
    for dg in (-0.01, -0.005, 0.0, 0.005, 0.01):
        col = {}
        for dw in (-0.02, -0.01, 0.0, 0.01, 0.02):
            try:
                col[f"WACC {w + dw:.2%}"] = discounted_cash_flow(flows, w + dw, g + dg).enterprise_value
            except ValueError:
                col[f"WACC {w + dw:.2%}"] = np.nan  # WACC <= g: sin valor terminal
        grid[f"g {g + dg:.2%}"] = col
    with st.expander("Sensibilidad del valor de la empresa (EV) a WACC y g"):
        st.dataframe(pd.DataFrame(grid).style.format("{:,.0f}", na_rep="WACC ≤ g"))
        st.caption("Si el EV cambia mucho con pequeños cambios de WACC o g, la conclusión depende de esos supuestos.")
    roic = st.number_input("ROIC estable para revisar la reinversión (decisión del equipo; 0 = no revisar)", value=0.0, step=0.01,
                           format="%.3f", key="lab_val_roic")
    if roic > 0:
        chk = reinvestment_check(proj, g, roic)
        (st.success if chk.consistent else st.warning)(chk.message)

    if lab.source == SOURCE_MARKET and lab.returns is not None:
        _market_betas(lab, results, rf_ea)

    erp = params["erp_madura"]
    xs = np.linspace(0, 2, 20)
    fig = go.Figure(go.Scatter(x=xs, y=[sml_required_return(params["rf_USD"], x, erp) for x in xs], name="SML",
                               line=dict(color=ACCENT_GOLD)))
    for label, b in (("Comparable", beta_c.beta), ("Empresa (reapalancada)", beta_l), ("Desapalancada", beta_u)):
        fig.add_trace(go.Scatter(x=[b], y=[sml_required_return(params["rf_USD"], b, erp)], mode="markers+text", text=[label],
                                 textposition="top left", marker=dict(size=11, color=STAR_WHITE), showlegend=False))
    fig.update_layout(title="SML del caso (USD, sin prima país)", xaxis_title="Beta", yaxis_title="Rendimiento requerido",
                      yaxis_tickformat=".0%", height=360, **LAYOUT)
    st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)

    _explain("¿Qué significan beta, CAPM y las demás palabras?", AYUDA["capm_valoracion"])


def _trace_context(lab: LabData) -> dict:
    """Campos de la plantilla de trazabilidad con valores reales del dato (o None, que la traza explica)."""
    ctx = {"frequency": lab.frequency or ("anual (parámetros dados)" if lab.m == 1 else None)}
    if lab.source == SOURCE_MARKET:
        result = st.session_state.get("comparison_result")
        ctx.update(currency=lab.currency or getattr(result, "base_currency", None),
                   source_fields=["Close con auto_adjust=True (cierre ajustado por dividendos y splits)"]
                   + ([f"{FX_TICKER_COP_PER_USD} (COP por USD) para la moneda base"] if lab.currency and lab.fx_note
                      and "Convertido" in lab.fx_note else []))
    elif lab.source == SOURCE_SYNTH:
        ctx.update(source_fields=["paquete_v2/data/precios_sinteticos_20.csv (columnas SIM1..SIM20)"])
    if lab.returns is not None:
        ctx.update(
            event_at=str(pd.Timestamp(lab.last_date).date()) if lab.last_date is not None else None,
            missing_data_rule=(f"Rendimientos simples sin rellenar huecos; los que cruzan un intervalo mayor al normal para la "
                               f"frecuencia {lab.frequency} se anulan ({lab.gap_removed}); luego máscara común de filas completas."),
            transformations=(["conversión a la moneda base: " + lab.fx_note] if lab.fx_note and "Convertido" in lab.fx_note else [])
            + ["orden por fecha", "pct_change(fill_method=None) por activo", "anulación de rendimientos sobre huecos",
               "máscara común (dropna)", "media y covarianza muestral ddof=1"],
        )
    triggers = st.session_state.get("lab_trigger_ids", [])
    if triggers:
        ctx["trigger_id"] = triggers[-1]
    return ctx


def _constraints_text(bounds, groups, unlimited: bool, assets) -> str:
    if unlimited:
        return "Pesos sin límites (cortos y apalancamiento permitidos); suma de pesos = 100 %."
    uniq = {tuple(b) for b in bounds}
    text = (f"Cada activo entre {list(uniq)[0][0]:.0%} y {list(uniq)[0][1]:.0%}" if len(uniq) == 1
            else "Cotas por activo: " + ", ".join(f"{a} [{b[0]:.0%}, {b[1]:.0%}]" for a, b in zip(assets, bounds)))
    if groups:
        text += "; topes por sector: " + ", ".join(f"{'+'.join(g)} ≤ {cap:.0%}" for g, cap in groups)
    return text + "; suma de pesos = 100 %."


def _tab_factsheet(lab: LabData, results, rf_ea, gamma, bounds, groups, sectors, unlimited):
    st.markdown("#### Ficha técnica del portafolio")
    st.caption("Estructura de la ficha técnica de los Fondos de Inversión Colectiva de la Superintendencia Financiera de "
               "Colombia (Decreto 1242 de 2013; Circular Básica Jurídica, Anexo 6). Es una **simulación académica**: los "
               "campos propios de un fondo real (valor del fondo, comisiones, calificación, custodio) se marcan «No aplica».")
    if not results:
        st.info("Abre el módulo «Markowitz y fronteras» para calcular las carteras.")
        return
    options = {"Tangente (máximo Sharpe)": ("tangent", f"Maximizar la razón de Sharpe con rf = {rf_ea:.2%} EA."),
               "Mínimo riesgo (GMV)": ("gmv", "Minimizar la varianza de la cartera."),
               "Mayor rendimiento esperado": ("top", "Maximizar el rendimiento esperado dentro de las restricciones."),
               "Óptimo personal": ("personal", f"Maximizar U = μ − (γ/2)σ² con γ = {gamma:g}.")}
    choice = st.selectbox("Cartera", list(options), key="lab_factsheet_choice")
    key, objective = options[choice]
    res = results.get(key)
    if res is None or not res.ok:
        st.warning(f"La cartera «{choice}» no tiene solución válida con estas restricciones ({getattr(res, 'status', 'N/D')}).")
        return
    m = lab.m
    stats = portfolio_stats(res.weights, lab.mu, lab.sigma)
    asset_ccy = None
    result = st.session_state.get("comparison_result")
    if lab.source == SOURCE_MARKET and result is not None:
        asset_ccy = {sm.ticker: sm.currency for sm in getattr(result, "summaries", [])}
    extra = [("Rendimiento esperado del modelo (μ·m)", _pct(stats.mean * m)),
             ("Volatilidad esperada del modelo (σ·√m)", _pct(stats.volatility * np.sqrt(m)))]
    bench = st.session_state.get("lab_bench_returns")
    if bench is not None and lab.returns is not None:
        b = beta_ols(portfolio_return_series(lab.returns, res.weights), bench.reindex(lab.returns.index))
        if b.status == "ok":
            extra.append((f"Beta frente a {st.session_state.get('lab_bench_name', 'benchmark')}", f"{b.beta:.3f}"))
    fs = build_factsheet(f"Cartera {choice} — {BRAND}", res.weights, lab.returns, m, lab.currency, objective,
                         _constraints_text(bounds, groups, unlimited, list(lab.mu.index)), rf_ea, TEAM, INSTITUTION,
                         asset_currency=asset_ccy, sectors=sectors or None, extra_risk=extra)
    def md_table(rows):  # tabla en Markdown: el texto largo se ajusta en vez de cortarse
        return "| Campo | Valor |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in rows)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**1. Características**")
        st.markdown(md_table(fs.general))
    with c2:
        st.markdown("**2. Política de inversión**")
        st.markdown(md_table(fs.policy))
    st.markdown("**3. Rentabilidad y volatilidad histórica** (efectiva anual por ventana)")
    st.dataframe(fs.performance.T.apply(lambda col: col.map(lambda v: "N/D" if pd.isna(v) else f"{v:.2%}")))
    if fs.performance.isna().all().all():
        st.caption("N/D: esta fuente no tiene serie de precios con fechas (caso docente con parámetros dados).")
    if fs.value_path is not None and len(fs.value_path) > 1:
        fig = go.Figure(go.Scatter(x=fs.value_path.index, y=fs.value_path, line=dict(color=ACCENT_GOLD), name="valor"))
        fig.update_layout(title=f"Evolución de 100.000 {lab.currency or ''} invertidos (pesos constantes, sin costos)",
                          height=320, **LAYOUT)
        st.plotly_chart(polish(fig), config=PLOTLY_CONFIG)
    c1, c2, c3 = st.columns(3)
    for col, series, title in ((c1, fs.composition_asset, "4. Composición por activo"),
                               (c2, fs.composition_currency, "Por moneda de origen"),
                               (c3, fs.composition_sector, "Por sector")):
        with col:
            st.markdown(f"**{title}**")
            if series.empty:
                st.caption("N/D" + (" — asignen sectores en «Cotas por activo y topes por sector»." if "sector" in title else ""))
            else:
                st.dataframe(series.rename("peso").to_frame().style.format("{:.2%}"))
    st.markdown("**5. Principales inversiones** (hasta 10, por |peso|)")
    st.dataframe(fs.top_holdings.rename("|peso|").to_frame().T.style.format("{:.2%}"))
    st.markdown("**6. Riesgo**")
    st.markdown(md_table(fs.risk))
    with st.expander("7. Campos de la ficha oficial que no aplican a una simulación"):
        for item in fs.not_applicable:
            st.write(f"- {item}: {NOT_APPLICABLE}")
    st.caption("Rentabilidades pasadas no garantizan rentabilidades futuras. No es asesoría financiera ni una oferta de "
               "inversión, y el bot no ejecuta órdenes.")
    st.download_button("Descargar ficha técnica (Markdown)", to_markdown(fs).encode("utf-8"),
                       file_name=f"ficha_tecnica_{key}.md", mime="text/markdown", key="lab_factsheet_md")


def _tab_export(lab: LabData, rf_ea, gamma, bounds, groups, results):
    text = snapshot_csv(lab.returns, lab.mu, lab.sigma)
    trace = build_trace(
        source=lab.source,
        rights="Datos sintéticos/caso docente o Yahoo Finance (uso académico; no redistribuir cotizaciones).",
        periods_per_year=lab.m, asset_order=list(lab.mu.index), snapshot_text=text,
        parameters={"rf_EA": rf_ea, "gamma": gamma, "bounds": [list(b) for b in bounds],
                    "groups": [[list(g_), cap] for g_, cap in (groups or [])], "frequency": lab.frequency},
        results=results or {}, solver=results["gmv"].solver if results else None,
        common_rows=None if lab.returns is None else len(lab.returns), rows_before_mask=lab.n_before,
        views_ids=st.session_state.get("lab_view_ids", []), rebalance_ids=st.session_state.get("lab_rebalance_ids", []),
        **_trace_context(lab),
    )
    files = export_bundle(trace, text)
    problems = verify_bundle(files)
    if problems:
        st.error("La exportación no es coherente: " + "; ".join(problems))
    else:
        st.success("Traza verificada: el hash coincide con el snapshot exportado, con parámetros y commit.")
    st.json(trace, expanded=False)
    c1, c2 = st.columns(2)
    c1.download_button("Descargar traza (JSON)", files["traza.json"], file_name=f"traza_{trace['analysis_id'][:8]}.json",
                       mime="application/json")
    c2.download_button("Descargar snapshot de datos (CSV)", files["snapshot.csv"], file_name=f"snapshot_{trace['analysis_id'][:8]}.csv",
                       mime="text/csv")
    st.caption("La traza conecta fuente → muestra → parámetros → resultado → commit, con los IDs de las views y de los "
               "rebalanceos usados. Cualquiera puede recalcular el SHA-256 del CSV y compararlo. La decisión del estudiante "
               "(`student_decision`) la completa el equipo; la app no la llena.")


# ---------------------------------------------------------------------------
# Entrada principal
# ---------------------------------------------------------------------------

def render_portfolio_lab() -> None:
    st.caption(
        "Asignación de capital: riesgo conjunto, Markowitz, Black-Litterman, rebalanceo simulado, beta/CAPM y "
        "valoración. Simulación académica: no envía órdenes ni constituye recomendación de inversión."
    )
    _explain("¿Qué es este laboratorio?", AYUDA["laboratorio"])

    _render_live_quote()
    st.markdown("---")

    source = st.radio("Fuente de datos del laboratorio", [SOURCE_TWO, SOURCE_SYNTH, SOURCE_MARKET], key="lab_source")
    if source == SOURCE_TWO:
        lab = _load_lab_data(source)
        st.info("**Caso docente de control.** Parámetros anuales dados (μ, Σ): sirve para reconstruir los cálculos a mano.")
    else:
        loaded = _load_lab_data(source)
        if loaded is None:
            st.warning("Primero ejecuta la sección **Comparación de activos** (arriba) para traer precios reales de Yahoo Finance.")
            return
        prices, m, label, frequency = loaded
        if source == SOURCE_SYNTH:
            st.warning("**MODO LABORATORIO SINTÉTICO.** Series generadas para practicar: **no son cotizaciones reales**.")
        else:
            st.success("**MODO MERCADO.** Precios históricos de Yahoo Finance traídos en la sección Comparación.")
        currency, fx_note = None, None
        if source == SOURCE_MARKET:
            from_ccy = str(getattr(st.session_state.get("comparison_result"), "base_currency", None) or "USD").upper()
            currency = st.selectbox(
                "Moneda base de la cartera (decisión del equipo)", list(SUPPORTED_BASES), index=0, key="lab_base_currency",
                help="La moneda del mandato la decide el equipo. USD por defecto. Con COP, cada precio se convierte con "
                     "USDCOP=X: P_COP = P_USD · FX, y los rendimientos quedan 1 + R_COP = (1 + R_USD)(1 + R_FX) (guía 3.2).")
            try:
                with st.spinner(f"Convirtiendo a {currency}..."):
                    prices, fx_note = _to_base_currency(prices, from_ccy, currency)
            except ValueError as exc:
                st.error(str(exc))
                return
            label = f"{label} Moneda base: {currency}."
            st.caption(f"**Moneda base: {currency}.** {fx_note}")
        all_assets = list(prices.columns)
        chosen = st.multiselect("Universo (decisión del equipo)", all_assets, default=all_assets, key=f"lab_universe_{source}")
        if len(chosen) < 2:
            st.error("Elige al menos 2 activos para formar una cartera.")
            return
        try:
            lab = _from_prices(source, prices, m, label, chosen, frequency)
        except ValueError as exc:
            st.error(str(exc))
            return
        lab.currency, lab.fx_note = currency, fx_note
    st.caption(lab.label + (" Frecuencia nativa: anual." if lab.m == 1 else f" Frecuencia nativa: {lab.m} periodos por año."))

    with st.container(border=True):
        st.markdown("**Reglas del ejercicio** (las decide el equipo; al abrir se ven las del ejemplo del profesor)")
        ctrl = _load_json("dos_activos.json")
        c1, c2, c3, c4 = st.columns(4)
        rf_ea = c1.number_input("Tasa libre de riesgo (efectiva anual)", value=float(ctrl["rf"]), step=0.005, format="%.4f", key="lab_rf",
                                help="Lo que ganarías al año **sin arriesgar nada**, por ejemplo prestándole al gobierno. "
                                     "0,03 = 3 %. Mira la pestaña Tasas soberanas.")
        gamma = c2.number_input("γ aversión al riesgo", value=float(ctrl["gamma"]), min_value=0.1, step=0.5, key="lab_gamma",
                                help="Qué tanto te asusta perder. 2 = te arriesgas bastante; 10 = prefieres ir a la segura.")
        lo = c3.number_input("Peso mínimo por activo", value=float(ctrl["bounds"][0][0]), step=0.05, format="%.2f", key="lab_lo",
                             help="Lo **menos** que puede tener cada empresa. 0 = puede quedar en cero.")
        hi = c4.number_input("Peso máximo por activo", value=float(ctrl["bounds"][0][1]), step=0.05, format="%.2f", key="lab_hi",
                             help="Lo **más** que puede tener cada empresa. 1 = hasta el 100 %; 0,25 = máximo 25 %.")
        unlimited = st.toggle("Sin límites de peso (cortos y apalancamiento ilimitados)", value=False, key="lab_unlimited",
                              help="Quita los límites de arriba: permite apostar en contra de una empresa o pedir prestado. Solo para comparar con la teoría.")
        max_target_ea = None
        if unlimited or lo < 0:
            max_target_ea = st.number_input(
                "Rendimiento objetivo máximo para dibujar la frontera (anual; decisión del equipo)", value=0.0, step=0.01,
                format="%.4f", key="lab_max_target",
                help="Con cortos el rendimiento esperado puede crecer sin fin; la frontera se dibuja hasta este valor. "
                     "0 = no dibujar más allá de lo que las cotas permitan.")
        _explain("¿Qué significa cada regla y qué pongo?", AYUDA["supuestos"])
        with st.expander("Cotas por activo y topes por sector (opcional)"):
            st.caption("Por defecto todos los activos usan el mínimo y máximo de arriba. Aquí se pueden cambiar por activo y "
                       "agrupar activos en sectores con un peso máximo por sector (decisión del equipo).")
            _explain("¿Qué pongo en esta tabla?", AYUDA["cotas"])
            assets = list(lab.mu.index)
            per_asset = st.data_editor(
                pd.DataFrame({"activo": assets, "mínimo": [lo] * len(assets), "máximo": [hi] * len(assets), "sector": [""] * len(assets)}),
                key=f"lab_bounds_{abs(hash((tuple(assets), lo, hi)))}", hide_index=True, disabled=["activo"])
            sectors = sorted({str(x).strip() for x in per_asset["sector"] if str(x).strip() and str(x) != "nan"})
            caps = {}
            if sectors:
                cap_df = st.data_editor(pd.DataFrame({"sector": sectors, "peso máximo": [1.0] * len(sectors)}),
                                        key=f"lab_caps_{abs(hash(tuple(sectors)))}", hide_index=True, disabled=["sector"])
                caps = dict(zip(cap_df["sector"], cap_df["peso máximo"].astype(float)))
    bounds = ([(None, None)] * len(lab.mu) if unlimited
              else [(float(r["mínimo"]), float(r["máximo"])) for _, r in per_asset.iterrows()])
    # La frontera muestra μ anualizado como μ·m (convención aritmética): el tope anual se divide entre m.
    max_target = max_target_ea / lab.m if max_target_ea else None
    groups = [([a for a, sec in zip(per_asset["activo"], per_asset["sector"]) if str(sec).strip() == name], cap)
              for name, cap in caps.items() if cap < 1.0] or None

    st.markdown(LAB_NAV_CSS, unsafe_allow_html=True)
    st.markdown("#### Módulos del laboratorio")
    st.caption("Elige un módulo; los supuestos de arriba aplican a todos.")
    with st.container(key="lab_nav"):
        tabs = st.tabs(LAB_MODULES)
    results = None
    with tabs[0]:
        w_test = _tab_risk(lab)
    with tabs[1]:
        _tab_stress(lab, w_test, bounds, groups)
    with tabs[2]:
        results = _tab_markowitz(lab, rf_ea, gamma, bounds, groups, max_target)
    with tabs[3]:
        _tab_black_litterman(lab, rf_ea, gamma, bounds, groups)
    with tabs[4]:
        _tab_rebalance(lab, gamma, bounds, groups)
    with tabs[5]:
        _tab_backtest(lab, rf_ea, gamma, bounds, groups)
    with tabs[6]:
        _tab_capm(lab, results, rf_ea)
    with tabs[7]:
        sector_map = {a: str(sec).strip() for a, sec in zip(per_asset["activo"], per_asset["sector"])
                      if str(sec).strip() and str(sec) != "nan"}
        _tab_factsheet(lab, results, rf_ea, gamma, bounds, groups, sector_map, unlimited)
    with tabs[8]:
        _tab_export(lab, rf_ea, gamma, bounds, groups, results)
