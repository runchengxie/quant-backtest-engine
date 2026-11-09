"""Literal first-action economics through the public source-bound session facade."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from quant_backtest_engine.product import parse_manifest, result_to_json
from test_impact_planning import request

from quant_backtest_core import BackendContext
from quant_backtest_core.planning.impact_planning import plan_with_impact
from quant_backtest_core.sessions import open_session, restore_session

ROOT = Path(__file__).resolve().parents[2]


def test_public_full_session_restore_then_replan_uses_delivered_state(tmp_path):
    wire = json.loads((ROOT / "fixtures/product/minute-session.json").read_text())
    wire["required_capabilities"] = ["session_ledger", "checkpoint", "restore", "linear_impact"]
    wire["model_versions"] = {"linear-impact": "v1"}
    wire["inline_inputs"]["targets"] = wire["inline_inputs"]["targets"][:1]
    wire["inline_inputs"]["bars"] = wire["inline_inputs"]["bars"][:3]
    wire["tapes"] = {key: [] for key in wire["tapes"]}
    for key in ("buy_fee_bp", "sell_fee_bp", "commission_minimum_cny", "sell_tax_bp"):
        wire["settings"]["config"][key] = "0"
    wire["settings"]["report_delay_seconds"] = "0"
    wire["settings"]["impact"] = {"transient": "0.001", "permanent": "0", "decay_seconds": "10"}
    calendar = json.dumps(
        {"schema": "synthetic-calendar.v1", "timezone": "Asia/Shanghai", "sessions": ["2026-01-05"]}
    ).encode()
    (tmp_path / "minute-calendar.json").write_bytes(calendar)
    wire["calendar"]["sha256"] = hashlib.sha256(calendar).hexdigest()
    clock = int(wire["inline_inputs"]["targets"][0]["decision_time"])
    req = request(
        initial_cash=10000,
        transient=np.array([0.001]),
        capacity=np.array([[100.0]]),
        risk_aversion=0,
        decision_ns=clock,
        forecast_available_ns=clock,
        risk_available_ns=clock,
        state_available_ns=clock,
    )
    first = plan_with_impact(req)
    # This hand solution saturates exactly one whole lot; no arbitrary rounding adapter.
    assert first.first_action == (100.0,)
    assert first.first_action[0] % 100 == 0
    wire["inline_inputs"]["targets"][0]["weight"] = str(first.first_action[0] * 10 / 10000)
    manifest = parse_manifest(wire)
    session = open_session(manifest, context=BackendContext(tmp_path, tmp_path / "original"))
    while not session.owner.simulation.fills:
        assert session.step() is not None
    assert session.owner.cursor < len(session.owner.simulation.times)
    observation = session.observe()
    assert observation.as_of_ns == "1767576720000000000"
    assert observation.account["cash"] == "8995.0"
    assert dict(observation.account["holdings"]) == {"A": "100"}
    assert observation.reports == ()
    assert session.owner.queue == []
    # Preserve raw binary multiplication evidence; hand notional is CNY 1005.
    fill = session.owner.simulation.fills[0]
    assert (fill["quantity"], fill["price"], fill["gross_amount"], fill["transaction_cost"]) == (
        100,
        10.05,
        1005.0000000000001,
        0,
    )
    assert len(session.owner.simulation.orders) == 1
    checkpoint = session.checkpoint()
    state = json.loads(checkpoint)
    assert state["owner_state"]["impact"]["states"]["A"]["transient"] == 0.1
    restored = restore_session(
        manifest, checkpoint, context=BackendContext(tmp_path, tmp_path / "restored")
    )
    assert restored.checkpoint() == checkpoint
    assert restored.observe() == observation
    assert restored.owner.checkpoint() == session.owner.checkpoint()
    assert restored.owner.cursor == session.owner.cursor
    assert restored.owner.simulation.orders == session.owner.simulation.orders
    assert restored.owner.simulation.fills == session.owner.simulation.fills
    assert restored.owner.queue == session.owner.queue == []
    before = restored.checkpoint()
    second = plan_with_impact(
        replace(
            req,
            initial_holdings=np.array([float(restored.observe().account["holdings"]["A"])]),
            initial_cash=float(restored.observe().account["cash"]),
            initial_transient=np.array(
                [restored.owner.simulation.impact_model.checkpoint()["states"]["A"]["transient"]]
            ),
            decision_ns=int(observation.as_of_ns),
            state_available_ns=int(observation.as_of_ns),
        )
    )
    assert second.first_action == (99.99999999999999,)
    assert second.execution_prices[0] == (10.15,)
    assert second.cash == (7980.0,)
    assert second.transient_after == ((0.2,),)
    assert restored.checkpoint() == before  # A contingent candidate does not deliver money/shares.
    assert restored.observe().account["cash"] == "8995.0"
    original_result, restored_result = session.finish(), restored.finish()
    assert result_to_json(original_result) == result_to_json(restored_result)
    raw = json.loads((tmp_path / "restored" / restored_result.raw_result.uri).read_text())
    assert len(raw["fills"]) == len(raw["orders"]) == 1
    assert raw["fills"][0]["quantity"] == "100"
    assert raw["daily"][-1]["cash"] == "8995.0"


def test_contingent_signed_cash_never_funds_a_blocked_actual_sale():
    from test_discrete_inventory import minute_result

    req = request(
        initial_cash=0,
        initial_holdings=np.array([10.0, 0.0]),
        unaffected_prices=np.array([10.0, 10.0]),
        expected_returns=np.array([[-1.0, 1.0]]),
        covariances=np.zeros((1, 2, 2)),
        initial_transient=np.zeros(2),
        transient=np.zeros(2),
        decay_seconds=np.ones(2),
        capacity=np.array([[10.0, 10.0]]),
        risk_aversion=0,
    )
    projected = plan_with_impact(req)
    assert projected.first_action == pytest.approx((-10, 10), abs=1e-6)
    assert projected.holdings[0] == pytest.approx((0, 10), abs=1e-6)
    actual = minute_result(
        (("2026-01-05", (1, 0)), ("2026-01-06", (0, 1))),
        prices=(10, 10),
        cash=100,
        sale_fills=False,
        restore_before_exit=True,
    )
    assert actual.fills.side.tolist() == ["buy"]
    assert actual.fills.quantity.tolist() == [10]
    assert actual.daily.iloc[-1].cash == 0
    assert actual.daily.iloc[-1].positions_value == 100
    # Replan from actual delivered balance, retaining A and no available sale capacity.
    replanned = plan_with_impact(
        replace(req, initial_cash=actual.daily.iloc[-1].cash, capacity=np.array([[0.0, 10.0]]))
    )
    assert replanned.first_action == (0.0, 0.0)
    assert replanned.cash == (0.0,)


def test_only_a_sale_blocked_b_remains_tradable_and_funded_control_buys():
    """Supplementary whole-B cash gate; retain the original shared-zero-volume fixture."""
    import pandas as pd
    from test_minute_execution import bars
    from test_minute_session import Policy

    from quant_backtest_core.backtest.minute import MinuteExecutionConfig
    from quant_backtest_core.backtest.minute_session import MinuteSession

    results = []
    for initial_cash in (100, 200):
        # Both accounts first own 10 A; only the control retains CNY 100 cash.
        weights = ((100 / initial_cash, 0), (0, 100 / initial_cash))
        targets = pd.DataFrame(
            [
                {
                    "decision_time": pd.Timestamp(day + " 09:29", tz="Asia/Shanghai"),
                    "entry_time": pd.Timestamp(day + " 09:30", tz="Asia/Shanghai"),
                    "symbol": symbol,
                    "weight": weight,
                }
                for day, group in zip(("2026-01-05", "2026-01-06"), weights, strict=True)
                for symbol, weight in zip(("AAA", "BBB"), group, strict=True)
            ]
        )
        frames = []
        for day in ("2026-01-05", "2026-01-06"):
            for symbol in ("AAA", "BBB"):
                frame = bars((day + " 09:29", day + " 09:32"), price=10, volume=1000)
                frame["symbol"] = symbol
                if day == "2026-01-06" and symbol == "AAA":
                    frame["tradable"] = False
                frames.append(frame)
        market = pd.concat(frames, ignore_index=True)
        active_b = market[
            (market.symbol == "BBB") & (market.time.dt.date.astype(str) == "2026-01-06")
        ]
        assert active_b.tradable.all() and (active_b.volume == 1000).all()
        result = MinuteSession(
            targets,
            market,
            MinuteExecutionConfig(initial_cash, 1, 0, 0, lot_size=1),
            policy=Policy(),
        ).run()
        results.append(result)
    blocked, funded = results
    assert blocked.fills.symbol.tolist() == ["AAA"]
    assert blocked.fills.quantity.tolist() == [10]
    assert blocked.daily.iloc[-1].cash == 0
    assert blocked.daily.iloc[-1].positions_value == 100
    assert not ((blocked.fills.symbol == "BBB") & (blocked.fills.side == "buy")).any()
    assert funded.fills.symbol.tolist() == ["AAA", "BBB"]
    assert funded.fills.side.tolist() == ["buy", "buy"]
    assert funded.fills.quantity.tolist() == [10, 10]
    assert funded.daily.iloc[-1].cash == 0
    assert funded.daily.iloc[-1].positions_value == 200
    assert not (funded.fills.side == "sell").any()
