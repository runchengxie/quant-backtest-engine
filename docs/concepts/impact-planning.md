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

`packages/core/tests/test_impact_planning.py` includes independent hand solutions, capacity and
alpha sensitivity, cash reservations, locked inventory, exact request binding,
owner matching and restoration, and failure rejection. It checks share-unit and
currency scaling, decaying round trips, and same-clock half-own-increment slicing.
Slicing invariance concerns economic impact cost, not identical conservative cash
envelopes under different capacity partitions. Inputs are synthetic, uncalibrated
mechanics, not market impact estimates or evidence of real-market optimality.

Install the built SDK and Core wheels with the explicit `planning` extra and the extraction pins NumPy 2.2.6, pandas 3.0.6 and SciPy 1.18.1. From outside the source tree, run the installed interpreter:

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/packages/core/tests/test_impact_planning.py" -q -p no:cacheprovider
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

`packages/core/tests/test_planning_session.py` uses `sessions.open_session`, a full source-bound
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
Run the installed `packages/core/tests/test_multiperiod.py` and `packages/core/tests/test_planning_session.py`
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

## Continuous-control reference and decision roadmap

Engine already has multi-period planning: `planning.multiperiod` and
`planning.impact_planning` implement bounded numerical planning with supplied
forecasts; the latter includes transient impact and conservative cash bounds.
Execute only a first action after owner checks, then replan. This is the MPC
interpretation described by [Boyd et al., Multi-Period Trading via Convex
Optimization](https://web.stanford.edu/~boyd/papers/cvx_portfolio.html), not a
promise that Engine estimates forecasts.

The independent standard-library module
`quant_backtest_core.planning.liquidation_reference` supplies an analytic
single-asset continuous-control benchmark. Its objective is

```text
min integral from 0 to T of [eta*v(t)^2 + lambda*sigma^2*x(t)^2] dt
subject to x'(t)=-v(t), x(0)=X>=0, x(T)=0.
```

Here time is seconds, inventory is raw shares, volatility `sigma` is absolute
price volatility in currency/(share*sqrt(second)), `lambda` is 1/currency, and
`eta` is currency*second/share². Objective and remaining value are currency;
`v` is shares/second. There is no hidden factor of one half. This is a simplified
risk/temporary-impact tradeoff in the spirit of [Almgren and Chriss, Optimal
execution of portfolio transactions](https://doi.org/10.21314/JOR.2001.041),
not that paper's complete execution specification or a calibrated market model.

For `a=lambda*sigma²` and `k=sqrt(a/eta)`, the exact mathematical solution is
`x(t)=X*sinh(k*(T-t))/sinh(k*T)` and
`v(t)=X*k*cosh(k*(T-t))/sinh(k*T)`. Its value function for arbitrary current
inventory `y` before maturity is `V(t,y)=A(t)*y²`, where
`A(t)=eta*k*coth(k*(T-t))`. It solves
`V_t + a*y² - V_y²/(4*eta)=0`, or `A'=A²/eta-a`, with a singular
hard-liquidation terminal boundary: `V(T,0)=0` and `V(T,y>0)=infinity`.
With zero risk the limits are TWAP `x=X*(T-t)/T`, `v=X/T`, and
`A=eta/(T-t)`. `evaluate` returns the remaining value **along this initial
optimal path**, not a value for arbitrary realized inventory.

```python
from quant_backtest_core.planning.liquidation_reference import LiquidationModel, evaluate

model = LiquidationModel(100.0, 10.0, 2.0, 0.0, 3.0)
point = evaluate(model, 4.0)
assert (point.inventory, point.sell_rate, point.remaining_value) == (60.0, 10.0, 1200.0)
```

At maturity inventory/value are zero and rate is the left limit. The module
uses exponential ratios to avoid hyperbolic overflow, uses the TWAP limit for
`k*T < 1e-8` (roundoff-scale corrections), and permits tiny late tails to
underflow to zero. Nonfinite or invalid inputs, nonfinite derived coefficient/time
scales, positive subnormal/underflowed risk, initial-rate or initial-cost scale intermediates, and unrepresentable
initial objective or outputs raise `ValueError`.
This is floating-point planning evidence; decimal account arithmetic is unchanged.

| Question | Existing capability / benchmark | Next evidence needed |
| --- | --- | --- |
| Does planning across periods help? | Supplied-forecast multi-period/QP/MPC; synthetic regression cases | Compare out-of-sample first actions with identical forecasts, constraints and owner fills |
| Is an execution cost/risk schedule correct in a tractable case? | Analytic LQ reference; hand-computed zero-risk TWAP, cost quadrature, along-path HJB residual, terminal and extreme-scale tests | Match units and objective before comparing a discretization's convergence |
| Does a transient-impact planner match the reference? | Different model: per-fill transient costs include `k*q²/2`, decay and state | Do not equate that coefficient with rate-cost `eta`; derive the time-step conversion and remove transient/cash/forecast differences first |
| Are stochastic control or general HJB PDEs solved? | Not implemented; the reference is a closed-form special case | Specify state, actions, stochastic dynamics, boundaries and independent convergence checks before adding a solver |
| Should market-making quotes use this schedule? | No quote/fill-arrival model in this reference | [Avellaneda–Stoikov](https://math.nyu.edu/inmemoriam/avellaneda/HighFrequencyTrading.pdf) concerns inventory-sensitive bid/ask quoting and arrival intensities; validate that separate market-making problem explicitly |

The next useful step is benchmark agreement and sensitivity analysis with
synthetic coefficients. Any empirical parameter estimation stays outside this
reference. It adds no cash ledger, execution fills, alpha learning, lots,
participation limits, fees, permanent impact, transient-impact state, or
production-order integration. Passing these tests proves this bounded example;
it provides no general HJB optimality certificate or realized-profit claim.

## Discrete convergence and paired schedule evidence

The optional planning module `planning.liquidation_discrete.solve(model, capacities)`
adds a scalar, sell-only, hard-terminal reference. Each capacity is a maximum
quantity for one equal-length period. It rejects infeasible capacities and failed
numerical solutions. For inventory endpoints `x,y` and sale `q=x-y`, its exact
piecewise-linear integral is `eta*q*q/dt + lambda*sigma*sigma*dt*(x*x+x*y+y*y)/3`.
This matches the continuous reference's objective, including every factor. It is
separate from the supplied-forecast transient-impact planner above.

The fixed convergence case uses inventory 3, horizon 2 seconds, eta 1.5,
volatility 0.8. Zero risk gives TWAP with objective 6.75 on all four grids.
At risk aversion 0.7, the analytic objective is 9.245677060235423:

| Periods | Discrete objective excess | Maximum inventory-node error |
| --- | --- | --- |
| 8 | 0.003603958 | 0.000285046 |
| 16 | 0.000902730 | 0.000071120 |
| 32 | 0.000225791 | 0.000017805 |
| 64 | 0.000056455 | 0.000004410 |

Doubling the grid reduces positive-risk objective error approximately fourfold.
These bounded numerical checks are not a general HJB/PDE solver or calibration.

`planning.execution_comparison.fixed_study()` retains 32 prespecified synthetic
rows: target 10, horizon 4 seconds, eight periods, volatility 1, eta 0.5 or 2,
risk aversion 0 or 1, actual capacity either 2 every period or zero for the first
two periods then 2. All policies initially forecast capacity 2 every period and
zero alpha. Open-loop submits the optimized schedule; TWAP submits 1.25 each period.
Both submit each scheduled quantity once and never retry clipped quantities.
Rolling replans from delivered inventory and observes only past fills, without
future actual capacity. Infeasible replans record a failure and submit zero;
there is no forced final sweep.

For eta 0.5 and zero risk, without an outage open-loop, TWAP and rolling complete at cost 12.5.
With the two-period outage, open-loop and TWAP leave 2.5 shares (accrued cost 9.375),
while rolling completes at cost 16.666667. The lower partial cost is **not** a
better liquidation objective. Compare objectives only among completed schedules
with matching initial state and horizon. Rolling's outage result measures
adaptation as well as optimization; completion is conditional on capacity.
At risk 1 without an outage, open-loop and rolling cost 101.571275 versus TWAP
145.833333; this describes the assumed cost functional, not investment returns.

There is no new cash ledger, stochastic price simulation, learned forecast or
net-return claim. Export every row and source identity in the locked installed
Core environment with `python scripts/verify/export_execution_comparison.py
--output <external.json>`. The paired implementation plan at
`docs/superpowers/plans/2026-11-24-execution-comparison.md` records the fixed
protocol before results.

The initial implementation used “once” for a fixed optimized schedule. That arm is
now named `open_loop`. To cover literal immediate execution, `immediate` requests
10 shares in period zero and submits zero thereafter. The same forecast and actual
capacity caps apply, so it fills only 2 shares without an outage (residual 8), or
zero during the initial outage (residual 10). Its intended schedule violates the
forecast capacity: `planned_capacity_feasible=false`, `planned_cost=null`. Every
other arm also reports the capacity feasibility flag. No fictitious full immediate
fill is compared with completed schedules. This corrects the requested policy
scope without changing cost, risk, capacities or the old 24 path outcomes. The
main grid now retains 32 rows and the infeasibility diagnostic retains four rows.

## Owner-backed controls

[Owner-backed execution evidence](owner-control-evidence.md) connects the discrete
control proxy to actual minute matching/accounting, fixed misspecification/capacity
panels and exhaustive recovery checks. Synthetic costs remain distinct from
calibrated market performance.
