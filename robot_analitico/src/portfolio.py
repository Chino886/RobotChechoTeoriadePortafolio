"""
Capa de cartera v2 (guía V2, secciones 4 y 5): retornos simples para agregar
capital, matrices de covarianza/correlación con diagnóstico, riesgo de
cartera con contribuciones, y optimización media-varianza (Markowitz) con
conjunto factible explícito.

Convención (ampliación v2, registrada en README y AGENTS):
- La capa individual de la v1 sigue usando g_t = ln(P_t/P_{t-1}).
- La capa de cartera usa retornos SIMPLES R_t = exp(g_t) - 1 = P_t/P_{t-1} - 1,
  porque el retorno de una cartera es R_p = sum_i w_i R_i. El promedio
  ponderado de logs NO es el retorno de la cartera.
- Retornos en decimales, covarianza en decimal al cuadrado, correlación sin
  unidad. La optimización se resuelve en la frecuencia nativa de los datos.

Las decisiones financieras (cotas de pesos, rf, gamma, universo) entran como
parámetros: este módulo no las elige.
"""
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd
from scipy.optimize import linprog, minimize

# Tolerancias numéricas (escala de retornos decimales).
WEIGHT_SUM_ATOL = 1e-8
ZERO_VARIANCE_ATOL = 1e-14
EIGEN_ATOL = 1e-12
SOLVER_NAME = "scipy.optimize (SLSQP / HiGHS)"


# ---------------------------------------------------------------------------
# Retornos
# ---------------------------------------------------------------------------

def simple_from_log(log_returns):
    """R = exp(g) - 1. Convierte log-rendimientos a rendimientos simples."""
    return np.expm1(log_returns)


def portfolio_simple_return(weights, simple_returns) -> float:
    """R_p = sum_i w_i R_i (pesos al inicio del periodo)."""
    return float(np.dot(np.asarray(weights, dtype=float), np.asarray(simple_returns, dtype=float)))


def portfolio_log_return(weights, simple_returns) -> float:
    """Log-rendimiento de la cartera: ln(1 + R_p), NO sum_i w_i g_i."""
    return float(np.log1p(portfolio_simple_return(weights, simple_returns)))


@dataclass
class ReturnsSample:
    returns: pd.DataFrame  # filas comunes, columnas = activos (orden conservado)
    n_before: int  # filas de rendimientos antes de la máscara común
    n_after: int  # filas después de la máscara común


def simple_returns_matrix(prices: pd.DataFrame) -> ReturnsSample:
    """
    Rendimientos simples por activo con pct_change(fill_method=None) (no se
    rellenan huecos), y DESPUÉS una máscara común de filas completas (guía
    3.2). Se registra cuántas filas había antes y después.
    """
    if prices.empty:
        raise ValueError("No hay precios.")
    if not prices.index.is_monotonic_increasing:
        prices = prices.sort_index()
    if prices.index.has_duplicates:
        raise ValueError("El índice de fechas tiene duplicados.")
    values = prices.to_numpy(dtype=float)
    if not np.isfinite(values[~np.isnan(values)]).all() or (values[~np.isnan(values)] <= 0).any():
        raise ValueError("Hay precios infinitos o no positivos.")
    raw = prices.pct_change(fill_method=None).iloc[1:]
    mask = raw.notna().all(axis=1)
    common = raw.loc[mask]
    return ReturnsSample(returns=common, n_before=len(raw), n_after=len(common))


# ---------------------------------------------------------------------------
# Covarianza, correlación y diagnóstico
# ---------------------------------------------------------------------------

def covariance_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    """
    Sigma = (R - mu)'(R - mu) / (T - 1) sobre una muestra común (sin
    faltantes). Se exige muestra común para no caer en la eliminación por
    pares de pandas, que puede dar matrices no PSD.
    """
    if returns.isna().any().any():
        raise ValueError("La matriz de rendimientos tiene faltantes: aplique antes la muestra común.")
    if len(returns) < 2:
        raise ValueError("Se necesitan al menos 2 observaciones comunes.")
    centered = returns - returns.mean()
    sigma = centered.T @ centered / (len(returns) - 1)
    return sigma.loc[returns.columns, returns.columns]


