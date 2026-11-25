"""Independent hand-calculated owner-table audit fixtures."""

from types import SimpleNamespace

import pandas as pd
import pytest

from quant_backtest_core.backtest.minute import MinuteExecutionConfig
from quant_backtest_core.planning.owner_control_audit import audit_owner_tables


def example():
    t = pd.Timestamp("2025-01-02 09:32", tz="Asia/Shanghai")
    u = pd.Timestamp("2025-01-03 09:31", tz="Asia/Shanghai")
    bars = pd.DataFrame(
        [
            {
                "time": x,
                "interval_start": x - pd.Timedelta(seconds=30),
                "symbol": "A",
                "volume": 1000.0,
                "close": 10.0,
            }
            for x in (t, u)
        ]
    )
    orders = pd.DataFrame(
        [
            {
                "order_id": i,
                "symbol": "A",
                "side": s,
                "entry_time": x - pd.Timedelta(minutes=1),
                "deadline": x + pd.Timedelta(minutes=1),
                "quantity": 10,
                "filled_quantity": 10,
                "commission_paid": fee,
                "tax_paid": tax,
                "status": "filled",
            }
            for i, s, x, fee, tax in [(0, "buy", t, 0.03, 0.0), (1, "sell", u, 0.0297, 0.0495)]
        ]
    )
    fills = pd.DataFrame(
        [
            {
                "order_id": 0,
                "time": t,
                "symbol": "A",
                "side": "buy",
                "quantity": 10,
                "price": 10.0,
                "gross_amount": 100.0,
                "commission": 0.03,
                "sell_tax": 0.0,
                "transaction_cost": 0.03,
            },
            {
                "order_id": 1,
                "time": u,
                "symbol": "A",
                "side": "sell",
                "quantity": 10,
                "price": 9.9,
                "gross_amount": 99.0,
                "commission": 0.0297,
                "sell_tax": 0.0495,
                "transaction_cost": 0.0792,
            },
        ]
    )
    daily = pd.DataFrame(
        [
            {
                "date": t.date(),
                "cash": 99.97,
                "positions_value": 100.0,
                "nav": 199.97,
                "transaction_cost": 0.03,
                "cash_receivable": 0.0,
                "stock_receivable_value": 0.0,
            },
            {
                "date": u.date(),
                "cash": 198.8908,
                "positions_value": 0.0,
                "nav": 198.8908,
                "transaction_cost": 0.1092,
                "cash_receivable": 0.0,
                "stock_receivable_value": 0.0,
            },
        ]
    )
    holdings = pd.DataFrame([{"date": t.date(), "symbol": "A", "quantity": 10}])
    result = SimpleNamespace(
        orders=orders,
        fills=fills,
        daily=daily,
        holdings=holdings,
        summary={"financial_reports_pending": 0},
    )
    config = MinuteExecutionConfig(
        200.0, 1.0, 3.0, 8.0, lot_size=1, latency_minutes=0, sell_tax_bp=5.0
    )
    return result, bars, config, u - pd.Timedelta(minutes=2)


def test_hand_shortfall_and_fees_not_double_charged():
    result, bars, config, start = example()
    metric = audit_owner_tables(result, bars, config, quantity=10, exit_start=start)
    assert metric["exit_price_shortfall_cny"] == pytest.approx(1.0)
    assert metric["exit_fees_cny"] == pytest.approx(0.0792)
    assert metric["exit_cost_cny"] == pytest.approx(1.0792)
    assert metric["exit_cost_bp_on_target"] == pytest.approx(107.92)
    assert metric["owner_final_cash"] == pytest.approx(198.8908)
    assert metric["completed"] and metric["rankable"]


@pytest.mark.parametrize(
    ("table", "column", "value", "match"),
    [
        ("fills", "transaction_cost", 0.0, "fee"),
        ("fills", "gross_amount", 100.0, "notional"),
        ("daily", "cash", 100.0, "cash"),
        ("orders", "filled_quantity", 9, "quantity"),
        ("fills", "quantity", 20, "quantity|participation|notional"),
    ],
)
def test_corrupt_financial_tables_rejected(table, column, value, match):
    result, bars, config, start = example()
    getattr(result, table).loc[1, column] = value
    with pytest.raises(ValueError, match=match):
        audit_owner_tables(result, bars, config, quantity=10, exit_start=start)


def test_partial_zero_exit_is_not_rankable_or_free_full_liquidation():
    result, bars, config, start = example()
    result.fills = result.fills.iloc[:1].copy()
    result.orders = result.orders.iloc[:1].copy()
    result.daily.loc[1, ["cash", "positions_value", "nav", "transaction_cost"]] = [
        99.97,
        100.0,
        199.97,
        0.03,
    ]
    result.holdings = pd.concat(
        [result.holdings, result.holdings.assign(date=result.daily.date.iloc[-1])],
        ignore_index=True,
    )
    metric = audit_owner_tables(result, bars, config, quantity=10, exit_start=start)
    assert not metric["completed"] and not metric["rankable"]
    assert metric["residual_quantity"] == 10
    assert metric["exit_cost_bp_on_filled"] is None


def test_per_bar_capacity_and_pending_reports_remain_distinct():
    result, bars, config, start = example()
    bars.loc[1, "volume"] = 5
    with pytest.raises(ValueError, match="participation"):
        audit_owner_tables(result, bars, config, quantity=10, exit_start=start)
    bars.loc[1, "volume"] = 1000
    result.summary["financial_reports_pending"] = 1
    metric = audit_owner_tables(result, bars, config, quantity=10, exit_start=start)
    assert metric["completed"] and not metric["rankable"]


def test_daily_cost_is_cumulative_not_a_flow_to_sum():
    result, bars, config, start = example()
    result.daily.loc[1, "transaction_cost"] = 0.0792
    with pytest.raises(ValueError, match="cumulative.*fee"):
        audit_owner_tables(result, bars, config, quantity=10, exit_start=start)


@pytest.mark.parametrize(
    ("column", "value", "match"),
    [("cash", 1.0, "cash"), ("nav", 1.0, "equity"), ("positions_value", 1.0, "mark")],
)
def test_intermediate_owner_days_are_also_reconciled(column, value, match):
    result, bars, config, start = example()
    result.daily.loc[0, column] = value
    with pytest.raises(ValueError, match=match):
        audit_owner_tables(result, bars, config, quantity=10, exit_start=start)
