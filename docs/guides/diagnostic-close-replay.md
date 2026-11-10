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


## Pure period-leg financial closure (Task 15P)

The source-closure review after merged provider C (PR #24) found additional pure
financial helpers still owned by Platform. Task 15P transfers those original
bodies before consumer Task 15 resumes; it does not revise PR #24's historical
evidence or add a financial model.

- `daily.leg_financial._build_backtest_leg_result` consumes explicit holdings,
  target/executed weights, entry/exit marks, prior state, dates and cost/slippage
  models. It preserves signed long/short diagnostic gross return, all turnover
  layers, cost method arguments, target/executed names, exposure and cash fields.
  `_build_leg_turnover_report` retains the previous recorded target distinction;
  `_next_position_state` retains initial cash and recorded-target flags.
- `daily.pricing.slippage_pricing_row` only reads the supplied participation
  amount table. Missing columns/dates retain the original lookup exceptions.
- `daily.period_turnover.period_result_from_leg/period_result_from_legs` return
  the Core-owned `daily.types.BacktestPeriodResult`, with the original field
  order/defaults and the same Core `CostBreakdown` class. Fees and slippage are
  summed once, unknown optional diagnostics remain unknown, names are merged as
  originally defined, and the later leg exit determines the period exit.
- `daily.trade_accounting.compute_trade_summary/drift_previous_weights` and
  their `_compute_trade_summary/_drift_previous_weights` aliases preserve the
  separate legacy API. An empty target returns zero turnover; an initial
  `None` or empty prior portfolio counts the full normalized target. These are
  different semantics from `daily._period_helpers`, which distinguishes an
  uninitialized account from explicit cash and supports preserved exposure.
  Existing `TradeCostConfig`, `TradeAccounting`, `drift_weights`,
  `compute_trade_accounting` and `compute_trade_accounting_frame` are unchanged.

Selection, ranking, grouping, target-weight construction, research period
orchestration, broad metrics, calendar acquisition, and `period_turnover_fields`
research projection stay in Platform. Diagnostic long/short legs do not add
short borrowing, margin, fills or a daily cash ledger to `python.daily`.
Each run retains one financial owner; no fee, slippage or shortfall is debited
again by the caller.

Core/SDK remain 0.3.0, Rust 0.2.0 and native 0.1.0. Task 15P wheels have distinct
immutable hashes and source revisions; versions alone cannot identify this
closure. Consumer migration waits for the reviewed, merged follow-up and its
exact VCS/wheel pin. No PyPI release is implied. Platform compatibility aliases
must remain for two minor-release cycles **and** until every recorded supported
consumer migrates. Old checkpoints keep their original complete environment.

Acceptance executes synthetic prepared calls in the actual pinned original
owner and ordinary installed Core wheels on Python 3.12/3.13, comparing every
dataclass field/property, Series value/index/dtype, signature, lookup exception
and cost-call argument. The executable
`project_tools/verify_period_leg_parity.py` records the actual import closure;
static source matching alone is not acceptance.

The strict parity profile also installs the original PyArrow 26.0.1 alongside pandas 3.0.6 and NumPy 2.2.6. Lean daily/union profiles omit PyArrow: their concrete Arrow-to-Python StringDtype storage differences are inventoried per Series index, then compared with exact values and dtype checks after only that explicit storage conversion. No blanket dtype suppression is used.
