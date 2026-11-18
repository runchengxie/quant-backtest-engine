"""Snapshot reconstruction must inspect depth and preserve unavailable evidence."""

import pytest

from quant_backtest_core.microstructure.depth_audit import audit_depth
from quant_backtest_core.microstructure.pack import SimulatorEvent as E
from quant_backtest_core.microstructure.pack import SimulatorPack


def pack(events=(), target=((101, 10), (102, 20))):
    start = E(0, "snapshot", bid_levels=((100, 10), (99, 20)), ask_levels=((101, 10), (102, 20)))
    end = E(10, "snapshot", bid_levels=((100, 10), (99, 20)), ask_levels=target)
    return SimulatorPack(list(events), [start, end])


def test_seeds_snapshot_and_compares_deeper_levels():
    assert audit_depth(pack()).status == "matched"
    result = audit_depth(pack(target=((101, 10), (102, 19))))
    assert result.status == "mismatched"
    assert result.ask_differences == ((102, 20, 19),)


def test_order_implied_fills_not_charged_twice():
    p = pack(
        [
            E(1, "order", order_id="buy", side=1, price=102, volume=15),
            E(2, "trade", price=101, volume=15),
        ],
        target=((102, 15),),
    )
    assert audit_depth(p).status == "matched"


def test_unknown_cancellation_remains_unavailable():
    r = audit_depth(pack([E(1, "cancel", order_id="before-snapshot")]))
    assert r.status == "not_comparable"
    assert r.reason == "unknown_cancel_id"


def test_missing_depth_and_boundary_ambiguity():
    p = pack()
    p.snapshots[1].ask_levels = None
    assert audit_depth(p).status == "not_comparable"
    assert (
        audit_depth(pack([E(10, "order", order_id="x", side=1, price=99, volume=1)])).reason
        == "snapshot_boundary_ambiguous"
    )


def test_rejects_time_reversal_and_duplicate_order_id():
    with pytest.raises(ValueError, match="ordered"):
        audit_depth(pack([E(2, "trade"), E(1, "trade")]))
    with pytest.raises(ValueError, match="duplicate"):
        audit_depth(
            pack([E(t, "order", order_id="same", side=1, price=99, volume=1) for t in (1, 2)])
        )


def test_sequence_gap_or_duplicate_not_certified():
    for seqs in [(1, 3), (1, 1), (2, 1)]:
        events = [E(i + 1, "trade", channel="A", sequence=n) for i, n in enumerate(seqs)]
        assert audit_depth(pack(events)).reason == "channel_sequence_discontinuity"


def test_cross_channel_tie_and_unsupported_order_type():
    events = [E(1, "trade", channel=c, sequence=1) for c in ("A", "B")]
    assert audit_depth(pack(events)).reason == "cross_channel_tie"
    assert (
        audit_depth(
            pack([E(1, "order", order_id="x", side=1, price=99, volume=1, order_type=9)])
        ).reason
        == "unsupported_order_type"
    )


def test_invalid_depth_and_incomplete_comparison():
    p = pack()
    p.snapshots[0].bid_levels = ((99, 10), (100, 10))
    with pytest.raises(ValueError, match="depth"):
        audit_depth(p)
    p = pack()
    p.snapshots[0].ask_levels = ((101, True),)
    with pytest.raises(ValueError, match="integer"):
        audit_depth(p)


def test_partial_target_only_checks_declared_depth():
    r = audit_depth(pack(target=((101, 10),)))
    assert r.status == "matched"
    assert r.scope == "supplied_snapshot_depth_orders_imply_trades"
    assert r.initial_order_identity_available is False


def test_partial_cancel_is_not_silently_interpreted_as_full_cancel():
    p = pack(
        [
            E(1, "order", order_id="new", side=1, price=99, volume=10),
            E(2, "cancel", order_id="new", volume=3),
        ]
    )
    assert audit_depth(p).reason == "partial_cancel_unsupported"


def test_known_cancel_and_readonly_depth():
    p = pack(
        [E(1, "order", order_id="new", side=1, price=99, volume=10), E(2, "cancel", order_id="new")]
    )
    result = audit_depth(p)
    assert result.status == "matched"
    assert result.sequence_evidence == "unknown"
    assert result.trade_rows_reconciled is False
