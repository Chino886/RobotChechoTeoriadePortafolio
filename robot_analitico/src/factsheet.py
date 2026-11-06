"""
Ficha técnica de una cartera simulada, con la estructura de la ficha técnica de los Fondos
de Inversión Colectiva de la Superintendencia Financiera de Colombia (Decreto 1242 de 2013;
Circular Básica Jurídica, Parte III, Título VI, Capítulo III, Anexo 6).

Es una **simulación académica**: la cartera no es un FIC, no tiene sociedad administradora,
custodio, calificación, comisiones ni participaciones. Esos campos se muestran como «No
aplica» para respetar la estructura sin inventar datos.

Rentabilidad histórica efectiva anual por ventana (último mes, 6 meses, año corrido, último
año, 2 y 3 años): con el valor de la cartera V (pesos constantes, rebalanceo cada periodo),
rent_EA = (V_fin / V_inicio)^(365 / días) − 1. Volatilidad histórica anualizada de la misma
ventana: σ(R_p)·√m. Una ventana sin historia suficiente queda en N/D.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

NOT_APPLICABLE = "No aplica (simulación académica, no es un FIC)"
WINDOWS = [("Último mes", 30), ("Últimos 6 meses", 182), ("Año corrido", None), ("Último año", 365),
           ("Últimos 2 años", 730), ("Últimos 3 años", 1095)]


@dataclass
class FactSheet:
    name: str
    as_of: Optional[date]
    general: "list[tuple[str, str]]"
    policy: "list[tuple[str, str]]"
    composition_asset: pd.Series  # pesos ordenados de mayor a menor
    composition_currency: pd.Series
    composition_sector: pd.Series
    top_holdings: pd.Series
    performance: pd.DataFrame  # filas = ventanas; columnas = rentabilidad EA, volatilidad
    risk: "list[tuple[str, str]]"
    value_path: Optional[pd.Series]  # evolución de 100.000 invertidos
    not_applicable: "list[str]" = field(default_factory=list)


def value_path(port_returns: pd.Series, start_value: float = 100_000.0) -> pd.Series:
    r = port_returns.dropna()
    return start_value * (1 + r).cumprod()


def window_stats(port_returns: pd.Series, m: int) -> pd.DataFrame:
    """Rentabilidad EA y volatilidad anualizada por ventana de la ficha (N/D si falta historia)."""
    r = port_returns.dropna()
    rows = {}
    if r.empty:
        return pd.DataFrame({"rentabilidad EA": [np.nan] * len(WINDOWS), "volatilidad anual": [np.nan] * len(WINDOWS)},
                            index=[w for w, _ in WINDOWS])
    v = (1 + r).cumprod()
    v = pd.concat([pd.Series([1.0], index=[r.index[0] - pd.Timedelta(days=1)]), v])  # valor antes del primer rendimiento
    end = v.index[-1]
    for label, days in WINDOWS:
        start_target = pd.Timestamp(end.year, 1, 1) - pd.Timedelta(days=1) if days is None else end - pd.Timedelta(days=days)
        if v.index[0] > start_target:  # no hay historia que cubra la ventana
            rows[label] = (np.nan, np.nan)
            continue
        start = v.index[v.index <= start_target][-1]
        span = (end - start).days
        ea = (v[end] / v[start]) ** (365.0 / span) - 1 if span > 0 else np.nan
        win = r[(r.index > start) & (r.index <= end)]
        vol = win.std(ddof=1) * np.sqrt(m) if len(win) >= 2 else np.nan
        rows[label] = (ea, vol)
    return pd.DataFrame(rows, index=["rentabilidad EA", "volatilidad anual"]).T


def max_drawdown(port_returns: pd.Series) -> float:
    v = (1 + port_returns.dropna()).cumprod()
    return float((v / v.cummax() - 1).min()) if len(v) else float("nan")


def build_factsheet(name: str, weights: pd.Series, returns: Optional[pd.DataFrame], m: int, currency: Optional[str],
                    objective: str, constraints: str, rf_annual: float, team: str, institution: str,
                    asset_currency: Optional["dict[str, str]"] = None, sectors: Optional["dict[str, str]"] = None,
                    extra_risk: Optional["list[tuple[str, str]]"] = None) -> FactSheet:
    w = weights.astype(float)
    w = w[w.abs() > 1e-10].sort_values(ascending=False)
    port = None if returns is None else returns[w.index].mul(w, axis=1).sum(axis=1, min_count=len(w))
    as_of = None if port is None or port.dropna().empty else port.dropna().index[-1].date()
    general = [
        ("Nombre", name),
        ("Tipo", "Cartera simulada con fines académicos (no es un Fondo de Inversión Colectiva)"),
        ("Fecha de corte", str(as_of) if as_of else "N/D (parámetros dados, sin serie de precios)"),
        ("Gestor (responsable del análisis)", f"{team} · {institution}"),
        ("Moneda de la cartera", currency or "N/D (datos sin moneda: caso docente o sintéticos)"),
        ("Inicio de la serie", str(port.dropna().index[0].date()) if port is not None and not port.dropna().empty else "N/D"),
        ("Número de activos con peso", str(len(w))),
    ]
    policy = [
        ("Objetivo", objective),
        ("Restricciones", constraints),
        ("Tasa libre de riesgo usada (EA)", f"{rf_annual:.2%}"),
        ("Posición corta (suma de pesos negativos)", f"{w[w < 0].sum():.2%}"),
        ("Rebalanceo supuesto", "Pesos constantes, rebalanceados cada periodo, sin costos (simulación)"),
    ]
    by_ccy = pd.Series(dtype=float)
    if asset_currency:
        by_ccy = w.groupby(lambda a: asset_currency.get(a, "N/D")).sum().sort_values(ascending=False)
    elif currency:
        by_ccy = pd.Series({currency: float(w.sum())})
    by_sector = pd.Series(dtype=float)
    if sectors:
        by_sector = w.groupby(lambda a: sectors.get(a) or "Sin sector asignado").sum().sort_values(ascending=False)
    perf = window_stats(port, m) if port is not None else window_stats(pd.Series(dtype=float), m)
    risk = []
    if port is not None and len(port.dropna()) >= 2:
        pr = port.dropna()
        q = float(-np.quantile(pr, 0.05))
        tail = pr[-pr >= q]
        risk = [
            ("Volatilidad anual de toda la muestra", f"{pr.std(ddof=1) * np.sqrt(m):.2%}"),
            ("VaR histórico 95 % (un periodo)", f"{max(0.0, q):.2%}"),
            ("Pérdida esperada (ES) 95 % (un periodo)", f"{float(-tail.mean()):.2%}" if len(tail) else "N/D"),
            ("Máxima caída (drawdown)", f"{max_drawdown(pr):.2%}"),
        ]
    risk += list(extra_risk or [])
    return FactSheet(
        name=name, as_of=as_of, general=general, policy=policy, composition_asset=w,
        composition_currency=by_ccy, composition_sector=by_sector, top_holdings=w.abs().sort_values(ascending=False).head(10),
        performance=perf, risk=risk, value_path=value_path(port) if port is not None else None,
        not_applicable=["Valor del fondo y unidades en circulación", "Calificación del fondo",
                        "Comisiones, remuneración y gastos", "Inversión mínima, preaviso y pacto de permanencia",
                        "Custodio, revisor fiscal y defensor del consumidor financiero",
                        "Información de plazos y duración (cartera de renta variable)"],
    )


def to_markdown(fs: FactSheet) -> str:
    def table(rows):
        return "\n".join(["| Campo | Valor |", "|---|---|"] + [f"| {k} | {v} |" for k, v in rows])

    def weights_table(s, title):
        if s.empty:
            return f"_{title}: N/D_"
        return "\n".join([f"| {title} | Peso |", "|---|---:|"] + [f"| {k} | {v:.2%} |" for k, v in s.items()])

    perf = "\n".join(["| Ventana | Rentabilidad EA | Volatilidad anual |", "|---|---:|---:|"] + [
        f"| {k} | {'N/D' if pd.isna(r['rentabilidad EA']) else format(r['rentabilidad EA'], '.2%')} | "
        f"{'N/D' if pd.isna(r['volatilidad anual']) else format(r['volatilidad anual'], '.2%')} |"
        for k, r in fs.performance.iterrows()])
    parts = [
        f"# Ficha técnica — {fs.name}",
        "_Estructura de la ficha técnica de FIC de la Superintendencia Financiera de Colombia (Decreto 1242 de 2013; "
        "Circular Básica Jurídica, Anexo 6). Simulación académica: no es un fondo ni una oferta de inversión._",
        "## 1. Características", table(fs.general),
        "## 2. Política de inversión", table(fs.policy),
        "## 3. Rentabilidad y volatilidad histórica", perf,
        "## 4. Composición del portafolio", weights_table(fs.composition_asset, "Por activo"),
        weights_table(fs.composition_currency, "Por moneda"), weights_table(fs.composition_sector, "Por sector"),
        "## 5. Principales inversiones", weights_table(fs.top_holdings, "Activo (|peso|)"),
        "## 6. Riesgo", table(fs.risk) if fs.risk else "_N/D: sin serie de rendimientos._",
        "## 7. Campos de la ficha oficial que no aplican", "\n".join(f"- {x}: {NOT_APPLICABLE}" for x in fs.not_applicable),
        "## Advertencia",
        "Resultado de una simulación académica con datos históricos. Rentabilidades pasadas no garantizan "
        "rentabilidades futuras. No constituye asesoría financiera ni recomendación de inversión, y no ejecuta órdenes.",
    ]
    return "\n\n".join(parts)
