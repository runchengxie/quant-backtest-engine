"""Export fixed synthetic schedule evidence; invoke in the locked Core environment."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from quant_backtest_core.planning.execution_comparison import compare, fixed_study
from quant_backtest_core.planning.liquidation_discrete import solve
from quant_backtest_core.planning.liquidation_reference import (
    LiquidationModel,
    evaluate,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    convergence = []
    for risk in (0.0, 0.7):
        model = LiquidationModel(3, 2, 1.5, risk, 0.8)
        for n in (8, 16, 32, 64):
            plan = solve(model, (3.0,) * n)
            convergence.append(
                {
                    "risk": risk,
                    "periods": n,
                    "cost": plan.cost,
                    "analytic_cost": evaluate(model, 0).remaining_value,
                    "excess_cost": plan.cost - evaluate(model, 0).remaining_value,
                    "max_inventory_error": max(
                        abs(x - evaluate(model, i * 2 / n).inventory)
                        for i, x in enumerate(plan.inventory)
                    ),
                }
            )
    root = Path(__file__).resolve().parents[2]
    sources = sorted(
        (root / "packages/core/src/quant_backtest_core/planning").glob("*.py")
    )
    value = {
        "schema": "synthetic-execution-comparison.v1",
        "source_revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sources
        },
        "python": sys.version,
        "protocol": {
            "objective": "sum eta*q^2/dt + lambda*sigma^2*dt*(x^2+x*y+y^2)/3",
            "constraints": "nonnegative sales, per-period quantity capacity, no oversell, hard terminal zero in planning",
            "study": {
                "initial_inventory": 10,
                "horizon_seconds": 4,
                "periods": 8,
                "volatility": 1,
                "eta_grid": [0.5, 2],
                "risk_grid": [0, 1],
                "forecast_capacity": [2] * 8,
                "alpha": [0] * 8,
            },
            "convergence": {
                "initial_inventory": 3,
                "horizon_seconds": 2,
                "temporary_cost": 1.5,
                "volatility": 0.8,
                "risk_grid": [0, 0.7],
                "period_grid": [8, 16, 32, 64],
                "capacity_per_period": 3,
            },
            "open_loop": "fixed optimal quantities submitted once, no retry",
            "immediate": "request 10 at period zero then zero; actual/forecast capacity clipping, no retry; infeasible intended capacity, planned cost null",
            "twap": "1.25 each period submitted once, no retry",
            "rolling": "replan delivered inventory; past fills only; infeasible submits zero and records failure",
            "solver": {"method": "SLSQP", "ftol": 1e-13, "maxiter": 2000},
        },
        "infeasibility_diagnostic": [
            dataclasses.asdict(r) for r in compare(0.5, 1, (0, 0, 0, 0, 2, 2, 2, 2))
        ],
        "scope": "schedule-cost functional; no cash ledger or net returns",
        "terminal_comparison": "Rank objectives only among completed paths. Residual paths report accrued cost only.",
        "convergence": convergence,
        "rows": [dataclasses.asdict(r) for r in fixed_study()],
    }
    args.output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
