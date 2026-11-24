"""Fixed synthetic schedule-cost study; no cash ledger or return claims."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .liquidation_discrete import _vector, objective, solve
from .liquidation_reference import LiquidationModel


@dataclass(frozen=True)
class ComparisonRow:
    policy: str
    eta: float
    risk: float
    actual_capacity: tuple[float, ...]
    fills: tuple[float, ...]
    planned_capacity_feasible: bool
    planned_cost: float | None
    realized_cost: float
    residual: float
    completed: bool
    failures: tuple[str, ...]


def compare(
    eta: float, risk: float, actual_capacity: tuple[float, ...]
) -> tuple[ComparisonRow, ...]:
    """Eight periods; all policies receive the same forecast of two shares/period.

    Actual capacities are revealed only after each submission. A failed replan
    submits zero and records its reason; no forced liquidation or hidden repair.
    """
    actual = _vector(actual_capacity)
    if len(actual) != 8:
        raise ValueError("exactly eight actual capacities required")
    model = LiquidationModel(10, 4, eta, risk, 1)
    initial = solve(model, (2,) * 8)
    rows = []
    for policy in ("immediate", "open_loop", "twap", "rolling"):
        planned = initial.sales if policy != "twap" else (1.25,) * 8
        if policy == "immediate":
            planned = (10.0,) + (0.0,) * 7
        capacity_feasible = all(q <= 2 for q in planned)
        residual = 10.0
        fills, failures = [], []
        for j, cap in enumerate(actual):
            submitted = planned[j]
            if policy == "rolling":
                state = replace(
                    model, initial_inventory=max(0.0, residual), horizon_seconds=(8 - j) * 0.5
                )
                try:
                    submitted = solve(state, (2,) * (8 - j)).sales[0]
                except ValueError as exc:
                    failures.append(f"period {j}: {exc}")
                    submitted = 0.0
            fill = min(submitted, cap, 2.0, max(0.0, residual))
            fills.append(fill)
            residual -= fill
        rows.append(
            ComparisonRow(
                policy,
                eta,
                risk,
                actual,
                tuple(fills),
                capacity_feasible,
                objective(model, planned) if capacity_feasible else None,
                objective(model, fills, require_terminal=False),
                residual,
                abs(residual) < 1e-8,
                tuple(failures),
            )
        )
    return tuple(rows)


def fixed_study() -> tuple[ComparisonRow, ...]:
    """Prespecified 2 cost × 2 risk × 2 capacity × 4 policies; retain every row."""
    return tuple(
        row
        for eta in (0.5, 2.0)
        for risk in (0.0, 1.0)
        for actual in ((2.0,) * 8, (0.0, 0.0, 2.0, 2.0, 2.0, 2.0, 2.0, 2.0))
        for row in compare(eta, risk, actual)
    )
