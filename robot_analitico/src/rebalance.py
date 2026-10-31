"""
Rebalanceo simulado con nueva información (guía V2, sección 7). Solo
contabilidad pedagógica: no hay bróker ni órdenes reales.

- Deriva sin flujos: w_i,pre = w_i,post_anterior (1 + R_i) / (1 + R_p).
- Turnover unilateral = 0,5 * sum |delta w| (caso normalizado sin flujos).
- Costos sobre el nominal REAL de cada compra y venta: costo = c * sum |operación|.
- Los pesos objetivo se aplican sobre el patrimonio posterior a costos:
  V_post = V_pre - costos (se resuelve por punto fijo).
- No se permite caja negativa ni deuda no autorizada: si la operación la
  produciría, se suspende la decisión con su motivo.
- Un evento repetido no produce una segunda decisión (queda registrado como
  "duplicado, sin decisión"); datos viejos o asincrónicos suspenden la
  decisión y conservan la cartera.
- La caja mínima se separa: los pesos objetivo se aplican sobre
  (V_post - caja mínima).
- En la simulación de política, cada decisión reestima mu y Sigma solo con
  la ventana conocida en esa fecha y recalcula el objetivo (guía 7.1).

La política (bandas, calendario, espera mínima, costos, caja mínima) la
define el equipo; aquí entra como parámetro.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, Optional

import numpy as np
import pandas as pd

ACTION_REBALANCE = "rebalancear"
ACTION_ABSTAIN = "abstenerse"
ACTION_SUSPEND = "suspendido"
ACTION_DUPLICATE = "duplicado"


def drifted_weights(previous_weights: pd.Series, simple_returns: pd.Series) -> pd.Series:
    """Pesos después de un periodo sin operar ni flujos."""
    r = simple_returns.reindex(previous_weights.index)
    rp = float((previous_weights * r).sum())
    return previous_weights * (1 + r) / (1 + rp)


def turnover(weights_before: pd.Series, weights_after: pd.Series) -> float:
    idx = weights_before.index.union(weights_after.index)
    return 0.5 * float((weights_after.reindex(idx, fill_value=0) - weights_before.reindex(idx, fill_value=0)).abs().sum())


@dataclass
class Book:
    """Libro de posiciones: cantidades por activo y caja, en una moneda."""
    quantities: pd.Series
    cash: float = 0.0
    currency: str = "USD"

    def values(self, prices: pd.Series) -> pd.Series:
        p = prices.reindex(self.quantities.index)
        if p.isna().any():
            raise ValueError(f"Faltan precios para: {list(p[p.isna()].index)}.")
        return self.quantities * p

    def equity(self, prices: pd.Series) -> float:
        return float(self.values(prices).sum() + self.cash)

    def weights(self, prices: pd.Series) -> pd.Series:
        """Pesos de los activos sobre el patrimonio total (la caja es el resto)."""
        return self.values(prices) / self.equity(prices)


@dataclass
class TradePlan:
    trades_value: pd.Series  # + compra, - venta (en moneda)
    trades_quantity: pd.Series
    traded_notional: float  # sum |operación|
    costs: float
    equity_before: float
    equity_after: float
    cash_after: float
    weights_before: pd.Series
    weights_after: pd.Series
    turnover: float
    new_book: Book


def plan_rebalance(book: Book, prices: pd.Series, target_weights: pd.Series, cost_rate: float,
                   fractional: bool = True, max_iter: int = 100, cash_minimum: float = 0.0) -> TradePlan:
    """
    Operaciones para llevar el libro a `target_weights` aplicados sobre el
    patrimonio invertible: (patrimonio posterior a costos - caja mínima). Si
    los pesos objetivo suman menos de 1, el resto también queda en caja. Con
    fractional=False se redondean cantidades hacia cero.
    """
    order = list(book.quantities.index)
    target = target_weights.reindex(order).fillna(0.0)
    if (target < -1e-12).any():
        raise ValueError("Pesos objetivo negativos: los cortos no están autorizados en esta simulación.")
    if target.sum() > 1 + 1e-9:
        raise ValueError("Los pesos objetivo suman más de 1: implicaría deuda no autorizada.")
    if cash_minimum < 0:
        raise ValueError("La caja mínima no puede ser negativa.")
    p = prices.reindex(order)
    values = book.values(p)
    v_pre = book.equity(p)

    def trades_for(v_post):
        investable = max(v_post - cash_minimum, 0.0)
        if fractional:
            return target * investable - values
        return (np.trunc((target * investable) / p) - book.quantities) * p

    v_post = v_pre
    for _ in range(max_iter):
        costs = cost_rate * float(trades_for(v_post).abs().sum())
        new_v = v_pre - costs
        if abs(new_v - v_post) < 1e-10:
            v_post = new_v
            break
        v_post = new_v

    trades = trades_for(v_post)
    traded = float(trades.abs().sum())
    costs = cost_rate * traded
    cash_after = book.cash - float(trades.sum()) - costs
    new_q = book.quantities + trades / p
    new_book = Book(quantities=new_q, cash=cash_after, currency=book.currency)
    equity_after = new_book.equity(p)
    w_before = values / v_pre
    w_after = new_book.weights(p)
    return TradePlan(
        trades_value=trades, trades_quantity=trades / p, traded_notional=traded, costs=costs,
        equity_before=v_pre, equity_after=equity_after, cash_after=cash_after,
        weights_before=w_before, weights_after=w_after, turnover=turnover(w_before, w_after), new_book=new_book,
    )


@dataclass
class RebalancePolicy:
    """Parámetros de la política del equipo (todos opcionales salvo el costo)."""
    cost_rate: float
    weight_band: Optional[float] = None  # opera si alguna |w - objetivo| supera la banda
    calendar_days: Optional[int] = None  # regla periódica: opera si pasaron estos días
    min_days_between: int = 0  # espera mínima entre decisiones
    max_quote_age: Optional[timedelta] = None  # dato más viejo que esto suspende
    max_asset_time_skew: Optional[timedelta] = None  # precios asincrónicos suspenden
    max_turnover: Optional[float] = None  # tope de rotación por decisión
    cash_minimum: float = 0.0  # se deja aparte; los pesos se aplican al resto
    fractional: bool = True
    information_events: bool = True  # una view que vence o cambia dispara revisión
    cost_benefit_margin: Optional[float] = None  # P85: operar solo si mejora de utilidad - costos >= margen


@dataclass
class MarketEvent:
    event_id: str
    at: datetime  # hora en que la información se conoce
    prices: pd.Series
    quote_times: "Optional[dict[str, datetime]]" = None
    kind: str = "precio"  # "precio" o "información" (vencimiento/cambio de view, noticia)
    description: str = ""


@dataclass
class TargetInfo:
    """Objetivo recalculado en una fecha: pesos teóricos, ventana usada y utilidad para el costo-beneficio."""
    weights: Optional[pd.Series]
    window: "Optional[tuple]" = None  # (primera fecha, última fecha) de la ventana de estimación
    rule: str = ""
    message: str = ""
    utility: Optional[Callable[[pd.Series], float]] = None


@dataclass
class Decision:
    event_id: str
    at: datetime
    action: str
    reason: str
    plan: Optional[TradePlan] = None
    window: "Optional[tuple]" = None
    theoretical: Optional[pd.Series] = None  # pesos objetivo (teóricos)
    realized: Optional[pd.Series] = None  # pesos después de operar (realizados)
    trigger: str = ""


@dataclass
class Rebalancer:
    """Aplica la política a eventos sucesivos y deja registro de cada decisión (incluidas abstenciones)."""
    policy: RebalancePolicy
    book: Book
    target_weights: pd.Series
    last_trade_at: Optional[datetime] = None
    processed_events: "set[str]" = field(default_factory=set)
    log: "list[Decision]" = field(default_factory=list)
    utility: Optional[Callable[[pd.Series], float]] = None  # U(w) por periodo, para la regla costo-beneficio
    target_provider: Optional[Callable[[MarketEvent], TargetInfo]] = None  # reestimación en cada decisión

    def _record(self, event: MarketEvent, action: str, reason: str, plan: Optional[TradePlan] = None, **extra) -> Decision:
        decision = Decision(event_id=event.event_id, at=event.at, action=action, reason=reason, plan=plan, **extra)
        self.log.append(decision)
        return decision

    def on_event(self, event: MarketEvent, now: Optional[datetime] = None) -> Optional[Decision]:
        if event.event_id in self.processed_events:
            self._record(event, ACTION_DUPLICATE, "duplicado, sin decisión")
            return None  # no hay segunda decisión
        self.processed_events.add(event.event_id)
        pol = self.policy
        now = now or event.at

        if event.quote_times:
            times = list(event.quote_times.values())
            if pol.max_quote_age is not None and now - min(times) > pol.max_quote_age:
                return self._record(event, ACTION_SUSPEND, "Dato obsoleto: supera la antigüedad máxima. Se conserva la cartera.")
            if pol.max_asset_time_skew is not None and max(times) - min(times) > pol.max_asset_time_skew:
                return self._record(event, ACTION_SUSPEND, "Precios asincrónicos entre activos. Se conserva la cartera.")
        if event.prices.reindex(self.book.quantities.index).isna().any():
            return self._record(event, ACTION_SUSPEND, "Falta el precio de un activo con posición: no se renormaliza en silencio.")

        if self.last_trade_at is not None and event.at - self.last_trade_at < timedelta(days=pol.min_days_between):
            return self._record(event, ACTION_ABSTAIN, f"Espera mínima de {pol.min_days_between} días sin cumplir.")

        current = self.book.weights(event.prices)
        drift = float((current - self.target_weights.reindex(current.index).fillna(0)).abs().max())
        periodic_due = (
            pol.calendar_days is not None
            and (self.last_trade_at is None or event.at - self.last_trade_at >= timedelta(days=pol.calendar_days))
        )
        band_breached = pol.weight_band is not None and drift > pol.weight_band
        info_due = pol.information_events and event.kind == "información"
        if not (periodic_due or band_breached or info_due):
            return self._record(event, ACTION_ABSTAIN, f"Deriva máxima {drift:.2%} dentro de la banda y sin fecha periódica ni evento.")
        trigger = ("evento de información: " + (event.description or event.event_id) if info_due
                   else "regla periódica" if periodic_due else f"deriva {drift:.2%} > banda {pol.weight_band:.2%}")

        window, utility = None, self.utility
        if self.target_provider is not None:
            info = self.target_provider(event)
            if info.weights is None:
                return self._record(event, ACTION_SUSPEND, f"Sin objetivo nuevo: {info.message}. Se conserva la cartera.",
                                    window=info.window, trigger=trigger)
            self.target_weights = info.weights
            window, utility = info.window, info.utility or utility

        plan = plan_rebalance(self.book, event.prices, self.target_weights, pol.cost_rate, fractional=pol.fractional,
                              cash_minimum=pol.cash_minimum)
        extra = dict(window=window, theoretical=self.target_weights.copy(), trigger=trigger)
        if plan.cash_after < pol.cash_minimum - 1e-9:
            return self._record(event, ACTION_SUSPEND, f"La operación dejaría caja {plan.cash_after:,.2f} bajo el mínimo.", plan, **extra)
        if pol.max_turnover is not None and plan.turnover > pol.max_turnover:
            return self._record(event, ACTION_ABSTAIN, f"Rotación {plan.turnover:.2%} supera el tope {pol.max_turnover:.2%}.", plan, **extra)
        if pol.cost_benefit_margin is not None and utility is not None:
            gain = utility(self.target_weights.reindex(current.index).fillna(0)) - utility(current)
            cost_frac = plan.costs / plan.equity_before if plan.equity_before else 0.0
            if gain - cost_frac < pol.cost_benefit_margin:
                return self._record(
                    event, ACTION_ABSTAIN,
                    f"La mejora de utilidad estimada ({gain:.6f}) no supera los costos ({cost_frac:.6f}) más el margen "
                    f"({pol.cost_benefit_margin:.6f}): no se opera.", plan, **extra)

        self.book = plan.new_book
        self.last_trade_at = event.at
        return self._record(event, ACTION_REBALANCE, f"Rebalanceo por {trigger}; costos {plan.costs:,.2f}.", plan,
                            realized=plan.weights_after, **extra)


TARGET_RULES = ["1/N", "GMV", "Óptimo personal", "BL posterior"]


@dataclass
class PolicyRun:
    rebalancer: Rebalancer
    prices: pd.DataFrame  # índice de precios del tramo simulado
    initial_book: Book
    initial_target: TargetInfo

    @property
    def log(self) -> "list[Decision]":
        return self.rebalancer.log


def simulate_policy(returns: pd.DataFrame, policy: RebalancePolicy, rule: str, window: int, horizon: int,
                    gamma: float, bounds, groups=None, capital: float = 10_000.0, views=None,
                    bl_delta: float = 3.0, bl_tau: float = 0.05, rf_period: float = 0.0,
                    w_ref: Optional[pd.Series] = None) -> PolicyRun:
    """
    Simula la política sobre los últimos `horizon` periodos. Cada fecha es un
    evento de precio; el vencimiento o la entrada en vigencia de una view es
    un evento de información. En cada decisión el objetivo se recalcula con
    la ventana de `window` rendimientos ANTERIORES a esa fecha.
    """
    from src.black_litterman import build_view_set, implied_prior, posterior
    from src.portfolio import covariance_matrix, min_variance, personal_optimum

    if rule not in TARGET_RULES:
        raise ValueError(f"Regla de objetivo desconocida: {rule}")
    if horizon >= len(returns) - window:
        raise ValueError("La muestra no alcanza para la ventana de estimación más el tramo simulado.")
    assets = list(returns.columns)
    views = views or []
    prices = 100 * (1 + returns).cumprod()

    def estimate(at) -> TargetInfo:
        known = returns.loc[returns.index < pd.Timestamp(at)].iloc[-window:]
        if len(known) < window:
            return TargetInfo(None, message="ventana insuficiente")
        win = (known.index[0], known.index[-1])
        mu, sigma = known.mean(), covariance_matrix(known)
        mu_used = mu
        if rule == "1/N":
            w = pd.Series(1 / len(assets), index=assets)
        elif rule == "GMV":
            res = min_variance(mu, sigma, bounds, groups=groups)
            w = res.weights if res.ok else None
        else:
            if rule == "BL posterior":
                ref = w_ref if w_ref is not None else pd.Series(1 / len(assets), index=assets)
                prior = implied_prior(sigma, ref, bl_delta)
                vs = build_view_set(views, assets, sigma, bl_tau, as_of=pd.Timestamp(at).date())
                mu_used = posterior(sigma, prior, bl_tau, vs).posterior + rf_period
            res = personal_optimum(mu_used, sigma, gamma, bounds, groups=groups)
            w = res.weights if res.ok else None
        if w is None:
            return TargetInfo(None, window=win, rule=rule, message=f"{rule}: {res.status}")
        m_arr, s_arr = mu_used.reindex(assets).to_numpy(), sigma.to_numpy()

        def utility(weights: pd.Series) -> float:
            x = weights.reindex(assets).fillna(0).to_numpy()
            return float(x @ m_arr - gamma / 2 * x @ s_arr @ x)

        return TargetInfo(w, window=win, rule=rule, utility=utility)

    sim_dates = returns.index[-horizon:]
    start = sim_dates[0]
    first = estimate(start)
    if first.weights is None:
        raise ValueError(f"No hay objetivo inicial: {first.message}")
    p0 = prices.loc[start]
    investable = capital - policy.cash_minimum
    book = Book(quantities=first.weights * investable / p0, cash=policy.cash_minimum)
    reb = Rebalancer(policy=policy, book=book, target_weights=first.weights, last_trade_at=pd.Timestamp(start).to_pydatetime(),
                     utility=first.utility, target_provider=lambda ev: estimate(ev.at))

    pending = []
    for v in views:
        if v.known_at is not None and pd.Timestamp(v.known_at) > start:
            pending.append((pd.Timestamp(v.known_at), f"view-{v.view_id}-conocida", f"entra en vigencia la view {v.view_id}"))
        if v.expires_at is not None and pd.Timestamp(v.expires_at) >= start:
            pending.append((pd.Timestamp(v.expires_at) + pd.Timedelta(days=1), f"view-{v.view_id}-vencida", f"vence la view {v.view_id}"))
    for d in sim_dates[1:]:
        row = prices.loc[d]
        for when, eid, desc in sorted(pending):
            if when <= d and eid not in reb.processed_events:
                reb.on_event(MarketEvent(eid, pd.Timestamp(d).to_pydatetime(), row, kind="información", description=desc))
        reb.on_event(MarketEvent(f"precio-{pd.Timestamp(d).date()}", pd.Timestamp(d).to_pydatetime(), row))
    return PolicyRun(rebalancer=reb, prices=prices.loc[sim_dates], initial_book=book, initial_target=first)
