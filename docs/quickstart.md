# Quick start

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


[Continue with the target-weight walkthrough](tutorial.md).
