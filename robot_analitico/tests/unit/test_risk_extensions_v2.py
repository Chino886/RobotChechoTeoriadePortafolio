"""
Fase 2 (v2) - Estimadores alternativos, estrés, concentración, calidad del
dato, moneda y relojes (guía V2, secciones 3, 4 y 10).

Pruebas de aceptación: P2-5 (huecos y calendario), P2-12 (barras completas,
sin duplicar eventos) y P2-24 (relojes de cotización, estimación y decisión
distintos), más controles de Ledoit-Wolf, EWMA, escenarios y FX. Sin red.
"""
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.data_quality import (  # noqa: E402
    calendar_report,
    cop_returns,
    drop_incomplete_last_bar,
    gap_safe_simple_returns,
    prices_in_cop,
)
from src.estimators import ewma_covariance, ewma_weights, ledoit_wolf  # noqa: E402
from src.market import Quote  # noqa: E402
from src.portfolio import covariance_matrix, portfolio_stats, simple_returns_matrix  # noqa: E402
from src.rebalance import Book, MarketEvent, RebalancePolicy, Rebalancer  # noqa: E402
from src.stress import (  # noqa: E402
    concentration,
    correlation_breakdown,
    historical_var,
    individual_shocks,
    joint_worst_historical,
    parametric_var,
    portfolio_loss,
    reverse_stress,
)


@pytest.fixture(scope="module")
def returns():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    return simple_returns_matrix(prices.iloc[:, :5]).returns


# --- Estimadores alternativos ------------------------------------------------

def test_ledoit_wolf_properties(returns):
    lw = ledoit_wolf(returns)
    assert 0 <= lw.intensity <= 1
    eig_lw = np.linalg.eigvalsh(lw.sigma.to_numpy())
    eig_s = np.linalg.eigvalsh(covariance_matrix(returns).to_numpy())
    assert eig_lw.min() > 0 and eig_lw.max() / eig_lw.min() <= eig_s.max() / eig_s.min() + 1e-12  # mejor condicionada
    assert np.trace(lw.sigma.to_numpy()) == pytest.approx(np.trace(returns.cov(ddof=0).to_numpy()), rel=1e-12)
    # Pocas observaciones para muchos activos -> se encoge más.
    assert ledoit_wolf(returns.iloc[:8]).intensity > lw.intensity


def test_ledoit_wolf_matches_reference_implementation(returns):
    sklearn = pytest.importorskip("sklearn.covariance")
    ref = sklearn.LedoitWolf(assume_centered=False).fit(returns.to_numpy())
    lw = ledoit_wolf(returns)
    assert lw.intensity == pytest.approx(ref.shrinkage_, abs=1e-10)
    np.testing.assert_allclose(lw.sigma.to_numpy(), ref.covariance_, atol=1e-14)


def test_ewma_weights_and_limits(returns):
    w = ewma_weights(100, 0.94)
    assert w.sum() == pytest.approx(1.0) and w[-1] > w[0]  # lo reciente pesa más
    cov = ewma_covariance(returns, 0.94)
    assert np.allclose(cov, cov.T) and np.linalg.eigvalsh(cov.to_numpy()).min() > 0
    near_one = ewma_covariance(returns, 0.999999)  # lambda -> 1: pesos iguales (MLE)
    np.testing.assert_allclose(near_one, returns.cov(ddof=0), rtol=1e-3)
    with pytest.raises(ValueError):
        ewma_covariance(returns, 1.0)


# --- Estrés y concentración ---------------------------------------------------

def test_stress_scenarios_and_reverse_stress(returns):
    w = pd.Series(0.2, index=returns.columns)
    sigma = covariance_matrix(returns)
    assert individual_shocks(w, -0.30).max() == pytest.approx(0.06)
    loss, worst = joint_worst_historical(w, returns)
    assert loss == pytest.approx(-(w * returns.min()).sum()) and loss > 0

    broken = correlation_breakdown(sigma, 1.0)
    vol_broken = portfolio_stats(w, returns.mean(), broken).volatility
    assert vol_broken == pytest.approx(float(w @ np.sqrt(np.diag(sigma))), rel=1e-12)  # sin diversificación
    assert vol_broken > portfolio_stats(w, returns.mean(), sigma).volatility
    with pytest.raises(ValueError):
        correlation_breakdown(sigma, -0.9)  # con 5 activos no puede ser PSD

    rs = reverse_stress(w, sigma, loss_limit=0.10)
    assert rs.loss == pytest.approx(0.10, abs=1e-12)
    assert portfolio_loss(w, rs.shocks) == pytest.approx(0.10, abs=1e-12)
    vol = portfolio_stats(w, returns.mean(), sigma).volatility
    assert rs.mahalanobis == pytest.approx(0.10 / vol)
    s_inv = np.linalg.inv(sigma.to_numpy())
    alt = rs.shocks.to_numpy() * 0 - 0.10 / w.sum()  # shock uniforme con la misma pérdida
    assert rs.shocks.to_numpy() @ s_inv @ rs.shocks.to_numpy() <= alt @ s_inv @ alt + 1e-12  # el inverso es el más probable


