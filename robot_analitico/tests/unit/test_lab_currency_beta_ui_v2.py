"""
Laboratorio con datos de mercado simulados: moneda base COP con USDCOP=X, tabla de betas
(OLS, Cov/Var, alfa), beta de cada cartera y Hamada con entradas del equipo en cero. Sin red.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import laboratorio_v2  # noqa: E402
from src.comparison import build_comparison  # noqa: E402
from src.data import AssetData  # noqa: E402


def _market():
    rng = np.random.default_rng(3)
    idx = pd.bdate_range("2024-01-01", periods=260)
    m = rng.normal(0.0004, 0.01, len(idx))
    def path(beta, s):
        return 100 * np.cumprod(1 + beta * m + rng.normal(0, s, len(idx)))
    assets = {t: AssetData(t, True, pd.DataFrame({"adjusted_close": path(b, s)}, index=idx), currency="USD")
              for t, b, s in (("AAA", 0.7, 0.006), ("BBB", 1.2, 0.008), ("CCC", 1.5, 0.01))}
    bench = AssetData("^GSPC", True, pd.DataFrame({"adjusted_close": 4000 * np.cumprod(1 + m)}, index=idx), currency="USD")
    fx_idx = pd.bdate_range("2023-12-20", periods=275)
    fx = AssetData("USDCOP=X", True, pd.DataFrame({"adjusted_close": 4000 * np.cumprod(1 + rng.normal(0, 0.004, len(fx_idx)))},
                                                  index=fx_idx), currency="COP")
    return build_comparison(assets, "Diaria", 252), {"^GSPC": bench, "USDCOP=X": fx}


def test_lab_cop_base_currency_betas_portfolio_betas_and_hamada(monkeypatch):
    from streamlit.testing.v1 import AppTest

    comparison, remote = _market()
    assert comparison.ok
    monkeypatch.setattr(laboratorio_v2, "fetch_asset_data", lambda t, s, e: remote[t])
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.session_state["comparison_result"] = comparison
    at.run()
    at.radio(key="lab_source").set_value(laboratorio_v2.SOURCE_MARKET).run()
    assert not at.exception
    base = at.selectbox(key="lab_base_currency")
    assert base.value == "USD"  # por defecto; la moneda del mandato la decide el equipo
    assert "decisión del equipo" in base.label
    base.set_value("COP").run()
    assert not at.exception
    assert any("Moneda base: COP" in c.value and "USDCOP=X" in c.value for c in at.caption)
    traces = [json.loads(j.value) if isinstance(j.value, str) else j.value for j in at.json]
    trace = next(t for t in traces if isinstance(t, dict) and "analysis_id" in t)
    assert trace["currency"] == "COP"
    assert any("USDCOP=X" in t for t in trace["transformations"])

    at.text_input(key="lab_beta_bench").input("^GSPC").run()
    assert not at.exception
    betas = next(d.value for d in at.dataframe if "beta (Cov/Var)" in getattr(d.value, "columns", []))
    assert {"beta (OLS)", "beta (Cov/Var)", "alfa (por periodo)"} <= set(betas.columns)
    np.testing.assert_allclose(betas["beta (OLS)"], betas["beta (Cov/Var)"], atol=1e-10)  # P2-31
    carteras = next(d.value for d in at.dataframe if "beta de cartera" in getattr(d.value, "columns", []))
    assert len(carteras) == 4 and carteras["beta de cartera"].notna().all()

    for key in ("lab_hamada_de", "lab_hamada_tax", "lab_hamada_bd", "lab_hamada_target"):
        assert at.number_input(key=key).value == 0.0  # vacíos: no se copian los del caso Alimentos
    hamada = [m for m in at.metric if "Beta" in m.label]
    assert hamada[0].value == hamada[1].value == hamada[2].value  # todo en 0: la beta no cambia
