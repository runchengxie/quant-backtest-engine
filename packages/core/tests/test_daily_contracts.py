import importlib
import inspect
import typing
from dataclasses import replace
from datetime import UTC, datetime

import pandas as pd
import pytest
from quant_backtest_engine.product.types import ClockSet

from quant_backtest_core._minute.corporate_actions import (
    CorporateAction,
    normalize_corporate_actions,
)
from quant_backtest_core.daily.contracts import (
    DailyDecisionTiming,
    DailyInputLayout,
    DailyReplayRequest,
    ExecutionCalendar,
    utc_ns,
)
from quant_backtest_core.daily.execution_sim.config import (
    ExecutionSimConfig,
    build_execution_sim_config,
)


def request():
    return DailyReplayRequest(
        pd.DataFrame(
            {
                "rebalance_date": ["2026-01-02", "2026-01-05"],
                "symbol": ["A", "A"],
                "target_weight": [1.0, 0.5],
            }
        ),
        pd.DataFrame(
            {
                "trade_date": ["2026-01-02"],
                "symbol": ["A"],
                "odd_price": [10.0],
                "liquid": [100.0],
                "can_buy": [True],
            }
        ),
        ExecutionCalendar.from_dates("UTC", ("2026-01-02", "2026-01-05")),
        {d: ClockSet(None, "1", "2", "4", None, None, "10") for d in ("2026-01-02", "2026-01-05")},
        ExecutionSimConfig(enabled=True, liquidity_cols=("liquid",)),
        "capacity",
        "raw",
        (),
        layout=DailyInputLayout(
            "odd_price",
            "odd_price",
            None,
            "can_buy",
            None,
            "CNY",
            "raw_share",
            "CNY/raw_share",
            {"liquid": "CNY"},
        ),
        decision_timing={},
    )


def test_selectors_sparse_targets_and_action_boundary():
    r = request()
    assert r.legacy_corporate_actions() is None
    assert (
        replace(
            r,
            price_basis="adjusted",
            layout=replace(
                r.layout, quantity_unit="adjusted_share", price_unit="CNY/adjusted_share"
            ),
        ).legacy_corporate_actions()
        is None
    )
    assert normalize_corporate_actions((), "raw") == ()
    with pytest.raises(ValueError):
        normalize_corporate_actions((), "adjusted")
    event = CorporateAction("d", "A", "2026-01-01", "2026-01-02", "2026-01-05", 1.0, "2026-01-05")
    assert replace(r, corporate_actions=(event,)).legacy_corporate_actions()[0] is event
    with pytest.raises(ValueError):
        replace(r, price_basis="adjusted", corporate_actions=(event,))


def test_layout_and_enabled_rule_inputs():
    r = request()
    for layout in (
        replace(r.layout, price_col="missing", mark_price_col="missing"),
        replace(r.layout, buy_tradable_col="missing"),
        replace(r.layout, liquidity_units={}),
        replace(r.layout, quantity_unit="lots"),
    ):
        with pytest.raises(ValueError):
            replace(r, layout=layout)
    with pytest.raises(ValueError):
        replace(r.layout, mark_price_col="different")
    for cfg in (
        replace(r.config, enforce_price_limits=True),
        replace(r.config, enforce_listing_status=True),
        replace(
            r.config, limit_up_col="missing", limit_down_col="missing", enforce_price_limits=True
        ),
    ):
        with pytest.raises(ValueError):
            replace(r, config=cfg)


def test_rebalance_coverage_and_causality():
    r = request()
    with pytest.raises(ValueError):
        replace(r, decision_clocks={})
    for clock in (
        ClockSet(None, "3", "2", "4", None, None, "10"),
        ClockSet("3", "1", "2", "4", None, None, "10"),
        ClockSet(None, "1", "2", None, None, None, "10"),
    ):
        with pytest.raises(ValueError):
            replace(r, decision_clocks={d: clock for d in r.decision_clocks})
    with pytest.raises(ValueError):
        replace(
            r, decision_timing={"20260102": DailyDecisionTiming(None, None, None, None, None, None)}
        )