def correlation_matrix(sigma: pd.DataFrame) -> pd.DataFrame:
    """C_ij = Sigma_ij / sqrt(Sigma_ii Sigma_jj). Indefinida (NaN) si una varianza es cero."""
    variances = np.diag(sigma.to_numpy(dtype=float))
    std = np.sqrt(np.where(variances > ZERO_VARIANCE_ATOL, variances, np.nan))
    corr = sigma.to_numpy(dtype=float) / np.outer(std, std)
    return pd.DataFrame(corr, index=sigma.index, columns=sigma.columns)


@dataclass
class CovarianceDiagnostics:
    symmetric: bool
    finite: bool
    n_assets: int
    rank: int
    min_eigenvalue: float
    max_eigenvalue: float
    condition_number: float  # inf si es singular
    psd: bool  # semidefinida positiva (autovalores >= -tolerancia)
    singular: bool  # PSD pero sin inversa
    zero_variance_assets: "list[str]"

    @property
    def status(self) -> str:
        if not (self.symmetric and self.finite):
            return "inválida"
        if not self.psd:
            return "indefinida (no PSD)"
        if self.singular:
            return "PSD singular (sin inversa)"
        return "definida positiva"


def diagnose_covariance(sigma: pd.DataFrame) -> CovarianceDiagnostics:
    values = sigma.to_numpy(dtype=float)
    finite = bool(np.isfinite(values).all())
    symmetric = bool(finite and np.allclose(values, values.T, atol=1e-12, rtol=0))
    if not finite:
        return CovarianceDiagnostics(symmetric, finite, len(values), 0, np.nan, np.nan, np.inf, False, False, [])
    eig = np.linalg.eigvalsh((values + values.T) / 2)
    scale = max(1.0, float(np.abs(eig).max()))
    tol = EIGEN_ATOL * scale
    psd = bool(eig.min() >= -tol)
    rank = int((eig > tol).sum())
    singular = psd and rank < len(values)
    cond = float(eig.max() / eig.min()) if eig.min() > tol else float("inf")
    zero_var = [str(name) for name, v in zip(sigma.index, np.diag(values)) if v <= ZERO_VARIANCE_ATOL]
    return CovarianceDiagnostics(
        symmetric=symmetric, finite=finite, n_assets=len(values), rank=rank,
        min_eigenvalue=float(eig.min()), max_eigenvalue=float(eig.max()),
        condition_number=cond, psd=psd, singular=singular, zero_variance_assets=zero_var,
    )


# ---------------------------------------------------------------------------
# Frecuencia y tasa libre de riesgo
# ---------------------------------------------------------------------------

def rf_per_period(rf_effective_annual: float, periods_per_year: int) -> float:
    """rf_periodo = (1 + rf_EA)^(1/m) - 1."""
    return float((1.0 + rf_effective_annual) ** (1.0 / periods_per_year) - 1.0)


def annualize_mean_simple(mu_period, periods_per_year: int):
    """mu_anual = m * mu (convención aritmética, no retorno compuesto exacto)."""
    return mu_period * periods_per_year


def annualize_sigma(sigma_period, periods_per_year: int):
    """sigma_anual = sqrt(m) * sigma (supone independencia temporal)."""
    return sigma_period * np.sqrt(periods_per_year)


# ---------------------------------------------------------------------------
# Riesgo de cartera
# ---------------------------------------------------------------------------

def _aligned(weights, mu=None, sigma=None):
    """Reindexa pesos (y mu/Sigma) por etiquetas antes de operar."""
    if isinstance(weights, pd.Series):
        order = list(weights.index)
        if sigma is not None:
            sigma = sigma.loc[order, order]
        if mu is not None:
            mu = mu.loc[order]
    w = np.asarray(weights, dtype=float)
    m = None if mu is None else np.asarray(mu, dtype=float)
    s = None if sigma is None else np.asarray(sigma, dtype=float)
    return w, m, s


@dataclass
class PortfolioStats:
    mean: float  # w'mu
    variance: float  # w'Sigma w
    volatility: float  # sqrt(var)


