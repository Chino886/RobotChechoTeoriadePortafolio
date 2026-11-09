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
    at.selectbox(key="lab_source").set_value(laboratorio_v2.SOURCE_MARKET).run()
    assert not at.exception
    base = at.selectbox(key="lab_base_currency")
    assert base.value == "USD"  # por defecto; la moneda del mandato la decide el equipo
    assert "Decisión del equipo" in base.help  # la barra de supuestos lo dice también en su título
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


def test_lab_performance_capm_and_factsheet(monkeypatch):
    from streamlit.testing.v1 import AppTest

    comparison, remote = _market()
    monkeypatch.setattr(laboratorio_v2, "fetch_asset_data", lambda t, s, e: remote[t])
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.session_state["comparison_result"] = comparison
    at.run()
    at.selectbox(key="lab_source").set_value(laboratorio_v2.SOURCE_MARKET).run()
    at.text_input(key="lab_beta_bench").input("^GSPC").run()
    assert not at.exception
    frames = [d.value for d in at.dataframe]

    def frame_with(col):
        return next(f for f in frames if col in getattr(f, "columns", []))

    betas = frame_with("riesgo sistemático")
    np.testing.assert_allclose(betas["riesgo sistemático"] + betas["riesgo no sistemático"], 1.0)
    capm = frame_with("requerido CAPM")
    assert {"AAA", "BBB", "CCC", "Tangente (máximo Sharpe)"} <= set(capm["activo o cartera"])
    perf = frame_with("alfa de Jensen")
    assert {"Sharpe", "Treynor", "razón de información", "error de seguimiento"} <= set(perf.columns)
    assert "1/N (referencia simple)" in perf.index and "Benchmark ^GSPC" in perf.index
    assert perf.loc["Benchmark ^GSPC", "beta"] == 1.0 or abs(perf.loc["Benchmark ^GSPC", "beta"] - 1.0) < 1e-9

    # Ficha técnica (estructura de la Superfinanciera) de la tangente, con rentabilidad por ventanas.
    assert at.selectbox(key="lab_factsheet_choice").value == "Tangente (máximo Sharpe)"
    windows = next(f for f in frames if "Último año" in getattr(f, "columns", []))
    assert {"Último mes", "Últimos 6 meses", "Año corrido", "Últimos 3 años"} <= set(windows.columns)
    assert any("Superintendencia Financiera" in c.value for c in at.caption)
    for choice in ("Mínimo riesgo (GMV)", "Mayor rendimiento esperado"):
        at.selectbox(key="lab_factsheet_choice").set_value(choice).run()
        assert not at.exception


def test_factsheet_with_teaching_case_has_no_history():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    assert not at.exception
    assert at.selectbox(key="lab_factsheet_choice").value == "Tangente (máximo Sharpe)"
    assert any("| Fecha de corte | N/D" in md.value for md in at.markdown)
    assert any("N/D: esta fuente no tiene serie de precios" in c.value for c in at.caption)


def test_basket_signal_board_and_expected_shortfall(monkeypatch):
    """Canasta: tablero de señales con entrada, stop-loss, take-profit, VaR y ES por activo y modelo."""
    import src.data
    from streamlit.testing.v1 import AppTest

    idx = pd.bdate_range("2023-01-02", periods=700)

    def fake(ticker, start, end):
        rng = np.random.default_rng(abs(hash(ticker)) % 1000)
        p = 50 * np.cumprod(1 + rng.normal(0.0006, 0.012, len(idx)))
        return AssetData(ticker, True, pd.DataFrame({"adjusted_close": p}, index=idx), currency="USD")

    monkeypatch.setattr(src.data, "fetch_asset_data", fake)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    next(b for b in at.button if b.label == "Pronosticar canasta").click().run()
    assert not at.exception
    board = next(d.value for d in at.dataframe if "stop-loss" in getattr(d.value, "columns", []))
    assert {"entrada", "take-profit", "equilibrio (P_BE)", "señal", "motivo"} <= set(board.columns)
    es_col = next(c for c in board.columns if c.startswith("ES "))
    var_col = next(c for c in board.columns if c.startswith("VaR "))
    assert (board[es_col] >= board[var_col] - 1e-12).all()
    assert any("no ejecuta órdenes" in c.value for c in at.caption)


def test_single_asset_risk_shows_expected_shortfall(monkeypatch):
    import src.data
    from streamlit.testing.v1 import AppTest

    idx = pd.bdate_range("2021-01-04", periods=1200)
    p = 100 * np.cumprod(1 + np.random.default_rng(9).normal(0.0004, 0.015, len(idx)))
    monkeypatch.setattr(src.data, "fetch_asset_data",
                        lambda t, s, e: AssetData(t, True, pd.DataFrame({"adjusted_close": p}, index=idx), currency="USD"))
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=300)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    next(b for b in at.button if b.label == "Descargar y limpiar").click().run()
    assert not at.exception
    labels = {m.label: m.value for m in at.metric}
    es = next(v for k, v in labels.items() if k.startswith("Pérdida esperada ES"))
    var = next(v for k, v in labels.items() if k.startswith("VaR fraccional"))
    assert float(es.rstrip("%")) >= float(var.rstrip("%"))
    # Descriptivos: los valores exactos van en una tabla legible, no como diccionario en formato código.
    exact = next(d.value for d in at.dataframe if "Indicador" in getattr(d.value, "columns", []))
    assert {"Muestra completa", "Media por periodo", "Volatilidad anualizada"} & (set(exact.columns) | set(exact["Indicador"]))
    assert not any("mediana" in str(j.value) for j in at.json)  # el único JSON es la traza de Exportar
