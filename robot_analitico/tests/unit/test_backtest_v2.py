"""
Fase 2 (v2) - Evaluación temporal walk-forward (guía V2, sección 7.2).

Pruebas de aceptación: P2-29 (sin look-ahead) y P2-30 (comparadores con el
mismo universo, periodo y costos), con las 20 series sintéticas del paquete.
Sin red.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.backtest import (  # noqa: E402
    ALL_STRATEGIES,
    STRAT_EQUAL,
    STRAT_GMV,
    STRAT_HOLD,
    BacktestConfig,
    _target_weights,
    performance,
    run_strategy,
    walk_forward,
)
from src.portfolio import simple_returns_matrix  # noqa: E402


@pytest.fixture(scope="module")
def returns():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    return simple_returns_matrix(prices.iloc[:, :5]).returns


def _cfg(**kw):
    base = dict(window=120, rebalance_every=21, cost_rate=0.001, rf_period=0.0001, gamma=5.0,
                bounds=[(0.0, 1.0)] * 5, periods_per_year=252)
    base.update(kw)
    return BacktestConfig(**base)


def test_no_look_ahead_p2_29(returns):
    cfg = _cfg()
    seen = []

    def spy(strategy, window, cfg_, previous, as_of=None):
        seen.append(window.index[-1])
        return _target_weights(strategy, window, cfg_, previous, as_of)

    run = run_strategy(STRAT_GMV, returns, cfg, target_fn=spy)
    for decision, last_used in zip(run.weights_history.index, seen):
        assert last_used < decision  # la ventana termina antes de la fecha en que se aplican los pesos

    # Cambiar el futuro no altera los pesos decididos antes.
    cut = run.weights_history.index[3]
    future = returns.copy()
    future.loc[cut:] = future.loc[cut:] * -3
    altered = run_strategy(STRAT_GMV, future, cfg)
    pd.testing.assert_frame_equal(run.weights_history.loc[:cut], altered.weights_history.loc[:cut])
    assert not run.weights_history.iloc[5:].equals(altered.weights_history.iloc[5:])


def test_comparators_share_universe_period_and_costs_p2_30(returns):
    cfg = _cfg()
    res = walk_forward(returns, cfg)
    idx = {name: tuple(run.wealth.index) for name, run in res.runs.items()}
    assert len(set(idx.values())) == 1  # mismo periodo evaluado
    from src.backtest import STRAT_BL, bl_label
    assert set(res.runs) == {bl_label(cfg) if s == STRAT_BL else s for s in ALL_STRATEGIES}
    for run in res.runs.values():
        assert list(run.weights_history.columns) == list(returns.columns)  # mismo universo y orden
    hold = res.runs[STRAT_HOLD]
    assert len(hold.weights_history) == 1 and hold.costs.sum() == 0  # mantener cantidades no opera después
    assert res.metrics.index.get_level_values("tramo").unique().tolist() == ["validación", "prueba final"]
    assert res.validation_start < res.test_start


def test_costs_reduce_net_return_and_hold_has_no_turnover(returns):
    free = run_strategy(STRAT_EQUAL, returns, _cfg(cost_rate=0.0))
    costly = run_strategy(STRAT_EQUAL, returns, _cfg(cost_rate=0.01))
    assert costly.wealth.iloc[-1] < free.wealth.iloc[-1]
    assert costly.costs.sum() == pytest.approx(0.01 * 2 * costly.turnover.sum(), rel=1e-12)  # costo sobre nominal = 2 x rotación
    # 1/N rebalanceado sin costos: el rendimiento del primer periodo es el promedio simple.
    first = returns.iloc[120]
    assert free.returns.iloc[0] == pytest.approx(first.mean(), abs=1e-15)


def test_performance_metrics_by_hand():
    r = pd.Series([0.10, -0.05, 0.02, 0.03])
    m = performance(r, rf_period=0.0, periods_per_year=4)
    wealth = np.cumprod(1 + r.to_numpy())
    assert m["rendimiento acumulado"] == pytest.approx(wealth[-1] - 1)
    assert m["rendimiento anual (CAGR)"] == pytest.approx(wealth[-1] - 1)  # 4 periodos = 1 año
    assert m["máximo drawdown"] == pytest.approx(-0.05)
    assert m["volatilidad anual"] == pytest.approx(r.std(ddof=1) * 2)


def test_optimizer_failure_keeps_previous_portfolio(returns):
    cfg = _cfg(bounds=[(0.0, 0.1)] * 5)  # cotas imposibles: nunca suman 1
    run = run_strategy(STRAT_GMV, returns, cfg)
    assert run.failures and "inviable" in run.failures[0]
    assert (run.weights_history.iloc[0] == 0.2).all()  # se declara el arranque en 1/N
    assert len(run.weights_history) == 1  # no se inventan pesos en las fechas que fallan
