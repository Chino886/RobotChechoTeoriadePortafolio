"""Comprobador de conexiones (P2-3): una fila por fuente, el fallo de una no detiene las demás. Sin red."""
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.connectivity import run_checks  # noqa: E402


def test_each_service_gets_a_row_with_time_and_errors_are_recorded():
    ticks = iter([0.0, 0.5, 1.0, 1.25, 2.0, 2.1])

    def broken():
        raise TimeoutError("sin respuesta")

    rows = run_checks({"Yahoo": lambda: (True, "SPY 500"), "FRED": broken, "News": lambda: (False, "vacío")},
                      clock=lambda: next(ticks), now=lambda: datetime(2026, 11, 6, 15, 0, tzinfo=timezone.utc))
    assert [r["servicio"] for r in rows] == ["Yahoo", "FRED", "News"]
    assert [r["estado"] for r in rows] == ["conectado", "falló", "falló"]
    assert rows[1]["detalle"] == "TimeoutError: sin respuesta"
    assert [r["tiempo (s)"] for r in rows] == [0.5, 0.25, 0.1]
    assert all(r["hora (UTC)"] == "2026-11-06 15:00:00" for r in rows)


def test_teaching_package_matches_its_manifest():
    """paquete_v2/ no se modifica (CLAUDE.md): el verificador debe pasar."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import verify_package

    assert verify_package.main() == 0
