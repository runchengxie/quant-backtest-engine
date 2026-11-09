# PAPER account event lifecycle

[简体中文](paper-account-events.zh-CN.md)

Implemented in the provider B worktree; unreleased until gate B merge. Core source is 0.2.0; merged release availability and consumer cutover remain separate. [Pinned original documentation](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/contracts/paper-account-events.md).

`quant_backtest_core.backtest.account_events.AccountEventAdapter` adds raw integer-share
orders, financial report delays, corporate actions and checkpoint/resume to
`project_paper_account`. The caller supplies modeled fills. This is a PAPER
accounting adapter, with no matching engine, executable broker interface or
historical calibration claim.

Initialize with `PaperState` and `EventAccountConfig(source_binding=...,
input_binding=...)`. Bind the source revision/configuration and the input manifest
identity explicitly. The adapter checks identity equality when restoring; these
identities and a content digest cannot prove that upstream inputs were available
historically.

## Financial state and clocks

`actual` contains modeled truth, while `visible` contains delivered financial
snapshots. Both are immutable `PaperState` values. `actual_nav`, `visible_nav` and
`visible_receivables` include signed dividend entitlements after ex and before pay.
`actual_margin` and `visible_margin` expose required margin, excess, breach and
the declared equity basis `nav_including_signed_receivables`.
`pending`, `entitlements`, `reductions` and `visible_reductions` return copies.
Strategy decisions use `visible`, `visible_receivables`, `pending` and
`available_cash(as_of)`. They must never read `actual` or `actual_nav` as strategy
information.

Every `AccountEvent(event_id, kind, occurred_at, available_at, payload)` has aware
`pandas.Timestamp` clocks and a finite JSON-native payload. Occurrence clocks are
nondecreasing; report availability cannot precede occurrence. New events cannot
retroactively introduce reports before the last delivery clock. Replaying the
same event ID and complete payload is a no-op, including after restore. Reusing
an ID with different content fails. Invalid events leave all state unchanged.
Admission, cancellation requests, new event occurrences and deliveries share a
monotone control clock. An offline driver applies truth events before advancing
the strategy/control clock for that tick. It cannot admit a future order and
then backfill an earlier split, or introduce an earlier occurrence after a later
strategy decision. Reports already queued may remain undelivered across ticks.
Identical event replay is still a no-op across this clock boundary.

Call `apply(event)` to advance truth, then `deliver(as_of)` to release known
reports. Delivery uses a conservative causal prefix: if an older financial
report is delayed, later account snapshots wait for it even when their own
availability clocks are earlier. This prevents later full snapshots from leaking
unreported fills, and prevents old reports from reverting newer state. This
policy applies to financial reports; callers may deliver independent market
quotes directly to their strategy. `visible.as_of` remains the endpoint of the
latest delivered snapshot, while `deliver` records its own monotone clock.

## Supplied projections and fills

For `projection`, the payload is `{"inputs": ...}`. For `fill`, add `order_id`,
signed integer `quantity`, positive `price`, optional nonnegative `fee`, optional
`fill_id`, and optional aware ISO `cash_available_at`. The inputs object is:

```python
{
    "price_basis": "raw",
    "marks": {"A": {"value": 10.0, "available_at": "2025-01-01T00:00:00+00:00"}},
    "borrow_rates": {"A": {"value": 0.10, "available_at": "2025-01-01T00:00:00+00:00"}},
    "locate_quantities": {"A": {"value": 100, "available_at": "2025-01-01T00:00:00+00:00"}},
    "financing_rate": {"value": 0.05, "available_at": "2025-01-01T00:00:00+00:00"},
}
```

Every projection/fill calls the existing projector, including zero-duration
events. Opening rates, endpoint marks and endpoint locate observations follow
its freshness and availability checks. Financing and borrow costs accrue once
over each actual state interval. Funding basis and house margin are explicit
configuration assumptions. A raw price declaration is required; adjusted price
declarations fail. The caller remains responsible for accurate price provenance.

Fills must respect the admitted limit, side, remaining quantity and admission
clock. `fill_id` identifies one economic execution across multiple report IDs;
consistent duplicates have no economic effect, while changed payloads fail.
Without `fill_id`, the stable event ID identifies the execution.

## Orders and reservations

