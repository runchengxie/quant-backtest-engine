"""Synthetic tests for date-aware execution fees and ledger accounting."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import date

import pandas as pd
import pytest

from quant_backtest_core.daily.dated_fees import (
    DatedFeeSchedule,
    DatedTradeFeeModel,
    FeeQuoteContext,
    FeeSchedulePeriod,
)
from quant_backtest_core.daily.execution_sim import (
    ExecutionSimConfig,
    simulate_execution_adjusted_nav,
    simulate_ideal_daily_nav,
)


def _period(
    start: str = "2020-01-01",
    end: str = "2020-02-01",
    *,
    market: str = "SYNTH-X",
    sell_stamp_bps: float = 10.0,
) -> FeeSchedulePeriod:
    return FeeSchedulePeriod(
        start_date=start,
        end_date=end,
        market=market,
        buy_commission_bps=2.0,
        sell_commission_bps=2.0,
        minimum_commission=5.0,
        sell_stamp_bps=sell_stamp_bps,
        transfer_bps=0.1,
        buy_spread_bps=0.0,
        sell_spread_bps=0.0,
    )


def _model(*periods: FeeSchedulePeriod) -> DatedTradeFeeModel:
    return DatedTradeFeeModel(
        schedule=DatedFeeSchedule(periods=periods or (_period(),)),
        symbol_markets={"AAA": "SYNTH-X"},
    )


def _quote(
    model: DatedTradeFeeModel,
    *,
    trade_date: str = "2020-01-15",
    side: str = "sell",
    market: str = "SYNTH-X",
    executed_notional: float = 1_000.0,
    cumulative_group_notional: float = 0.0,
):
    return model.quote(
        FeeQuoteContext(
            trade_date=trade_date,
            side=side,
            symbol="AAA",
            market=market,
            executed_notional=executed_notional,
            cumulative_group_notional=cumulative_group_notional,
        )
    )


def test_sell_quote_returns_hand_derived_components():
    quote = _quote(_model())

    assert quote.commission == pytest.approx(5.0)
    assert quote.stamp_tax == pytest.approx(1.0)
    assert quote.transfer_fee == pytest.approx(0.01)
    assert quote.spread_cost == pytest.approx(0.0)
    assert quote.total_cost == pytest.approx(6.01)


def test_commission_minimum_accrues_once_per_group():
    model = _model()

    first = _quote(model, side="buy")
    second = _quote(model, side="buy", cumulative_group_notional=1_000.0)
    threshold = _quote(
        model,
        side="buy",
        executed_notional=28_000.0,
        cumulative_group_notional=2_000.0,
    )

    assert first.commission == pytest.approx(5.0)
    assert second.commission == pytest.approx(0.0)
    assert threshold.commission == pytest.approx(1.0)
    assert first.commission + second.commission + threshold.commission == pytest.approx(6.0)


def test_cumulative_notional_of_30000_has_total_commission_of_6():
    quote = _quote(_model(), side="buy", executed_notional=30_000.0)

    assert quote.commission == pytest.approx(6.0)


def test_zero_fill_never_incurs_minimum_commission():
    quote = _quote(_model(), side="buy", executed_notional=0.0)

    assert quote.total_cost == 0.0


def test_schedule_uses_inclusive_start_and_exclusive_end_boundaries():
    model = _model(
        _period("2020-01-01", "2020-01-10", sell_stamp_bps=10.0),
        _period("2020-01-10", "2020-02-01", sell_stamp_bps=5.0),
    )

    before = _quote(model, trade_date="2020-01-09")
    boundary = _quote(model, trade_date="2020-01-10")

    assert before.stamp_tax == pytest.approx(1.0)
    assert boundary.stamp_tax == pytest.approx(0.5)
    assert before.period_start == date(2020, 1, 1)
    assert boundary.period_start == date(2020, 1, 10)


def test_missing_date_coverage_fails_closed():
    model = _model(_period("2020-01-01", "2020-01-10"))

    with pytest.raises(ValueError, match="no fee period"):
        _quote(model, trade_date="2020-01-10")


def test_market_identity_must_match_symbol_mapping():
    model = _model()

    with pytest.raises(ValueError, match="market mismatch"):
        _quote(model, market="SYNTH-Y")


def test_missing_symbol_market_mapping_fails_closed():
    model = DatedTradeFeeModel(
        schedule=DatedFeeSchedule(periods=(_period(),)),
        symbol_markets={},
    )

    with pytest.raises(ValueError, match="missing market mapping"):
        _quote(model)


def test_overlapping_periods_for_the_same_market_are_rejected():
    with pytest.raises(ValueError, match="overlapping fee periods"):
        DatedFeeSchedule(
            periods=(
                _period("2020-01-01", "2020-01-20"),
                _period("2020-01-10", "2020-02-01"),
            )
        )


@pytest.mark.parametrize("side", ["", "hold", "BUY "])
def test_invalid_side_is_rejected(side: str):
    with pytest.raises(ValueError, match="side"):
        _quote(_model(), side=side)


@pytest.mark.parametrize("field", ["executed_notional", "cumulative_group_notional"])
@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_quote_amount_is_rejected(field: str, value: float):
    kwargs = {field: value}

    with pytest.raises(ValueError, match=field):
        _quote(_model(), **kwargs)


@pytest.mark.parametrize(
    "field",
    [
        "buy_commission_bps",
        "sell_commission_bps",
        "minimum_commission",
        "sell_stamp_bps",
        "transfer_bps",
        "buy_spread_bps",
        "sell_spread_bps",
    ],
)
@pytest.mark.parametrize("value", [-1.0, float("nan"), float("inf"), float("-inf")])
def test_invalid_fee_rate_is_rejected(field: str, value: float):
    kwargs = {
        "start_date": "2020-01-01",
        "end_date": "2020-02-01",
        "market": "SYNTH-X",
        "buy_commission_bps": 2.0,
        "sell_commission_bps": 2.0,
        "minimum_commission": 5.0,
        "sell_stamp_bps": 10.0,
        "transfer_bps": 0.1,
        "buy_spread_bps": 0.0,
        "sell_spread_bps": 0.0,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=field):
        FeeSchedulePeriod(**kwargs)


def test_period_dates_and_market_are_validated():
    with pytest.raises(ValueError, match="start_date"):
        _period("not-a-date", "2020-02-01")
    with pytest.raises(ValueError, match="before end_date"):
        _period("2020-02-01", "2020-02-01")
    with pytest.raises(ValueError, match="market"):
        _period(market="")


def test_fee_configuration_is_immutable():
    period = _period()
    model = _model(period)

    with pytest.raises(FrozenInstanceError):
        period.sell_stamp_bps = 1.0  # type: ignore[misc]
    with pytest.raises(TypeError):
        model.symbol_markets["BBB"] = "SYNTH-X"  # type: ignore[index]


def _ledger_model(*, symbol_markets=None) -> DatedTradeFeeModel:
    return DatedTradeFeeModel(
        schedule=DatedFeeSchedule(
            periods=(
                _period("2020-01-01", "2020-01-06", sell_stamp_bps=10.0),
                _period("2020-01-06", "2020-02-01", sell_stamp_bps=5.0),
            )
        ),
        symbol_markets={"AAA": "SYNTH-X"} if symbol_markets is None else symbol_markets,
    )


def _continuous_inputs(
    *,
    amounts: dict[str, float],
    second_target: bool = False,
    portfolio_value: float = 1_000.0,
    round_lot: int | None = None,
):
    dates = pd.to_datetime(sorted(amounts))
    positions = pd.DataFrame(
        {
            "rebalance_date": ["2020-01-02"] + (["2020-01-03"] if second_target else []),
            "entry_date": ["2020-01-02"] + (["2020-01-03"] if second_target else []),
            "symbol": ["AAA"] + (["__CASH__"] if second_target else []),
            "weight": [1.0] + ([0.0] if second_target else []),
            "side": ["long"] + (["long"] if second_target else []),
        }
    )
    pricing = pd.DataFrame(
        {
            "trade_date": dates,
            "symbol": "AAA",
            "open": 10.0,
            "amount": [amounts[item.strftime("%Y-%m-%d")] for item in dates],
            "is_tradable": [amounts[item.strftime("%Y-%m-%d")] > 0 for item in dates],
        }
    )
    config = ExecutionSimConfig(
        enabled=True,
        portfolio_value=portfolio_value,
        participation_rate=1.0,
        liquidity_cols=("amount",),
        buy_max_days=3,
        sell_max_days=3,
        round_lot=round_lot,
    )
    return positions, pricing, config


def _run_continuous(
    *,
    amounts: dict[str, float],
    model: object,
    second_target: bool = False,
    portfolio_value: float = 1_000.0,
    round_lot: int | None = None,
):
    positions, pricing, config = _continuous_inputs(
        amounts=amounts,
        second_target=second_target,
        portfolio_value=portfolio_value,
        round_lot=round_lot,
    )
    return simulate_execution_adjusted_nav(
        positions,
        pricing,
        config,
        price_col="open",
        tradable_col="is_tradable",
        trade_fee_model=model,  # type: ignore[arg-type]
    )


def test_continuous_ledger_uses_actual_delayed_fill_date_and_records_fee_context():
    result = _run_continuous(
        amounts={"2020-01-02": 10_000.0, "2020-01-03": 0.0, "2020-01-06": 10_000.0},
        model=_ledger_model(),
        second_target=True,
    )

    buy, sell = [row for _, row in result.fills.iterrows()]
    assert buy["trade_date"] == "20200102"
    assert buy["fee_period_start"] == "2020-01-01"
    assert sell["trade_date"] == "20200106"
    assert sell["fee_period_start"] == "2020-01-06"
    assert sell["cost_stamp_tax"] == pytest.approx(sell["filled_notional"] * 5.0 / 10_000.0)
    assert sell["fee_market"] == "SYNTH-X"
    assert sell["fee_group_notional_before"] == 0.0
    assert sell["fee_group_notional_after"] == pytest.approx(sell["filled_notional"])
    assert "sell" in sell["fee_group_id"]
    assert "20200106" in sell["fee_group_id"]


def test_dated_sell_defers_when_fee_exceeds_cash_and_proceeds_then_fills_later():
    result = _run_continuous(
        amounts={"2020-01-02": 10_000.0, "2020-01-03": 1.0, "2020-01-06": 10_000.0},
        model=_ledger_model(),
        second_target=True,
        portfolio_value=1_005.01,
    )

    sell_fills = result.fills.loc[result.fills["side"].eq("sell")]
    assert sell_fills["trade_date"].tolist() == ["20200106"]
    assert sell_fills["filled_notional"].tolist() == pytest.approx([1_000.0])
    assert sell_fills["fee_group_notional_before"].tolist() == [0.0]
    deferred_day = result.daily.loc[result.daily["trade_date"].eq("20200103")].iloc[0]
    assert deferred_day["traded_notional"] == 0.0
    assert deferred_day["transaction_cost"] == 0.0
    assert deferred_day["cash"] == pytest.approx(0.0)
    sell_order = result.orders.loc[result.orders["side"].eq("sell")].iloc[0]
    assert sell_order["status"] == "filled"
    assert sell_order["first_fill_date"] == "20200106"


def test_one_order_split_across_days_gets_one_minimum_per_execution_day():
    result = _run_continuous(
        amounts={"2020-01-02": 500.0, "2020-01-03": 500.0},
        model=_ledger_model(),
    )

    assert result.fills["cost_commission"].tolist() == pytest.approx([5.0, 5.0])
    assert result.fills["fee_group_notional_before"].tolist() == [0.0, 0.0]
    assert result.fills["fee_group_id"].nunique() == 2


def test_reusing_one_dated_model_across_runs_does_not_leak_accrual_state():
    model = _ledger_model()
    kwargs = {
        "amounts": {"2020-01-02": 500.0, "2020-01-03": 500.0},
        "model": model,
    }

    first = _run_continuous(**kwargs)
    second = _run_continuous(**kwargs)

    pd.testing.assert_frame_equal(first.daily, second.daily)
    pd.testing.assert_frame_equal(first.fills, second.fills)


def test_no_actual_fill_accrues_no_fee():
    result = _run_continuous(
        amounts={"2020-01-02": 0.0, "2020-01-03": 0.0},
        model=_ledger_model(),
    )

    assert result.fills.empty
    assert result.daily["transaction_cost"].tolist() == [0.0, 0.0]
    assert result.daily["cash"].tolist() == [1_000.0, 1_000.0]


@pytest.mark.parametrize(
    ("portfolio_value", "expected_notional", "expected_commission", "expected_transfer"),
    [
        (1_005.01, 1_000.0, 5.0, 0.01),
        (500_000.0, 499_000.0, 99.8, 4.99),
    ],
)
def test_minimum_commission_scales_with_cash_budget_and_round_lots(
    portfolio_value: float,
    expected_notional: float,
    expected_commission: float,
    expected_transfer: float,
):
    result = _run_continuous(
        amounts={"2020-01-02": 1_000_000_000.0},
        model=_ledger_model(),
        portfolio_value=portfolio_value,
        round_lot=100,
    )

    fill = result.fills.iloc[0]
    assert fill["filled_notional"] == pytest.approx(expected_notional)
    assert fill["cost_commission"] == pytest.approx(expected_commission)
    assert fill["cost_transfer_fee"] == pytest.approx(expected_transfer)
    assert result.daily.loc[0, "cash"] >= 0.0
    assert result.daily.loc[0, "portfolio_value"] == pytest.approx(
        portfolio_value - fill["transaction_cost"]
    )


def test_fill_components_reconcile_to_transaction_cost_and_nav_cash_change():
    result = _run_continuous(
        amounts={"2020-01-02": 10_000.0},
        model=_ledger_model(),
        portfolio_value=1_005.0,
    )
    fill = result.fills.iloc[0]

    component_sum = (
        fill["cost_commission"]
        + fill["cost_stamp_tax"]
        + fill["cost_transfer_fee"]
        + fill["cost_spread"]
        + fill["cost_temporary_impact"]
        + fill["cost_permanent_impact"]
        + fill["cost_opportunity"]
        + fill["cost_financing"]
    )
    assert component_sum == pytest.approx(fill["transaction_cost"])
    assert result.daily.loc[0, "transaction_cost"] == pytest.approx(component_sum)
    assert 1_005.0 - result.daily.loc[0, "portfolio_value"] == pytest.approx(component_sum)


def test_run_description_serializes_complete_dated_schedule():
    model = _ledger_model()
    result = _run_continuous(amounts={"2020-01-02": 10_000.0}, model=model)

    assert result.summary["fee_model"] == model.describe()


def test_dated_run_with_missing_market_mapping_fails_before_execution():
    with pytest.raises(ValueError, match="missing market mapping"):
        _run_continuous(
            amounts={"2020-01-02": 0.0},
            model=_ledger_model(symbol_markets={}),
        )


def test_unknown_fee_model_type_is_rejected_by_explicit_dispatch():
    class DuckTypedFeeModel:
        def notional_cost_breakdown(self, notional, *, side):
            raise TypeError("internal type error must not be swallowed")

    with pytest.raises(TypeError, match="unsupported trade_fee_model"):
        _run_continuous(
            amounts={"2020-01-02": 10_000.0},
            model=DuckTypedFeeModel(),
        )


def test_dated_fee_types_are_available_from_the_public_execution_module():
    from quant_backtest_core.daily.execution import (
        DatedFeeQuote,
        DatedFeeSchedule,
        DatedTradeFeeModel,
        FeeQuoteContext,
        FeeSchedulePeriod,
    )

    assert DatedFeeQuote.__module__ == "quant_backtest_core.daily.dated_fees"
    assert DatedFeeSchedule.__module__ == "quant_backtest_core.daily.dated_fees"
    assert DatedTradeFeeModel.__module__ == "quant_backtest_core.daily.dated_fees"
    assert FeeQuoteContext.__module__ == "quant_backtest_core.daily.dated_fees"
    assert FeeSchedulePeriod.__module__ == "quant_backtest_core.daily.dated_fees"


def test_ideal_nav_rejects_dated_model_before_any_legacy_or_empty_result_path():
    with pytest.raises(TypeError, match="not supported by simulate_ideal_daily_nav"):
        simulate_ideal_daily_nav(
            pd.DataFrame(),
            pd.DataFrame(),
            price_col="open",
            trade_fee_model=_ledger_model(),  # type: ignore[arg-type]
        )


def test_schedule_coverage_starts_at_first_executable_ledger_date():
    positions = pd.DataFrame(
        {
            "rebalance_date": ["2020-01-02"],
            "entry_date": ["2020-01-02"],
            "symbol": ["AAA"],
            "weight": [1.0],
        }
    )
    pricing = pd.DataFrame(
        {
            "trade_date": pd.to_datetime(["2020-01-01", "2020-01-02"]),
            "symbol": ["AAA", "AAA"],
            "open": [10.0, 10.0],
            "amount": [10_000.0, 10_000.0],
        }
    )
    model = DatedTradeFeeModel(
        schedule=DatedFeeSchedule(periods=(_period("2020-01-02", "2020-02-01"),)),
        symbol_markets={"AAA": "SYNTH-X"},
    )

    result = simulate_execution_adjusted_nav(
        positions,
        pricing,
        ExecutionSimConfig(
            enabled=True,
            portfolio_value=1_000.0,
            participation_rate=1.0,
            liquidity_cols=("amount",),
        ),
        price_col="open",
        trade_fee_model=model,
    )

    assert result.summary["status"] == "ok"
    assert result.fills["trade_date"].tolist() == ["20200102"]
