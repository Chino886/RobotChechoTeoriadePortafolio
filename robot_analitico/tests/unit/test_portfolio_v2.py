"""
Fase 2 (v2) - Capa de cartera, riesgo conjunto y Markowitz (guía V2, secc. 4-5).

Pruebas de aceptación cubiertas: P2-6, P2-7, P2-8, P2-9, P2-10, P2-11,
P2-13, P2-14, P2-15, P2-16 y P2-17, con el caso docente de dos activos
(paquete_v2/data/dos_activos.json) y las 20 series sintéticas del paquete.
Los controles analíticos se calculan aquí de forma independiente del solver.
Sin red.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.portfolio import (  # noqa: E402
    correlation_matrix,
    covariance_matrix,
    diagnose_covariance,
    efficient_frontier,
    gmv_analytic,
    max_expected_return,
    max_sharpe,
    min_variance,
    optimal_risky_share,
    optimal_risky_share_no_debt,
    personal_optimum,
    portfolio_log_return,
    portfolio_simple_return,
    portfolio_stats,
    rf_per_period,
    risk_contributions,
    simple_from_log,
    simple_returns_matrix,
    weighted_average_volatility,
)

PAQUETE = ROOT / "paquete_v2" / "data"
ATOL = 1e-8
RTOL = 1e-8
SOLVER_ATOL = 1e-6  # residuales normalizados del optimizador (guía, secc. 12)


@pytest.fixture(scope="module")
def two_assets():
    data = json.loads((PAQUETE / "dos_activos.json").read_text())
    mu = pd.Series(data["mu"], index=data["assets"])
    sigma = pd.DataFrame(data["Sigma"], index=data["assets"], columns=data["assets"])
    bounds = [tuple(b) for b in data["bounds"]]
    return mu, sigma, bounds, data["rf"], data["gamma"]


@pytest.fixture(scope="module")
def synthetic_prices():
    return pd.read_csv(PAQUETE / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")


# --- P2-6: agregación simple distinta del promedio de logs -----------------

def test_simple_aggregation_differs_from_mean_of_logs_p2_6():
    weights = [0.5, 0.5]
    simple = [0.10, -0.10]
    logs = np.log1p(simple)
    assert portfolio_simple_return(weights, simple) == pytest.approx(0.0, abs=1e-15)
    assert portfolio_log_return(weights, simple) == pytest.approx(0.0, abs=1e-15)
    assert float(np.dot(weights, logs)) < -1e-3  # el promedio de logs es negativo
    np.testing.assert_allclose(simple_from_log(logs), simple, atol=1e-15)


# --- P2-7 / P2-2: covarianza manual = pandas ddof=1, orden de etiquetas -----

def test_covariance_manual_matches_pandas_p2_7(synthetic_prices):
    sample = simple_returns_matrix(synthetic_prices)
    assert sample.n_before == 599 and sample.n_after == 599
    sigma = covariance_matrix(sample.returns)
    assert list(sigma.index) == list(synthetic_prices.columns) == list(sigma.columns)
    np.testing.assert_allclose(sigma, sample.returns.cov(ddof=1), atol=ATOL, rtol=RTOL)
    np.testing.assert_allclose(sigma, np.cov(sample.returns.to_numpy(), rowvar=False, ddof=1), atol=ATOL, rtol=RTOL)
    # Una entrada reconstruida "a mano"
    a, b = sample.returns["SIM1"], sample.returns["SIM2"]
    manual = ((a - a.mean()) * (b - b.mean())).sum() / (len(a) - 1)
    assert sigma.loc["SIM1", "SIM2"] == pytest.approx(manual, abs=ATOL, rel=RTOL)


def test_common_mask_records_rows_and_does_not_bridge_gaps():
    idx = pd.date_range("2024-01-01", periods=6, freq="D")
    prices = pd.DataFrame({"X": [100, 101, np.nan, 103, 104, 105], "Y": [50, 51, 52, 53, 54, 55]}, index=idx, dtype=float)
    sample = simple_returns_matrix(prices)
    # El hueco de X elimina los dos rendimientos que lo tocan; no se une 101->103 como un solo día.
    assert sample.n_before == 5 and sample.n_after == 3
    assert not np.isclose(sample.returns["X"], 103 / 101 - 1).any()


# --- P2-8: varianza cero produce correlación indefinida ---------------------

def test_zero_variance_gives_undefined_correlation_p2_8():
    returns = pd.DataFrame({"A": [0.01, -0.02, 0.03], "CONST": [0.0, 0.0, 0.0]})
    corr = correlation_matrix(covariance_matrix(returns))
    assert np.isnan(corr.loc["A", "CONST"]) and np.isnan(corr.loc["CONST", "CONST"])
    assert corr.loc["A", "A"] == pytest.approx(1.0)
    assert diagnose_covariance(covariance_matrix(returns)).zero_variance_assets == ["CONST"]


# --- P2-9: PSD, singularidad, condicionamiento y permutación ----------------

def test_psd_singular_indefinite_and_permutation_p2_9(two_assets, synthetic_prices):
    mu, sigma, _, _, _ = two_assets
    diag = diagnose_covariance(sigma)
    assert diag.psd and not diag.singular and diag.status == "definida positiva"
    assert diag.condition_number == pytest.approx(0.04 / 0.01, rel=0.2)  # orden de magnitud

    returns = simple_returns_matrix(synthetic_prices).returns
    duplicated = returns.assign(COPIA=returns["SIM1"])  # columna linealmente dependiente
    singular = diagnose_covariance(covariance_matrix(duplicated))
    assert singular.psd and singular.singular and singular.condition_number == float("inf")

    indefinite = pd.DataFrame([[1.0, 2.0], [2.0, 1.0]], index=["A", "B"], columns=["A", "B"])
    assert not diagnose_covariance(indefinite).psd

    # Permutar el orden de activos no cambia el riesgo si se reindexa por etiquetas.
    w = pd.Series({"A": 0.3, "B": 0.7})
    w_perm = w[["B", "A"]]
    assert portfolio_stats(w, mu, sigma).variance == pytest.approx(portfolio_stats(w_perm, mu, sigma).variance, abs=1e-15)


# --- P2-10: frecuencia y tasa libre de riesgo compatibles -------------------

def test_rf_conversion_compounds_back_p2_10():
    rf_ea = 0.03
    for m in (252, 52, 12):
        assert (1 + rf_per_period(rf_ea, m)) ** m - 1 == pytest.approx(rf_ea, abs=1e-12)
    assert rf_per_period(rf_ea, 12) < rf_ea / 12  # no es simplemente rf/m


# --- P2-11: riesgo y contribuciones reconcilian; rama cero explícita --------

def test_risk_contributions_reconcile_and_zero_branch_p2_11(two_assets):
    _, sigma, _, _, _ = two_assets
    w = pd.Series({"A": 0.6, "B": 0.4})
    rc = risk_contributions(w, sigma)
    expected_vol = np.sqrt(0.36 * 0.01 + 0.16 * 0.04 + 2 * 0.6 * 0.4 * 0.004)
    assert rc.volatility == pytest.approx(expected_vol, abs=ATOL)
    assert rc.contributions.sum() == pytest.approx(rc.volatility, abs=ATOL)
    assert rc.percent.sum() == pytest.approx(1.0, abs=ATOL)
    # El promedio ponderado de volatilidades sobrestima el riesgo con rho < 1.
    assert weighted_average_volatility(w, sigma) > rc.volatility

    zero = risk_contributions(pd.Series({"A": 0.5, "B": 0.5}), pd.DataFrame(0.0, index=["A", "B"], columns=["A", "B"]))
    assert zero.zero_risk and zero.volatility == 0.0 and (zero.contributions == 0).all()


# --- P2-13: GMV de dos activos coincide con el control analítico ------------

def test_gmv_two_assets_matches_analytic_p2_13(two_assets):
    mu, sigma, bounds, _, _ = two_assets
    s_a, s_b, s_ab = 0.01, 0.04, 0.004
    w_a = (s_b - s_ab) / (s_a + s_b - 2 * s_ab)  # = 0.036 / 0.042
    np.testing.assert_allclose(gmv_analytic(sigma), [w_a, 1 - w_a], atol=1e-12)
    gmv = min_variance(mu, sigma, bounds)
    assert gmv.ok and gmv.active_bounds == []  # cotas inactivas: el control aplica
    np.testing.assert_allclose(gmv.weights.to_numpy(), [w_a, 1 - w_a], atol=SOLVER_ATOL)
    assert gmv.budget_residual < 1e-9


# --- P2-14: frontera por optimización y casos degenerados -------------------

def test_frontier_branches_and_degenerate_case_p2_14(two_assets):
    mu, sigma, bounds, _, _ = two_assets
    frontier = efficient_frontier(mu, sigma, bounds, n_points=20)
    gmv = min_variance(mu, sigma, bounds)
    eff = frontier[frontier["rama"] == "eficiente"]
    ineff = frontier[frontier["rama"] == "no eficiente"]
    assert (frontier["estado"] == "óptimo").all()
    assert not ineff.empty  # con cotas [0,1] existe la rama inferior entre 8 % y la GMV
    assert (eff["volatilidad"].diff().dropna() >= -1e-9).all()  # riesgo crece en la rama eficiente
    assert (frontier["volatilidad"] >= gmv.volatility - 1e-9).all()
    assert eff["objetivo"].max() == pytest.approx(0.14, abs=1e-9)

    same_mu = pd.Series({"A": 0.1, "B": 0.1})
    degenerate = efficient_frontier(same_mu, sigma, bounds)
    assert len(degenerate) == 1 and (degenerate["rama"] == "eficiente").all()  # no se inventa rama


# --- P2-15: cotas, inviabilidad y no acotación visibles ---------------------

def test_bounds_respected_and_infeasible_or_unbounded_states_p2_15(two_assets):
    mu, sigma, _, _, _ = two_assets
    capped = [(0.0, 0.7), (0.0, 0.7)]
    res = min_variance(mu, sigma, capped)
    assert res.ok and (res.weights <= 0.7 + 1e-9).all() and res.weights.sum() == pytest.approx(1.0, abs=1e-9)
    assert any("cota superior" in a for a in res.active_bounds)  # la GMV libre (85,7 % en A) queda recortada

    assert min_variance(mu, sigma, [(0.0, 0.4), (0.0, 0.4)]).status == "inviable"
    unreachable = min_variance(mu, sigma, [(0, 1), (0, 1)], target_return=0.20)
    assert unreachable.status == "inviable" and "fuera del rango" in unreachable.message
    assert max_expected_return(mu, [(None, None), (None, None)]).status == "no acotado"


# --- P2-16: máximo esperado, tangencia y óptimo personal diferenciados ------

def test_max_tangency_and_personal_are_distinct_p2_16(two_assets):
    mu, sigma, bounds, rf, gamma = two_assets
    s = sigma.to_numpy()
    m = mu.to_numpy()

    best = max_expected_return(mu, bounds, sigma)
    np.testing.assert_allclose(best.weights.to_numpy(), [0.0, 1.0], atol=1e-9)

    # Tangente analítica (cotas inactivas): w ∝ Sigma^-1 (mu - rf 1)
    raw = np.linalg.solve(s, m - rf)
    w_t = raw / raw.sum()
    tangent = max_sharpe(mu, sigma, rf, bounds)
    assert tangent.ok
    np.testing.assert_allclose(tangent.weights.to_numpy(), w_t, atol=SOLVER_ATOL)

    # Óptimo personal analítico por KKT: [gamma*Sigma 1; 1' 0][w; l] = [mu; 1]
    kkt = np.block([[gamma * s, np.ones((2, 1))], [np.ones((1, 2)), np.zeros((1, 1))]])
    w_p = np.linalg.solve(kkt, np.append(m, 1.0))[:2]
    personal = personal_optimum(mu, sigma, gamma, bounds)
    np.testing.assert_allclose(personal.weights.to_numpy(), w_p, atol=SOLVER_ATOL)

    gmv = min_variance(mu, sigma, bounds)
    distinct = [gmv.weights["A"], tangent.weights["A"], personal.weights["A"], best.weights["A"]]
    assert len({round(x, 4) for x in distinct}) == 4


# --- P2-17: gamma, deuda y premios no positivos ------------------------------

def test_gamma_debt_and_non_positive_premium_p2_17(two_assets):
    mu, sigma, bounds, rf, gamma = two_assets
    assert max_sharpe(mu, sigma, 0.20, bounds).status == "premio no positivo"
    assert personal_optimum(mu, sigma, 0, bounds).status == "inviable"

    tangent = max_sharpe(mu, sigma, rf, bounds)
    y_free = optimal_risky_share(rf, tangent.mean, tangent.volatility, gamma=1.0)
    assert y_free > 1  # con baja aversión el óptimo libre pide endeudarse
    assert optimal_risky_share_no_debt(rf, tangent.mean, tangent.volatility, gamma=1.0) == 1.0
    assert optimal_risky_share_no_debt(0.5, tangent.mean, tangent.volatility, gamma=gamma) == 0.0


# --- P2-12 (parcial) y panel de riesgo: ventanas completas -------------------

def test_rolling_risk_uses_complete_windows(synthetic_prices):
    from src.portfolio import drawdown_from_returns, portfolio_return_series, rolling_correlation, rolling_volatility

    returns = simple_returns_matrix(synthetic_prices[["SIM1", "SIM2"]]).returns
    vol = rolling_volatility(returns, window=20)
    assert vol.iloc[:19].isna().all().all() and vol.iloc[19:].notna().all().all()  # sin ventanas incompletas
    assert vol["SIM1"].iloc[19] == pytest.approx(returns["SIM1"].iloc[:20].std(ddof=1), abs=1e-15)

    weights = pd.Series({"SIM1": 0.25, "SIM2": 0.75})
    rp = portfolio_return_series(returns, weights)
    assert rp.iloc[0] == pytest.approx(0.25 * returns["SIM1"].iloc[0] + 0.75 * returns["SIM2"].iloc[0], abs=1e-15)
    assert rolling_correlation(returns["SIM1"], returns["SIM1"], 20).dropna().round(12).eq(1).all()

    dd = drawdown_from_returns(pd.Series([0.10, -0.50, 0.20]))
    np.testing.assert_allclose(dd, [0.0, -0.5, -0.4], atol=1e-12)
    with pytest.raises(ValueError):
        portfolio_return_series(returns, pd.Series({"SIM1": 1.0}))


# --- P2-15 (ampliado): topes por grupo/sector ---------------------------------

def test_group_caps_are_respected_and_can_be_infeasible():
    mu = pd.Series({"X1": 0.12, "X2": 0.10, "Y1": 0.05})
    sigma = pd.DataFrame(np.diag([0.04, 0.03, 0.01]), index=mu.index, columns=mu.index)
    bounds = [(0.0, 1.0)] * 3
    groups = [(["X1", "X2"], 0.6)]  # el "sector X" no puede pesar más de 60 %
    for res in (max_expected_return(mu, bounds, sigma, groups=groups), min_variance(mu, sigma, bounds, groups=groups),
                max_sharpe(mu, sigma, 0.01, bounds, groups=groups), personal_optimum(mu, sigma, 2.0, bounds, groups=groups)):
        assert res.ok, res.message
        assert res.weights[["X1", "X2"]].sum() <= 0.6 + 1e-7
        assert res.weights.sum() == pytest.approx(1.0, abs=1e-8)
    assert max_expected_return(mu, bounds, sigma, groups=groups).weights["X1"] == pytest.approx(0.6, abs=1e-9)
    frontier = efficient_frontier(mu, sigma, bounds, n_points=8, groups=groups)
    assert (frontier["estado"] == "óptimo").all()
    # Tope del grupo + cotas imposibles: Y1 <= 0.2 y X <= 0.6 no suman 1.
    assert max_expected_return(mu, [(0, 1), (0, 1), (0, 0.2)], sigma, groups=groups).status == "inviable"
