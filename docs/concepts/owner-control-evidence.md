# Owner-backed execution control evidence

[简体中文](owner-control-evidence.zh-CN.md)

A correct schedule is not sufficient execution evidence. This fixed synthetic
study passes four controls through the existing `MinuteSession` matcher, cash,
fee, T+1, impact and delayed-feedback owner. All 96 unique cases were audited;
104 panel rows retain shared identities. Every one of 232 event-boundary recovery
checks preserves the full financial/policy/impact/delivery state. Completion is
still conditional: rolling does not guarantee liquidation when feedback or
capacity is insufficient. There is no calibrated impact or strategy-profit claim.

## One owner, separated model assumptions

`planning.owner_control_case` builds a synthetic raw-share instrument A. On
2025-01-02 the owner buys Q from initial cash 20Q at external mark 10; liquidation
is on the next day, with eight decision slots four minutes apart. Decisions precede
entry by one minute, each parent has two minutes of life and two fill bars.
Liquidity is 500 shares per exit bar, or zero in the first two outage slots.
Fresh mark-only trailing bars drain delayed reports without extending deadlines.
One-share lots keep this a bounded reference, not full A-share lot/auction realism.

Actual `LinearImpact` has transient `1e-4 * actual_multiplier`, permanent zero
and 300-second decay. It changes owner fill prices once. Buy fee is 3 bp, sell
fee 8 bp including 5 bp tax, with no minimum. These are fixed synthetic assumptions,
not a historical or current statutory fee schedule. Raw valuation marks stay
external and exclude own impact, as declared by the owner.

The LQ planning proxy uses `eta=.5*1e-4*belief_multiplier*240`, risk aversion
`1e-4` and absolute volatility `.01`. This eta matches only an isolated fill in
one bucket; it omits transient cross-fill effects, actual bar timing and fees.
Its risk penalty is not a cash fee. Planned utility and owner execution shortfall
are different quantities. See [analytic/discrete reference](impact-planning.md).

The callback holds only mode, target quantity, participation and belief multiplier.
It cannot read actual-impact or future-liquidity scenario settings. An opaque
full-case hash binds recovery without passing those settings to decision logic.
Forecast volume is fixed before the experiment, not future realized volume.

## Four controls and three panels

- `immediate`: request all delivered holdings in the first exit slot only.
- `open_loop`: submit each initial optimized quantity once, without catch-up.
- `twap`: submit each fixed equal-rate quantity once, without catch-up.
- `rolling`: replan from delivered holdings and remaining slots; no fallback when
  the hard-terminal planner reports infeasibility or numerical failure.

Pending orders or undelivered financial reports gate all new orders. Integer
schedules round cumulative inventory endpoints, retaining the target total.
Target weights encode the desired whole-share position; the owner independently
sizes and validates actual orders. No forced terminal fill is inserted.

| Panel | Fixed dimensions | Rows |
| --- | --- | ---: |
| Impact belief | belief(.5,1,2) × actual(.5,1,2) × four controls |36|
| Capacity | Q(80,400,1200) × participation(.05,.1,.2) × controls |36|
| Feedback | report delay(0,300s) × latency(0,1min) × normal/outage × controls |32|

Defaults are Q400, participation .1, belief=actual=1, no delay and normal liquidity.
Duplicate defaults share case IDs; 104 rows do not represent 104 independent
market samples. All rows are retained; there is no parameter selection or winner.

## Actual owner costs and conditional completion

At the default settings:

| Control | Sold / target | Remaining shares | Exit price shortfall + actual fees, CNY |
| --- | ---: | ---: | --- |
| Immediate |25%|300|1.2543 accrued only; not a full-liquidation comparison|
| Open loop |100%|0|5.5814|
| TWAP |100%|0|5.4603|
| Rolling |100%|0|5.5814|

The planning proxy's optimum need not minimize this different realized cost
functional. This flat-price example also does not measure the value of inventory
risk protection. Compare only completed, valid paths with matching inputs and
terminal state. A partial path cannot win by leaving impact unpaid.

