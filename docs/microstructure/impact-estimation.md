# Execution impact estimation

[简体中文](impact-estimation.zh-CN.md)

`quant_backtest_core.microstructure.impact` owns the deterministic execution
estimator, implemented in the provider B worktree and **unreleased until gate B
merge**. It uses the same `ReplaySession` and `ReplayFill` as [LOB replay](replay.md).
The [actual original code](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/packages/microstructure/src/ticknet/simulator/impact.py)
is the historical reference; there was no dedicated original impact-estimation
page. The transfer preserves that module's bodies, including `_mid`, unchanged.

## Schedule and units

`ExecutionSchedule(side, total_volume, n_child=1, start_time_ms=1000,
end_time_ms=5000)` uses side +1 for buys and -1 for sells, integer raw shares,
integer replay milliseconds and raw integer price units. It is a limit-order
schedule, not a guaranteed-fill market order or a calibrated trading algorithm.

Volumes split by integer division, with the remainder in the last child. Child
clock i is `start_time_ms + max(end_time_ms-start_time_ms, 1)*i//n_child`.
Before running replay, each child limit is selected from the current opposing
best quote. If absent, use `int(mid_before + 1)` for buys or
`int(mid_before - 1)` for sells. These limits are selected while queueing children,
not by advancing the market to each child's future clock. The entire queued
session then runs, including background events beyond the schedule's end.

Validation and operation order are preserved: Python per-fill capability first,
then schedule side/volume/count, pending queue validation, start/child clocks,
pre-execution midpoint, fill cursor and child reservations. Reserved `IMPACT{i}`
IDs avoid queued history, reserved names and live-book IDs. Explicit resting order
ID uniqueness remains the caller's obligation; reservation does not harden legacy
duplicate-ID admission or remove its characterized backend divergence.

```python
from quant_backtest_core.microstructure.impact import ExecutionSchedule, ImpactEstimator
from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.replay import ReplaySession

session = ReplaySession(MatchingEngine(backend="python"), (100, 50), (101, 30))
result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 40))
assert (result.filled_volume, result.unfilled_volume) == (30, 10)
assert result.execution_vwap == 101.0
```

## Actual fills and descriptive shortfall

`ImpactResult` preserves `mid_before`, `mid_after`, direction-adjusted
`slippage_bps`, `filled_volume`, `unfilled_volume=0`, `execution_vwap=None`,
`execution_slippage_bps=None`, and `fills=()` defaults. `fills` contains only new
actual child fills, including passive child fills when matched later in the run;
background-only trades are excluded. Direction chooses the buy or sell ID used
for attribution. Volume sums and the volume-weighted execution price derive from
those exact fills, not an aggregate-trade proxy. Remainders are requested volume
minus attributed filled volume. Successive runs do not double count prior fills.

For positive initial midpoint, midpoint slippage is
`side * (mid_after-mid_before)/mid_before * 10000`; execution slippage is
`side * (execution_vwap/mid_before-1) * 10000`. Units are basis points. Without
fills the VWAP and execution shortfall are `None`, not zero. These values describe
a synthetic replay intervention, not calibrated causal real-market impact.

## Native and empty-book limits

Native replay currently lacks per-fill evidence. Selecting a non-Python engine
raises the original `NotImplementedError` **before** schedule validation, ID
reservation or book mutation. There is no aggregate substitution or silent
fallback. The required-native rejection acceptance uses a real installed native
wheel on Python 3.12 and 3.13; missing optional native execution is not parity.

`_mid` averages both best quotes, uses the sole quote if only one side exists,
and returns raw sentinel **0.0** for an empty book. When the initial midpoint is
nonpositive, legacy midpoint slippage remains **0.0**, and execution shortfall is
unavailable. An empty zero-volume schedule returns zero before/after midpoint
and zero slippage with no price evidence. A buy child may rest at fallback price
1, producing mid_after 1 despite no fills. These sentinels are **not measured zero
market impact**. Consuming the only populated side can also return mid_after 0 with raw
midpoint slippage -10000 bps for a buy or +10000 bps for a sell, even when
execution price equals the starting quote. The unchanged raw outputs are
characterized, not repaired.

The estimator does not debit any account. Midpoint displacement and execution
shortfall are descriptive; do not add them as another cash charge. This is
separate from [LinearImpact and paper-account feedback](../backtest/account-feedback.md),
whose execution-price offsets are already in cash accounting. Fees are charged
once. Learned `generator.py` and the consumer diagnostic `sqrt_law.py` remain
Platform-owned; no calibrated square-root impact law is claimed.

## Verification and ownership

The full eleven original impact cases, two replay-clock admission cases, native
per-fill rejection case and new empty-book characterization transfer together.
Acceptance uses installed regular core wheels outside repositories with
`TICKNET_REQUIRE_RUST=1`, all 15 impact tests and zero native skips. Source/output
parity permits owner identity only; replay arithmetic and price/clock units stay
unchanged. Importing replay/impact requires only the standard library and the base
SDK dependency, not scientific, training, Platform or Runtime packages.
