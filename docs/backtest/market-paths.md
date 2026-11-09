# Dependent synthetic market paths

Language: English · [简体中文](market-paths.zh-CN.md)

Use `quant_backtest_core.backtest.market_paths` for conditional return and liquidity
paths with common sampled time blocks across assets. These are uncalibrated
synthetic scenarios. Their quantiles describe this generator, not probabilities
of future market outcomes.

```python
import pandas as pd
from quant_backtest_core.backtest.market_paths import (
    MarketPathSpec,
    fit_market_paths,
    generate_market_paths,
)

# training_panel is a balanced synthetic panel with the required columns below.
training_panel = pd.DataFrame([
    dict(symbol=symbol, time=time, open=price, high=price, low=price,
         close=price, volume=100, amount=100 * price)
    for symbol in ["A", "B"]
    for time, price in zip(
        pd.date_range("2026-01-01", periods=3, tz="UTC"), [10.0, 11.0, 8.8]
    )
])
model = fit_market_paths(
    training_panel,
    cutoff=pd.Timestamp("2026-01-31", tz="UTC"),
    spec=MarketPathSpec(block_length=2, seed=7),
)
paths = generate_market_paths(
    model,
    calendar=pd.date_range("2026-02-01", periods=8, tz="UTC"),
    scenario_ids=["illustration-1"],
    initial_prices={"A": 100.0, "B": 200.0},
)
```

## Input and fit contract

Required columns: `symbol,time,open,high,low,close,volume,amount`.
`time` and `cutoff` must be timezone-aware pandas timestamps. Clocks mean
availability and are canonicalized to UTC. Only rows available at or before the
cutoff enter content validation, the frozen snapshot and hashes; all input
clocks must be valid. Extra columns are not consumed or included in identity.

Prices are positive finite raw quote currency per share, volume is finite
nonnegative shares and amount is finite nonnegative quote currency. OHLC must
obey `low <= open,close <= high`. Positive volume requires `amount / volume`
inside the OHLC range. Zero volume requires zero amount; its positive prices
remain known marks, without asserting tradability. Missing or unknown prices
are rejected. Invalid evidence is never clipped or filled.

`missing_policy="reject"` is the only supported policy. Each fitted clock must
have exactly one row for every canonical sorted symbol. Duplicate symbol clocks,
unbalanced panels and fewer than `block_length + 1` training clocks fail.
The first clock is a preceding-close anchor, not a sampled return observation.

`FrozenPathModel` contains immutable nested tuples and a frozen specification,
not a shared DataFrame. `source_hash` binds canonical consumed values, asset
order and availability clocks. `model_hash` also binds the UTC cutoff,
specification, declared units and generator version `common-moving-block.v1`.
Input ordering, equivalent timezone representations and numeric dtype do not
define distinct data identities. Future rows do not change model identity.
Hashes do not attest external data provenance or a source repository revision;
retain that revision in the consuming run's provenance.

## Generation and identities

`generate_market_paths(model, calendar, scenario_ids, initial_prices)` returns a
dictionary from scenario identity to DataFrame. The calendar must be nonempty,
strictly increasing, unique, aware and entirely after the fit cutoff. Initial
prices must be finite and positive for exactly the fitted symbols, and mean the
close immediately preceding the first generated bar. Scenario identifiers must
be unique nonempty strings; an empty list returns an empty mapping.

The generator samples uniformly from eligible fixed-length, nonwrapping moving
blocks of aligned observations. SHA-256 keys bind model identity, seed, scenario
identity and block ordinal. Every asset uses the same block index. Each sampled
OHLC value is multiplied by
`generated_previous_close / sampled_previous_close`. Sampled volume is retained;
amount is scaled by the same price factor, retaining sampled VWAP relative to
prices. Zero volume and amount remain zero. Source VWAP validation uses exact
float inequalities. Generated VWAP arithmetic alone may fall outside an OHLC
boundary by at most both four ULPs of that boundary (using `math.ulp(boundary)`)
and eight machine epsilons relative error, with no absolute tolerance floor.
The relative cap prevents a large percentage allowance near subnormal zero.
Values remain unmodified: no clipping or amount correction occurs. Positive
volume still requires positive finite VWAP. Material discrepancies, including
unrepresentable amount underflow, and other nonfinite or incoherent output fail
explicitly. The `vwap_coherence` attribute records this numerical contract.

