# SPDX-License-Identifier: Apache-2.0
"""Deterministic policies for scheduling and prioritizing orders.

These functions neither match orders nor reserve cash. Callers apply their
outputs to the account and enforce venue and funding constraints there.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction


def checkpoint_sides(completion: Mapping[str, Decimal], floor: Decimal) -> tuple[str, ...]:
    """Return the sides still short of the floor in buy-then-sell order."""
    if set(completion) != {"buy", "sell"} or not floor.is_finite() or not 0 <= floor <= 1:
        raise ValueError("expected both side completions and a floor in [0, 1]")
    if any(not value.is_finite() or not 0 <= value <= 1 for value in completion.values()):
        raise ValueError("side completion must be in [0, 1]")
    return tuple(side for side in ("buy", "sell") if completion[side] < floor)


def proportional_lots(requests: Mapping[str, int], budget: int) -> dict[str, int]:
    """Allocate interchangeable lots by size. Break remainder ties in input order.

    Lots must have equal budget cost for this allocation. For securities with
    different cash costs, determine cash reservations in the account owner.
    """
    if (
        type(budget) is not int
        or budget < 0
        or any(type(value) is not int or value < 0 for value in requests.values())
    ):
        raise ValueError("requests and budget must be nonnegative integer lots")
    total = sum(requests.values())
    if budget >= total:
        return dict(requests)
    quotas = {symbol: divmod(requested * budget, total) for symbol, requested in requests.items()}
    allotted = {symbol: whole for symbol, (whole, _) in quotas.items()}
    remainder = budget - sum(allotted.values())
    for symbol in sorted(quotas, key=lambda symbol: quotas[symbol][1], reverse=True)[:remainder]:
        allotted[symbol] += 1
    return allotted


@dataclass(frozen=True)
class BuyLotRequest:
    """One executable order cap and conservative, fee-inclusive cost per lot."""

    max_lots: int
    cash_per_lot: Decimal
    target_gap: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if (
            type(self.max_lots) is not int
            or self.max_lots < 0
            or not self.cash_per_lot.is_finite()
            or self.cash_per_lot <= 0
            or not self.target_gap.is_finite()
            or self.target_gap < 0
        ):
            raise ValueError("invalid buy lot request")


def allocate_buy_lots(
    requests: Mapping[str, BuyLotRequest], cash: Decimal, policy: str
) -> dict[str, int]:
    """Plan unreserved lots without overspending the supplied available cash.

    Fixed priority uses mapping insertion order. Pro rata first gives every
    request the same fraction of its full size, then uses fixed priority for
    the residual cash. Largest-gap priority sorts gaps from high to low and
    breaks ties by input order. The account must still reserve at submission.
    """
    if not cash.is_finite() or cash < 0:
        raise ValueError("cash must be finite and nonnegative")
    if policy not in {"fixed", "pro_rata", "largest_gap"}:
        raise ValueError("unknown cash allocation policy")
    cost = {key: Fraction(request.cash_per_lot) for key, request in requests.items()}
    budget = Fraction(cash)
    assigned = dict.fromkeys(requests, 0)
    order = list(requests)
    if policy == "largest_gap":
        order.sort(key=lambda key: requests[key].target_gap, reverse=True)
    if policy == "pro_rata":
        demand = sum(
            (cost[key] * request.max_lots for key, request in requests.items()), Fraction(0)
        )
        if demand:
            fraction = min(Fraction(1), budget / demand)
            for key, request in requests.items():
                assigned[key] = int(fraction * request.max_lots)
                budget -= assigned[key] * cost[key]
    for key in order:
        extra = min(requests[key].max_lots - assigned[key], budget // cost[key])
        assigned[key] += extra
        budget -= extra * cost[key]
    return assigned


def released_quantity(
    parent_quantity: Decimal,
    lot_size: int,
    weights: tuple[int, ...],
    slices_released: int,
) -> int:
    """Cumulative released shares for an immutable slice schedule."""
    if (
        not parent_quantity.is_finite()
        or parent_quantity < 0
        or type(lot_size) is not int
        or lot_size <= 0
        or any(type(weight) is not int or weight < 0 for weight in weights)
        or not any(weights)
        or type(slices_released) is not int
        or not 0 <= slices_released <= len(weights)
    ):
        raise ValueError("invalid release schedule")
    fraction = Fraction(sum(weights[:slices_released]), sum(weights))
    return (Fraction(parent_quantity) * fraction // lot_size) * lot_size
