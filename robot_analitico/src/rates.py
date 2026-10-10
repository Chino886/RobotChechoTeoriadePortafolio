"""
Tasas de bonos soberanos por país, vía la API de FRED (Federal Reserve
Economic Data, Banco de la Reserva Federal de St. Louis). Es una fuente de
datos complementaria y distinta a yfinance, pensada como referencia
macroeconómica de contexto (ej. para hablar de tasa libre de riesgo por
país) — no entra en la comparación de activos, la dominancia ni la
preselección del resto del sistema.

Nunca se adivina ni se memoriza el código de serie de un país: siempre se
usa el buscador oficial de FRED (fred/series/search) para encontrar la
serie real, y se muestra el título exacto que FRED devuelve para que quede
claro cuál serie se está usando.
"""
import pandas as pd
import requests

FRED_BASE_URL = "https://api.stlouisfed.org/fred"


def search_bond_series(api_key: str, country_query: str, limit: int = 5) -> "list[dict]":
    """
    Busca en FRED series relacionadas con el rendimiento de bonos soberanos
    a 10 años del país indicado. Devuelve la lista tal cual la reporta FRED
    (id, title, frequency, units, etc.), sin completar ni inventar campos.
    """
    params = {
        "search_text": f"{country_query} 10-Year government bond yield",
        "api_key": api_key,
        "file_type": "json",
        "limit": limit,
        "order_by": "popularity",
        "sort_order": "desc",
    }
    response = requests.get(f"{FRED_BASE_URL}/series/search", params=params, timeout=15)
    response.raise_for_status()
    return response.json().get("seriess", [])


def fetch_bond_series(api_key: str, series_id: str, start_date, end_date) -> pd.Series:
    """
    Descarga el histórico de una serie de FRED ya elegida por su series_id
    real (obtenido con search_bond_series). Descarta los valores '.' que
    FRED usa para marcar datos faltantes — nunca los imputa ni los aproxima,
    igual que src.data con los precios de yfinance.
    """
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": pd.Timestamp(start_date).strftime("%Y-%m-%d"),
        "observation_end": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
    }
    response = requests.get(f"{FRED_BASE_URL}/series/observations", params=params, timeout=15)
    response.raise_for_status()
    rows = [
        (obs["date"], obs["value"])
        for obs in response.json().get("observations", [])
        if obs["value"] != "."
    ]
    if not rows:
        return pd.Series(dtype=float)
    dates, values = zip(*rows)
    series = pd.Series([float(v) for v in values], index=pd.to_datetime(dates))
    series.index.name = "date"
    return series
