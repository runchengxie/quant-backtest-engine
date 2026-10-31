# quant-backtest-engine

[Documentation](https://runchengxie.github.io/quant-backtest-engine/) ·
[中文说明](README.zh-CN.md) ·
[中文文档](https://runchengxie.github.io/quant-backtest-engine/index.zh-CN/)

Independent **Rust library and CLI** with a thin adapter to
[NautilusTrader](https://github.com/nautechsystems/nautilus_trader).
Upstream performs execution simulation, fees and cash accounting; this repository
owns a versioned input/output boundary, validation and translation.

**Experimental:** currently supports synthetic USD cash equities, L1 quote ticks and
precomputed market-order intents. Existing Python backends remain compatibility
references. A-share rules, target-weight sizing and a complete daily ledger still
require explicit migration and validation.

## Run the synthetic example

Rust 1.99.0+ is required; NautilusTrader crates are pinned to 0.66.0.

```sh
cargo build --locked
cargo run --locked -- capabilities
cargo run --locked -- run fixtures/roundtrip.json
```

The fixture starts with USD 10,000, buys 10 shares at 10, sells at 12 and charges
10 bps per fill. Expected final cash/equity: **10019.78**, commission: **0.22**.
Financial values are decimal strings and timestamps are explicit UTC nanoseconds.
The CLI emits only result JSON on stdout; errors use stderr and a nonzero exit code.

## Read next

- [Quick start and Rust API](https://runchengxie.github.io/quant-backtest-engine/quickstart/)
- [Request/result contracts](https://runchengxie.github.io/quant-backtest-engine/contracts/)
- [Execution and valuation assumptions](https://runchengxie.github.io/quant-backtest-engine/execution/)
- [Runtime integration](https://runchengxie.github.io/quant-backtest-engine/runtime/)
- [Development and validation](https://runchengxie.github.io/quant-backtest-engine/development/)

The library depends on neither quant-platform nor quant-backtest-runtime. Portfolio
construction belongs to callers; runtime owns queueing, job state, process limits,
cancellation and durable publication. Runtime's opt-in v5 integration preserves
legacy protocols and tests this engine through a pinned real subprocess.

## License

LGPL-3.0-only. See [LICENSE](LICENSE), [COPYING](COPYING) and
[third-party notices](docs/third-party-notices.md). Upstream dependencies retain their
own copyright and licensing obligations.
