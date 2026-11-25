"""Export the fixed synthetic owner study into a fresh external data directory."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd
import quant_backtest_core.planning.owner_control as controller
import quant_backtest_core.planning.owner_control_audit as audit_module
import quant_backtest_core.planning.owner_control_case as case_module
import quant_backtest_core.planning.owner_control_protocol as protocol_module
from quant_backtest_core.backtest._minute_checkpoint import _wire
from quant_backtest_core.planning.owner_control_audit import audit_owner_tables
from quant_backtest_core.planning.owner_control_case import (
    OwnerControlCase,
    build_session,
    case_inputs,
    restore_case,
    run_case,
)
from quant_backtest_core.planning.owner_control_protocol import (
    POLICIES,
    case_id,
    fixed_panels,
)


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")


def fresh_output(path: Path, code: Path, data: Path) -> Path:
    path, code, data = path.resolve(), code.resolve(), data.resolve()
    if data.is_relative_to(code) or not path.is_relative_to(data) or path == data:
        raise ValueError("output must be a fresh child of external project data root")
    if path.is_relative_to(code) or any(
        (p / ".git").exists() for p in (path, *path.parents)
    ):
        raise ValueError("output cannot be inside a source checkout")
    if path.exists():
        raise FileExistsError(path)
    path.mkdir(parents=True, exist_ok=False)
    return path


def source_identity(root: Path) -> dict[str, Any]:
    if subprocess.check_output(
        ["git", "status", "--porcelain"], cwd=root, text=True
    ).strip():
        raise ValueError("freeze and commit source before exporting evidence")
    for module in (controller, audit_module, case_module, protocol_module):
        source = (
            root
            / "packages/core/src"
            / Path(*module.__name__.split(".")).with_suffix(".py")
        )
        if Path(module.__file__).read_bytes() != source.read_bytes():
            raise ValueError("installed study source differs from the checkout")
    source_paths = [
        *sorted((root / "packages/core/src").rglob("*.py")),
        Path(__file__).resolve(),
    ]
    return {
        "revision": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, text=True
        ).strip(),
        "source_sha256": {
            str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in source_paths
        },
        "dependencies": {
            n: importlib.metadata.version(n)
            for n in ("numpy", "scipy", "pandas", "quant-backtest-core")
        },
        "policy_dependencies": controller.fingerprints(),
    }


def recovery_check(case: OwnerControlCase) -> dict[str, Any]:
    expected, diagnostics = run_case(case)
    session = build_session(case)
    rows = []
    while True:
        checkpoint = session.checkpoint()
        wire = json.loads(json.dumps(checkpoint, allow_nan=False))
        restored = restore_case(case, wire)
        while restored.step():
            pass
        if restored.checkpoint() != diagnostics["checkpoint"]:
            raise ValueError("recovery final owner/impact/delivery checkpoint differs")
        result = restored.run()
        for name in ("daily", "orders", "fills", "holdings"):
            pd.testing.assert_frame_equal(
                getattr(result, name), getattr(expected, name), check_exact=True
            )
        if _wire(result.summary) != _wire(expected.summary):
            raise ValueError("recovery summary differs")
        rows.append(
            {
                "cursor": session.cursor,
                "checkpoint_digest": checkpoint["digest"],
                "queued_reports": len(session.queue),
                "live_orders": sum(
                    o["status"] == "pending" for o in session.simulation.orders
                ),
                "exact": True,
            }
        )
        if not session.step():
            break
    return {
        "case_id": case_id(case),
        "case": dataclasses.asdict(case),
        "boundaries": rows,
        "all_boundary_financial_policy_impact_delivery_parity": True,
    }


def run_one(case: OwnerControlCase, folder: Path) -> dict[str, Any]:
    targets, bars, config = case_inputs(case)
    write_json(
        folder / "inputs.json",
        _wire(
            {
                "case": dataclasses.asdict(case),
                "targets": targets,
                "bars": bars,
                "config": dataclasses.asdict(config),
            }
        ),
    )
    result, diagnostics = run_case(case)
    write_json(
        folder / "owner.json",
        _wire(
            {
                n: getattr(result, n)
                for n in ("daily", "orders", "fills", "holdings", "summary")
            }
        ),
    )
    write_json(folder / "diagnostics.json", diagnostics)
    metric = audit_owner_tables(
        result,
        bars,
        config,
        quantity=case.quantity,
        exit_start=pd.Timestamp("2025-01-03 09:29", tz="Asia/Shanghai"),
    )
    trace = diagnostics["policy_trace"]
    metric.update(
        planning_failure_decisions=sum(
            r["action"] == "planning_failure" for r in trace
        ),
        wait_pending_decisions=sum(r["action"] == "wait_pending" for r in trace),
    )
    write_json(folder / "metrics.json", metric)
    return {"status": "audited", "metrics": metric}


def export(output: Path, root: Path, code: Path, data: Path) -> dict[str, Any]:
    identity = source_identity(root)
    output = fresh_output(output, code, data)
    panels = fixed_panels()
    protocol = {
        "schema": "owner-control-study.v1",
        "identity": identity,
        "panels": [
            {"panel": p, "case_id": case_id(c), "case": dataclasses.asdict(c)}
            for p, c in panels
        ],
        "constants": {
            "symbol": "A",
            "external_price_cny": 10,
            "initial_cash_per_share": 20,
            "seed_date": "2025-01-02",
            "exit_date": "2025-01-03",
            "slots": 8,
            "slot_seconds": 240,
            "order_life_minutes": 2,
            "lot_size": 1,
            "forecast_volume_per_bar": 500,
            "bars_per_slot": 2,
            "buy_fee_bp": 3,
            "sell_fee_bp": 8,
            "included_sell_tax_bp": 5,
            "minimum_fee_cny": 0,
            "belief_eta": "0.5*1e-4*belief_multiplier*240",
            "risk_aversion": 1e-4,
            "volatility_cny_per_share_sqrt_second": 0.01,
            "actual_transient": "1e-4*actual_multiplier",
            "permanent": 0,
            "decay_seconds": 300,
        },
        "limits": [
            "synthetic only; not calibrated market impact or exchange queue realism",
            "risk penalty is not cash; eta isolated-fill proxy is not the transient owner model",
            "daily.transaction_cost is cumulative; audit uses fill fees and prefix checks",
            "incomplete paths cannot win a terminal-liquidation comparison",
            "no production change, corporate action repair, alpha fitting or real net-performance claim",
        ],
        "table_encoding": "owner checkpoint _wire for exact tables; diagnostics retains original owner wire",
        "policy_source": "planning.owner_control.OwnerLiquidationPolicy",
        "model_information": "four control fields only; actual scenario retained outside callback; opaque restore identity",
    }
    write_json(output / "protocol.json", protocol)
    unique = {case_id(c): c for _, c in panels}
    results = {}
    for key, case in unique.items():
        folder = output / "cases" / key
        folder.mkdir(parents=True)
        try:
            results[key] = run_one(case, folder)
        except (ValueError, RuntimeError, ArithmeticError, AssertionError) as exc:
            results[key] = {
                "status": "unavailable",
                "exception": type(exc).__name__,
                "message": str(exc),
            }
            write_json(folder / "failure.json", results[key])
        print(
            "case", len(results), "/", len(unique), results[key]["status"], flush=True
        )
    write_json(output / "case-summary.json", results)
    write_json(
        output / "panel-summary.json",
        [
            {
                "panel": p,
                "case_id": case_id(c),
                "case": dataclasses.asdict(c),
                **results[case_id(c)],
            }
            for p, c in panels
        ],
    )
    recovery = [
        recovery_check(
            OwnerControlCase(
                policy=p,
                report_delay_seconds=300.0,
                latency_minutes=1,
                liquidity="outage",
            )
        )
        for p in POLICIES
    ]
    write_json(output / "recovery.json", recovery)
    files = {
        str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(output.rglob("*"))
        if p.is_file()
    }
    report = {
        "schema": "owner-control-study-report.v1",
        "identity": identity,
        "panel_rows": len(panels),
        "unique_cases": len(unique),
        "unavailable_cases": sum(v["status"] != "audited" for v in results.values()),
        "recovery_boundaries": sum(len(r["boundaries"]) for r in recovery),
        "files": files,
        "limits": protocol["limits"],
    }
    write_json(output / "report.json", report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("output", "code-root", "data-root"):
        parser.add_argument("--" + name, type=Path, required=True)
    a = parser.parse_args()
    result = export(
        a.output, Path(__file__).resolve().parents[2], a.code_root, a.data_root
    )
    return 2 if result["unavailable_cases"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
