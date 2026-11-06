"""
Desempeño frente a un benchmark (guía final, núcleo «Desempeño y benchmark» y «Betas y
rendimiento requerido»). Todo en la misma frecuencia y la misma muestra común.

Por periodo, con rf_p la tasa libre de riesgo del periodo:
- Sharpe   = (media(R_p) − rf_p) / σ(R_p), anualizado × √m.
- β y R²   = regresión de excesos R_p − rf_p sobre R_m − rf_p.
- Treynor  = (media(R_p) − rf_p)·m / β.
- α Jensen = [media(R_p) − rf_p − β (media(R_m) − rf_p)]·m.
- Error de seguimiento (TE) = σ(R_p − R_m)·√m; razón de información = media(R_p − R_m)·m / TE.
- Riesgo sistemático = R² (fracción de la varianza explicada por el benchmark: β²σ_m²/σ_p²);
  no sistemático = 1 − R².
- CAPM: rendimiento requerido = rf + β·ERP (anual).
Las medias se anualizan aritméticamente (μ·m), igual que en el laboratorio.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.capm import beta_ols


@dataclass
class Performance:
    name: str
    n: int
    ann_return: float
    ann_vol: float
    sharpe: float
    beta: float
    r_squared: float
    systematic_share: float
    idiosyncratic_share: float
    treynor: float
    jensen_alpha: float
    tracking_error: float
    information_ratio: float


def performance(name: str, port: pd.Series, bench: pd.Series, rf_period: float, m: int) -> Performance:
    df = pd.concat({"p": port, "b": bench}, axis=1, sort=True).dropna()
    if len(df) < 3:
        raise ValueError(f"{name}: menos de 3 observaciones comunes con el benchmark.")
    p, b = df["p"], df["b"]
    excess = p.mean() - rf_period
    vol = p.std(ddof=1)
    fit = beta_ols(p, b, rf=rf_period)
    beta = fit.beta
    diff = p - b
    te = diff.std(ddof=1) * np.sqrt(m)
    return Performance(
        name=name, n=len(df), ann_return=float(p.mean() * m), ann_vol=float(vol * np.sqrt(m)),
        sharpe=float(excess / vol * np.sqrt(m)) if vol > 0 else float("nan"),
        beta=float(beta), r_squared=float(fit.r_squared),
        systematic_share=float(fit.r_squared), idiosyncratic_share=float(1 - fit.r_squared),
        treynor=float(excess * m / beta) if np.isfinite(beta) and beta != 0 else float("nan"),
        jensen_alpha=float((excess - beta * (b.mean() - rf_period)) * m) if np.isfinite(beta) else float("nan"),
        tracking_error=float(te),
        information_ratio=float(diff.mean() * m / te) if te > 0 else float("nan"),
    )


def capm_required_return(rf_annual: float, beta: float, erp_annual: float) -> float:
    """Rendimiento requerido por CAPM (SML): rf + β·ERP, anual."""
    return float(rf_annual + beta * erp_annual)


def historical_erp(bench: pd.Series, rf_period: float, m: int) -> float:
    """Prima de mercado histórica del benchmark en la ventana: (media(R_m) − rf_p)·m."""
    return float((bench.dropna().mean() - rf_period) * m)


def performance_table(portfolios: "dict[str, pd.Series]", bench: pd.Series, rf_period: float, m: int) -> pd.DataFrame:
    rows = []
    for name, series in portfolios.items():
        try:
            rows.append(vars(performance(name, series, bench, rf_period, m)))
        except ValueError as exc:
            rows.append({"name": name, "n": 0, "nota": str(exc)})
    return pd.DataFrame(rows).set_index("name")
