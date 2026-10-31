"""
Fase 2 (v2) - Black-Litterman (guía V2, sección 6).

Pruebas de aceptación: P2-19, P2-20, P2-21, P2-22, P2-23, con el control
sintético del paquete (paquete_v2/data/black_litterman_control.json). La
posterior se contrasta con la fórmula escrita aparte con inversas
explícitas (solo como control en este caso pequeño y bien condicionado).
Sin red.
"""
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.black_litterman import (  # noqa: E402
    View,
    absolute_total_to_excess,
    build_view_set,
    implied_prior,
    posterior,
)

ATOL = 1e-8
RTOL = 1e-8


@pytest.fixture(scope="module")
def control():
    data = json.loads((ROOT / "paquete_v2" / "data" / "black_litterman_control.json").read_text())
    assets = data["assets"]
    sigma = pd.DataFrame(data["Sigma"], index=assets, columns=assets)
    w_ref = pd.Series(data["w_ref"], index=assets)
    return data, assets, sigma, w_ref


def _control_views(data, assets):
    P, Q, Omega = data["P"], data["Q"], data["Omega"]
    return [
        View("V1-abs", dict(zip(assets, P[0])), Q[0], omega=Omega[0][0]),
        View("V2-rel", dict(zip(assets, P[1])), Q[1], omega=Omega[1][1]),
    ]


def test_prior_and_posterior_match_explicit_formula(control):
    data, assets, sigma, w_ref = control
    pi = implied_prior(sigma, w_ref, data["delta"])
    np.testing.assert_allclose(pi, [3 * 0.0076, 3 * 0.0184], atol=1e-15)  # delta Sigma w_ref a mano

    vs = build_view_set(_control_views(data, assets), assets, sigma, data["tau"])
    res = posterior(sigma, pi, data["tau"], vs)

    S, P, Q, Om, tau = np.array(data["Sigma"]), np.array(data["P"]), np.array(data["Q"]), np.array(data["Omega"]), data["tau"]
    B = tau * S
    inv = np.linalg.inv
    mu_expected = inv(inv(B) + P.T @ inv(Om) @ P) @ (inv(B) @ pi.to_numpy() + P.T @ inv(Om) @ Q)  # forma alternativa
    M_expected = inv(inv(B) + P.T @ inv(Om) @ P)
    np.testing.assert_allclose(res.posterior, mu_expected, atol=ATOL, rtol=RTOL)
    np.testing.assert_allclose(res.M, M_expected, atol=ATOL, rtol=RTOL)
    assert res.n_views == 2 and list(res.posterior.index) == assets


def test_no_views_keeps_prior_p2_19(control):
    data, assets, sigma, w_ref = control
    pi = implied_prior(sigma, w_ref, data["delta"])
    res = posterior(sigma, pi, data["tau"], build_view_set([], assets, sigma, data["tau"]))
    np.testing.assert_allclose(res.posterior, pi, atol=1e-15)
    np.testing.assert_allclose(res.M, data["tau"] * sigma, atol=1e-15)  # M = B


def test_views_equal_to_prior_do_not_move_mean_p2_20(control):
    data, assets, sigma, w_ref = control
    pi = implied_prior(sigma, w_ref, data["delta"])
    P = np.array(data["P"])
    q_at_prior = P @ pi.to_numpy()
    views = [View(f"V{i}", dict(zip(assets, P[i])), float(q_at_prior[i]), omega=0.001) for i in range(2)]
    res = posterior(sigma, pi, data["tau"], build_view_set(views, assets, sigma, data["tau"]))
    np.testing.assert_allclose(res.posterior, pi, atol=1e-14)
    # Orden de activos: si el universo se entrega al revés, el resultado se reindexa igual.
    rev = assets[::-1]
    res_rev = posterior(sigma.loc[rev, rev], pi[rev], data["tau"], build_view_set(views, rev, sigma, data["tau"]))
    np.testing.assert_allclose(res_rev.posterior[assets], res.posterior, atol=1e-14)


