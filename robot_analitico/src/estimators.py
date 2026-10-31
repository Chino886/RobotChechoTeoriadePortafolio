"""
Estimadores alternativos de la matriz de covarianza (guía V2, sección 4.2):
se contrastan con la muestral para ver su efecto sobre pesos y estabilidad.
Sus parámetros (lambda de EWMA) los fija el equipo SIN usar el bloque de prueba.

- Ledoit-Wolf (2004) hacia una identidad escalada: Sigma = d*mu*I + (1-d)*S,
  con la intensidad d estimada de los datos (entre 0 y 1). Reduce el error de
  estimación cuando hay muchos activos para pocas observaciones.
- EWMA: pondera más las observaciones recientes con lambda en (0, 1); el
  peso de la observación de hace k periodos es proporcional a lambda^k.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class ShrinkageResult:
    sigma: pd.DataFrame
    intensity: float  # d en [0, 1]: 0 = muestral (MLE), 1 = solo el blanco
    target_variance: float  # mu = traza(S)/N


def ledoit_wolf(returns: pd.DataFrame) -> ShrinkageResult:
    """
    Ledoit-Wolf hacia mu*I. Usa la covarianza MLE (divide por T), como el
    artículo original; para T grande la diferencia con ddof=1 es despreciable.
    """
    if returns.isna().any().any():
        raise ValueError("Use una muestra común sin faltantes.")
    x = returns.to_numpy(dtype=float)
    t, n = x.shape
    if t < 2:
        raise ValueError("Se necesitan al menos 2 observaciones.")
    x = x - x.mean(axis=0)
    s = x.T @ x / t
    mu = np.trace(s) / n
    delta2 = np.sum((s - mu * np.eye(n)) ** 2) / n
    beta_bar2 = sum(np.sum((np.outer(row, row) - s) ** 2) for row in x) / (t ** 2) / n
    beta2 = min(beta_bar2, delta2)
    d = 0.0 if delta2 == 0 else beta2 / delta2
    shrunk = d * mu * np.eye(n) + (1 - d) * s
    cols = returns.columns
    return ShrinkageResult(sigma=pd.DataFrame(shrunk, index=cols, columns=cols), intensity=float(d), target_variance=float(mu))


def ewma_covariance(returns: pd.DataFrame, lam: float) -> pd.DataFrame:
    """
    Covarianza con pesos exponenciales: w_k ∝ lam^k (k = 0 la más reciente),
    normalizados a sumar 1, sobre retornos centrados en su media ponderada.
    """
    if not 0 < lam < 1:
        raise ValueError("lambda debe estar entre 0 y 1.")
    if returns.isna().any().any():
        raise ValueError("Use una muestra común sin faltantes.")
    x = returns.to_numpy(dtype=float)
    t = len(x)
    weights = lam ** np.arange(t - 1, -1, -1)  # la última fila (más reciente) pesa 1
    weights = weights / weights.sum()
    mean = weights @ x
    centered = x - mean
    cov = (centered * weights[:, None]).T @ centered
    cols = returns.columns
    return pd.DataFrame(cov, index=cols, columns=cols)


def ewma_weights(n: int, lam: float) -> np.ndarray:
    """Pesos EWMA normalizados (del más antiguo al más reciente), útiles para mostrar la 'memoria' efectiva."""
    w = lam ** np.arange(n - 1, -1, -1)
    return w / w.sum()
