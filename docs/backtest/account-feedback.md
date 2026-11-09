# Account feedback and impact stress

[简体中文](account-feedback.zh-CN.md)

Implemented in the provider B worktree; unreleased until gate B merge. Core source is 0.2.0; merged release availability and consumer cutover remain separate. [Pinned original documentation](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/account-feedback.md).

Import minute execution explicitly from `quant_backtest_core.backtest.minute`.
`decision_policy(state, proposed_weights)` runs at each decision clock before bars
ending at that clock. The read-only snapshot contains actual cash, inventory, raw
marks and their timestamps, pending parent orders and receivables. A returned complete
weight mapping freezes until entry; omitted held names target zero. An empty mapping
exits all holdings. Returning `None` preserves pending orders without resubmission.

Reports and cancellation are synchronous in this reference simulator. Replacing a
target cancels residual parents at entry; this does not model delayed exchange
acknowledgements or reproduce a real order queue. Future data used by an external
policy is still the caller's responsibility. Missing data is not manufactured.

`LinearImpact` in `quant_backtest_core.backtest.impact` is an uncalibrated linear stress
model. Transient/permanent coefficients are price units per signed share; the decay
constant is elapsed seconds. For signed fill q, the average price offset is prior
transient plus permanent state plus half the current linear increment. Actual fills
update both components; only the transient component decays. Same-clock splitting
preserves total cost. Nonnegative coefficients with exponential decay have a
nonnegative flat-market round-trip cost. This does not identify real market impact.

Pass a separate `impact_model` per simulation. The model changes execution prices
and subsequent executions. Cash uses those prices and does not deduct impact again.
Price-limit violations block affected fills. Valuation and policy observations use
external raw prices, excluding own impact; results are execution-price stress, not
an endogenous market simulation. The summary declares these semantics and retains
the impact checkpoint. An impact checkpoint does not restore the complete account.
Do not share one mutable model across independent scenarios.

Participation slippage defaults to `coverage_policy="raise"`: when impact is enabled,
missing/nonpositive/nonfinite liquidity and participation above `max_participation`
fail explicitly. That bound is a calibration boundary, not a fill capacity control.
`coverage_policy="legacy"` preserves earlier missing-liquidity and clipping behavior
for compatibility; formal studies should explicitly select strict coverage. Builders
and descriptions preserve the policy. Price-embedded costs must not also be charged
as cash fees. Calibration cutoff and parameter applicability remain study evidence.

The minute result summary declares `execution_ledger_daily_nav`, account-delivery and
valuation semantics. It does not certify an execution-aware canonical result bundle,
data availability, market completeness, or strategy profitability.

## Delayed paper feedback and reservations

The separate [PAPER event adapter](../contracts/paper-account-events.md) models
delayed reports and cancellation acknowledgements; its `visible` and `pending`
views feed the [neutral reservation seam](../contracts/pending-allocation.md).
Minute execution above remains synchronous. `ExecutionState` checkpoints include
policy, fill deduplication, impact, account state and pending reports together.
[LOB execution-impact estimation](../microstructure/impact-estimation.md) reports
actual replay fills and descriptive shortfall; it does not debit this account.
