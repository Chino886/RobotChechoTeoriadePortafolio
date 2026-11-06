"""Directorio de tickers (NASDAQ Trader) y búsqueda. Sin red."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.tickers import fallback_tickers, fetch_us_tickers, search  # noqa: E402

NASDAQ = """Symbol|Security Name|Market Category|Test Issue|Financial Status|Round Lot Size|ETF|NextShares
AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N
QQQ|Invesco QQQ Trust, Series 1|G|N|N|100|Y|N
ZXZZT|NASDAQ TEST STOCK|G|Y|N|100|N|N
File Creation Time: 1106202621:00|||||||
"""
OTHER = """ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|Test Issue|NASDAQ Symbol
BRK.B|Berkshire Hathaway Inc. Class B|N|BRK.B|N|100|N|BRK.B
KO|Coca-Cola Company (The) Common Stock|N|KO|N|100|N|KO
SPY|SPDR S&P 500 ETF Trust|P|SPY|Y|100|N|SPY
File Creation Time: 1106202621:00|||||||
"""


class _Resp:
    def __init__(self, text):
        self.text = text

    def raise_for_status(self):
        pass


class _Http:
    def get(self, url, **kw):
        return _Resp(NASDAQ if "nasdaqlisted" in url else OTHER)


def test_directory_parses_both_files_skips_tests_and_uses_yahoo_format():
    df = fetch_us_tickers(http=_Http())
    assert df["ticker"].tolist() == ["AAPL", "BRK-B", "KO", "QQQ", "SPY"]
    row = df.set_index("ticker")
    assert row.loc["BRK-B", "bolsa"] == "NYSE" and row.loc["SPY", "bolsa"] == "NYSE Arca"
    assert row.loc["QQQ", "tipo"] == "Fondo (ETF)" and row.loc["AAPL", "tipo"] == "Acción"


def test_search_by_name_or_ticker_and_type():
    df = fetch_us_tickers(http=_Http())
    assert search(df, "coca")["ticker"].tolist() == ["KO"]
    assert search(df, "apple")["ticker"].tolist() == ["AAPL"]
    assert search(df, "spy")["ticker"].iloc[0] == "SPY"  # el ticker exacto va primero
    assert set(search(df, "", "Fondo (ETF)")["ticker"]) == {"QQQ", "SPY"}
    assert len(fallback_tickers()) >= 20


def test_simple_interface_tickers_tab_news_home_and_tooltips(monkeypatch):
    """Pestaña Tickers lleva el código a Preselección; noticias en Inicio (sin barra lateral ni hitos); ayudas con '?'."""
    import src.tickers
    from streamlit.testing.v1 import AppTest

    import streamlit as st

    monkeypatch.setattr(src.tickers.requests, "get", _Http().get)
    st.cache_data.clear()  # otra prueba pudo dejar en caché el directorio real (en CI hay red)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    assert not at.exception
    labels = [t.label for t in at.tabs]
    assert labels[0] == "Inicio" and "Tickers" in labels
    assert "Economía" in labels  # noticias de la semana en Inicio
    assert not any("Hitos" in e.label for e in at.expander)  # sin hitos históricos
    assert len(at.sidebar.button) == 0 and not any("Noticias" in m.value for m in at.sidebar.markdown)

    at.text_input(key="ticker_search").input("coca").run()
    assert at.selectbox(key="ticker_pick").value.startswith("KO")
    next(b for b in at.button if b.key == "ticker_use").click().run()
    assert not at.exception
    assert at.text_input(key="asset_ticker").value == "KO"
    assert any("quedó escrito" in s.value for s in at.success)

    # Las explicaciones ya no son desplegables: son líneas con ayuda emergente.
    assert not any(e.label.startswith(("¿Qué significa", "Más información")) for e in at.expander)
    assert sum(1 for c in at.caption if getattr(c, "help", None)) >= 5
