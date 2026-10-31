"""
Fase 2 (v2) - Reloj de cotización (guía V2, sección 3). Pruebas con mocks
sin red: metadatos, antigüedad, dato repetido, error aislado y sesión.
La conexión real a Yahoo (P2-3) se verifica aparte; un mock no la acredita.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.market import fetch_quote, fetch_quotes, format_age  # noqa: E402

NOW = datetime(2026, 10, 30, 15, 0, 30, tzinfo=timezone.utc)
SESSION = {"regular": {"start": int(datetime(2026, 10, 30, 13, 30, tzinfo=timezone.utc).timestamp()),
                       "end": int(datetime(2026, 10, 30, 20, 0, tzinfo=timezone.utc).timestamp())}}


class FakeTicker:
    def __init__(self, bars_by_period, metadata=None, fail=False):
        self.bars_by_period, self.metadata, self.fail = bars_by_period, metadata or {}, fail
        self.calls = []

    def history(self, period, **kwargs):
        self.calls.append((period, kwargs))
        if self.fail:
            raise TimeoutError("429 Too Many Requests")
        return self.bars_by_period.get(period, pd.DataFrame())

    def get_history_metadata(self):
        return self.metadata


def _bars(times, closes):
    idx = pd.DatetimeIndex(times).tz_localize("America/New_York")
    return pd.DataFrame({"Close": closes}, index=idx)


def test_quote_metadata_age_and_session():
    bars = _bars(["2026-10-30 10:58", "2026-10-30 10:59"], [270.0, 270.5])
    fake = FakeTicker({"1d": bars}, {"fullExchangeName": "NasdaqGS", "currency": "USD",
                                    "exchangeTimezoneName": "America/New_York", "currentTradingPeriod": SESSION})
    q = fetch_quote("aapl", now=NOW, ticker_factory=lambda t: fake)
    assert q.ok and q.ticker == "AAPL" and q.price == 270.5
    assert q.exchange == "NasdaqGS" and q.currency == "USD" and q.timezone == "America/New_York"
    assert q.last_bar_at == datetime(2026, 10, 30, 14, 59, tzinfo=timezone.utc)
    assert q.age_seconds == 90 and q.session == "en sesión"
    assert fake.calls[0][1]["auto_adjust"] is False and fake.calls[0][1]["interval"] == "1m"


def test_repeated_quote_is_not_new_data():
    bars = _bars(["2026-10-30 10:59"], [270.5])
    make = lambda t: FakeTicker({"1d": bars})  # noqa: E731
    first = fetch_quote("AAPL", now=NOW, ticker_factory=make)
    second = fetch_quote("AAPL", now=NOW.replace(second=59), ticker_factory=make)
    assert second.same_data_as(first)
    moved = fetch_quote("AAPL", now=NOW, ticker_factory=lambda t: FakeTicker({"1d": _bars(["2026-10-30 11:00"], [271.0])}))
    assert not moved.same_data_as(first)


def test_closed_market_uses_last_available_bar_with_real_age():
    friday = _bars(["2026-10-30 15:59"], [271.0])
    saturday = datetime(2026, 10, 31, 16, 0, tzinfo=timezone.utc)
    q = fetch_quote("AAPL", now=saturday, ticker_factory=lambda t: FakeTicker({"1d": pd.DataFrame(), "5d": friday},
                                                                              {"currentTradingPeriod": SESSION}))
    assert q.ok and q.session == "fuera de sesión" and q.age_seconds > 20 * 3600


def test_errors_are_isolated_and_reported():
    q = fetch_quote("AAPL", now=NOW, ticker_factory=lambda t: FakeTicker({}, fail=True))
    assert not q.ok and "429" in q.error
    q = fetch_quote("NOEXISTE", now=NOW, ticker_factory=lambda t: FakeTicker({}))
    assert not q.ok and "Sin barras" in q.error
    assert fetch_quote("  ", ticker_factory=lambda t: FakeTicker({})).error == "Ticker vacío."


def test_format_age():
    assert format_age(45) == "45 s" and format_age(600) == "10 min" and format_age(None) == "N/D"


def test_many_quotes_isolate_errors_and_keep_bars():
    good = _bars(["2026-10-30 10:58", "2026-10-30 10:59"], [270.0, 270.5])

    def factory(t):
        return FakeTicker({}, fail=True) if t == "MALO" else FakeTicker({"1d": good})

    quotes = fetch_quotes(["aapl", "MALO", "msft", "AAPL", ""], now=NOW, ticker_factory=factory)
    assert [q.ticker for q in quotes] == ["AAPL", "MALO", "MSFT"]  # sin duplicados ni vacíos
    assert [q.ok for q in quotes] == [True, False, True]  # el error no borra a los demás
    assert len(quotes[0].bars) == 2 and quotes[0].bars.iloc[-1] == 270.5
