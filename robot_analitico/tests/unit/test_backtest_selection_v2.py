"""
Fase 2 (v2) - Backtest: Black-Litterman con views por fecha, estimadores de
Sigma y selección en validación sin reajustar en la prueba final (guía V2,
4.2 y 7.2; P2-29, P2-30). Sin red.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.backtest import (  # noqa: E402
    STRAT_BL,
    STRAT_GMV,
    BacktestConfig,
    bl_label,
    run_strategy,
    select_by_validation,
    walk_forward,
)
from src.black_litterman import View  # noqa: E402
from src.portfolio import simple_returns_matrix  # noqa: E402


@pytest.fixture(scope="module")
def returns():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    return simple_returns_matrix(prices.iloc[:, :4]).returns


def _cfg(**kw):
    base = dict(window=120, rebalance_every=21, cost_rate=0.001, rf_period=0.0, gamma=3.0,
                bounds=[(0.0, 1.0)] * 4, periods_per_year=252, bl_delta=3.0)
    base.update(kw)
    return BacktestConfig(**base)


def test_bl_without_views_is_labeled_and_equals_equal_weight(returns):
    cfg = _cfg()  # gamma = delta y w_ref = 1/N
    assert "= 1/N" in bl_label(cfg)
    run = run_strategy(STRAT_BL, returns, cfg)
    np.testing.assert_allclose(run.weights_history.to_numpy(), 0.25, atol=1e-9)
    assert "= 1/N" not in bl_label(_cfg(gamma=5.0))


def test_bl_uses_each_view_only_between_known_and_expiry(returns):
    dates = returns.index
    known, expiry = dates[300], dates[420]
    view = View("V1", {"SIM1": 1.0}, 0.002, omega=1e-7, known_at=known.date(), expires_at=expiry.date())
    with_view = run_strategy(STRAT_BL, returns, _cfg(views=[view]))
    base = run_strategy(STRAT_BL, returns, _cfg())
    wh, bh = with_view.weights_history, base.weights_history
    before = wh.index < known
    active = (wh.index >= known) & (wh.index <= expiry)
    after = wh.index > expiry
    np.testing.assert_allclose(wh[before].to_numpy(), bh[before].to_numpy(), atol=1e-12)  # sin look-ahead de la view
    assert (wh[active]["SIM1"] > bh[active]["SIM1"] + 1e-3).all()  # la view optimista sube SIM1 mientras rige
    np.testing.assert_allclose(wh[after].to_numpy(), bh[after].to_numpy(), atol=1e-12)  # vencida, se retira
    assert "views registradas" in bl_label(_cfg(views=[view]))


def test_estimator_option_changes_weights(returns):
    sample = run_strategy(STRAT_GMV, returns, _cfg(estimator="muestral"))
    lw = run_strategy(STRAT_GMV, returns, _cfg(estimator="Ledoit-Wolf"))
    ewma = run_strategy(STRAT_GMV, returns, _cfg(estimator="EWMA", ewma_lambda=0.94))
    assert not np.allclose(sample.weights_history, lw.weights_history)
    assert not np.allclose(sample.weights_history, ewma.weights_history)
    with pytest.raises(ValueError):
        run_strategy(STRAT_GMV, returns, _cfg(estimator="otro"))


def test_selection_on_validation_reports_test_without_refit(returns):
    res = walk_forward(returns, _cfg(), strategies=[STRAT_GMV, "1/N rebalanceado"], estimators=["muestral", "Ledoit-Wolf"])
    # 1/N no depende de Σ: se corre una sola vez; la GMV, una vez por estimador.
    assert len(res.runs) == 3 and all("Σ" in name for name in res.runs)
    assert sum("no aplica" in name for name in res.runs) == 1
    pick = select_by_validation(res, criterion="Sharpe anual")
    val = res.metrics.xs("validación", level="tramo")["Sharpe anual"]
    assert pick.chosen == val.idxmax()  # elegido solo con validación
    test_row = res.metrics.loc[(pick.chosen, "prueba final")]
    assert pick.test_metrics["Sharpe anual"] == pytest.approx(test_row["Sharpe anual"])  # prueba final tal cual
    assert "sin reajustar" in pick.note