def portfolio_stats(weights, mu, sigma) -> PortfolioStats:
    w, m, s = _aligned(weights, mu, sigma)
    var = float(w @ s @ w)
    var = max(var, 0.0) if var > -1e-15 else var
    return PortfolioStats(mean=float(w @ m), variance=var, volatility=float(np.sqrt(var)) if var >= 0 else float("nan"))


@dataclass
class RiskContributions:
    contributions: pd.Series  # RC_i = w_i (Sigma w)_i / sigma_p; suman sigma_p
    percent: pd.Series  # RC_i / sigma_p
    volatility: float
    zero_risk: bool  # rama explícita: sigma_p = 0, sin división


def risk_contributions(weights: pd.Series, sigma: pd.DataFrame) -> RiskContributions:
    order = list(weights.index)
    s = sigma.loc[order, order].to_numpy(dtype=float)
    w = weights.to_numpy(dtype=float)
    marginal = s @ w
    var = float(w @ marginal)
    if var <= ZERO_VARIANCE_ATOL:
        zeros = pd.Series(0.0, index=order)
        return RiskContributions(contributions=zeros, percent=zeros * np.nan, volatility=0.0, zero_risk=True)
    vol = float(np.sqrt(var))
    rc = pd.Series(w * marginal / vol, index=order)
    return RiskContributions(contributions=rc, percent=rc / vol, volatility=vol, zero_risk=False)


def weighted_average_volatility(weights, sigma) -> float:
    """Promedio ponderado de volatilidades: NO es el riesgo de la cartera (solo para contrastar)."""
    w, _, s = _aligned(weights, None, sigma)
    return float(w @ np.sqrt(np.diag(s)))


# ---------------------------------------------------------------------------
# Conjunto factible y optimización
# ---------------------------------------------------------------------------

@dataclass
class OptimizationResult:
    name: str
    status: str  # "óptimo", "inviable", "no acotado", "falla numérica", "premio no positivo"
    weights: Optional[pd.Series] = None
    mean: float = float("nan")
    volatility: float = float("nan")
    message: str = ""
    solver: str = SOLVER_NAME
    iterations: int = 0
    budget_residual: float = float("nan")  # |sum(w) - 1|
    active_bounds: "list[str]" = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "óptimo"


def check_bounds(bounds: "list[tuple[Optional[float], Optional[float]]]") -> Optional[str]:
    """Devuelve un motivo si las cotas hacen imposible sumar 1; None si son factibles."""
    for lo, hi in bounds:
        if lo is not None and hi is not None and lo > hi:
            return f"Cota inferior {lo} mayor que la superior {hi}."
    lows = [lo for lo, _ in bounds]
    highs = [hi for _, hi in bounds]
    if all(lo is not None for lo in lows) and sum(lows) > 1 + WEIGHT_SUM_ATOL:
        return f"La suma de cotas inferiores ({sum(lows):.4f}) supera 1."
    if all(hi is not None for hi in highs) and sum(highs) < 1 - WEIGHT_SUM_ATOL:
        return f"La suma de cotas superiores ({sum(highs):.4f}) es menor que 1."
    return None


def _finish(name, res_x, mu, sigma, labels, bounds, message, iterations) -> OptimizationResult:
    w = pd.Series(res_x, index=labels)
    stats = portfolio_stats(w.to_numpy(), mu, sigma)
    active = []
    for label, wi, (lo, hi) in zip(labels, res_x, bounds):
        if lo is not None and abs(wi - lo) <= 1e-7:
            active.append(f"{label} en cota inferior {lo:g}")
        if hi is not None and abs(wi - hi) <= 1e-7:
            active.append(f"{label} en cota superior {hi:g}")
    return OptimizationResult(
        name=name, status="óptimo", weights=w, mean=stats.mean, volatility=stats.volatility,
        message=message, iterations=iterations, budget_residual=abs(float(np.sum(res_x)) - 1.0),
        active_bounds=active,
    )


def _labels(mu) -> "list[str]":
    return list(mu.index) if isinstance(mu, pd.Series) else [f"A{i + 1}" for i in range(len(mu))]


