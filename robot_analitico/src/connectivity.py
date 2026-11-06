"""
Comprobación de conexiones reales (evidencia de la prueba P2-3: consultas reales
sucesivas con fuente y hora). Cada comprobación es una función sin argumentos que
devuelve (ok, detalle); aquí solo se mide el tiempo, se captura el error y se
anota la hora UTC, para que cada fila quede como evidencia.
"""
import time
from datetime import datetime, timezone
from typing import Callable

Check = Callable[[], "tuple[bool, str]"]


def run_checks(checks: "dict[str, Check]", clock=time.perf_counter, now=None) -> "list[dict]":
    """Ejecuta cada comprobación y devuelve una fila por servicio. Un fallo no detiene las demás."""
    rows = []
    for service, check in checks.items():
        start = clock()
        try:
            ok, detail = check()
        except Exception as exc:  # la evidencia debe registrar el fallo, no ocultarlo
            ok, detail = False, f"{type(exc).__name__}: {exc}"
        rows.append({
            "hora (UTC)": (now() if now else datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M:%S"),
            "servicio": service,
            "estado": "conectado" if ok else "falló",
            "detalle": detail,
            "tiempo (s)": round(clock() - start, 2),
        })
    return rows
