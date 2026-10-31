"""
Fase 2 (v2) - P2-4 (veinte válidos más un inválido, error aislado y sin
fallback sintético oculto) y P2-18 (CAL, CML y SML con sus propios ejes y
supuestos). Con mocks, sin red.
"""
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.capm import sml_required_return  # noqa: E402
from src.comparison import build_comparison  # noqa: E402
from src.data import AssetData  # noqa: E402
from src.market import fetch_quotes  # noqa: E402
from src.portfolio import cal_point, cml_expected_return  # noqa: E402

TICKERS = [f"T{i:02d}" for i in range(20)]
NOW = datetime(2026, 10, 30, 15, 0, tzinfo=timezone.utc)


class _Ticker:
    def __init__(self, ticker):
        self.ticker = ticker

    def history(self, period, **kw):
        if self.ticker == "INVALIDO":
            return pd.DataFrame()
        idx = pd.DatetimeIndex(["2026-10-30 10:58", "2026-10-30 10:59"]).tz_localize("America/New_York")
        return pd.DataFrame({"Close": [100.0, 100.5]}, index=idx)

    def get_history_metadata(self):
        return {"currency": "USD"}


def test_twenty_valid_quotes_plus_one_invalid_p2_4():
    quotes = fetch_quotes(TICKERS + ["INVALIDO"], now=NOW, ticker_factory=_Ticker)
    assert len(quotes) == 21
    good = [q for q in quotes if q.ok]
    bad = [q for q in quotes if not q.ok]
    assert len(good) == 20 and [q.ticker for q in bad] == ["INVALIDO"]
    assert bad[0].price is None and bad[0].bars is None and "Sin barras" in bad[0].error  # sin precio inventado


def test_twenty_valid_assets_plus_one_invalid_in_comparison_p2_4():
    idx = pd.bdate_range("2025-01-01", periods=80)
    rng = np.random.default_rng(1)
    assets = {
        t: AssetData(ticker=t, ok=True, currency="USD",
                     prices=pd.DataFrame({"adjusted_close": 100 * np.cumprod(1 + rng.normal(0, 0.01, len(idx)))}, index=idx))
        for t in TICKERS
    }
    assets["INVALIDO"] = AssetData(ticker="INVALIDO", ok=False, error="Respuesta vacía: ticker inexistente.")
    result = build_comparison(assets, "Diaria", 252)
    assert result.ok and len(result.summaries) == 20
    assert [e.ticker for e in result.excluded] == ["INVALIDO"] and "inexistente" in result.excluded[0].reason
    assert set(result.common_prices) == set(TICKERS)  # el inválido no se reemplaza con datos sintéticos


def test_cal_cml_sml_have_their_own_axes_p2_18():
    rf, mu_t, vol_t = 0.03, 0.10, 0.12
    # CAL: el eje es la volatilidad total de la combinación con la tangente.
    assert cal_point(rf, mu_t, vol_t, 0.5) == pytest.approx((0.065, 0.06))
    # CML: solo con un proxy de mercado rotulado; misma forma, pero con el "mercado".
    assert cml_expected_return(rf, 0.08, 0.15, 0.15, "1/N del universo (proxy del equipo)") == pytest.approx(0.08)
    with pytest.raises(ValueError):
        cml_expected_return(rf, 0.08, 0.15, 0.15, "")
    # SML: el eje es beta, no la volatilidad total; dos activos con igual beta exigen lo mismo.
    assert sml_required_return(rf, 1.2, 0.055) == pytest.approx(0.03 + 1.2 * 0.055)
    assert sml_required_return(rf, 1.2, 0.055) == sml_required_return(rf, 1.2, 0.055)
