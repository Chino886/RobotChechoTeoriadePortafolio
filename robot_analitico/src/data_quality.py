"""
Calidad del dato y calendario (guía V2, secciones 3.1 y 3.2).

- Un hueco de varios días no se convierte en un rendimiento "diario": se
  detecta por el intervalo entre fechas y ese rendimiento se excluye.
- Precios repetidos muchos periodos seguidos (estancados) se reportan.
- Solo barras completas: la barra del día en curso no se usa como cierre
  diario antes del cierre de la bolsa.
- Moneda: con FX en COP por USD, P_COP = P_USD * FX y
  1 + R_COP = (1 + R_USD)(1 + R_FX).
"""
from datetime import datetime, time
from typing import Optional

import numpy as np
import pandas as pd

# Máximo de días calendario normales entre dos datos consecutivos por frecuencia.
MAX_GAP_DAYS = {"Diaria": 4, "Semanal": 10, "Mensual": 35}
STALE_RUN = 5  # precios idénticos consecutivos que se reportan como estancados


def calendar_report(prices: pd.DataFrame, frequency: str = "Diaria") -> pd.DataFrame:
    """
    Una fila por problema: hueco mayor al normal, fecha duplicada, precio no
    positivo o precio estancado. Vacío si no hay problemas.
    """
    limit = MAX_GAP_DAYS[frequency]
    rows = []
    if prices.index.has_duplicates:
        for d in prices.index[prices.index.duplicated()].unique():
            rows.append({"activo": "(todos)", "problema": "fecha duplicada", "desde": d, "hasta": d, "detalle": ""})
    for col in prices.columns:
        s = prices[col].dropna()
        if s.empty:
            rows.append({"activo": col, "problema": "sin datos", "desde": None, "hasta": None, "detalle": ""})
            continue
        gaps = s.index.to_series().diff().dt.days
        for end, days in gaps[gaps > limit].items():
            start = s.index[s.index.get_loc(end) - 1]
            rows.append({"activo": col, "problema": "hueco", "desde": start, "hasta": end, "detalle": f"{int(days)} días"})
        bad = s[s <= 0]
        for d in bad.index:
            rows.append({"activo": col, "problema": "precio no positivo", "desde": d, "hasta": d, "detalle": f"{bad[d]}"})
        same = (s.diff() == 0).astype(int)
        run = same.groupby((same == 0).cumsum()).cumsum()
        if (run >= STALE_RUN).any():
            end = run[run >= STALE_RUN].index[-1]
            rows.append({"activo": col, "problema": "precio estancado", "desde": None, "hasta": end,
                         "detalle": f"{int(run.max()) + 1} precios iguales seguidos"})
    return pd.DataFrame(rows, columns=["activo", "problema", "desde", "hasta", "detalle"])


def gap_safe_simple_returns(prices: pd.DataFrame, frequency: str = "Diaria") -> "tuple[pd.DataFrame, int]":
    """
    Rendimientos simples por activo sin rellenar huecos; los que cruzan un
    intervalo mayor al normal se anulan (no se llaman 'diarios'). Devuelve los
    rendimientos y cuántos se anularon por huecos.
    """
    limit = MAX_GAP_DAYS[frequency]
    out = {}
    removed = 0
    for col in prices.columns:
        s = prices[col].dropna()
        r = s.pct_change(fill_method=None)
        gaps = s.index.to_series().diff().dt.days
        mask = gaps > limit
        removed += int(mask.sum())
        r[mask] = np.nan
        out[col] = r
    return pd.DataFrame(out).reindex(prices.index).iloc[1:], removed


def drop_incomplete_last_bar(prices: pd.DataFrame, as_of: datetime, close: time, tz: str) -> pd.DataFrame:
    """
    Quita la última barra diaria si corresponde al día en curso y la bolsa aún
    no cerró (en la zona horaria de la bolsa). Así la estimación usa barras completas.
    """
    if prices.empty:
        return prices
    local_now = pd.Timestamp(as_of).tz_convert(tz) if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of).tz_localize(tz)
    last = pd.Timestamp(prices.index[-1])
    last_date = (last.tz_convert(tz) if last.tzinfo else last).date()
    if last_date == local_now.date() and local_now.time() < close:
        return prices.iloc[:-1]
    return prices


