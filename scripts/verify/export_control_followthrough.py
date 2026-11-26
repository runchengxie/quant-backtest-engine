"""Fixed synthetic follow-through export. No market parameters are fitted."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd
from quant_backtest_core.backtest._minute_checkpoint import _wire
from quant_backtest_core.planning import (
    control_followthrough,
    control_followthrough_audit,
)
from quant_backtest_core.planning.control_followthrough import (
    StudyCase,
    build_study,
    restore_study,
    run_study,
    study_inputs,
)
from quant_backtest_core.planning.control_followthrough_audit import audit_study
from quant_backtest_core.planning.owner_control_case import OwnerControlCase

sys.path.insert(0, str(Path(__file__).resolve().parent))
from export_owner_control import fresh_output, source_identity, write_json


def study_id(case: StudyCase) -> str:
    return hashlib.sha256(
        json.dumps(dataclasses.asdict(case), sort_keys=True, allow_nan=False).encode()
    ).hexdigest()


def fixed_studies() -> list[tuple[str, StudyCase]]:
    controls = [
        ("immediate", 0),
        ("open_loop", 0),
        ("twap", 0),
        ("rolling", 0),
        ("rolling", 1),
    ]
    rows = []
    for (policy, reserve), delay, latency, liquidity in itertools.product(
        controls, (0.0, 300.0), (0, 1), ("normal", "outage")
    ):
        rows.append(
            (
                "feedback",
                StudyCase(
                    OwnerControlCase(
                        policy=policy,
                        report_delay_seconds=delay,
                        latency_minutes=latency,
                        liquidity=liquidity,
                    ),
                    reserve_slots=reserve,
                ),
            )
        )
    for (policy, reserve), path in itertools.product(
        controls, ("flat", "up", "down", "oscillating", "jump")
    ):
        rows.append(
            (
                "price",
                StudyCase(
                    OwnerControlCase(policy=policy),
                    price_path=path,
                    reserve_slots=reserve,
                ),
            )
        )
    for policy, reserve in controls:
        rows.append(
            (
                "capacity",
                StudyCase(
                    OwnerControlCase(policy=policy, quantity=1200),
                    reserve_slots=reserve,
                ),
            )
        )
    return rows


def recovery(case: StudyCase) -> dict[str, Any]:
    expected, diag = run_study(case)
    session = build_study(case)
    boundaries = []
    while True:
        cp = json.loads(json.dumps(session.checkpoint(), allow_nan=False))
        restored = restore_study(case, cp)
        while restored.step():
            pass
        if restored.checkpoint() != diag["checkpoint"]:
            raise ValueError("restored final checkpoint differs")
        actual = restored.run()
        for name in ("daily", "orders", "fills", "holdings"):
            pd.testing.assert_frame_equal(
                getattr(actual, name), getattr(expected, name), check_exact=True
            )
        if _wire(actual.summary) != _wire(expected.summary):
            raise ValueError("restored summary differs")
        boundaries.append(
            {"cursor": session.cursor, "digest": cp["digest"], "exact": True}
        )
        if not session.step():
            break
    return {"case_id": study_id(case), "boundaries": boundaries}


def export(output: Path, root: Path, code: Path, data: Path) -> dict[str, Any]:
    identity = source_identity(root)
    for module in (control_followthrough, control_followthrough_audit):
        path = (
            root
            / "packages/core/src"
            / Path(*module.__name__.split(".")).with_suffix(".py")
        )
        if path.read_bytes() != Path(module.__file__).read_bytes():
            raise ValueError("installed follow-through source differs")
    for path in (Path(__file__), Path(__file__).with_name("export_owner_control.py")):
        identity["source_sha256"][str(path.relative_to(root))] = hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
    output = fresh_output(output, code, data)
    rows = fixed_studies()
    protocol = {
        "schema": "control-followthrough.v1",
        "source": identity,
        "panels": [
            {"panel": p, "case_id": study_id(c), "case": dataclasses.asdict(c)}
            for p, c in rows
        ],
        "limitations": [
            "synthetic fixed paths, not forecasts or market samples",
            "hard report gate unchanged; concurrent reservation not implemented",
            "flags overlap, not causal shares",
            "residual inventory marked, not forced liquidation",
            "no parameter/winner selection",
        ],
    }
    write_json(output / "protocol.json", protocol)
    cases = {study_id(c): c for _, c in rows}
    summaries = []
    for cid, case in cases.items():
        folder = output / cid
        folder.mkdir()
        targets, bars, config = study_inputs(case)
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
        try:
            result, diag = run_study(case)
            metric = audit_study(case, result, diag)
            write_json(
                folder / "owner.json",
                _wire(
                    {
                        n: getattr(result, n)
                        for n in ("daily", "orders", "fills", "holdings", "summary")
                    }
                ),
            )
            write_json(folder / "diagnostics.json", diag)
            write_json(folder / "metrics.json", metric)
            summaries.append(
                {
                    "case_id": cid,
                    "case": dataclasses.asdict(case),
                    "status": "audited",
                    "metrics": metric,
                }
            )
        except (ValueError, RuntimeError, ArithmeticError, AssertionError) as exc:
            summaries.append(
                {
                    "case_id": cid,
                    "case": dataclasses.asdict(case),
                    "status": "unavailable",
                    "error": str(exc),
                }
            )
    write_json(output / "case-summary.json", summaries)
    recoveries = [
        recovery(
            StudyCase(
                OwnerControlCase(
                    policy="rolling",
                    report_delay_seconds=delay,
                    latency_minutes=latency,
                    liquidity="outage",
                ),
                price_path="jump",
                reserve_slots=1,
            )
        )
        for delay, latency in ((0, 0), (300, 1))
    ]
    write_json(output / "recovery.json", recoveries)
    report = {
        "schema": "control-followthrough-report.v1",
        "source": identity,
        "panel_rows": len(rows),
        "unique_cases": len(cases),
        "unavailable": sum(s["status"] == "unavailable" for s in summaries),
        "recovery_boundaries": sum(len(r["boundaries"]) for r in recoveries),
        "files": {
            str(p.relative_to(output)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(output.rglob("*.json"))
        },
    }
    write_json(output / "report.json", report)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--code-root", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    args = parser.parse_args()
    report = export(
        args.output, Path(__file__).resolve().parents[2], args.code_root, args.data_root
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "panel_rows",
                    "unique_cases",
                    "unavailable",
                    "recovery_boundaries",
                )
            }
        )
    )
    raise SystemExit(2 if report["unavailable"] else 0)
