"""Hand-oracle timing probes of the existing Python book, not a latency model."""

import pytest

from quant_backtest_core.microstructure.matching import MatchingEngine


@pytest.mark.parametrize("arrival,filled", [(1, 2), (3, 0)])
def test_passive_order_arrival_changes_fill(arrival, filled):
    engine = MatchingEngine()
    engine.apply_order("ahead", 1, 100, 5)
    engine.apply_order("lower", 1, 99, 10)
    records = []
    for _, kind in sorted([(arrival, "own"), (2, "sell")]):
        trade = (
            engine.apply_order("own", 1, 100, 3)
            if kind == "own"
            else engine.apply_order("seller", -1, 99, 7)
        )
        if trade:
            records.extend(f for f in trade.fills if f.buy_id == "own")
    assert sum(f.volume for f in records) == filled


@pytest.mark.parametrize("cancel_arrival,filled", [(2, 0), (4, 3)])
def test_cancel_inflight_can_lose_race_to_trade(cancel_arrival, filled):
    engine = MatchingEngine()
    engine.apply_order("own", 1, 100, 3)
    records = []
    for _, kind in sorted([(cancel_arrival, "cancel"), (3, "sell")]):
        if kind == "cancel":
            engine.cancel_order("own")
        else:
            trade = engine.apply_order("seller", -1, 100, 3)
            if trade:
                records.extend(trade.fills)
    assert sum(f.volume for f in records if f.buy_id == "own") == filled


def test_walks_levels_and_partial_fill_keeps_residual():
    engine = MatchingEngine()
    engine.apply_order("ask1", -1, 101, 2)
    engine.apply_order("ask2", -1, 102, 3)
    trade = engine.apply_order("own", 1, 102, 7)
    assert [(f.price, f.volume) for f in trade.fills] == [(101, 2), (102, 3)]
    assert engine.lob.best_bid() == (102, 2)
    assert engine.lob.best_ask() is None
