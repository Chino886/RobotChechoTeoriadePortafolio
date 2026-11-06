"""
Tipo de cambio sin mirar al futuro y moneda base USD/COP (guía 3.2). Sin red.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.comparison import build_comparison  # noqa: E402
from src.data import AssetData  # noqa: E402
from src.data_quality import align_fx_no_lookahead, convert_prices_base, cop_returns  # noqa: E402

D = pd.to_datetime


def test_fx_uses_latest_rate_on_or_before_each_date():
    asset_dates = D(["2024-01-01", "2024-01-03", "2024-01-05"])
    # El FX cotizó el 2 y el 4, días que el activo no tiene; el 3 y el 5 no cotizó.
    fx = pd.Series([4000.0, 4100.0, 4200.0, 4300.0], index=D(["2024-01-01", "2024-01-02", "2024-01-04", "2024-01-08"]))
    aligned = align_fx_no_lookahead(asset_dates, fx)
    assert aligned.tolist() == [4000.0, 4100.0, 4200.0]  # antes: 4000, 4000, 4000
    # Nunca usa un dato posterior: el 8 no aparece, y antes del primer FX queda vacío.
    early = align_fx_no_lookahead(D(["2023-12-29", "2024-01-01"]), fx)
    assert np.isnan(early.iloc[0]) and early.iloc[1] == 4000.0


def test_build_comparison_converts_with_fx_date_missing_from_asset_dates():
    idx = D(["2024-01-01", "2024-01-03", "2024-01-05"])
    usd = AssetData("SPY", True, pd.DataFrame({"adjusted_close": [100.0, 101.0, 102.0]}, index=idx), currency="USD")
    cop = AssetData("ECOPETROL", True, pd.DataFrame({"adjusted_close": [2000.0, 2050.0, 2100.0]}, index=idx), currency="COP")
    # USD por 1 COP con datos el 2 y el 4 (días que los activos no tienen).
    usd_per_cop = pd.Series([1 / 4000, 1 / 4100, 1 / 4200], index=D(["2024-01-01", "2024-01-02", "2024-01-04"]))
    res = build_comparison({"SPY": usd, "ECOPETROL": cop}, "Diaria", 252, base_currency="USD", fx_rates={"COP": usd_per_cop})
    assert res.ok
    np.testing.assert_allclose(res.common_prices["ECOPETROL"].to_numpy(), [2000 / 4000, 2050 / 4100, 2100 / 4200])


def test_convert_to_cop_and_back_and_return_identity():
    idx = D(["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    prices = pd.DataFrame({"A": [100.0, 102.0, 101.0, 105.0], "B": [50.0, 49.0, 51.0, 52.0]}, index=idx)
    fx = pd.Series([3900.0, 3950.0, 4010.0, 3980.0], index=idx)
    cop, dropped = convert_prices_base(prices, "USD", "COP", fx)
    assert dropped == 0
    np.testing.assert_allclose(cop["A"].to_numpy(), prices["A"].to_numpy() * fx.to_numpy())  # P_COP = P_USD · FX
    # 1 + R_COP = (1 + R_USD)(1 + R_FX)
    r_cop = cop["A"].pct_change().dropna()
    expected = cop_returns(prices["A"].pct_change().dropna(), fx.pct_change().dropna())
    np.testing.assert_allclose(r_cop.to_numpy(), expected.to_numpy(), atol=1e-14)
    back, _ = convert_prices_base(cop, "COP", "USD", fx)
    np.testing.assert_allclose(back.to_numpy(), prices.to_numpy(), rtol=1e-14)
    same, n = convert_prices_base(prices, "USD", "USD", None)
    assert n == 0 and same.equals(prices)


def test_convert_reports_rows_without_previous_fx_and_rejects_other_pairs():
    idx = D(["2024-01-01", "2024-01-02", "2024-01-03"])
    prices = pd.DataFrame({"A": [1.0, 2.0, 3.0]}, index=idx)
    fx = pd.Series([4000.0], index=D(["2024-01-02"]))
    out, dropped = convert_prices_base(prices, "USD", "COP", fx)
    assert dropped == 1 and list(out.index) == list(idx[1:])
    with pytest.raises(ValueError):
        convert_prices_base(prices, "USD", "EUR", fx)
    with pytest.raises(ValueError):
        convert_prices_base(prices, "USD", "COP", None)
