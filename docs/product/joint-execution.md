# Joint execution forecast benchmark

[简体中文](joint-execution.zh-CN.md)

`quant_backtest_core.planning.joint_execution` compares finite paths of target
weights by replaying every candidate through the existing `MinuteSession`.
Alpha, terminal risk, lot sizes, parent minimum commissions, participation,
T+1, delayed reports and transient/permanent linear impact therefore influence
the same decision. The session remains the sole owner of cash and holdings.
Install the optional Python product with the `planning` extra.

This is a bounded forecast benchmark. It does not estimate alpha, covariance,
capacity or impact coefficients. Supply a scenario that was available at the
planning clock; realized future market bars belong only in an independent
execution evaluation. Future target weights are contingent: execute the first
choice through the actual owner, receive its reports, then replan.

## Request and result

The frozen `JointExecutionRequest` requires:

- `names`: fixed, unique symbol order used by weights and terminal covariance.
- `decision_ns`, `forecast_available_ns`, `risk_available_ns`: integer UTC
  nanoseconds; both availability clocks must be at or before the decision.
- `forecast_bars`: caller forecast bars strictly after the decision;
  `past_bars` optionally supplies observed bars at or before it.
- `decision_times`, `entry_times`: aligned UTC nanoseconds. The first decision
  equals `decision_ns`; entries follow decisions, and each later decision
  follows the preceding entry.
- `weight_choices`: one nonempty tuple of weight vectors per decision. Each
  vector is long only and sums to at most one. Index zero is the caller's first
  choice; it is not implicitly cash.
- `config`: exact `MinuteExecutionConfig`; `terminal_covariance`: finite,
  symmetric positive semidefinite return covariance in `names` order.

Optional `committed_targets` supplies the already chosen prefix in the existing
minute target schema (`decision_time`, `entry_time`, `symbol`, `weight`). Both
clocks must be at or before the as-of decision and prefix decisions strictly
before it. Its weights must also be finite, long only and sum to at most one
per decision. Starting holdings, cash, pending orders, reports and impact state
are replayed from this prefix; arbitrary initial shares or cash adjustments are
not supported. The configuration's initial cash is the start of that replay.

Bars use the existing minute schema: timezone-aware `time`, `interval_start`,
`symbol`, `open`, `high`, `low`, `close`, `volume`, `amount`; optional limit and
tradability columns follow the minute owner. Prices must be positive and OHLC
consistent, capacity nonnegative, and forecast data must extend beyond the last
entry. Missing decision/execution marks retain the owner's rejection behavior;
unknown decision holdings marks or terminal holdings marks reject evaluation.
There is no order-book queue, stochastic path distribution, short inventory,
corporate-action tape, or capital-flow tape in this benchmark.

Optional scalars are `risk_aversion=0`, `transient=0`, `permanent=0`,
`decay_seconds=1`, `report_delay_seconds=0`, `max_evaluations=4096`.
Impact uses the existing uncalibrated `LinearImpact` model: price units per
signed share, with elapsed-second exponential transient decay. Fees and impact
are debited by the owner exactly once. A policy waits whenever its delivered
observation has pending orders or an undelivered financial report. No planned
sale proceeds fund purchases before the owner actually fills the sale.

`evaluate_joint_path(request, indices)` returns `JointPathEvaluation` with the
actual owner `result`, `objective`, `initial_nav`, `terminal_nav`,
`risk_penalty`, source-bound `request_digest`, decision and terminal checkpoints,
and an `evidence` property exposing the delivered observation, report queue,
policy trace and impact state. Input frames and arrays are copied for each
public call. The request digest binds the entire problem and loaded owner and
policy sources independently of the selected path; checkpoints separately bind
that path's exact targets. A checkpoint can only restore unchanged owner inputs
and sources, not a new forecast or a changed target path.

`solve_joint_execution(request)` returns `JointExecutionPlan` with `indices`,
`first_weights`, selected `evaluation`, `evaluation_count`, `total_paths`,
`request_digest`, `status` and explicit contingent-plan semantics.

## Objective and search scope

The CNY objective to minimize is

```text
initial_nav - terminal_nav
+ risk_aversion / (2 * initial_nav) * terminal_exposure' covariance terminal_exposure
```

Initial NAV is the owner's economic wealth immediately before the first
decision event; delivered balances remain separate checkpoint evidence.
Terminal exposure is actual remaining shares times the owner's final marks.
Terminal NAV is marked wealth, not forced liquidation proceeds. Risk is a
terminal penalty, not a full temporal risk model. Forecast prices carry alpha;
there is no separate alpha reward that would count the same price gain twice.
Profitable paths can have negative objectives, so no zero lower bound is given.

The declared caps are eight decisions, 32 choices per decision and 100,000
owner evaluations. When the complete Cartesian grid fits the requested budget,
every path is evaluated and `status="optimal_exhaustive"` means best on that
finite grid only. Otherwise deterministic coordinate search starts from the
all-zero **indices** path, retains a feasible owner-replayed incumbent and
returns `status="heuristic_budgeted"` unless it actually evaluated every path.
It may stop before the budget at a coordinate fixed point. Ties use the
lexicographically smallest index tuple. There is no optimality certificate or
lower bound for incomplete searches. Validation and computation errors propagate;
failed evaluations are never silently removed from an alleged complete grid.

## Synthetic acceptance

`packages/core/tests/test_joint_execution.py` includes a literal finite wealth oracle,
fees/lots and terminal risk changing the first choice, partial fills charging a
parent commission minimum once, a blocked A sale that cannot fund tradable B,
a funded B control, forecast timing and future capacity changing the first
choice, transient/permanent state recovery under the exact owner binding,
delayed-report waits, input immutability, availability rejection and honest
budget status. These synthetic cases establish implementation behavior, not
out-of-sample forecasting skill or market-calibrated execution performance.
