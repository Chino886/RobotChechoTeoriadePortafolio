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
from concurrent.futures import ThreadPoolExecutor

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


# Series de FRED que se usan para armar la lista de países. Los códigos no se adivinan
# por país: se le pregunta a FRED qué series existen con cada prefijo.
# - OCDE (IRLTLT01…): "Long-Term Government Bond Yields: 10-Year: Main (Including Benchmark)".
#   Es la tasa a 10 años; viene mensual (M156N), trimestral (Q156N) o anual (A156N).
# - FMI (INTGSB…): "Interest Rates, Government Securities, Government Bonds". Cubre más países,
#   pero el plazo del bono depende del país (no siempre 10 años); M193N, Q193N o A193N.
SOURCES = {
    "IRLTLT01": {"name": "OCDE", "detail": "bono del gobierno a 10 años", "suffixes": {"M156N": "mensual", "Q156N": "trimestral", "A156N": "anual"}},
    "INTGSB": {"name": "FMI", "detail": "bonos del gobierno (plazo según el país, no siempre 10 años)", "suffixes": {"M193N": "mensual", "Q193N": "trimestral", "A193N": "anual"}},
}
FREQ_RANK = {"mensual": 0, "trimestral": 1, "anual": 2}
# Se prefiere la serie a 10 años de la OCDE salvo que la del FMI sea más de un año más reciente.
OECD_GRACE_DAYS = 365

# Nombres en español para mostrar; si FRED trae un país que no está aquí, se muestra en inglés.
COUNTRY_ES = {
    "Albania": "Albania", "Algeria": "Argelia", "Argentina": "Argentina", "Armenia": "Armenia",
    "Australia": "Australia", "Austria": "Austria", "Bahamas": "Bahamas", "Bahrain": "Baréin",
    "Bangladesh": "Bangladés", "Barbados": "Barbados", "Belgium": "Bélgica", "Belize": "Belice",
    "Bolivia": "Bolivia", "Botswana": "Botsuana", "Brazil": "Brasil", "Bulgaria": "Bulgaria",
    "Canada": "Canadá", "Chile": "Chile", "China": "China", "Colombia": "Colombia", "Costa Rica": "Costa Rica",
    "Croatia": "Croacia", "Cyprus": "Chipre", "Czechia": "Chequia", "Czech Republic": "Chequia",
    "Denmark": "Dinamarca", "Dominican Republic": "República Dominicana", "Ecuador": "Ecuador", "Egypt": "Egipto",
    "El Salvador": "El Salvador", "Estonia": "Estonia", "Ethiopia": "Etiopía",
    "Euro Area (19 Countries)": "Zona euro (19 países)", "Euro area (19 countries)": "Zona euro (19 países)",
    "Euro Area": "Zona euro", "Fiji": "Fiyi", "Finland": "Finlandia", "France": "Francia", "Georgia": "Georgia",
    "Germany": "Alemania", "Ghana": "Ghana", "Greece": "Grecia", "Guatemala": "Guatemala", "Honduras": "Honduras",
    "Hong Kong": "Hong Kong", "Hungary": "Hungría", "Iceland": "Islandia", "India": "India",
    "Indonesia": "Indonesia", "Ireland": "Irlanda", "Israel": "Israel", "Italy": "Italia", "Jamaica": "Jamaica",
    "Japan": "Japón", "Jordan": "Jordania", "Kazakhstan": "Kazajistán", "Kenya": "Kenia", "Korea": "Corea del Sur",
    "Republic of Korea": "Corea del Sur", "Kuwait": "Kuwait", "Latvia": "Letonia", "Lebanon": "Líbano",
    "Lithuania": "Lituania", "Luxembourg": "Luxemburgo", "Malaysia": "Malasia", "Malta": "Malta",
    "Mauritius": "Mauricio", "Mexico": "México", "Morocco": "Marruecos", "Namibia": "Namibia", "Nepal": "Nepal",
    "Netherlands": "Países Bajos", "New Zealand": "Nueva Zelanda", "Nicaragua": "Nicaragua", "Nigeria": "Nigeria",
    "North Macedonia": "Macedonia del Norte", "Norway": "Noruega", "Pakistan": "Pakistán", "Panama": "Panamá",
    "Paraguay": "Paraguay", "Peru": "Perú", "Philippines": "Filipinas", "Poland": "Polonia",
    "Portugal": "Portugal", "Qatar": "Catar", "Romania": "Rumania", "Russia": "Rusia",
    "Russian Federation": "Rusia", "Saudi Arabia": "Arabia Saudita", "Serbia": "Serbia", "Singapore": "Singapur",
    "Slovak Republic": "Eslovaquia", "Slovakia": "Eslovaquia", "Slovenia": "Eslovenia",
    "South Africa": "Sudáfrica", "Spain": "España", "Sri Lanka": "Sri Lanka", "Sweden": "Suecia",
    "Switzerland": "Suiza", "Thailand": "Tailandia", "Trinidad and Tobago": "Trinidad y Tobago",
    "Tunisia": "Túnez", "Turkey": "Turquía", "Türkiye": "Turquía", "Uganda": "Uganda", "Ukraine": "Ucrania",
    "United Kingdom": "Reino Unido", "United States": "Estados Unidos", "Uruguay": "Uruguay",
    "Venezuela": "Venezuela", "Vietnam": "Vietnam", "Zambia": "Zambia",
}


