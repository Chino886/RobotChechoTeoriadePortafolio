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


# Serie mensual de la OCDE en FRED: "Interest Rates: Long-Term Government Bond Yields:
# 10-Year: Main (Including Benchmark) for <país>". El código no se adivina: la lista
# de países se arma preguntándole a FRED qué series existen con ese prefijo.
LONG_TERM_PREFIX = "IRLTLT01"
MONTHLY_SUFFIX = "M156N"

# Nombres en español para mostrar; si FRED trae un país que no está aquí, se muestra en inglés.
COUNTRY_ES = {
    "Australia": "Australia", "Austria": "Austria", "Belgium": "Bélgica", "Brazil": "Brasil",
    "Bulgaria": "Bulgaria", "Canada": "Canadá", "Chile": "Chile", "China": "China", "Colombia": "Colombia",
    "Costa Rica": "Costa Rica", "Croatia": "Croacia", "Cyprus": "Chipre", "Czechia": "Chequia",
    "Czech Republic": "Chequia", "Denmark": "Dinamarca", "Estonia": "Estonia",
    "Euro Area (19 Countries)": "Zona euro (19 países)", "Euro area (19 countries)": "Zona euro (19 países)",
    "Euro Area": "Zona euro", "Finland": "Finlandia", "France": "Francia", "Germany": "Alemania",
    "Greece": "Grecia", "Hungary": "Hungría", "Iceland": "Islandia", "India": "India", "Indonesia": "Indonesia",
    "Ireland": "Irlanda", "Israel": "Israel", "Italy": "Italia", "Japan": "Japón", "Korea": "Corea del Sur",
    "Republic of Korea": "Corea del Sur", "Latvia": "Letonia", "Lithuania": "Lituania", "Luxembourg": "Luxemburgo",
    "Malta": "Malta", "Mexico": "México", "Netherlands": "Países Bajos", "New Zealand": "Nueva Zelanda",
    "Norway": "Noruega", "Poland": "Polonia", "Portugal": "Portugal", "Romania": "Rumania", "Russia": "Rusia",
    "Russian Federation": "Rusia", "Slovak Republic": "Eslovaquia", "Slovakia": "Eslovaquia",
    "Slovenia": "Eslovenia", "South Africa": "Sudáfrica", "Spain": "España", "Sweden": "Suecia",
    "Switzerland": "Suiza", "Turkey": "Turquía", "Türkiye": "Turquía", "United Kingdom": "Reino Unido",
    "United States": "Estados Unidos",
}


def _country_from_title(title: str) -> str:
    return title.rsplit(" for ", 1)[-1].strip() if " for " in title else title.strip()


def list_long_term_yield_countries(api_key: str, http=requests) -> "list[dict]":
    """
    Países que de verdad tienen en FRED la serie mensual de bonos del gobierno a
    10 años (prefijo IRLTLT01, sufijo M156N). Devuelve una lista ordenada por el
    nombre en español con: country (nombre en FRED), label (español), id, title,
    observation_end (último dato). Si FRED devuelve dos series para un mismo país
    se queda con la de dato más reciente.
    """
    params = {
        "search_text": f"{LONG_TERM_PREFIX}*",
        "search_type": "series_id",
        "api_key": api_key,
        "file_type": "json",
        "limit": 1000,
    }
    response = http.get(f"{FRED_BASE_URL}/series/search", params=params, timeout=15)
    response.raise_for_status()
    best = {}
    for s in response.json().get("seriess", []):
        sid = s.get("id", "")
        if not (sid.startswith(LONG_TERM_PREFIX) and sid.endswith(MONTHLY_SUFFIX)):
            continue
        country = _country_from_title(s.get("title", ""))
        if not country:
            continue
        row = {"country": country, "label": COUNTRY_ES.get(country, country), "id": sid,
               "title": s.get("title", ""), "observation_end": s.get("observation_end", "")}
        if country not in best or row["observation_end"] > best[country]["observation_end"]:
            best[country] = row
    return sorted(best.values(), key=lambda r: r["label"])
