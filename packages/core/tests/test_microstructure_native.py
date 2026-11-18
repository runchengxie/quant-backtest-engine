"""Rust simulation kernel must agree with the public Python reference."""

from __future__ import annotations

import importlib
import os
import random

import pytest

from quant_backtest_core.microstructure.matching import LimitOrderBook, MatchingEngine
from quant_backtest_core.microstructure.ordering import sort_simulator_events
from quant_backtest_core.microstructure.pack import SimulatorEvent
from quant_backtest_core.microstructure.replay import InterventionOrder, ReplaySession


def _native():
    try:
        return importlib.import_module("_microstructure_rs")
    except ImportError:
        if os.environ.get("TICKNET_REQUIRE_RUST") == "1":
            raise
        pytest.skip("optional Rust wheel is not installed")


def test_order_book_matches_python_reference_for_seeded_events():
    native = _native()
    for seed in range(20):
        rng = random.Random(seed)
        python_book = LimitOrderBook()
        rust_book = native.OrderBook()
        ids: list[str] = []
        for index in range(300):
            if ids and rng.random() < 0.25:
                order_id = rng.choice(ids)
                quantity = rng.choice([None, 1, 10, 1000])
                assert rust_book.cancel_order(order_id, quantity) == python_book.cancel_order(
                    order_id, quantity
                )
            else:
                order_id = f"{seed}-{index}"
                ids.append(order_id)
                side = rng.choice([-1, 1])
                price = rng.randint(97, 103)
                volume = rng.randint(1, 100)
                actual = rust_book.apply_order(order_id, side, price, volume)
                expected = python_book.apply_order(order_id, side, price, volume)
                assert actual == (
                    None
                    if expected is None
                    else (expected.buy_id, expected.sell_id, expected.price, expected.volume)
                )
            assert rust_book.best_bid() == python_book.best_bid()
            assert rust_book.best_ask() == python_book.best_ask()


def test_batch_replay_matches_python_and_keeps_book_state():
    native = _native()
    python_engine = MatchingEngine()
    session = ReplaySession(python_engine, (100, 50), (101, 40), init_time_ms=7)
    background = [(12, -1, 100, 20, ""), (14, 1, 101, 10, "B"), (14, -1, 99, 5, "S")]
    interventions = [(12, 1, 101, 30, "I"), (15, -1, 100, 10, "J")]
    for row in background:
        session.add_background(*row)
    for row in interventions:
        session.add_intervention(InterventionOrder(*row))
    expected = session.run()

    book = native.OrderBook()
    book.apply_order("INIT_BID", 1, 100, 50)
    book.apply_order("INIT_ASK", -1, 101, 40)
    actual = book.replay(background, interventions)
    assert actual == [
        (tick.time_ms, tick.best_bid, tick.best_ask, tick.source) for tick in expected[1:]
    ]
    assert book.best_bid() == python_engine.lob.best_bid()
    assert book.best_ask() == python_engine.lob.best_ask()


def test_timestamp_ordering_preserves_cross_channel_source_order():
    native = _native()
    rows = [
        (10, "order", "A", 2, 2),
        (10, "snapshot", "", None, 0),
        (10, "cancel", "B", 1, 1),
        (9, "order", "", None, 3),
    ]
    assert native.sort_event_indices(rows) == [3, 2, 0, 1]


def test_public_engine_and_replay_use_rust_backend():
    _native()
    engine = MatchingEngine(backend="rust")
    session = ReplaySession(engine, (100, 50), (101, 40))
    session.add_intervention(InterventionOrder(1, 1, 101, 45, "I"))
    ticks = session.run()
    assert [tick.best_bid for tick in ticks] == [(100, 50), (101, 5)]
    assert engine.lob.best_ask() is None


def test_public_ordering_backend_matches_python():
    _native()
    events = [
        SimulatorEvent(10, "order", order_id="a", channel="A", sequence=3, source_index=0),
        SimulatorEvent(10, "cancel", order_id="b", channel="A", sequence=1, source_index=1),
        SimulatorEvent(10, "snapshot", source_index=2),
        SimulatorEvent(9, "order", order_id="c", source_index=3),
    ]
    assert sort_simulator_events(events, backend="rust") == sort_simulator_events(events)


def test_seed_and_anonymous_reduction_match_python():
    native = _native()
    python_book = LimitOrderBook()
    rust_book = native.OrderBook()
    for book in (python_book, rust_book):
        book.seed_level(1, 100, 20, "a")
        book.seed_level(1, 100, 30, "b")
        assert book.reduce_level(1, 100, 25)
        assert book.best_bid() == (100, 25)
        assert not book.has_order("a")
        assert book.has_order("b")
        assert not book.reduce_level(-1, 100, 3)
        assert book.cancel_order("b", 50) is False
        assert book.best_bid() == (100, 25)


