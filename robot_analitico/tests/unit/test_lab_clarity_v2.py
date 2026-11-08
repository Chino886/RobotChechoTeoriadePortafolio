"""
Laboratorio claro para un usuario nuevo: ayuda (?) en cada casilla, "¿Cómo leo esto?" en gráficas y tablas,
nombres propios en lugar de A/B en el caso docente y casillas sin valores inválidos. Sin red.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def _app():
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180)
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    assert not at.exception
    return at


def test_every_lab_input_has_help_and_charts_tables_have_guide():
    at = _app()
    widgets = [*at.number_input, *at.text_input, *at.selectbox, *at.slider, *at.toggle]
    lab = [w for w in widgets if str(getattr(w, "key", "") or "").startswith("lab_")]
    assert lab and all(getattr(w, "help", None) for w in lab), [w.key for w in lab if not getattr(w, "help", None)]
    guides = [c for c in at.caption if c.value == "¿Cómo leo esto?" and c.help]
    assert len(guides) >= 10


def test_teaching_case_uses_the_names_the_user_types():
    at = _app()
    at.text_input(key="lab_name_a").input("Apple").run()
    at.text_input(key="lab_name_b").input("Microsoft").run()
    assert not at.exception
    cols = set()
    for d in at.dataframe:
        v = d.value
        cols |= set(map(str, getattr(v, "columns", []))) | set(map(str, getattr(v, "index", [])))
    assert {"Apple", "Microsoft"} <= cols and "A" not in cols


def test_number_inputs_start_on_a_valid_step():
    """El navegador marca «Ingresa un valor válido» si el valor no es mínimo + k·paso."""
    at = _app()
    for w in at.number_input:
        p = w.proto
        if getattr(p, "has_min", False) and p.step and w.value is not None:
            k = (w.value - p.min) / p.step
            assert math.isclose(k, round(k), abs_tol=1e-6), (w.key, p.min, p.step, w.value)
