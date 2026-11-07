"""La vista visual de la comparación muestra exactamente los valores de comparison_table()."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.compare_view import (asset_panel_html, comparison_table_html, evolution_figure, mean_bar_figure,
                              risk_bar_figures)
from src.comparison import build_comparison, comparison_table, non_dominated_tickers, preselect_max_rvr
from src.data import AssetData
from tests.fixtures_path import FIXTURE_20_PRICES

pytestmark = pytest.mark.skipif(not FIXTURE_20_PRICES.exists(), reason="falta el fixture oficial de 20 activos")


@pytest.fixture(scope="module")
def result():
    raw = pd.read_csv(FIXTURE_20_PRICES, parse_dates=["date"])
    assets = {t: AssetData(ticker=t, ok=True, prices=g.sort_values("date").set_index("date")[["adjusted_close"]],
                           currency=g["currency"].iloc[0], source=g["source"].iloc[0]) for t, g in raw.groupby("ticker")}
    return build_comparison(assets, frequency="Diaria", periods_per_year=252)


def test_table_and_panel_show_original_values(result):
    nd = non_dominated_tickers(result.summaries)
    sel = preselect_max_rvr(result.summaries)
    table = comparison_table(result, nd)
    html = comparison_table_html(result, {}, nd, sel, None)
    panel = asset_panel_html(result, {}, nd, sel, None, "Perfil Moderado")
    for t, row in table.iterrows():
        for value in (f"{row.media_anualizada:.2%}", f"{row.volatilidad_anualizada:.2%}", f"{row.max_drawdown:.2%}",
                      f"{row.rvr_individual:.3f}", f"{row.q05_log:.4f}", f"{row.q95_log:.4f}"):
            assert value in html
        assert f'data-mean="{row.media_anualizada}"' in panel and f'data-vol="{row.volatilidad_anualizada}"' in panel
    assert html.count('data-state="sel') == len(sel) and panel.count("Preseleccionado</span>") == len(sel)
    assert html.count("No dominado</span>") == len(nd)


def test_charts_use_same_series_and_metrics(result):
    t = result.summaries[0].ticker
    fig = evolution_figure(result, [t], "Todo", "Precio")
    assert list(fig.data[0].y) == list(result.common_prices[t].dropna())  # mismos precios procesados
    pct = evolution_figure(result, [t], "Todo", "Variación %").data[0].y
    s = result.common_prices[t].dropna()
    assert pct[0] == 0 and abs(pct[-1] - (s.iloc[-1] / s.iloc[0] - 1)) < 1e-12
    bars = mean_bar_figure(result.summaries, set()).data[0]
    assert dict(zip(bars.y, bars.x)) == {s.ticker: s.mean_annual for s in result.summaries}
    vol, rvr, dd = (f.data[0] for f in risk_bar_figures(result.summaries, set()))
    assert dict(zip(vol.y, vol.x)) == {s.ticker: s.vol_annual for s in result.summaries}
    assert dict(zip(dd.y, dd.x)) == {s.ticker: s.max_dd for s in result.summaries}
