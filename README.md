# quant-backtest-engine

[中文说明](README.zh-CN.md) · [Documentation](https://runchengxie.github.io/quant-backtest-engine/)

Test how a set of stock orders would fill and how they would change an account.
Give this engine quotes, planned orders and starting cash. It returns fills,
fees, positions and account balances. It uses NautilusTrader for execution and
accounting, with a Rust library, command-line tool and independent Python client.

Use it when you already know which orders to test. For a first experiment, the
included synthetic example needs no market data, strategy code or runtime service.

Provider A is implemented in this source tree: the optional Python core 0.1.0 adds
standalone minute sessions, source-bound recovery and transferred financial leaf APIs;
SDK 0.3.0 retains the existing client namespace. Start with the
[optional product installation](docs/product/installation.md) and
[recovery example](docs/product/recovery.md), using exact reviewed source and wheel hashes.
Provider A integration/release verification and Platform/Runtime consumer cutovers are
still pending; this is not a PyPI availability or consumer-release claim.

## Try a small backtest

From a source checkout, use Rust 1.99.0 or newer on Linux. Dependencies are locked,
including NautilusTrader 0.66.0. Choose a build directory outside the checkout.

```sh
export CARGO_TARGET_DIR=/absolute/external/engine-build
cargo run --locked -- run fixtures/roundtrip.json
```

Replace the example build path with your own. The first run compiles the engine.
The fixture starts with USD 10,000, buys 10 shares at 10 and sells them at 12.
After fees, the JSON result has `cash` and `equity` of `"10019.78"` and
`commission` of `"0.22"`. A completed run can still contain rejected orders.
Check order statuses when trying your own inputs.

For a prebuilt executable, follow the [experimental release guide](docs/releases.md).
The documented alpha.2 release includes the static validator. Alpha.1 does not.

## What it covers

This is experimental software for synthetic cash equities and L1 quotes (best bid
and ask). It accepts precomputed market orders. Callers choose trades and build
portfolios. The session interface adds USD/CNY daily account records and explicitly
configured rules such as T+1 and buy lots. The Rust backend does not support corporate actions, delistings or full
market parity. The separate Python minute backend supports explicit corporate-action
tapes within its documented scope. See the [capability matrix](docs/capabilities.md)
before using it for a new scenario.

The engine runs a backtest. [quant-backtest-runtime](https://github.com/runchengxie/quant-backtest-runtime)
adds queues, job status, cancellation, resource limits and saved results.
[quant-platform](https://github.com/runchengxie/quant-platform) retains the Python
backends currently used for compatibility and unsupported scenarios. The [reusable product migration](docs/migration/reusable-product.md) records the
implemented financial owners and remaining consumer gates. Core 0.3.0 adds the independent
[daily execution graph](docs/product/daily-inputs.md); provider C release and consumer
cutover remain gated by review, merge and exact artifact verification.
You can use this engine without either repository.

## Next steps

- [Quick start and Rust API](docs/quickstart.md), or [Python client](docs/python-client.md)
- [Target-weight walkthrough](docs/tutorial.md). Plan orders and inspect a session ledger
- [Contracts](docs/contracts.md) and [execution assumptions](docs/execution.md). Interpret inputs and results
- [Runtime integration](docs/runtime.md). Validate requests and submit engine jobs
- [Benchmarks and profiling](docs/benchmarks.md), or [development checks](docs/development.md)

## License

LGPL-3.0-only. See [LICENSE](LICENSE), [COPYING](COPYING) and
[third-party notices](docs/third-party-notices.md). Upstream dependencies retain
their own copyright and licensing obligations.

Deterministic LOB matching/replay is implemented in provider B source, pending merged release. [LOB Python / optional PyO3 modes](docs/development/microstructure-rust.md).
