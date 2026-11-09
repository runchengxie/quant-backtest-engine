# Finite inventory and lot comparison

Language: English · [简体中文](discrete-inventory.zh-CN.md)

`quant_backtest_core.planning.discrete_inventory` compares a deterministic feasible
heuristic with a bounded exhaustive reference for a small, declared long-only
inventory problem. These are synthetic planning results. The existing
[buy-only oracle](impact-optimization-scenarios.md) retains its behavior.

## Prefunded cash is the optimization domain

Every buy notional and every nonzero order's fee must fit within supplied cash
minus reserved cash. Planned sale proceeds cannot pay for a buy or even the
sale's own fee. For example, zero cash and a positive minimum fee prevent a sale
in this conservative domain even when its proceeds would exceed that fee.
This policy intentionally excludes useful sale-funded execution sequences.
A finite-domain optimum is an optimum only under this prefunding policy.

`projected_cash` includes assumed sale proceeds and subtracts assumed order
costs. It is a scenario amount, never delivered or available cash.
`unreserved_cash` excludes sale proceeds and existing reservations.
After the execution owner reports actual fills and settlement, submit a new
request using actual holdings, actual available shares and actual cash.
An unfilled or blocked sale cannot change the next request's cash.

## Inputs, objective and quantities

Construct `DiscreteInventoryRequest` and call `solve_discrete_inventory(request)`.
Vectors use declared asset order. `holdings`, `available_sell_shares`,
`locked_shares` and lot bounds are nonnegative integers. Buy trades are bounded
by `max_buy_lots * buy_lot_sizes`. Ordinary sales use `sell_lot_sizes`,
intersect available original inventory with unlocked inventory and prohibit
shorts. Availability must reflect the caller's settlement and T+1 rules.
The optional complete odd-lot exit may sell all original integer holdings only
when all are available and unlocked. Disabling it retains the ordinary sell grid.

`fractional_entitlements` contains separate fractions in [0, 1), preserved
unchanged. They affect tracking error and never become trade variables.
The total target includes those entitlements. Source fractional holdings must
be decomposed exactly before constructing integer holdings.

The objective is the sum across assets of
`tracking_weight * (final_integer_holdings + entitlement - target_shares)²
+ turnover_penalty * abs(trade_shares)`. Weights and penalties are nonnegative.
Defaults are one for tracking weights and zero for turnover penalties.
Tracking terms use squared shares, and turnover penalties use objective units
per share. No covariance, forecast utility, taxes, fractional trading, borrowing
or general nonconvex objective is supported.

Each nonzero asset trade pays
`fixed_fee + max(minimum_fee, proportional_fee * absolute_notional)`.
Zero trades pay zero. Rates are fractions of notional, not basis points.
Fees constrain feasibility, rather than being added to the tracking objective.
All prices, targets, weights, penalties and amounts become exact
`Fraction(str(value))` values, with existing `Fraction` inputs preserved.
A float therefore declares its displayed decimal value, not a binary-money
tolerance. Prices must be positive and all inputs finite.

## Search results and certificates

The heuristic starts at no trade and makes one coordinate pass in declared
asset order, choosing the best feasible quantity on each asset's bounded grid.
It may stop at a local solution. Equal objective values use lexicographically
smaller signed trade tuples for both searches. Its separate evaluation budget
may return a feasible partial pass.

| Reference status | Meaning |
| --- | --- |
| `optimal_exhaustive` | Every state in the stated domain was evaluated. |
| `budget_exhausted` | A prefix was evaluated, retaining the best feasible heuristic or enumerated incumbent. |
| `domain_too_large` | The exhaustive state cap was exceeded, but the bounded heuristic ran. |
| `asset_domain_limit` | An individual grid exceeded its cap before allocation. No plan was constructed. |
| `asset_limit` | The asset cap was exceeded. No plan was constructed. |

`max_assets`, `max_asset_states`, `max_domain_states`,
`max_evaluations` and `max_heuristic_evaluations` are positive integer caps.
Invalid contracts raise `ValueError`. Exhausted or oversized searches never
claim optimality. Supported incomplete searches report the mathematically
valid nonnegative-objective lower bound zero and incumbent objective upper bound.
Complete enumeration reports equal bounds and the heuristic's exact gap.
An unknown gap is `None`, even if an incomplete incumbent attains zero.

Plan amounts and objectives are exact `Fraction` values. For a wire format,
encode `{"numerator": value.numerator, "denominator": value.denominator}`.
Convert to a float only for a deliberately approximate display or compatible
execution API. Do not infer feasibility from rounded display values.

## Independent checks and execution ownership

The public tests enumerate a literal two-asset feasible set and check fee,
lot, lock, entitlement, decimal-boundary and search-cap expectations.
A separate synthetic comparison uses prices (4, 6), targets (1.9, 1.9),
cash 14 and minimum commission 1. The one-pass heuristic buys (2, 0),
spends 9 including fees and leaves 5 cash with squared tracking error 3.62.
The exhaustive solution buys (1, 1), spends 12 including fees and leaves
2 cash with error 1.62. Both selected targets run through the existing public
minute execution owner with one-share lots and matching minimum
commissions. Assertions compare actual fills, turnover, charged fees,
cash, invested value and residual tracking error to literal expectations.
A further owner fixture blocks or fills an inventory sale and replans only from
the actual delivered cash and remaining holdings.

The planner never debits a ledger or matches an order. Owner compatibility
must be checked before submitting targets. In particular, a generic fixed
ticket fee, separate buy/sell grids, corporate entitlements, partial fills or
day-specific fee grouping may differ from an execution owner's supported
semantics. The owner comparison exercises supported minimum-commission
parameters without fixed fees or taxes. Recheck actual costs, lots,
restrictions, cash and residual holdings after execution. No synthetic check
establishes market calibration, executable liquidation or general global
optimality.

The original dated-fee and daily-owner variants of `test_both_plans_use_public_owner_fills_fees_cash_and_residual_tracking` and `test_actual_public_owner_sale_controls_later_buy_funding` remain named Task 14/15 parity obligations at the pinned source below. These minute fixtures retain every literal economic assertion and restore the entire owner before exit; they do not establish daily or dated-fee ownership.

Install the built SDK and Core wheels with the explicit `planning` extra and the extraction pins NumPy 2.2.6, pandas 3.0.6 and SciPy 1.18.1. From outside the source tree, run the installed interpreter:

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_discrete_inventory.py" -q -p no:cacheprovider
```

Adapted from [pinned Apache-2.0 source](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/discrete-inventory.md). Implemented on the unreleased provider B branch; Core source is 0.2.0; whole-provider review and integration remain pending. Consumer cutover is separate.
