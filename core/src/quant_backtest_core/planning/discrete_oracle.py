# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/portfolio/discrete_oracle.py
# Original SHA256: 98aac895872f1f86536f7739852a02110c8ffd40532157d26009f81c3139a7b0
"""Bounded synthetic buy-only lot oracle; not a production portfolio solver."""

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import isfinite, prod


@dataclass(frozen=True)
class LotOracleResult:
    status: str
    quantities: tuple[int, ...] | None = None
    objective: float | None = None
    spent: float | None = None
    evaluated: int = 0
    candidate_status: str = "not_provided"
    candidate_gap: float | None = None


def enumerate_lot_portfolios(
    *,
    prices: Sequence[float],
    target_quantities: Sequence[float],
    max_lots: Sequence[int],
    lot_sizes: Sequence[int],
    cash_budget: float,
    minimum_commission: float = 0,
    proportional_commission: float = 0,
    max_states: int = 100_000,
    candidate_quantities: Sequence[int] | None = None,
) -> LotOracleResult:
    """Minimize sum squared quantity tracking errors over a finite lot grid.

    Each nonzero asset order pays max(minimum, proportional * notional).
    Decimal-string inputs are compared using exact rational arithmetic.
    Float result amounts are display values; budget includes fees and allows
    residual cash. Exact optimality covers only
    this enumerated domain, objective and fee rule. A candidate gap is reported
    only when the candidate is feasible. No holdings, shorts, covariance, or tax
    lots are modeled. The squared continuous objective is convex; integer lots
    and a nonzero minimum order commission create the discrete problem.
    """
    n = len(prices)
    _validate(
        prices,
        target_quantities,
        max_lots,
        lot_sizes,
        cash_budget,
        minimum_commission,
        proportional_commission,
        max_states,
    )
    states = prod(v + 1 for v in max_lots)
    if states > max_states:
        return LotOracleResult("search_limit")

    exact_prices = tuple(Fraction(str(p)) for p in prices)
    exact_targets = tuple(Fraction(str(t)) for t in target_quantities)
    exact_budget = Fraction(str(cash_budget))
    exact_minimum = Fraction(str(minimum_commission))
    exact_rate = Fraction(str(proportional_commission))

    def evaluate(q):
        spent = sum(
            p * x + (max(exact_minimum, exact_rate * p * x) if x else 0)
            for p, x in zip(exact_prices, q, strict=True)
        )
        loss = sum((x - t) ** 2 for x, t in zip(q, exact_targets, strict=True))
        if not isfinite(spent) or not isfinite(loss):
            raise ValueError("objective or budget overflow")
        return spent, loss

    best = None
    for lots in product(*(range(v + 1) for v in max_lots)):
        q = tuple(x * size for x, size in zip(lots, lot_sizes, strict=True))
        spent, loss = evaluate(q)
        if spent <= exact_budget and (best is None or loss < best[0]):
            best = (loss, q, spent)
    # The all-zero portfolio is always feasible for a validated nonnegative budget.
    assert best is not None
    candidate_status, gap = "not_provided", None
    if candidate_quantities is not None:
        candidate_status = "infeasible"
        if len(candidate_quantities) == n and all(
            type(x) is int and 0 <= x <= bound * size and x % size == 0
            for x, bound, size in zip(candidate_quantities, max_lots, lot_sizes, strict=True)
        ):
            cost, loss = evaluate(candidate_quantities)
            if cost <= exact_budget:
                candidate_status, gap = "feasible", float(loss - best[0])
    return LotOracleResult(
        "optimal_exhaustive", best[1], float(best[0]), float(best[2]), states, candidate_status, gap
    )


def _validate(
    prices,
    target_quantities,
    max_lots,
    lot_sizes,
    cash_budget,
    minimum_commission,
    proportional_commission,
    max_states,
):
    n = len(prices)
    if not n or any(len(v) != n for v in (target_quantities, max_lots, lot_sizes)):
        raise ValueError("nonempty aligned asset vectors required")
    scalar_values = (
        *prices,
        *target_quantities,
        cash_budget,
        minimum_commission,
        proportional_commission,
    )
    if any(isinstance(v, bool) or not isfinite(v) for v in scalar_values):
        raise ValueError("finite numeric inputs required")
    if (
        min(prices) <= 0
        or min(target_quantities) < 0
        or min(cash_budget, minimum_commission, proportional_commission) < 0
    ):
        raise ValueError("prices positive; targets, budget and fees nonnegative")
    if any(type(v) is not int or v < 0 for v in max_lots) or any(
        type(v) is not int or v <= 0 for v in (*lot_sizes, max_states)
    ):
        raise ValueError("integer lot bounds and positive sizes/search limit required")
