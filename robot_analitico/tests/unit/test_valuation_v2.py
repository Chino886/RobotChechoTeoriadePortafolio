"""
Fase 2 (v2) - Motor de valoración del caso Alimentos del Norte (guía V2,
9 y 9.1; banco P108, P113-P117, P119). Los controles se calculan a mano.
Las entradas del equipo (crecimiento, CAPEX, depreciación, escenarios) se
fijan aquí solo como valores de prueba. Sin red.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.capm import unlever_beta  # noqa: E402
from src.valuation import (  # noqa: E402
    Scenario,
    budget_target,
    case_cost_of_capital,
    ebit_from_drivers,
    iterate_capital_structure,
    project,
    reinvestment_check,
    value_firm,
)


@pytest.fixture(scope="module")
def params():
    return json.loads((ROOT / "paquete_v2" / "data" / "caso_alimentos_parametros.json").read_text())


def _proj(params, **kw):
    base = dict(sales_growth=[0.03] * 5, capex=[10_000.0] * 5, depreciation=[9_000.0] * 5)
    base.update(kw)
    return project(params, **base)


def test_base_year_reproduces_ebit0(params):
    assert ebit_from_drivers(params["ventas0"], params["costo_variable"], params["gastos_fijos"], params["depreciacion0"]) == 18_000
    assert _proj(params).table.loc[0, "EBIT"] == pytest.approx(params["ebit0"])


def test_projection_mechanics_by_hand(params):
    p = _proj(params)
    t = p.table
    s1 = 150_000 * 1.03
    assert t.loc[1, "ventas"] == pytest.approx(s1)
    assert t.loc[1, "EBIT"] == pytest.approx(s1 * 0.4 - 33_000 - 9_000)
    assert t.loc[1, "ΔNWC"] == pytest.approx(0.12 * (s1 - 150_000))
    assert t.loc[1, "FCFF"] == pytest.approx(t.loc[1, "EBIT"] * 0.65 + 9_000 - 10_000 - 0.12 * (s1 - 150_000))
    assert t.loc[1, "intereses"] == pytest.approx(0.135 * 45_000)
    assert t.loc[1, "FCFE"] == pytest.approx((t.loc[1, "EBIT"] - 0.135 * 45_000) * 0.65 + 9_000 - 10_000 - t.loc[1, "ΔNWC"])
    assert t.loc[1, "deuda/EBITDA"] == pytest.approx(45_000 / (t.loc[1, "EBIT"] + 9_000))


def test_covenant_alert(params):
    ok = _proj(params)
    assert ok.table.loc[1:, "covenant < 3"].all() and not ok.notes
    stressed = _proj(params, sales_growth=[-0.15] * 5)  # caída fuerte de ventas: EBITDA baja
    assert not stressed.table.loc[1:, "covenant < 3"].all()
    assert any("Covenant" in n for n in stressed.notes)


def test_scenarios_fx_lag_and_variable_rate(params):
    base = _proj(params)
    sc = Scenario(fx_shock=0.20, imported_share=0.5, pass_through_lag_days=60)
    shocked = _proj(params, scenario=sc)
    extra = 0.6 * 0.5 * 0.20 * 60 / 365
    s1 = base.table.loc[1, "ventas"]
    assert base.table.loc[1, "EBIT"] - shocked.table.loc[1, "EBIT"] == pytest.approx(s1 * extra)
    assert shocked.table.loc[2, "EBIT"] == pytest.approx(base.table.loc[2, "EBIT"])  # ya trasladado a precios
    rate = _proj(params, scenario=Scenario(kd_shift=0.02))
    assert rate.table.loc[1, "intereses"] == pytest.approx((0.135 + 0.02) * 45_000)
    assert rate.table.loc[1, "utilidad neta"] < base.table.loc[1, "utilidad neta"]


def test_budget_target_and_ebit_gap_p113_p114(params):
    p = _proj(params)
    ke = 0.18
    gap = budget_target(p, ke, params["patrimonio_libros"])
    assert gap.required_net_income == pytest.approx(0.18 * 60_000)
    ebit_req = 0.18 * 60_000 / 0.65 + 0.135 * 45_000
    assert gap.required_ebit == pytest.approx(ebit_req)
    assert gap.gap_by_year.loc[1] == pytest.approx(ebit_req - p.table.loc[1, "EBIT"])


def test_fcfe_and_fcff_both_reported_and_terminal_guard_p116_p117(params):
    p = _proj(params)
    v = value_firm(p, wacc_rate=0.14, ke=0.18, growth=0.045)
    assert v.equity_fcff == pytest.approx(v.enterprise_value - 45_000)
    assert v.difference == pytest.approx(v.equity_fcfe - v.equity_fcff)
    assert "coinciden" in v.explanation
    with pytest.raises(ValueError):
        value_firm(p, wacc_rate=0.04, ke=0.18, growth=0.045)  # WACC <= g


def test_capital_structure_iteration_converges_p108_p119(params):
    beta_u = unlever_beta(0.0424 / 0.028, params["de_comparable"], params["tax_supuesto"])
    p = _proj(params, sales_growth=[0.05] * 5, capex=[9_500.0] * 5)
    steps = iterate_capital_structure(params, p, beta_u, growth=0.045, start_de=params["de_empresa"], tol=1e-8)
    assert len(steps) > 1
    last = steps[-1]
    assert abs(45_000 / last.equity - last.debt_to_equity) < 1e-6  # D/E coherente con el patrimonio estimado
    cc = case_cost_of_capital(params, beta_u, last.debt_to_equity)
    assert cc.wacc == pytest.approx(last.wacc) and cc.ke_cop == pytest.approx(last.ke_cop)


def test_reinvestment_consistency_check(params):
    p = _proj(params, sales_growth=[0.045] * 5, capex=[9_000.0] * 5)  # CAPEX = depreciación
    chk = reinvestment_check(p, growth=0.045, roic=0.15)
    assert chk.required_rate == pytest.approx(0.3)
    assert not chk.consistent  # crecer 4,5 % sin reinversión neta suficiente no es coherente
