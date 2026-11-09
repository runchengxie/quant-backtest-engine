# Shared sleeve allocation and unfinished exits

Language: English · [简体中文](sleeve-allocation.zh-CN.md)

Use `quant_backtest_core.planning.sleeve_allocation` to attribute one batch of
existing shared-account fills to sleeves. Generic `pool_sleeves` target pooling remains Platform-owned. This helper owns no matcher, account, capacity
or impact state. Execution remains with the existing owner. Independent brokers
sharing a venue require a separate model and are unsupported here.

## Declare a batch

Call `net_sleeve_demands(demands, reference_prices=..., policy="pro_rata")`,
then execute its `external_orders` through the owner and call
`allocate_external_fills(net_plan, fills)`. Supply one immutable `SleeveDemand`
per sleeve/symbol, with nonempty identifiers and nonzero signed integer shares.
References are positive raw prices in one common account currency. Exactly the
batch's symbol set must have references. Positive demand buys, negative sells.
All rows for a symbol use one positive integer `lot_size`, default one. Desired
quantities must be exact lots. Fractional entitlements and odd-lot exceptions
are outside this trade contract, even if an execution owner supports them.

Every row declares `inventory`, `sellable`, `locked`, `cash_budget` and
`fee_budget`. `sellable` is settled eligible inventory before the declared lock.
`locked` is a subset of that count: require
`0 <= locked <= sellable <= inventory`. Sale capacity is
`sellable - locked`, rounded down to lots. Map a whole-symbol `QuantityLock`
to `locked=sellable`, including when other inventory is unsettled.
`blocked=True` prohibits both buys and sales, including internal transfers.
Evidence must be valid throughout this batch. Split and replan batches when
restrictions, inventory or reservations change. Demand alone is not evidence
of sellable holdings.

Each cash budget is an exclusive row reservation backed by caller-owned
balances, without reuse for another symbol, sleeve or batch. The caller must
reconcile reservations to its account. A buy also requires `max_buy_price` at
least the reference price. Reserve the whole `fee_budget` first, then cap buying
at `(cash_budget - fee_budget) / max_buy_price`, rounded down to lots.
Sell rows require no maximum buy price and reserve fees from existing cash.
This conservative contract does not finance purchases or fee reservations from
prospective sale proceeds or internal-transfer proceeds. It does not infer
borrowing, corporate entitlements or available cash from strategy intent.

## Internal crossing and external attribution

For each symbol, match the smaller total eligible side. Allocate each side
pro rata in lots: floor exact proportional units, then award the remaining
units by descending fractional remainder, with lexical sleeve-name ties.
An internal share increases buyer inventory and decreases seller inventory at
the declared reference value. Cash transfers cancel exactly. No external fill,
fee, venue capacity or impact is created. At most one residual external order
per symbol remains. Locked or budget-constrained requests remain residuals.

Supply physical fills with `fill_id`, positive UTC `ts_ns`, `symbol`, `side`,
integer positive `quantity`, positive raw `price`, `gross_amount` and `fee`.
The caller binds each ID to physical source evidence, not a repeated state
snapshot. Values normalize through `Decimal(str(value))`, without rounding,
in an exact 64-digit decimal accounting context. Inexact extremes fail.
Gross must equal quantity times price exactly. Fees and fee reservations are
nonnegative whole cents. Cash and gross can retain subcent precision.
An adapter for a binary-float owner must declare any monetary normalization
and preserve source evidence. An inconsistent raw price/gross pair fails.
The helper never silently rounds an owner's cash into a different ledger.

Canonical `(ts_ns, fill_id)` ordering apportions each fill over the remaining
eligible side, using the same lot/remainder rule. Split that fill's actual fee
cents pro rata to its assigned shares, with lexical sleeve ties. Recorded parent
minimum fees are never recalculated. Identical repeated physical identities
count once within the call, while conflicting reports fail. The result retains
normalized consumed fill evidence. Cross-batch identity tracking is caller-owned.

Every actual fill must match the plan's symbol, side, available quantity and
whole lot. Each receiving buy must fit its maximum price. Cumulative allocated
fees and cash debits must fit each row's reservation. An incompatible fill
rejects the entire pure attribution call, preserving all caller inputs and
actual owner fills for reconciliation. It is never clipped, silently dropped,
redistributed to evade a fee reservation or partially committed.

`SleeveAllocation.deltas` contains internal/external quantities, total quantity
and cash deltas, actual allocated fees and signed remaining requested demand.
Sum quantity deltas by symbol to `pooled_quantities`, cash to
`pooled_cash_delta`, and fees to `pooled_fee`. Internal cash sums to zero.
These are batch deltas, not a second lifetime ledger. Add them to supplied
initial sleeve balances to reconstruct the pooled cash and holdings. Lifetime
PnL additionally needs cost bases, marks, entitlements and capital flows from
their owners. Opportunity shortfall is never debited as cash.

## Hand cases and finite horizons

A buyer requesting five shares and a seller offering three at reference ten
transfer three internally: buyer cash minus thirty, seller plus thirty, and
one external buy request for two. A three-share external fill against two
three-share requests allocates two to sleeve `a` and one to `b`. A five-cent
recorded fee splits three cents and two cents, so cash deltas are minus 20.03
and minus 10.02, with residuals one and two shares. No independent rounding is
performed on sleeve gross amounts.

Synthetic owner tests submit a single 1,000-share aggregate order. A 10%
participation cap on a 1,000-share bar fills only 100 shares once. An explicitly
nonzero hypothetical permanent-impact coefficient of 0.002 gives price 10.1,
gross 1,010 and one fee of 1, then permanent state 0.2. Allocation changes none
of that owner state. These are sensitivity mechanics, not calibrated market
impact or historical queue evidence. Zero impact remains the baseline option.

Predeclare the observation horizon and hold, rebalance, exit-only or finite-exit
comparison before execution. A zero target requests disposal, not completion.
A tested owner buys 500 shares at ten with 10,000 initial cash. A supplied lock
blocks the next day's exit. The final day's capacity permits only a 100-share
sale: cash is 6,000 and 400 shares remain. Call the existing
`quant_backtest_core.evidence.execution_integrity.exit_wealth` with owner cash, residual quantities,
receivables and explicit mark timestamps/freshness. A fresh mark of ten gives
marked wealth 10,000 and residual marked value 4,000, but realized cash wealth
is unknown. Missing or stale residual marks make marked wealth unknown too.
Only an empty settled book has `cash_realized_wealth`. Residual marks never
prove executable liquidation proceeds. Locks/notices and impact inputs here
are synthetic, with no broker, borrow or corporate-action calibration claim.

Install the built SDK and Core wheels with the explicit `planning` extra and the extraction pins NumPy 2.2.6, pandas 3.0.6 and SciPy 1.18.1. From outside the source tree, run the installed interpreter:

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_sleeve_allocation.py" -q -p no:cacheprovider
```

Adapted from [pinned Apache-2.0 source](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/sleeve-allocation.md). Implemented on the unreleased provider B branch; Core source is 0.2.0; whole-provider review and integration remain pending. Consumer cutover is separate.
