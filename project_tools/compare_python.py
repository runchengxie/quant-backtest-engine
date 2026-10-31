"""Optional narrow differential check against the installed Python reference backend."""

from __future__ import annotations

import argparse
import json
from decimal import Decimal
from pathlib import Path

from tutorial import ROOT, invoke


def compare(engine: Path) -> dict:
    import pandas as pd
    from portfolio_backtester.backends import (
        NativePositionReplayBackend,
        NativePositionReplayRequest,
    )
    from portfolio_backtester.position_backtest import PositionBacktestConfig

    request = json.loads((ROOT / "fixtures/sessions.json").read_text())
    request["fee_bps"] = "0"
    request["enforce_t1"] = False
    request["sessions"][0]["orders"] = request["sessions"][0]["orders"][:1]
    request["sessions"][0]["orders"][0]["quantity"] = "1000"
    request["sessions"][1]["orders"][0]["quantity"] = "1000"
    result = invoke(engine, "run", request)
    python_result = NativePositionReplayBackend().run(
        NativePositionReplayRequest(
            positions=pd.DataFrame(
                [
                    {
                        "rebalance_date": "20250101",
                        "entry_date": "20250102",
                        "symbol": "AAA",
                        "weight": 1.0,
                        "side": "long",
                    }
                ]
            ),
            pricing=pd.DataFrame(
                [
                    {"trade_date": "20250102", "symbol": "AAA", "close": 10.0},
                    {"trade_date": "20250103", "symbol": "AAA", "close": 12.0},
                ]
            ),
            periods=pd.DataFrame(
                [
                    {
                        "rebalance_date": "20250101",
                        "entry_date": "20250102",
                        "exit_date": "20250103",
                    }
                ]
            ),
            config=PositionBacktestConfig(transaction_cost_bps=0.0),
        )
    )
    reference_return = Decimal(str(python_result.performance.iloc[0]["net_return"]))
    engine_return = Decimal(result["final_nav"]) / Decimal(request["initial_cash"]) - 1
    assert abs(reference_return - Decimal("0.2")) < Decimal("1e-12")
    assert abs(reference_return - engine_return) < Decimal("1e-12")
    return {
        "case": "fully-invested-fee-free-long-only",
        "python_return": str(reference_return),
        "rust_return": str(engine_return),
        "rust_final_nav": result["final_nav"],
        "scope": "Period return only; timing, daily marks, fees, corporate actions and full ledger parity are not compared.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--engine", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        parser.error("output must be a new external file")
    result = compare(args.engine.resolve(strict=True))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
