# Impact-aware rolling planning

Language: English · [简体中文](impact-planning.zh-CN.md)

Use `quant_backtest_core.planning.impact_planning.plan_with_impact` to form a continuous,
long-only finite-horizon plan with diagonal transient impact. Execute only the
first action after the execution owner checks quantities, fees, prices and timing.
Then replan from actual delivered holdings, available cash and impact state.
Existing `quant_backtest_core.planning.multiperiod.plan_trades` defaults are unchanged.

The supported problem is a convex QP with conservative affine cash limits.
It does not optimize over the exact economic cash-feasible set. Exact execution
cash is quadratic in trades; treating those constraints as affine would be wrong.
The plan separately reports and checks economic cash and its conservative lower
bound. Capacity may therefore make an economically affordable trade unavailable.

## Request and objective

`ImpactPlanningRequest` uses raw shares and CNY (`units="raw_shares_CNY"`):

- `initial_holdings`, `unaffected_prices`, `initial_transient`, `transient` and
  `decay_seconds` have shape `(N,)`. Prices are fixed positive unaffected marks.
  Displacement is CNY/share (price units), impact coefficients are CNY/share²,
  and decay is strictly positive elapsed seconds, as in
  `LinearImpact`'s `linear-impact.v1` convention. Initial displacement is signed
  and already advanced to `decision_ns`; permanent impact is zero.
- `expected_returns` and nonnegative finite `capacity` have shape `(H,N)`;
  `covariances` has shape `(H,N,N)` and contains symmetric PSD return covariances.
  Symmetry/eigenvalue roundoff within `1e-12` is symmetrized/projected onto PSD.
  `step_seconds` contains `H-1` nonnegative gaps. First action is at elapsed zero;
  equal-clock steps are allowed. Expected returns reward post-trade holdings for
  each step and are not spendable cash.
- `initial_cash`, `reserved_cash` and `risk_aversion` are finite and nonnegative.
  Reservations cannot exceed initial cash. `locked_holdings` is an optional
  `(N,)` floor no greater than initial inventory. Zero capacity locks a step/name.
- `fee_per_share` and `spread_per_share` are nonnegative fixed CNY/share scalars
  or `(N,)` arrays. Spread shifts execution price by trade sign; fees debit cash
  once. Nonzero `fee_rate`, `minimum_fee`, `quantity_step` or `permanent` are
  explicitly unsupported. Integral lots and execution-notional fees need another
  owner-supported decision/recheck process; they are not silently approximated.
- `decision_ns`, `forecast_available_ns`, `risk_available_ns` and
  `state_available_ns` are integer UTC nanoseconds. No availability clock may be
  after the decision. These checks do not authenticate source data or validate
  model fitting history; callers retain those records. All arrays share one
  caller-maintained name order. Do not mutate input arrays during invocation.

Let `q[t]` be signed shares, `h[t] = h[0-] + sum(q[:t+1])`, prices `p`,
initial decision NAV `V = initial_cash + p @ h[0-]`, and elapsed times `s[t]`.
For each name, the pre-fill transient state and execution displacement are

```text
d[t] = exp(-s[t]/tau)*d[0-] + k*sum(exp(-(s[t]-s[u])/tau)*q[u], u<t)
offset[t] = d[t] + k*q[t]/2
state_after[t] = d[t] + k*q[t]
```

The declared objective, returned in CNY, is

```text
sum_t (risk_aversion/(2*V) * (p*h[t])' Sigma[t] (p*h[t])
       - alpha[t]' (p*h[t])
       + q[t]' offset[t] + (fee+spread)' abs(q[t]))
```

The transient quadratic kernel is `k*exp(-abs(s[t]-s[u])/tau)` per name,
which is PSD. Risk is PSD; absolute linear costs use auxiliary variables.
The implementation validates the assembled Hessian. The solve uses NAV-normalized
notional variables for conditioning, analytic gradients and SLSQP; solver success
is not an independent certificate of numerical global optimality. No terminal
liquidation or residual-mark cash is assumed. An initial signed transient state
can benefit an offsetting trade; a zero-state closed round trip at constant
unaffected prices cannot create impact profit.

## Affine cash envelope and execution checks

From capacities `c[t]`, define the nonnegative price displacement bound

```text
B[t] = abs(exp(-s[t]/tau)*d[0-]) + k*c[t]/2
       + k*sum(exp(-(s[t]-s[u])/tau)*c[u], u<t)
cash_lower[t] = initial_cash - sum(p' q[u] + (B[u]+fee+spread)' abs(q[u]), u<=t)
```

The QP enforces `cash_lower[t] >= reserved_cash` using the absolute-value
auxiliary variables; all its constraints are affine or bounds. It rejects
capacity/state combinations with `B[t]+spread >= p`, which could allow nonpositive
execution prices. This restriction and the cash envelope are intentionally
conservative. Cash is checked at each step's net settlement; execute sells before
buys if using their proceeds within a step. Exchange settlement, pending-order
locks and changing actual prices still require the execution owner's checks.

The returned trades are independently propagated through `LinearImpact`, with
half the own increment in fill price. Cash subtracts signed fill notional plus
fixed fees exactly once; impact is never an additional fee. `ImpactPlan` returns
trades, first action, holdings, pre/post transient states, execution prices,
economic cash, affine cash lower bounds, objective, solver status/message and
named residuals. Residuals are dimensionless using decision NAV/notional and must
not exceed `1e-7`. Failed solves or independent infeasibility raise `ValueError`.
The report's `request_digest` binds the request snapshot's numerical float64 bytes,
array shapes, exact integer clocks, configuration and versioned model convention
using SHA-256; it is not source authentication. Preserve source bytes/provenance
and the implementation commit alongside it. Unknown provenance remains unknown.

