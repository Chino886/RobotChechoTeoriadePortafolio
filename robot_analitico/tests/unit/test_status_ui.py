"""Estados de conexión/carga/error: solo reflejan operaciones reales; sin cifras ni conexiones supuestas."""
from src.status_ui import (STATE_KEY, classify, error_card_html, get_state, set_state, skeleton_html,
                           status_center_html, sync_from_checks)


def test_unused_services_are_never_marked_connected():
    html = status_center_html({})
    assert "Conectado" not in html.replace("«Conectado»", "") and "Sin verificar" in html
    assert get_state({}, "fred")["status"] == "unverified"


def test_states_follow_real_results():
    state = {}
    set_state(state, "yahoo_hist", "ok", "AAPL: 100 observaciones", "2026-11-07 21:00 UTC")
    set_state(state, "fred", classify("Failed to perform, curl: (7) CONNECT tunnel failed"), "x", "2026-11-07 21:30 UTC")
    assert state[STATE_KEY]["fred"]["status"] == "offline"
    assert classify("Respuesta vacía: ticker inexistente") == "nodata" and classify("ZeroDivisionError") == "error"
    html = status_center_html(state)
    assert "1 conectada" in html and "1 con error" in html
    # una prueba real de conexiones más reciente manda sobre lo anterior
    sync_from_checks(state, [{"hora (UTC)": "2026-11-07 22:00:00", "servicio": "FRED · tasas", "estado": "conectado",
                              "detalle": "ok"}])
    assert state[STATE_KEY]["fred"]["status"] == "ok"


def test_error_card_and_skeleton_have_no_technical_or_numeric_noise():
    card = error_card_html("Tasas soberanas", "No se pudo descargar la tasa", "Serie IRLTLT01COM156N", "Vuelve a intentar")
    for part in ("Tasas soberanas", "No se pudo descargar la tasa", "Serie IRLTLT01COM156N", "Vuelve a intentar"):
        assert part in card
    for kind in ("table", "chart", "cards", "news"):
        sk = skeleton_html(kind, "Consultando…")
        assert "Consultando" in sk and not any(ch.isdigit() for ch in sk.split("<svg")[0].replace("dpst", ""))