def test_confidence_and_omega_coherent_p2_21(control):
    data, assets, sigma, w_ref = control
    pi = implied_prior(sigma, w_ref, data["delta"])
    tau = data["tau"]
    view = lambda conf: View("V", {"A": 1.0}, 0.03, confidence=conf)  # noqa: E731

    zero = build_view_set([view(0.0)], assets, sigma, tau)
    assert zero.used == [] and "Confianza 0" in zero.excluded["V"]  # cero confianza NO es certeza

    almost_none = posterior(sigma, pi, tau, build_view_set([view(1e-9)], assets, sigma, tau))
    np.testing.assert_allclose(almost_none.posterior, pi, atol=1e-9)  # incertidumbre alta -> prior

    exact = posterior(sigma, pi, tau, build_view_set([view(1.0)], assets, sigma, tau))
    assert exact.posterior["A"] == pytest.approx(0.03, abs=1e-12)  # 100 % = restricción exacta sin invertir Omega

    # Si Omega escala con tau, la media posterior no depende de tau; M sí.
    p = np.array([1.0, 0.0])
    def scaled(t):
        om = t * float(p @ sigma.to_numpy() @ p)
        return posterior(sigma, pi, t, build_view_set([View("V", {"A": 1.0}, 0.03, omega=om)], assets, sigma, t))
    small, large = scaled(0.01), scaled(0.5)
    np.testing.assert_allclose(small.posterior, large.posterior, atol=1e-14)
    assert not np.allclose(small.M, large.M)


def test_absolute_relative_expiry_duplicate_conflict_p2_22(control):
    data, assets, sigma, _ = control
    tau, rf = data["tau"], data["rf"]
    assert absolute_total_to_excess(0.06, rf) == pytest.approx(0.03, abs=1e-15)  # "A: 6 % total = 3 % exceso"
    assert absolute_total_to_excess(-0.01, rf, p_row_sum=0.0) == -0.01  # relativa: P·1 = 0

    views = [
        View("V1", {"A": 1.0}, 0.03, omega=0.0002),
        View("V1", {"A": 1.0}, 0.05, omega=0.0002),  # mismo ID
        View("V2", {"A": 1.0, "B": -1.0}, -0.01, omega=0.001, expires_at=date(2026, 1, 1)),  # vencida
        View("V3", {"A": 1.0}, 0.03, omega=0.0002),  # repite V1
        View("V4", {"A": 1.0}, 0.04, omega=0.0002),  # contradice V1
        View("V5", {"Z": 1.0}, 0.02, omega=0.001),  # activo fuera del universo
    ]
    vs = build_view_set(views, assets, sigma, tau, as_of=date(2026, 10, 31))
    assert vs.used == ["V1", "V4"]
    assert set(vs.excluded) == {"V1 (duplicado)", "V2", "V3", "V5"}
    assert "Vencida" in vs.excluded["V2"] and "Repite" in vs.excluded["V3"]
    assert any("Conflicto" in w for w in vs.warnings)
    assert vs.P.shape == (2, 2) and list(vs.P.columns) == assets


def test_mean_uncertainty_separated_from_predictive_risk_p2_23(control):
    data, assets, sigma, w_ref = control
    pi = implied_prior(sigma, w_ref, data["delta"])
    res = posterior(sigma, pi, data["tau"], build_view_set(_control_views(data, assets), assets, sigma, data["tau"]))
    np.testing.assert_allclose(res.sigma_predictive, sigma + res.M, atol=1e-15)
    assert np.linalg.eigvalsh(res.M.to_numpy()).min() > -1e-15  # M es PSD
    # Las views reducen la incertidumbre de la media: B - M es PSD.
    assert np.linalg.eigvalsh(data["tau"] * sigma.to_numpy() - res.M.to_numpy()).min() > -1e-15
    with pytest.raises(ValueError):
        implied_prior(sigma, w_ref, delta=-1.0)  # delta negativa no se invierte de signo en silencio


def test_view_not_yet_known_is_excluded(control):
    data, assets, sigma, _ = control
    future = View("VF", {"A": 1.0}, 0.03, omega=0.0002, known_at=date(2026, 12, 1))
    vs = build_view_set([future], assets, sigma, data["tau"], as_of=date(2026, 10, 31))
    assert vs.used == [] and "Aún no conocida" in vs.excluded["VF"]
    assert build_view_set([future], assets, sigma, data["tau"], as_of=date(2026, 12, 1)).used == ["VF"]
