"""Literal financial oracles, independent of implementation formulas."""

from dataclasses import asdict
from decimal import Decimal

from quant_backtest_core.backtest.costs import CostModel, CostQuote
from quant_backtest_core.backtest.impact_scenarios import linear_impact_scenario
from quant_backtest_core.evidence.execution_integrity import (
    compare_prefixes,
    exit_wealth,
    fill_prefixes,
)


def test_impact_in_price_and_cash_fee_each_count_once():
    result = linear_impact_scenario(
        [4, -4], unaffected_price=100, permanent=0.5, temporary=0.1, fee_per_share=0.25
    )
    assert [row.execution_price for row in result.fills] == [101.4, 100.6]
    assert [row.fee for row in result.fills] == [1, 1]
    assert round(result.cash_change, 8) == -5.2
    fills = [
        dict(fill_id="buy", ts_ns=10, symbol="A", side="buy", quantity="4", price="101.4", fee="1"),
        dict(
            fill_id="sell", ts_ns=20, symbol="A", side="sell", quantity="4", price="100.6", fee="1"
        ),
    ]
    assert fill_prefixes(fills, "1000") == [
        dict(ts_ns=0, cash=Decimal("1000"), quantities={}),
        dict(ts_ns=10, cash=Decimal("593.4"), quantities={"A": Decimal("4")}),
        dict(ts_ns=20, cash=Decimal("994.8"), quantities={}),
    ]


def test_equal_endpoint_divergent_prefix_rejected():
    left = [
        dict(ts_ns=0, cash=Decimal("1000"), quantities={}),
        dict(ts_ns=10, cash=Decimal("900"), quantities={"A": Decimal("1")}),
        dict(ts_ns=20, cash=Decimal("1005"), quantities={}),
    ]
    right = [
        dict(ts_ns=0, cash=Decimal("1000"), quantities={}),
        dict(ts_ns=10, cash=Decimal("899"), quantities={"A": Decimal("1")}),
        dict(ts_ns=20, cash=Decimal("1005"), quantities={}),
    ]
    assert compare_prefixes(left, right) == [{"ts_ns": 10, "left": left[1], "right": right[1]}]


def test_stale_mark_wealth_unknown():
    result = exit_wealth(
        "40",
        {"A": 3},
        {"A": {"price": "20", "ts_ns": 89}},
        as_of_ns=100,
        max_mark_age_ns=10,
        receivable="2",
    )
    assert result["cash"] == Decimal("40")
    assert result["receivable"] == Decimal("2")
    assert result["marked_wealth"] is None
    assert result["cash_realized_wealth"] is None
    assert result["unpriced_symbols"] == ["A"]


def test_cost_quote_retains_exact_transport_and_owner_identity():
    quote = CostQuote(
        currency="CNY",
        side="buy",
        effective_ns="1767225600000000001",
        quantity="4",
        notional="405.6",
        commission="1",
        tax="0",
        total="1",
        model_id="original-owner:synthetic-v1",
        rounding="owner-half-up-cent",
    )
    assert asdict(quote) == dict(
        currency="CNY",
        side="buy",
        effective_ns="1767225600000000001",
        quantity="4",
        notional="405.6",
        commission="1",
        tax="0",
        total="1",
        model_id="original-owner:synthetic-v1",
        rounding="owner-half-up-cent",
    )
    assert CostModel.quote.__annotations__["return"] in ("CostQuote", CostQuote)
