# Execution comparison implementation plan

[简体中文](2026-11-24-execution-comparison.zh-CN.md)

Goal: compare a discrete hard-terminal liquidation reference with the continuous
LQ solution, and compare fixed synthetic execution schedules on one cost functional.

Architecture/spec: `planning/liquidation_discrete.py` owns scalar nonnegative
sales, per-period quantity capacity, and zero terminal inventory. Its objective is
sum eta*q²/dt + lambda*sigma²*dt*(x²+x*y+y²)/3. NumPy/SciPy are optional planning
dependencies. Reject nonfinite, unrepresentable and infeasible inputs. No forecasts
are estimated: supplied alpha is identically zero. Existing multiperiod planning
has different terminal/impact semantics and is not relabeled as this model.

`planning/execution_comparison.py` compares immediate, open-loop, TWAP and rolling
optimization using identical target, horizon, cost, risk, forecast and capacities.
All realized fills obey supplied actual capacity. Rolling replans delivered inventory;
infeasible replans record failure and submit zero, without terminal repair.
Results distinguish planned/realized cost and residual/completion. These are schedule
costs, not cash accounting or net returns: existing financial owners do not implement
this exact quadratic rate functional.

Fixed scenarios: target 10, horizon 4, eight periods, volatility 1, eta {0.5,2},
risk {0,1}, forecast capacity 2 shares/period, actual capacity either all 2 or
{0,0,2,2,2,2,2,2}. Retain all 32 policy rows, including incomplete outcomes.
Convergence uses 8/16/32/64 periods with target 3, horizon 2, eta 1.5,
volatility 0.8 and risk {0,0.7}; compare objective and inventory against analytic
reference with identical units and factors, plus independent stationarity checks.

Review focus: invalid scalars, capacity infeasibility, saturated capacity, zero
inventory, solver failure; test each explicitly. Reject unsupported shapes.

- [ ] Add failing objective/convergence/validation tests, observe missing module.
- [ ] Implement discrete optimizer and objective; test independent finite-difference stationarity.
- [ ] Add failing paired-study tests; implement fixed scenarios and delivered-state replay.
- [ ] Run full Python, Rust, ownership and strict paired docs validation; record external results.
- [ ] Commit and request independent review through coordinator.

## Reading and reproducing the evidence

Open-loop and TWAP submit each fixed scheduled quantity exactly once. Clipped quantities
are not retried. Rolling receives the same initial capacity forecast and observes
past delivered fills; it does not receive future actual capacities. Its advantage
under outages measures adaptation as well as schedule choice. There is no random
price process, estimated alpha, strategy selection or calibrated market claim.

An incomplete path's realized cost is only its accrued integral; never rank it
against a completed hard-terminal objective. Compare objectives only for completed
paths with the same initial state and horizon. Completion is conditional on the
capacity scenario, not a probability or guarantee.

Run `python scripts/verify/export_execution_comparison.py --output <external.json>`
in the locked installed Core environment. The export records the source revision,
source hashes, every fixed row, analytic cost, objective excess and maximum node
inventory error. There is no hidden cost-factor adjustment. Zero-risk single-period
inventory 3, horizon 2 and eta 1.5 costs 6.75. Positive-risk objective errors should
shrink approximately fourfold when the uniform grid doubles; numerical tolerance
sets a floor for the zero-risk solution.

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
