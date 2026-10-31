"""
Escenarios de estrés, pérdida y concentración (guía V2, secciones 4.4 y 10).

- Shock individual: un activo cae x % y los demás no se mueven.
- Shock conjunto adverso: todos los activos sufren a la vez su peor
  rendimiento histórico (pesimista: en la realidad no ocurren el mismo día).
- Ruptura de correlaciones: se conservan las volatilidades y se fuerzan las
  correlaciones a un valor (por ejemplo 1: la diversificación desaparece).
- Escenario inverso: el shock MÁS PROBABLE (mínima distancia de Mahalanobis)
  que produce una pérdida dada; responde "¿qué tendría que pasar para romper
  el mandato?".
Convención: pérdida positiva = se pierde dinero. Los límites de pérdida los
fija el mandato del equipo.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import norm


def portfolio_loss(weights: pd.Series, shocks: pd.Series) -> float:
    """Pérdida como fracción del patrimonio: -sum_i w_i * shock_i."""
    s = shocks.reindex(weights.index).fillna(0.0)
    return float(-(weights * s).sum())


def individual_shocks(weights: pd.Series, shock: float) -> pd.Series:
    """Pérdida de la cartera si cada activo, por separado, cae `shock` (p. ej. -0.20)."""
    return pd.Series({a: -weights[a] * shock for a in weights.index}, name="pérdida")


def joint_worst_historical(weights: pd.Series, returns: pd.DataFrame) -> "tuple[float, pd.Series]":
    """Todos los activos en su peor rendimiento histórico a la vez (cota pesimista)."""
    worst = returns.min()
    return portfolio_loss(weights, worst), worst


def worst_historical_portfolio_period(weights: pd.Series, returns: pd.DataFrame) -> "tuple[float, object]":
    rp = (returns[weights.index] * weights).sum(axis=1)
    return float(-rp.min()), rp.idxmin()


def correlation_breakdown(sigma: pd.DataFrame, rho: float) -> pd.DataFrame:
    """Misma volatilidad por activo, todas las correlaciones iguales a rho (en [-1/(N-1), 1] para ser PSD)."""
    n = len(sigma)
    lower = -1 / (n - 1) if n > 1 else -1
    if not lower - 1e-12 <= rho <= 1 + 1e-12:
        raise ValueError(f"Con {n} activos, rho debe estar entre {lower:.3f} y 1 para que la matriz sea válida.")
    vol = np.sqrt(np.diag(sigma.to_numpy(dtype=float)))
    corr = np.full((n, n), rho)
    np.fill_diagonal(corr, 1.0)
    return pd.DataFrame(np.outer(vol, vol) * corr, index=sigma.index, columns=sigma.columns)


@dataclass
class ReverseStress:
    shocks: pd.Series  # shock por activo (decimal) que produce la pérdida objetivo
    mahalanobis: float  # "cuántas desviaciones" conjuntas hacen falta (más bajo = más plausible)
    loss: float


def reverse_stress(weights: pd.Series, sigma: pd.DataFrame, loss_limit: float) -> ReverseStress:
    """
    Shock x de mínima distancia sqrt(x' Sigma^-1 x) tal que -w'x = L:
    x = -L * Sigma w / (w' Sigma w); su distancia es L / sigma_p.
    """
    order = list(weights.index)
    s = sigma.loc[order, order].to_numpy(dtype=float)
    w = weights.to_numpy(dtype=float)
    var = float(w @ s @ w)
    if var <= 0:
        raise ValueError("La cartera no tiene riesgo estimado: ningún shock 'probable' la mueve.")
    x = -loss_limit * (s @ w) / var
    return ReverseStress(shocks=pd.Series(x, index=order), mahalanobis=float(loss_limit / np.sqrt(var)),
                         loss=float(-(w @ x)))


def parametric_var(mean_period: float, vol_period: float, confidence: float, horizon: int = 1) -> float:
    """VaR normal de la cartera (fracción del patrimonio, piso en 0): z*sigma*sqrt(h) - mu*h."""
    z = norm.ppf(confidence)
    return max(0.0, z * vol_period * np.sqrt(horizon) - mean_period * horizon)


def historical_var(portfolio_returns: pd.Series, confidence: float) -> float:
    """VaR histórico: pérdida del cuantil (1 - confianza) de los rendimientos observados (piso en 0)."""
    return max(0.0, float(-np.quantile(portfolio_returns.dropna(), 1 - confidence)))


@dataclass
class Concentration:
    hhi: float  # sum w^2 (1/N = diversificado al máximo; 1 = un solo activo)
    effective_n: float  # 1 / HHI
    max_weight: float
    max_asset: str


def concentration(weights: pd.Series) -> Concentration:
    w = weights.astype(float)
    hhi = float((w ** 2).sum())
    return Concentration(hhi=hhi, effective_n=1 / hhi if hhi > 0 else float("nan"),
                         max_weight=float(w.abs().max()), max_asset=str(w.abs().idxmax()))