def _country_from_title(title: str) -> str:
    return title.rsplit(" for ", 1)[-1].strip() if " for " in title else title.strip()


def _search_prefix(api_key: str, prefix: str, http) -> "list[dict]":
    """Todas las series cuyo código empieza por `prefix`, pidiendo páginas hasta agotar el conteo."""
    out, offset = [], 0
    while True:
        params = {"search_text": f"{prefix}*", "search_type": "series_id", "api_key": api_key,
                  "file_type": "json", "limit": 1000, "offset": offset}
        response = http.get(f"{FRED_BASE_URL}/series/search", params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        page = data.get("seriess", [])
        out.extend(page)
        offset += len(page)
        if not page or offset >= int(data.get("count", 0) or 0):
            return out


# Países que se buscan además por nombre (la búsqueda por código de serie no siempre los
# trae; así se encontraba Colombia antes). Nombres en inglés, como los titula FRED.
TEXT_SEARCH_COUNTRIES = [
    "Colombia", "Brazil", "Peru", "Chile", "Mexico", "Argentina", "Ecuador", "Uruguay", "Paraguay", "Bolivia",
    "Costa Rica", "Panama", "Guatemala", "Dominican Republic", "Venezuela", "China", "India", "Indonesia",
    "South Africa", "Turkey", "Philippines", "Thailand", "Malaysia", "Vietnam", "Egypt", "Nigeria",
    "Saudi Arabia", "Russia",
]
FREQ_SHORT = {"D": "diaria", "W": "semanal", "M": "mensual", "Q": "trimestral", "A": "anual"}
SOURCE_RANK = {"OCDE": 0, "FMI": 1, "FRED": 2}
FREQ_RANK.update({"diaria": -2, "semanal": -1})


def _row(series: dict, country: str, source: str, detail: str, frequency: str) -> dict:
    return {"country": country, "label": COUNTRY_ES.get(country, country), "id": series.get("id", ""),
            "title": series.get("title", ""), "source": source, "detail": detail, "frequency": frequency,
            "observation_end": series.get("observation_end", "")}


def _classify(series: dict, country: str) -> "dict | None":
    """Convierte un resultado de la búsqueda por nombre en fila, si es una tasa de bonos del gobierno del país."""
    title = series.get("title", "")
    if _country_from_title(title) != country:
        return None
    low = title.lower()
    if "bond" not in low and "government securities" not in low:
        return None
    if "long-term government bond yields" in low and "10-year" in low:
        source, detail = "OCDE", SOURCES["IRLTLT01"]["detail"]
    elif series.get("id", "").startswith("INTGSB") or "government bonds" in low:
        source, detail = "FMI", SOURCES["INTGSB"]["detail"]
    else:
        source, detail = "FRED", "según el título de la serie"
    freq = FREQ_SHORT.get(str(series.get("frequency_short", "")).upper()[:1])
    return _row(series, country, source, detail, freq) if freq else None


def _search_country_text(api_key: str, country: str, http) -> "list[dict]":
    """Misma búsqueda por nombre que usaba la versión anterior; si no trae nada útil, una más general."""
    for text in (f"{country} 10-Year government bond yield", f"{country} government bond yield"):
        params = {"search_text": text, "api_key": api_key, "file_type": "json",
                  "limit": 25, "order_by": "popularity", "sort_order": "desc"}
        response = http.get(f"{FRED_BASE_URL}/series/search", params=params, timeout=15)
        response.raise_for_status()
        rows = [r for r in (_classify(s, country) for s in response.json().get("seriess", [])) if r]
        if rows:
            return rows
    return []


def list_long_term_yield_countries(api_key: str, http=requests) -> "list[dict]":
    """
    Países con alguna serie de rendimiento de bonos del gobierno en FRED. Una fila por país
    (por nombre en español, sin repetidos), ordenada, con: country, label, id, title, source,
    detail, frequency, observation_end.

    1. Búsqueda por código: OCDE a 10 años (IRLTLT01…) y FMI (INTGSB…).
    2. Búsqueda por nombre para los países de TEXT_SEARCH_COUNTRIES que no salieron en el paso 1
       (por ejemplo Colombia).
    Por país se prefiere la OCDE a 10 años, luego el FMI y luego otra serie de bonos, salvo que
    una de menor preferencia tenga datos más de un año más recientes.
    """
    candidates = {}
    for prefix, meta in SOURCES.items():
        for s in _search_prefix(api_key, prefix, http):
            sid = s.get("id", "")
            freq = next((f for suf, f in meta["suffixes"].items() if sid.startswith(prefix) and sid.endswith(suf)), None)
            country = _country_from_title(s.get("title", ""))
            if freq and country:
                row = _row(s, country, meta["name"], meta["detail"], freq)
                candidates.setdefault(row["label"], []).append(row)

    missing = [c for c in TEXT_SEARCH_COUNTRIES if COUNTRY_ES.get(c, c) not in candidates]
    if missing:
        def safe(country):
            try:
                return _search_country_text(api_key, country, http)
            except Exception:  # un país que falle no tumba la lista
                return []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for rows in pool.map(safe, missing):
                for row in rows:
                    candidates.setdefault(row["label"], []).append(row)

    def best_of(rows):
        # Entre las series con dato de hasta un año menos que la más nueva, la de mayor frecuencia
        # y, si empatan, la más reciente.
        newest = max(r["observation_end"] for r in rows)
        fresh = [r for r in rows if _days_between(r["observation_end"], newest) <= OECD_GRACE_DAYS]
        return sorted(fresh, key=lambda r: (FREQ_RANK[r["frequency"]], _neg(r["observation_end"])))[0]

    chosen = []
    for rows in candidates.values():
        per_source = sorted((best_of([r for r in rows if r["source"] == src]) for src in {r["source"] for r in rows}),
                            key=lambda r: SOURCE_RANK[r["source"]])
        newest = max(r["observation_end"] for r in per_source)
        chosen.append(next(r for r in per_source if _days_between(r["observation_end"], newest) <= OECD_GRACE_DAYS))
    return sorted(chosen, key=lambda r: r["label"])


def _days_between(older: str, newer: str) -> int:
    """Días que `older` va detrás de `newer` (0 si va igual o adelante; fechas vacías cuentan como muy viejas)."""
    try:
        return max(0, (pd.Timestamp(newer) - pd.Timestamp(older)).days)
    except (ValueError, TypeError):
        return 10 ** 6


def _neg(date_str: str) -> int:
    try:
        return -pd.Timestamp(date_str).value
    except (ValueError, TypeError):
        return 0
