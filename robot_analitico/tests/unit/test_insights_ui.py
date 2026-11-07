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
