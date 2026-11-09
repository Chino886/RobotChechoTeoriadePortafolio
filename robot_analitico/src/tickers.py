"""
Directorio de tickers (el código con el que cada empresa o fondo aparece en la bolsa).

Fuente: directorio público de símbolos de NASDAQ Trader, sin clave ni registro:
- nasdaqlisted.txt: empresas y fondos de NASDAQ;
- otherlisted.txt: NYSE, NYSE American, NYSE Arca, Cboe e IEX.
Ambos archivos son texto separado por «|», con una última línea «File Creation Time».
Se descartan las emisiones de prueba. El símbolo se pasa al formato de Yahoo Finance
(«BRK.B» → «BRK-B»), que es el que usa el bot para descargar precios.

Si el directorio no responde, se usa una lista corta de empresas conocidas.
"""
import io
import re
import unicodedata

import pandas as pd
import requests

NASDAQ_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
OTHER_URL = "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
EXCHANGES = {"A": "NYSE American", "N": "NYSE", "P": "NYSE Arca", "Z": "Cboe", "V": "IEX"}
COLUMNS = ["ticker", "empresa", "bolsa", "tipo"]

# Respaldo: empresas y fondos muy conocidos (ticker de Yahoo Finance).
FALLBACK = [
    ("AAPL", "Apple", "NASDAQ", "Acción"), ("MSFT", "Microsoft", "NASDAQ", "Acción"),
    ("GOOGL", "Alphabet (Google)", "NASDAQ", "Acción"), ("AMZN", "Amazon", "NASDAQ", "Acción"),
    ("META", "Meta Platforms (Facebook)", "NASDAQ", "Acción"), ("NVDA", "NVIDIA", "NASDAQ", "Acción"),
    ("TSLA", "Tesla", "NASDAQ", "Acción"), ("NFLX", "Netflix", "NASDAQ", "Acción"),
    ("PEP", "PepsiCo", "NASDAQ", "Acción"), ("KO", "Coca-Cola", "NYSE", "Acción"),
    ("MCD", "McDonald's", "NYSE", "Acción"), ("NKE", "Nike", "NYSE", "Acción"),
    ("DIS", "Walt Disney", "NYSE", "Acción"), ("WMT", "Walmart", "NYSE", "Acción"),
    ("JPM", "JPMorgan Chase", "NYSE", "Acción"), ("V", "Visa", "NYSE", "Acción"),
    ("MA", "Mastercard", "NYSE", "Acción"), ("JNJ", "Johnson & Johnson", "NYSE", "Acción"),
    ("PG", "Procter & Gamble", "NYSE", "Acción"), ("XOM", "Exxon Mobil", "NYSE", "Acción"),
    ("EC", "Ecopetrol (ADR)", "NYSE", "Acción"), ("CIB", "Bancolombia (ADR)", "NYSE", "Acción"),
    ("AVAL", "Grupo Aval (ADR)", "NYSE", "Acción"), ("SPY", "SPDR S&P 500 ETF", "NYSE Arca", "Fondo (ETF)"),
]


def fallback_tickers() -> pd.DataFrame:
    return pd.DataFrame(FALLBACK, columns=COLUMNS)


def _read(text: str) -> pd.DataFrame:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("File Creation Time")]
    return pd.read_csv(io.StringIO("\n".join(lines)), sep="|", dtype=str, keep_default_na=False)


def _to_yahoo(symbol: str) -> str:
    return symbol.strip().replace(".", "-")


def parse_nasdaq_listed(text: str) -> pd.DataFrame:
    df = _read(text)
    df = df[df.get("Test Issue", "N") != "Y"]
    return pd.DataFrame({
        "ticker": df["Symbol"].map(_to_yahoo), "empresa": df["Security Name"].str.strip(),
        "bolsa": "NASDAQ", "tipo": df["ETF"].map(lambda x: "Fondo (ETF)" if x == "Y" else "Acción"),
    })


def parse_other_listed(text: str) -> pd.DataFrame:
    df = _read(text)
    df = df[df.get("Test Issue", "N") != "Y"]
    return pd.DataFrame({
        "ticker": df["ACT Symbol"].map(_to_yahoo), "empresa": df["Security Name"].str.strip(),
        "bolsa": df["Exchange"].map(lambda x: EXCHANGES.get(x, x)),
        "tipo": df["ETF"].map(lambda x: "Fondo (ETF)" if x == "Y" else "Acción"),
    })


def fetch_us_tickers(http=requests) -> pd.DataFrame:
    """Todas las empresas y fondos de las bolsas de EE. UU., ordenados por ticker."""
    parts = []
    for url, parser in ((NASDAQ_URL, parse_nasdaq_listed), (OTHER_URL, parse_other_listed)):
        resp = http.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0 (bot académico)"})
        resp.raise_for_status()
        parts.append(parser(resp.text))
    out = pd.concat(parts, ignore_index=True)
    out = out[out["ticker"].str.len() > 0].drop_duplicates("ticker")
    return out.sort_values("ticker").reset_index(drop=True)


