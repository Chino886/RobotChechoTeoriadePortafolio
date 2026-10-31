"""
Fase 2 (v2) - Cortos: frontera y tangente cuando las cotas permiten pesos
negativos o no hay cotas (guía V2, sección 5; P2-15, P2-17). Sin red.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.portfolio import (  # noqa: E402
    covariance_matrix,
    efficient_frontier,
    max_sharpe,
    random_portfolios,
    simple_returns_matrix,
)


@pytest.fixture(scope="module")
def daily():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    r = simple_returns_matrix(prices.iloc[:, :6]).returns
    return r.mean(), covariance_matrix(r)


def test_unbounded_tangent_is_analytic_or_reports_state(daily):
    mu, sigma = daily
    rf = 1e-4
    z = np.linalg.solve(sigma.to_numpy(), mu.to_numpy() - rf)
    res = max_sharpe(mu, sigma, rf, [(None, None)] * len(mu))
    assert res.ok
    np.testing.assert_allclose(res.weights.to_numpy(), z / z.sum(), atol=1e-12)
    high_rf = max_sharpe(mu, sigma, 0.05, [(None, None)] * len(mu))  # rf por encima de la GMV: denominador <= 0
    assert high_rf.status == "premio no positivo" and "1'Σ⁻¹" in high_rf.message


def test_frontier_with_shorts_needs_team_max_target(daily):
    mu, sigma = daily
    free = [(None, None)] * len(mu)
    assert efficient_frontier(mu, sigma, free).empty
    assert "decisión del equipo" in efficient_frontier(mu, sigma, free).attrs["estado"]
    target = float(mu.max())
    f = efficient_frontier(mu, sigma, free, n_points=8, max_target=target)
    assert not f.empty and f["objetivo"].max() == pytest.approx(target) and (f["estado"] == "óptimo").all()
    assert set(f["rama"]) == {"eficiente", "no eficiente"}
    # Cortos limitados (-50 %): la frontera numérica existe sin tope adicional.
    limited = efficient_frontier(mu, sigma, [(-0.5, 1.0)] * len(mu), n_points=8)
    assert not limited.empty and (limited["estado"] == "óptimo").all()
    # Cortos ilimitados con techo por activo: el máximo es no acotado y usa el tope del equipo.
    half_open = efficient_frontier(mu, sigma, [(None, 1.0)] * len(mu), n_points=6, max_target=target)
    assert not half_open.empty and half_open["objetivo"].max() == pytest.approx(target)


def test_random_cloud_respects_negative_bounds_or_is_labeled(daily):
    mu, sigma = daily
    finite = random_portfolios(mu, sigma, [(-0.5, 1.0)] * len(mu), n=200)
    assert not finite.empty and "dentro de las cotas" in finite.attrs["etiqueta"]
    open_ = random_portfolios(mu, sigma, [(None, None)] * len(mu), n=200)
    assert "SOLO LARGOS" in open_.attrs["etiqueta"]
