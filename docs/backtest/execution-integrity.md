# Recorded-fill integrity and pooled-account exploration

[简体中文](execution-integrity.zh-CN.md)

`quant_backtest_core.evidence.execution_integrity` reconstructs recorded-fill
cash and raw integer shares; it never matches or submits orders. It compares
every clock prefix, including paths whose endpoints agree. A matching endpoint
cannot certify an interior account history.

```python
from decimal import Decimal
from quant_backtest_core.evidence.execution_integrity import fill_prefixes, exit_wealth

fills = [dict(fill_id="f", ts_ns=10, symbol="A", side="buy",
              quantity="4", price="101.4", fee="1")]
prefix = fill_prefixes(fills, "1000")
assert prefix[-1]["cash"] == Decimal("593.4")
wealth = exit_wealth("593.4", {"A": 4}, {"A": {"price": "100", "ts_ns": 10}},
                     as_of_ns=21, max_mark_age_ns=10)
assert wealth["marked_wealth"] is None
assert wealth["cash_realized_wealth"] is None
```

`fill_prefixes(fills, initial_cash, initial_quantities=None)` requires unique
source fill IDs, positive integer shares and prices, nonnegative fees, finite
Decimal-compatible values and a long-only book. Fills at one integer UTC
nanosecond clock are grouped before comparison. The initial row has clock zero.
Its legacy clock input is an integer; the public product envelope uses exact
string clocks, with conversion at its boundary. No float clock conversion is allowed.

`compare_prefixes(left, right, *, cash_atol="0.00000001")` returns every divergent
clock with left/right cash and quantities. Arithmetic uses an isolated
64-significant-digit Decimal context; inexact results raise ValueError rather
than inheriting caller precision. These are evidence reconstructions, not
observations of an upstream owner's hidden state. Cash admission, T+1, queue
priority and fee correctness require separate evidence from that owner.

`exit_wealth(cash, quantities, marks, *, as_of_ns, max_mark_age_ns, receivable="0")`
retains prices, mark clocks, freshness bounds, cash, receivables and residual
shares. Stale, future, missing or zero held marks leave marked wealth unknown.
Unsold shares are never realized cash. Cash-realized wealth is available only
with zero inventory and receivables. Supplied marks are not executable quotes.

## Capital flows

`evidence.capital_returns.CapitalObservation` records NAV before an external
flow, the signed flow, and NAV after it. `capital_performance(initial_nav,
start_ns, observations)` requires complete strictly ordered positive valuations
and verifies the flow identity. Deposits/withdrawals are separate from PnL.

```python
from quant_backtest_core.evidence.capital_returns import CapitalObservation, capital_performance

result = capital_performance(1000, 0, [
    CapitalObservation(1, 1000, 1000, 2000),
    CapitalObservation(2, 1900, -500, 1400),
])
assert result["net_external_flow"] == 500
assert result["net_monetary_gain"] == -100
assert round(result["time_weighted_return"], 8) == -0.05
assert result["money_weighted_irr"] is None
```

Linked time-weighted return and approximate elapsed-time Modified Dietz return
remain distinct. Full redemption is a boundary, not a silently continued series.
The implementation makes no unique IRR claim.

Pooled sleeve planning and real-backend comparison experiments remain in Platform
until their own migration tasks. This leaf provides no sleeve allocation,
broker coordination or account execution backend. The old account implementation
and checkpoints remain pinned. [Source notices](../third-party-notices.md).
