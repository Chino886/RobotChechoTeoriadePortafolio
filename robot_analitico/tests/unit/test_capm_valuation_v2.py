"""
Fase 2 (v2) - Beta, CAPM, apalancamiento y valoración (guía V2, secc. 8-9).

Pruebas de aceptación: P2-31, P2-32, P2-33, P2-34, con el caso docente
congelado Alimentos del Norte (paquete_v2/data/caso_alimentos_*.json/csv).
Los controles se calculan a mano (sumas de desviaciones), no con el módulo.
Sin red.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.capm import (  # noqa: E402
    beta_ols,
    cost_of_equity,
    discounted_cash_flow,
    equity_value,
    fcfe,
    fcff,
    nominal_rate_to_other_currency,
    relever_beta,
    sml_required_return,
    stable_reinvestment_rate,
    terminal_value,
    unlever_beta,
    wacc,
)

PAQUETE = ROOT / "paquete_v2" / "data"


@pytest.fixture(scope="module")
def case():
    params = json.loads((PAQUETE / "caso_alimentos_parametros.json").read_text())
    returns = pd.read_csv(PAQUETE / "caso_alimentos_retornos.csv").set_index("anio")
    return params, returns


def test_beta_manual_equals_ols_and_constant_benchmark_p2_31(case):
    params, r = case
    # Control a mano: medias 10 % y 8 %; sum(dc*dm) = 0,0424; sum(dm^2) = 0,028.
    manual = 0.0424 / 0.028
    res = beta_ols(r["comparable"], r["referencia"], rf=params["rf_USD"])
    assert res.status == "ok" and res.n == 6
    assert res.beta == pytest.approx(manual, abs=1e-10)
    assert res.beta_cov_ratio == pytest.approx(res.beta, abs=1e-12)  # OLS = Cov/Var en la misma muestra
    assert res.ci95[0] < res.beta < res.ci95[1] and 0 <= res.r_squared <= 1

    constant = beta_ols(r["comparable"], pd.Series(0.05, index=r.index))
    assert constant.status == "indefinido" and np.isnan(constant.beta)

    # Con rf variable, la beta de excesos puede diferir de la de retornos brutos.
    rf_var = pd.Series([0.01, 0.02, 0.03, 0.05, 0.04, 0.02], index=r.index)
    assert beta_ols(r["comparable"], r["referencia"], rf=rf_var).beta != pytest.approx(manual, abs=1e-6)


def test_hamada_round_trip_same_assumptions_p2_32(case):
    params, _ = case
    beta_l = 0.0424 / 0.028
    tax = params["tax_supuesto"]
    beta_u = unlever_beta(beta_l, params["de_comparable"], tax)
    assert beta_u == pytest.approx(beta_l / (1 + (1 - tax) * 0.60), abs=1e-12)
    assert relever_beta(beta_u, params["de_comparable"], tax) == pytest.approx(beta_l, abs=1e-12)  # ida y vuelta
    target = relever_beta(beta_u, params["de_empresa"], tax)
    assert target == pytest.approx(beta_u * (1 + (1 - tax) * 0.75), abs=1e-12)
    # Con beta de deuda distinta de cero, ida y vuelta también cierra con el mismo supuesto.
    bu_d = unlever_beta(beta_l, 0.6, tax, beta_debt=0.2)
    assert relever_beta(bu_d, 0.6, tax, beta_debt=0.2) == pytest.approx(beta_l, abs=1e-12)
    assert bu_d != pytest.approx(beta_u)


def test_capm_country_inflation_currency_without_double_count_p2_33(case):
    params, _ = case
    beta_u = unlever_beta(0.0424 / 0.028, params["de_comparable"], params["tax_supuesto"])
    beta_l = relever_beta(beta_u, params["de_empresa"], params["tax_supuesto"])
    ke = cost_of_equity(params["rf_USD"], beta_l, params["erp_madura"], params["proxy_pais"], params["lambda"])
    assert ke.base == pytest.approx(0.043 + beta_l * 0.055, abs=1e-12)
    assert ke.country_premium == pytest.approx(0.032, abs=1e-12)  # se muestra aparte, una sola vez
    assert ke.ke == pytest.approx(ke.base + 0.032, abs=1e-12)
    ke_cop = nominal_rate_to_other_currency(ke.ke, params["inflacion_COL"], params["inflacion_USA"])
    assert ke_cop == pytest.approx((1 + ke.ke) * 1.045 / 1.025 - 1, abs=1e-12)
    assert ke_cop != pytest.approx(ke.ke + 0.045 - 0.025, abs=1e-6)  # no se suman inflaciones
    assert sml_required_return(0.043, 1.0, 0.055) == pytest.approx(0.098, abs=1e-12)


def test_fcff_fcfe_wacc_and_invalid_terminal_p2_34():
    assert fcff(ebit=18000, tax=0.35, d_and_a=9000, capex=9000, delta_nwc=600) == pytest.approx(18000 * 0.65 - 600)
    assert fcfe(net_income=5000, d_and_a=900, capex=1200, delta_nwc=100, net_borrowing=300) == pytest.approx(4900)
    w = wacc(ke=0.20, kd=0.135, tax=0.35, debt_to_equity=0.75)
    assert w == pytest.approx(1 / 1.75 * 0.20 + 0.75 / 1.75 * 0.135 * 0.65, abs=1e-12)
    with pytest.raises(ValueError):
        terminal_value(100.0, discount_rate=0.04, growth=0.045)  # WACC <= g: no hay valor terminal
    dcf = discounted_cash_flow([100.0, 110.0], discount_rate=0.10, growth=0.03)
    tv = 110 * 1.03 / 0.07
    assert dcf.terminal == pytest.approx(tv)
    assert dcf.enterprise_value == pytest.approx(100 / 1.1 + 110 / 1.21 + tv / 1.21)
    assert 0 < dcf.terminal_share < 1
    assert equity_value(1000, 50, 20, 400, 10) == pytest.approx(660)
    assert stable_reinvestment_rate(0.045, 0.15) == pytest.approx(0.3)
