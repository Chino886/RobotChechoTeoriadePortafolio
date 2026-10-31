"""
Beta, CAPM, apalancamiento y valoración (guía V2, secciones 8 y 9).

- Beta por OLS con intercepto sobre EXCESOS: R_i - rf = alpha + beta (R_M - rf) + e,
  contrastada con Cov(exceso_i, exceso_M) / Var(exceso_M) en la misma muestra.
  Un benchmark constante deja beta indefinida (no se divide por cero).
- Hamada con beta de la deuda (beta_D = 0 da la versión simplificada).
- Ke = rf + beta_L * ERP (+ lambda * CRP mostrado aparte) y paso a COP por
  paridad de inflación: (1 + Ke_USD)(1 + pi_COL)/(1 + pi_USA) - 1.
- WACC, FCFF, FCFE, valor terminal con WACC > g y puente EV -> patrimonio.

Los insumos (benchmark, rf, ERP, CRP, lambda, impuestos, estructura objetivo,
proyecciones) los decide el equipo o vienen congelados del caso docente.
"""
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy import stats as sps


@dataclass
class BetaResult:
    status: str  # "ok" o "indefinido"
    n: int
    beta: float = float("nan")
    alpha: float = float("nan")
    beta_cov_ratio: float = float("nan")  # Cov/Var, debe coincidir con la pendiente OLS
    std_error: float = float("nan")
    ci95: "tuple[float, float]" = (float("nan"), float("nan"))
    r_squared: float = float("nan")
    message: str = ""


def beta_ols(asset_returns: pd.Series, market_returns: pd.Series, rf=0.0) -> BetaResult:
    """
    Regresión con intercepto de excesos. `rf` puede ser un escalar o una serie
    alineada (tasa del mismo periodo). Usa solo fechas comunes sin faltantes.
    """
    df = pd.concat({"i": asset_returns, "m": market_returns}, axis=1)
    if isinstance(rf, pd.Series):
        df["rf"] = rf
    else:
        df["rf"] = float(rf)
    df = df.dropna()
    n = len(df)
    if n < 3:
        return BetaResult(status="indefinido", n=n, message="Se necesitan al menos 3 observaciones comunes.")
    y = (df["i"] - df["rf"]).to_numpy()
    x = (df["m"] - df["rf"]).to_numpy()
    var_x = np.var(x, ddof=1)
    if var_x <= 1e-18:
        return BetaResult(status="indefinido", n=n, message="El benchmark (en exceso) es constante: beta indefinida.")
    cov_ratio = float(np.cov(y, x, ddof=1)[0, 1] / var_x)
    X = np.column_stack([np.ones(n), x])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ coef
    dof = n - 2
    s2 = float(resid @ resid / dof)
    cov_coef = s2 * np.linalg.inv(X.T @ X)
    se = float(np.sqrt(cov_coef[1, 1]))
    t = sps.t.ppf(0.975, dof)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - float(resid @ resid) / ss_tot if ss_tot > 0 else float("nan")
    return BetaResult(
        status="ok", n=n, beta=float(coef[1]), alpha=float(coef[0]), beta_cov_ratio=cov_ratio,
        std_error=se, ci95=(float(coef[1] - t * se), float(coef[1] + t * se)), r_squared=r2,
    )


def unlever_beta(beta_levered: float, debt_to_equity: float, tax: float, beta_debt: float = 0.0) -> float:
    """beta_U = [beta_L + beta_D (1 - t) D/E] / [1 + (1 - t) D/E]. Con beta_D = 0 es Hamada simplificada."""
    k = (1 - tax) * debt_to_equity
    return (beta_levered + beta_debt * k) / (1 + k)


def relever_beta(beta_unlevered: float, debt_to_equity: float, tax: float, beta_debt: float = 0.0) -> float:
    """beta_L = beta_U + (beta_U - beta_D) (1 - t) D/E. Con beta_D = 0: beta_U [1 + (1 - t) D/E]."""
    return beta_unlevered + (beta_unlevered - beta_debt) * (1 - tax) * debt_to_equity