def _slsqp(objective, x0, bounds, constraints):
    return minimize(
        objective, x0, method="SLSQP", bounds=bounds, constraints=constraints,
        options={"ftol": 1e-15, "maxiter": 1000},
    )


def _start(bounds, n) -> np.ndarray:
    x0 = np.full(n, 1.0 / n)
    lo = np.array([b[0] if b[0] is not None else -np.inf for b in bounds])
    hi = np.array([b[1] if b[1] is not None else np.inf for b in bounds])
    return np.clip(x0, lo, hi)


def gmv_analytic(sigma) -> np.ndarray:
    """Control analítico sin cotas: w = Sigma^-1 1 / (1' Sigma^-1 1). Solo válido con inversa y cotas inactivas."""
    s = np.asarray(sigma, dtype=float)
    ones = np.ones(len(s))
    x = np.linalg.solve(s, ones)
    return x / x.sum()


def max_expected_return(mu, bounds, sigma=None) -> OptimizationResult:
    """Máximo w'mu sujeto a sum(w)=1 y cotas (programación lineal). Puede ser no acotado sin límites."""
    labels = _labels(mu)
    reason = check_bounds(bounds)
    if reason:
        return OptimizationResult(name="Máximo rendimiento esperado", status="inviable", message=reason)
    m = np.asarray(mu, dtype=float)
    res = linprog(-m, A_eq=np.ones((1, len(m))), b_eq=[1.0], bounds=bounds, method="highs")
    if res.status == 2:
        return OptimizationResult(name="Máximo rendimiento esperado", status="inviable", message=res.message)
    if res.status == 3:
        return OptimizationResult(
            name="Máximo rendimiento esperado", status="no acotado",
            message="Sin límites a los pesos el rendimiento esperado puede crecer sin fin (apalancamiento ilimitado).",
        )
    if not res.success:
        return OptimizationResult(name="Máximo rendimiento esperado", status="falla numérica", message=res.message)
    s = np.zeros((len(m), len(m))) if sigma is None else np.asarray(sigma, dtype=float)
    result = _finish("Máximo rendimiento esperado", res.x, m, s, labels, bounds, res.message, res.nit)
    if sigma is None:
        result.volatility = float("nan")  # sin Sigma no se informa riesgo
    return result


def min_variance(mu, sigma, bounds, target_return: Optional[float] = None, name: str = "Mínima varianza global") -> OptimizationResult:
    """
    min w'Sigma w  s.a.  sum(w)=1, cotas, y (opcional) w'mu = objetivo.
    Sin objetivo es la cartera global de mínima varianza (no depende de mu).
    """
    labels = _labels(mu)
    reason = check_bounds(bounds)
    if reason:
        return OptimizationResult(name=name, status="inviable", message=reason)
    m = np.asarray(mu, dtype=float)
    s = np.asarray(sigma, dtype=float)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)}]
    if target_return is not None:
        # Antes de optimizar: ¿el objetivo está entre el mínimo y el máximo rendimiento alcanzables?
        top, bottom = max_expected_return(m, bounds), max_expected_return(-m, bounds)
        if top.ok and bottom.ok and not (-bottom.mean - 1e-12 <= target_return <= top.mean + 1e-12):
            return OptimizationResult(
                name=name, status="inviable",
                message=f"El objetivo {target_return:.4%} está fuera del rango alcanzable "
                        f"[{-bottom.mean:.4%}, {top.mean:.4%}] con estas cotas.",
            )
        cons.append({"type": "eq", "fun": lambda w: w @ m - target_return, "jac": lambda w: m})
    res = _slsqp(lambda w: w @ s @ w, _start(bounds, len(m)), bounds, cons)
    if not res.success:
        status = "inviable" if "incompatible" in str(res.message).lower() else "falla numérica"
        return OptimizationResult(name=name, status=status, message=str(res.message), iterations=int(res.nit))
    if abs(np.sum(res.x) - 1) > 1e-6 or (target_return is not None and abs(res.x @ m - target_return) > 1e-6):
        return OptimizationResult(name=name, status="inviable", message="Las restricciones no se cumplen con este objetivo.")
    return _finish(name, res.x, m, s, labels, bounds, str(res.message), int(res.nit))


