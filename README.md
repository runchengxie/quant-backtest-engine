# quant-backtest-engine

[中文说明](README.zh-CN.md)

A reusable **Rust library and CLI** with a thin adapter to
[NautilusTrader](https://github.com/nautechsystems/nautilus_trader).
Nautilus performs execution simulation, order handling, fees and cash accounting.
This repository owns a small versioned input/output boundary, validation and translation.
It does not implement another matching engine.

**Status: experimental.** The first supported scenario is USD cash equities on a
simulated venue, driven by quote ticks and precomputed market-order intents.
This is not yet a replacement for the existing quant-platform execution backends.

## Run

Requires Rust **1.99.0+**. Upstream crates are pinned to **0.66.0** and Cargo.lock
pins transitive dependencies. Linux is the first validated target.

```sh
# Set CARGO_TARGET_DIR to your external build directory if required by your workspace.
cargo build --locked
cargo run --locked -- capabilities
cargo run --locked -- run fixtures/roundtrip.json
```

`run` reads one JSON request file and writes one result JSON document to stdout.
Errors go to stderr with a nonzero exit code. The CLI never writes request files,
databases or result directories. A runtime can capture stdout and publish it under
its own durability and integrity rules. One request is executed per process.

The synthetic fixture starts with USD 10,000, buys 10 shares at 10, sells at 12,
and charges 10 bps on each fill. Expected final cash/equity: **10019.78**;
commission: **0.22**. These values are asserted against real upstream execution.

## Library

```rust,no_run
use quant_backtest_engine::{Request, run};
# fn main() -> anyhow::Result<()> {
let request: Request = serde_json::from_str(
    &std::fs::read_to_string("fixtures/roundtrip.json")?
)?;
let result = run(&request)?;
println!("{}", result.equity);
# Ok(())
# }
```

The synchronous `run` function uses a fresh thread for upstream thread-local state
and disposes the engine after execution, including errors. Repeated calls are tested.
For timeout, memory limits and cancellation use isolated CLI processes supervised
by a runtime. An in-process thread is not a resource or security sandbox.

## Request: `engine_request.v1`

See [the complete synthetic request](fixtures/roundtrip.json) and the public
[Rust contract](src/contract.rs). All fields are required; unknown fields fail.

| Field | Meaning |
| --- | --- |
| `initial_cash` | Positive USD decimal string, at most 2 decimal places, <= 10^12 |
| `fee_bps` | Proportional fee in basis points, decimal string from 0 to 10000, <= 4 decimal places |
| `instruments` | Unique symbols with `price_precision` from 0 to 4 |
| `quotes` | `symbol`, `ts_ns`, positive decimal `bid` and `ask` |
| `orders` | Unique `id`, `symbol`, `information_ts_ns`, `side` (`buy`/`sell`), integer-string `quantity` |
| `required_capabilities` | Explicit list; unknown/unsupported capabilities fail |

Symbols and order IDs contain 1–40 ASCII letters, digits, `_` or `-`.
Quotes must be globally nondecreasing in time, strictly increasing per instrument.
Every instrument requires a quote. Timestamps are UTC nanoseconds after epoch and
no later than 2100-01-01; JSON consumers must preserve 64-bit integers (JavaScript
callers should use a lossless JSON library). Prices are <= 10^6; quantities <= 10^6.
There is one synthetic venue `SIM`, USD currency, cash accounting, netted positions,
unit lots, no starting positions and no short selling. Values outside these bounds
are rejected before upstream constructors are called.

## Timing and execution assumptions

- An intent becomes eligible on the **first quote for its instrument strictly after
  `information_ts_ns`**. It is submitted from that quote callback. Upstream executes
  against its current simulated market. Equal-time information cannot trade that quote.
- At a shared timestamp, quote input order and then order-intent input order determine
  processing order and cash availability. This is part of the reproducibility contract.
- Buy market orders cross the ask; sells cross the bid. This is an L1 quote model,
  not a daily-bar open/close model, volume participation model or order-book replay.
- Quote size is a fixed 1,000,000 shares per side. It is synthetic liquidity;
  **no real capacity or partial-fill realism is claimed**.
- Requests contain precomputed intents, not executable strategies or target weights.
  Portfolio construction and conversion from weights to quantities belong to callers.
- The upstream proportional fee model rounds commission using USD precision.
  A pretrade cash guard uses that same upstream fee function and upstream `deny_order`
  API to reject buys whose notional plus commission exceeds available cash. Buys
  queued in one quote callback reserve this amount; sell proceeds from that callback
  become reusable on a later callback after upstream accounting has processed them.
  This guard addresses upstream 0.66.0 notional-only cash admission, without
  changing matching, fills or account balances.
- No forced liquidation occurs at the end. A remaining position is marked at its
  instrument's last bid/ask midpoint; positions may therefore have stale marks if
  instrument histories end at different times. This is a valuation convention,
  not a claim that liquidation can occur at midpoint.
- Information timestamps are caller assertions. They do not prove that features,
  prices or model training inputs were historically available.

## Result: `engine_result.v1`

The result includes `backend`, `backend_version`, `capabilities`, USD `cash`,
`positions_value`, `equity`, total `commission`, and normalized `orders`, `fills`,
`positions`. Financial numbers are normalized decimal strings (e.g. `10`, not
necessarily `10.00`). Orders preserve caller IDs; fills preserve actual upstream
quantity, price, commission and UTC event timestamp. Economic results exclude
random event IDs, host identity and wall-clock timing, allowing repeat comparisons.

Orders with no eligible later quote are `NOT_SUBMITTED`; submitted orders retain
upstream status such as `FILLED`, `DENIED` or `REJECTED`. A successful process exit
means the simulation completed, not that every order filled. Callers must inspect
order statuses. Result equity equals upstream cash plus marked open position value.
This is a final snapshot, not a time series or a Sharpe/drawdown report.

Declared capabilities: `quote_market_orders`, `multi_asset`, `final_balances`,
`proportional_fees`. A-share T+1, limit bands, suspension rules, corporate actions,
delistings, multiple currencies, leverage, shorts, limit orders and realistic
capacity constraints are **not supported**. Do not silently translate those requests.

## Repository boundaries and adoption

```text
research / platform: portfolio decisions and order intents
                 |
                 v
quant-backtest-engine: stable Rust/JSON boundary -> NautilusTrader
                 ^
                 |
quant-backtest-runtime: job lifecycle, isolated process, publication
```

The engine depends on neither platform nor runtime. Existing Python backends remain
the behavior reference for their own contracts. Consumers opt in explicitly; legacy
requests and fingerprints must remain unchanged. Follow the
[design](docs/superpowers/specs/2026-10-31-independent-engine-design.md) and
[implementation plan](docs/superpowers/plans/2026-10-31-independent-engine.md).

Opt-in runtime integration is available through
[quant-backtest-runtime v5 jobs](https://github.com/runchengxie/quant-backtest-runtime/blob/e4ad3169d1897b93d04c3cb9e8f01c8e32b4a683/docs/development.md#independent-rust-engine-jobs-v5).
It pins executable bytes and immutable inputs, supervises timeout/cancellation, and
publishes a separately verified final snapshot. Runtime CI builds this engine at
`a2dc923b01c46389f090db7865175c5d87b6819c` and tests the real process boundary.

Next stages are broader behavior comparisons and market-specific capabilities only
after explicit tests. Target-weight strategies need a separately specified sizing
interface before automatic migration.

## Validation

```sh
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo run --locked -- run fixtures/roundtrip.json
git diff --check
```

Tests cover strict validation, no lookahead, fees, rejected orders, open/multiple
positions, repeatability and the real CLI protocol. CI runs the same checks.
No performance advantage or production parity is claimed without measurement.

## License

LGPL-3.0-only. See [LICENSE](LICENSE), [COPYING](COPYING) and
[third-party notices](THIRD_PARTY_NOTICES.md). NautilusTrader is an upstream
dependency under its own copyright and LGPL-3.0-only license. Source and notices
must accompany redistributions as required by the applicable licenses; changing
linkage or packaging does not remove those requirements.
