# Sequenced execution {#sequenced-execution}

[简体中文](sequenced-execution.zh-CN.md)

Use `run_daily(request)` with `mode="sequenced"` to replay chosen decisions through one original daily cash/share owner. A fresh call creates a fresh account. `ExecutionAdjustedNavResult` preserves daily, orders, fills and optional action/holding tables.

Provide one SDK `ClockSet` per ISO rebalance date, explicit entry dates, `DailyDecisionTiming`, `ExecutionCalendar` and `DailyInputLayout`. Information cutoff dates match rebalance dates; information ≤ decision ≤ entry. Source timing constrains entry sessions and the valuation horizon. The simulation resolves dates only: legacy fill audit timestamps remain synthetic midnight labels in Asia/Shanghai. They are not observed event times and do not establish intraday execution eligibility.

Every entry needs supplied pricing/session coverage. Duplicate decision/symbol keys, multiple decisions on one entry date, nonfinite/negative or overweight targets, incomplete clocks, future pricing and unknown enabled rule fields fail admission. Planned sale proceeds cannot fund buys: the share ledger uses actual sells before fee-inclusive buy affordability.

    from quant_backtest_core.daily.runner import run_daily
    result = run_daily(request)
    ledger = result.to_unified_ledger()

The complete synthetic wire example is `fixtures/product/daily.json`; see [daily inputs](../product/daily-inputs.md). Select `python.daily` explicitly. There is no daily checkpoint/restore API or runtime database.

The old Platform `SequencedExecutionRequest` / `research.clock.v1` adapter and research bundle writer remain consumer concerns; serialized identifiers stay unchanged. A single-clock research bundle must still reject a multi-decision run. Supplied clocks and calendars do not authenticate historical input visibility.
