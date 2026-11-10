# Dated execution fees

Language: English · [简体中文](dated-execution-fees.zh-CN.md)

Core 0.3.0 implements the daily owner graph; release availability still requires merged-source and exact-wheel receipts. Selection, research statistics and bundle publication remain Platform. See [daily inputs](product/daily-inputs.md).


`DatedTradeFeeModel` applies caller-supplied fee periods to actual fills in the
continuous execution-adjusted NAV ledger. It has no built-in market tariff,
vendor data, credentials, or strategy settings. Existing callers that omit a
dated model keep the previous transaction-cost behavior.

## Public contract

Import the dated interfaces from `quant_backtest_core.daily.execution`:

```python
from quant_backtest_core.daily.execution import (
    DatedFeeSchedule,
    DatedTradeFeeModel,
    FeeQuoteContext,
    FeeSchedulePeriod,
)
```

Each `FeeSchedulePeriod` is active from its inclusive `start_date` through its
exclusive `end_date` for one explicit market identifier. The caller supplies
buy and sell commission rates, minimum commission, sell stamp rate, transfer
rate, and buy and sell spread rates. Rates are basis points except for the
minimum commission, which uses the same currency unit as executed notional.

Periods for the same market cannot overlap. A missing date, ambiguous date, or
missing symbol-to-market mapping raises instead of selecting a fallback.
Configuration objects and the copied symbol mapping are immutable.

## Pure quotation

Quotations do not mutate either the model or the schedule:

```python
periods = (
    FeeSchedulePeriod(
        start_date="2030-01-01",
        end_date="2030-07-01",
        market="SYNTH-X",
        buy_commission_bps=2.0,
        sell_commission_bps=2.0,
        minimum_commission=5.0,
        sell_stamp_bps=10.0,
        transfer_bps=0.1,
        buy_spread_bps=0.0,
        sell_spread_bps=0.0,
    ),
    FeeSchedulePeriod(
        start_date="2030-07-01",
        end_date="2031-01-01",
        market="SYNTH-X",
        buy_commission_bps=2.0,
        sell_commission_bps=2.0,
        minimum_commission=5.0,
        sell_stamp_bps=5.0,
        transfer_bps=0.1,
        buy_spread_bps=0.0,
        sell_spread_bps=0.0,
    ),
)
model = DatedTradeFeeModel(
    schedule=DatedFeeSchedule(periods=periods),
    symbol_markets={"SYNTH-AAA": "SYNTH-X"},
)
quote = model.quote(
    FeeQuoteContext(
        trade_date="2030-07-01",
        side="sell",
        symbol="SYNTH-AAA",
        market="SYNTH-X",
        executed_notional=1_000.0,
        cumulative_group_notional=0.0,
    )
)
```

Commission is incremental. For cumulative group notional `before` and fill
notional `fill`, it is the commission accrued on `before + fill` minus the
commission already accrued on `before`. A zero cumulative amount has zero
accrued commission, so a zero fill never triggers the minimum. Stamp, transfer,
and spread components apply only to the actual incremental fill.

## Continuous-ledger integration

Pass the model as `trade_fee_model` to
`simulate_execution_adjusted_nav`. Before execution, the run verifies that all
target symbols have market mappings and that every simulated trade date has one
period for each used market. This intentionally fails closed on date gaps.

Fee accrual belongs to the simulation run, not the reusable model. The ledger
groups commissions by original order and execution day. This is an explicit
generic broker-grouping assumption: fills for the same order on different days
receive separate daily minimums. Affordability checks are pure previews; only a
recorded fill advances its group notional. Fee-inclusive cash checks are repeated
after round-lot adjustment, and an unaffordable fill is not debited.
If a dated sale's fee would exceed current cash plus its proceeds, that sale is
deferred without changing holdings, order progress, fee accrual, or receipts;
the pending order may fill on a later affordable execution day.

Fill receipts include component costs plus `fee_market`, period boundaries,
`fee_order_id`, `fee_group_id`, and cumulative group notional before and after
the fill. The run summary serializes the complete dated schedule and symbol map.

## Scope and limitations

The dated model is integrated with the continuous execution-adjusted NAV path.
It is not a claim of full realistic execution, broker invoice replication, or
dividend support. It does not infer markets from ticker syntax, fill date gaps,
combine unrelated orders, model intraday ordering, or provide jurisdictional
defaults. Use synthetic schedules for examples and tests, and supply externally
validated public fee inputs for any real application.
