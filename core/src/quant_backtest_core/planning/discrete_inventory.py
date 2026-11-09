# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/portfolio/discrete_inventory.py
# Original SHA256: 3238ecae91588ae6818f718af8938ecefc506ae2e357c5627644f07ed982bd58
"""Small long-only finite inventory comparison, with exact prefunded feasibility.

This is a planning reference, never a matcher or an execution certificate.
Money and objective values are Fractions, including decimal-string float inputs.
"""

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from itertools import product
from math import prod

Scalar = int | float | str | Decimal | Fraction


@dataclass(frozen=True)
class DiscreteInventoryRequest:
    prices: tuple[Scalar, ...]
    holdings: tuple[int, ...]
    target_shares: tuple[Scalar, ...]
    available_sell_shares: tuple[int, ...]
    buy_lot_sizes: tuple[int, ...]
    sell_lot_sizes: tuple[int, ...]
    max_buy_lots: tuple[int, ...]
    cash: Scalar
    reserved_cash: Scalar = 0
    locked_shares: tuple[int, ...] | None = None
    fractional_entitlements: tuple[Scalar, ...] | None = None
    tracking_weights: tuple[Scalar, ...] | None = None
    turnover_penalties: tuple[Scalar, ...] | None = None
    proportional_fee: Scalar = 0
    minimum_fee: Scalar = 0
    fixed_fee: Scalar = 0
    allow_odd_lot_exit: bool = True
    max_assets: int = 16
    max_asset_states: int = 10_000
    max_domain_states: int = 100_000
    max_evaluations: int = 100_000
    max_heuristic_evaluations: int = 10_000


@dataclass(frozen=True)
class DiscreteInventoryPlan:
    trades: tuple[int, ...]
    holdings: tuple[int, ...]
    fractional_entitlements: tuple[Fraction, ...]
    objective: Fraction
    fees: Fraction
    turnover_notional: Fraction
    projected_cash: Fraction
    unreserved_cash: Fraction


@dataclass(frozen=True)
class DiscreteInventoryResult:
    status: str
    heuristic: DiscreteInventoryPlan | None = None
    incumbent: DiscreteInventoryPlan | None = None
    domain_states: int | None = None
    evaluated: int = 0
    heuristic_status: str = "not_run"
    heuristic_evaluated: int = 0
    lower_bound: Fraction | None = None
    upper_bound: Fraction | None = None
    heuristic_gap: Fraction | None = None
    funding_policy: str = "prefund_all_orders_no_sale_recycling"


@dataclass(frozen=True)
class _Exact:
    prices: tuple[Fraction, ...]
    targets: tuple[Fraction, ...]
    entitlements: tuple[Fraction, ...]
    weights: tuple[Fraction, ...]
    penalties: tuple[Fraction, ...]
    cash: Fraction
    reserved: Fraction
    rate: Fraction
    minimum: Fraction
    fixed: Fraction


def _number(value: Scalar) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal, Fraction)):
        raise ValueError("finite rational or decimal-string numeric inputs required")
    try:
        return value if isinstance(value, Fraction) else Fraction(str(value))
    except (ValueError, OverflowError, ZeroDivisionError) as error:
        raise ValueError("finite rational or decimal-string numeric inputs required") from error


def _vector(values, n, default):
    if values is None:
        return (Fraction(default),) * n
    if len(values) != n:
        raise ValueError("nonempty aligned asset vectors required")
    result = tuple(_number(value) for value in values)
    if any(value < 0 for value in result):
        raise ValueError("targets, weights, entitlements and penalties must be nonnegative")
    return result


def _validate(request):
    n = len(request.prices)
    if not n or any(
        len(values) != n
        for values in (
            request.holdings,
            request.target_shares,
            request.available_sell_shares,
            request.buy_lot_sizes,
            request.sell_lot_sizes,
            request.max_buy_lots,
        )
    ):
        raise ValueError("nonempty aligned asset vectors required")
    locks = (0,) * n if request.locked_shares is None else request.locked_shares
    if len(locks) != n:
        raise ValueError("nonempty aligned asset vectors required")
    for values in (request.holdings, request.available_sell_shares, request.max_buy_lots, locks):
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("nonnegative integer holdings, availability, locks and bounds needed")
    caps = (
        request.max_assets,
        request.max_asset_states,
        request.max_domain_states,
        request.max_evaluations,
        request.max_heuristic_evaluations,
    )
    if any(
        type(value) is not int or value <= 0
        for value in (*request.buy_lot_sizes, *request.sell_lot_sizes, *caps)
    ):
        raise ValueError("positive integer lots and search caps required")
    if type(request.allow_odd_lot_exit) is not bool:
        raise ValueError("allow_odd_lot_exit must be boolean")
    if any(
        sell > held or locked > held
        for sell, held, locked in zip(
            request.available_sell_shares, request.holdings, locks, strict=True
        )
    ):
        raise ValueError("availability and locks cannot exceed original holdings")
    exact = _Exact(
        tuple(_number(p) for p in request.prices),
        _vector(request.target_shares, n, 0),
        _vector(request.fractional_entitlements, n, 0),
        _vector(request.tracking_weights, n, 1),
        _vector(request.turnover_penalties, n, 0),
        _number(request.cash),
        _number(request.reserved_cash),
        _number(request.proportional_fee),
        _number(request.minimum_fee),
        _number(request.fixed_fee),
    )
    if (
        any(p <= 0 for p in exact.prices)
        or min(exact.cash, exact.reserved, exact.rate, exact.minimum, exact.fixed) < 0
    ):
        raise ValueError("positive prices and nonnegative cash, reservations and fees required")
    _validate_exact(exact)
    return exact, locks


