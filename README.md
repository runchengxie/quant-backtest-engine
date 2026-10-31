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
references. A separate sizing utility and v2 CNY/USD session ledger support configured T+1, buy
lots and quote permissions. Corporate actions and complete market parity remain
explicit migration limits.

## Run the synthetic example

Rust 1.99.0+ is required; NautilusTrader crates are pinned to 0.66.0.

```sh
cargo build --locked
cargo run --locked -- capabilities
cargo run --locked -- validate fixtures/roundtrip.json
cargo run --locked -- run fixtures/roundtrip.json
```

The fixture starts with USD 10,000, buys 10 shares at 10, sells at 12 and charges
10 bps per fill. Expected final cash/equity: **10019.78**, commission: **0.22**.
Financial values are decimal strings and timestamps are explicit UTC nanoseconds.
The CLI emits only result JSON on stdout; errors use stderr and a nonzero exit code.

`validate REQUEST.json` (or `validate -` for stdin) is a pure static operation:
it uses the execution request parser and semantic validator without backtesting.
Input is capped at 1 MiB. Success emits only an `engine_validation.v1` receipt
with `validator_version=1`, `request_schema=engine_request.v1`, `valid=true` and
`input_sha256` for the exact input bytes. Capabilities advertise `validator_version`
separately from simulation capabilities. Malformed, oversized or invalid requests
exit with status 2 and empty stdout; I/O/internal failures use status 1.

## Read next

- [Quick start and Rust API](https://runchengxie.github.io/quant-backtest-engine/quickstart/)
- [Request/result contracts](https://runchengxie.github.io/quant-backtest-engine/contracts/)
- [Execution and valuation assumptions](https://runchengxie.github.io/quant-backtest-engine/execution/)
- [Runtime integration](https://runchengxie.github.io/quant-backtest-engine/runtime/)
- [Development and validation](https://runchengxie.github.io/quant-backtest-engine/development/)

The library depends on neither quant-platform nor quant-backtest-runtime. Portfolio
construction belongs to callers; runtime owns queueing, job state, process limits,
cancellation and durable publication. Runtime's opt-in v5/v6 integrations preserve
legacy protocols and test this engine through pinned real subprocesses.

## License

LGPL-3.0-only. See [LICENSE](LICENSE), [COPYING](COPYING) and
[third-party notices](docs/third-party-notices.md). Upstream dependencies retain their
own copyright and licensing obligations.