def test_ordering_randomized_differential():
    _native()
    for seed in range(30):
        rng = random.Random(seed)
        events = [
            SimulatorEvent(
                rng.randrange(5),
                rng.choice(["order", "cancel", "trade", "snapshot"]),
                order_id=str(i),
                channel=rng.choice(["", "A", "B"]),
                sequence=rng.choice([None, 1, 2, 3]),
                source_index=i,
            )
            for i in range(100)
        ]
        assert sort_simulator_events(events, backend="rust") == sort_simulator_events(events)


def test_unknown_side_matches_python_reference():
    native = _native()
    python_book = LimitOrderBook()
    rust_book = native.OrderBook()
    for book in (python_book, rust_book):
        book.apply_order("low", 1, 98, 10)
        book.apply_order("high", 1, 101, 10)
    expected = python_book.apply_order("unknown", 0, 100, 5)
    actual = rust_book.apply_order("unknown", 0, 100, 5)
    assert actual == (expected.buy_id, expected.sell_id, expected.price, expected.volume)
    assert rust_book.best_bid() == python_book.best_bid()


def test_replay_generated_ids_follow_sorted_background_position():
    native = _native()
    background = [(20, 1, 99, 1, ""), (10, 1, 100, 1, "")]
    python_engine = MatchingEngine()
    session = ReplaySession(python_engine, (95, 1), (105, 1))
    for row in background:
        session.add_background(*row)
    session.run()

    rust_book = native.OrderBook()
    rust_book.apply_order("INIT_BID", 1, 95, 1)
    rust_book.apply_order("INIT_ASK", -1, 105, 1)
    rust_book.replay(background, [])
    for order_id in ("BG0", "BG1"):
        assert rust_book.cancel_order(order_id) == python_engine.cancel_order(order_id)
        assert rust_book.best_bid() == python_engine.lob.best_bid()


def test_complete_supported_replay_outputs_include_native_fill_evidence():
    """Compare every tick and fill, including tied integer clocks above 2**53."""
    from dataclasses import asdict

    _native()
    sessions = [
        ReplaySession(MatchingEngine(backend=b), (100, 50), (101, 40)) for b in ("python", "rust")
    ]
    for session in sessions:
        session.add_background(2**53 + 1, 1, 101, 3, "first")
        session.add_background(2**53 + 1, 1, 101, 4, "second")
        session.add_intervention(InterventionOrder(2**53 + 1, 1, 101, 5, "iv"))
        session.run()
        session.run()
    assert [asdict(t) for t in sessions[0].ticks] == [asdict(t) for t in sessions[1].ticks]
    assert [asdict(f) for f in sessions[0].fills] == [
        dict(
            buy_id=name,
            sell_id="INIT_ASK",
            price=101,
            volume=volume,
            time_ms=2**53 + 1,
            source=source,
        )
        for name, volume, source in [
            ("iv", 5, "intervention"),
            ("first", 3, "background"),
            ("second", 4, "background"),
        ]
    ]
    assert sessions[1].fills == sessions[0].fills


def test_full_aggregate_trade_fields_and_multilevel_python_fills():
    from dataclasses import asdict

    _native()
    engines = [MatchingEngine(backend=b) for b in ("python", "rust")]
    for engine in engines:
        engine.apply_order("a", -1, 101, 3)
        engine.apply_order("b", -1, 102, 4)
    python_trade, rust_trade = [e.apply_order("buy", 1, 102, 6) for e in engines]
    assert asdict(python_trade) == dict(
        buy_id="buy",
        sell_id="b",
        price=102,
        volume=6,
        fills=(
            {"buy_id": "buy", "sell_id": "a", "price": 101, "volume": 3},
            {"buy_id": "buy", "sell_id": "b", "price": 102, "volume": 3},
        ),
    )
    assert asdict(rust_trade) == asdict(python_trade)
    assert engines[0].lob.best_ask() == engines[1].lob.best_ask() == (102, 1)


def test_equal_clock_all_equal_keys_preserve_input_sequence_native():
    _native()
    events = [
        SimulatorEvent(2**53 + 1, "order", order_id=name, channel="A", sequence=1, source_index=0)
        for name in ("a", "b", "c")
    ]
    assert sort_simulator_events(events, backend="rust") == events


def test_sequence_gap_fixture_preserves_native_reference_parity():
    """Same synthetic rows as Platform sequence_gap, without its scenario I/O owner."""
    from quant_backtest_core.microstructure.ordering import ordering_provenance

    _native()
    events = [
        SimulatorEvent(100, "order", order_id="SYN_A", channel="1", sequence=1, source_index=0),
        SimulatorEvent(100, "cancel", order_id="SYN_A", channel="1", sequence=3, source_index=1),
    ]
    assert sort_simulator_events(events, backend="rust") == sort_simulator_events(events)
    assert ordering_provenance(events)["sequence_gap_count"] == 1
    assert ordering_provenance(events)["sequence_completeness"] == "gaps_observed"