def _validate_exact(exact):
    if exact.reserved > exact.cash:
        raise ValueError("reserved cash exceeds supplied cash")
    if any(value >= 1 for value in exact.entitlements):
        raise ValueError("fractional entitlements must be in [0, 1), outside integer holdings")


def _domains(request, locks):
    counts, specifications = [], []
    for held, available, locked, buy, sell, bound in zip(
        request.holdings,
        request.available_sell_shares,
        locks,
        request.buy_lot_sizes,
        request.sell_lot_sizes,
        request.max_buy_lots,
        strict=True,
    ):
        sell_lots = min(available, held - locked) // sell
        odd_exit = bool(
            request.allow_odd_lot_exit and held % sell and available == held and locked == 0
        )
        counts.append(sell_lots + bound + 1 + odd_exit)
        specifications.append((held, buy, sell, bound, sell_lots, odd_exit))
    states = prod(counts)
    if max(counts) > request.max_asset_states:
        return None, states
    domains = []
    for held, buy, sell, bound, sell_lots, odd_exit in specifications:
        values = [-(lot * sell) for lot in range(1, sell_lots + 1)]
        values.extend(lot * buy for lot in range(bound + 1))
        if odd_exit:
            values.append(-held)
        domains.append(tuple(sorted(values)))
    return tuple(domains), states


def _plan(request, exact, trades):
    buys = sum((p * max(q, 0) for p, q in zip(exact.prices, trades, strict=True)), Fraction())
    sales = sum((p * max(-q, 0) for p, q in zip(exact.prices, trades, strict=True)), Fraction())
    fees = sum(
        (
            exact.fixed + max(exact.minimum, exact.rate * p * abs(q))
            for p, q in zip(exact.prices, trades, strict=True)
            if q
        ),
        Fraction(),
    )
    unreserved = exact.cash - exact.reserved - buys - fees
    if unreserved < 0:
        return None
    holdings = tuple(h + q for h, q in zip(request.holdings, trades, strict=True))
    objective = sum(
        (
            weight * (held + entitlement - target) ** 2 + penalty * abs(q)
            for weight, held, entitlement, target, penalty, q in zip(
                exact.weights,
                holdings,
                exact.entitlements,
                exact.targets,
                exact.penalties,
                trades,
                strict=True,
            )
        ),
        Fraction(),
    )
    return DiscreteInventoryPlan(
        tuple(trades),
        holdings,
        exact.entitlements,
        objective,
        fees,
        buys + sales,
        exact.cash + sales - buys - fees,
        unreserved,
    )


def _key(plan):
    return plan.objective, plan.trades


def _heuristic(request, exact, domains):
    # Deterministic one-pass coordinate descent in declared asset order.
    best = _plan(request, exact, (0,) * len(domains))
    assert best is not None
    evaluated = 0
    for index, values in enumerate(domains):
        chosen = best
        for quantity in values:
            if evaluated >= request.max_heuristic_evaluations:
                return chosen, "budget_exhausted", evaluated
            trades = list(best.trades)
            trades[index] = quantity
            candidate = _plan(request, exact, tuple(trades))
            evaluated += 1
            if candidate is not None and _key(candidate) < _key(chosen):
                chosen = candidate
        best = chosen
    return best, "feasible", evaluated


def solve_discrete_inventory(request: DiscreteInventoryRequest) -> DiscreteInventoryResult:
    """Compare a feasible heuristic and an exact finite-domain reference.

    Fee per nonzero asset trade is fixed + max(minimum, rate * absolute notional).
    All buy notional AND all order fees must be prefunded by cash minus reservations.
    Projected sells never finance orders, including their own fees. This deliberately
    excludes useful sale-funded sequences; replan after actual owner settlement.
    Availability is caller-supplied settlement eligibility, intersected with locks.
    Buy and ordinary sell trades use their respective lots; an enabled complete
    odd-lot exit sells all original integer inventory only when fully available.
    Fractional entitlements never enter trade variables and remain unchanged.

    The objective is sum(weight * (integer holdings + entitlement - target)**2
    + penalty * abs(trade)). The zero lower bound follows from nonnegativity,
    not a relaxation solve. Only complete enumeration reports optimality, limited
    to this prefunded finite domain. An exhausted reference retains the better
    heuristic/enumerated incumbent and its valid upper bound. Wire consumers must
    encode each Fraction as numerator/denominator or an explicit display conversion.
    """
    exact, locks = _validate(request)
    if len(request.prices) > request.max_assets:
        return DiscreteInventoryResult("asset_limit")
    domains, states = _domains(request, locks)
    if domains is None:
        return DiscreteInventoryResult("asset_domain_limit", domain_states=states)
    heuristic, heuristic_status, heuristic_evaluated = _heuristic(request, exact, domains)
    best, evaluated = heuristic, 0
    status = "domain_too_large"
    if states <= request.max_domain_states:
        status = "optimal_exhaustive"
        for trades in product(*domains):
            if evaluated >= request.max_evaluations:
                status = "budget_exhausted"
                break
            candidate = _plan(request, exact, trades)
            evaluated += 1
            if candidate is not None and _key(candidate) < _key(best):
                best = candidate
    complete = status == "optimal_exhaustive"
    return DiscreteInventoryResult(
        status=status,
        heuristic=heuristic,
        incumbent=best,
        domain_states=states,
        evaluated=evaluated,
        heuristic_status=heuristic_status,
        heuristic_evaluated=heuristic_evaluated,
        lower_bound=best.objective if complete else Fraction(0),
        upper_bound=best.objective,
        heuristic_gap=heuristic.objective - best.objective if complete else None,
    )
