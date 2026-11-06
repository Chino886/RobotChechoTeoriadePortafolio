"""
Pérdida esperada (Expected Shortfall, ES) junto al VaR (guía final, núcleo «Riesgo y
probabilidades»). Módulo aparte para no modificar la v1 (src/risk_rules.py).

Activo individual (mismo modelo y horizonte que el VaR de la v1): el log-rendimiento
acumulado X ~ N(M, S²), con M = m·H y S² = σ²·H. La pérdida fraccional es 1 − e^X y
el VaR es la pérdida en el cuantil q = M + S·z_(1−c). La ES es la pérdida promedio
cuando se supera el VaR:
    ES = 1 − E[e^X | X ≤ q] = 1 − exp(M + S²/2) · Φ((q − M − S²)/S) / (1 − c).
"""
import numpy as np
from scipy.stats import norm

from src.forecasting import ForecastModel, terminal_moments


def expected_shortfall_fraction(model: ForecastModel, horizon: int, confidence: float) -> float:
    """ES fraccional (positivo = pérdida, con piso en cero como el VaR de la v1)."""
    m_h, v_h = terminal_moments(model, horizon)
    if v_h <= 0:  # rama determinista: no hay cola
        return max(0.0, 1.0 - float(np.exp(m_h)))
    s = v_h ** 0.5
    tail = 1.0 - confidence
    q = m_h + s * norm.ppf(tail)
    cond_mean = np.exp(m_h + v_h / 2) * norm.cdf((q - m_h - v_h) / s) / tail
    return max(0.0, 1.0 - float(cond_mean))
