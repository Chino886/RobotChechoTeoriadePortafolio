"""polish() solo cambia presentación: las series de cada gráfica quedan idénticas."""
import copy
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.charts import NEGATIVE, POSITIVE, forecast_chart, polish, price_chart, return_chart, risk_return_map

DATA_KEYS = ("x", "y", "z", "text", "customdata", "base", "fill", "mode", "name", "yaxis")


def _data(fig):
    return [{k: copy.deepcopy(tr[k]) for k in DATA_KEYS if k in tr} for tr in fig.to_plotly_json()["data"]]


def _same(a, b):
    assert len(a) == len(b)
    for ta, tb in zip(a, b):
        assert ta.keys() == tb.keys()
        for k in ta:
            np.testing.assert_array_equal(np.asarray(ta[k], dtype=object), np.asarray(tb[k], dtype=object))


def _prices():
    idx = pd.date_range("2024-01-01", periods=400, freq="B")
    return pd.Series(100 * np.exp(np.cumsum(np.random.default_rng(1).normal(0, 0.01, 400))), index=idx)


def test_polish_keeps_series_identical():
    p = _prices()
    steps = [SimpleNamespace(median_price=101 + i, q05_price=95 + i, q95_price=108 + i) for i in range(10)]
    s = [SimpleNamespace(ticker=t, vol_annual=v, mean_annual=m) for t, v, m in (("A", .2, .1), ("B", .3, .05))]
    dual = go.Figure([go.Scatter(x=p.index, y=p.values, name="a"),
                      go.Scatter(x=p.index, y=-p.values / 1000, name="b", yaxis="y2")])
    dual.update_layout(yaxis2=dict(overlaying="y", tickformat=".0%"))
    figs = [price_chart(p, "AAPL", "USD", "Diaria", "Yahoo"), return_chart(np.log(p).diff().dropna(), "AAPL", "Diaria"),
            forecast_chart(p, steps, "AAPL", "Diaria"), risk_return_map(s, {"A"}, "B"), dual,
            go.Figure(go.Heatmap(z=[[1, 0.2], [0.2, 1]], x=["A", "B"], y=["A", "B"]))]
    for fig in figs:
        before = _data(fig)
        polish(fig)
        _same(before, _data(fig))
    assert figs[0].layout.xaxis.hoverformat == "%Y-%m-%d"  # fecha exacta en el encabezado del tooltip
    assert "%{x|%Y-%m-%d}" in figs[4].data[0].hovertemplate  # sin modo unificado, la fecha va en cada punto
    assert figs[0].layout.xaxis.rangeselector.buttons  # selector de periodo en series de tiempo
    assert ".2%" in dual.data[1].hovertemplate  # cada serie usa el formato de su propio eje


def test_sign_colors_only_when_bar_has_no_color():
    bar = polish(go.Figure(go.Bar(x=["a", "b"], y=[0.2, -0.1])))
    assert list(bar.data[0].marker.color) == [POSITIVE, NEGATIVE]
    own = polish(go.Figure(go.Bar(x=["a", "b"], y=[0.2, -0.1], marker_color="#123456")))
    assert own.data[0].marker.color == "#123456"
