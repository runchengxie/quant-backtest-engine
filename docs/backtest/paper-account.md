# Signed paper account

[简体中文](paper-account.zh-CN.md)

Implemented in the provider B worktree; unreleased until gate B merge. Core remains version 0.1.0 during transfer. [Pinned original documentation](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/paper-account.md).

`quant_backtest_core.backtest.paper_account.project_paper_account` projects an opening
`PaperState` through explicit costs and supplied endpoint fills, then marks its
signed inventory. Feed its returned `state` into the next projection and its
`weights` into a caller's next portfolio decision. It never constructs fills,
certifies executable prices, or reconstructs brokerage terms.

All timestamps must be timezone-aware `pandas.Timestamp` objects. A fill's
`timestamp` must equal the projection's `as_of`; multiple fills are processed in
supplied order at that endpoint. Intraperiod executions require separate account
steps. Marks, annual decimal borrow rates, assumed locate quantities and the
annual decimal financing rate use `Observed(value, available_at)`. `max_age` is an
explicit nonnegative `Timedelta`. Rates must already be available at the opening
state's time; marks and locates must be available at the endpoint. Missing, future,
stale, nonfinite or nonpositive prices fail the projection. Zero held quantities
need no marks. Both opening and newly opened shorts require borrow rates and
locates, including zero-duration steps. A zero borrow rate is an explicit
assumption, never a missing-input fallback.

Cash changes by minus signed fill quantity times price, minus nonnegative fill
fees, minus borrowing and financing costs, plus signed dividend cash. Positive
quantity buys and negative quantity sells. `dividends` supplies nonnegative
per-share endpoint entitlements on opening inventory: long inventory receives
cash and short inventory owes cash. Split an interval if entitlement timing or
inventory changes differ. Do not add cash dividends to a dividend-reinvested
price series unless the research contract explicitly avoids double counting.

Costs accrue on opening balances and opening marks for actual elapsed calendar
days, including fractional days, divided by 365. Borrow costs apply to opening
short marked value. Financing requires an explicit `financing_basis`:

- `cash`: charge on the absolute amount of negative opening cash.
- `unrestricted_cash`: charge on the positive excess of the assumed opening short
  reserve over opening cash. The reserve equals opening short marked value times
  `HouseMargin.short_proceeds_fraction`.

This deliberately simple funding assumption may charge financing with positive
cash. For example, NAV 100 with long value 350, short value 350 and cash 100,
using a restriction fraction of 1, funds a principal of 250. Annual financing and
borrow rates of 36.5% over two days cost 0.5 and 0.7 respectively; unchanged marks
leave NAV 98.8. These are model assumptions, not historical account evidence.

`restricted_proceeds` is the endpoint marked-short reserve diagnostic. Cash
already includes short sale proceeds; this reserve is never subtracted again
from NAV. NAV always equals cash plus signed marked positions. `margin_required`
is long marked value times `long_haircut` plus short marked value times
`short_haircut`; `margin_excess` is NAV less this amount. The caller supplies all
three house assumptions explicitly. A breach is reported without liquidation.
An opening or increasing short cannot exceed its assumed locate quantity cap.
Existing shorts may be covered after a recall; remaining excess appears in
`borrow_breaches`. No real historical locate or broker margin is inferred.

The projection reports cash costs (`borrow_cost`, `financing_cost`, `fill_fees`),
signed `dividend_cash`, `elapsed_days`, and the chosen financing principal/basis.
Gross/net leverage and signed weights divide marked exposure by positive NAV.
For zero or negative NAV, `insolvent` is true and weights/leverage are `None`;
positions remain visible. Arithmetic overflow in any derived balance, cost, exposure,
weight or diagnostic rejects the projection rather than returning infinity. Results always have `paper_only=True` and
`executable=False`. State and weight mappings are immutable copies, so caller
mutation cannot rewrite the accounting history.

The implementation and tests contain only generic mechanisms and synthetic
examples. Strategies, proprietary source data and retained research results
belong to the owning private research project.

## Complete execution recovery

`quant_backtest_core.backtest.checkpoints.ExecutionState` composes this account
with `LinearImpact`, the input cursor, keyed-random seed, policy state and physical
fill deduplication. Its checkpoint contains the full account, including delayed
reports and reservations. Restore must use the exact configuration and input/source
bindings. Impact state alone cannot restore the account. See the [event contract](../contracts/paper-account-events.md#checkpoints).

[External reconciliation](capital-and-reconciliation.md) compares supplied evidence;
[reservations](../contracts/pending-allocation.md) use only delivered holdings.

## Relocated checkpoint identity

Engine account checkpoints use integer schema **2**; composite checkpoints use
**execution-state.v2**. Original Platform schema 1 / execution-state.v1 checkpoints
are rejected unchanged. Retain their full pinned Platform/Runtime/Go environment;
no converter is supplied. The version change and resulting content digests are
identity changes only, with financial state and calculations preserved.

`source_binding` and `input_binding` are caller-attested strings checked with the
entire configuration and content digest. Raw helpers do not measure the loaded
code or authenticate source provenance. Actual source/wheel hashes belong in
installed artifact receipts and product-level provider binding. Copying old
strings does not make an old schema acceptable. Tampering with checkpoint content
or changing configuration/source/input binding rejects restore.