@dataclass
class CostOfEquity:
    rf: float
    beta: float
    erp: float
    base: float  # rf + beta * ERP
    country_premium: float  # lambda * CRP, mostrado por separado
    ke: float  # base + prima país


def cost_of_equity(rf: float, beta_levered: float, erp: float, crp: float = 0.0, lam: float = 0.0) -> CostOfEquity:
    base = rf + beta_levered * erp
    country = lam * crp
    return CostOfEquity(rf=rf, beta=beta_levered, erp=erp, base=base, country_premium=country, ke=base + country)


def nominal_rate_to_other_currency(rate: float, inflation_target: float, inflation_source: float) -> float:
    """(1 + r)(1 + pi_destino)/(1 + pi_origen) - 1. No es suma de inflaciones ni predicción de TRM."""
    return (1 + rate) * (1 + inflation_target) / (1 + inflation_source) - 1


def sml_required_return(rf: float, beta: float, erp: float) -> float:
    """SML: E(R) = rf + beta * ERP (el eje es beta, no la volatilidad total)."""
    return rf + beta * erp


def wacc(ke: float, kd: float, tax: float, debt_to_equity: float) -> float:
    """WACC = E/(D+E) Ke + D/(D+E) Kd (1 - t), con pesos derivados de D/E."""
    wd = debt_to_equity / (1 + debt_to_equity)
    return (1 - wd) * ke + wd * kd * (1 - tax)


def fcff(ebit: float, tax: float, d_and_a: float, capex: float, delta_nwc: float) -> float:
    """FCFF = EBIT (1 - t) + D&A - CAPEX - delta NWC."""
    return ebit * (1 - tax) + d_and_a - capex - delta_nwc


def fcfe(net_income: float, d_and_a: float, capex: float, delta_nwc: float, net_borrowing: float) -> float:
    """FCFE = NI + D&A - CAPEX - delta NWC + deuda neta emitida."""
    return net_income + d_and_a - capex - delta_nwc + net_borrowing


def terminal_value(next_cash_flow: float, discount_rate: float, growth: float) -> float:
    """TV_H = flujo_(H+1) / (r - g). Exige r > g (si no, el valor no está definido)."""
    if discount_rate <= growth:
        raise ValueError(f"La tasa de descuento ({discount_rate:.4%}) debe ser mayor que g ({growth:.4%}).")
    return next_cash_flow / (discount_rate - growth)


@dataclass
class DCFResult:
    present_values: "list[float]"
    terminal: float
    pv_terminal: float
    enterprise_value: float
    terminal_share: float  # peso del terminal sobre el EV


def discounted_cash_flow(flows: "list[float]", discount_rate: float, growth: float,
                         next_flow: Optional[float] = None) -> DCFResult:
    """
    Flujos de fin de año 1..H descontados a `discount_rate` y valor terminal
    al cierre del año H. Si no se da `next_flow`, se usa flujo_H (1 + g); esa
    simplificación supone reinversión coherente con g (revisar reinversión = g/ROIC).
    """
    if not flows:
        raise ValueError("Se necesita al menos un flujo proyectado.")
    h = len(flows)
    pvs = [f / (1 + discount_rate) ** t for t, f in enumerate(flows, start=1)]
    nxt = flows[-1] * (1 + growth) if next_flow is None else next_flow
    tv = terminal_value(nxt, discount_rate, growth)
    pv_tv = tv / (1 + discount_rate) ** h
    ev = sum(pvs) + pv_tv
    return DCFResult(present_values=pvs, terminal=tv, pv_terminal=pv_tv, enterprise_value=ev,
                     terminal_share=pv_tv / ev if ev else float("nan"))


def equity_value(enterprise_value: float, excess_cash: float, non_operating_assets: float,
                 financial_debt: float, other_claims: float = 0.0) -> float:
    """Equity = EV + caja excedente + otros activos no operativos - deuda financiera - otros derechos prioritarios."""
    return enterprise_value + excess_cash + non_operating_assets - financial_debt - other_claims


def stable_reinvestment_rate(growth: float, roic: float) -> float:
    """Reinversión estable = g / ROIC (crecer exige invertir)."""
    if roic <= 0:
        raise ValueError("ROIC debe ser positivo.")
    return growth / roic