def max_sharpe(mu, sigma, rf_period: float, bounds) -> OptimizationResult:
    """
    Cartera tangente: máximo (w'mu - rf)/sqrt(w'Sigma w) dentro de las cotas.
    Si ninguna cartera factible tiene premio positivo, no hay tangente
    significativa: se informa en lugar de forzarla.
    """
    name = "Tangente (máximo Sharpe)"
    best = max_expected_return(mu, bounds)
    if not best.ok:
        if best.status == "no acotado":
            return OptimizationResult(name=name, status="no acotado", message="Sin cotas el Sharpe no queda bien definido con este solver; fije límites.")
        return OptimizationResult(name=name, status=best.status, message=best.message)
    if best.mean - rf_period <= 0:
        return OptimizationResult(
            name=name, status="premio no positivo",
            message="Ninguna cartera factible supera la tasa libre de riesgo: no hay tangente con premio positivo.",
        )
    labels = _labels(mu)
    m = np.asarray(mu, dtype=float)
    s = np.asarray(sigma, dtype=float)

    def neg_sharpe(w):
        var = w @ s @ w
        return -(w @ m - rf_period) / np.sqrt(max(var, 1e-30))

    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)}]
    starts = [_start(bounds, len(m)), best.weights.to_numpy()]
    results = [_slsqp(neg_sharpe, x0, bounds, cons) for x0 in starts]
    results = [r for r in results if r.success]
    if not results:
        return OptimizationResult(name=name, status="falla numérica", message="El solver no convergió.")
    res = min(results, key=lambda r: r.fun)
    return _finish(name, res.x, m, s, labels, bounds, str(res.message), int(res.nit))


def personal_optimum(mu, sigma, gamma: float, bounds) -> OptimizationResult:
    """
    Óptimo personal: máximo U = w'mu - (gamma/2) w'Sigma w dentro de las
    cotas. gamma (aversión al riesgo) la decide el equipo; aquí solo se usa.
    """
    name = "Óptimo personal (utilidad media-varianza)"
    if not gamma or gamma <= 0:
        return OptimizationResult(name=name, status="inviable", message="gamma debe ser positiva.")
    reason = check_bounds(bounds)
    if reason:
        return OptimizationResult(name=name, status="inviable", message=reason)
    labels = _labels(mu)
    m = np.asarray(mu, dtype=float)
    s = np.asarray(sigma, dtype=float)
    cons = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0, "jac": lambda w: np.ones_like(w)}]
    res = _slsqp(lambda w: -(w @ m - gamma / 2 * (w @ s @ w)), _start(bounds, len(m)), bounds, cons)
    if not res.success:
        return OptimizationResult(name=name, status="falla numérica", message=str(res.message))
    return _finish(name, res.x, m, s, labels, bounds, str(res.message), int(res.nit))


