"""Export fixed synthetic schedule evidence; invoke in the locked Core environment."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from quant_backtest_core.planning.execution_comparison import fixed_study
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
        "scope": "schedule-cost functional; no cash ledger or net returns",
        "terminal_comparison": "Rank objectives only among completed paths. Residual paths report accrued cost only.",
        "convergence": convergence,
        "rows": [dataclasses.asdict(r) for r in fixed_study()],
    }
    args.output.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
