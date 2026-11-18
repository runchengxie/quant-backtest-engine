"""Optional HftBacktest 2.4.4 queue/arrival hand-oracle comparison.

Run with PYTHONPATH=packages/core/src:packages/python-sdk/src in an isolated experiment environment.
This compares one passive order under a supplied queue assumption. The two
engines do not share market-state semantics; this is not historical feed parity.
No product financial backend or production dependency is registered.
"""

import json
import hashlib
from importlib.metadata import version
import numpy as np
from hftbacktest import (
    BacktestAsset,
    HashMapMarketDepthBacktest,
    DEPTH_EVENT,
    TRADE_EVENT,
    EXCH_EVENT,
    LOCAL_EVENT,
    BUY_EVENT,
    SELL_EVENT,
)
from hftbacktest.types import event_dtype
from hftbacktest.order import GTC, LIMIT


def probe(entry_latency):
    if version("hftbacktest") != "2.4.4":
        raise RuntimeError("this probe requires hftbacktest 2.4.4")
    f = EXCH_EVENT | LOCAL_EVENT
    rows = [
        (f | DEPTH_EVENT | BUY_EVENT, 100, 100, 100.0, 5.0, 0, 0, 0.0),
        (f | DEPTH_EVENT | SELL_EVENT, 100, 100, 101.0, 10.0, 0, 0, 0.0),
        (f | TRADE_EVENT | SELL_EVENT, 200, 200, 100.0, 7.0, 0, 0, 0.0),
        (f | DEPTH_EVENT | BUY_EVENT, 201, 201, 100.0, 0.0, 0, 0, 0.0),
        (f | DEPTH_EVENT | BUY_EVENT, 1000, 1000, 99.0, 10.0, 0, 0, 0.0),
    ]
    data = np.array(rows, dtype=event_dtype)
    asset = (
        BacktestAsset()
        .data(data)
        .linear_asset(1.0)
        .constant_order_latency(entry_latency, 0)
        .risk_adverse_queue_model()
        .partial_fill_exchange()
        .trading_value_fee_model(0.0, 0.0)
        .tick_size(1.0)
        .lot_size(1.0)
    )
    h = HashMapMarketDepthBacktest([asset])
    try:
        assert h.elapse(10) == 0
        assert h.current_timestamp == 110
        assert h.submit_buy_order(0, 1, 100.0, 3.0, GTC, LIMIT, False) == 0
        assert h.elapse(300) == 0
        order = h.orders(0).get(1)
        return {
            "entry_latency": entry_latency,
            "input_sha256": hashlib.sha256(data.tobytes()).hexdigest(),
            "observed_at": int(h.current_timestamp),
            "executed": float(order.exec_qty),
            "remaining": float(order.leaves_qty),
            "status": int(order.status),
        }
    finally:
        h.close()


def own_probe(entry_latency):
    from quant_backtest_core.microstructure.latency_replay import Command, replay_commands

    result = replay_commands(
        [
            Command("ahead", "order", 100, 0, 0, 0, "ahead", 1, 100, 5),
            Command("lower", "order", 100, 0, 0, 1, "lower", 1, 99, 10),
            Command("own", "order", 110, entry_latency, 0, 2, "own", 1, 100, 3),
            Command("seller", "order", 200, 0, 0, 3, "seller", -1, 99, 7),
        ]
    )
    filled = sum(f.volume for e in result.events for f in e.fills if f.buy_id == "own")
    return filled, result.input_sha256


def main():
    cases = []
    for latency, expected in ((1, 2), (150, 0)):
        external = probe(latency)
        own, own_hash = own_probe(latency)
        if external["executed"] != expected or own != expected:
            raise AssertionError({"external": external, "own": own, "expected": expected})
        cases.append(
            {**external, "own_executed": own, "own_input_sha256": own_hash, "hand_oracle": expected}
        )
    print(
        json.dumps(
            {
                "hftbacktest": version("hftbacktest"),
                "scope": "one passive queue hand oracle; not historical market-state parity",
                "clock": "synthetic nanoseconds; explicit send plus entry latency in both probes",
                "model": "risk_adverse_queue_model / partial_fill_exchange",
                "calibrated": False,
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
