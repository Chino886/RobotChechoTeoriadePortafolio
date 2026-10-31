"""
Cotización en línea (guía V2, sección 3): adaptador aislado sobre yfinance
para el "reloj de cotización". Separado de la descarga histórica de la v1
(src/data.py), que alimenta el reloj de estimación.

- Usa barras de 1 minuto SIN ajustar (último negocio aproximado), no cierres
  diarios. La última barra puede estar incompleta.
- "Consultado ahora" no significa "negociado ahora": se muestran la hora de
  la última barra, la hora de recepción y la antigüedad.
- Una cotización repetida (misma barra y precio) no es un dato nuevo.
- Fuera de sesión se informa el último dato disponible; no se inventa
  movimiento. Yahoo publica con retrasos según la bolsa y prohíbe
  redistribuir sus datos: no se guardan cotizaciones en archivos.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

PRICE_TYPE = "Cierre de la última barra de 1 minuto, sin ajustar (aprox. último negocio)"


@dataclass
class Quote:
    ticker: str
    ok: bool
    price: Optional[float] = None
    price_type: str = PRICE_TYPE
    exchange: Optional[str] = None
    currency: Optional[str] = None
    timezone: Optional[str] = None
    last_bar_at: Optional[datetime] = None  # hora del evento (inicio de la barra), en UTC
    received_at: Optional[datetime] = None  # cuándo la recibió la app, en UTC
    session: str = "desconocida"  # "en sesión", "fuera de sesión" o "desconocida"
    error: Optional[str] = None

    @property
    def age_seconds(self) -> Optional[float]:
        if self.last_bar_at is None or self.received_at is None:
            return None
        return (self.received_at - self.last_bar_at).total_seconds()

    def same_data_as(self, other: Optional["Quote"]) -> bool:
        """True si es la misma barra y el mismo precio: no aumenta la muestra ni dispara decisiones."""
        return (
            other is not None and other.ok and self.ok and other.ticker == self.ticker
            and other.last_bar_at == self.last_bar_at and other.price == self.price
        )


def _session_state(metadata: dict, now: datetime) -> str:
    try:
        regular = metadata["currentTradingPeriod"]["regular"]
        start = datetime.fromtimestamp(int(regular["start"]), tz=timezone.utc)
        end = datetime.fromtimestamp(int(regular["end"]), tz=timezone.utc)
        return "en sesión" if start <= now <= end else "fuera de sesión"
    except Exception:
        return "desconocida"


def fetch_quote(ticker: str, now: Optional[datetime] = None, ticker_factory=None) -> Quote:
    """
    Consulta la última barra de 1 minuto. Si hoy no hay barras (fin de semana
    o antes de abrir), usa los últimos 5 días para mostrar el último dato
    disponible con su antigüedad real. Nunca lanza excepción: devuelve el
    diagnóstico en `error`.
    """
    ticker = (ticker or "").strip().upper()
    if not ticker:
        return Quote(ticker=ticker, ok=False, error="Ticker vacío.")
    if ticker_factory is None:
        import yfinance as yf
        ticker_factory = yf.Ticker
    try:
        yf_ticker = ticker_factory(ticker)
        bars = None
        for period in ("1d", "5d"):
            bars = yf_ticker.history(period=period, interval="1m", auto_adjust=False, prepost=False, actions=False)
            if bars is not None and not bars.empty and "Close" in bars and bars["Close"].dropna().size:
                break
        received = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        if bars is None or bars.empty or "Close" not in bars:
            return Quote(ticker=ticker, ok=False, received_at=received, error="Sin barras recientes (símbolo inválido o sin datos).")
        close = bars["Close"].dropna()
        close = close[close > 0]
        if close.empty:
            return Quote(ticker=ticker, ok=False, received_at=received, error="Barras sin precios válidos.")
        last_at = pd.Timestamp(close.index[-1])
        last_at = (last_at.tz_localize("UTC") if last_at.tzinfo is None else last_at.tz_convert("UTC")).to_pydatetime()
        try:
            metadata = yf_ticker.get_history_metadata() or {}
        except Exception:
            metadata = {}
        return Quote(
            ticker=ticker, ok=True, price=float(close.iloc[-1]),
            exchange=metadata.get("fullExchangeName") or metadata.get("exchangeName"),
            currency=metadata.get("currency"), timezone=metadata.get("exchangeTimezoneName"),
            last_bar_at=last_at, received_at=received, session=_session_state(metadata, received),
        )
    except Exception as exc:  # timeout, 429, red: se conserva el diagnóstico
        return Quote(ticker=ticker, ok=False, received_at=(now or datetime.now(timezone.utc)), error=f"Error de consulta: {exc}")


def format_age(seconds: Optional[float]) -> str:
    if seconds is None:
        return "N/D"
    seconds = max(seconds, 0)
    if seconds < 120:
        return f"{seconds:.0f} s"
    if seconds < 7200:
        return f"{seconds / 60:.0f} min"
    if seconds < 172800:
        return f"{seconds / 3600:.1f} h"
    return f"{seconds / 86400:.1f} días"
