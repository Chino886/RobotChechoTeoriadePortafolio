"""
Fase 2 (v2) - P2-35: la exportación coincide con snapshot, parámetros y commit.
Sin red.
"""
import io
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.portfolio import covariance_matrix, min_variance, simple_returns_matrix  # noqa: E402
from src.trace import build_trace, export_bundle, sha256_text, snapshot_csv, verify_bundle  # noqa: E402


def _bundle():
    prices = pd.read_csv(ROOT / "paquete_v2" / "data" / "precios_sinteticos_20.csv", parse_dates=["fecha"]).set_index("fecha")
    sample = simple_returns_matrix(prices.iloc[:, :4])
    returns = sample.returns
    mu, sigma = returns.mean(), covariance_matrix(returns)
    text = snapshot_csv(returns, mu, sigma)
    gmv = min_variance(mu, sigma, [(0, 1)] * 4)
    trace = build_trace(source="sintético", rights="paquete docente", periods_per_year=252, asset_order=list(mu.index),
                        snapshot_text=text, parameters={"rf_EA": 0.03, "gamma": 5}, results={"gmv": gmv},
                        solver=gmv.solver, common_rows=len(returns), rows_before_mask=sample.n_before,
                        views_ids=["V1"], rebalance_ids=["R1"], code_commit="abc123")
    return export_bundle(trace, text), returns


def test_export_matches_snapshot_parameters_and_commit_p2_35():
    files, returns = _bundle()
    assert verify_bundle(files) == []
    trace = json.loads(files["traza.json"])
    assert trace["code_commit"] == "abc123" and trace["views_ids"] == ["V1"] and trace["rebalance_ids"] == ["R1"]
    assert trace["asset_order"] == list(returns.columns)
    # El CSV exportado reproduce la muestra con precisión completa.
    back = pd.read_csv(io.StringIO(files["snapshot.csv"]), index_col=0, float_precision="round_trip")
    pd.testing.assert_frame_equal(back.reset_index(drop=True), returns.reset_index(drop=True), check_exact=True)
    w = trace["results"]["gmv"]["weights"]
    assert abs(sum(w.values()) - 1) < 1e-8


def test_tampered_export_is_detected():
    files, _ = _bundle()
    tampered = dict(files, **{"snapshot.csv": files["snapshot.csv"].replace("0.", "0.9", 1)})
    assert any("hash" in p for p in verify_bundle(tampered))
    assert sha256_text("a") != sha256_text("b")
