"""
Fase 2 (v2) - Precisión del optimizador con escalas diarias (varianza ~7e-5).

Con los 20 activos sintéticos del paquete:
- sin cotas, la GMV debe coincidir con la solución analítica Sigma^-1 1 / 1'Sigma^-1 1 (atol 1e-8);
- con cotas 0-25 %, la varianza no puede superar la de una referencia exacta
  (método de conjunto activo implementado aquí, independiente del solver)
  en más de 1e-12 relativo.
Sin red.
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
    gmv_analytic,
    min_variance,
    personal_optimum,
    simple_returns_matrix,
)


@pytest.fixture(scope="module")
def daily():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    r = simple_returns_matrix(prices).returns
    return r.mean(), covariance_matrix(r)


def _reference_box_qp(sigma: np.ndarray, lo: float, hi: float, linear=None, quad_scale=2.0) -> np.ndarray:
    """
    Referencia exacta: min (quad_scale/2) x'Sx + linear'x s.a. sum x = 1, lo <= x <= hi,
    por conjunto activo primal (Nocedal & Wright, alg. 16.3).
    """
    n = len(sigma)
    H = quad_scale * sigma
    c = np.zeros(n) if linear is None else linear
    x = np.full(n, 1.0 / n)
    fixed = {}  # índice -> valor de la cota activa
    for _ in range(500):
        free = [i for i in range(n) if i not in fixed]
        f_idx = list(fixed)
        f_val = np.array([fixed[i] for i in f_idx])
        k = len(free)
        kkt = np.zeros((k + 1, k + 1))
        kkt[:k, :k] = H[np.ix_(free, free)]
        kkt[:k, k] = -1.0
        kkt[k, :k] = 1.0
        rhs = np.zeros(k + 1)
        rhs[:k] = -c[free] - (H[np.ix_(free, f_idx)] @ f_val if f_idx else 0)
        rhs[k] = 1.0 - f_val.sum()
        sol = np.linalg.solve(kkt, rhs)
        cand = x.copy()
        cand[free] = sol[:k]
        lam = sol[k]
        step = cand - x
        alpha, block = 1.0, None
        for i in free:
            if step[i] < -1e-15 and cand[i] < lo:
                a = (lo - x[i]) / step[i]
                if a < alpha:
                    alpha, block = a, (i, lo)
            if step[i] > 1e-15 and cand[i] > hi:
                a = (hi - x[i]) / step[i]
                if a < alpha:
                    alpha, block = a, (i, hi)
        x = x + alpha * step
        if block is not None:
            fixed[block[0]] = block[1]
            x[block[0]] = block[1]
            continue
        g = H @ x + c
        worst, worst_i = 0.0, None
        for i, v in fixed.items():
            mult = g[i] - lam if v == lo else lam - g[i]
            if mult < worst:
                worst, worst_i = mult, i
        if worst_i is None:
            return x
        del fixed[worst_i]
    raise RuntimeError("La referencia no convergió.")


def test_gmv_unbounded_matches_analytic(daily):
    mu, sigma = daily
    res = min_variance(mu, sigma, [(None, None)] * len(mu))
    assert res.ok
    np.testing.assert_allclose(res.weights.to_numpy(), gmv_analytic(sigma), atol=1e-8)


def test_gmv_capped_reaches_exact_reference(daily):
    mu, sigma = daily
    ref = _reference_box_qp(sigma.to_numpy(), 0.0, 0.25)
    var_ref = float(ref @ sigma.to_numpy() @ ref)
    res = min_variance(mu, sigma, [(0.0, 0.25)] * len(mu))
    assert res.ok
    w = res.weights.to_numpy()
    assert w.min() >= -1e-12 and w.max() <= 0.25 + 1e-12 and abs(w.sum() - 1) < 1e-12
    assert float(w @ sigma.to_numpy() @ w) <= var_ref * (1 + 1e-12)
    np.testing.assert_allclose(w, ref, atol=1e-8)


def test_personal_optimum_capped_reaches_exact_reference(daily):
    mu, sigma = daily
    gamma = 5.0
    ref = _reference_box_qp(sigma.to_numpy(), 0.0, 0.25, linear=-mu.to_numpy(), quad_scale=gamma)
    res = personal_optimum(mu, sigma, gamma, [(0.0, 0.25)] * len(mu))
    assert res.ok
    np.testing.assert_allclose(res.weights.to_numpy(), ref, atol=1e-8)


def test_frontier_points_are_exact_minimum_variance(daily):
    mu, sigma = daily
    s = sigma.to_numpy()
    m = mu.to_numpy()
    frontier = efficient_frontier(mu, sigma, [(None, None)] * len(mu), n_points=6, max_target=float(m.max()))
    inv = np.linalg.inv(s)
    one = np.ones(len(m))
    A, B, C = one @ inv @ one, one @ inv @ m, m @ inv @ m
    D = A * C - B ** 2
    for _, row in frontier.iterrows():
        exact = np.sqrt((A * row["objetivo"] ** 2 - 2 * B * row["objetivo"] + C) / D)
        assert row["volatilidad"] == pytest.approx(exact, rel=1e-9)


@pytest.mark.parametrize("lo,hi", [(0.0, 1.0), (0.0, 0.25), (-0.5, 1.0)])
def test_many_windows_match_exact_reference(lo, hi):
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    r = simple_returns_matrix(prices).returns
    for end in range(150, 599, 75):  # varias ventanas de 120 días, incluidas soluciones de esquina
        win = r.iloc[end - 120:end]
        mu, sigma = win.mean(), covariance_matrix(win)
        s = sigma.to_numpy()
        for gamma in (1.0, 5.0):
            res = personal_optimum(mu, sigma, gamma, [(lo, hi)] * len(mu))
            assert res.ok, res.message
            ref = _reference_box_qp(s, lo, hi, linear=-mu.to_numpy(), quad_scale=gamma)
            np.testing.assert_allclose(res.weights.to_numpy(), ref, atol=1e-9)
        gmv = min_variance(mu, sigma, [(lo, hi)] * len(mu))
        assert gmv.ok
        np.testing.assert_allclose(gmv.weights.to_numpy(), _reference_box_qp(s, lo, hi), atol=1e-9)