def efficient_frontier(mu, sigma, bounds, n_points: int = 30) -> pd.DataFrame:
    """
    Frontera de mínima varianza calculada por optimización (no por nube
    simulada): para cada retorno objetivo alcanzable se resuelve min w'Sigma w.
    La rama 'eficiente' va de la GMV al máximo retorno; la rama 'no eficiente'
    va del mínimo retorno alcanzable a la GMV, y solo existe si ese rango no
    es degenerado.
    """
    m = np.asarray(mu, dtype=float)
    gmv = min_variance(mu, sigma, bounds)
    hi = max_expected_return(mu, bounds)
    lo = max_expected_return(-m if not isinstance(mu, pd.Series) else -mu, bounds)
    rows = []
    if not (gmv.ok and hi.ok and lo.ok):
        return pd.DataFrame(columns=["objetivo", "volatilidad", "rama", "estado"])
    r_min, r_gmv, r_max = -lo.mean, gmv.mean, hi.mean
    branches = []
    if r_gmv - r_min > 1e-10:
        branches.append(("no eficiente", np.linspace(r_min, r_gmv, max(n_points // 2, 2))[:-1]))
    branches.append(("eficiente", np.linspace(r_gmv, r_max, n_points) if r_max - r_gmv > 1e-10 else np.array([r_gmv])))
    for branch, targets in branches:
        for target in targets:
            res = min_variance(mu, sigma, bounds, target_return=float(target), name="frontera")
            rows.append({
                "objetivo": float(target),
                "volatilidad": res.volatility if res.ok else np.nan,
                "rama": branch,
                "estado": res.status,
            })
    return pd.DataFrame(rows)


def random_portfolios(mu, sigma, bounds, n: int = 2000, seed: int = 7) -> pd.DataFrame:
    """Nube de carteras factibles al azar (ilustrativa; NO sustituye la frontera calculada)."""
    rng = np.random.default_rng(seed)
    m = np.asarray(mu, dtype=float)
    s = np.asarray(sigma, dtype=float)
    k = len(m)
    lo = np.array([b[0] if b[0] is not None else 0.0 for b in bounds])
    hi = np.array([b[1] if b[1] is not None else 1.0 for b in bounds])
    out = []
    for _ in range(n * 3):
        w = lo + rng.dirichlet(np.ones(k)) * max(1 - lo.sum(), 0)
        if (w <= hi + 1e-12).all() and abs(w.sum() - 1) < 1e-9:
            out.append((float(w @ m), float(np.sqrt(max(w @ s @ w, 0)))))
        if len(out) >= n:
            break
    return pd.DataFrame(out, columns=["media", "volatilidad"])


# ---------------------------------------------------------------------------
# CAL (línea de asignación de capital)
# ---------------------------------------------------------------------------

def cal_point(rf: float, mean_t: float, vol_t: float, y: float) -> "tuple[float, float]":
    """E(R_c) = rf + y (mu_T - rf); sigma_c = |y| sigma_T."""
    return rf + y * (mean_t - rf), abs(y) * vol_t


def optimal_risky_share(rf: float, mean_t: float, vol_t: float, gamma: float) -> float:
    """y* = (mu_T - rf) / (gamma sigma_T^2), sin restricciones (puede ser > 1 o < 0)."""
    return (mean_t - rf) / (gamma * vol_t ** 2)


def optimal_risky_share_no_debt(rf: float, mean_t: float, vol_t: float, gamma: float) -> float:
    """
    y* con 0 <= y <= 1 (sin endeudamiento ni venta en corto del activo sin
    riesgo). Como la utilidad es cóncava en y, el óptimo restringido es el
    óptimo libre proyectado al intervalo; esto NO implica que la tangente siga
    siendo la mejor cartera riesgosa bajo otras restricciones.
    """
    return float(min(max(optimal_risky_share(rf, mean_t, vol_t, gamma), 0.0), 1.0))


# ---------------------------------------------------------------------------
# Riesgo móvil (panel de riesgo, guía 4.4)
# ---------------------------------------------------------------------------

def portfolio_return_series(returns: pd.DataFrame, weights: pd.Series) -> pd.Series:
    """
    R_p,t = sum_i w_i R_i,t con pesos CONSTANTES (equivale a rebalancear a
    esos pesos cada periodo, sin costos). Mantener cantidades es otra
    contabilidad (ver src/rebalance.py).
    """
    w = weights.reindex(returns.columns)
    if w.isna().any():
        raise ValueError("Faltan pesos para algunos activos de la matriz.")
    return (returns * w).sum(axis=1).rename("cartera")


def rolling_volatility(returns, window: int) -> "pd.DataFrame | pd.Series":
    """Desviación estándar móvil (ddof=1) con ventana completa; sin anualizar."""
    if window < 2:
        raise ValueError("La ventana debe tener al menos 2 observaciones.")
    return returns.rolling(window, min_periods=window).std(ddof=1)


def rolling_correlation(a: pd.Series, b: pd.Series, window: int) -> pd.Series:
    """Correlación móvil entre dos series de rendimientos (ventana completa)."""
    return a.rolling(window, min_periods=window).corr(b)


def drawdown_from_returns(returns: pd.Series) -> pd.Series:
    """Caída desde el máximo previo del valor acumulado (1 + R)."""
    wealth = (1 + returns).cumprod()
    return wealth / wealth.cummax() - 1
