"""DPST Financial Insights: explica con valores de la sesión, no recomienda, no inventa cifras."""
from dataclasses import asdict

from src.insights import answer, answer_html, context_options, detect_topic, is_advice_request, record
from src.ui_fx import icon

ASSET = {"ticker": "AAPL", "freq": "Diaria", "n": 1004, "mean": 0.2215, "vol": 0.24, "dd": -0.3048,
         "start": "2023-01-03", "end": "2026-11-06"}


def test_never_recommends_buying_or_selling():
    for q in ("¿Debo comprar AAPL?", "¿Qué acción me recomiendas?", "¿Vendo o no?", "¿En qué invierto?"):
        a = answer(q, ASSET, None, {})
        assert a.refused and not a.indicator
    assert not is_advice_request("Explícame qué significa esta volatilidad y cómo debo interpretarla")
    assert not is_advice_request("Quiero comprender la beta")


def test_uses_real_session_values_and_marks_assumptions():
    a = answer("Explícame qué significa esta volatilidad y cómo debo interpretarla", ASSET, None, {},
               ("asset_vol", "Volatilidad anual de AAPL", "volatility"))
    assert a.has_data and "24.00%" in a.indicator[0] and "1004" in a.indicator[0]
    assert "supuesto" in a.example and a.limitations
    html = answer_html(asdict(a), icon)
    for part in ("Explicación sencilla", "Interpretación financiera", "Indicador utilizado", "Limitaciones",
                 "Ejemplo educativo", "Valores reales de tu sesión"):
        assert part in html


def test_without_results_it_says_so_and_invents_nothing():
    for q in ("¿Qué es la beta?", "¿Qué representa el Sharpe Ratio?", "¿Cómo leo la frontera eficiente?",
              "¿Qué significan los resultados de Black-Litterman?", "¿Cómo interpreto el pronóstico?",
              "¿Qué representan las tasas soberanas?", "¿Qué significa diversificar?"):
        a = answer(q, None, None, {})
        assert not a.has_data and a.indicator and not any(ch.isdigit() for ch in " ".join(a.indicator)), q
        assert "Sin resultado en la sesión" in answer_html(asdict(a), icon)


def test_recorded_lab_values_are_used_verbatim():
    state = {}
    record(state, "capm", "Beta y desempeño frente a SPY", {"bench": "SPY", "window": "2020-01-01 a 2024-12-31",
           "rows": [{"cartera": "GMV", "beta": 0.8123, "r2": 0.5, "sharpe": 0.41}]})
    ctx = state["insights_ctx"]
    a = answer("¿Qué es la beta?", None, None, ctx)
    assert a.has_data and any("0.812" in x for x in a.indicator)
    assert ("capm", "Beta y desempeño frente a SPY", "beta") in context_options(None, None, ctx)
    assert detect_topic("¿Cómo interpreto los resultados de Markowitz?") == "markowitz"


def test_deep_analysis_uses_session_values_and_follow_ups():
    asset = dict(ASSET, recent_vol=0.30, recent_mean=0.10, n_recent=252, partial=False, std=0.015, min=-0.09,
                 kurt=6.0, skew=-0.4, median=0.001, mean_pp=0.0009)
    comparison = {"rows": [{"ticker": "AAPL", "mean": 0.22, "vol": 0.24, "rvr": 0.92, "dd": -0.30},
                           {"ticker": "MSFT", "mean": 0.18, "vol": 0.20, "rvr": 0.90, "dd": -0.25}],
                  "window": "2023-01-03 a 2026-11-06", "currency": "USD", "nd": {"AAPL", "MSFT"}}
    a = answer("¿Qué tan riesgoso es AAPL?", asset, comparison, {})
    text = " ".join(a.analysis)
    assert "30.00%" in text and "24.00%" in text and "+25%" in text  # ventana reciente vs muestra completa
    assert "curtosis 6.00" in text and "puesto 1 de 2 en media" in text
    assert a.followups and "Análisis de tus resultados" in answer_html(asdict(a), icon)
    cmp_ = answer("Compara AAPL y MSFT", asset, comparison, {})
    assert cmp_.topic == "compare" and any("AAPL vs MSFT" in x and "+4.00%" in x for x in cmp_.analysis)
    ctx = {"markowitz": {"label": "M", "ts": "t", "values": {"rf_ea": 0.03, "n_assets": 2, "n_frontier": 10, "rows": [
        {"cartera": "Mínima varianza global", "ok": True, "ret": 0.05, "vol": 0.10, "sharpe": 0.1, "weights": {"A": 0.6, "B": 0.4}},
        {"cartera": "Tangente (máximo Sharpe)", "ok": True, "ret": 0.08, "vol": 0.14, "sharpe": 0.2, "weights": {"A": 0.3, "B": 0.7}}]}}}
    first = answer("¿Cómo interpreto los resultados de Markowitz?", None, None, ctx)
    follow = answer("¿y la tangente?", None, None, ctx, previous_topic=first.topic)
    assert follow.topic == "markowitz" and follow.analysis[0].startswith("Tangente") and "+3.00%" in follow.analysis[0]