def test_var_and_concentration(returns):
    assert parametric_var(0.0, 0.01, 0.95) == pytest.approx(1.6448536269514722 * 0.01)
    assert parametric_var(0.05, 0.01, 0.95) == 0.0  # piso en cero
    rp = returns.mean(axis=1)
    assert historical_var(rp, 0.95) == pytest.approx(-np.quantile(rp, 0.05))
    c = concentration(pd.Series({"A": 0.5, "B": 0.25, "C": 0.25}))
    assert c.hhi == pytest.approx(0.375) and c.effective_n == pytest.approx(1 / 0.375) and c.max_asset == "A"


# --- P2-5: huecos, calendario y ajustes no producen retornos falsos -----------

def test_gaps_are_detected_and_not_bridged_p2_5():
    idx = pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-20", "2026-01-21"])
    prices = pd.DataFrame({"A": [100.0, 101.0, 102.0, 110.0, 111.0], "B": [50.0, 50.0, 50.0, 50.0, 50.0]}, index=idx)
    rep = calendar_report(prices, "Diaria")
    assert ((rep["problema"] == "hueco") & (rep["activo"] == "A")).any()
    r, removed = gap_safe_simple_returns(prices, "Diaria")
    assert removed == 2  # el salto 7 -> 20 de enero, en A y en B
    assert np.isnan(r.loc["2026-01-20", "A"])  # no se llama "diario" a 13 días
    assert r.loc["2026-01-21", "A"] == pytest.approx(111 / 110 - 1)
    assert (calendar_report(prices, "Semanal")["problema"] == "hueco").any()  # 13 días > 10 también es hueco semanal
    monthly = calendar_report(prices, "Mensual")
    assert not (monthly["problema"] == "hueco").any()  # pero no para datos mensuales (límite 35 días)

    stale = pd.DataFrame({"S": [10.0] * 7 + [11.0]}, index=pd.bdate_range("2026-02-02", periods=8))
    assert (calendar_report(stale)["problema"] == "precio estancado").any()
    dup = pd.DataFrame({"A": [1.0, 2.0]}, index=pd.to_datetime(["2026-03-02", "2026-03-02"]))
    assert (calendar_report(dup)["problema"] == "fecha duplicada").any()


# --- P2-12 / P2-24: barras completas y tres relojes ---------------------------

def test_complete_bars_and_three_clocks_p2_12_p2_24():
    tz = "America/New_York"
    idx = pd.bdate_range("2026-10-12", "2026-10-30").tz_localize(tz)
    rng = np.random.default_rng(3)
    prices = pd.DataFrame({"A": 100 * np.cumprod(1 + rng.normal(0, 0.01, len(idx))),
                           "B": 50 * np.cumprod(1 + rng.normal(0, 0.01, len(idx)))}, index=idx)
    during = datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc)  # 11:00 en Nueva York: sesión abierta
    after = datetime(2026, 10, 30, 21, 0, tzinfo=timezone.utc)  # 17:00: ya cerró
    complete = drop_incomplete_last_bar(prices, during, time(16, 0), tz)
    assert len(complete) == len(prices) - 1  # la barra de hoy no cuenta como cierre diario
    assert len(drop_incomplete_last_bar(prices, after, time(16, 0), tz)) == len(prices)

    # Reloj de estimación: cambiar el precio "en vivo" de la barra incompleta no cambia mu/Sigma.
    sigma_before = covariance_matrix(simple_returns_matrix(complete).returns)
    moved = prices.copy()
    moved.iloc[-1] = moved.iloc[-1] * 1.05  # nueva cotización intradía
    sigma_after = covariance_matrix(simple_returns_matrix(drop_incomplete_last_bar(moved, during, time(16, 0), tz)).returns)
    pd.testing.assert_frame_equal(sigma_before, sigma_after)

    # Reloj de cotización: un dato repetido no es una observación nueva.
    q1 = Quote("A", True, price=102.5, last_bar_at=during, received_at=during)
    q2 = Quote("A", True, price=102.5, last_bar_at=during, received_at=during + timedelta(seconds=30))
    assert q2.same_data_as(q1)

    # Reloj de decisión: solo un evento válido y nuevo genera decisión.
    book = Book(quantities=pd.Series({"A": 10.0, "B": 10.0}))
    reb = Rebalancer(RebalancePolicy(cost_rate=0.0, weight_band=0.01), book, pd.Series({"A": 0.5, "B": 0.5}))
    p = complete.iloc[-1]
    assert reb.on_event(MarketEvent("cierre-2026-10-29", after, p)) is not None
    assert reb.on_event(MarketEvent("cierre-2026-10-29", after + timedelta(minutes=1), p)) is None  # duplicado
    assert [d.action for d in reb.log][-1] == "duplicado" and sum(d.action != "duplicado" for d in reb.log) == 1


# --- Moneda ----------------------------------------------------------------------

def test_cop_conversion_compounds_returns():
    idx = pd.to_datetime(["2026-01-05", "2026-01-06"])
    r = cop_returns(pd.Series([0.10, -0.02], index=idx), pd.Series([0.05, 0.01], index=idx))
    np.testing.assert_allclose(r, [1.1 * 1.05 - 1, 0.98 * 1.01 - 1])
    assert r.iloc[0] != pytest.approx(0.15)  # no es la suma
    p = prices_in_cop(pd.Series([10.0, 11.0], index=idx), pd.Series([4000.0, 4100.0], index=idx))
    np.testing.assert_allclose(p, [40000.0, 45100.0])
    np.testing.assert_allclose(p.pct_change().iloc[1], 1.1 * 1.025 - 1)
