# Diagnostic period replay {#next-close-diagnostic-replay}

[简体中文](diagnostic-close-replay.zh-CN.md)

`run_period_replay` evaluates already chosen holdings on explicit period boundaries and returns the original `PositionBacktestResult(net_returns, gross_returns, periods, summary)`. It never manufactures daily cash, shares, orders, fills or cash fee-debit evidence.

    from quant_backtest_core.daily.period_replay import run_period_replay
    result = run_period_replay(
        positions=positions, pricing=pricing, periods=periods,
        calendar=calendar, config={"transaction_cost_bps": 10.0},
    )

This corrects the pre-implementation plan's missing `periods` input and unsuitable daily-NAV result. The actual source is pinned `_position_backtest_config/_position_backtest_engine` plus pure normalization/drift helpers. All original net/gross/period columns, duplicate period-end rows, dtypes, skipped-period metadata and arithmetic remain. Explicit periods require rebalance_date, entry_date and exit_date; the new helper rejects missing supplied session coverage without calendar fetches or inferred period boundaries.

The direct `daily.position_backtest.run_position_backtest` signature remains, including optional intraday VWAP diagnostics. Normalization, exit policies and terminal-only marks retain their original behavior. Selection, strategy weight-model construction and publication remain Platform. Broad annualized/Sharpe/drawdown/H1/H2 research statistics are absent from Core. Financial-only average turnover, cost and exposure fields remain under `summary["stats"]`. Task 15 reconstructs the original research dictionary using the same owned result class.

The unchanged liquid golden has gross return `0.05` and net return `0.049` with 10 bps initial cost. It explicitly declares no order lifecycle, partial fills or daily ledger.

## Retained next-close workflow {#inputs-and-execution-timing}

Platform's separate `target_close_replay.replay_close_targets` remains there: first close after formation, fractional adjusted units, caller-selected 25 bps default, whole-basket deferral on blocked trades, no broker fills/dividend ledger. This extraction does not replace it. [Pinned original guide](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/guides/diagnostic-close-replay.en.md) retains its full timing and exposure contract.

## Exposure changes {#exposure-changes}

Exposure decisions, volatility targets and target construction remain Platform inputs. Core infers neither cash interest nor future exposure.

## Audit helpers {#audit-helpers}

Holdings PnL, drawdown episodes and matched-volatility research diagnostics remain in the retained workflow. Historical visibility, dividend adjustment, delisting and practical feasibility need separate evidence.
