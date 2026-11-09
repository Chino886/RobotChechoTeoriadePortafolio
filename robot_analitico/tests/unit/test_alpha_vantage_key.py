"""
Aviso «falta la clave» de Alpha Vantage: debe desaparecer apenas el equipo agrega la clave en
Secrets, sin esperar a que venza la caché de 3 horas. Sin red (requests.get simulado).
"""
import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


class _Resp:
    def json(self):
        return {"feed": [{"title": "t", "url": "https://example.com/n", "source": "s",
                          "time_published": "20261109T120000", "topics": []}]}


def test_key_added_after_first_call_is_used_immediately(monkeypatch):
    app = importlib.import_module("app")
    app._fetch_alpha_vantage_cached.clear()
    calls = []
    monkeypatch.setattr(app.requests, "get", lambda url, params=None, timeout=None: calls.append(params) or _Resp())

    monkeypatch.setattr(app.st, "secrets", {})
    assert "API key" in app._fetch_alpha_vantage(None, "economy_macro", 3)["status"]
    assert not calls  # sin clave no se consulta nada

    monkeypatch.setattr(app.st, "secrets", {"ALPHA_VANTAGE_API_KEY": "demo"})
    out = app._fetch_alpha_vantage(None, "economy_macro", 3)
    assert out["status"] == "ok" and len(out["items"]) == 1
    assert calls[-1]["apikey"] == "demo"
    app._fetch_alpha_vantage_cached.clear()
