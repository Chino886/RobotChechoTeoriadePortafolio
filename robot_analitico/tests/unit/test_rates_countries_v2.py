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
        {"id": "IRLTLT01CAQ156N", "title": OECD + "Canada", "observation_end": "2026-04-01"},  # solo trimestral
        {"id": "IRLTLT01KRM156N", "title": OECD + "Korea", "observation_end": "2026-09-01"},
        {"id": "IRLTLT01KRA156N", "title": OECD + "Republic of Korea", "observation_end": "2026-01-01"},  # mismo país
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


# Búsqueda por nombre: Colombia no sale por código, sí por nombre (como antes del cambio).
TEXT = {
    "Colombia 10-Year government bond yield": [
        {"id": "IRLTLT01COM156N", "title": OECD + "Colombia", "observation_end": "2026-09-01", "frequency_short": "M"},
        {"id": "COLCPI", "title": "Consumer Price Index for Colombia", "observation_end": "2026-09-01", "frequency_short": "M"},
        {"id": "IRLTLT01PEM156N", "title": OECD + "Peru", "observation_end": "2026-09-01", "frequency_short": "M"},
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
            if params.get("search_type") != "series_id":
                return _Resp({"seriess": TEXT.get(params["search_text"], [])})
            rows = SERIES[params["search_text"].rstrip("*")]
            off = params.get("offset", 0)
            return _Resp({"count": len(rows), "seriess": rows[off:off + self.page_size]})
        obs = [{"date": f"2025-{m:02d}-01", "value": f"{9 + m / 10:.2f}"} for m in range(1, 13)]
        return _Resp({"observations": obs + [{"date": "2026-01-01", "value": "."}]})


def test_countries_from_codes_and_name_search_without_duplicates():
    rows = list_long_term_yield_countries("KEY", http=_Http())
    labels = [r["label"] for r in rows]
    assert labels == ["Alemania", "Brasil", "Canadá", "Colombia", "Corea del Sur", "Perú"]  # Corea una sola vez
    by = {r["label"]: r for r in rows}
    assert by["Colombia"]["id"] == "IRLTLT01COM156N" and by["Colombia"]["source"] == "OCDE"  # vía búsqueda por nombre
    assert by["Canadá"]["frequency"] == "trimestral"
    assert by["Corea del Sur"]["id"] == "IRLTLT01KRM156N"
    assert by["Alemania"]["id"] == "IRLTLT01DEM156N"  # OCDE a 10 años y mensual gana al FMI
    assert by["Brasil"]["source"] == "FMI"
    assert by["Perú"]["id"] == "INTGSBPEM193N"  # la OCDE de Perú está 11 años atrasada


def test_search_reads_every_page():
    http = _Http(page_size=2)
    list_long_term_yield_countries("KEY", http=http)
    code_calls = [(c["search_text"], c["offset"]) for c in http.calls if c.get("search_type") == "series_id"]
    assert code_calls == [("IRLTLT01*", 0), ("IRLTLT01*", 2), ("IRLTLT01*", 4), ("IRLTLT01*", 6),
                          ("INTGSB*", 0), ("INTGSB*", 2)]
    name_calls = {c["search_text"] for c in http.calls if c.get("search_type") != "series_id"}
    assert "Colombia 10-Year government bond yield" in name_calls  # misma búsqueda que la versión anterior
    assert "Colombia government bond yield" not in name_calls  # ya encontró con la primera
    assert not any(t.startswith("Brazil") for t in name_calls)  # Brasil ya salió por código


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
    assert box.value == "Colombia" and len(box.options) == 6
    assert any("10.20%" in m.value for m in at.metric)
    box.set_value("Brasil").run()
    assert not at.exception and any("Brasil" in m.label for m in at.metric)
    assert any("FMI" in c.value for c in at.caption)
