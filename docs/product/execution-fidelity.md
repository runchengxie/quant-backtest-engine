# Execution fidelity and production acceptance

[简体中文](execution-fidelity.zh-CN.md)

Use the existing financial owners and verify the exact adapter used by each run.
There is no production integration with HftBacktest or Backtrader. The L1 session adapter and the opt-in native depth adapter have separate input
contracts and acceptance scopes, documented below.

## Native event-depth profile

`rust.nautilus.depth` is an opt-in product backend using `rust-depth.v1` inputs.
The native `engine_depth_request.v1` interface accepts a single instrument,
ordered aggregate depth snapshots, absolute price-level deltas and identified
trade observations. Limit orders, cancels and target-position commands run at
explicit event sequences. NautilusTrader 0.66.0 owns matching, cash and positions.
Target decisions read actual holdings, available cash and working orders.

The profile uses raw shares, CNY and an explicit Asia/Shanghai event calendar.
Native direct requests also accept USD. Fees are proportional and round through
upstream currency amounts. Pending buys reserve a conservative admission budget
computed from upstream orders. This budget is reported separately from cash.

Order and cancel delays are supplied assumptions, bounded to 60 seconds. Native
timer alerts settle positive-delay arrivals between observations without adding
market events. At an arrival sharing a market timestamp, native market processing
precedes that arrival. Source events at equal clocks retain supplied sequence.
This profile requires `ts_ns == available_ns`; delayed market-data reception needs
a separately validated clock profile. An explicit `end_ns` includes command
arrivals, and the final depth mark must be at most 60 seconds old.

Limits are 100,000 events, 100 levels per side per event, one million depth rows
and 10,000 commands. One command is allowed per decision event. A target waits
while another order is working. Portfolio optimization and path construction
remain caller responsibilities. The product rejects corporate actions, T+1,
multiple instruments and policy/model inputs in this profile.

```sh
cargo run --locked -- depth-validate tests/fixtures/depth.json
cargo run --locked -- depth tests/fixtures/depth.json
```

The synthetic example buys two shares at 10 and three at 10.1. Final cash is
9949.65 and fees are 0.05. The SDK exposes `validate_depth` and `run_depth` on a
content-pinned `EngineClient`. Product callers select `rust.nautilus.depth` with
`tests/fixtures/product/rust-depth.json` and its paired `depth-calendar.json`.

Raw results retain native receipts, physical simulated trade identifiers,
observed fill order, decision account states and the input digest. Normalized
product tables expose fills, positions and reports. Other tables are explicitly
unavailable. These tests establish the supplied normalized semantics. Historical
queue position, measured network latency, real-fill calibration and exchange
feed completeness retain separate acceptance gates. Existing L1 sessions and
historical checkpoints keep their original contracts. Runtime admission for this
new backend requires a separately pinned consumer release.

## Current implementation

| Area | Available evidence | Remaining gate |
| --- | --- | --- |
| Separate Python book | Price/time FIFO, per-fill evidence, multi-level walking and remaining quantity | Exchange-specific order types and real queue-position calibration |
| Optional PyO3 book | Explicit backend, aggregate executions and book ticks | No complete per-fill evidence; unsuitable for acceptance requiring it |
| Minute execution | Actual account ownership and delayed reports | No network cancellation latency or exchange queue model |
| Nautilus adapters | Pinned 0.66.0, existing L1 sessions and opt-in L2 depth with command latency and account feedback | Historical queue calibration, exchange parity and Runtime consumer admission |
| Depth reconstruction diagnostic | Snapshot-seeded comparison of each supplied top-N level | Complete exchange-feed normalization and identity-aware historical queue reconstruction |
| Supplied latency replay | Limit/cancel arrival, separate response clocks and FIFO snapshots | Product backend integration, closed-loop scheduling and measured latency calibration |
| Scenario/planning APIs | Independent accounts, bounded search, documented impact assumptions | Actual-fill calibration and economically credible counterfactual path validation |

The pinned Nautilus `SimulatedVenueConfig` includes `queue_position` and
`latency_model`; these are upstream integration opportunities, not acceptance of
this adapter. New product inputs must be versioned, capability-gated and tested
against the same authoritative Nautilus ledger. Preserve existing native wire
schemas and historical checkpoints.

## Snapshot depth audit

`quant_backtest_core.microstructure.depth_audit.audit_depth(pack)` is an opt-in
Python diagnostic. It is separate from the unchanged historical
`correctness.replay_and_compare`, whose empty-start, best-quote-only convention
cannot certify snapshot-to-snapshot depth reconstruction.

Supply `SimulatorPack` with ordered events and two snapshots containing integer
price/volume `bid_levels` and `ask_levels`. This API explicitly assumes ordinary
limit-order rows imply their resulting trades. Trade rows are observations and
are not debited again or independently reconciled. `order_type=0` declares that normalized convention; other
raw exchange encodings require an explicit normalization layer. Cancels follow
the existing pack's full-cancel-by-ID convention.

The starting aggregate depth is seeded without claiming historical order IDs.
Unknown cancellation IDs, sequence discontinuities, cross-channel ties, missing
depth and events sharing either snapshot clock return `not_comparable`. Malformed
prices, duplicate IDs and time reversal raise errors. No sorting or anonymous
FIFO cancellation is silently used to recover a passing comparison.

A match covers only the supplied top N target levels, including price and size.
For an explicitly empty side it checks emptiness. Deeper unreported levels,
hidden orders, queue identity, feed completeness and calibrated latency remain
unverified. Sequence continuity inside the observed interval is not proof of a
complete feed; matching two snapshots cannot detect all missing round trips.

## Supplied command latency replay

