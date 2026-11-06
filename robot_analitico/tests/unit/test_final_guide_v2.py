"""
Guía final de sustentación: pérdida esperada (ES), desempeño frente al benchmark (Sharpe,
Treynor, alfa de Jensen, razón de información, riesgo sistemático) y ficha técnica con la
estructura de la Superintendencia Financiera. Sin red.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.factsheet import build_factsheet, to_markdown, window_stats  # noqa: E402
from src.forecasting import ForecastModel  # noqa: E402
from src.performance import capm_required_return, historical_erp, performance  # noqa: E402
from src.risk_extras import expected_shortfall_fraction  # noqa: E402
from src.risk_rules import compute_var  # noqa: E402
from src.stress import historical_es, historical_var, parametric_es, parametric_var  # noqa: E402


def test_lognormal_expected_shortfall_matches_simulation_and_exceeds_var():
    model = ForecastModel("lognormal", mean_per_period=0.0004, std_per_period=0.015, n_train=500)
    es = expected_shortfall_fraction(model, horizon=10, confidence=0.95)
    var = compute_var(model, 100.0, 10, 0.95, 1.0).var_fraction
    x = np.random.default_rng(0).normal(0.004, 0.015 * np.sqrt(10), 2_000_000)
    loss = 1 - np.exp(x)
    sim = loss[loss >= np.quantile(loss, 0.95)].mean()
    assert es == pytest.approx(sim, rel=5e-3)
    assert es > var > 0


def test_normal_and_historical_portfolio_es():
    es = parametric_es(0.0005, 0.01, 0.95)
    x = np.random.default_rng(1).normal(0.0005, 0.01, 2_000_000)
    assert es == pytest.approx(-x[x <= np.quantile(x, 0.05)].mean(), rel=5e-3)
    assert es > parametric_var(0.0005, 0.01, 0.95)
    r = pd.Series([-0.05, -0.03, -0.01, 0.0, 0.01, 0.02, 0.03, 0.01, -0.02, 0.04])
    var = historical_var(r, 0.8)
    assert historical_es(r, 0.8) == pytest.approx(-r[-r >= var].mean())


def test_performance_metrics_follow_their_definitions():
    rng = np.random.default_rng(5)
    idx = pd.bdate_range("2022-01-03", periods=750)
    bench = pd.Series(rng.normal(0.0004, 0.01, len(idx)), index=idx)
    port = 0.0002 + 1.2 * bench + pd.Series(rng.normal(0, 0.006, len(idx)), index=idx)
    rf, m = 0.0001, 252
    p = performance("cartera", port, bench, rf, m)
    beta = np.cov(port - rf, bench - rf, ddof=1)[0, 1] / np.var(bench, ddof=1)
    assert p.beta == pytest.approx(beta, rel=1e-10)
    assert p.sharpe == pytest.approx((port.mean() - rf) / port.std(ddof=1) * np.sqrt(m))
    assert p.treynor == pytest.approx((port.mean() - rf) * m / beta)
    assert p.jensen_alpha == pytest.approx((port.mean() - rf - beta * (bench.mean() - rf)) * m)
    te = (port - bench).std(ddof=1) * np.sqrt(m)
    assert p.tracking_error == pytest.approx(te) and p.information_ratio == pytest.approx((port - bench).mean() * m / te)
    # R² = β²σ_m²/σ_p²: parte sistemática del riesgo; el resto es no sistemático.
    assert p.systematic_share == pytest.approx(beta ** 2 * bench.var() / port.var(), rel=1e-9)
    assert p.systematic_share + p.idiosyncratic_share == pytest.approx(1.0)
    assert capm_required_return(0.04, 1.2, 0.05) == pytest.approx(0.10)
    assert historical_erp(bench, rf, m) == pytest.approx((bench.mean() - rf) * m)


def test_factsheet_windows_composition_and_structure():
    idx = pd.date_range("2023-01-01", "2026-10-30", freq="D")
    rets = pd.DataFrame({"A": 0.0003, "B": -0.0001, "C": 0.0002}, index=idx)
    w = pd.Series({"A": 0.5, "B": 0.3, "C": 0.2})
    daily = float((rets * w).sum(axis=1).iloc[0])
    perf = window_stats((rets * w).sum(axis=1), 365)
    assert perf.loc["Último año", "rentabilidad EA"] == pytest.approx((1 + daily) ** 365 - 1, rel=1e-9)
    assert perf.loc["Últimos 3 años", "rentabilidad EA"] == pytest.approx((1 + daily) ** 365 - 1, rel=1e-9)
    assert np.isnan(window_stats((rets * w).sum(axis=1).loc["2026-06-01":], 365).loc["Últimos 2 años", "rentabilidad EA"])

    fs = build_factsheet("Tangente", w, rets, 365, "USD", "Máximo Sharpe", "Pesos entre 0 y 1", 0.04, "Equipo DPST",
                         "Tech Business School – Universidad EIA", asset_currency={"A": "USD", "B": "USD", "C": "COP"},
                         sectors={"A": "tecnología", "B": "tecnología"})
    assert fs.composition_asset.index.tolist() == ["A", "B", "C"]
    assert fs.composition_currency.to_dict() == pytest.approx({"USD": 0.8, "COP": 0.2})
    assert fs.composition_sector.to_dict() == pytest.approx({"tecnología": 0.8, "Sin sector asignado": 0.2})
    assert fs.value_path.iloc[0] == pytest.approx(100_000 * (1 + daily))
    md = to_markdown(fs)
    for heading in ("Características", "Política de inversión", "Rentabilidad y volatilidad histórica",
                    "Composición del portafolio", "Principales inversiones", "Anexo 6", "no es un fondo"):
        assert heading in md
    control = build_factsheet("GMV", w, None, 1, None, "Mínima varianza", "0 a 1", 0.03, "Equipo DPST", "EIA")
    assert control.as_of is None and control.risk == [] and control.performance.isna().all().all()


def test_contrastable_calculations_notebook_runs():
    """El anexo docs/anexos/calculos_contrastables.ipynb: cada celda compara el cálculo a mano con el bot."""
    import json
    import os

    nb = json.loads((ROOT / "docs" / "anexos" / "calculos_contrastables.ipynb").read_text(encoding="utf-8"))
    cwd = os.getcwd()
    os.chdir(ROOT)
    try:
        ns = {}
        for cell in nb["cells"]:
            if cell["cell_type"] == "code":
                exec(compile("".join(cell["source"]), "anexo", "exec"), ns)  # las celdas tienen sus propios assert
    finally:
        os.chdir(cwd)
