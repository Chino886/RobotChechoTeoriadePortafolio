"""
Valoración del caso Alimentos del Norte (guía V2, secciones 8.2, 9 y 9.1).

Parámetros congelados de paquete_v2/data/caso_alimentos_parametros.json:
EBIT = ventas*(1 - costo_variable) - gastos_fijos - depreciación (año 0:
150.000*0,4 - 33.000 - 9.000 = 18.000). Capital de trabajo = nwc_ventas*ventas.

Decisiones del equipo (entradas, nunca valores fijados aquí): crecimiento de
ventas y márgenes futuros, CAPEX y depreciación por año (la regla del caso con
capacidad_ventas y capex_venta_adicional está PENDIENTE de confirmar con el
PDF del caso, que no está en el repositorio), deuda futura, ROIC estable y las
magnitudes de los escenarios.

Escenarios (mecanismo simplificado y documentado; magnitudes del equipo):
- Insumos importados: un choque FX encarece la parte importada del costo
  variable: cv_año = cv * (1 + participación_importada * choque_FX).
- Rezago de 60 días: los precios trasladan ese mayor costo con un rezago de
  L días; el primer año el margen absorbe el costo adicional durante L/365 del
  año y desde entonces se traslada. (Si el equipo modela otro mecanismo, se
  cambia aquí con su prueba.)
- Tasa variable: Kd sube (o baja) en un diferencial; afecta intereses,
  utilidad neta, FCFE y WACC.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from src.capm import (
    cost_of_equity,
    discounted_cash_flow,
    nominal_rate_to_other_currency,
    relever_beta,
    terminal_value,
    wacc,
)

COVENANT_MAX = 3.0  # deuda/EBITDA < 3 (Restrepo Montoya, 2026, p. 81)


def ebit_from_drivers(sales: float, variable_cost: float, fixed_costs: float, depreciation: float) -> float:
    return sales * (1 - variable_cost) - fixed_costs - depreciation


@dataclass
class Scenario:
    """Magnitudes de los escenarios: todas son decisión del equipo (0 = sin escenario)."""
    fx_shock: float = 0.0  # variación del tipo de cambio que encarece insumos importados
    imported_share: float = 0.0  # fracción del costo variable que es importada
    pass_through_lag_days: float = 0.0  # rezago para trasladar el mayor costo a precios
    kd_shift: float = 0.0  # cambio de Kd por tasa variable (decimal)


@dataclass
class Projection:
    table: pd.DataFrame  # filas = años 0..H
    kd: float
    tax: float
    scenario: Scenario
    notes: "list[str]" = field(default_factory=list)


def project(params: dict, sales_growth: "list[float]", capex: "list[float]", depreciation: "list[float]",
            variable_cost: "Optional[list[float]]" = None, fixed_costs: "Optional[list[float]]" = None,
            debt: "Optional[list[float]]" = None, scenario: Optional[Scenario] = None) -> Projection:
    """
    Proyección anual (años 1..H) con los parámetros del caso. Las listas
    tienen un valor por año proyectado; costo variable, gastos fijos y deuda
    usan los del año 0 si no se entregan.
    """
    h = len(sales_growth)
    if not (len(capex) == len(depreciation) == h):
        raise ValueError("Crecimiento, CAPEX y depreciación deben tener un valor por año.")
    sc = scenario or Scenario()
    cv0, fixed0, debt0 = params["costo_variable"], params["gastos_fijos"], params["deuda_financiera"]
    cv = variable_cost or [cv0] * h
    fixed = fixed_costs or [fixed0] * h
    debt_path = debt or [debt0] * h
    tax = params["tax_supuesto"]
    kd = params["kd_EA"] + sc.kd_shift
    nwc_rate = params["nwc_ventas"]

    rows = [{
        "año": 0, "ventas": params["ventas0"], "costo variable %": cv0, "gastos fijos": fixed0,
        "depreciación": params["depreciacion0"],
        "EBIT": ebit_from_drivers(params["ventas0"], cv0, fixed0, params["depreciacion0"]),
        "capital de trabajo": nwc_rate * params["ventas0"], "deuda": debt0,
    }]
    sales = params["ventas0"]
    for t in range(h):
        sales = sales * (1 + sales_growth[t])
        cost_rate = cv[t]
        if t == 0 and sc.fx_shock and sc.imported_share:
            extra = cv[t] * sc.imported_share * sc.fx_shock  # costo adicional por el choque FX
            cost_rate = cv[t] + extra * min(max(sc.pass_through_lag_days, 0.0), 365.0) / 365.0
        rows.append({
            "año": t + 1, "ventas": sales, "costo variable %": cost_rate, "gastos fijos": fixed[t],
            "depreciación": depreciation[t], "EBIT": ebit_from_drivers(sales, cost_rate, fixed[t], depreciation[t]),
            "capital de trabajo": nwc_rate * sales, "deuda": debt_path[t], "CAPEX": capex[t],
        })
    df = pd.DataFrame(rows).set_index("año")
    df["ΔNWC"] = df["capital de trabajo"].diff()
    df["EBITDA"] = df["EBIT"] + df["depreciación"]
    df["NOPAT"] = df["EBIT"] * (1 - tax)
    df["FCFF"] = df["NOPAT"] + df["depreciación"] - df["CAPEX"] - df["ΔNWC"]
    df["intereses"] = kd * df["deuda"].shift(1).fillna(df["deuda"])  # intereses sobre la deuda al inicio del año
    df["utilidad neta"] = (df["EBIT"] - df["intereses"]) * (1 - tax)
    df["deuda neta emitida"] = df["deuda"].diff()
    df["FCFE"] = df["utilidad neta"] + df["depreciación"] - df["CAPEX"] - df["ΔNWC"] + df["deuda neta emitida"]
    df["deuda/EBITDA"] = df["deuda"] / df["EBITDA"]
    df["covenant < 3"] = df["deuda/EBITDA"] < COVENANT_MAX
    notes = []
    breaches = df.index[(~df["covenant < 3"]) & (df.index > 0)].tolist()
    if breaches:
        notes.append(f"⚠️ Covenant deuda/EBITDA < {COVENANT_MAX:g} incumplido en el año {', '.join(map(str, breaches))}.")
    return Projection(table=df, kd=kd, tax=tax, scenario=sc, notes=notes)


@dataclass
class CostOfCapital:
    beta_levered: float
    ke_usd: float
    ke_cop: float
    wacc: float
    debt_to_equity: float


def case_cost_of_capital(params: dict, beta_unlevered: float, debt_to_equity: float, kd: Optional[float] = None) -> CostOfCapital:
    """beta_L a la estructura dada, Ke USD con prima país aparte, Ke COP por paridad de inflación y WACC en COP."""
    beta_l = relever_beta(beta_unlevered, debt_to_equity, params["tax_supuesto"], params["beta_deuda_supuesto"])
    ke = cost_of_equity(params["rf_USD"], beta_l, params["erp_madura"], params["proxy_pais"], params["lambda"]).ke
    ke_cop = nominal_rate_to_other_currency(ke, params["inflacion_COL"], params["inflacion_USA"])
    w = wacc(ke_cop, params["kd_EA"] if kd is None else kd, params["tax_supuesto"], debt_to_equity)
    return CostOfCapital(beta_levered=beta_l, ke_usd=ke, ke_cop=ke_cop, wacc=w, debt_to_equity=debt_to_equity)


@dataclass
class BudgetGap:
    required_net_income: float  # Ke * patrimonio en libros (meta presupuestal del caso)
    required_ebit: float  # EBIT que produce esa utilidad neta
    gap_by_year: pd.Series  # EBIT requerido - EBIT proyectado (positivo = falta)


def budget_target(projection: Projection, ke: float, equity_book: float) -> BudgetGap:
    """
    Meta presupuestal Ke * patrimonio en libros (P113-P114). No es la
    rentabilidad exigida de mercado ni alfa: es una meta contable del caso.
    """
    df = projection.table
    ni_req = ke * equity_book
    interest = df["intereses"]
    ebit_req = ni_req / (1 - projection.tax) + interest
    return BudgetGap(required_net_income=ni_req, required_ebit=float(ebit_req.iloc[1]),
                     gap_by_year=(ebit_req - df["EBIT"]).iloc[1:])


@dataclass
class ValuationResult:
    enterprise_value: float
    equity_fcff: float  # EV - deuda
    equity_fcfe: float  # FCFE descontado a Ke
    difference: float
    terminal_share: float
    explanation: str


def value_firm(projection: Projection, wacc_rate: float, ke: float, growth: float) -> ValuationResult:
    """FCFF a WACC (EV - deuda) y FCFE a Ke, conciliados (P116-P117). Exige WACC > g y Ke > g."""
    df = projection.table.loc[1:]
    dcf = discounted_cash_flow(df["FCFF"].tolist(), wacc_rate, growth)
    debt0 = float(projection.table["deuda"].iloc[0])
    eq_fcff = dcf.enterprise_value - debt0
    fcfe = df["FCFE"].tolist()
    h = len(fcfe)
    pv = sum(f / (1 + ke) ** t for t, f in enumerate(fcfe, start=1))
    tv = terminal_value(fcfe[-1] * (1 + growth), ke, growth)
    eq_fcfe = pv + tv / (1 + ke) ** h
    diff = eq_fcfe - eq_fcff
    explanation = (
        "Las dos rutas solo coinciden si la estructura de capital usada en el WACC es la que resulta de los "
        "valores (D/E de mercado constante) y el FCFE incluye la deuda neta coherente con esa estructura. "
        "Una diferencia grande señala supuestos inconsistentes entre Kd, D/E y la deuda proyectada."
    )
    return ValuationResult(enterprise_value=dcf.enterprise_value, equity_fcff=eq_fcff, equity_fcfe=eq_fcfe,
                           difference=diff, terminal_share=dcf.terminal_share, explanation=explanation)


@dataclass
class IterationStep:
    iteration: int
    debt_to_equity: float
    beta_levered: float
    ke_cop: float
    wacc: float
    equity: float


def iterate_capital_structure(params: dict, projection: Projection, beta_unlevered: float, growth: float,
                              start_de: float, tol: float = 1e-6, max_iter: int = 100) -> "list[IterationStep]":
    """
    D/E de mercado coherente con el valor (P108, P119): se valora con un D/E,
    se calcula el patrimonio, D/E = deuda/patrimonio, se reapalanca beta y se
    recalculan Ke y WACC hasta que D/E cambia menos que `tol`.
    """
    debt0 = float(projection.table["deuda"].iloc[0])
    de = start_de
    steps = []
    for i in range(1, max_iter + 1):
        cc = case_cost_of_capital(params, beta_unlevered, de, kd=projection.kd)
        val = value_firm(projection, cc.wacc, cc.ke_cop, growth)
        steps.append(IterationStep(i, de, cc.beta_levered, cc.ke_cop, cc.wacc, val.equity_fcff))
        if val.equity_fcff <= 0:
            raise ValueError("El patrimonio estimado no es positivo: D/E de mercado no está definido.")
        new_de = debt0 / val.equity_fcff
        if abs(new_de - de) < tol:
            break
        de = new_de
    return steps


@dataclass
class ReinvestmentCheck:
    implied_rate: float  # (CAPEX - D&A + ΔNWC) / NOPAT del último año
    required_rate: float  # g / ROIC
    consistent: bool
    message: str


def reinvestment_check(projection: Projection, growth: float, roic: float, tolerance: float = 0.02) -> ReinvestmentCheck:
    """En el estado estable, reinversión = g / ROIC; crecer sin reinvertir no es coherente."""
    if roic <= 0:
        raise ValueError("ROIC debe ser positivo.")
    last = projection.table.iloc[-1]
    implied = (last["CAPEX"] - last["depreciación"] + last["ΔNWC"]) / last["NOPAT"] if last["NOPAT"] else float("nan")
    required = growth / roic
    ok = bool(np.isfinite(implied) and abs(implied - required) <= tolerance)
    msg = (f"Reinversión implícita del último año {implied:.1%} vs. requerida g/ROIC = {required:.1%}: "
           + ("coherente." if ok else "no es coherente con el crecimiento terminal; revise CAPEX, NWC o g."))
    return ReinvestmentCheck(implied_rate=float(implied), required_rate=required, consistent=ok, message=msg)
