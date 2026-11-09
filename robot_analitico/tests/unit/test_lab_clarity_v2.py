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


def test_risk_profile_sets_gamma_and_personal_portfolio():
    """Laboratorio: se elige Conservador/Moderado/Agresivo y el bot usa γ = 10/5/2; Personalizado pide el número."""
    at = _app()
    box = at.selectbox(key="lab_risk_profile")
    assert box.value == "Moderado" and box.options == ["Conservador", "Moderado", "Agresivo", "Personalizado"]
    assert not any(n.key == "lab_gamma" for n in at.number_input)

    def personal_weight_of_first_asset():
        for d in at.dataframe:
            v = d.value
            col = "Óptimo personal (utilidad media-varianza)"
            if col in map(str, getattr(v, "columns", [])) and "A" in map(str, v.index):
                return v.loc["A", col]
        raise AssertionError("no está la tabla de Markowitz")

    shown = {}
    for name in ("Conservador", "Moderado", "Agresivo"):
        at.selectbox(key="lab_risk_profile").set_value(name).run()
        assert not at.exception
        assert any(f"γ = {g:g}" in c.value for c, g in [(c, {"Conservador": 10, "Moderado": 5, "Agresivo": 2}[name])
                                                         for c in at.caption])
        shown[name] = personal_weight_of_first_asset()
    # A es el activo de menor riesgo del caso docente: un perfil más conservador pone más en A.
    assert shown["Moderado"] == "57.14%"  # mismo resultado de siempre (γ = 5 del ejemplo del profesor)
    pct = {k: float(v.rstrip("%")) for k, v in shown.items()}
    assert pct["Conservador"] > pct["Moderado"] > pct["Agresivo"]

    at.selectbox(key="lab_risk_profile").set_value("Personalizado").run()
    assert not at.exception and any(n.key == "lab_gamma" for n in at.number_input)


def test_valuation_uses_the_kd_typed_by_the_user():
    """M8: el Kd de la casilla debe llegar a la proyección (intereses, FCFE) y no solo al WACC mostrado."""
    at = _app()

    def interest_and_debt():
        for d in at.dataframe:
            v = getattr(d.value, "data", d.value)  # Styler → DataFrame
            if "intereses" in map(str, getattr(v, "columns", [])):
                return float(v.loc[1, "intereses"])
        raise AssertionError("no está la tabla de proyección")

    base_interest = interest_and_debt()
    at.number_input(key="lab_val_kd").set_value(0.20).run()
    assert not at.exception
    interest = interest_and_debt()
    assert abs(interest / base_interest - 0.20 / 0.135) < 1e-9  # intereses = Kd × deuda al inicio del año