def test_duplicate_ids_retain_explicit_legacy_backend_difference():
    """Duplicate IDs are not a parity-supported identity contract in legacy v0.1."""
    _native()
    python_engine, native_engine = [MatchingEngine(backend=b) for b in ("python", "rust")]
    for engine in (python_engine, native_engine):
        engine.apply_order("duplicate", 1, 100, 5)
        engine.apply_order("duplicate", 1, 100, 7)
        assert engine.cancel_order("duplicate", 3)
        assert engine.lob.best_bid() == (100, 9)
        assert engine.cancel_order("duplicate")
        assert not engine.has_order("duplicate")
    assert python_engine.lob.best_bid() is None
    assert native_engine.lob.best_bid() == (100, 7)


def test_native_impact_estimation_uses_fill_evidence():
    _native()
    from quant_backtest_core.microstructure.impact import ExecutionSchedule, ImpactEstimator

    session = ReplaySession(MatchingEngine(backend="rust"), (100, 50), (101, 40))
    result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 10))
    assert result.filled_volume == 10
    assert result.execution_vwap == 101
    assert session.engine.lob.best_ask() == (101, 30)
    assert len(session.fills) == 1


def test_native_detailed_fills_preserve_fifo_prices_and_snapshot():
    native = _native()
    for side in (1, -1):
        book = native.OrderBook()
        for oid, price, qty in [
            ("first", 100, 3),
            ("second", 100, 4),
            ("third", 101 if side == 1 else 99, 5),
        ]:
            book.apply_order(oid, -side, price, qty)
        result = book.apply_order_with_fills("taker", side, 102 if side == 1 else 98, 10)
        expected = (
            [("taker", "first", 100, 3), ("taker", "second", 100, 4), ("taker", "third", 101, 3)]
            if side == 1
            else [
                ("first", "taker", 100, 3),
                ("second", "taker", 100, 4),
                ("third", "taker", 99, 3),
            ]
        )
        assert result[1] == expected
        assert result[0] == (*expected[-1][:3], 10)
        snapshot = list(result[1])
        book.cancel_order("third")
        assert result[1] == snapshot
        assert book.apply_order_with_fills("zero", side, 100, 0) is None


def test_public_native_detailed_randomized_parity():
    _native()
    for seed in range(12):
        rng = random.Random(seed)
        reference, native = MatchingEngine(), MatchingEngine("rust")
        for i in range(250):
            if i and rng.random() < 0.2:
                oid, qty = str(rng.randrange(i)), rng.choice([None, 1, 7])
                assert native.cancel_order(oid, qty) == reference.cancel_order(oid, qty)
            else:
                args = (str(i), rng.choice([-1, 1]), rng.randrange(97, 104), rng.randrange(1, 50))
                assert native.apply_order(*args) == reference.apply_order(*args)
            assert native.lob.best_bid() == reference.lob.best_bid()
            assert native.lob.best_ask() == reference.lob.best_ask()


def test_replay_native_keeps_per_fill_evidence_across_runs():
    _native()
    sessions = [ReplaySession(MatchingEngine(b), (99, 10), (101, 4)) for b in ("python", "rust")]
    for session in sessions:
        session.add_background(1, -1, 101, 3, "ask2")
        session.add_background(1, -1, 102, 5, "ask3")
        session.add_intervention(InterventionOrder(2, 1, 102, 10, "take"))
        session.run()
    assert sessions[0].fills == sessions[1].fills
    assert len(sessions[1].fills) == 3
    for session in sessions:
        session.add_background(3, 1, 102, 2, "later")
        session.run()
    assert sessions[0].fills == sessions[1].fills
    assert sessions[0].ticks == sessions[1].ticks


@pytest.mark.parametrize("side", [1, -1])
@pytest.mark.parametrize("children", [1, 3])
def test_native_impact_estimate_matches_python(side, children):
    _native()
    from quant_backtest_core.microstructure.impact import ExecutionSchedule, ImpactEstimator

    results = []
    for backend in ("python", "rust"):
        session = ReplaySession(MatchingEngine(backend), (100, 8), (101, 6))
        session.add_background(1500, -side, 101 if side == 1 else 100, 5, "extra")
        result = ImpactEstimator(session).estimate(
            ExecutionSchedule(side, 20, children, start_time_ms=1000, end_time_ms=2000)
        )
        results.append(result)
    assert results[0] == results[1]


def test_old_native_wheel_rejected_before_order_mutation(monkeypatch):
    import sys
    from types import SimpleNamespace

    class OldBook:
        def apply_order(self, *args):
            raise AssertionError("old book must not be mutated")

    monkeypatch.setitem(sys.modules, "_microstructure_rs", SimpleNamespace(OrderBook=OldBook))
    with pytest.raises(ImportError, match="per-fill evidence API"):
        MatchingEngine("rust")