def _norm(text: str) -> str:
    """Minúsculas, sin tildes y sin signos: «Coca-Cola» y «coca cola» quedan iguales."""
    t = unicodedata.normalize("NFD", str(text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t).split())


def search(df: pd.DataFrame, text: str, kind: str = "Todos") -> pd.DataFrame:
    """
    Busca por nombre de empresa o por ticker (sin distinguir mayúsculas, tildes ni signos); filtra por tipo.
    Un nombre coincide si contiene todas las palabras escritas («coca cola» encuentra «Coca-Cola Company»).
    """
    out = df
    if kind != "Todos":
        out = out[out["tipo"] == kind]
    raw = (text or "").strip().lower()
    words = _norm(raw).split()
    if raw:
        exact = out["ticker"].str.lower() == raw
        names = out["empresa"].map(_norm)
        hit = out["ticker"].str.lower().str.startswith(raw)
        if words:
            joined = names.str.replace(" ", "", regex=False)
            hit = hit | names.map(lambda n: all(w in n for w in words)) | joined.str.contains("".join(words), regex=False)
        out = pd.concat([out[exact], out[hit & ~exact]])
    return out


# ---------------------------------------------------------------------------
# Otras bolsas del mundo (formato de Yahoo Finance: sufijo después del punto)
# ---------------------------------------------------------------------------
# Sufijo de Yahoo → (país, bolsa, moneda de cotización). La moneda es la que Yahoo informa para esa
# bolsa; al descargar el activo, el bot la vuelve a leer de Yahoo y usa esa (no esta tabla).
SUFFIX_INFO = {
    "CL": ("Colombia", "BVC (Bogotá)", "COP"), "SA": ("Brasil", "B3 (São Paulo)", "BRL"),
    "MX": ("México", "BMV", "MXN"), "SN": ("Chile", "Bolsa de Santiago", "CLP"),
    "BA": ("Argentina", "BYMA", "ARS"), "LM": ("Perú", "BVL (Lima)", "PEN"),
    "DE": ("Alemania", "XETRA", "EUR"), "F": ("Alemania", "Fráncfort", "EUR"), "BE": ("Alemania", "Berlín", "EUR"),
    "MU": ("Alemania", "Múnich", "EUR"), "SG": ("Alemania", "Stuttgart", "EUR"), "HM": ("Alemania", "Hamburgo", "EUR"),
    "HA": ("Alemania", "Hannover", "EUR"), "DU": ("Alemania", "Düsseldorf", "EUR"),
    "PA": ("Francia", "Euronext París", "EUR"), "AS": ("Países Bajos", "Euronext Ámsterdam", "EUR"),
    "MC": ("España", "BME (Madrid)", "EUR"), "MI": ("Italia", "Borsa Italiana", "EUR"),
    "L": ("Reino Unido", "LSE (Londres)", "GBp"), "SW": ("Suiza", "SIX", "CHF"),
    "T": ("Japón", "Bolsa de Tokio", "JPY"), "HK": ("Hong Kong", "HKEX", "HKD"),
    "TO": ("Canadá", "TSX (Toronto)", "CAD"), "AX": ("Australia", "ASX", "AUD"),
}
# Códigos de bolsa de Yahoo que son de EE. UU. (tickers sin sufijo)
US_EXCHANGES = {"NMS": "NASDAQ", "NGM": "NASDAQ", "NCM": "NASDAQ", "NYQ": "NYSE", "ASE": "NYSE American",
                "PCX": "NYSE Arca", "BTS": "Cboe", "NAS": "NASDAQ"}
WORLD_TYPES = {"EQUITY": "Acción", "ETF": "Fondo (ETF)"}

