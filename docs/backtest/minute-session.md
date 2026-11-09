# Recoverable minute execution sessions

Language: English · [简体中文](minute-session.zh-CN.md)

`quant_backtest_core.backtest.minute_session.MinuteSession` steps and restores the
existing minute matcher and economic ledger. It supports immutable corporate
action, permanent valuation and external capital-flow tapes, with a conservative
delayed financial view. It does not implement broker recovery or historical queues.

## Construct and restore

Use targets, bars and `MinuteExecutionConfig`, plus a callable policy implementing
`checkpoint()`. Optional keywords are `corporate_actions=()`,
`valuation_events=()`, `capital_flows=()`, `quantity_locks=()`,
`report_delay_seconds=0` and `impact=None`. Old constructor inputs remain valid.
Import `CorporateAction`, `ValuationEvent` and `CapitalFlow` from
`quant_backtest_core.backtest.minute`. The synchronous `simulate_minute_execution`
accepts the same three financial tapes and uses the same ledger.

Call `step()` for one scheduled instant, `checkpoint()` before finalization,
and `run()` to finish. Reconstruct the policy from the checkpoint's `policy`
field, then call:

```python
restored = MinuteSession.restore(
    targets,
    bars,
    config,
    checkpoint,
    policy=restored_policy,
    corporate_actions=expected_actions,
    valuation_events=expected_valuations,
    capital_flows=expected_capital_flows,
)
```

Expected tapes are checked exactly. Omitting a tape argument uses its embedded
checkpoint tape for convenience. An external job must still bind its expected
source artifacts and supply expected tapes, including empty tuples. Embedded
data alone does not establish that the caller intended those inputs.
Policies need inspectable source files. Recoverable models accept only the exact
`LinearImpact` type, and financial tapes require exact supported event types.

## Financial clocks and ordering

Corporate actions retain the existing timezone-naive calendar-date contract:
`available_date <= record_date < ex_date`. Record-day closing holdings establish
rights. The first observed subsequent day recognizes ex-date receivables and
credits due cash payments or released stock. Dates are not invented historical
intraday timestamps. Missing record-day coverage fails. Synthetic ex references,
withholding, fractional entitlements, T+1 and fees retain their owner semantics.

At a scheduled instant, the owner closes the prior observed day, resets T+1,
opens the new day and applies due actions, then applies permanent valuations,
capital flows, order expiry and quantity-lock guards. Due financial reports are
delivered before decisions. Decisions precede entries and bars. A bar stamped at
the same clock is not a pre-flow or decision mark.

`ValuationEvent` retains its aware availability/effective clocks and permanent
trading prohibition. Pre-window declarations apply at the first instant.
Post-window valuations are disclosed as ignored and do not extend the window.
Their marks include legal stock receivables without creating disposal cash.
Absent held marks remain unknown. Stale daily marks still invalidate daily NAV.

## External capital and returns

`CapitalFlow(event_id, available_time, effective_time, amount, source)` declares
signed cash in the account currency. Amount must be finite and nonzero.
Availability must be timezone-aware and no later than the effective time.
The effective time must lie within the simulation window and is added to its
event schedule. Sessions include decision instants in that window. Synchronous
execution includes them when a decision policy is supplied. Pre-window and post-window capital
flows fail rather than changing the initial account or being silently ignored.
Unique event IDs deduplicate effects. Multiple flows at one clock apply in
lexicographic event-ID order, irrespective of input order.

Deposits increase cash. Withdrawals use existing economic cash only, never
assumed liquidation proceeds, and may not overdraw it. Result
`capital_flow_ledger` records clocks, source, signed amount and before/after cash
and NAV. Flow tapes opt in to daily `capital_flow`,
`cumulative_capital_flow`, `pnl` and `cumulative_return`.
Inception PnL equals NAV minus initial cash minus cumulative external capital.

Returns chain marked subperiod growth: initialize anchor wealth to initial cash
and factor to one. Immediately before each flow, multiply the factor by
`pre_flow_NAV / anchor`, then set the anchor to `pre_flow_NAV + amount`.
At daily close report `factor * daily_NAV / anchor - 1`. Thus capital never
counts as investment return. Subperiod marks use prior observations and any
already-effective permanent valuation, including outstanding rights.
If held shares or stock rights lack a mark or a current-day observation
(except persistent permanent valuations), pre-flow NAV and subsequent cumulative
return are unknown. A stale daily close alone makes that day's return unknown.
Zero or negative pre-flow wealth, post-flow anchor or daily wealth has no defined
reported return. An undefined flow boundary keeps subsequent returns unknown.
No borrowing, insolvency resolution or executable terminal liquidation is inferred.

## Delayed visibility and locks

Snapshots contain cash, legal holdings, entitlement rights and pending orders.
Visible NAV values delivered holdings and rights using current external marks.
Undelivered changes at the current clock immediately create a pending-report
marker. While any financial report remains undelivered, new target submissions
are suppressed at both decision and entry, even if the policy requests them.
Cancellation is synchronous with delayed acknowledgement, without network latency.

`QuantityLock` uses inclusive UTC-nanosecond availability/start/end clocks and
symbol restrictions. Restrictions apply after both availability and start.
Actions may increase legal shares under a lock, but none become executable until
the restriction ends and owner T+1/release rules permit them. Locks cancel remaining
orders, skip sizing and prohibit fills in any overlapping bar. Release does not
revive cancelled orders. Fractional rights remain unsellable. Lock notices and
active guards restore together with economic and delivered state.

## Checkpoint version and failure policy

`minute-session.v3` embeds `minute-financial-tapes.v1`, event tapes, the event
cursor, rights, valuations, capital-flow dedup IDs and return anchors, T+1 state,
parent fees, orders/fills, policy snapshots, impact and the delivery queue.
Float inputs bind their exact consumed Python values, without decimal truncation.
Inputs, configuration, policy implementation and all participating owner helper
sources are content-bound. Nonfinite diagnostics use explicit tagged encodings.
Digests detect accidental corruption, not a hostile author who can rewrite them.

Platform version 1 and version 2 checkpoints are rejected with instructions to restart from original
inputs or run their original pinned sources. Missing new state is never silently
defaulted. No in-place migration is provided. A failed step poisons the session:
it cannot run or checkpoint further. Discard it and reconstruct from the last
successful checkpoint. Earlier effects within a failed multi-event instant may
exist only in that discarded object. Fixing an input requires a fresh run because
the checkpoint binds the original tape. Finalized sessions cannot be checkpointed
or rerun. Final closing rights and order expiry remain owner finalization behavior.

Every-boundary tests compare full state and financial tables to uninterrupted
execution. Zero-delay cases also compare with the synchronous owner. These are
synthetic accounting tests, not Runtime process-kill or live-broker recovery claims.

## Engine ownership and synthetic example

Install `quant-backtest-core[minute]` explicitly. Core defines the financial types.
Platform remains on its original provider until the complete type, `LinearImpact`
and compatibility-alias cohort switches in the consumer wave. No Platform, Runtime
or model-training dependency is imported. The product runner now registers `python.minute`; see [financial recovery](../product/recovery.md).

Run the repository’s synthetic CNY example against installed wheels:

```bash
python -I -B examples/product/minute_session.py
```

It exercises actions, locks, delayed reports and external capital, checking complete
financial tables after recovery. See the [minute execution guide](../guides/minute-execution.md)
for clock and recovery semantics. Old `minute-session.v2` state requires its original
complete pinned provider environment; rewriting digests or silent migration is unsupported.
