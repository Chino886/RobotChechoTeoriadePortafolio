"""
Evaluación temporal walk-forward de estrategias (guía V2, sección 7.2).

- En cada fecha de decisión t solo se usan rendimientos ANTERIORES a t
  (ventana móvil de `window` periodos); los pesos se aplican desde t. Sin
  look-ahead (P2-29).
- Todas las estrategias comparten universo, periodo, frecuencia de
  rebalanceo y costos (P2-30).
- Entre rebalanceos los pesos derivan con los precios; los costos se cobran
  sobre el nominal negociado (sum |delta w| * patrimonio).
- La muestra se separa en calentamiento (primera ventana, no se evalúa),
  validación y prueba final. Las elecciones (ventana, gamma, frecuencia)
  deben hacerse mirando validación, no la prueba final.
- Si el optimizador falla en una fecha se conserva la cartera anterior y se
  cuenta la falla (no se inventan pesos).
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from src.black_litterman import implied_prior
from src.portfolio import covariance_matrix, min_variance, personal_optimum

STRAT_HOLD = "Mantener cantidades (1/N inicial)"
STRAT_EQUAL = "1/N rebalanceado"
STRAT_GMV = "Mínima varianza (GMV)"
STRAT_MV = "Markowitz (óptimo personal γ)"
STRAT_BL = "Black-Litterman (prior, sin views)"
ALL_STRATEGIES = [STRAT_HOLD, STRAT_EQUAL, STRAT_GMV, STRAT_MV, STRAT_BL]


@dataclass
class BacktestConfig:
    window: int  # observaciones de la ventana de estimación
    rebalance_every: int  # cada cuántos periodos se decide
    cost_rate: float  # costo por unidad de nominal negociado
    rf_period: float
    gamma: float
    bounds: "list[tuple[Optional[float], Optional[float]]]"
    periods_per_year: int
    validation_share: float = 0.5  # fracción del tramo evaluable usada como validación
    bl_delta: float = 3.0
    groups: Optional[list] = None


@dataclass
class StrategyRun:
    wealth: pd.Series  # valor neto (empieza en 1)
    returns: pd.Series  # rendimiento neto por periodo
    weights_history: pd.DataFrame  # pesos objetivo en cada decisión
    turnover: pd.Series  # rotación en cada decisión
    costs: pd.Series  # costo (fracción del patrimonio) en cada decisión
    failures: "list[str]" = field(default_factory=list)


@dataclass
class BacktestResult:
    runs: "dict[str, StrategyRun]"
    metrics: pd.DataFrame  # filas (estrategia, tramo)
    validation_start: pd.Timestamp
    test_start: pd.Timestamp
    decision_dates: "list[pd.Timestamp]"


def _target_weights(strategy: str, window: pd.DataFrame, cfg: BacktestConfig, previous: Optional[pd.Series]) -> "tuple[Optional[pd.Series], str]":
    assets = list(window.columns)
    n = len(assets)
    if strategy in (STRAT_EQUAL, STRAT_HOLD):
        return pd.Series(1.0 / n, index=assets), ""
    mu = window.mean()
    sigma = covariance_matrix(window)
    if strategy == STRAT_GMV:
        res = min_variance(mu, sigma, cfg.bounds, groups=cfg.groups)
    elif strategy == STRAT_MV:
        res = personal_optimum(mu, sigma, cfg.gamma, cfg.bounds, groups=cfg.groups)
    elif strategy == STRAT_BL:
        pi = implied_prior(sigma, pd.Series(1.0 / n, index=assets), cfg.bl_delta)
        res = personal_optimum(pi + cfg.rf_period, sigma, cfg.gamma, cfg.bounds, groups=cfg.groups)
    else:
        raise ValueError(f"Estrategia desconocida: {strategy}")
    if not res.ok:
        return None, f"{res.status}: {res.message}"
    return res.weights, ""


def run_strategy(strategy: str, returns: pd.DataFrame, cfg: BacktestConfig,
                 target_fn: Optional[Callable] = None) -> StrategyRun:
    target_fn = target_fn or _target_weights
    r = returns.to_numpy(dtype=float)
    dates = returns.index
    assets = list(returns.columns)
    t0 = cfg.window
    if len(returns) <= t0 + 1:
        raise ValueError("La muestra no alcanza para la ventana de estimación más un periodo de evaluación.")
    w = None
    wealth = 1.0
    out_wealth, out_ret = [], []
    hist, turns, costs, failures = {}, {}, {}, []
    for t in range(t0, len(r)):
        is_decision = (t - t0) % cfg.rebalance_every == 0
        cost = 0.0
        if is_decision and (strategy != STRAT_HOLD or w is None):
            window = returns.iloc[t - cfg.window: t]  # solo información anterior a t
            target, why = target_fn(strategy, window, cfg, None if w is None else pd.Series(w, index=assets))
            if target is None:
                failures.append(f"{dates[t].date() if hasattr(dates[t], 'date') else dates[t]}: {why}")
                if w is None:
                    target = pd.Series(1.0 / len(assets), index=assets)  # primer periodo sin solución: se declara
                    failures[-1] += " (se usa 1/N para empezar)"
            if target is not None:
                new_w = target.reindex(assets).to_numpy(dtype=float)
                prev = np.zeros(len(assets)) if w is None else w
                traded = float(np.abs(new_w - prev).sum())
                cost = cfg.cost_rate * traded if w is not None else 0.0  # la compra inicial no se cobra: base común
                turns[dates[t]] = 0.5 * traded if w is not None else 0.0
                costs[dates[t]] = cost
                hist[dates[t]] = pd.Series(new_w, index=assets)
                w = new_w
        rp = float(w @ r[t])
        net = (1 - cost) * (1 + rp) - 1
        wealth *= 1 + net
        out_wealth.append(wealth)
        out_ret.append(net)
        w = w * (1 + r[t]) / (1 + rp) if 1 + rp != 0 else w  # deriva
    idx = dates[t0:]
    return StrategyRun(
        wealth=pd.Series(out_wealth, index=idx, name=strategy), returns=pd.Series(out_ret, index=idx, name=strategy),
        weights_history=pd.DataFrame(hist).T, turnover=pd.Series(turns, dtype=float),
        costs=pd.Series(costs, dtype=float), failures=failures,
    )


def performance(net_returns: pd.Series, rf_period: float, periods_per_year: int) -> dict:
    if net_returns.empty:
        return {}
    wealth = (1 + net_returns).cumprod()
    years = len(net_returns) / periods_per_year
    cagr = wealth.iloc[-1] ** (1 / years) - 1 if years > 0 and wealth.iloc[-1] > 0 else float("nan")
    vol = net_returns.std(ddof=1) * np.sqrt(periods_per_year) if len(net_returns) > 1 else float("nan")
    excess = net_returns - rf_period
    sharpe = excess.mean() / net_returns.std(ddof=1) * np.sqrt(periods_per_year) if len(net_returns) > 1 and net_returns.std(ddof=1) > 0 else float("nan")
    dd = (wealth / wealth.cummax() - 1).min()
    return {"rendimiento anual (CAGR)": cagr, "volatilidad anual": vol, "Sharpe anual": sharpe,
            "máximo drawdown": dd, "rendimiento acumulado": wealth.iloc[-1] - 1, "periodos": len(net_returns)}


def walk_forward(returns: pd.DataFrame, cfg: BacktestConfig, strategies: "Optional[list[str]]" = None) -> BacktestResult:
    strategies = strategies or ALL_STRATEGIES
    runs = {s: run_strategy(s, returns, cfg) for s in strategies}
    eval_index = returns.index[cfg.window:]
    split = int(len(eval_index) * cfg.validation_share)
    split = min(max(split, 1), len(eval_index) - 1)
    val_start, test_start = eval_index[0], eval_index[split]
    rows = []
    for name, run in runs.items():
        for segment, sl in (("validación", run.returns.loc[:test_start].iloc[:-1]), ("prueba final", run.returns.loc[test_start:])):
            m = performance(sl, cfg.rf_period, cfg.periods_per_year)
            seg_turn = run.turnover[(run.turnover.index >= sl.index[0]) & (run.turnover.index <= sl.index[-1])] if len(sl) else run.turnover.iloc[:0]
            seg_cost = run.costs[(run.costs.index >= sl.index[0]) & (run.costs.index <= sl.index[-1])] if len(sl) else run.costs.iloc[:0]
            wh = run.weights_history
            stability = float(wh.diff().abs().sum(axis=1).iloc[1:].mean()) if len(wh) > 1 else 0.0
            m.update({"estrategia": name, "tramo": segment, "rotación media por decisión": float(seg_turn.mean()) if len(seg_turn) else 0.0,
                      "costos totales": float(seg_cost.sum()), "cambio medio de pesos objetivo": stability,
                      "fallas del optimizador": len(run.failures)})
            rows.append(m)
    metrics = pd.DataFrame(rows).set_index(["estrategia", "tramo"])
    decisions = sorted(set().union(*[set(r.weights_history.index) for r in runs.values()]))
    return BacktestResult(runs=runs, metrics=metrics, validation_start=val_start, test_start=test_start, decision_dates=decisions)