def cop_returns(returns_usd: pd.Series, fx_returns: pd.Series) -> pd.Series:
    """1 + R_COP = (1 + R_USD)(1 + R_FX), alineando fechas (sin rellenar)."""
    df = pd.concat({"usd": returns_usd, "fx": fx_returns}, axis=1).dropna()
    return ((1 + df["usd"]) * (1 + df["fx"]) - 1).rename("cop")


def prices_in_cop(prices_usd: pd.Series, fx_cop_per_usd: pd.Series) -> pd.Series:
    """P_COP = P_USD * FX con FX en COP por USD, solo en fechas comunes."""
    df = pd.concat({"p": prices_usd, "fx": fx_cop_per_usd}, axis=1).dropna()
    return (df["p"] * df["fx"]).rename("precio_COP")


def last_bar_age(index: pd.DatetimeIndex, now: Optional[datetime] = None) -> Optional[float]:
    """Días desde la última barra (antigüedad del dato histórico)."""
    if len(index) == 0:
        return None
    last = pd.Timestamp(index[-1])
    now = pd.Timestamp(now or datetime.now())
    if last.tzinfo and not now.tzinfo:
        now = now.tz_localize(last.tzinfo)
    elif now.tzinfo and not last.tzinfo:
        last = last.tz_localize(now.tzinfo)
    return (now - last).total_seconds() / 86400


# Par de Yahoo Finance con COP por 1 USD (guía 3.2: FX en COP por USD).
FX_TICKER_COP_PER_USD = "USDCOP=X"
SUPPORTED_BASES = ("USD", "COP")


def _naive_sorted(series: pd.Series) -> pd.Series:
    s = series.copy()
    if isinstance(s.index, pd.DatetimeIndex) and s.index.tz is not None:
        s.index = s.index.tz_localize(None)
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def align_fx_no_lookahead(target_index: pd.Index, fx: pd.Series) -> pd.Series:
    """
    Tipo de cambio para cada fecha de `target_index`: el último dato FX publicado en esa
    fecha o antes (nunca uno posterior). Se unen los dos calendarios, se ordena, se
    rellena hacia adelante y se vuelve a las fechas pedidas. Así, si el FX no cotizó un
    día del activo pero sí un día intermedio que el activo no tiene, se usa ese dato
    intermedio y no uno más viejo. Fechas anteriores al primer FX quedan en NaN.
    """
    fx = _naive_sorted(fx.dropna())
    target = pd.DatetimeIndex(target_index)
    if target.tz is not None:
        target = target.tz_localize(None)
    union = target.union(fx.index)
    return fx.reindex(union).sort_index().ffill().reindex(target)


def convert_prices_base(prices: pd.DataFrame, from_currency: str, to_currency: str,
                        fx_cop_per_usd: Optional[pd.Series]) -> "tuple[pd.DataFrame, int]":
    """
    Pasa una tabla de precios (columnas = activos) entre USD y COP con FX en COP por USD:
    P_COP = P_USD · FX y P_USD = P_COP / FX, con el FX alineado sin mirar al futuro. Los
    rendimientos resultantes cumplen 1 + R_COP = (1 + R_USD)(1 + R_FX).
    Devuelve (precios convertidos, filas descartadas por no tener FX previo).
    """
    src, dst = (from_currency or "").upper(), (to_currency or "").upper()
    if src == dst:
        return prices.copy(), 0
    if {src, dst} != set(SUPPORTED_BASES):
        raise ValueError(f"Conversión no soportada: {src} → {dst} (solo USD ↔ COP).")
    if fx_cop_per_usd is None or fx_cop_per_usd.dropna().empty:
        raise ValueError(f"Falta la serie {FX_TICKER_COP_PER_USD} para convertir {src} → {dst}.")
    fx = align_fx_no_lookahead(prices.index, fx_cop_per_usd)
    keep = fx.notna().to_numpy()
    factor = fx[keep].to_numpy()[:, None]
    out = prices[keep] * factor if dst == "COP" else prices[keep] / factor
    return out, int((~keep).sum())
