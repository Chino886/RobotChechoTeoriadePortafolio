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
# Empresas de otras bolsas (búsqueda de Yahoo Finance)
# El directorio de NASDAQ Trader solo trae las bolsas de EE. UU. Para empresas de otros países se
# consulta el buscador de Yahoo Finance (la misma fuente de los precios). El sufijo del ticker dice
# la bolsa y la moneda en que cotiza; la Comparación ya convierte esa moneda a la moneda base.
# ---------------------------------------------------------------------------
SUFFIX_MARKETS = {
    "CL": ("Bolsa de Colombia", "COP"), "MX": ("Bolsa Mexicana", "MXN"), "SA": ("B3 Brasil", "BRL"),
    "BA": ("Bolsa de Buenos Aires", "ARS"), "SN": ("Bolsa de Santiago", "CLP"), "LM": ("Bolsa de Lima", "PEN"),
    "TO": ("Bolsa de Toronto", "CAD"), "V": ("TSX Venture", "CAD"), "L": ("Bolsa de Londres", "GBP (peniques)"),
    "DE": ("Xetra Alemania", "EUR"), "F": ("Bolsa de Fráncfort", "EUR"), "PA": ("Euronext París", "EUR"),
    "AS": ("Euronext Ámsterdam", "EUR"), "BR": ("Euronext Bruselas", "EUR"), "LS": ("Euronext Lisboa", "EUR"),
    "MC": ("Bolsa de Madrid", "EUR"), "MI": ("Bolsa de Milán", "EUR"), "HE": ("Bolsa de Helsinki", "EUR"),
    "SW": ("SIX Suiza", "CHF"), "ST": ("Bolsa de Estocolmo", "SEK"), "OL": ("Bolsa de Oslo", "NOK"),
    "CO": ("Bolsa de Copenhague", "DKK"), "T": ("Bolsa de Tokio", "JPY"), "HK": ("Bolsa de Hong Kong", "HKD"),
    "SS": ("Bolsa de Shanghái", "CNY"), "SZ": ("Bolsa de Shenzhen", "CNY"), "KS": ("Bolsa de Corea", "KRW"),
    "TW": ("Bolsa de Taiwán", "TWD"), "NS": ("NSE India", "INR"), "BO": ("Bolsa de Bombay", "INR"),
    "AX": ("Bolsa de Australia", "AUD"), "NZ": ("Bolsa de Nueva Zelanda", "NZD"), "SI": ("Bolsa de Singapur", "SGD"),
    "JO": ("Bolsa de Johannesburgo", "ZAR (centavos)"),
}
_QUOTE_TYPES = {"EQUITY": "Acción", "ETF": "Fondo (ETF)"}


def market_of(ticker: str, exch_disp: str = "") -> str:
    """Texto de la columna «bolsa» para un ticker de Yahoo: nombre de la bolsa y moneda según su sufijo."""
    suffix = ticker.rsplit(".", 1)[1].upper() if "." in ticker else ""
    if suffix in SUFFIX_MARKETS:
        name, ccy = SUFFIX_MARKETS[suffix]
        return f"{name} · {ccy}"
    return (exch_disp or "Otra bolsa").strip()


def parse_yahoo_search(quotes) -> pd.DataFrame:
    """Resultados del buscador de Yahoo (acciones y ETF) en las mismas columnas del directorio."""
    rows = []
    for q in quotes or []:
        kind = _QUOTE_TYPES.get(str(q.get("quoteType", "")).upper())
        symbol = str(q.get("symbol") or "").strip()
        if not kind or not symbol:
            continue
        name = str(q.get("longname") or q.get("shortname") or symbol).strip()
        rows.append((symbol, name, market_of(symbol, str(q.get("exchDisp") or q.get("exchange") or "")), kind))
    return pd.DataFrame(rows, columns=COLUMNS).drop_duplicates("ticker")


def yahoo_search(text: str, max_results: int = 25, searcher=None) -> pd.DataFrame:
    """Busca en Yahoo Finance (todas las bolsas). Lanza la excepción si la consulta falla."""
    if searcher is None:
        import yfinance as yf
        if not hasattr(yf, "Search"):
            raise RuntimeError("Esta versión de yfinance no trae el buscador (se necesita yfinance 0.2.47 o más).")
        searcher = lambda q: yf.Search(q, max_results=max_results, news_count=0, raise_errors=True).quotes  # noqa: E731
    return parse_yahoo_search(searcher(text))


def merge_international(local: pd.DataFrame, international: pd.DataFrame, kind: str = "Todos",
                        keep_first: int = 20) -> pd.DataFrame:
    """
    Junta el directorio de EE. UU. con lo de otras bolsas (sin repetir tickers): primero los mejores
    resultados locales, luego los internacionales y después el resto, para que no queden escondidos.
    """
    if international is None or international.empty:
        return local
    extra = international[~international["ticker"].isin(set(local["ticker"]))]
    if kind != "Todos":
        extra = extra[extra["tipo"] == kind]
    return pd.concat([local.head(keep_first), extra, local.iloc[keep_first:]], ignore_index=True)