def test_timing_overlap_and_exact_ns():
    r = request()
    timing = DailyDecisionTiming("1", "4", "3", "8", "policy", "calendar")
    assert timing.entry_ns == "4"
    replace(r, decision_timing={d: timing for d in r.decision_clocks})
    assert DailyDecisionTiming(None, None, None, None, None, None).entry_ns is None
    assert DailyDecisionTiming(None, "4", None, None, None, None).entry_ns == "4"
    assert DailyDecisionTiming(None, None, "3", "8", None, None).entry_ns == "3"
    for values in (("1", "9", "3", "8", "p", "c"), ("1", None, "3", None, "p", "c")):
        with pytest.raises(ValueError):
            DailyDecisionTiming(*values)
    with pytest.raises(ValueError):
        replace(r, decision_timing={d: replace(timing, signal_ns="3") for d in r.decision_clocks})
    assert utc_ns(datetime(2026, 1, 2, 0, 0, 0, 123456, tzinfo=UTC)) == "1767312000123456000"
    assert utc_ns(pd.Timestamp("2026-01-02T00:00:00.123456789Z")) == "1767312000123456789"
    with pytest.raises(ValueError):
        utc_ns(datetime(2026, 1, 2))


def test_config_and_type_hints_without_runner():
    cfg = build_execution_sim_config(
        {
            "enabled": True,
            "participation": 0.2,
            "liquidity_col": "x",
            "sell_max_days": "next_rebalance",
            "cap_daily_amount": False,
            "round_lot": 10,
        }
    )
    assert cfg.liquidity_cols == ("x",)
    assert cfg.sell_max_days == "until_next_rebalance"
    assert cfg.participation_rate == 0.2
    for module in ("contracts", "calendar", "summary", "execution_sim.config"):
        m = importlib.import_module("quant_backtest_core.daily." + module)
        for value in vars(m).values():
            if (
                inspect.isclass(value) or inspect.isfunction(value)
            ) and value.__module__ == m.__name__:
                typing.get_type_hints(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("signal_ns", "0"),
        ("signal_ns", "3"),
        ("earliest_order_ns", "1"),
        ("execution_window_start_ns", "1"),
        ("execution_window_end_ns", "11"),
    ],
)
def test_source_timing_constraints_are_preserved(field, value):
    r = request()
    timing = DailyDecisionTiming("1", "4", "3", "8", "policy", "calendar")
    with pytest.raises(ValueError):
        bad = replace(timing, **{field: value})
        replace(r, decision_timing={day: bad for day in r.decision_clocks})


def test_clock_valuation_constraint_and_unavailable_metadata():
    r = request()
    timing = DailyDecisionTiming("1", "4", "3", "8", None, None)
    with pytest.raises(ValueError):
        replace(
            r,
            decision_clocks={
                day: replace(clock, valuation_ns="1") for day, clock in r.decision_clocks.items()
            },
            decision_timing={day: timing for day in r.decision_clocks},
        )
    # Effective/report are independent; no invented total ordering.
    replace(
        r,
        decision_clocks={
            day: replace(clock, effective_ns="0", report_ns="0")
            for day, clock in r.decision_clocks.items()
        },
    )
    with pytest.raises(TypeError):
        r.decision_clocks["2026-01-02"] = next(iter(r.decision_clocks.values()))
    with pytest.raises(TypeError):
        r.layout.liquidity_units["liquid"] = "USD"


def test_explicit_liquidity_multiplier_and_units():
    r = request()
    replace(
        r,
        config=replace(r.config, liquidity_notional_multiplier=1000),
        layout=replace(r.layout, liquidity_units={"liquid": "1000 CNY"}),
    )
    with pytest.raises(ValueError):
        replace(r, config=replace(r.config, liquidity_notional_multiplier=1000))