The audit reads original owner tables, without reconstructing a replacement
account. It checks fill/parent quantities and fees, per-bar participation,
release/latency/deadline rules, and every day's cash, NAV, positions and marks
against original fill prefixes. Minute owner `daily.transaction_cost` is cumulative:
use each prefix or final cumulative value, never sum those daily cumulative rows.
Bootstrap costs are separate from exit costs. Exit shortfall is
`sum(q*(10-fill_price)) + sum(exit_fill.transaction_cost)`; neither risk penalty
nor another impact charge is added. Both basis-point costs use benchmark notional: target quantity × 10 or filled
quantity × 10, not actual gross traded amounts. The latter cost is unknown
when there are no exit fills.

## Capacity and feedback can dominate the apparent benefit

The following TWAP completion rates hold only on the fixed normal/no-delay tape:

| Q / initial cash CNY | Participation .05 | .1 | .2 |
| --- | ---: | ---: | ---: |
|80 / 1,600|100%|100%|100%|
|400 / 8,000|100%|100%|100%|
|1200 / 24,000|33.33%|66.67%|100%|

At Q1200 and participation .05/.1, the LQ hard-terminal forecast is infeasible;
open-loop/rolling record planning failures and submit no replacement strategy.
That is a declared limitation, not evidence that zero trading costs are optimal.
These scales are arbitrary reference units, not estimates of market capacity.

For Q400 and participation .1, completion rates in the feedback panel are:

| Report delay | Latency | Liquidity | Immediate | Open loop | TWAP | Rolling |
| --- | --- | --- | ---: | ---: | ---: | ---: |
|0s|0min|Normal|25%|100%|100%|100%|
|0s|0min|Outage|0%|61.75%|75%|100%|
|0s|1min|Normal|12.5%|85%|100%|100%|
|0s|1min|Outage|0%|60%|75%|62.5%|
|300s|0min|Normal|25%|53.75%|50%|79%|
|300s|0min|Outage|0%|29%|37.5%|50%|
|300s|1min|Normal|12.5%|41.5%|50%|25%|
|300s|1min|Outage|0%|29%|37.5%|12.5%|

Waiting for reports prevents sizing against hidden cash/shares, but consumes the
remaining horizon. Some replans then become infeasible. This is one deterministic
stress tape, not a probability estimate or proof that any control is superior.
The partial costs and failure reasons remain visible instead of being dropped.

## Recovery and reproduction

`OwnerLiquidationPolicy` checkpoints bind projected controls, opaque case identity,
policy source through the owner, solver-helper hashes and Python/NumPy/SciPy/Pandas
versions. Restore validates fixed schedule lengths, types and conservation,
failure-state consistency and trace prefixes before owner restore. Hashes detect
changes relative to trusted identity; they are not authentication or timestamping.

Four delayed/outage representative cases are restored at every event boundary,
including live orders and queued reports. Exact parity covers daily/orders/fills/
holdings, pre-finish owner checkpoint, policy state, impact and delivery state.
Separate tests reject changed configuration/dependencies or malformed state and
check that modifying future bars does not alter earlier decisions or fills.

Run in the installed locked Core environment, after freezing the source:

```sh
python -B scripts/verify/export_owner_control.py \
  --output "$DATA_ROOT/quant/quant-backtest-engine/tasks/<task>/run" \
  --code-root "$CODE_ROOT" \
  --data-root "$DATA_ROOT/quant/quant-backtest-engine"
```

Output must be a fresh directory outside source checkouts. Each case retains
original targets/bars/config, lossless owner-wire tables, diagnostics/checkpoint
and metrics. The manifest binds 388 files, all case IDs, source hashes and actual
dependencies. Unexpected audited-case failures remain recorded and make the
exporter exit nonzero. The completed reference run has zero such unavailable
cases: 50 unique paths complete and 46 remain partial. It retains 38 planning-failure
decisions and 56 pending waits; these decisions are not independent trials.

Reference source is `80388e73230fffe94bc164c3255b876dcacd9a2d`; report SHA256
`fe82bb7523c90e7cd9fbfc9c31d17fa57b2656f5d84c726bc6e26c0301833351`.
No raw corporate-action valuation, research promotion, production scheduling,
queue-fill calibration or live-money conclusion is supplied by this reference.
