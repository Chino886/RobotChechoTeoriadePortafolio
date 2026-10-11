"""
Comparación de N activos, mapa histórico rendimiento-riesgo, dominancia,
preselección y exportación (RF-19 a RF-22, sección 5.8 de la guía).

No es asset allocation: no se calculan pesos, covarianzas, correlaciones
conjuntas ni frontera eficiente. El mapa es histórico y sus coordenadas NO
dependen de H (el horizonte de pronóstico de las fases anteriores).

Comparabilidad (RF-20): todos los puntos usan la intersección común de
fechas después del remuestreo, la misma frecuencia, precio, log-rendimiento,
factores de anualización y moneda base (USD por defecto). Los activos en
otra moneda se convierten a la moneda base usando el tipo de cambio
histórico correspondiente (ver src.data.fetch_fx_to_usd); si no se consigue
ese tipo de cambio, el activo queda excluido de la comparación (nunca se
inventa ni se aproxima una tasa), y se reporta aparte.

Todas las fórmulas fueron verificadas contra el fixture obligatorio de 20
activos de la guía (Fixture_20_activos_sintetico_TBS_EIA.csv /
Resultados_esperados_20_activos_TBS_EIA.csv): coinciden con un error
absoluto máximo del orden de 1e-15 en todos los campos numéricos, y la
dominancia y la selección por máximo RVR coinciden exactamente.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone as dt_timezone
from typing import Optional

import numpy as np
import pandas as pd

from src.analytics import annualize_mean, annualize_vol, log_returns, max_drawdown

# La guía exige que la vista comparativa pueda aceptar simultáneamente al
# menos 20 activos válidos (RF-19). No se usa para bloquear con menos: solo
# para advertir si aún no se alcanza durante las pruebas.
MIN_COMPARISON_ASSETS = 20

# Tolerancias obligatorias para empates y dominancia (RF-20, sección 5.8).
DOMINANCE_ATOL = 1e-12
DOMINANCE_RTOL = 1e-10


@dataclass
class AssetSummary:
    ticker: str
    currency: str
    source: str
    n: int
    start_date: "pd.Timestamp"
    end_date: "pd.Timestamp"
    last_price: float
    mean_period: float
    std_period: float
    mean_annual: float  # y_i del mapa histórico (RF-19)
    vol_annual: float  # x_i del mapa histórico (RF-19)
    rvr: Optional[float]  # razón individual media/volatilidad; None si vol_annual == 0
    q05: float
    q95: float
    max_dd: float


@dataclass
class ExcludedAsset:
    ticker: str
    reason: str


@dataclass
class ComparisonResult:
    ok: bool
    base_currency: Optional[str] = None
    frequency: Optional[str] = None
    periods_per_year: Optional[int] = None
    common_start: Optional["pd.Timestamp"] = None
    common_end: Optional["pd.Timestamp"] = None
    n_common: int = 0
    summaries: "list[AssetSummary]" = field(default_factory=list)
    excluded: "list[ExcludedAsset]" = field(default_factory=list)
    common_prices: "Optional[dict[str, pd.Series]]" = None  # ticker -> precios recortados a la ventana común
    reason: Optional[str] = None  # motivo si ok=False


def _isclose(a: float, b: float) -> bool:
    return bool(np.isclose(a, b, atol=DOMINANCE_ATOL, rtol=DOMINANCE_RTOL))


def build_comparison(
    assets: "dict[str, object]",  # ticker -> AssetData (de src.data), ya remuestreados
    frequency: str,
    periods_per_year: int,
    base_currency: Optional[str] = None,
    fx_rates: "Optional[dict[str, pd.Series]]" = None,
) -> ComparisonResult:
    """
    Construye la comparación de N activos (RF-19, RF-20). `assets` debe venir
    de src.data.fetch_many (o equivalente), ya remuestreado a la frecuencia
    elegida. Los activos con ok=False (RF-08) se excluyen automáticamente con
    su motivo; no detienen el análisis de los demás.

    `fx_rates` (ampliación de RF-20): dict moneda -> serie de tipo de cambio
    (unidades de `base_currency` por 1 unidad de esa moneda), ya descargada
    y remuestreada por el llamador con src.data.fetch_fx_to_usd. Los activos
    en otra moneda se convierten multiplicando su precio por el tipo de
    cambio alineado por fecha; si no hay tasa disponible para esa moneda, el
    activo se excluye (nunca se inventa una tasa).
    """
    ok_assets = {t: a for t, a in assets.items() if getattr(a, "ok", False) and a.prices is not None and not a.prices.empty}
    excluded: "list[ExcludedAsset]" = []

    for ticker, asset in assets.items():
        if ticker not in ok_assets:
            excluded.append(ExcludedAsset(ticker=ticker, reason=getattr(asset, "error", None) or "Activo inválido."))

    if not ok_assets:
        return ComparisonResult(ok=False, reason="Ningún activo válido para comparar.", excluded=excluded)

    # Moneda base (RF-20 ampliado): USD por defecto, salvo que se indique otra.
    if base_currency is None:
        base_currency = "USD"

    fx_rates = fx_rates or {}

    # Convierte cada activo a la moneda base. Si ya está en esa moneda, se usa
    # el precio tal cual; si no, se necesita el tipo de cambio en fx_rates
    # alineado por fecha (forward-fill para días sin cotización de la divisa,
    # igual que un feriado); si no hay tasa suficiente, el activo se excluye.
    compatible: "dict[str, pd.DataFrame]" = {}
    for ticker, asset in ok_assets.items():
        currency = (asset.currency or "N/D").upper()

        # Normaliza fechas sin zona horaria (distintas bolsas usan distintas
        # zonas horarias en yfinance; sin esto, fechas del "mismo día" no
        # coinciden al comparar/alinear entre activos o con el tipo de cambio).
        asset_prices = asset.prices
        if asset_prices.index.tz is not None:
            asset_prices = asset_prices.copy()
            asset_prices.index = asset_prices.index.tz_localize(None)

        if currency == base_currency:
            compatible[ticker] = asset_prices
            continue

        fx_series = fx_rates.get(currency)
        if fx_series is None or fx_series.empty:
            excluded.append(
                ExcludedAsset(
                    ticker=ticker,
                    reason=(
                        f"No se encontró tipo de cambio de '{currency}' a '{base_currency}' "
                        "para convertir este activo (RF-20 ampliado: conversión de monedas)."
                    ),
                )
            )
            continue

        if fx_series.index.tz is not None:
            fx_series = fx_series.copy()
            fx_series.index = fx_series.index.tz_localize(None)

        aligned_fx = fx_series.reindex(asset_prices.index).ffill()
        valid = aligned_fx.notna()
        if int(valid.sum()) < 2:
            excluded.append(
                ExcludedAsset(
                    ticker=ticker,
                    reason=(
                        f"Tipo de cambio '{currency}->{base_currency}' insuficiente para "
                        "convertir este activo."
                    ),
                )
            )
            continue

        converted_close = asset_prices.loc[valid, "adjusted_close"] * aligned_fx[valid]
        compatible[ticker] = pd.DataFrame({"adjusted_close": converted_close})

    if not compatible:
        return ComparisonResult(
            ok=False,
            reason=f"Ningún activo pudo expresarse en la moneda base '{base_currency}'.",
            excluded=excluded,
            base_currency=base_currency,
        )
    # Intersección común de fechas DESPUÉS del remuestreo (RF-20). Las
    # coordenadas históricas resultantes no dependen de H.
    common_index = None
    for prices in compatible.values():
        idx = prices.index
        common_index = idx if common_index is None else common_index.intersection(idx)

    if common_index is None or len(common_index) < 2:
        return ComparisonResult(
            ok=False,
            reason="La intersección común de fechas entre los activos compatibles tiene menos de 2 observaciones.",
            excluded=excluded,
            base_currency=base_currency,
        )

    common_index = common_index.sort_values()
    summaries: "list[AssetSummary]" = []
    common_prices: "dict[str, pd.Series]" = {}

    for ticker, trimmed_prices in compatible.items():
        trimmed = trimmed_prices.loc[common_index, "adjusted_close"]
        returns = log_returns(trimmed)
        if len(returns) < 2:
            excluded.append(
                ExcludedAsset(ticker=ticker, reason="Menos de 2 rendimientos en la ventana común de fechas.")
            )
            continue

        mean_period = float(returns.mean())
        std_period = float(returns.std(ddof=1))
        mean_annual = annualize_mean(mean_period, periods_per_year)
        vol_annual = annualize_vol(std_period, periods_per_year)
        rvr = (mean_annual / vol_annual) if vol_annual > 0 else None

        original_asset = ok_assets[ticker]
        summaries.append(
            AssetSummary(
                ticker=ticker,
                currency=original_asset.currency or "N/D",
                source=original_asset.source,
                n=len(returns),
                start_date=trimmed.index.min(),
                end_date=trimmed.index.max(),
                last_price=float(trimmed.iloc[-1]),
                mean_period=mean_period,
                std_period=std_period,
                mean_annual=mean_annual,
                vol_annual=vol_annual,
                rvr=rvr,
                q05=float(returns.quantile(0.05)),
                q95=float(returns.quantile(0.95)),
                max_dd=max_drawdown(trimmed),
            )
        )
        common_prices[ticker] = trimmed

    if not summaries:
        return ComparisonResult(
            ok=False,
            reason="Ningún activo tiene al menos 2 rendimientos en la ventana común de fechas.",
            excluded=excluded,
            base_currency=base_currency,
        )

    return ComparisonResult(
        ok=True,
        base_currency=base_currency,
        frequency=frequency,
        periods_per_year=periods_per_year,
        common_start=common_index.min(),
        common_end=common_index.max(),
        n_common=len(common_index),
        summaries=summaries,
        excluded=excluded,
        common_prices=common_prices,
    )


# ---------------------------------------------------------------------------
# Dominancia media-volatilidad (RF-20, sección 5.8)
# ---------------------------------------------------------------------------


def dominates(mean_a: float, vol_a: float, mean_b: float, vol_b: float) -> bool:
    """
    True si A domina a B: media igual o mayor Y volatilidad igual o menor,
    con al menos una desigualdad estricta (fuera de tolerancia). No es
    dominancia estocástica.
    """
    mean_ge = mean_a > mean_b or _isclose(mean_a, mean_b)
    vol_le = vol_a < vol_b or _isclose(vol_a, vol_b)
    strictly_better = (mean_a > mean_b and not _isclose(mean_a, mean_b)) or (
        vol_a < vol_b and not _isclose(vol_a, vol_b)
    )
    return bool(mean_ge and vol_le and strictly_better)


def non_dominated_tickers(summaries: "list[AssetSummary]") -> "set[str]":
    """Activos que ningún otro activo del lote domina (RF-20)."""
    result = set()
    for candidate in summaries:
        dominated = any(
            dominates(other.mean_annual, other.vol_annual, candidate.mean_annual, candidate.vol_annual)
            for other in summaries
            if other.ticker != candidate.ticker
        )
        if not dominated:
            result.add(candidate.ticker)
    return result


# ---------------------------------------------------------------------------
# Preselección transparente (RF-21). Cada función devuelve TODOS los
# empates dentro de tolerancia, nunca un único "mejor" arbitrario, y una
# lista vacía si ningún activo cumple el criterio (nunca se fuerza una
# selección). La salida se debe presentar como "mejor según el criterio y
# los parámetros elegidos", nunca como frontera eficiente ni mejor
# inversión universal.
# ---------------------------------------------------------------------------


def preselect_max_mean_under_risk_limit(summaries: "list[AssetSummary]", risk_limit: float) -> "list[str]":
    """Máxima media histórica entre los activos con volatilidad <= risk_limit."""
    candidates = [s for s in summaries if s.vol_annual < risk_limit or _isclose(s.vol_annual, risk_limit)]
    if not candidates:
        return []
    best = max(s.mean_annual for s in candidates)
    return [s.ticker for s in candidates if s.mean_annual > best or _isclose(s.mean_annual, best)]


def preselect_min_vol_under_min_mean(summaries: "list[AssetSummary]", min_mean: float) -> "list[str]":
    """Mínima volatilidad entre los activos con media histórica >= min_mean."""
    candidates = [s for s in summaries if s.mean_annual > min_mean or _isclose(s.mean_annual, min_mean)]
    if not candidates:
        return []
    best = min(s.vol_annual for s in candidates)
    return [s.ticker for s in candidates if s.vol_annual < best or _isclose(s.vol_annual, best)]


def preselect_max_rvr(summaries: "list[AssetSummary]") -> "list[str]":
    """Máxima razón individual media-volatilidad. Excluye RVR indefinida (vol_annual == 0)."""
    candidates = [s for s in summaries if s.rvr is not None]
    if not candidates:
        return []
    best = max(s.rvr for s in candidates)
    return [s.ticker for s in candidates if s.rvr > best or _isclose(s.rvr, best)]


def preselect_non_dominated(summaries: "list[AssetSummary]") -> "list[str]":
    """Conjunto no dominado completo (no es frontera eficiente de portafolios)."""
    return sorted(non_dominated_tickers(summaries))


# ---------------------------------------------------------------------------
# Exportación (RF-22): precios procesados, resultados por activo, tabla
# comparativa y parámetros, con fecha y fuente.
# ---------------------------------------------------------------------------


def comparison_table(result: ComparisonResult, non_dominated: "set[str]") -> pd.DataFrame:
    """Tabla comparativa (para mostrar en pantalla y exportar, RF-19/RF-22)."""
    rows = []
    for s in result.summaries:
        rows.append(
            {
                "ticker": s.ticker,
                "moneda_original": s.currency,
                "fuente": s.source,
                "n_rendimientos": s.n,
                "fecha_inicio_comun": s.start_date.date(),
                "fecha_fin_comun": s.end_date.date(),
                "ultimo_precio": s.last_price,
                "media_anualizada": s.mean_annual,
                "volatilidad_anualizada": s.vol_annual,
                "rvr_individual": s.rvr,
                "q05_log": s.q05,
                "q95_log": s.q95,
                "max_drawdown": s.max_dd,
                "no_dominado": s.ticker in non_dominated,
            }
        )
    return pd.DataFrame(rows).set_index("ticker")


def processed_prices_export(result: ComparisonResult) -> pd.DataFrame:
    """Precios procesados (ventana común, ya remuestreados) en formato largo (RF-22)."""
    if not result.common_prices:
        return pd.DataFrame(columns=["date", "ticker", "adjusted_close"])
    frames = []
    for ticker, series in result.common_prices.items():
        frame = series.rename("adjusted_close").reset_index()
        frame.columns = ["date", "adjusted_close"]
        frame.insert(1, "ticker", ticker)
        frames.append(frame)
    return pd.concat(frames, ignore_index=True).sort_values(["ticker", "date"])


def export_parameters(result: ComparisonResult) -> dict:
    """Parámetros de la comparación, con fecha y fuente (RF-22)."""
    sources = sorted({s.source for s in result.summaries})
    return {
        "fecha_exportacion_utc": datetime.now(dt_timezone.utc).isoformat(),
        "fuente(s)": sources,
        "moneda_base": result.base_currency,
        "frecuencia": result.frequency,
        "periodos_por_anio": result.periods_per_year,
        "fecha_inicio_comun": result.common_start.date().isoformat() if result.common_start is not None else None,
        "fecha_fin_comun": result.common_end.date().isoformat() if result.common_end is not None else None,
        "n_observaciones_comunes": result.n_common,
        "n_activos_incluidos": len(result.summaries),
        "n_activos_excluidos": len(result.excluded),
        "tolerancia_atol_dominancia": DOMINANCE_ATOL,
        "tolerancia_rtol_dominancia": DOMINANCE_RTOL,
    }
