"""Tickers de otras bolsas (buscador de Yahoo Finance), sin red."""
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import src.tickers as tk  # noqa: E402

QUOTES = [
    {"symbol": "ECOPETROL.CL", "longname": "Ecopetrol S.A.", "exchDisp": "Colombia", "quoteType": "EQUITY"},
    {"symbol": "EC", "longname": "Ecopetrol S.A.", "exchDisp": "NYSE", "quoteType": "EQUITY"},
    {"symbol": "SAP.DE", "shortname": "SAP SE", "exchDisp": "XETRA", "quoteType": "EQUITY"},
    {"symbol": "EURUSD=X", "shortname": "EUR/USD", "quoteType": "CURRENCY"},
    {"symbol": "ICOLCAP.CL", "longname": "iShares MSCI COLCAP", "exchDisp": "Colombia", "quoteType": "ETF"},
]


def test_parse_keeps_only_stocks_and_etfs_with_market_and_currency():
    df = tk.yahoo_search("ecopetrol", searcher=lambda q: QUOTES)
    assert list(df.columns) == tk.COLUMNS and "EURUSD=X" not in set(df["ticker"])
    row = df.set_index("ticker").loc["ECOPETROL.CL"]
    assert row["bolsa"] == "Bolsa de Colombia · COP" and row["tipo"] == "Acción" and row["empresa"] == "Ecopetrol S.A."
    assert df.set_index("ticker").loc["SAP.DE", "bolsa"] == "Xetra Alemania · EUR"
    assert df.set_index("ticker").loc["ICOLCAP.CL", "tipo"] == "Fondo (ETF)"


def test_merge_adds_international_without_duplicates_and_respects_type():
    local = pd.DataFrame([("EC", "Ecopetrol (ADR)", "NYSE", "Acción")], columns=tk.COLUMNS)
    intl = tk.parse_yahoo_search(QUOTES)
    out = tk.merge_international(local, intl)
    assert list(out["ticker"]).count("EC") == 1 and {"ECOPETROL.CL", "SAP.DE"} <= set(out["ticker"])
    etf_only = tk.merge_international(local, intl, kind="Fondo (ETF)")
    assert set(etf_only["ticker"]) == {"EC", "ICOLCAP.CL"}


def test_tickers_page_shows_other_markets(monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setattr(tk, "yahoo_search", lambda q, **k: tk.parse_yahoo_search(QUOTES))
    monkeypatch.setattr(tk, "fetch_us_tickers", lambda http=None: tk.fallback_tickers())
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    at.text_input(key="ticker_search").input("ecopetrol").run()
    assert not at.exception
    labels = at.selectbox(key="ticker_pick").options
    assert any(l.startswith("ECOPETROL.CL") for l in labels) and any(l.startswith("EC —") for l in labels)
    assert any("Otras bolsas (Yahoo Finance)" in c.value for c in at.caption)
