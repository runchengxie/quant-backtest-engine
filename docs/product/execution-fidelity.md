# Execution fidelity and production acceptance

[简体中文](execution-fidelity.zh-CN.md)

Use the existing financial owners and verify the exact adapter used by each run.
There is no production integration with HftBacktest or Backtrader. The current
Nautilus adapter remains an L1 session implementation; upstream L2, queue and
latency facilities are not automatically product capabilities.

## Current implementation

| Area | Available evidence | Remaining gate |
| --- | --- | --- |
| Separate Python book | Price/time FIFO, per-fill evidence, multi-level walking and remaining quantity | Exchange-specific order types and real queue-position calibration |
| Optional PyO3 book | Explicit backend, aggregate executions and book ticks | No complete per-fill evidence; unsuitable for acceptance requiring it |
| Minute execution | Actual account ownership and delayed reports | No network cancellation latency or exchange queue model |
| Nautilus adapter | Pinned 0.66.0, L1_MBP, explicit liquidity consumption | Product depth input, command latency configuration, queue contract and exact ledger acceptance |
| Depth reconstruction diagnostic | Snapshot-seeded comparison of each supplied top-N level | Complete exchange-feed normalization and identity-aware historical queue reconstruction |
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

## Queue and timing hand checks

`core/tests/test_execution_fidelity.py` checks supplied arrival ordering against
hand-computed outcomes. An order arriving after a trade misses that queue
opportunity; an in-flight cancel can lose to an earlier arriving trade. Multi-level
fills preserve exact prices and quantities. These tests validate the matching
primitive under supplied ordering. They do not implement a network latency model
or establish real queue position from aggregate L2 data.

```sh
PYTHONPATH=core/src:python/src python -m pytest \
  core/tests/test_depth_audit.py core/tests/test_execution_fidelity.py \
  core/tests/test_microstructure_matching.py -q -p no:cacheprovider
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

`examples/diagnostics/compare_queue.py` requires a separate environment with
`hftbacktest==2.4.4`, Python 3.13 and this source's microstructure package on
`PYTHONPATH`. It fails on a different comparator version. No optional comparator
imports enter the Engine package or production dependency graph.

```sh
PYTHONPATH=core/src:python/src python examples/diagnostics/compare_queue.py
```

The hand oracle supplies 5 shares ahead of a 3-share passive order and an
aggressive quantity of 7. At a synthetic send clock of 110 ns, an arrival delay of
1 ns produces 2 filled shares; a delay of 150 ns misses the trade at 200 ns and
produces zero. HftBacktest uses its risk-averse queue and partial-fill exchange;
the separate Python book is given the corresponding arrival ordering. This is a
single-order queue comparison, not a common historical-feed or account-parity
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
