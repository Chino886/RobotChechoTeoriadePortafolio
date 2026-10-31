"""
Trazabilidad de una ejecución del laboratorio v2 (guía V2, sección 11,
plantilla paquete_v2/plantillas/trazabilidad.json).

Cadena: fuente -> transformación -> muestra -> estimador -> modelo/solver ->
resultado -> decisión del estudiante -> prueba -> commit. El snapshot_sha256
se calcula sobre el MISMO texto CSV que se exporta, de modo que cualquiera
puede verificar que la traza corresponde a esos datos (P2-35).
"""
import hashlib
import json
import platform
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

SCHEMA = "bot-portafolios/trace/v2"


def git_commit(repo_dir: Optional[Path] = None) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_dir or Path(__file__).parent,
                             capture_output=True, text=True, timeout=5)
        return out.stdout.strip() or "no disponible"
    except Exception:
        return "no disponible"


def snapshot_csv(returns: Optional[pd.DataFrame], mu: pd.Series, sigma: pd.DataFrame) -> str:
    """Texto canónico de la muestra (o de mu/Sigma si no hay serie), con precisión completa."""
    if returns is not None:
        return returns.to_csv(float_format="%.17g", lineterminator="\n")
    table = pd.concat([mu.rename("mu"), sigma], axis=1)
    return table.to_csv(float_format="%.17g", lineterminator="\n")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _result_dict(res) -> dict:
    return {
        "status": res.status,
        "weights": None if res.weights is None else {k: float(v) for k, v in res.weights.items()},
        "mean_period": None if np.isnan(res.mean) else float(res.mean),
        "vol_period": None if np.isnan(res.volatility) else float(res.volatility),
        "active_bounds": list(res.active_bounds),
        "budget_residual": None if np.isnan(res.budget_residual) else float(res.budget_residual),
        "message": str(res.message),
    }


TEMPLATE_KEYS = [
    "schema", "analysis_id", "snapshot_sha256", "code_commit", "dependencies", "source", "rights", "source_fields",
    "event_at", "available_at", "received_at", "calculated_at", "timezone", "currency", "frequency",
    "return_convention", "annualization", "asset_order", "missing_data_rule", "common_rows", "transformations",
    "parameters", "solver", "residuals", "views_ids", "trigger_id", "rebalance_id", "student_decision",
    "test_evidence", "status",
]  # claves de paquete_v2/plantillas/trazabilidad.json


def _versions() -> dict:
    import scipy

    return {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__, "scipy": scipy.__version__}


def build_trace(*, source: str, rights: str, periods_per_year: int, asset_order: "list[str]", snapshot_text: str,
                parameters: dict, results: Optional[dict] = None, solver: Optional[str] = None,
                common_rows: Optional[int] = None, rows_before_mask: Optional[int] = None,
                views_ids: "Optional[list[str]]" = None, rebalance_ids: "Optional[list[str]]" = None,
                code_commit: Optional[str] = None, student_decision: Optional[str] = None,
                currency: Optional[str] = None, timezone_name: Optional[str] = None, frequency: Optional[str] = None,
                source_fields: "Optional[list[str]]" = None, event_at: Optional[str] = None,
                available_at: Optional[str] = None, received_at: Optional[str] = None,
                missing_data_rule: Optional[str] = None, transformations: "Optional[list[str]]" = None,
                trigger_id: Optional[str] = None, test_evidence: Optional[str] = None) -> dict:
    """
    Traza con TODAS las claves de la plantilla trazabilidad.json. Un campo que
    no aplica o no se conoce queda en null y su motivo va en `null_reasons`.
    """
    results = results or {}
    residuals = {k: {"budget_residual": None if np.isnan(r.budget_residual) else float(r.budget_residual),
                     "active_bounds": list(r.active_bounds)} for k, r in results.items()}
    trace = {
        "schema": SCHEMA,
        "analysis_id": str(uuid.uuid4()),
        "snapshot_sha256": sha256_text(snapshot_text),
        "code_commit": code_commit or git_commit(),
        "dependencies": _versions(),
        "source": source,
        "rights": rights,
        "source_fields": source_fields,
        "event_at": event_at,
        "available_at": available_at,
        "received_at": received_at,
        "calculated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timezone": timezone_name,
        "currency": currency,
        "frequency": frequency,
        "frequency_periods_per_year": periods_per_year,
        "return_convention": "simple (capa de cartera); logs solo en la capa individual v1",
        "annualization": "mu*m, sigma*sqrt(m) (convención aritmética)",
        "asset_order": list(asset_order),
        "missing_data_rule": missing_data_rule,
        "common_rows": common_rows,
        "rows_before_mask": rows_before_mask,
        "transformations": transformations,
        "parameters": parameters,
        "solver": solver,
        "residuals": residuals or None,
        "results": {k: _result_dict(r) for k, r in results.items()},
        "views_ids": list(views_ids or []),
        "trigger_id": trigger_id,
        "rebalance_id": (rebalance_ids or [None])[-1],  # el último rebalanceo de la ejecución
        "rebalance_ids": list(rebalance_ids or []),
        "student_decision": student_decision,  # lo completa el equipo
        "test_evidence": test_evidence,
        "status": "ejecucion_laboratorio",
    }
    reasons = {
        "source_fields": "fuente sin campos de proveedor (parámetros dados o datos sintéticos)",
        "event_at": "sin fecha de evento (parámetros dados por el caso)",
        "available_at": "el proveedor no informa la hora de publicación del dato",
        "received_at": "los datos no se descargaron en esta ejecución (sintéticos, caso o descarga previa sin registro)",
        "timezone": "la fuente no informa zona horaria",
        "currency": "la fuente no informa moneda",
        "frequency": "parámetros anuales dados por el caso",
        "missing_data_rule": "sin serie de precios",
        "common_rows": "sin serie de precios",
        "rows_before_mask": "sin serie de precios",
        "transformations": "sin transformaciones registradas",
        "solver": "no se ejecutó optimización en esta traza",
        "residuals": "no se ejecutó optimización en esta traza",
        "trigger_id": "ninguna decisión de esta ejecución fue disparada por un evento",
        "rebalance_id": "no hubo rebalanceos en esta ejecución",
        "student_decision": "decisión pendiente del equipo",
        "test_evidence": "no se adjuntó evidencia de pruebas a esta ejecución",
    }
    trace["null_reasons"] = {k: reasons.get(k, "no aplica") for k in TEMPLATE_KEYS if trace.get(k) is None}
    return trace


def export_bundle(trace: dict, snapshot_text: str) -> "dict[str, str]":
    """Archivos que se descargan juntos: la traza y el snapshot que la respalda."""
    return {"traza.json": json.dumps(trace, indent=2, ensure_ascii=False, default=str), "snapshot.csv": snapshot_text}


def verify_bundle(files: "dict[str, str]") -> "list[str]":
    """Devuelve la lista de problemas (vacía si la exportación es coherente)."""
    problems = []
    trace = json.loads(files["traza.json"])
    if sha256_text(files["snapshot.csv"]) != trace.get("snapshot_sha256"):
        problems.append("El hash del snapshot no coincide con la traza.")
    header = files["snapshot.csv"].splitlines()[0].split(",")[1:]
    order = trace.get("asset_order", [])
    if header[: len(order)] != order and header[1: len(order) + 1] != order:
        problems.append("El orden de activos del snapshot no coincide con la traza.")
    if not trace.get("code_commit"):
        problems.append("Falta el commit del código.")
    if not trace.get("parameters"):
        problems.append("Faltan los parámetros.")
    return problems
