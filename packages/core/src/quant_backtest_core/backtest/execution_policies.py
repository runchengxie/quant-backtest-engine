# SPDX-License-Identifier: Apache-2.0
"""Deterministic policies for scheduling and prioritizing orders.

These functions neither match orders nor reserve cash. Callers apply their
outputs to the account and enforce venue and funding constraints there.
"""

from collections.abc import Mapping
from decimal import Decimal


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