# Acciones internacionales comprobadas con una consulta real a Yahoo Finance (precios 2024-01-01 a
# 2026-11-06 y moneda informada por Yahoo). Se dejaron fuera las que no trajeron datos ese día:
# PFBCOLOM.CL y BCOLOMBIA.CL (Yahoo: «possibly delisted»). NUTRESA.CL traía datos pero quedó fuera por
# su OPA y baja negociación (precio poco representativo). Sirven aunque la búsqueda en línea falle.
VERIFIED_ON = "2026-11-09"
VERIFIED_INTL = [
    ("ECOPETROL.CL", "Ecopetrol (acción local)"), ("ISA.CL", "Interconexión Eléctrica ISA"),
    ("GRUPOSURA.CL", "Grupo Sura"), ("CEMARGOS.CL", "Cementos Argos"), ("GEB.CL", "Grupo Energía Bogotá"),
    ("PETR4.SA", "Petrobras (preferencial)"), ("VALE3.SA", "Vale"), ("ITUB4.SA", "Itaú Unibanco (preferencial)"),
    ("WALMEX.MX", "Walmart de México"), ("AMXB.MX", "América Móvil (serie B)"), ("FEMSAUBD.MX", "FEMSA (UBD)"),
    ("SQM-B.SN", "SQM (serie B)"), ("FALABELLA.SN", "Falabella"), ("CHILE.SN", "Banco de Chile"),
    ("SAP.DE", "SAP"), ("SIE.DE", "Siemens"), ("MC.PA", "LVMH"), ("AIR.PA", "Airbus"),
    ("HSBA.L", "HSBC Holdings"), ("SHEL.L", "Shell"), ("7203.T", "Toyota Motor"), ("6758.T", "Sony Group"),
]
WORLD_COLUMNS = COLUMNS + ["pais", "pais_bolsa", "moneda", "fuente"]


def place_info(symbol: str, exchange: str = "", exch_disp: str = "") -> "tuple[str, str, str]":
    """(país, bolsa, moneda) según el sufijo del ticker de Yahoo; sin sufijo y bolsa de EE. UU. → USD."""
    sym = (symbol or "").upper()
    if "." in sym and not sym.startswith("^"):
        suf = sym.rsplit(".", 1)[1]
        if suf in SUFFIX_INFO:
            return SUFFIX_INFO[suf]
    if exchange in US_EXCHANGES or ("." not in sym and not exchange):
        return ("EE. UU.", US_EXCHANGES.get(exchange, exch_disp or "EE. UU."), "USD")
    return ("Otro", exch_disp or exchange or "N/D", "N/D")


def add_place_columns(df: pd.DataFrame, fuente: str) -> pd.DataFrame:
    """Agrega país, «País/Bolsa» y moneda de cotización a una tabla del directorio."""
    out = df.copy()
    if out.empty:
        return pd.DataFrame(columns=WORLD_COLUMNS)
    us = out["ticker"].map(lambda t: "." not in str(t) or str(t).rsplit(".", 1)[1] not in SUFFIX_INFO)
    info = [("EE. UU.", b, "USD") if u else place_info(t) for t, b, u in zip(out["ticker"], out["bolsa"], us)]
    out["pais"] = [i[0] for i in info]
    out["pais_bolsa"] = [f"{i[0]} · {i[1]}" for i in info]
    out["moneda"] = [i[2] for i in info]
    out["bolsa"] = [i[1] for i in info]
    out["fuente"] = fuente
    return out[WORLD_COLUMNS]


def verified_international() -> pd.DataFrame:
    """Lista curada de acciones de otras bolsas, comprobada con Yahoo Finance el día VERIFIED_ON."""
    rows = []
    for t, name in VERIFIED_INTL:
        pais, bolsa, moneda = place_info(t)
        rows.append((t, name, bolsa, "Acción", pais, f"{pais} · {bolsa}", moneda, f"Lista verificada ({VERIFIED_ON})"))
    return pd.DataFrame(rows, columns=WORLD_COLUMNS)


def parse_world_quotes(quotes: "list[dict]") -> pd.DataFrame:
    """Convierte los resultados de yfinance.Search en filas del directorio (solo acciones y ETF)."""
    rows = []
    for q in quotes or []:
        sym, kind = str(q.get("symbol") or "").strip().upper(), WORLD_TYPES.get(q.get("quoteType"))
        if not sym or not kind:
            continue
        pais, bolsa, moneda = place_info(sym, q.get("exchange") or "", q.get("exchDisp") or "")
        name = str(q.get("longname") or q.get("shortname") or sym).strip()
        rows.append((sym, name, bolsa, kind, pais, f"{pais} · {bolsa}", moneda, "Búsqueda Yahoo Finance"))
    return pd.DataFrame(rows, columns=WORLD_COLUMNS).drop_duplicates("ticker")


def search_world(text: str, searcher=None, max_results: int = 20) -> pd.DataFrame:
    """
    Busca por nombre en todas las bolsas con yfinance.Search (Yahoo Finance). Lanza la excepción si
    Yahoo no responde, para que el llamador lo informe; no inventa resultados.
    """
    text = (text or "").strip()
    if len(text) < 2:
        return pd.DataFrame(columns=WORLD_COLUMNS)
    if searcher is None:
        import yfinance as yf

        searcher = lambda q: yf.Search(q, max_results=max_results, news_count=0, lists_count=0,  # noqa: E731
                                       recommended=0, raise_errors=True).quotes
    return parse_world_quotes(searcher(text))
