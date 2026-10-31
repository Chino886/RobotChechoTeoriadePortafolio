"""Lista de países con tasa de bonos del gobierno en FRED (sin red, respuestas simuladas)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.rates import list_long_term_yield_countries  # noqa: E402

OECD = "Interest Rates: Long-Term Government Bond Yields: 10-Year: Main (Including Benchmark) for "
IMF = "Interest Rates, Government Securities, Government Bonds for "

SERIES = {
    "IRLTLT01": [
        {"id": "IRLTLT01COQ156N", "title": OECD + "Colombia", "observation_end": "2026-04-01"},  # solo trimestral
        {"id": "IRLTLT01DEM156N", "title": OECD + "Germany", "observation_end": "2026-09-01"},
        {"id": "IRLTLT01DEA156N", "title": OECD + "Germany", "observation_end": "2025-01-01"},
        {"id": "IRLTLT01PEA156N", "title": OECD + "Peru", "observation_end": "2015-01-01"},  # vieja
        {"id": "IRLTLT01USM156S", "title": OECD + "United States", "observation_end": "2026-09-01"},  # sufijo ajeno
    ],
    "INTGSB": [
        {"id": "INTGSBBRM193N", "title": IMF + "Brazil", "observation_end": "2026-06-01"},  # solo FMI
        {"id": "INTGSBDEM193N", "title": IMF + "Germany", "observation_end": "2026-08-01"},
        {"id": "INTGSBPEM193N", "title": IMF + "Peru", "observation_end": "2026-07-01"},
    ],
}


class _Resp:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


class _Http:
    """Responde por prefijo y en páginas de 2 para probar la paginación."""

    def __init__(self, page_size=2):
        self.page_size, self.calls = page_size, []

    def get(self, url, params=None, timeout=None, **kw):
        if url.endswith("/series/search"):
            self.calls.append(dict(params))
            rows = SERIES[params["search_text"].rstrip("*")]
            off = params.get("offset", 0)
            return _Resp({"count": len(rows), "seriess": rows[off:off + self.page_size]})
        obs = [{"date": f"2025-{m:02d}-01", "value": f"{9 + m / 10:.2f}"} for m in range(1, 13)]
        return _Resp({"observations": obs + [{"date": "2026-01-01", "value": "."}]})


def test_countries_from_oecd_any_frequency_plus_imf():
    rows = {r["label"]: r for r in list_long_term_yield_countries("KEY", http=_Http())}
    assert sorted(rows) == ["Alemania", "Brasil", "Colombia", "Perú"]
    assert rows["Colombia"]["id"] == "IRLTLT01COQ156N" and rows["Colombia"]["frequency"] == "trimestral"
    assert rows["Alemania"]["id"] == "IRLTLT01DEM156N"  # OCDE a 10 años y mensual gana
    assert rows["Brasil"]["source"] == "FMI"
    assert rows["Perú"]["id"] == "INTGSBPEM193N"  # la OCDE de Perú está 11 años atrasada


def test_search_reads_every_page():
    http = _Http(page_size=2)
    list_long_term_yield_countries("KEY", http=http)
    offsets = [(c["search_text"], c["offset"]) for c in http.calls]
    assert offsets == [("IRLTLT01*", 0), ("IRLTLT01*", 2), ("IRLTLT01*", 4), ("INTGSB*", 0), ("INTGSB*", 2)]
    assert all(c["search_type"] == "series_id" for c in http.calls)


def test_rates_page_lists_countries_and_shows_rate_without_typing(monkeypatch):
    """La pestaña de tasas muestra un desplegable de países y la tasa del elegido sin botón."""
    import requests
    from streamlit.testing.v1 import AppTest

    http = _Http(page_size=1000)
    monkeypatch.setattr(requests, "get", http.get)
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=60)
    at.secrets["FRED_API_KEY"] = "KEY"
    at.session_state["intro_ack"] = True
    at.session_state["terms_accepted"] = True
    at.run()
    assert not at.exception
    box = at.selectbox(key="rates_country")
    assert box.value == "Colombia" and len(box.options) == 4
    assert any("10.20%" in m.value for m in at.metric)
    box.set_value("Brasil").run()
    assert not at.exception and any("Brasil" in m.label for m in at.metric)
    assert any("FMI" in c.value for c in at.caption)
