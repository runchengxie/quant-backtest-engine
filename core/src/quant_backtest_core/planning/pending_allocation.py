"""Single-period PAPER allocation around independently uncertain outstanding fills.

No hidden account state is read. The caller supplies a complete delivered order
snapshot, fixed positive NAV and raw prices, known cash and sell/locate capacity.
Each outstanding order may independently fill any fraction in [0, 1]. A base target
is delivered holdings plus NEW fully filled trades, excluding outstanding orders.
Scenario endpoint = base target + outstanding fills; do not submit base targets as
incremental orders or subtract outstanding orders again. New orders also may fail
to fill: endpoint constraints here are conditional on their complete execution,
not guarantees over intermediate paths. Resources reserve their full amounts.

Only a single period is modeled: no repricing, funding from sale proceeds,
settlement release, cancellation, margin model, corporate actions or dynamic NAV.
Risk/return/cost optimization remains the existing base-target factor QP, not a
worst-case-return or multi-stage stochastic objective. This is never execution.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from .pending_protocol import PendingOptimizer, PendingRequest, PendingSolveResult


@dataclass(frozen=True)
class PendingOrder:
    """Delivered remaining raw shares; cancel requests remain outstanding.

    reserve_price is an assumed buy execution-price ceiling (at least raw price
    is reserved). fee_budget reserves remaining fees independently of direction.
    Delayed, unreported fills remain in remaining_quantity until delivered.
    """

    order_id: str
    symbol: str
    remaining_quantity: int
    reserve_price: float
    fee_budget: float
    observed_at: pd.Timestamp


@dataclass(frozen=True)
class PendingAllocationState:
    """Caller-attested causal snapshot; quantities and prices share raw basis.

    cash_before_reserves excludes restricted/unsettled cash and existing short
    collateral but has NOT subtracted outstanding-order reservations. Sell
    capacity includes available delivered longs plus confirmed incremental
    locates, before outstanding sales. Incremental locates exclude units already
    consumed by delivered shorts. Buying/covering does not increase capacity.
    Fees on new orders are assumed proportional to raw notional on both sides.
    All observations must be known by request.information_time. orders_as_of
    equals that time; no order may be omitted, including pending cancellations.
    delivered_quantities and NAV are revalued at the supplied fixed raw prices.
    """

    delivered_quantities: pd.Series
    raw_prices: pd.Series
    quote_times: pd.Series
    nav: float
    cash_before_reserves: float
    sell_capacity_quantities: pd.Series
    new_fee_rates: pd.Series
    outstanding_orders: tuple[PendingOrder, ...]
    delivered_at: pd.Timestamp
    orders_as_of: pd.Timestamp
    complete_order_snapshot: bool
    assumptions: str


@dataclass(frozen=True)
class PendingAllocationEnvelope:
    """Conservative base-target bounds; negative resources signal infeasibility."""

    gross_limit: float
    lower_bounds: pd.Series
    upper_bounds: pd.Series
    factor_bounds: Mapping[str, tuple[float, float]]
    net_base_bounds: tuple[float, float]
    pending_lower: pd.Series
    pending_upper: pd.Series
    pending_gross: float
    reserved_cash: float
    available_cash: float
    remaining_sell_quantities: pd.Series
    factor_increments: Mapping[str, tuple[float, float]]


@dataclass(frozen=True)
class PendingAllocationResult:
    status: Literal["optimal", "infeasible", "numerical_failure"]
    message: str
    envelope: PendingAllocationEnvelope
    base_result: PendingSolveResult | None = None
    new_trade_weights: pd.Series | None = None
    endpoint_net_bounds: tuple[float, float] | None = None
    endpoint_factor_bounds: Mapping[str, tuple[float, float]] | None = None
    endpoint_gross_upper: float | None = None
    new_cash_required: float | None = None
    paper_only: Literal[True] = field(default=True, init=False)
    executable: Literal[False] = field(default=False, init=False)


def _clock(value, information_time):
    if (
        not isinstance(value, pd.Timestamp)
        or pd.isna(value)
        or value.tzinfo is None
        or value > information_time
    ):
        raise ValueError("Observations require aware clocks no later than information_time")


def _series(value, index, name, *, integer=False, minimum=None):
    if not value.index.equals(index) or not np.isfinite(value.to_numpy(dtype=float)).all():
        raise ValueError(f"{name} requires matching finite asset values")
    if integer and (
        value.dtype.kind == "b" or (value != np.floor(value)).any() or (value.abs() > 2**53).any()
    ):
        raise ValueError(f"{name} requires raw integer shares")
    if minimum is not None and (value < minimum).any():
        raise ValueError(f"{name} below permitted minimum")


def _validate_request(r: PendingRequest) -> None:
    """Preserve execution validation without inspecting caller-owned risk fields."""
    index = r.expected_returns.index
    if index.empty or not index.is_unique or index.hasnans:
        raise ValueError("Assets must be nonempty, unique and nonmissing")
    for name in ("expected_returns", "current_weights", "lower_bounds", "upper_bounds"):
        value = getattr(r, name)
        if not value.index.equals(index) or not np.isfinite(value.to_numpy(dtype=float)).all():
            raise ValueError(f"{name} must have matching finite asset values")
    factors = r.factor_loadings
    if (
        not factors.index.equals(index)
        or not factors.columns.is_unique
        or not all(isinstance(name, str) and name for name in factors.columns)
        or not np.isfinite(factors.to_numpy(dtype=float)).all()
    ):
        raise ValueError("Factor loadings must have unique names and matching finite assets")
    for name, bounds in r.factor_bounds.items():
        if (
            name not in factors.columns
            or len(bounds) != 2
            or not np.isfinite(bounds).all()
            or bounds[0] > bounds[1]
        ):
            raise ValueError("Factor bounds must be finite, ordered and named in loadings")
    if not np.isfinite([r.gross_limit, r.net_target]).all() or r.gross_limit < 0:
        raise ValueError("Gross must be nonnegative; scalars finite")
    if (r.lower_bounds > r.upper_bounds).any():
        raise ValueError("Asset bounds must be ordered")
    for timestamp in (r.information_time, r.decision_time):
        if (
            not isinstance(timestamp, pd.Timestamp)
            or pd.isna(timestamp)
            or timestamp.tzinfo is None
        ):
            raise ValueError(
                "Valid timezone-aware pandas Timestamp information and decision times required"
            )
    if r.information_time > r.decision_time:
        raise ValueError("Information must not follow decision time")


def _validate_state(r, state, net_band):
    _validate_request(r)
    index = r.current_weights.index
    for name, integer, minimum in (
        ("delivered_quantities", True, None),
        ("raw_prices", False, 1e-12),
        ("sell_capacity_quantities", True, 0),
        ("new_fee_rates", False, 0),
    ):
        _series(getattr(state, name), index, name, integer=integer, minimum=minimum)
    if (
        not np.isfinite([state.nav, state.cash_before_reserves]).all()
        or state.nav <= 0
        or isinstance(state.nav, bool)
        or state.complete_order_snapshot is not True
        or not isinstance(state.assumptions, str)
        or not state.assumptions.strip()
    ):
        raise ValueError("Positive NAV, finite cash, complete snapshot and assumptions required")
    _clock(state.delivered_at, r.information_time)
    _clock(state.orders_as_of, r.information_time)
    if state.orders_as_of != r.information_time or state.delivered_at > state.orders_as_of:
        raise ValueError("Order snapshot must cover information_time and delivered holdings")
    if not state.quote_times.index.equals(index):
        raise ValueError("Quote clocks require matching assets")
    for clock in state.quote_times:
        _clock(clock, r.information_time)
    observed = state.delivered_quantities.astype(float) * state.raw_prices.astype(float) / state.nav
    if not np.allclose(observed, r.current_weights, rtol=0, atol=1e-12):
        raise ValueError(
            "current_weights must be actual delivered holdings at fixed raw prices/NAV"
        )
    if len(net_band) != 2 or not np.isfinite(net_band).all() or net_band[0] > net_band[1]:
        raise ValueError("Explicit finite ordered endpoint net band required")
    _validate_orders(r, state)


def _validate_orders(r, state):
    seen = set()
    for order in state.outstanding_orders:
        if (
            not isinstance(order.order_id, str)
            or not order.order_id.strip()
            or order.order_id in seen
            or order.symbol not in r.current_weights.index
            or isinstance(order.remaining_quantity, bool)
            or not isinstance(order.remaining_quantity, int)
            or not 0 < abs(order.remaining_quantity) <= 2**53
            or not np.isfinite([order.reserve_price, order.fee_budget]).all()
            or order.reserve_price <= 0
            or order.fee_budget < 0
        ):
            raise ValueError(
                "Unique known orders, signed integer remaining shares and reserves required"
            )
        seen.add(order.order_id)
        _clock(order.observed_at, state.orders_as_of)


def pending_allocation_envelope(
    r: PendingRequest,
    state: PendingAllocationState,
    *,
    net_band: tuple[float, float],
) -> PendingAllocationEnvelope:
    """Tighten linear constraints for independent fills without changing holdings.

    Net is an endpoint band, while r.net_target fixes the base-target net. Exact
    endpoint neutrality is infeasible whenever independent pending net varies.
    Gross uses triangle inequality, a sufficient bound that can reject feasible
    offsets. Factor extrema are exact for each linear exposure over the fill box.
    """
    _validate_state(r, state, net_band)
    lower, upper = r.current_weights.astype(float) * 0, r.current_weights.astype(float) * 0
    sales = state.sell_capacity_quantities.astype(float) * 0
    reserved, gross = 0.0, 0.0
    increments = {name: [0.0, 0.0] for name in r.factor_bounds}
    for order in state.outstanding_orders:
        symbol, quantity = order.symbol, order.remaining_quantity
        price = float(state.raw_prices[symbol])
        weight = quantity * price / state.nav
        lower[symbol] += min(weight, 0)
        upper[symbol] += max(weight, 0)
        gross += abs(weight)
        sales[symbol] += max(-quantity, 0)
        reserved += max(quantity, 0) * max(float(order.reserve_price), price)
        reserved += order.fee_budget
        for name, bounds in increments.items():
            exposure = weight * r.factor_loadings.loc[symbol, name]
            bounds[0] += min(exposure, 0)
            bounds[1] += max(exposure, 0)
    factor_bounds = {
        name: (lo - increments[name][0], hi - increments[name][1])
        for name, (lo, hi) in r.factor_bounds.items()
    }
    remaining = state.sell_capacity_quantities - sales
    asset_lower = np.maximum(
        r.lower_bounds - lower,
        r.current_weights - remaining * state.raw_prices / state.nav,
    )
    result = PendingAllocationEnvelope(
        r.gross_limit - gross,
        asset_lower,
        r.upper_bounds - upper,
        factor_bounds,
        (net_band[0] - float(lower.sum()), net_band[1] - float(upper.sum())),
        lower,
        upper,
        gross,
        float(reserved),
        float(state.cash_before_reserves - reserved),
        remaining,
        {name: (bounds[0], bounds[1]) for name, bounds in increments.items()},
    )
    _finite_envelope(result)
    return result


def _finite_envelope(envelope):
    scalars = [
        envelope.gross_limit,
        envelope.pending_gross,
        envelope.reserved_cash,
        envelope.available_cash,
        *envelope.net_base_bounds,
        *(v for bounds in envelope.factor_bounds.values() for v in bounds),
        *envelope.lower_bounds,
        *envelope.upper_bounds,
    ]
    if not np.isfinite(scalars).all():
        raise ValueError("Nonfinite derived pending envelope")


def _infeasible(envelope, base_net):
    return (
        envelope.gross_limit < 0
        or envelope.available_cash < 0
        or (envelope.remaining_sell_quantities < 0).any()
        or (envelope.lower_bounds > envelope.upper_bounds).any()
        or not envelope.net_base_bounds[0] <= base_net <= envelope.net_base_bounds[1]
        or any(lo > hi for lo, hi in envelope.factor_bounds.values())
    )


def solve_pending_allocation(
    optimizer: PendingOptimizer,
    r: PendingRequest,
    state: PendingAllocationState,
    *,
    net_band: tuple[float, float],
) -> PendingAllocationResult:
    """Optimize base targets with full pending reserves; return NEW trade weights.

    r.current_weights stays the delivered portfolio, including its trading-cost
    baseline. No outstanding order is canceled or assumed filled. Infeasible or
    failed solves release no targets, including when old reservations exceed
    known resources. New cash reserves buy notional plus fees on both directions.
    """
    optimizer.validate(r)
    envelope = pending_allocation_envelope(r, state, net_band=net_band)
    if _infeasible(envelope, r.net_target):
        return PendingAllocationResult(
            "infeasible", "Pending envelope or reserves infeasible", envelope
        )
    base = optimizer.solve_pending(
        r,
        envelope=envelope,
        cash_limit=(envelope.available_cash / state.nav, state.new_fee_rates.to_numpy(dtype=float)),
    )
    if base.status != "optimal":
        return PendingAllocationResult(base.status, base.message, envelope)
    return _pending_receipt(r, state, envelope, base, net_band)


def _pending_receipt(r, state, envelope, base, net_band):
    weights = base.weights
    trades = weights - r.current_weights
    cash = float(state.nav * (trades.clip(lower=0).sum() + state.new_fee_rates @ trades.abs()))
    net = float(weights.sum())
    net_bounds = (net + envelope.pending_lower.sum(), net + envelope.pending_upper.sum())
    factor_bounds = {
        name: (
            float(r.factor_loadings[name] @ weights) + lo,
            float(r.factor_loadings[name] @ weights) + hi,
        )
        for name, (lo, hi) in envelope.factor_increments.items()
    }
    gross = float(weights.abs().sum() + envelope.pending_gross)
    violations = [
        cash / state.nav - envelope.available_cash / state.nav,
        gross - r.gross_limit,
        net_band[0] - net_bounds[0],
        net_bounds[1] - net_band[1],
        float((r.lower_bounds - weights - envelope.pending_lower).max()),
        float((weights + envelope.pending_upper - r.upper_bounds).max()),
        float((-trades - envelope.remaining_sell_quantities * state.raw_prices / state.nav).max()),
    ]
    for name, (lo, hi) in factor_bounds.items():
        violations.extend([r.factor_bounds[name][0] - lo, hi - r.factor_bounds[name][1]])
    if not np.isfinite([cash, gross, *net_bounds, *violations]).all() or max(violations) > 1e-7:
        return PendingAllocationResult(
            "numerical_failure", "Pending residual exceeds 1e-7", envelope
        )
    return PendingAllocationResult(
        "optimal",
        "Single-period conditional endpoint envelope",
        envelope,
        base,
        trades,
        net_bounds,
        factor_bounds,
        gross,
        cash,
    )
