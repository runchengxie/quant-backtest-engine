"""Run the synthetic target-weight -> order -> session-ledger walkthrough."""

from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def invoke(engine: Path, command: str, request: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="engine-tutorial-") as directory:
        path = Path(directory) / "request.json"
        path.write_text(json.dumps(request), encoding="utf-8")
        process = subprocess.run(
            [str(engine), command, str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return json.loads(process.stdout)


def walkthrough(engine: Path) -> dict:
    request = json.loads((ROOT / "fixtures/sessions.json").read_text())
    first = request["sessions"][0]
    information_time = first["open_ts_ns"] - 1
    sizing = {
        "schema_version": "sizing_request.v1",
        "currency": "CNY",
        "information_ts_ns": information_time,
        "cash": "10000",
        "fee_bps": "10",
        "assets": [
            {
                "symbol": "AAA",
                "held_quantity": "0",
                "reference_price": "10",
                "price_ts_ns": information_time,
                "target_weight": "0.1",
                "buy_lot": 100,
            }
        ],
    }
    # Reference price is synthetic information available BEFORE the first quote.
    # The model/weight generation itself belongs to research, not the engine.
    plan = invoke(engine, "size", sizing)
    assert len(plan["orders"]) == 1 and plan["orders"][0]["quantity"] == "100"
    first["orders"][0] = plan["orders"][0]
    result = invoke(engine, "run", request)
    assert len(result["daily_ledger"]) == 2
    for day, expected in zip(
        result["daily_ledger"], [("8999", "1100", "10099"), ("10197.8", "0", "10197.8")]
    ):
        assert tuple(
            Decimal(day[k]) for k in ("cash", "positions_value", "nav")
        ) == tuple(map(Decimal, expected))
    assert Decimal(result["total_commission"]) == Decimal("2.2")
    statuses = {order["id"]: order["status"] for order in result["orders"]}
    assert statuses["same-day-sell"] == "DENIED"
    assert statuses["next-day-sell"] == "FILLED"
    assert len(result["fills"]) == 2
    assert any(
        row["order_id"] == "same-day-sell" and row["reason"]
        for row in result["rejections"]
    )
    return {
        "engine_sha256": hashlib.sha256(engine.read_bytes()).hexdigest(),
        "sizing_request": sizing,
        "sizing_result": plan,
        "engine_request": request,
        "engine_result": result,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, required=True, help="New external output directory"
    )
    args = parser.parse_args()
    engine = args.engine.resolve(strict=True)
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        parser.error("output must be a new directory outside the source repository")
    records = walkthrough(engine)
    output.mkdir(parents=True)
    for name, value in records.items():
        (output / f"{name}.json").write_text(
            json.dumps(value, indent=2) + "\n", encoding="utf-8"
        )
    print(
        json.dumps(
            {
                "status": "passed",
                "final_nav": records["engine_result"]["final_nav"],
                "output": str(output),
            }
        )
    )


if __name__ == "__main__":
    main()
