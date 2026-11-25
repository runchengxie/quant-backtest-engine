# Owner-backed execution control evidence

## Scope and chosen approach

Implement the four agreed tasks in one additive synthetic Engine study: controller
through owner matching/accounting, impact-belief stress, capital/participation
capacity curves, and checkpoint/causal-feedback acceptance. Existing `MinuteSession`
owns fills, cash, fees, T+1, impact and recovery. No financial ledger, production
policy default, alpha model, real market payload or private research is added.

A new standalone matcher would duplicate ownership. Treating rate-cost eta as the
existing propagator coefficient would misstate the models. Instead bridge the
existing discrete LQ schedule to complete target weights consumed by the minute
owner, recording continuous intent, integer target, submitted owner order, fills
and actual account outputs separately. Synthetic-only APIs are named as such.

## Fixed experiment

One raw-share instrument A, flat external price10, daily T+1. Owner first buys Q
on2025-01-02 from cash20Q; liquidation takes place2025-01-03. Eight decision slots
four minutes apart; decision one minute before entry; two one-minute bars per
2minute order lifetime; latency0 or1minute; one-share lots. Bootstrap liquidity
is ample. Exit baseline volume500 per bar, up/down limits15/5, raw marks remain
external and exclude own impact. A zero-volume outage affects the first two exit
slots only. Sufficient trailing marks drain reports but cannot extend order life.

Fixed fees: buy3bp, sell8bp including5bp tax, zero minimum; these are synthetic
constants, not a historical fee schedule. Actual LinearImpact: transient
1e-4 times actual_multiplier, permanent0, decay300seconds. Planning proxy:
eta=.5*(1e-4*belief_multiplier)*240, risk_aversion1e-4, volatility.01. The eta
conversion matches only an isolated same-bucket fill; transient cross-fill
coupling, fill timing and fees are absent from the LQ proxy and explicitly
remain model misspecification. Risk penalty is never charged to owner cash.
Forecast volume500 per bar and configured participation are known before decisions;
future actual volumes, impact state and hidden financial snapshots are not exposed.

Policies: immediate submits all delivered shares in the first exit slot only;
TWAP/open_loop submit only each fixed scheduled quantity once; rolling replans
from delivered inventory and remaining slots. No retry/catch-up is hidden in
fixed schedules. Pending live orders or undelivered reports prohibit new orders.
Whole-share scheduling is a declared deterministic rounding of cumulative
inventory endpoints; no terminal forced fill or numerical failure fallback.
Weight encoding uses the owner sizing interval for the desired integer target;
owner recomputes and validates the actual order at entry. All choices are logged.

Three prespecified panels, not a Cartesian parameter search:

- Impact: belief_multiplier(.5,1,2) × actual_multiplier(.5,1,2) × four policies.
- Capacity: Q(80,400,1200) × participation(.05,.1,.2) × four policies.
- Feedback: report delay(0,300)seconds × latency(0,1)minute × normal/outage × policies.

Defaults Q400, participation.1, belief=actual1, delay=latency0, normal liquidity.
Thus104 panel rows and96 unique cases; duplicates retain shared identity. Every
planning/owner failure stays in the exported inventory. No winner selected.

## Accounting and acceptance

Metrics audit only owner tables: quantities, filled fraction, remaining shares,
actual fees and exit price shortfall against external10. Separate bootstrap from
exit costs. Owner equity/cash/holdings are reported as owner values, not recreated
as another financial engine. Check share conservation, per-bar participation,
fees and cash consistency. Compare liquidation cost only on completed, valid
same-state paths; partial/failed paths never win by avoiding execution.

Checkpoint the policy schema, configuration, decision log, scheduled state and
code/dependency hashes. Restore validates expected case configuration and helper
fingerprints before MinuteSession restore. Verify all event boundaries for four
representative delayed/outage policies, including live orders and queued reports.
Compare daily/orders/fills/holdings, policy state, impact, owner final checkpoint
before finish and pending delivery states. Changed inputs/config/dependency or
malformed checkpoints reject. A future-bar mutation must not alter earlier
policy decisions/orders/fills. Fixed model clocks are not future observations.

## Deliverables and limits

Add controller/fixtures/metrics as small separate modules, meaningful hand and
fault tests, external manifest-bound all-case output plus recovery evidence, and
paired EN/ZH concept documentation. Old scientific inputs and defaults stay
unchanged. Synthetic price stress is not market impact calibration, exchange
queue realism, raw corporate-action repair or profitable strategy evidence.