`quant_backtest_core.microstructure.latency_replay.replay_commands` starts an empty
Python book and executes supplied limit/cancel commands by arrival time. `Command`
records send time, outbound latency and response latency separately. All clocks
share one run-local integer nanosecond domain in `0..2**63-1`; prices use integer
cents and quantities use integer shares. Equal arrivals use caller-supplied
`sequence`; duplicate arrival/sequence pairs are rejected.

`command-latency.v1` retains a canonical input digest, per-event depth, FIFO
identities and exact per-fill prices/quantities. Each command event response keeps
its effective and delivery clocks separately; delivery can reorder while the
original event snapshot stays fixed. Passive fills are attached to the command
that triggers matching. A separate broker order-notification protocol requires an
upper-layer implementation. The full request is validated before replay. Order
identities remain unique for the full run; full and exact partial cancels are
supported. Missing resting orders and excessive cancels produce `not_resting` and
`cancel_rejected` respectively.

At most 1,000 commands are supported; `max_commands` can set a lower positive
budget. This bounds full per-event queue snapshot growth. Latency values are
caller-supplied and the existing financial owner retains accounting. The separate native depth profile above provides event-level account-feedback targets.
Fitting actual latency distributions retains a separate acceptance gate. Preserve
the implementation revision alongside the input digest.

The queue illustration is generated by `scripts/build/export_event_demo.py` using
this API. The site recomputes outputs and checks source hashes. Four cases cover
timely/late orders and two cancel races. Existing teaching evidence and protocols
remain unchanged.

## Queue and timing hand checks

`packages/core/tests/test_execution_fidelity.py` checks supplied arrival ordering against
hand-computed outcomes. An order arriving after a trade misses that queue
opportunity; an in-flight cancel can lose to an earlier arriving trade. Multi-level
fills preserve exact prices and quantities. These tests validate the matching
primitive under supplied ordering. They do not implement a network latency model
or establish real queue position from aggregate L2 data.

```sh
PYTHONPATH=packages/core/src:packages/python-sdk/src python -m pytest \
  packages/core/tests/test_depth_audit.py packages/core/tests/test_execution_fidelity.py \
  packages/core/tests/test_microstructure_matching.py -q -p no:cacheprovider
```

Use an isolated Python 3.12/3.13 test environment. Production acceptance additionally
requires regular installed-wheel verification, as described in [acceptance](acceptance.md).

## Independent framework comparison

NautilusTrader remains the main native execution foundation. Its upstream
[depth book](https://nautilustrader.io/docs/latest/concepts/order_book/) and
[command latency](https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/)
should be evaluated against the pinned 0.66.0 API before adding another production
backend. These links follow upstream latest documentation and may differ from
the pinned source.

[HftBacktest](https://hftbacktest.readthedocs.io/en/latest/reference/initialization.html)
provides queue and order-latency models useful as an independent comparator.
Its [historical replay assumptions](https://hftbacktest.readthedocs.io/en/latest/order_fill.html)
include limits on the market response to our own orders. A comparator run must
record the exact distribution, input hashes, event clocks, queue model and fill
assumptions. Compare quantities and execution times before P&L; explain differences
rather than requiring two models to agree by construction. Each run has its own
financial owner; never combine two engines' cash ledgers.

[Backtrader](https://www.backtrader.com/docu/) offers a different strategy research
interface, including volume fillers and slippage extensions. No demonstrated gap
in this acceptance requires adding it as a production dependency.

## Reproduce the isolated queue comparison

`packages/core/examples/diagnostics/compare_queue.py` requires a separate environment with
`hftbacktest==2.4.4`, Python 3.13 and this source's microstructure package on
`PYTHONPATH`. It fails on a different comparator version. No optional comparator
imports enter the Engine package or production dependency graph.

```sh
PYTHONPATH=packages/core/src:packages/python-sdk/src python packages/core/examples/diagnostics/compare_queue.py
```

The hand oracle supplies 5 shares ahead of a 3-share passive order and an
aggressive quantity of 7. At a synthetic send clock of 110 ns, an arrival delay of
1 ns produces 2 filled shares; a delay of 150 ns misses the trade at 200 ns and
produces zero. HftBacktest uses its risk-averse queue and partial-fill exchange;
the standalone Python command replay receives the same send and entry-latency values. This is a
single-order queue comparison. The Python book also has 10 shares at 99 to absorb residual selling when our order arrives late. This is not a common historical-feed or account-parity
claim. The script asserts the startup clock and expected quantities and emits
comparator version, input hash, observation clock and remaining quantity. Preserve
the full environment resolution with each run; these nanosecond values are
synthetic and do not estimate real infrastructure latency.

## Gates for the intended CNY 20–50 million use

Total NAV alone cannot establish execution capacity. Record per-name order size,
participation, execution horizon and liquidity cohort for the intended strategy.
The following remain separate acceptance stages:

1. Reconstruct representative supplied depth across sessions. Report uncomparable
   intervals alongside mismatches, data gaps, auction treatment and ordering scope.
2. Validate the selected product adapter end to end with depth inputs, arrival and
   cancellation timing, partial fills, exact fees and authoritative account outputs.
3. Stress participation, delayed responses, spread and impact assumptions. Preserve
   unfilled quantity and explicit opportunity shortfall separately from cash costs.
4. Compare shadow orders against broker/exchange records when available. Estimate
   distributions of fill rate, execution shortfall and latency by liquidity cohort.
5. Before live deployment, validate the actual trading system's exposure limits,
   cancellation/rejection handling, reconciliation and recovery. Engine acceptance
   does not certify a broker connection or authorize live orders.

Synthetic checks establish implementation properties. Historical reconstruction
establishes agreement under a declared feed interpretation. Actual-order calibration
is a later evidence stage. This page does not certify readiness to manage live assets.
