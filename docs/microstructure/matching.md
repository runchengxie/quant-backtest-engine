# Microstructure development guide {#microstructure-development-guide}

[简体中文](matching.zh-CN.md)

The standalone deterministic simulator is implemented in this provider B source;
provider B merge and verified wheels are still required before consumer cutover.
It preserves the pinned Platform arithmetic and integer price/quantity/time contracts.
It is a low-level LOB API, not a registered ProductManifest financial backend.

## Code layout {#code-layout}

`quant_backtest_core.microstructure.matching` owns `LimitOrderBook`, `MatchingEngine`,
`Fill` and `Trade`; `pack` owns `SimulatorEvent`, `SimulatorPack`, and
`build_simulator_pack`; `ordering` owns `sort_simulator_events` and provenance;
`correctness.replay_and_compare` compares reconstructed snapshots. Missing target
sides remain not comparable, not a successful empty book match.

Prices remain integer cents, quantities integer shares and simulator clocks integer
milliseconds. These clocks are not the ProductManifest UTC nanosecond envelope.
Price priority and FIFO preserve original aggregate trade rounding (the final fill
price is the aggregate trade price), per-fill prices, partial cancellation and
legacy duplicate-ID behavior. Callers should supply distinct IDs: duplicate resting
IDs are not rejected and can alias cancellation lookup; no deduplication is implied.
Duplicate-ID cancellation is not a parity-supported contract: Python indexes the
last duplicate, while native cancellation selects the first matching queue entry.
For two same-price orders of 5 and 7 shares under one ID, cancelling 3 then cancelling
the ID leaves Python empty but native with 7 shares no longer indexed by that ID.
This historical difference is retained and tested; supply unique resting IDs.
Neither `SimulatorPack` / `build_simulator_pack` nor `ReplaySession` rejects
duplicate explicit IDs. `reserve_order_id` protects generated candidates only.
Unique explicit resting IDs remain the caller’s responsibility; strict admission
would be a separate behavior-changing design, not part of this extraction.

```python
from quant_backtest_core.microstructure.matching import MatchingEngine

engine = MatchingEngine(backend="python")
engine.apply_order("sell", -1, 101, 10)
trade = engine.apply_order("buy", 1, 101, 4)
assert trade.fills[0].volume == 4
assert engine.lob.best_ask() == (101, 6)
```

At equal clocks, single-channel complete exchange sequences sort by sequence then
source index; mixed channels or absent sequences retain source order. Exact equal
keys retain input order. Snapshots follow non-snapshots in the same clock bucket.
This is not evidence of a total exchange order across channels or a complete feed.

## Local checks {#local-checks}

Run `uv run --project core --locked pytest core/tests/test_microstructure*.py -q`.
Native cases skip only when the optional wheel is absent; set `TICKNET_REQUIRE_RUST=1`
for the required native profile. See [native builds](../development/microstructure-rust.md)
and [replay](replay.md). Tests use synthetic fixtures only.

[Original source and license](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/packages/microstructure)
remain Apache-2.0. Learned `OrderGenerator`, models, datasets, Torch and eventstream
training remain Platform; nothing here supplies a calibrated endogenous market.
