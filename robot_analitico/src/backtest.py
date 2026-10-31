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
- Black-Litterman usa las views registradas, cada una solo desde su fecha de
  conocimiento y hasta su vencimiento. Sin views, con gamma = delta y
  w_ref = 1/N, el óptimo coincide exactamente con 1/N: se rotula así.
- Sigma puede estimarse con la muestral, Ledoit-Wolf o EWMA (guía 4.2), y la
  elección entre candidatos se hace en validación; la prueba final se reporta
  sin reajustar.
"""
from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np
import pandas as pd

from src.black_litterman import build_view_set, implied_prior, posterior
from src.estimators import ewma_covariance, ledoit_wolf
from src.portfolio import covariance_matrix, min_variance, personal_optimum

STRAT_HOLD = "Mantener cantidades (1/N inicial)"
STRAT_EQUAL = "1/N rebalanceado"
STRAT_GMV = "Mínima varianza (GMV)"
STRAT_MV = "Markowitz (óptimo personal γ)"
STRAT_BL = "Black-Litterman"
ALL_STRATEGIES = [STRAT_HOLD, STRAT_EQUAL, STRAT_GMV, STRAT_MV, STRAT_BL]
ESTIMATORS = ["muestral", "Ledoit-Wolf", "EWMA"]


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
    estimator: str = "muestral"  # "muestral", "Ledoit-Wolf" o "EWMA"
    ewma_lambda: float = 0.94
    views: Optional[list] = None  # views registradas (con known_at / expires_at)
    bl_tau: float = 0.05
    w_ref: Optional[pd.Series] = None  # referencia de BL; None = 1/N


def bl_label(cfg: BacktestConfig) -> str:
    """Nombre honesto de la estrategia BL según las views y los parámetros."""
    if cfg.views:
        return "Black-Litterman (views registradas, por fecha)"
    if cfg.w_ref is None and abs(cfg.gamma - cfg.bl_delta) < 1e-12:
        return "Black-Litterman sin views (= 1/N: γ = δ y w_ref = 1/N)"
    return "Black-Litterman sin views (prior de equilibrio)"


def estimate_sigma(window: pd.DataFrame, cfg: BacktestConfig) -> pd.DataFrame:
    if cfg.estimator == "muestral":
        return covariance_matrix(window)
    if cfg.estimator == "Ledoit-Wolf":
        return ledoit_wolf(window).sigma
    if cfg.estimator == "EWMA":
        return ewma_covariance(window, cfg.ewma_lambda)
    raise ValueError(f"Estimador desconocido: {cfg.estimator}")


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


def _target_weights(strategy: str, window: pd.DataFrame, cfg: BacktestConfig, previous: Optional[pd.Series],
                    as_of=None) -> "tuple[Optional[pd.Series], str]":
    assets = list(window.columns)
    n = len(assets)
    if strategy in (STRAT_EQUAL, STRAT_HOLD):
        return pd.Series(1.0 / n, index=assets), ""
    mu = window.mean()
    sigma = estimate_sigma(window, cfg)
    if strategy == STRAT_GMV:
        res = min_variance(mu, sigma, cfg.bounds, groups=cfg.groups)
    elif strategy == STRAT_MV:
        res = personal_optimum(mu, sigma, cfg.gamma, cfg.bounds, groups=cfg.groups)
    elif strategy == STRAT_BL:
        ref = cfg.w_ref.reindex(assets) if cfg.w_ref is not None else pd.Series(1.0 / n, index=assets)
        pi = implied_prior(sigma, ref, cfg.bl_delta)
        mu_bl = pi
        if cfg.views:
            day = pd.Timestamp(as_of if as_of is not None else window.index[-1]).date()
            vs = build_view_set(cfg.views, assets, sigma, cfg.bl_tau, as_of=day)  # solo views conocidas y vigentes
            mu_bl = posterior(sigma, pi, cfg.bl_tau, vs).posterior
        res = personal_optimum(mu_bl + cfg.rf_period, sigma, cfg.gamma, cfg.bounds, groups=cfg.groups)
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
            target, why = target_fn(strategy, window, cfg, None if w is None else pd.Series(w, index=assets), dates[t])
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


def walk_forward(returns: pd.DataFrame, cfg: BacktestConfig, strategies: "Optional[list[str]]" = None,
                 estimators: "Optional[list[str]]" = None) -> BacktestResult:
    """
    Corre cada estrategia (y, si se pasan varios, cada estimador de Sigma)
    con la misma configuración. Los nombres incluyen el estimador cuando hay
    más de uno; BL lleva su rótulo honesto (ver bl_label).
    """
    from dataclasses import replace

    strategies = strategies or ALL_STRATEGIES
    estimators = estimators or [cfg.estimator]
    runs = {}
    for est in estimators:
        c = replace(cfg, estimator=est)
        for s in strategies:
            name = bl_label(c) if s == STRAT_BL else s
            if len(estimators) > 1 and s not in (STRAT_HOLD, STRAT_EQUAL):
                name = f"{name} · Σ {est}"
            elif len(estimators) > 1:
                name = f"{name} · Σ (no aplica)"
                if name in runs:
                    continue
            runs[name] = run_strategy(s, returns, c)
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


@dataclass
class Selection:
    chosen: str
    criterion: str
    validation_metrics: dict
    test_metrics: dict
    note: str


def select_by_validation(result: BacktestResult, criterion: str = "Sharpe anual",
                         candidates: "Optional[list[str]]" = None, higher_is_better: bool = True) -> Selection:
    """
    Elige entre los candidatos definidos por el equipo usando SOLO el tramo
    de validación; la prueba final del elegido se reporta tal cual, sin
    reajustar ni volver a elegir.
    """
    val = result.metrics.xs("validación", level="tramo")
    if candidates:
        val = val.loc[[c for c in candidates if c in val.index]]
    scores = val[criterion].dropna()
    if scores.empty:
        raise ValueError("Ningún candidato tiene la métrica de validación.")
    chosen = scores.idxmax() if higher_is_better else scores.idxmin()
    return Selection(
        chosen=chosen, criterion=criterion, validation_metrics=val.loc[chosen].to_dict(),
        test_metrics=result.metrics.loc[(chosen, "prueba final")].to_dict(),
        note=f"Elegido por {criterion} en validación; la prueba final se muestra sin reajustar.",
    )
