"""Rebalanceo en modo mercado: la tabla trae los activos elegidos (no A y B del caso docente). Sin red."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import laboratorio_v2  # noqa: E402
from tests.unit.test_lab_currency_beta_ui_v2 import _market  # noqa: E402


def test_market_rebalance_uses_chosen_universe_and_real_prices(monkeypatch):
    from streamlit.testing.v1 import AppTest

    comparison, remote = _market()
    monkeypatch.setattr(laboratorio_v2, "fetch_asset_data", lambda t, s, e: remote[t])
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.session_state["comparison_result"] = comparison
    at.run()
    at.selectbox(key="lab_source").set_value(laboratorio_v2.SOURCE_MARKET).run()
    assert not at.exception
    caps = [c.value for c in at.caption if "paper trading" in c.value]
    assert caps and "los 3 del universo" in caps[0] and "rebalanceo_control.json" not in caps[0]
    last2 = comparison.common_prices["AAA"].dropna().index[-2:]
    assert str(last2[0].date()) in caps[0] and str(last2[1].date()) in caps[0]  # sus dos últimos precios reales
    assert any("cantidades" in i.value and "no las inventa" in i.value for i in at.info)
    # el caso docente sigue igual (A y B del archivo de control)
    at.selectbox(key="lab_source").set_value(laboratorio_v2.SOURCE_TWO).run()
    assert not at.exception
    assert any("rebalanceo_control.json" in c.value for c in at.caption)


def test_target_weights_can_come_from_lab_results(monkeypatch):
    from streamlit.testing.v1 import AppTest

    comparison, remote = _market()
    monkeypatch.setattr(laboratorio_v2, "fetch_asset_data", lambda t, s, e: remote[t])
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.session_state["comparison_result"] = comparison
    at.run()
    at.selectbox(key="lab_source").set_value(laboratorio_v2.SOURCE_MARKET).run()
    sel = at.selectbox(key="lab_reb_target_real")
    opts = list(sel.options)
    assert opts[0] == laboratorio_v2.TARGET_EQUAL and laboratorio_v2.TARGET_MANUAL in opts
    gmv = next(o for o in opts if o.startswith("Markowitz · GMV"))
    assert any(o.startswith("Black-Litterman") for o in opts)
    assert any("Suma de pesos objetivo: **100.00%**" in c.value for c in at.caption)
    sel.set_value(gmv).run()
    assert not at.exception
    assert any("Suma de pesos objetivo" in c.value for c in at.caption)