The first action is continuous, not a submitted order. Before releasing it, use
the existing owner's quantity rounding and feasibility checks, and verify fee and
impact conventions and actual elapsed clocks. Later planned quantities are neither
reserved nor completed trades. Restore the owner's state and replan after actual
fills; do not advance live impact state with hypothetical future trades. The
synthetic tests exercise an exactly integral first action through the existing
minute matcher, restore its state, and check single cash charging.

## Reproduction and limits

`core/tests/test_impact_planning.py` includes independent hand solutions, capacity and
alpha sensitivity, cash reservations, locked inventory, exact request binding,
owner matching and restoration, and failure rejection. It checks share-unit and
currency scaling, decaying round trips, and same-clock half-own-increment slicing.
Slicing invariance concerns economic impact cost, not identical conservative cash
envelopes under different capacity partitions. Inputs are synthetic, uncalibrated
mechanics, not market impact estimates or evidence of real-market optimality.

Install the built SDK and Core wheels with the explicit `planning` extra and the extraction pins NumPy 2.2.6, pandas 3.0.6 and SciPy 1.18.1. From outside the source tree, run the installed interpreter:

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_impact_planning.py" -q -p no:cacheprovider
```

Adapted from [pinned Apache-2.0 source](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/impact-planning.md). Implemented on the unreleased provider B branch; Core source is 0.2.0; whole-provider review and integration remain pending. Consumer cutover is separate.

## Conditional cash and full-session replanning

Signed plan cash assumes that the proposed sells and buys occur. It is a contingent
net-step projection, never delivered cash or an order reservation. Actual admission
cannot spend unavailable sale proceeds. Finite inventory and sleeve allocation use
stricter prefunding. Keep these domains distinct; do not change the QP cash formula.
The blocked-sale test starts with ten A shares and zero cash: a hypothetical rotation
can plan a sale and purchase, but the blocked actual sale leaves zero cash and ten A.
The next request uses those actual facts and zero sale capacity; it cannot buy B.

`core/tests/test_planning_session.py` uses `sessions.open_session`, a full source-bound
checkpoint and `sessions.restore_session` before replanning. One 100-share fill at
10.05 leaves cash 8995 and transient state 0.1 at exact UTC ns 1767576720000000000.
The decimal hand notional is 1005; the owner's preserved raw binary gross is
1005.0000000000001. Full original/restored checkpoints and final results compare
exactly. The next immediate candidate returns raw quantity 99.99999999999999 (hand optimum 100),
price 10.15 and projected cash 7980;
it changes no live holdings, cash or impact. Later execution must account for decay.

## Multiperiod weight planning

`quant_backtest_core.planning.multiperiod.plan_trades(MultiPeriodRequest(...))`
accepts caller-supplied forecasts and PSD covariances, never constructs estimates.
Weights and costs use fixed decision-NAV units. Costs are
`cost_linear * abs(trade) + 0.5 * cost_quadratic * trade**2` summed over names.
Long-only holdings, budget, per-name/per-step trade caps, boolean tradability,
reserved cash and cumulative estimated costs constrain the path. Expected returns
never fund cash. Decision/forecast clocks reject future forecast availability.
There is no terminal liquidation, shorts, borrowing, exchange queue or automatic
future-data access. Execute only `first_trade`, then replan from delivered state.
SLSQP uses ftol 1e-12/maxiter 2000; failed/nonfinite or residual >1e-7 results raise.
This bounded research interface offers no independent numerical optimum certificate.
Run the installed `core/tests/test_multiperiod.py` and `core/tests/test_planning_session.py`
alongside the impact suite. Generic risk estimation and signed optimizers remain Platform.

## Independent scenario composition

Use the executable [typed-target scenario example](../product/scenarios.md) for independent minute accounts. Forecast and risk estimation remain external; the initial scenario adapter accepts only null risk and the existing target-weights policy. Planned sales do not finance buys: the supplementary actual-owner test blocks only A sales while B remains tradable, and a separately funded B control demonstrates the cash gate. The continuous candidate `99.99999999999999` remains contingent and is not rounded or submitted. Daily-owner variants remain later migration work.

## Installed planner example

Install `[planning]` with the documented extraction pins, then run this synthetic
example. These arrays use the unchanged numerical leaf API; public scenario money
and nanosecond wire values remain strings. The first action is exactly integral
in this fixture. Its cash is conditional on execution, not actual delivered cash.
No order is submitted and no live owner is mutated.

```sh
python -I -B - <<'PY'
import numpy as np
from quant_backtest_core.planning.impact_planning import ImpactPlanningRequest, plan_with_impact

clock = int("1767576540000000000")
request = ImpactPlanningRequest(
    initial_holdings=np.array([0.0]), initial_cash=10000.0,
    unaffected_prices=np.array([10.0]), expected_returns=np.array([[0.1]]),
    covariances=np.array([[[1.0]]]), step_seconds=np.array([]),
    initial_transient=np.array([0.0]), transient=np.array([0.001]),
    decay_seconds=np.array([10.0]), capacity=np.array([[100.0]]),
    risk_aversion=0, decision_ns=clock, forecast_available_ns=clock,
    risk_available_ns=clock, state_available_ns=clock,
)
plan = plan_with_impact(request)
assert plan.first_action == (100.0,)
assert plan.cash == (8995.0,)
print({"first_action": plan.first_action, "conditional_cash": plan.cash,
       "request_digest": plan.request_digest})
PY
```
