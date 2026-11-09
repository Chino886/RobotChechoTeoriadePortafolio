"""
Botón «¿Necesitas ayuda?»: contenido para cada sección y módulo, siguiente paso según el estado
de la sesión, sin lenguaje de recomendación de inversión, y visible solo tras los consentimientos. Sin red.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src import help_assistant as ha  # noqa: E402
from src.help_ui import panel_html  # noqa: E402

TABS = ["Inicio", "Tickers", "Preselección de activos", "Tasas soberanas", "Laboratorio de portafolios",
        "DPST Insights"]


def _lab():
    from laboratorio_v2 import LAB_MODULES, MODULE_TITLES, SOURCE_MARKET
    return LAB_MODULES, MODULE_TITLES, SOURCE_MARKET


def _all_texts():
    out = [ha.DISCLAIMER]
    for s in ha.SECTIONS:
        out += [s.label, s.path, *s.steps, *(x for qa in s.faqs for x in qa)]
    for steps, faqs in ha.LAB_MODULE_HELP:
        out += [*steps, *(x for qa in faqs for x in qa)]
    out += [x for pair in ha.GLOSSARY for x in pair]
    return out


def test_every_section_has_help():
    assert [s.label for s in ha.SECTIONS] == TABS
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"Inicio", "Tickers", "Preselección de activos", "Tasas soberanas", LAB_TITLE, INSIGHTS_TITLE' in src
    assert f'LAB_TITLE = "{ha.LAB_SECTION}"' in src
    assert len({s.slug for s in ha.SECTIONS}) == len(ha.SECTIONS)
    for s in ha.SECTIONS:
        assert 2 <= len(s.steps) <= 3, s.label
        assert 3 <= len(s.faqs) <= 5, s.label
        assert s.path.startswith("Menú → ")
        for _q, a in s.faqs:
            assert len(a) <= 170, a  # respuesta de máximo dos líneas


def test_every_lab_module_has_help():
    modules, titles, _ = _lab()
    assert len(ha.LAB_MODULE_HELP) == len(modules) == len(titles)
    for steps, faqs in ha.LAB_MODULE_HELP:
        assert 2 <= len(steps) <= 3
        assert 2 <= len(faqs) <= 5
        assert all(len(a) <= 170 for _q, a in faqs)


def _state(**kw):
    base = dict(has_asset=False, has_comparison=False, lab_uses_market=False, markowitz_done=False)
    base.update(kw)
    return base


def test_next_step_without_data():
    steps = ha.next_steps(**_state())
    assert len(steps) == 1 and "Preselección de activos → Comparación" in steps[0] and "Tickers" in steps[0]
    assert ha.next_target(**_state())[1:3] == ("Preselección de activos", "Comparación")


def test_next_step_with_one_asset_asks_for_comparison():
    steps = ha.next_steps(**_state(has_asset=True))
    assert "Comparación" in steps[0] and "varias empresas" in steps[0]


def test_next_step_with_data_but_lab_not_on_market():
    steps = ha.next_steps(**_state(has_asset=True, has_comparison=True))
    assert "Mercado real" in steps[0] and "Fuente" in steps[0]
    assert ha.next_target(**_state(has_comparison=True))[1] == ha.LAB_SECTION


def test_next_step_with_market_suggests_markowitz():
    st_ = _state(has_comparison=True, lab_uses_market=True)
    assert "Markowitz" in ha.next_steps(**st_)[0]
    modules, _, _ = _lab()
    assert ha.next_target(**st_)[3] == "3 · Markowitz y fronteras" in modules


def test_next_step_after_markowitz():
    st_ = _state(has_comparison=True, lab_uses_market=True, markowitz_done=True)
    first = ha.next_steps(**st_)[0]
    assert "Ficha técnica" in first and "DPST Insights" in first
    modules, _, _ = _lab()
    assert ha.next_target(**st_)[3] == "8 · Ficha técnica" in modules


def test_next_step_shows_status_errors_with_explanation():
    issues = [("Yahoo Finance · históricos", "Sin conexión", "Revisa internet y vuelve a probar."),
              ("FRED · tasas", "Falta configuración", "Falta la clave de API."),
              ("Otro", "Error", "x")]
    steps = ha.next_steps(**_state(), issues=issues)
    assert len(steps) == 3  # paso principal + 2 avisos como máximo
    assert "Comparación" in steps[0]
    assert "Yahoo Finance" in steps[1] and "Revisa internet" in steps[1]
    assert "FRED" in steps[2]


def test_session_summary_reads_state():
    from src.insights import CTX_KEY
    from src.status_ui import REASONS, SERVICES, STATE_KEY, STATES
    _, _, market = _lab()

    class Ok:
        ok = True

    kw = dict(service_names=SERVICES, state_labels=STATES, reasons=REASONS, conn_key=STATE_KEY,
              ctx_key=CTX_KEY, market_source=market)
    empty = ha.session_summary({}, **kw)
    assert empty == {"has_asset": False, "has_comparison": False, "lab_uses_market": False,
                     "markowitz_done": False, "issues": []}
    full = ha.session_summary({"asset_result": Ok(), "comparison_result": Ok(), "lab_source": market,
                               CTX_KEY: {"markowitz": {}},
                               STATE_KEY: {"yahoo_hist": {"status": "offline"}, "fred": {"status": "ok"}}}, **kw)
    assert full["has_asset"] and full["has_comparison"] and full["lab_uses_market"] and full["markowitz_done"]
    assert full["issues"] == [(SERVICES["yahoo_hist"][0], STATES["offline"][0], REASONS["offline"])]
    # Markowitz del caso docente no cuenta como «ya calculaste tu cartera»
    docente = ha.session_summary({"comparison_result": Ok(), "lab_source": "Caso docente", CTX_KEY: {"markowitz": {}}}, **kw)
    assert not docente["markowitz_done"]


def test_no_investment_advice_language():
    modules, titles, _ = _lab()
    texts = _all_texts()
    states = [_state(), _state(has_asset=True), _state(has_comparison=True),
              _state(has_comparison=True, lab_uses_market=True),
              _state(has_comparison=True, lab_uses_market=True, markowitz_done=True)]
    for st_ in states:
        texts += ha.next_steps(**st_) + [ha.next_target(**st_)[0]]
        texts.append(re.sub(r"<[^>]+>", " ", panel_html(modules, titles, {**st_, "issues": []})))
    pattern = re.compile(r"\b(" + "|".join(re.escape(w) for w in ha.FORBIDDEN) + r")\b", re.IGNORECASE)
    bad = [t for t in texts if pattern.search(t)]
    assert not bad, bad


def test_panel_order_and_disclaimer():
    modules, titles, _ = _lab()
    h = panel_html(modules, titles, {**_state(), "issues": []})
    order = ["Estás en:", "Qué puedes hacer aquí", "Siguiente paso recomendado", "Preguntas frecuentes",
             "Glosario rápido", ha.DISCLAIMER]
    pos = [h.index(x) for x in order]
    assert pos == sorted(pos)
    assert 'data-dpst-help="close"' in h.replace("'", '"') and "data-dpst-help='search'" in h
    for s in ha.SECTIONS:
        assert f"data-sec='{s.slug}'" in h
    for i in range(1, len(modules) + 1):
        assert f"data-mod='{i}'" in h


def _run(consent: bool):
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    if consent:
        at.session_state["intro_ack"] = True
        at.session_state["terms_accepted"] = True
    at.run()
    assert not at.exception
    return at


def test_help_button_only_after_consent():
    before = _run(False)
    assert not any("dpst-help" in m.value for m in before.markdown)
    after = _run(True)
    assert any("class='dpst-help'" in m.value and ha.DISCLAIMER in m.value for m in after.markdown)


def test_optional_news_quota_is_not_a_help_warning():
    from src.insights import CTX_KEY
    from src.status_ui import REASONS, SERVICES, STATE_KEY, STATES
    _, _, market = _lab()
    kw = dict(service_names=SERVICES, state_labels=STATES, reasons=REASONS, conn_key=STATE_KEY,
              ctx_key=CTX_KEY, market_source=market)
    quota = ha.session_summary({STATE_KEY: {"alpha_vantage": {"status": "limit"}}}, **kw)
    assert quota["issues"] == []
    nokey = ha.session_summary({STATE_KEY: {"alpha_vantage": {"status": "nokey"}}}, **kw)
    assert len(nokey["issues"]) == 1  # sin clave sí se avisa: tiene arreglo
