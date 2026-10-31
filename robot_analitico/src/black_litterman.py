"""
Black-Litterman (guía V2, sección 6). Todo en EXCESOS de rendimiento simple,
en la misma frecuencia, moneda y horizonte que Sigma.

    pi = delta * Sigma * w_ref                      (prior de equilibrio)
    B = tau * Sigma ;  A = P B P' + Omega
    mu_BL = pi + B P' solve(A, Q - P pi)            (media posterior)
    M = B - B P' solve(A, P B)                      (incertidumbre de la media)
    Sigma_predictiva = Sigma + M

M es incertidumbre sobre la MEDIA, no riesgo de los retornos: la
comparación principal cambia mu manteniendo Sigma y las cotas; la variante
con Sigma_predictiva se etiqueta aparte.

Nunca se invierte Omega: con Omega = 0 (confianza total) A = P B P' sigue
siendo invertible si P tiene rango completo, y la posterior cumple P mu = Q
exactamente. Las views, delta, tau, w_ref y la confianza las decide el
equipo; este módulo solo calcula y valida.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import numpy as np
import pandas as pd


@dataclass
class View:
    """
    Una opinión. Para una absoluta, P_row tiene un 1 en el activo; para una
    relativa "A rinde x más que B", 1 en A y -1 en B. Q_excess ya debe estar
    en exceso (use absolute_total_to_excess para convertir una absoluta total).
    `omega` es la varianza de la opinión (incertidumbre); si es None se usa
    `confidence` con el método proporcional (ver omega_from_confidence).
    """
    view_id: str
    P_row: "dict[str, float]"
    Q_excess: float
    omega: Optional[float] = None
    confidence: Optional[float] = None  # 0 excluye la view; 1 = restricción exacta
    expires_at: Optional[date] = None
    author: str = ""
    thesis: str = ""


def absolute_total_to_excess(q_total: float, rf: float, p_row_sum: float = 1.0) -> float:
    """Q_exceso = Q_total - rf * (P·1). Para una relativa P·1 = 0 y no cambia."""
    return q_total - rf * p_row_sum


def implied_prior(sigma: pd.DataFrame, w_ref: pd.Series, delta: float) -> pd.Series:
    """pi = delta Sigma w_ref. Exige delta > 0 (no se cambia el signo de forma oculta)."""
    if delta <= 0:
        raise ValueError("delta debe ser positiva; una calibración negativa debe declararse, no invertirse.")
    order = list(sigma.index)
    w = w_ref.reindex(order)
    if w.isna().any():
        raise ValueError("w_ref no cubre todos los activos de Sigma.")
    return pd.Series(delta * sigma.loc[order, order].to_numpy() @ w.to_numpy(), index=order, name="pi")


def omega_from_confidence(p_row: np.ndarray, sigma: np.ndarray, tau: float, confidence: float) -> float:
    """
    Método proporcional: omega = (1 - c)/c * p' (tau Sigma) p, con c en (0, 1].
    c = 1 da omega = 0 (restricción exacta); c -> 0 da omega -> infinito (la
    view casi no pesa). c = 0 no se convierte en certeza: la view se excluye
    antes de llegar aquí. La confianza NO es una probabilidad de ganar.
    """
    if not 0 < confidence <= 1:
        raise ValueError("La confianza debe estar en (0, 1].")
    base = float(p_row @ (tau * sigma) @ p_row)
    return (1 - confidence) / confidence * base


@dataclass
class ViewSet:
    P: pd.DataFrame  # K x N
    Q: pd.Series  # K
    Omega: pd.DataFrame  # K x K diagonal
    used: "list[str]"
    excluded: "dict[str, str]" = field(default_factory=dict)  # view_id -> motivo
    warnings: "list[str]" = field(default_factory=list)


def build_view_set(views: "list[View]", asset_order: "list[str]", sigma: pd.DataFrame, tau: float,
                   as_of: Optional[date] = None) -> ViewSet:
    """Arma P, Q y Omega en el orden de activos dado, validando vencimiento, duplicados y conflictos."""
    s = sigma.loc[asset_order, asset_order].to_numpy()
    rows, qs, omegas, used = [], [], [], []
    excluded: "dict[str, str]" = {}
    warnings: "list[str]" = []
    seen_ids: "set[str]" = set()
    seen_rows: "dict[tuple, tuple[str, float]]" = {}

    for v in views:
        if v.view_id in seen_ids:
            excluded[f"{v.view_id} (duplicado)"] = "ID duplicado: la misma view no se cuenta dos veces."
            continue
        seen_ids.add(v.view_id)
        unknown = set(v.P_row) - set(asset_order)
        if unknown:
            excluded[v.view_id] = f"Activos fuera del universo: {sorted(unknown)}."
            continue
        if as_of is not None and v.expires_at is not None and v.expires_at < as_of:
            excluded[v.view_id] = f"Vencida el {v.expires_at}."
            continue
        if v.confidence is not None and v.confidence == 0:
            excluded[v.view_id] = "Confianza 0: la view se excluye (no equivale a certeza)."
            continue
        p = np.array([float(v.P_row.get(a, 0.0)) for a in asset_order])
        if not np.any(p):
            excluded[v.view_id] = "Fila P vacía."
            continue
        key = tuple(np.round(p, 12))
        if key in seen_rows:
            other_id, other_q = seen_rows[key]
            if np.isclose(other_q, v.Q_excess):
                excluded[v.view_id] = f"Repite la view {other_id} (misma P y Q): no es evidencia independiente."
                continue
            warnings.append(f"Conflicto: {v.view_id} y {other_id} opinan distinto sobre la misma combinación de activos.")
        seen_rows[key] = (v.view_id, v.Q_excess)
        if v.omega is not None:
            if v.omega < 0:
                excluded[v.view_id] = "Omega negativa."
                continue
            omega = float(v.omega)
        elif v.confidence is not None:
            omega = omega_from_confidence(p, s, tau, v.confidence)
        else:
            excluded[v.view_id] = "Sin incertidumbre (Omega) ni confianza declarada."
            continue
        rows.append(p)
        qs.append(float(v.Q_excess))
        omegas.append(omega)
        used.append(v.view_id)

    P = pd.DataFrame(rows, index=used, columns=asset_order) if rows else pd.DataFrame(columns=asset_order, dtype=float)
    Q = pd.Series(qs, index=used, dtype=float)
    Omega = pd.DataFrame(np.diag(omegas) if omegas else np.zeros((0, 0)), index=used, columns=used)
    return ViewSet(P=P, Q=Q, Omega=Omega, used=used, excluded=excluded, warnings=warnings)


@dataclass
class BLResult:
    prior: pd.Series  # pi (exceso)
    posterior: pd.Series  # mu_BL (exceso)
    M: pd.DataFrame  # incertidumbre posterior de la media
    sigma_predictive: pd.DataFrame  # Sigma + M
    n_views: int
    condition_A: float  # condicionamiento de A (inf si no hay views)
    view_residuals: Optional[pd.Series] = None  # P mu_BL - Q


def posterior(sigma: pd.DataFrame, prior: pd.Series, tau: float, view_set: ViewSet) -> BLResult:
    if tau <= 0:
        raise ValueError("tau debe ser positiva.")
    order = list(sigma.index)
    if list(prior.index) != order:
        prior = prior.reindex(order)
    if prior.isna().any():
        raise ValueError("El prior no cubre todos los activos.")
    s = sigma.to_numpy(dtype=float)
    pi = prior.to_numpy(dtype=float)
    B = tau * s
    k = len(view_set.Q)
    if k == 0:
        M = B
        return BLResult(
            prior=prior, posterior=prior.copy().rename("mu_BL"), M=pd.DataFrame(M, index=order, columns=order),
            sigma_predictive=pd.DataFrame(s + M, index=order, columns=order), n_views=0, condition_A=float("inf"),
        )
    P = view_set.P.loc[:, order].to_numpy(dtype=float)
    if P.shape != (k, len(order)):
        raise ValueError(f"P debe ser {k}x{len(order)}; es {P.shape}.")
    Q = view_set.Q.to_numpy(dtype=float)
    Omega = view_set.Omega.to_numpy(dtype=float)
    A = P @ B @ P.T + Omega
    cond = float(np.linalg.cond(A))
    if not np.isfinite(cond) or cond > 1e12:
        raise ValueError("A = P tau Sigma P' + Omega es singular o está mal condicionada (views redundantes con confianza total).")
    mu_bl = pi + B @ P.T @ np.linalg.solve(A, Q - P @ pi)
    M = B - B @ P.T @ np.linalg.solve(A, P @ B)
    M = (M + M.T) / 2
    return BLResult(
        prior=prior,
        posterior=pd.Series(mu_bl, index=order, name="mu_BL"),
        M=pd.DataFrame(M, index=order, columns=order),
        sigma_predictive=pd.DataFrame(s + M, index=order, columns=order),
        n_views=k,
        condition_A=cond,
        view_residuals=pd.Series(P @ mu_bl - Q, index=view_set.used),
    )
