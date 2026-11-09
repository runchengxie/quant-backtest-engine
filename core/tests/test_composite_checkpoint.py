from copy import deepcopy
from dataclasses import replace

import pandas as pd
import pytest
from test_account_events import inputs

from quant_backtest_core.backtest.account_events import (
    AccountEvent,
    AccountEventAdapter,
    EventAccountConfig,
)
from quant_backtest_core.backtest.checkpoints import ExecutionState
from quant_backtest_core.backtest.impact import LinearImpact
from quant_backtest_core.backtest.paper_account import PaperState


def state():
    at = pd.Timestamp("2025-01-01T00:00:00Z")
    config = EventAccountConfig("source-v1", "input-v1")
    account = AccountEventAdapter(PaperState(at, 10000, {}, {"A": 10}), config)
    account.admit_order("buy", "A", 100, 11, as_of=at, locate_quantity=0, risk_limit=10000)
    return ExecutionState(
        account, LinearImpact(permanent=0.001), seed=7, policy_state={"planned": {"A": 0.1}}
    ), at


def test_hidden_fill_and_impact_recover_exactly_once():
    live, at = state()
    fill = AccountEvent(
        "f",
        "fill",
        at,
        at + pd.Timedelta(seconds=2),
        {
            "order_id": "buy",
            "quantity": 40,
            "price": 10,
            "inputs": inputs(),
            "fill_id": "physical-f",
        },
    )
    live.apply_fill(fill)
    restored = ExecutionState.restore(live.checkpoint(), live.account.config)
    assert restored.account.visible.quantities == {}
    assert restored.account.actual.quantities == {"A": 40}
    restored.apply_fill(fill)
    restored.apply_fill(
        replace(fill, event_id="duplicate-report", available_at=at + pd.Timedelta(seconds=3))
    )
    live.account.deliver(at + pd.Timedelta(seconds=2))
    restored.account.deliver(at + pd.Timedelta(seconds=2))
    assert restored.checkpoint() == live.checkpoint()
    assert restored.impact.offset("A", at.timestamp()) == pytest.approx(0.04)
    assert restored.policy_state == {"planned": {"A": 0.1}}


def test_checkpoint_tamper_and_failed_fill_are_atomic():
    live, at = state()
    before = live.checkpoint()
    bad = AccountEvent(
        "bad", "fill", at, at, {"order_id": "buy", "quantity": 101, "price": 10, "inputs": inputs()}
    )
    with pytest.raises(ValueError):
        live.apply_fill(bad)
    assert live.checkpoint() == before
    changed = deepcopy(before)
    changed["cursor"] = 9
    with pytest.raises(ValueError, match="digest"):
        ExecutionState.restore(changed, live.account.config)


def test_cancel_race_replay_at_every_boundary_preserves_policy_and_reservations():
    def replay_step(current, number):
        at = pd.Timestamp("2025-01-01T00:00:00Z")
        if number in (0, 2):
            seconds, quantity = (0, 40) if number == 0 else (2, 20)
            event = AccountEvent(
                f"f-{number}",
                "fill",
                at + pd.Timedelta(seconds=seconds),
                at + pd.Timedelta(seconds=5 if number == 0 else 6),
                {"order_id": "buy", "quantity": quantity, "price": 10, "inputs": inputs(seconds)},
            )
            current.apply_fill(event)
        elif number == 1:
            current.account.request_cancel("buy", as_of=at + pd.Timedelta(seconds=1))
        elif number == 3:
            current.account.apply(
                AccountEvent(
                    "ack",
                    "cancel_ack",
                    at + pd.Timedelta(seconds=3),
                    at + pd.Timedelta(seconds=4),
                    {"order_id": "buy"},
                )
            )
        else:
            current.account.deliver(at + pd.Timedelta(seconds=number))
            current.policy_state.setdefault("trace", []).append(
                dict(current.account.visible.quantities)
            )
        current.cursor += 1

    full, _ = state()
    for n in range(7):
        replay_step(full, n)
    for cursor in range(8):
        resumed, _ = state()
        for n in range(cursor):
            replay_step(resumed, n)
        resumed = ExecutionState.restore(resumed.checkpoint(), resumed.account.config)
        for n in range(resumed.cursor, 7):
            replay_step(resumed, n)
        assert resumed.checkpoint() == full.checkpoint()
    assert full.policy_state["trace"] == [{}, {"A": 40}, {"A": 60}]


def test_impact_price_limit_failure_keeps_both_owners_unchanged():
    live, at = state()
    live.impact = LinearImpact(permanent=0.1)
    before = live.checkpoint()
    event = AccountEvent(
        "limit",
        "fill",
        at,
        at,
        {"order_id": "buy", "quantity": 40, "price": 10, "inputs": inputs()},
    )
    with pytest.raises(ValueError, match="limit"):
        live.apply_fill(event)
    assert live.checkpoint() == before


@pytest.mark.parametrize("binding", ["source_binding", "input_binding"])
def test_changed_execution_binding_rejects_restore(binding):
    live, _ = state()
    with pytest.raises(ValueError, match="source/input mismatch"):
        ExecutionState.restore(
            live.checkpoint(), replace(live.account.config, **{binding: "changed"})
        )


def test_original_platform_schema_rejects_without_converter():
    import hashlib
    import json

    live, _ = state()
    old = live.checkpoint()
    old.pop("digest")
    old["schema"] = "execution-state.v1"
    old["account"].pop("digest")
    old["account"]["schema"] = 1
    old["account"]["digest"] = hashlib.sha256(
        json.dumps(old["account"], sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    old["digest"] = hashlib.sha256(
        json.dumps(old, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    with pytest.raises(ValueError, match="schema"):
        ExecutionState.restore(old, live.account.config)
    with pytest.raises(ValueError, match="schema"):
        AccountEventAdapter.restore(old["account"], live.account.config)
