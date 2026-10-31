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
- Un evento repetido no produce una segunda decisión; datos viejos o
  asincrónicos suspenden la decisión y conservan la cartera.

La política (bandas, calendario, espera mínima, costos, caja mínima) la
define el equipo; aquí entra como parámetro.
"""
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd

ACTION_REBALANCE = "rebalancear"
ACTION_ABSTAIN = "abstenerse"
ACTION_SUSPEND = "suspendido"


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
                   fractional: bool = True, max_iter: int = 100) -> TradePlan:
    """
    Operaciones para llevar el libro a `target_weights` sobre el patrimonio
    posterior a costos. Si los pesos objetivo suman menos de 1, el resto
    queda en caja. Con fractional=False se redondean cantidades hacia cero.
    """
    order = list(book.quantities.index)
    target = target_weights.reindex(order).fillna(0.0)
    if (target < -1e-12).any():
        raise ValueError("Pesos objetivo negativos: los cortos no están autorizados en esta simulación.")
    if target.sum() > 1 + 1e-9:
        raise ValueError("Los pesos objetivo suman más de 1: implicaría deuda no autorizada.")
    p = prices.reindex(order)
    values = book.values(p)
    v_pre = book.equity(p)

    v_post = v_pre
    for _ in range(max_iter):
        trades = target * v_post - values
        if not fractional:
            qty = np.trunc((target * v_post) / p) - book.quantities
            trades = qty * p
        costs = cost_rate * float(trades.abs().sum())
        new_v = v_pre - costs
        if abs(new_v - v_post) < 1e-10:
            v_post = new_v
            break
        v_post = new_v

    trades = target * v_post - values if fractional else (np.trunc((target * v_post) / p) - book.quantities) * p
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
    cash_minimum: float = 0.0
    fractional: bool = True


@dataclass
class MarketEvent:
    event_id: str
    at: datetime  # hora en que la información se conoce
    prices: pd.Series
    quote_times: "Optional[dict[str, datetime]]" = None
    kind: str = "precio"  # "periódico", "umbral", "información", "precio"
    description: str = ""


@dataclass
class Decision:
    event_id: str
    at: datetime
    action: str
    reason: str
    plan: Optional[TradePlan] = None


@dataclass
class Rebalancer:
    """Aplica la política a eventos sucesivos y deja registro de cada decisión (incluidas abstenciones)."""
    policy: RebalancePolicy
    book: Book
    target_weights: pd.Series
    last_trade_at: Optional[datetime] = None
    processed_events: "set[str]" = field(default_factory=set)
    log: "list[Decision]" = field(default_factory=list)

    def _record(self, event: MarketEvent, action: str, reason: str, plan: Optional[TradePlan] = None) -> Decision:
        decision = Decision(event_id=event.event_id, at=event.at, action=action, reason=reason, plan=plan)
        self.log.append(decision)
        return decision

    def on_event(self, event: MarketEvent, now: Optional[datetime] = None) -> Optional[Decision]:
        if event.event_id in self.processed_events:
            return None  # evento duplicado: no hay segunda decisión (ni otro registro)
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
        if not (periodic_due or band_breached):
            return self._record(event, ACTION_ABSTAIN, f"Deriva máxima {drift:.2%} dentro de la banda y sin fecha periódica.")

        plan = plan_rebalance(self.book, event.prices, self.target_weights, pol.cost_rate, fractional=pol.fractional)
        if plan.cash_after < pol.cash_minimum - 1e-9:
            return self._record(event, ACTION_SUSPEND, f"La operación dejaría caja {plan.cash_after:,.2f} bajo el mínimo.", plan)
        if pol.max_turnover is not None and plan.turnover > pol.max_turnover:
            return self._record(event, ACTION_ABSTAIN, f"Rotación {plan.turnover:.2%} supera el tope {pol.max_turnover:.2%}.", plan)

        self.book = plan.new_book
        self.last_trade_at = event.at
        trigger = "regla periódica" if periodic_due else f"deriva {drift:.2%} > banda {pol.weight_band:.2%}"
        return self._record(event, ACTION_REBALANCE, f"Rebalanceo por {trigger}; costos {plan.costs:,.2f}.", plan)
