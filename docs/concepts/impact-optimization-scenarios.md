# Impact and discrete optimization: synthetic checks

Language: English · [简体中文](impact-optimization-scenarios.zh-CN.md)

Two opt-in experimental modules make a narrow set of assumptions inspectable.
They do not change historical replay, production accounting or the optimizer
registry. Implementation and synthetic checks are available; real historical
validation and actual-fill calibration have not been performed.

## Permanent impact sensitivity

`quant_backtest_core.backtest.impact_scenarios.linear_impact_scenario` accepts a signed
share path at one fixed unaffected price, starting with zero inventory and zero
price displacement. Prices are currency/share; the permanent and temporary
coefficients are currency/share²; `fee_per_share` is currency/share. Outputs are
cash change (currency), inventory (shares), displacement (currency/share), and
individual fills. These quantities are not NAV fractions.

For inventory `x` before a slice `q`, execution price is
`p + permanent*x + permanent*q/2 + temporary*q`. The new displacement is
`permanent*(x+q)`. Cash changes by `-q*execution_price-fee_per_share*abs(q)`.
The half-slice term integrates the linear permanent curve: total permanent
cash expenditure is `permanent*Q²/2` starting flat, and zero for a closed round
trip. Temporary expenditure is `temporary*sum(q²)`. Thus nonnegative
coefficients cannot manufacture round-trip profit at a constant unaffected price.
Changing slice sizes changes temporary costs, with no modeled time or liquidity.

The model never rewrites historical prices and never charges displacement again
as a separate cash fee. It returns no marked NAV. Any future NAV integration
would require an explicit reference-price convention to avoid counting the same
impact twice. This is an uncalibrated sensitivity oracle, not credible historical
counterfactual execution, and does not model recovery, cross-impact, bid/ask,
liquidity, information effects, or endogenous market responses. Invalid or
nonpositive modeled prices are rejected.

## Existing cost accounting audit

This historical audit remains a Platform boundary; Engine does not own the legacy
NAV handlers described here. [Pinned original audit](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/impact-optimization-scenarios.md#existing-cost-accounting-audit).

The legacy cost and slippage `cost(...)` contracts return fractions of portfolio
value, not total account amounts or per-share premiums. In execution simulation,
`_quote_trade_fee` forms trade weights as `notional/portfolio_value`, multiplies
slippage's returned fraction by portfolio value once, and adds it to the cost
breakdown. NAV order handlers debit reference fill notional plus `total_cost`
for buys (reference proceeds minus costs for sells). These handlers do not also
shift execution prices for that modeled slippage. `CostEvidence` records account
amounts and is descriptive, not an additional cash debit instruction.

A detailed fee model can include spread/slippage bps while a separate slippage
model adds another amount. This is deliberately additive implementation behavior;
it can economically double-model the same spread if configured carelessly. The
bucket name `temporary_impact` alone does not establish measured market impact.
This audit does not establish absence of overlap in every backend or strategy
configuration, and no existing accounting semantics were changed.

## Continuous baseline and discrete oracle

The existing Platform-owned SLSQP risk backend is checked against an analytic two-asset convex
quadratic risk plus quadratic previous-weight penalty. That penalty is a regularizer,
not calibrated transaction costs. PSD covariance, nonnegative quadratic penalties,
and linear constraints preserve convexity. Solver success and feasibility do not
constitute an independent global optimality certificate. Existing `optimal`
diagnostics retain their historical meaning; these additions do not upgrade them.

`quant_backtest_core.planning.discrete_oracle.enumerate_lot_portfolios` minimizes
sum of squared share-target errors over a bounded, buy-only integer lot grid.
It starts with cash only; it cannot fund purchases from unfilled sells. Per-asset
nonzero orders pay `max(minimum_commission, proportional_commission*notional)`;
zero orders pay zero. Cash budget includes all those fees. Budget, fees and objective comparisons use
exact rational arithmetic from decimal strings of inputs; returned float amounts
are display values. Thus `0.1 + 0.2` of asset costs fits a `0.3` budget. Residual cash is
allowed. This fixed minimum creates a discontinuity at zero; lots introduce
integer decisions. Market impact is not inherently nonconvex.

Results include quantities, objective, spent cash, number of enumerated states,
and candidate feasibility. A feasible supplied rounded/heuristic portfolio gets
an absolute objective gap relative to the exhaustive optimum; an infeasible
candidate gets no gap. `optimal_exhaustive` covers only this finite domain,
objective and fee rule. `search_limit` rejects oversized search before
enumeration, returning no solution, objective or certificate. Inputs are validated;
there is no borrowing, risk budget, covariance, initial holdings, sell side,
tax-lot handling or global production MIQP solver. Commission is charged once
per asset order, not per fill or across broker order groups.

A synthetic example with prices `(6,4)`, share targets `(1.5,1.5)`, one-share lots,
maximum lots `(3,3)`, cash `14`, and minimum commission `1` selects `(1,1)`:
spend `12`, objective `0.5`. Rounded `(2,1)` exceeds budget; feasible `(0,2)` has
objective `2.5`, hence gap `2`. These are synthetic correctness examples, not
performance claims or realistic portfolio recommendations.

Install the built SDK/Core wheels with `planning` and NumPy 2.2.6, pandas 3.0.6,
SciPy 1.18.1. Run from outside the source tree:

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_discrete_oracle.py" "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_impact_scenarios.py" -q -p no:cacheprovider
```

The retained general risk optimizer test belongs to [pinned Platform tests](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/tests/test_impact_optimization_scenarios.py).
All fixtures are synthetic. The two pure helpers themselves use the standard library;
planning's numerical extra supports the separate continuous interfaces. This is
unreleased provider B code, Core 0.1.0 until Task 11; consumer migration is separate.
Adapted from the pinned Platform Apache-2.0 source above. The Chinese counterpart is
new; there was no historical Chinese scenario route.

Related primary research (background, not claims of equivalent implementation):
[Boyd et al., Multi-Period Trading via Convex Optimization](https://web.stanford.edu/~boyd/papers/cvx_portfolio.html)
and [Lobo, Fazel and Boyd, Portfolio optimization with linear and fixed transaction costs](https://stanford.edu/~boyd/papers/portfolio.html).
