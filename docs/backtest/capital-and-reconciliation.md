# Capital events, investment returns and external evidence

[简体中文](capital-and-reconciliation.zh-CN.md)

Implemented in the provider B worktree; unreleased until gate B merge. Core remains version 0.1.0 during transfer. [Pinned original documentation](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/capital-and-reconciliation.md).

`quant_backtest_core.evidence.capital_returns` links returns from complete capital
observations. Supply initial NAV/start UTC nanoseconds and `CapitalObservation`
records containing strictly increasing clocks, NAV immediately before external
flow, signed external flow and NAV immediately after it. Before/after values must
satisfy the cash identity within floating-point ULP precision. NAV must remain
positive: stop before a full redemption or insolvent boundary rather than inventing
units for a restarted account.

`capital_performance` reports exact linked time-weighted return and net monetary
gain, separately from an explicitly approximate elapsed-time Modified Dietz return.
It does not assume or search for a unique money-weighted IRR. Dividends, fees and
market gains belong in investment NAV; deposits and redemptions are external flows.
Missing valuations cannot be repaired by labeling the difference a capital flow.

The existing supplied-event `AccountEventAdapter` accepts `cashflow` (signed amount)
and `fee_adjustment` (nonnegative cost), each with a nonempty reason. The economic
clock must already be projected. Balances below the configured credit limit reject
atomically. Existing report delay and event-ID idempotence apply; callers must use
one canonical physical identity for each capital/fee event. This API does not infer
broker cash movements or support fee credits as negative costs. Dividends continue
to use their existing record/ex/pay lifecycle, including unpaid entitlements.

`quant_backtest_core.backtest.reconciliation` compares immutable caller-supplied
`AccountEvidence`, with normalized `OrderEvidence`, raw integer holdings and venue
fill identities. Snapshots must have matching account/currency/economic clocks and
fill-history coverage, be declared complete, and be available by the decision.
Cash/receivable differences beyond the explicit tolerance, share differences,
unknown orders or unequal physical fill sets block new orders. Overflow and missing
or late evidence block comparison without emitting nonfinite JSON amounts.

A match only describes the supplied evidence. The API has no venue access, changes
no books, emits no corrective fills and does not certify a caller's source or
completeness declaration. Unmatched data must be investigated by the owner; internal
checkpoint recovery is not a substitute for external reconciliation.

The existing uncertainty math is also available at
`quant_platform.portfolio.robust_uncertainty`: `conservative_score`,
`box_worst_case_return` and `add_conservative_score`. This is the existing
implementation, not a new uncertainty estimator or calibrated risk model.

Generic robust uncertainty and advanced capital research remain Platform-owned; the transfer here covers account feedback and external evidence reconciliation only.
