"""
Fase 2 (v2) - Rebalanceo simulado (guía V2, sección 7).

Pruebas de aceptación: P2-25, P2-26, P2-27, P2-28, con el control del
paquete (paquete_v2/data/rebalanceo_control.json): 60 y 40 unidades a 100,
precios nuevos 110 y 95, objetivo 50/50 sobre el patrimonio posterior a
costos, costo 0,1 % del nominal, fracciones permitidas, sin caja negativa.
Sin red.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.rebalance import (  # noqa: E402
    ACTION_ABSTAIN,
    ACTION_REBALANCE,
    ACTION_SUSPEND,
    Book,
    MarketEvent,
    RebalancePolicy,
    Rebalancer,
    drifted_weights,
    plan_rebalance,
    turnover,
)

ATOL = 1e-8


@pytest.fixture(scope="module")
def control():
    data = json.loads((ROOT / "paquete_v2" / "data" / "rebalanceo_control.json").read_text())
    assets = data["assets"]
    book = Book(quantities=pd.Series(data["cantidades"], index=assets, dtype=float), cash=data["caja"], currency=data["moneda"])
    return (
        data, book,
        pd.Series(data["precios_iniciales"], index=assets, dtype=float),
        pd.Series(data["precios_nuevos"], index=assets, dtype=float),
        pd.Series(data["pesos_objetivo"], index=assets, dtype=float),
    )


def test_weight_drift_matches_quantities_p2_25(control):
    _, book, p0, p1, _ = control
    w0 = book.weights(p0)
    np.testing.assert_allclose(w0, [0.6, 0.4], atol=1e-15)
    drifted = drifted_weights(w0, p1 / p0 - 1)
    np.testing.assert_allclose(drifted, book.weights(p1), atol=1e-15)  # misma deriva por fórmula y por cantidades
    np.testing.assert_allclose(drifted, [6600 / 10400, 3800 / 10400], atol=1e-15)


def test_turnover_costs_and_cash_reconcile_p2_26(control):
    data, book, _, p1, target = control
    plan = plan_rebalance(book, p1, target, data["costo_por_nominal"], fractional=data["fracciones"])
    # Control a mano: V_pre = 10.400; se vende A y se compra B por 2.800 de nominal total
    # -> costos 2,8 y V_post = 10.397,2; cada activo queda en 5.198,6.
    assert plan.equity_before == pytest.approx(10400.0, abs=ATOL)
    assert plan.traded_notional == pytest.approx(2800.0, abs=1e-6)
    assert plan.costs == pytest.approx(2.8, abs=1e-9)  # sobre el nominal real, no sobre la mitad
    assert plan.equity_after == pytest.approx(10400.0 - 2.8, abs=1e-6)
    np.testing.assert_allclose(plan.trades_value, [5198.6 - 6600, 5198.6 - 3800], atol=1e-6)
    assert plan.cash_after == pytest.approx(0.0, abs=1e-6) and plan.cash_after >= -1e-9
    np.testing.assert_allclose(plan.weights_after, [0.5, 0.5], atol=1e-9)
    w_before = pd.Series([6600 / 10400, 3800 / 10400], index=target.index)
    assert plan.turnover == pytest.approx(turnover(w_before, target), abs=1e-9)
    assert plan.turnover == pytest.approx(0.5 * 2 * abs(6600 / 10400 - 0.5), abs=1e-9)


def test_no_debt_and_no_shorts(control):
    data, book, _, p1, _ = control
    with pytest.raises(ValueError):
        plan_rebalance(book, p1, pd.Series({"A": 0.8, "B": 0.4}), data["costo_por_nominal"])
    with pytest.raises(ValueError):
        plan_rebalance(book, p1, pd.Series({"A": 1.2, "B": -0.2}), data["costo_por_nominal"])


def test_duplicate_event_gives_single_decision_p2_27(control):
    data, book, _, p1, target = control
    reb = Rebalancer(RebalancePolicy(cost_rate=data["costo_por_nominal"], weight_band=0.05), book, target)
    event = MarketEvent("E1", datetime(2026, 10, 1), p1)
    first = reb.on_event(event)
    second = reb.on_event(event)
    assert first.action == ACTION_REBALANCE and second is None
    assert len(reb.log) == 1


def test_abstentions_are_recorded_p2_28(control):
    data, book, _, p1, target = control
    t0 = datetime(2026, 10, 1, 15, 0)

    # Dentro de la banda: abstención registrada.
    calm = Rebalancer(RebalancePolicy(cost_rate=data["costo_por_nominal"], weight_band=0.20), book, target)
    d = calm.on_event(MarketEvent("E-banda", t0, p1))
    assert d.action == ACTION_ABSTAIN and "banda" in d.reason

    # Dato viejo: se suspende y se conserva la cartera.
    stale = Rebalancer(RebalancePolicy(cost_rate=0.001, weight_band=0.05, max_quote_age=timedelta(minutes=30)), book, target)
    d = stale.on_event(MarketEvent("E-viejo", t0, p1, quote_times={"A": t0 - timedelta(hours=2), "B": t0}), now=t0)
    assert d.action == ACTION_SUSPEND and stale.book is book

    # Costo/rotación por encima del tope: abstención.
    capped = Rebalancer(RebalancePolicy(cost_rate=0.001, weight_band=0.05, max_turnover=0.05), book, target)
    assert capped.on_event(MarketEvent("E-rot", t0, p1)).action == ACTION_ABSTAIN

    # Espera mínima tras operar: la segunda señal se abstiene.
    waiting = Rebalancer(RebalancePolicy(cost_rate=0.001, weight_band=0.0, min_days_between=7), book, target)
    assert waiting.on_event(MarketEvent("E1", t0, p1)).action == ACTION_REBALANCE
    d = waiting.on_event(MarketEvent("E2", t0 + timedelta(days=2), p1 * pd.Series({"A": 1.2, "B": 0.9})))
    assert d.action == ACTION_ABSTAIN and "Espera mínima" in d.reason

    # Regla periódica: opera aunque la deriva sea pequeña.
    periodic = Rebalancer(RebalancePolicy(cost_rate=0.001, calendar_days=30), book, target)
    assert periodic.on_event(MarketEvent("P1", t0, p1)).action == ACTION_REBALANCE
    assert periodic.on_event(MarketEvent("P2", t0 + timedelta(days=10), p1)).action == ACTION_ABSTAIN
    assert periodic.on_event(MarketEvent("P3", t0 + timedelta(days=31), p1)).action == ACTION_REBALANCE


def test_whole_shares_keep_leftover_cash(control):
    data, book, _, p1, target = control
    plan = plan_rebalance(book, p1, target, data["costo_por_nominal"], fractional=False)
    assert (plan.new_book.quantities == plan.new_book.quantities.round()).all()
    assert plan.cash_after >= 0
    assert plan.equity_after == pytest.approx(plan.equity_before - plan.costs, abs=1e-6)
