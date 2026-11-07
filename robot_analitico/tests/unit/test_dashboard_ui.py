"""Dashboard de Inicio: solo presentación de lo que ya hay en la sesión."""
from datetime import datetime, timezone
from types import SimpleNamespace

import pandas as pd

from src.dashboard import (KPI_DEFAULT_ORDER, Kpi, Service, TrackedAsset, dashboard_html, spark_data,
                           track_activity)


def _asset(ticker="AAPL"):
    idx = pd.date_range("2024-01-01", periods=300, freq="B")
    return SimpleNamespace(ok=True, ticker=ticker, prices=pd.DataFrame({"adjusted_close": range(1, 301)}, index=idx))


def test_spark_keeps_real_first_and_last_points():
    s = pd.Series(range(1, 301), index=pd.date_range("2024-01-01", periods=300, freq="B"), dtype=float)
    sp = spark_data(s)
    assert sp["v"][0] == 1.0 and sp["v"][-1] == 300.0
    assert sp["d"][-1] == str(s.index[-1].date()) and len(sp["v"]) <= 62
    assert spark_data(s.iloc[:1]) is None and spark_data(None) is None


def test_activity_logs_each_result_once():
    state = {}
    now = datetime(2026, 11, 7, 21, 30, tzinfo=timezone.utc)
    assert track_activity(state, "Lab", now) == []
    res = _asset()
    state["asset_result"] = res
    ev = track_activity(state, "Lab", now)
    assert len(ev) == 1 and ev[0]["title"].endswith("AAPL") and ev[0]["ts"] == "2026-11-07T21:30:00Z"
    assert len(track_activity(state, "Lab", now)) == 1  # mismo objeto: no se repite
    state["asset_result"] = _asset("KO")
    assert [e["title"] for e in track_activity(state, "Lab", now)][-1].endswith("KO")
    state["conn_check_log"] = [{"hora (UTC)": "2026-11-07 21:31:00", "servicio": "x", "estado": "conectado"}]
    assert track_activity(state, "Lab", now)[-1]["detail"] == "1 de 1 servicios conectados"


def test_dashboard_html_shows_given_values_and_all_cards():
    kpis = [Kpi(i, "info", i.upper(), f"v-{i}", "nota", "ayuda") for i in KPI_DEFAULT_ORDER]
    html = dashboard_html(kpis, [TrackedAsset("AAPL", "Datos del activo", mean_annual=0.1234, vol_annual=0.2)], [],
                          [Service("FRED · tasas", "idle", "sin probar")], "estado")
    for i in KPI_DEFAULT_ORDER:
        assert f'data-kpi="{i}"' in html and f"v-{i}" in html
    assert "12.34%" in html and "20.00%" in html  # mismos valores que recibe, solo con formato
    assert 'data-fav="AAPL"' in html and "data-dash-reset" in html and "data-dash-edit" in html
