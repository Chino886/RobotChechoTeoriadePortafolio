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


def build_trace(*, source: str, rights: str, periods_per_year: int, asset_order: "list[str]", snapshot_text: str,
                parameters: dict, results: Optional[dict] = None, solver: Optional[str] = None,
                common_rows: Optional[int] = None, rows_before_mask: Optional[int] = None,
                views_ids: "Optional[list[str]]" = None, rebalance_ids: "Optional[list[str]]" = None,
                code_commit: Optional[str] = None, student_decision: Optional[str] = None) -> dict:
    return {
        "schema": SCHEMA,
        "analysis_id": str(uuid.uuid4()),
        "snapshot_sha256": sha256_text(snapshot_text),
        "code_commit": code_commit or git_commit(),
        "dependencies": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "source": source,
        "rights": rights,
        "calculated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "frequency_periods_per_year": periods_per_year,
        "return_convention": "simple (capa de cartera); logs solo en la capa individual v1",
        "annualization": "mu*m, sigma*sqrt(m) (convención aritmética)",
        "asset_order": list(asset_order),
        "common_rows": common_rows,
        "rows_before_mask": rows_before_mask,
        "parameters": parameters,
        "solver": solver,
        "results": {k: _result_dict(r) for k, r in (results or {}).items()},
        "views_ids": list(views_ids or []),
        "rebalance_ids": list(rebalance_ids or []),
        "student_decision": student_decision,  # lo completa el equipo
        "status": "ejecucion_laboratorio",
    }


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
