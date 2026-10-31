"""Lista de países con serie de bonos a 10 años en FRED (sin red, respuesta simulada)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.rates import list_long_term_yield_countries  # noqa: E402

TITLE = "Interest Rates: Long-Term Government Bond Yields: 10-Year: Main (Including Benchmark) for "


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _Http:
    def __init__(self, data):
        self.data, self.params = data, None

    def get(self, url, params=None, timeout=None):
        self.params = params
        return _Resp(self.data)


def test_only_monthly_series_one_per_country_sorted_in_spanish():
    http = _Http({"seriess": [
        {"id": "IRLTLT01COM156N", "title": TITLE + "Colombia", "observation_end": "2026-08-01"},
        {"id": "IRLTLT01COA156N", "title": TITLE + "Colombia", "observation_end": "2025-01-01"},  # anual: fuera
        {"id": "IRLTLT01DEM156N", "title": TITLE + "Germany", "observation_end": "2026-09-01"},
        {"id": "IRLTLT01USM156N", "title": TITLE + "United States", "observation_end": "2026-09-01"},
        {"id": "IRLTLT01XXM156N", "title": TITLE + "Atlantis", "observation_end": "2020-01-01"},
        {"id": "DGS10", "title": "Market Yield on U.S. Treasury Securities at 10-Year", "observation_end": "2026-10-30"},
    ]})
    rows = list_long_term_yield_countries("KEY", http=http)
    assert [r["label"] for r in rows] == ["Alemania", "Atlantis", "Colombia", "Estados Unidos"]
    assert {r["id"] for r in rows} == {"IRLTLT01DEM156N", "IRLTLT01XXM156N", "IRLTLT01COM156N", "IRLTLT01USM156N"}
    assert http.params["search_type"] == "series_id" and http.params["search_text"] == "IRLTLT01*"


def test_rates_page_lists_countries_and_shows_rate_without_typing(monkeypatch):
    """La pestaña de tasas muestra un desplegable de países y la tasa del elegido sin botón."""
    import requests
    from streamlit.testing.v1 import AppTest

    obs = {"observations": [{"date": f"2025-{m:02d}-01", "value": f"{9 + m / 10:.2f}"} for m in range(1, 13)]
           + [{"date": "2026-01-01", "value": "."}]}
    search = {"seriess": [
        {"id": "IRLTLT01COM156N", "title": TITLE + "Colombia", "observation_end": "2025-12-01"},
        {"id": "IRLTLT01DEM156N", "title": TITLE + "Germany", "observation_end": "2025-12-01"},
    ]}

    def fake_get(url, params=None, timeout=None, **kw):
        return _Resp(search if url.endswith("/series/search") else obs)

    monkeypatch.setattr(requests, "get", fake_get)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.secrets["FRED_API_KEY"] = "KEY"
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    assert not at.exception
    box = at.selectbox(key="rates_country")
    assert box.options == ["Alemania", "Colombia"] and box.value == "Colombia"
    assert any("10.20%" in m.value for m in at.metric)
    box.set_value("Alemania").run()
    assert not at.exception and any("Alemania" in m.label for m in at.metric)
