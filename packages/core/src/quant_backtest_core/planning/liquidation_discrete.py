"""Bounded, hard-terminal scalar LQ reference (optional planning dependencies)."""

from __future__ import annotations

import math
from dataclasses import dataclass
from numbers import Real
from typing import Sequence

from .liquidation_reference import LiquidationModel, evaluate


@dataclass(frozen=True)
class LiquidationPlan:
    sales: tuple[float, ...]
    inventory: tuple[float, ...]
    cost: float


def _vector(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) == 0 or any(
        isinstance(v, bool) or not isinstance(v, Real) or not math.isfinite(v) or v < 0
        for v in values
    ):
        raise ValueError("nonempty finite nonnegative scalar quantities required")
    return tuple(float(v) for v in values)


def _validate_model(model: LiquidationModel) -> None:
    if any(
        isinstance(v, bool) or not isinstance(v, Real)
        for v in (
            model.initial_inventory,
            model.horizon_seconds,
            model.temporary_cost,
            model.risk_aversion,
            model.volatility,
        )
    ):
        raise ValueError("real scalar coefficients required")
    evaluate(model, 0)


def _risk_coefficient(model: LiquidationModel) -> float:
    scale = math.sqrt(model.risk_aversion) * model.volatility
    coefficient = scale * scale
    if not math.isfinite(coefficient) or (scale > 0 and coefficient == 0):
        raise ValueError("risk coefficient is unrepresentable")
    return coefficient


def objective(
    model: LiquidationModel, sales: Sequence[float], *, require_terminal: bool = True
) -> float:
    """Exact integral for constant sales rates and piecewise-linear inventory.

    A residual path may be scored explicitly, but its cost is not a feasible
    hard-terminal value and includes no invented terminal penalty.
    """
    _validate_model(model)
    q = _vector(sales)
    dt = model.horizon_seconds / len(q)
    if dt == 0:
        raise ValueError("period duration underflows")
    risk = _risk_coefficient(model)
    x = model.initial_inventory
    total = 0.0
    for fill in q:
        y = x - fill
        if y < -1e-8 * model.initial_inventory:
            raise ValueError("sales exceed available inventory")
        total += model.temporary_cost * fill * fill / dt
        total += risk * dt * (x * x + x * y + y * y) / 3
        x = y
    if require_terminal and abs(x) > 1e-8 * model.initial_inventory:
        raise ValueError("hard terminal liquidation required")
    if not math.isfinite(total):
        raise ValueError("objective is unrepresentable")
    return total


def solve(model: LiquidationModel, capacities: Sequence[float]) -> LiquidationPlan:
    """Minimize the strictly convex quadratic; reject infeasibility or solver failure."""
    _validate_model(model)
    caps = _vector(capacities)
    x = model.initial_inventory
    if not math.isfinite(sum(caps)) or sum(caps) < x:
        raise ValueError("insufficient or unrepresentable total capacity")
    if x == 0:
        return LiquidationPlan((0.0,) * len(caps), (0.0,) * (len(caps) + 1), 0.0)
    import numpy as np
    from numpy.typing import NDArray
    from scipy.optimize import minimize  # type: ignore[import-untyped]

    # Optimize fractions for consistent tolerances across inventory units.
    n = len(caps)
    dt = model.horizon_seconds / n
    if dt == 0:
        raise ValueError("period duration underflows")
    a = model.temporary_cost * x * x / dt
    b = _risk_coefficient(model) * dt * x * x / 3
    if not all(math.isfinite(v) and v >= 0 for v in (a, b)) or a == 0:
        raise ValueError("quadratic coefficient domain is unrepresentable")
    lower = np.tril(np.ones((n, n)), -1)
    upper = lower + np.eye(n)
    scale = max(a, b)
    a, b = a / scale, b / scale

    def fun(q: NDArray[np.float64]) -> float:
        before, after = 1 - lower @ q, 1 - upper @ q
        return float(a * (q @ q) + b * (before @ before + before @ after + after @ after))

    def jac(q: NDArray[np.float64]) -> NDArray[np.float64]:
        before, after = 1 - lower @ q, 1 - upper @ q
        return 2 * a * q - b * (lower.T @ (2 * before + after) + upper.T @ (before + 2 * after))

    bounds = np.minimum(np.asarray(caps), x) / x
    initial = bounds / bounds.sum()
    result = minimize(
        fun,
        initial,
        jac=jac,
        bounds=list(zip(np.zeros(n), bounds)),
        constraints={"type": "eq", "fun": lambda q: q.sum() - 1, "jac": lambda q: np.ones(n)},
        method="SLSQP",
        options={"ftol": 1e-13, "maxiter": 2000},
    )
    q = result.x * x
    if (
        not result.success
        or not np.all(np.isfinite(q))
        or np.any(q < 0)
        or np.any(q > np.asarray(caps) + 1e-9 * x)
        or abs(q.sum() - x) > 1e-8 * x
    ):
        raise ValueError(f"uncertified numerical solution: {result.message}")
    sales = tuple(float(v) for v in q)
    inventory = tuple(float(v) for v in np.r_[x, x - np.cumsum(q)])
    return LiquidationPlan(sales, inventory, objective(model, sales))
