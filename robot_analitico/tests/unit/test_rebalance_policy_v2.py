"""
Fase 2 (v2) - Rebalanceo con caja mínima, reestimación, eventos de views,
abstención costo-beneficio y duplicados registrados (guía V2, 7.1; P2-24,
P2-27, P2-28; banco P85, P86). Sin red.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.black_litterman import View  # noqa: E402
from src.portfolio import covariance_matrix, min_variance, simple_returns_matrix  # noqa: E402
from src.rebalance import (  # noqa: E402
    ACTION_ABSTAIN,
    ACTION_DUPLICATE,
    ACTION_REBALANCE,
    Book,
    MarketEvent,
    RebalancePolicy,
    Rebalancer,
    plan_rebalance,
    simulate_policy,
)


@pytest.fixture(scope="module")
def control():
    data = json.loads((ROOT / "paquete_v2" / "data" / "rebalanceo_control.json").read_text())
    a = data["assets"]
    return (data, Book(quantities=pd.Series(data["cantidades"], index=a, dtype=float), cash=data["caja"]),
            pd.Series(data["precios_nuevos"], index=a, dtype=float), pd.Series(data["pesos_objetivo"], index=a, dtype=float))


@pytest.fixture(scope="module")
def returns():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    return simple_returns_matrix(prices.iloc[:, :4]).returns


def test_cash_minimum_is_kept_apart_from_target_weights(control):
    data, book, p1, target = control
    plan = plan_rebalance(book, p1, target, data["costo_por_nominal"], cash_minimum=100.0)
    # Control a mano: nominal 2.800 (se vende A y se compra B), costos 2,8, V_post = 10.397,2,
    # invertible = V_post − 100 = 10.297,2 -> 5.148,6 por activo y la caja queda en 100.
    assert plan.costs == pytest.approx(2.8, abs=1e-9)
    assert plan.cash_after == pytest.approx(100.0, abs=1e-6)
    np.testing.assert_allclose(plan.new_book.values(p1), [5148.6, 5148.6], atol=1e-6)
    reb = Rebalancer(RebalancePolicy(cost_rate=data["costo_por_nominal"], weight_band=0.05, cash_minimum=100.0), book, target)
    decision = reb.on_event(MarketEvent("E1", datetime(2026, 10, 1), p1))
    assert decision.action == ACTION_REBALANCE  # antes: cualquier caja mínima > 0 suspendía siempre


def test_duplicate_event_is_logged_without_decision(control):
    data, book, p1, target = control
    reb = Rebalancer(RebalancePolicy(cost_rate=0.001, weight_band=0.05), book, target)
    event = MarketEvent("E1", datetime(2026, 10, 1), p1)
    assert reb.on_event(event).action == ACTION_REBALANCE
    assert reb.on_event(event) is None  # no hay segunda decisión...
    assert [d.action for d in reb.log] == [ACTION_REBALANCE, ACTION_DUPLICATE]  # ...pero queda registrado
    assert reb.log[1].reason == "duplicado, sin decisión"


def test_cost_benefit_abstention_p85(control):
    data, book, p1, target = control
    big_margin = Rebalancer(RebalancePolicy(cost_rate=0.001, weight_band=0.05, cost_benefit_margin=0.5), book, target,
                            utility=lambda w: 0.0)
    d = big_margin.on_event(MarketEvent("E1", datetime(2026, 10, 1), p1))
    assert d.action == ACTION_ABSTAIN and "no supera los costos" in d.reason
    no_rule = Rebalancer(RebalancePolicy(cost_rate=0.001, weight_band=0.05), book, target, utility=lambda w: 0.0)
    assert no_rule.on_event(MarketEvent("E1", datetime(2026, 10, 1), p1)).action == ACTION_REBALANCE


def test_reestimation_uses_only_known_window_and_records_it_p86(returns):
    policy = RebalancePolicy(cost_rate=0.001, calendar_days=30)
    run = simulate_policy(returns, policy, rule="GMV", window=60, horizon=120, gamma=5.0, bounds=[(0.0, 1.0)] * 4)
    trades = [d for d in run.log if d.action == ACTION_REBALANCE]
    assert trades, "debe haber al menos una decisión periódica"
    for d in trades:
        start, end = d.window
        assert end < pd.Timestamp(d.at)  # solo información anterior a la decisión
        win = returns.loc[start:end]
        assert len(win) == 60
        expected = min_variance(win.mean(), covariance_matrix(win), [(0.0, 1.0)] * 4).weights
        pd.testing.assert_series_equal(d.theoretical.sort_index(), expected.sort_index(), check_names=False, atol=1e-10)
        assert d.realized is not None and abs(d.realized.sum() - 1) < 1e-9
        assert d.reason


def test_view_expiry_is_an_information_trigger_p2_24(returns):
    idx = returns.index
    start = idx[-60]
    expiry = idx[-30]
    views = [View("V1", {returns.columns[0]: 1.0}, 0.0002, omega=1e-6, known_at=start.date(), expires_at=expiry.date())]
    policy = RebalancePolicy(cost_rate=0.0, weight_band=0.99)  # banda enorme: solo los eventos de información operan
    run = simulate_policy(returns, policy, rule="BL posterior", window=60, horizon=60, gamma=5.0, bounds=[(0.0, 1.0)] * 4,
                          views=views, bl_delta=3.0, bl_tau=0.05, rf_period=0.0)
    info = [d for d in run.log if d.event_id.startswith("view-")]
    assert any("vence" in d.event_id or "vencida" in d.event_id for d in info)
    assert all(d.action in (ACTION_REBALANCE, ACTION_ABSTAIN) for d in info)
    assert any(d.action == ACTION_REBALANCE for d in info)
