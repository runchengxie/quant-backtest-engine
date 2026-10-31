# Independent Rust backtest engine

## Decision and purpose

The owner selected independent engine, runtime and platform repositories and delegated
implementation choices and continued execution on 2026-10-31. Build a reusable Rust
library and CLI that directly depends on NautilusTrader. Other projects should consume
a stable request/result boundary without installing the research platform or scheduler.

## Approaches

Chosen: direct Rust crate integration, retaining upstream execution/accounting.
Alternative: Rust launcher with Python Nautilus adapter, easier access to Python APIs
but an additional interpreter/process protocol. Rejected for this first implementation.
A new simulator or a source-code fork would increase maintenance and is not justified.

## Boundaries

Engine owns validation, instrument/data/order translation, capability declarations and
normalized results. Runtime owns queue, job state, timeout, cancellation and publication.
Platform owns portfolio construction, analytics and the existing Python reference.
No runtime rewrite, automatic replacement of old backends, ML training, private strategy,
real datasets, live trading or distributed scheduling is included in the first release.

## First supported contract

A strict versioned JSON request supplies initial USD cash, synthetic/simple USD equity
instruments on a simulated venue, ordered UTC nanosecond quote ticks, and market-order
intents with an information timestamp. Orders execute only on a later quote, never
against a quote that predates or equals their information timestamp. Multiple instruments
are supported. Monetary prices, quantities and fees use decimal strings. Unknown fields,
unsupported semantics, invalid precision, duplicate IDs, unordered/duplicate instrument
quotes, impossible quantities and invalid timestamps fail before entering the engine.
A batch CLI process handles one request; runtime may run isolated processes concurrently.

The initial order-intent boundary is narrower than portfolio target weights: weight-to-order
translation remains a portfolio responsibility. No A-share T+1, limit bands, corporate
actions, volume participation or short selling is claimed. Requests requiring unsupported
capabilities must fail explicitly. No hidden final liquidation is performed.

## Results

Versioned JSON reports backend/version, declared capabilities, executed orders/fills,
final positions, cash, commission and marked equity. Values come from upstream cache,
accounts and positions, with quote midpoint marking explicitly documented. Stable user
order IDs and deterministic economic output are required; random upstream IDs and wall
clock timings are excluded. Cash plus marked position value must equal equity.
No fill may be fabricated by the adapter. Record unexecuted intents explicitly.

## Validation and delivery

Pin upstream 0.66.0 and Rust 1.99.0 minimum; commit Cargo.lock. Validate hand-calculated
single/multi-asset trades, fees, insufficient cash, no lookahead, open positions,
repeatability, malformed inputs and CLI errors against real upstream execution.
Use cargo fmt, clippy with warnings denied, locked tests and synthetic CLI smoke in CI.
Publish English docs with linked Chinese introduction, upstream notices and limitations.
Use LGPL-3.0-only for this integrated first release to align distribution with the
upstream; include upstream license texts, without claiming legal advice or relicensing it.

## Integration stages

First merge the engine provider. Then add explicit opt-in runtime execution using a
versioned subprocess boundary; keep runtime the sole job-state/publication writer.
Preserve v1-v4 and their fingerprints. Update platform boundary documentation and provide
a compatibility path only where verified. Record exact provider/consumer revisions.
If a legacy contract cannot represent the new result, add a new version rather than
masquerading as a legacy backend. Never publish unverified capability parity.
