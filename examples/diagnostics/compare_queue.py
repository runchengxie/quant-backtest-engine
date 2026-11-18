"""Optional HftBacktest 2.4.4 queue/arrival hand-oracle comparison.

Run with PYTHONPATH=core/src:python/src in an isolated experiment environment.
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


def own_probe(arrival):
    from quant_backtest_core.microstructure.matching import MatchingEngine

    engine = MatchingEngine()
    engine.apply_order("ahead", 1, 100, 5)
    engine.apply_order("lower", 1, 99, 10)
    filled = 0
    for _, kind in sorted([(arrival, "own"), (200, "sell")]):
        trade = (
            engine.apply_order("own", 1, 100, 3)
            if kind == "own"
            else engine.apply_order("seller", -1, 99, 7)
        )
        if trade:
            filled += sum(f.volume for f in trade.fills if f.buy_id == "own")
    return filled


def main():
    cases = []
    for latency, expected in ((1, 2), (150, 0)):
        external = probe(latency)
        own = own_probe(110 + latency)
        if external["executed"] != expected or own != expected:
            raise AssertionError(
                {"external": external, "own": own, "expected": expected}
            )
        cases.append({**external, "own_executed": own, "hand_oracle": expected})
    print(
        json.dumps(
            {
                "hftbacktest": version("hftbacktest"),
                "scope": "one passive queue hand oracle; not historical market-state parity",
                "clock": "synthetic nanoseconds for HftBacktest; supplied arrival ordering for own book",
                "model": "risk_adverse_queue_model / partial_fill_exchange",
                "calibrated": False,
                "cases": cases,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
