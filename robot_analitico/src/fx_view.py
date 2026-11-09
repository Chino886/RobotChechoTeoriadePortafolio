"""
Conversión de monedas visible (Comparación y Datos del activo).

No reescribe la conversión: usa src.data.fetch_fx_to_usd (par directo o invertido de Yahoo
Finance) y src.data_quality.align_fx_no_lookahead (último dato FX publicado en o antes de cada
fecha). Este módulo solo:
- arma la serie «moneda base por 1 unidad de la moneda del activo» para base USD o COP;
- ajusta las monedas que Yahoo da en subunidades (GBp = peniques: ÷ 100 → GBP);
- deja escrito qué par se usó, si se invirtió, cuándo se consultó y las tasas de la ventana,
  para mostrarlo en pantalla.

Fórmulas (guía): P_USD = P_COP / (COP por USD) y 1 + R_USD = (1 + R_COP)(1 + R_FX).
Nunca se inventa ni se rellena una tasa: si falta, la serie queda vacía y el activo se excluye.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd

from src.data import fetch_asset_data, fetch_fx_to_usd
from src.data_quality import FX_TICKER_COP_PER_USD, align_fx_no_lookahead

BASES = ("USD", "COP")

# Monedas que Yahoo publica en subunidades: código tal como llega → (moneda, divisor).
MINOR_UNITS = {"GBp": ("GBP", 100.0), "GBX": ("GBP", 100.0), "ZAc": ("ZAR", 100.0), "ZAC": ("ZAR", 100.0),
               "ILA": ("ILS", 100.0)}


@dataclass
class FxLeg:
    """Tipo de cambio de una moneda a la base: serie = unidades de `base` por 1 unidad de `currency`."""
    currency: str
    base: str
    ok: bool
    series: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))
    pairs: str = ""  # descripción del par o pares de Yahoo usados
    fetched_at: str = ""
    error: Optional[str] = None


def normalize_minor_units(asset):
    """
    Si el activo viene en subunidades (p. ej. GBp, peniques), devuelve una copia con el precio
    dividido entre 100 y la moneda principal (GBP), más una nota. Si no, devuelve (asset, None).
    """
    raw = (getattr(asset, "currency", None) or "").strip()
    if raw not in MINOR_UNITS or getattr(asset, "prices", None) is None:
        return asset, None
    major, div = MINOR_UNITS[raw]
    out = copy.copy(asset)
    out.prices = asset.prices.copy()
    out.prices["adjusted_close"] = out.prices["adjusted_close"] / div
    out.currency = major
    return out, f"{asset.ticker}: Yahoo da el precio en {raw} (subunidad); se divide entre {div:g} para pasarlo a {major}."


def _naive(s: pd.Series) -> pd.Series:
    s = s.dropna().sort_index()
    if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
        s = s.copy()
        s.index = s.index.tz_localize(None)
    return s


def _pair_text(res) -> str:
    pair = getattr(res, "fx_pair", None) or getattr(res, "ticker", "?")
    if getattr(res, "fx_inverted", False):
        cur = pair[3:6]
        return f"{pair} (invertido: 1 / tasa, {cur}→USD)"
    return pair


def fx_to_base(currency: str, base: str, start, end, *, now: str = "",
               fetch_fx: Optional[Callable] = None, fetch: Optional[Callable] = None) -> FxLeg:
    """
    Serie de `base` por 1 `currency` entre start y end.
    - Base USD: el par de fetch_fx_to_usd (directo, o invertido si Yahoo solo publica USDxxx=X).
    - Base COP y activo en USD: USDCOP=X (COP por USD) tal cual.
    - Base COP y otra moneda: cruce (USD por moneda) × (COP por USD), cada uno con su último dato
      publicado en o antes de cada fecha (sin mirar al futuro).
    """
    fetch_fx = fetch_fx or fetch_fx_to_usd
    fetch = fetch or fetch_asset_data
    cur, base = (currency or "").strip().upper(), (base or "USD").strip().upper()
    if not cur or cur == "N/D":
        return FxLeg(cur or "N/D", base, False, fetched_at=now, error="El proveedor no informó la moneda del activo.")
    if cur == base:
        return FxLeg(cur, base, False, fetched_at=now, error="No necesita conversión.")

    if base == "USD":
        res = fetch_fx(cur, start, end)
        if not res.ok or res.prices is None or res.prices.empty:
            return FxLeg(cur, base, False, fetched_at=now, error=res.error or "sin datos de tipo de cambio")
        return FxLeg(cur, base, True, _naive(res.prices["adjusted_close"]), _pair_text(res), now)

    if base != "COP":
        return FxLeg(cur, base, False, fetched_at=now, error=f"Moneda base no soportada: {base} (solo USD o COP).")

    cop = fetch(FX_TICKER_COP_PER_USD, start, end)
    if not cop.ok or cop.prices is None or cop.prices.empty:
        return FxLeg(cur, base, False, fetched_at=now,
                     error=cop.error or f"sin datos de {FX_TICKER_COP_PER_USD} (COP por USD)")
    cop_per_usd = _naive(cop.prices["adjusted_close"])
    if cur == "USD":
        return FxLeg(cur, base, True, cop_per_usd, f"{FX_TICKER_COP_PER_USD} (COP por 1 USD)", now)

    res = fetch_fx(cur, start, end)
    if not res.ok or res.prices is None or res.prices.empty:
        return FxLeg(cur, base, False, fetched_at=now, error=res.error or "sin datos de tipo de cambio")
    usd_per_cur = _naive(res.prices["adjusted_close"])
    idx = usd_per_cur.index.union(cop_per_usd.index)
    cross = (align_fx_no_lookahead(idx, usd_per_cur) * align_fx_no_lookahead(idx, cop_per_usd)).dropna()
    return FxLeg(cur, base, True, cross, f"{_pair_text(res)} × {FX_TICKER_COP_PER_USD} (cruce vía USD)", now)


def rate_on(leg: FxLeg, when) -> Optional[float]:
    """Tasa usada en esa fecha: el último dato publicado en o antes (la misma regla de la conversión)."""
    if not leg.ok or leg.series.empty:
        return None
    v = align_fx_no_lookahead(pd.DatetimeIndex([pd.Timestamp(when)]), leg.series).iloc[0]
    return None if pd.isna(v) else float(v)


def human_rate(rate: Optional[float], currency: str, base: str) -> str:
    """«1 USD = 3.238,38 COP» o «1 EUR = 1,1228 USD»: la forma fácil de leer la tasa."""
    if rate is None or rate <= 0:
        return "N/D"
    if rate < 1:
        return f"1 {base} = {1 / rate:,.2f} {currency}"
    return f"1 {currency} = {rate:,.4f} {base}"


def conversion_rows(result, assets: dict, legs: "dict[str, FxLeg]", notes: "dict[str, str]" = None) -> "list[dict]":
    """
    Una fila por activo convertido de la comparación: moneda original, par usado, tasa del primer y
    del último día de la ventana común, hora de consulta y precio original vs. convertido del último día.
    `assets` son los activos ya normalizados (subunidades) que entraron a build_comparison.
    """
    rows = []
    notes = notes or {}
    base = (getattr(result, "base_currency", None) or "USD").upper()
    for s in getattr(result, "summaries", []) or []:
        asset = assets.get(s.ticker)
        cur = (getattr(asset, "currency", None) or "N/D").upper()
        if asset is None or cur == base or cur not in legs:
            continue
        leg = legs[cur]
        first, last = result.common_start, result.common_end
        r0, r1 = rate_on(leg, first), rate_on(leg, last)
        prices = _naive(asset.prices["adjusted_close"])
        p_orig = float(prices.loc[:last].iloc[-1]) if not prices.loc[:last].empty else None
        p_conv = float(result.common_prices[s.ticker].iloc[-1]) if result.common_prices else None
        rows.append({
            "Activo": s.ticker,
            "Moneda original": cur + (" (de subunidad ÷ 100)" if s.ticker in notes else ""),
            "Par usado": leg.pairs,
            "Tasa unidad": f"{base} por 1 {cur}",
            "Tasa primer día": r0, "Fecha primer día": pd.Timestamp(first).date(),
            "Tasa último día": r1, "Fecha último día": pd.Timestamp(last).date(),
            "Equivale a (último día)": human_rate(r1, cur, base),
            "Consulta": leg.fetched_at,
            "Precio original (último día)": p_orig,
            "Precio convertido (último día)": p_conv,
            "Moneda base": base,
        })
    return rows


def returns_identity(price_local: pd.Series, fx_base_per_local: pd.Series) -> pd.DataFrame:
    """Comprobación de la guía: 1 + R_base = (1 + R_local)(1 + R_FX), con el FX alineado sin look-ahead."""
    p = _naive(price_local)
    fx = align_fx_no_lookahead(p.index, fx_base_per_local)
    keep = fx.notna()
    p, fx = p[keep], fx[keep]
    conv = p * fx
    return pd.DataFrame({"R_local": p.pct_change(), "R_FX": fx.pct_change(), "R_base": conv.pct_change()}).dropna()