Within blocks, source return/liquidity order and cross-asset pairing are
preserved. Continuity is lost at boundaries; exact long-horizon dependence is
not preserved. Calendar intervals come from the caller: observation order, not
source wall-clock spacing, is retained. The generator models neither continuous
paths between observations nor endogenous market response.

Rows are ordered by calendar then canonical asset. Each has `event_id`,
`sampled_block_id`, `source_time`, `block_offset` and `block_boundary`. Block
identity includes scenario and ordinal, so repeated draws remain separate
blocks. `generation_hash` binds model, scenario and canonical initial prices.
Event identity binds that generation hash, output ordinal, UTC clock and symbol.
Changing anchors changes evidence identity without changing sampled blocks. Scenario batching/order and initial-price mapping order do not affect
paths. Extending an unchanged calendar preserves its prefix. Identical calls
have identical canonical frame serialization, without a guarantee about pickle
bytes across pandas versions.

Frame attributes record synthetic scope, evidence class, source/model/generation hashes, cutoff, units,
seed, scenario, block policy, initial prices and continuity limitation. Preserve
attributes or export them alongside rows; CSV alone loses them. Keep attempted
scenarios and failures in the consuming trial registry. A repeated deterministic
path is a reproduction, not a new independent market sample.

## Execution boundary

These are return/liquidity paths only. Corporate actions, price limits and
tradability semantics are absent, explicitly recorded in metadata. Extra source
columns do not supply them. Before execution, the consumer must supply and
validate a consistent synthetic execution contract, reject unsupported paths
and recompute affected features, labels and decisions. The existing account
and matcher own fills, accounting and fees. This module adds no simulator,
calibration or out-of-sample claim.


## Standalone stress and impact leaves

Install the core `scenario` extra for market paths and `JointStress` /
`stress_bars`. Stress keeps the supplied daily limits, clips the synthetic OHLC
and VWAP to them, and floors reduced volume to shares. `keyed_uniform` draws are
keyed by seed, symbol, UTC clock and stream, so row order does not change the shock.
Risk and impact multipliers are explicit caller inputs; this leaf does not run a
risk estimator or change an account.

`quant_backtest_core.backtest.impact.LinearImpact` uses price units per signed
share and elapsed seconds on one clock. Its transient state decays exponentially;
the permanent state does not decay. Each fill price includes half its current
linear increment, so same-clock splitting cannot reduce modeled cost.
`preview` does not mutate state; `execute` and `offset` advance that symbol's
state. Clocks cannot go backwards. Checkpoint/restore retains coefficients and
symbol state, but this does not make a legacy account checkpoint portable.
Instantiate separate models and accounts for separate scenarios.

`backtest.impact_scenarios.linear_impact_scenario` is a separate nondecaying
sensitivity calculation at a fixed unaffected price. Permanent and temporary
coefficients use currency/share²; temporary cost is quadratic per slice, with
no time or volume calibration. Negative execution prices are rejected.
Fees are separate currency amounts. These are uncalibrated sensitivities,
not empirical impact estimates or probabilities.

```python
from quant_backtest_core.backtest.impact_scenarios import linear_impact_scenario

result = linear_impact_scenario(
    [4, -4], unaffected_price=100, permanent=0.5,
    temporary=0.1, fee_per_share=0.25,
)
assert [fill.execution_price for fill in result.fills] == [101.4, 100.6]
assert [fill.fee for fill in result.fills] == [1, 1]
assert round(result.cash_change, 8) == -5.2
```

The Engine leaf has its own module identity. Existing Platform minute owners,
source-hashed impact bindings and pinned legacy environments stay unchanged
until their consumer gate. A source/model hash alone does not authorize restore
into another financial owner. See [source notices](../third-party-notices.md).

## Execute independent target scenarios

The [scenario runner](../product/scenarios.md) consumes external execution-ready target artifacts through a fixed minute profile. It preserves explicit tradability, limits, calendars and tapes; a generated path does not supply these missing semantics automatically. Fixed and recomputed modes are explicit. Bar-close availability is a declared synthetic convention, base/transformation hashes are declared lineage, and repeated paths are not independent observations.