`admit_order(order_id, symbol, quantity, limit_price, as_of=...,
locate_quantity=..., risk_limit=..., risk_price=None, fee_budget=0)` accepts
caller-known locate units and a
currency-denominated gross exposure cap. Admission uses delivered inventory,
cash and marks. Opposite orders do not net cash or risk reservations. Visible
long inventory can back sell orders once; pending buys and hidden fills cannot
supply long inventory or locate capacity. Covers need cash but no new locates.

Cash reservation is positive remaining quantity times limit price plus the
declared remaining fee budget. Gross-risk reservation is absolute remaining
quantity times `risk_price`, added conservatively to visible gross inventory.
The risk price defaults to the limit and must be at least that limit. A supplied
fill above the risk price fails, including a short sale price improvement above
its admitted exposure bound. Set a wider explicit risk price to permit that
modeled outcome. Fill fees must fit the remaining declared fee budget; unused
budget releases with completion or cancellation reports. A configurable credit
limit is an assumed cash facility, not broker buying power.

`request_cancel(order_id, as_of=...)` preserves every reservation. A modeled
`cancel_ack` event with `order_id` must follow the request, and releases pending
reservations only when delivered. Partial fill reports release only their filled
portion. A full fill can win the cancellation race; a later acknowledgement
then leaves the completed order closed. A fill after a cancellation acknowledgement
fails. There is no wall-clock reservation expiry.

## Corporate actions, reductions and settlement

Project to the action clock before a corporate event. This prevents applying new
inventory to a previous accrual interval. Corporate payloads are:

| Kind | Payload and behavior |
| --- | --- |
| `dividend_record` | `entitlement_id`, `symbol`; record signed actual shares. |
| `dividend_ex` | `entitlement_id`, nonnegative per-record-share `amount`; create signed receivable/payable. |
| `dividend_pay` | `entitlement_id`; settle that recorded entitlement into cash exactly once. |
| `split` | `symbol`, positive integer `numerator`, `denominator`, `price_basis="raw"`; scale raw positions and open order quantities/remaining/locate units, and divide raw marks/limit prices by the ratio. |
| `recall` | `symbol`; emit a required cover intent for actual short exposure. |

Entitlements survive position closes, including a cover before ex or pay.
Recorded quantities remain in their original record-date units across a later
split; the declared dividend amount must use the same units. Any fractional
position, pending quantity or locate units produced by a split reject the entire
action. There is no implicit rounding or cash-in-lieu model. Integer quantities
are bounded by the exact integer range of the underlying floating-point
projector.
Split reports retain the IDs of orders open when the split occurred. Delayed
delivery transforms only those orders; an order admitted afterward never receives
that earlier split retroactively, including admission at the same timestamp.

Borrow breaches from projections and margin breaches after every event emit
explicit `required` reduction intents. Margin equity includes all signed ex-date
receivables and payables, so an unpaid short dividend can trigger a breach
immediately at ex. A required margin intent becomes `resolved` only when a later
actual state restores margin excess to zero or above. Its delivered status
changes with the corresponding report. These are diagnostic instructions, not filled covers or an
execution plan. Failed fills preserve exposure. The caller chooses any reduction
orders and supplies their modeled fills; intent history is retained.

Cash settlement is independent of inventory sale eligibility. Positive sale
proceeds have an explicit availability timestamp: a fill override, or fill time
plus configured `settlement_delay_seconds` (default zero). This is a generic
calendar-second policy, not A-share T+1. `available_cash` subtracts delivered
unsettled proceeds, modeled short-proceeds restrictions and pending buy reserves.
Each sale records its proceeds and the part opening new short exposure, with
fees allocated in proportion to shares. Unsettled short proceeds and modeled
short collateral overlap within the same symbol: reserve their union rather than
subtracting both in full. The overlap is the smaller of unsettled opening-short
proceeds and that symbol's current marked collateral requirement. Symbols do not
share this overlap. This is an explicit pooled collateral assumption, not a
claim about a broker's tax lots or settlement terms.
Book cash/NAV recognize supplied fills immediately. Accrual uses the selected
projector cash funding basis, not a separate settlement-credit facility model.

## Checkpoints

`checkpoint()` returns deterministic JSON-native schema version 2 content,
configuration and SHA-256 content digest. It includes actual/visible states,
pending orders and reservations, unreported snapshots, processed event and fill
IDs, signed entitlements, reduction history, settlement records and clocks.
`AccountEventAdapter.restore(checkpoint, config)` checks schema, complete digest
and exact configuration/source/input bindings before resuming. Serialized
checkpoints may be stored under the owning project's data root. A checkpoint is
a reproducibility record, not an authenticated statement about external markets.

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
