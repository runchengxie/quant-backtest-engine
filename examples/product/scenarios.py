"""Installed synthetic scenario callback; no model training or broker access.

Run with python -I -B examples/product/scenarios.py --output-root NEW_DIRECTORY.
"""

import argparse
import copy
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal
from pathlib import Path

from quant_backtest_core import BackendContext
from quant_backtest_core.artifacts import json_bytes
from quant_backtest_core.scenarios import run_scenarios
from quant_backtest_engine.product import ArtifactRef, ScenarioIdentity, parse_manifest

ROOT = Path(__file__).resolve().parents[2]

PREFIX = "1767576540000000000"  # 2026-01-05 09:29 Asia/Shanghai
DECISION = "1767576600000000000"  # 09:30
ENTRY = "1767576660000000000"  # 09:31
FILL = "1767576780000000000"  # 09:33, interval 09:32:30 > entry + 1 minute latency


def digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def artifact(root, name, value):
    data = json_bytes(value)
    (root / name).write_bytes(data)
    return ArtifactRef(name, hashlib.sha256(data).hexdigest(), "application/json")


def fixture(tmp_path, identifier="A", close="9", mode="recomputed", seed=1):
    from quant_backtest_core.scenarios import ScenarioCase

    sources = tmp_path / "inputs"
    sources.mkdir(exist_ok=True)
    calendar = artifact(
        sources,
        "calendar.json",
        {
            "schema": "synthetic-calendar.v1",
            "timezone": "Asia/Shanghai",
            "sessions": ["2026-01-05"],
        },
    )
    wire = json.loads((ROOT / "fixtures/product/minute-session.json").read_text())
    row = wire["inline_inputs"]["bars"][0]
    bars = []
    for instant, price in [(PREFIX, close), (DECISION, "10"), (FILL, "10")]:
        bar = copy.deepcopy(row)
        bar.update(
            time=instant,
            interval_start=str(int(instant) - 30_000_000_000),
            open=price,
            high=price,
            low=price,
            close=price,
            amount=str(int(price) * 1000),
            up_limit="20",
            down_limit="1",
            volume="1000",
        )
        bars.append(bar)
    wire["inline_inputs"] = {
        "bars": bars,
        "targets": [
            {
                "information_time": PREFIX,
                "decision_time": DECISION,
                "entry_time": ENTRY,
                "symbol": "A",
                "weight": "0",
            }
        ],
    }
    wire["calendar"] = asdict(calendar)
    wire["initial_account"] = {"cash": "1000"}
    wire["tapes"] = {key: [] for key in wire["tapes"]}
    wire["settings"]["config"].update(
        participation_rate="1",
        buy_fee_bp="0",
        sell_fee_bp="0",
        commission_minimum_cny="0",
        sell_tax_bp="0",
        lot_size=1,
        latency_minutes=1,
    )
    wire["settings"].update(impact=None, report_delay_seconds="0")
    wire["clocks"].update(
        available_ns=PREFIX, information_ns=PREFIX, decision_ns=DECISION, entry_ns=ENTRY
    )
    wire["required_capabilities"] = ["session_ledger"]
    identity = ScenarioIdentity(
        identifier, "external-market-path", seed, "1" * 64, "2" * 64, mode
    )
    return ScenarioCase(identity, parse_manifest(wire)), BackendContext(
        sources, tmp_path / "outputs"
    )


class PrefixProvider:
    def __init__(self, root, mutate=None):
        self.root, self.mutate = root, mutate
        self.seen = []

    def recompute(self, case, inputs):
        from quant_backtest_core.scenarios import PredictionArtifacts

        self.seen.append(case.identity.id)
        source = inputs["resolved_manifest"]["inline_inputs"]["bars"][0]
        targets = copy.deepcopy(inputs["resolved_manifest"]["inline_inputs"]["targets"])
        targets[0]["weight"] = "1" if Decimal(source["close"]) > 10 else "0"
        payload = {
            "schema": "scenario-minute-targets.v1",
            "scenario": asdict(case.identity),
            "provider_id": "synthetic-prefix",
            "provider_version": "v1",
            "available_ns": PREFIX,
            "input_sha256": digest(inputs),
            "targets": targets,
            "source_records": [
                {
                    "id": "synthetic-rule",
                    "kind": "implementation",
                    "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                }
            ],
            "consumed_inputs": [
                {
                    "pointer": "/resolved_manifest/inline_inputs/bars/0",
                    "sha256": digest(source),
                    "available_ns": PREFIX,
                }
            ],
        }
        if self.mutate:
            self.mutate(case, inputs, payload)
        forecast = artifact(self.root, case.identity.id + ".json", payload)
        return PredictionArtifacts(
            forecast,
            None,
            None,
            payload["provider_id"],
            payload["provider_version"],
            payload["available_ns"],
            payload["input_sha256"],
        )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    args.output_root.mkdir(parents=True, exist_ok=False)
    a, context = fixture(args.output_root, "A", "9", seed=1)
    bad, _ = fixture(args.output_root, "invalid-middle", "11", seed=2)
    b, _ = fixture(args.output_root, "B", "11", seed=3)
    fixed, _ = fixture(args.output_root, "fixed-B", "11", mode="fixed", seed=4)

    def reject_middle(case, inputs, payload):
        if case.identity.id == "invalid-middle":
            payload["schema"] = "opaque-forecast.v1"

    attempts = run_scenarios(
        [a, bad, b, fixed],
        context=context,
        prediction_provider=PrefixProvider(context.artifact_root, reject_middle),
    )
    assert [a.status for a in attempts] == [
        "completed",
        "failed",
        "completed",
        "completed",
    ]
    for index in (0, 3):
        assert (
            next(t.rows for t in attempts[index].result.tables if t.name == "fills")
            == ()
        )
    (fill,) = next(t.rows for t in attempts[2].result.tables if t.name == "fills")
    assert Decimal(fill["quantity"]) == 100 and Decimal(fill["price"]) == 10
    daily = next(t.rows for t in attempts[2].result.tables if t.name == "daily")[-1]
    assert Decimal(daily["cash"]) == 0
    print(
        json.dumps(
            {
                "attempts": [
                    {
                        "id": a.identity.id,
                        "status": a.status,
                        "composition": asdict(a.composition) if a.composition else None,
                    }
                    for a in attempts
                ],
                "hand_oracle": {"B_quantity": "100", "B_price": "10", "B_cash": "0"},
                "availability": "declared synthetic bar-close convention, not observed arrival",
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
