"""
Conversión de monedas visible y acciones de otras bolsas. Sin red: Yahoo Finance se simula.
- Acción en COP → USD con la tasa invertida de USDCOP=X.
- Tasa faltante → el activo se excluye con motivo (no se inventa la tasa).
- La alineación nunca usa tasas del futuro.
- La búsqueda devuelve resultados .CL con su moneda.
- La tabla de conversión coincide con el cálculo a mano.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import src.data as data  # noqa: E402
import src.fx_view as fx_view  # noqa: E402
from src.comparison import build_comparison  # noqa: E402
from src.data import AssetData, fetch_fx_to_usd  # noqa: E402
from src.fx_view import conversion_rows, fx_to_base, normalize_minor_units, rate_on, returns_identity  # noqa: E402
from src.tickers import add_place_columns, place_info, verified_international, yahoo_search  # noqa: E402

DAYS = pd.date_range("2025-01-06", periods=6, freq="B")
COP_PRICES = [2400.0, 2450.0, 2430.0, 2500.0, 2520.0, 2480.0]
USDCOP = [4000.0, 4050.0, 3990.0, 4100.0, 4080.0, 4020.0]
AAPL = [190.0, 191.0, 189.5, 193.0, 194.0, 192.0]


def _asset(ticker, prices, currency, index=DAYS):
    return AssetData(ticker=ticker, ok=True, prices=pd.DataFrame({"adjusted_close": prices}, index=index),
                     currency=currency)


def _fake_yahoo(series_by_ticker):
    """fetch_asset_data simulado: solo conoce los tickers del diccionario."""
    def fetch(ticker, start, end):
        t = (ticker or "").upper()
        if t not in series_by_ticker:
            return AssetData(ticker=t, ok=False, error="Respuesta vacía: ticker inexistente, sin datos en el rango o timeout.")
        idx, vals = series_by_ticker[t]
        return AssetData(ticker=t, ok=True, prices=pd.DataFrame({"adjusted_close": vals}, index=idx), currency="X")
    return fetch


@pytest.fixture
def yahoo_cop(monkeypatch):
    """Yahoo solo publica USDCOP=X (no COPUSD=X), como en la realidad."""
    fake = _fake_yahoo({"USDCOP=X": (DAYS, USDCOP)})
    monkeypatch.setattr(data, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_fx_to_usd", data.fetch_fx_to_usd)
    return fake


def test_cop_stock_converted_with_inverted_usdcop(yahoo_cop):
    res = fetch_fx_to_usd("COP", DAYS[0], DAYS[-1])
    assert res.ok and res.fx_pair == "USDCOP=X" and res.fx_inverted
    leg = fx_to_base("COP", "USD", DAYS[0], DAYS[-1], now="2026-11-09 16:00 UTC")
    assert leg.ok and "USDCOP=X" in leg.pairs and "invertido" in leg.pairs
    assets = {"ECOPETROL.CL": _asset("ECOPETROL.CL", COP_PRICES, "COP"), "AAPL": _asset("AAPL", AAPL, "USD")}
    result = build_comparison(assets, "Diaria", 252, base_currency="USD", fx_rates={"COP": leg.series})
    assert result.ok and result.base_currency == "USD"
    got = result.common_prices["ECOPETROL.CL"].to_numpy()
    np.testing.assert_allclose(got, np.array(COP_PRICES) / np.array(USDCOP))  # P_USD = P_COP / (COP por USD)
    # 1 + R_USD = (1 + R_COP)(1 + R_FX)
    ident = returns_identity(assets["ECOPETROL.CL"].prices["adjusted_close"], leg.series)
    np.testing.assert_allclose(1 + ident["R_base"], (1 + ident["R_local"]) * (1 + ident["R_FX"]))


def test_missing_rate_excludes_asset_with_visible_reason(monkeypatch):
    fake = _fake_yahoo({})  # Yahoo no tiene ningún par de BRL
    monkeypatch.setattr(data, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_fx_to_usd", data.fetch_fx_to_usd)
    leg = fx_to_base("BRL", "USD", DAYS[0], DAYS[-1])
    assert not leg.ok and "BRLUSD=X" in leg.error and "USDBRL=X" in leg.error and leg.series.empty
    assets = {"PETR4.SA": _asset("PETR4.SA", [40.0, 41, 40.5, 42, 41.5, 41], "BRL"), "AAPL": _asset("AAPL", AAPL, "USD")}
    result = build_comparison(assets, "Diaria", 252, base_currency="USD", fx_rates={})
    assert [s.ticker for s in result.summaries] == ["AAPL"]
    (exc,) = result.excluded
    assert exc.ticker == "PETR4.SA" and "tipo de cambio" in exc.reason and "BRL" in exc.reason


def test_alignment_never_uses_future_rates():
    fx = pd.Series([4000.0, 4100.0, 4200.0], index=pd.to_datetime(["2025-01-06", "2025-01-08", "2025-01-10"]))
    leg = fx_view.FxLeg("COP", "COP", True, fx)
    # El 7 y el 9 no hay tasa: se usa la del día anterior, nunca la siguiente.
    assert rate_on(leg, "2025-01-07") == 4000.0
    assert rate_on(leg, "2025-01-09") == 4100.0
    assert rate_on(leg, "2025-01-05") is None  # antes de la primera tasa: no se rellena hacia atrás
    days = pd.to_datetime(["2025-01-05", "2025-01-07", "2025-01-09", "2025-01-11"])
    asset = _asset("X.CL", [1.0, 1.0, 1.0, 1.0], "COP", index=days)
    result = build_comparison({"X.CL": asset, "Y": _asset("Y", [1.0, 2.0, 3.0, 4.0], "USD", index=days)},
                              "Diaria", 252, base_currency="USD", fx_rates={"COP": 1 / fx})
    conv = result.common_prices["X.CL"]
    assert list(conv.index.strftime("%m-%d")) == ["01-07", "01-09", "01-11"]  # el 5 queda fuera: no hay tasa previa
    np.testing.assert_allclose(conv.to_numpy(), [1 / 4000.0, 1 / 4100.0, 1 / 4200.0])


def test_world_search_returns_cl_results_with_currency():
    quotes = [{"symbol": "EC", "quoteType": "EQUITY", "exchange": "NYQ", "exchDisp": "NYSE", "shortname": "Ecopetrol S.A."},
              {"symbol": "ECOPETROL.CL", "quoteType": "EQUITY", "exchange": "BVC", "exchDisp": "BVC", "shortname": "ECOPETROL SA"},
              {"symbol": "E1CO34.SA", "quoteType": "EQUITY", "exchange": "SAO", "shortname": "ECOPETROL SADRN"},
              {"symbol": "XX", "quoteType": "OPTION", "exchange": "NYQ"}]
    df = add_place_columns(yahoo_search("ecopetrol", searcher=lambda q: quotes), "Buscador").set_index("ticker")
    assert list(df.index) == ["EC", "ECOPETROL.CL", "E1CO34.SA"]  # la opción se descarta
    assert df.loc["ECOPETROL.CL", "moneda"] == "COP" and df.loc["ECOPETROL.CL", "pais"] == "Colombia"
    assert df.loc["ECOPETROL.CL", "pais_bolsa"] == "Colombia · BVC (Bogotá)"
    assert df.loc["EC", "moneda"] == "USD" and df.loc["EC", "pais"] == "EE. UU."
    assert df.loc["E1CO34.SA", "moneda"] == "BRL"
    assert add_place_columns(yahoo_search("x", searcher=lambda q: []), "Buscador").empty


def test_verified_list_has_country_and_currency_and_no_dead_tickers():
    v = verified_international()
    assert len(v) >= 20 and not (v["moneda"] == "N/D").any()
    assert {"COP", "BRL", "MXN", "CLP", "EUR", "GBp", "JPY"} <= set(v["moneda"])
    assert not {"PFBCOLOM.CL", "BCOLOMBIA.CL"} & set(v["ticker"])  # sin datos en Yahoo el día de la verificación
    assert place_info("SAP.DE") == ("Alemania", "XETRA", "EUR") and place_info("7203.T")[2] == "JPY"


def test_conversion_table_matches_hand_calculation(yahoo_cop):
    leg = fx_to_base("COP", "USD", DAYS[0], DAYS[-1], now="2026-11-09 16:00 UTC")
    assets = {"ECOPETROL.CL": _asset("ECOPETROL.CL", COP_PRICES, "COP"), "AAPL": _asset("AAPL", AAPL, "USD")}
    result = build_comparison(assets, "Diaria", 252, base_currency="USD", fx_rates={"COP": leg.series})
    (row,) = conversion_rows(result, assets, {"COP": leg})
    assert row["Activo"] == "ECOPETROL.CL" and row["Moneda original"] == "COP" and row["Moneda base"] == "USD"
    assert row["Tasa primer día"] == pytest.approx(1 / 4000.0) and row["Tasa último día"] == pytest.approx(1 / 4020.0)
    assert row["Precio original (último día)"] == 2480.0
    assert row["Precio convertido (último día)"] == pytest.approx(2480.0 / 4020.0)
    assert row["Equivale a (último día)"] == "1 USD = 4,020.00 COP"
    assert row["Consulta"] == "2026-11-09 16:00 UTC"


def test_cop_base_uses_usdcop_and_cross_rate(monkeypatch):
    brlusd = [0.20, 0.21, 0.19, 0.20, 0.22, 0.21]
    fake = _fake_yahoo({"USDCOP=X": (DAYS, USDCOP), "BRLUSD=X": (DAYS, brlusd)})
    monkeypatch.setattr(data, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_fx_to_usd", data.fetch_fx_to_usd)
    usd = fx_to_base("USD", "COP", DAYS[0], DAYS[-1])
    assert usd.ok and usd.series.tolist() == USDCOP
    brl = fx_to_base("BRL", "COP", DAYS[0], DAYS[-1])
    assert brl.ok and "cruce" in brl.pairs
    np.testing.assert_allclose(brl.series.to_numpy(), np.array(brlusd) * np.array(USDCOP))
    assert not fx_to_base("COP", "COP", DAYS[0], DAYS[-1]).ok  # misma moneda: no se convierte


def test_pence_are_divided_by_100():
    a = _asset("HSBA.L", [1300.0, 1310.0], "GBp", index=DAYS[:2])
    norm, note = normalize_minor_units(a)
    assert norm.currency == "GBP" and norm.prices["adjusted_close"].tolist() == [13.0, 13.1]
    assert "GBp" in note and a.prices["adjusted_close"].iloc[0] == 1300.0  # el original no se toca
    same, none = normalize_minor_units(_asset("SAP.DE", [200.0], "EUR", index=DAYS[:1]))
    assert none is None and same.currency == "EUR"


def test_comparison_shows_conversion_box(monkeypatch):
    """Interfaz: al comparar un activo en COP aparece el recuadro «Conversión de monedas». Sin red."""
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    assets = {"ECOPETROL.CL": _asset("ECOPETROL.CL", COP_PRICES, "COP"), "AAPL": _asset("AAPL", AAPL, "USD")}
    monkeypatch.setattr(data, "fetch_many", lambda tickers, s, e, f: {t: assets[t] for t in tickers if t in assets})
    fake = _fake_yahoo({"USDCOP=X": (DAYS, USDCOP)})
    monkeypatch.setattr(data, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_asset_data", fake)
    monkeypatch.setattr(fx_view, "fetch_fx_to_usd", data.fetch_fx_to_usd)
    st.cache_data.clear()
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    at.text_area(key="comparison_tickers_text").input("AAPL, ECOPETROL.CL")
    at.selectbox(key="comparison_frequency").select("Diaria")
    next(b for b in at.button if b.label == "Comparar activos").click().run()
    assert not at.exception
    text = " ".join(m.value for m in at.markdown)
    assert "Conversión de monedas" in text and "esta comparación en <b>USD</b>" in text
    table = next(d.value for d in at.dataframe if "Par usado" in getattr(d.value, "columns", []))
    assert table.iloc[0]["Activo"] == "ECOPETROL.CL" and "USDCOP=X" in table.iloc[0]["Par usado"]
