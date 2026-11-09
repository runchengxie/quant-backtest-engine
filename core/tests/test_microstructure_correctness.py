"""Synthetic characterization of the legacy empty-start, best-quote diagnostic."""

from __future__ import annotations

from quant_backtest_core.microstructure.correctness import replay_and_compare
from quant_backtest_core.microstructure.pack import build_simulator_pack


def _synthetic_pack():
    """构造合成序列：snapshot@0 -> 挂单 -> 撤单 -> snapshot@1000。"""
    orders = [
        {
            "time_ms": 100,
            "order_id": "O1",
            "price": 1000,
            "volume": 500,
            "order_type": 0,
            "side": 1,
            "last_price": 1000,
        },
        {
            "time_ms": 200,
            "order_id": "O2",
            "price": 1001,
            "volume": 300,
            "order_type": 0,
            "side": -1,
            "last_price": 1001,
        },
        {
            "time_ms": 300,
            "order_id": "O3",
            "price": 1000,
            "volume": 200,
            "order_type": 0,
            "side": 1,
            "last_price": 1000,
        },
    ]
    trades = []
    snapshots = [
        {
            "time_ms": 0,
            "bid": [(999, 400)],
            "ask": [(1002, 250)],
            "order_count": {"bid": [1], "ask": [1]},
        },
        # 回放后预期盘口：买一 1000(700)、卖一 1001(300)
        {
            "time_ms": 1000,
            "bid": [(1000, 700)],
            "ask": [(1001, 300)],
            "order_count": {"bid": [2], "ask": [1]},
        },
    ]
    return build_simulator_pack(orders, trades, snapshots)


def test_replay_reconstructs_matching_snapshot():
    pack = _synthetic_pack()
    # 第一个 snapshot 仅确定起始时钟；从空盘口回放后对比第二个 snapshot
    result = replay_and_compare(pack, init_snapshot_idx=0, target_snapshot_idx=1)
    assert result.matched, result.detail
    assert result.bid_error == 0
    assert result.ask_error == 0


def test_replay_detects_mismatch():
    pack = _synthetic_pack()
    # 故意改坏目标 snapshot 的期望值，应报不匹配
    pack.snapshots[1].expected_bid = (999, 999)
    result = replay_and_compare(pack, init_snapshot_idx=0, target_snapshot_idx=1)
    assert not result.matched


def test_replay_marks_missing_target_as_not_comparable():
    pack = _synthetic_pack()
    pack.snapshots[1].expected_ask = None

    result = replay_and_compare(pack, init_snapshot_idx=0, target_snapshot_idx=1)

    assert result.status == "not_comparable"
    assert result.matched is False


def test_unchanged_nonempty_snapshots_remain_comparable_mismatch():
    snapshots = [
        {"time_ms": time_ms, "bid": [(100, 5)], "ask": [(101, 7)]} for time_ms in (0, 1000)
    ]
    pack = build_simulator_pack([], [], snapshots)

    result = replay_and_compare(pack)

    assert result.status == "mismatched"
    assert result.matched is False
    assert result.comparable is True
    assert result.bid_error == 1
    assert result.ask_error == 1
