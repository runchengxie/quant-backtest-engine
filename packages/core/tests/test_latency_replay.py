"""Independent hand oracles for supplied nanosecond command timing."""

import pytest

from quant_backtest_core.microstructure.latency_replay import Command, replay_commands


def order(key, time, seq, side, price, quantity, delay=0, response=0):
    return Command(key, "order", time, delay, response, seq, key, side, price, quantity)


def scenario(delay):
    return [
        order("ahead", 100, 0, 1, 100, 5),
        order("lower", 100, 1, 1, 99, 10),
        order("own", 110, 2, 1, 100, 3, delay),
        order("sell", 200, 3, -1, 99, 7),
    ]


@pytest.mark.parametrize("delay,expected", [(1, 2), (150, 0)])
def test_arrival_and_fifo(delay, expected):
    result = replay_commands(scenario(delay))
    assert sum(f.volume for e in result.events for f in e.fills if f.buy_id == "own") == expected
    assert result.input_sha256 == replay_commands(scenario(delay)[::-1]).input_sha256


@pytest.mark.parametrize("delay,expected,status", [(0, 0, "cancelled"), (100, 3, "not_resting")])
def test_cancel_arrives_before_or_after_trade(delay, expected, status):
    commands = [
        order("own", 100, 0, 1, 100, 3),
        order("seller", 200, 2, -1, 100, 3),
        Command("cancel", "cancel", 150, delay, 0, 1, "own"),
    ]
    result = replay_commands(commands)
    assert sum(f.volume for e in result.events for f in e.fills if f.buy_id == "own") == expected
    assert next(e for e in result.events if e.event_id == "cancel").status == status


def test_same_clock_uses_explicit_sequence_and_multi_level_prices():
    commands = [
        order("b", 100, 1, -1, 102, 3),
        order("a", 100, 0, -1, 101, 2),
        order("own", 100, 2, 1, 102, 7),
    ]
    result = replay_commands(commands)
    assert [(f.price, f.volume) for f in result.events[-1].fills] == [(101, 2), (102, 3)]
    assert result.events[-1].bids == ((102, 2),)
    assert result.events[0].asks == ((101, 2),)


def test_response_delivery_can_reorder_but_never_change_exchange_state():
    commands = [order("a", 100, 0, 1, 100, 2, response=200), order("b", 200, 1, -1, 100, 1)]
    result = replay_commands(commands)
    assert [r.event_id for r in result.reports] == ["b", "a"]
    assert [r.effective_ns for r in result.reports] == [200, 100]
    assert result.events[-1].bids == ((100, 1),)
    assert result.reports[-1].event.bids == ((100, 2),)


def test_cancel_before_order_and_partial_cancel_preserve_quantity():
    commands = [
        order("a", 100, 1, 1, 100, 5, delay=100),
        Command("early", "cancel", 110, 0, 0, 0, "a"),
        Command("part", "cancel", 250, 0, 0, 2, "a", quantity=2),
    ]
    result = replay_commands(commands)
    assert result.events[0].status == "not_resting"
    assert result.events[-1].bids == ((100, 3),)
    assert result.events[-1].cancelled_quantity == 2


@pytest.mark.parametrize(
    "change",
    [
        {"latency_ns": -1},
        {"response_ns": True},
        {"send_ns": 2**63},
        {"kind": "market"},
        {"side": 0},
        {"quantity": 0},
        {"price": 0},
        {"order_id": ""},
        {"sequence": -1},
        {"send_ns": 2**63 - 1, "latency_ns": 1},
    ],
)
def test_invalid_requests_fail(change):
    from dataclasses import replace

    with pytest.raises(ValueError):
        replay_commands([replace(order("a", 100, 0, 1, 100, 1), **change)])


def test_duplicate_id_tie_and_budget_rejected():
    with pytest.raises(ValueError):
        replay_commands([order("a", 100, 0, 1, 100, 1), order("a", 200, 1, 1, 100, 1)])
    with pytest.raises(ValueError):
        replay_commands([order("a", 100, 0, 1, 100, 1), order("b", 100, 0, -1, 100, 1)])
    with pytest.raises(ValueError):
        replay_commands(scenario(1), max_commands=2)


def test_overcancel_and_large_clock_preserve_exact_state():
    base = 2**53 + 123
    commands = [
        order("a", base, 0, 1, 100, 5, response=20),
        Command("bad-cancel", "cancel", base + 1, 0, 0, 1, "a", quantity=6),
    ]
    result = replay_commands(commands)
    assert result.events[-1].status == "cancel_rejected"
    assert result.events[-1].queue == (("a", 1, 100, 5),)
    assert result.events[0].effective_ns == base
    assert result.reports[-1].delivered_ns == base + 20
    with pytest.raises(ValueError):
        replay_commands([], max_commands=1001)
