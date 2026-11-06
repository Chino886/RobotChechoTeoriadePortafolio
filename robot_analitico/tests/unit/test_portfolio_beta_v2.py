"""
Beta de cartera (P102, P104), Hamada sobre un activo y validación cruzada con el
repositorio de Checho (Chech-d/robot-analitico-tbs-eia). Sin red.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.black_litterman import View, build_view_set, implied_prior, posterior  # noqa: E402
from src.capm import (  # noqa: E402
    beta_ols,
    cost_of_equity,
    nominal_rate_to_other_currency,
    portfolio_beta,
    relever_beta,
    unlever_beta,
)
from src.rebalance import Book, plan_rebalance  # noqa: E402

DATA = ROOT / "paquete_v2" / "data"


def test_portfolio_beta_is_weighted_sum_and_equals_regression_of_portfolio():
    rng = np.random.default_rng(7)
    m = pd.Series(rng.normal(0.0005, 0.01, 300))
    assets = pd.DataFrame({"X": 0.8 * m + rng.normal(0, 0.005, 300), "Y": 1.4 * m + rng.normal(0, 0.007, 300),
                           "Z": -0.2 * m + rng.normal(0, 0.004, 300)})
    betas = pd.Series({a: beta_ols(assets[a], m).beta for a in assets})
    w = pd.Series({"X": 0.5, "Y": 0.3, "Z": 0.2})
    # Con la misma muestra y el mismo benchmark, Σ w β coincide con la beta de la cartera.
    assert portfolio_beta(w, betas) == pytest.approx(beta_ols(assets @ w, m).beta, abs=1e-12)
    assert portfolio_beta(w, betas) == pytest.approx(float((w * betas).sum()), abs=1e-15)


def test_portfolio_beta_errors_when_an_asset_beta_is_missing():
    with pytest.raises(ValueError, match="Falta la beta de: Y"):
        portfolio_beta(pd.Series({"X": 0.6, "Y": 0.4}), pd.Series({"X": 1.1}))
    with pytest.raises(ValueError, match="Falta la beta de: Y"):
        portfolio_beta(pd.Series({"X": 0.6, "Y": 0.4}), pd.Series({"X": 1.1, "Y": np.nan}))
    # Un activo con peso cero no necesita beta.
    assert portfolio_beta(pd.Series({"X": 1.0, "Y": 0.0}), pd.Series({"X": 1.1})) == pytest.approx(1.1)


def test_hamada_with_empty_team_inputs_leaves_beta_unchanged_and_round_trips():
    assert unlever_beta(1.3, 0.0, 0.0, 0.0) == pytest.approx(1.3)
    assert relever_beta(1.3, 0.0, 0.0, 0.0) == pytest.approx(1.3)
    bu = unlever_beta(1.3, 0.8, 0.3, 0.1)
    assert relever_beta(bu, 0.8, 0.3, 0.1) == pytest.approx(1.3, abs=1e-12)


def test_cross_validation_with_checho_repository():
    """Los mismos controles del paquete dan lo mismo aquí y en Chech-d/robot-analitico-tbs-eia (2026-10-20)."""
    p = json.loads((DATA / "caso_alimentos_parametros.json").read_text())
    r = pd.read_csv(DATA / "caso_alimentos_retornos.csv").set_index("anio")
    b = beta_ols(r["comparable"], r["referencia"], rf=p["rf_USD"]).beta
    assert b == pytest.approx(1.5142857142857142, abs=1e-8)
    bl = relever_beta(unlever_beta(b, p["de_comparable"], p["tax_supuesto"], p["beta_deuda_supuesto"]),
                      p["de_empresa"], p["tax_supuesto"], p["beta_deuda_supuesto"])
    assert bl == pytest.approx(1.6205035971223012, abs=1e-8)
    ke = cost_of_equity(p["rf_USD"], bl, p["erp_madura"], p["proxy_pais"], p["lambda"]).ke
    assert ke == pytest.approx(0.16412769784172657, abs=1e-8)
    assert nominal_rate_to_other_currency(ke, p["inflacion_COL"], p["inflacion_USA"]) == pytest.approx(0.18684238462888225, abs=1e-8)

    d = json.loads((DATA / "black_litterman_control.json").read_text())
    a = d["assets"]
    S = pd.DataFrame(d["Sigma"], index=a, columns=a)
    pi = implied_prior(S, pd.Series(d["w_ref"], index=a), d["delta"])
    vs = build_view_set([View("V1", dict(zip(a, d["P"][0])), d["Q"][0], omega=d["Omega"][0][0]),
                         View("V2", dict(zip(a, d["P"][1])), d["Q"][1], omega=d["Omega"][1][1])], a, S, d["tau"])
    np.testing.assert_allclose(posterior(S, pi, d["tau"], vs).posterior.to_numpy(), [0.0285, 0.0450], atol=1e-6)

    c = json.loads((DATA / "rebalanceo_control.json").read_text())
    ca = c["assets"]
    book = Book(quantities=pd.Series(c["cantidades"], index=ca, dtype=float), cash=c["caja"])
    plan = plan_rebalance(book, pd.Series(c["precios_nuevos"], index=ca, dtype=float),
                          pd.Series(c["pesos_objetivo"], index=ca, dtype=float), c["costo_por_nominal"])
    assert plan.equity_before == pytest.approx(10400.0) and plan.costs == pytest.approx(2.8)
    assert plan.equity_after == pytest.approx(10397.2)
    np.testing.assert_allclose(plan.trades_value, [-1401.4, 1398.6], atol=1e-4)
