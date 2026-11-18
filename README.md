# Quant Backtest Engine

[简体中文](README.zh-CN.md) · [Documentation and interactive examples](https://runchengxie.github.io/quant-backtest-engine/)

Replay historical market data and trading decisions to see what fills, what it costs, and how the account changes. Use the resulting holdings and available cash to make the next decision, or repeat the experiment under different execution conditions.

This is a reusable backtest module for other projects. Supply your own strategy and data, then call it through Rust, the command line or Python. It runs independently of the companion research platform and job runner.

## What you can test

| Question | Available building blocks |
| --- | --- |
| How would orders execute? | Quote-based sessions, L2 depth and trade-event replay, limit orders, cancels and supplied command latency |
| What happens after a partial fill? | Actual holdings and cash, working-order checks and target-position decisions based on account feedback |
| How do costs and constraints change a decision? | Fees, slippage and impact assumptions, discrete portfolio constraints and bounded planning |
| How sensitive is the result? | Independent scenario accounts, supplied market paths, account reconciliation and recovery checks |

Each entry point has its own supported inputs and rules. The [capability guide](docs/capabilities.md) and [execution fidelity guide](docs/product/execution-fidelity.md) describe the Rust and Python implementations separately. Market-impact parameters and real queue positions need their own calibration evidence.

## Run an event-level example

From a Linux source checkout with Rust 1.99 or newer, choose a directory outside the repository for build files.

```sh
export CARGO_TARGET_DIR=/path/to/your/data/engine-build
cargo run --locked -- depth tests/fixtures/depth.json
```

The synthetic account starts with CNY 10,000 and buys five shares across two ask levels. After CNY 0.05 in fees, `account.cash` is `"9949.65"`. Inspect `account.fills`, order statuses and event receipts to follow the result. The example requires no downloaded market data.

For Python installation and verified source-built packages, follow [installation](docs/product/installation.md). The native adapter uses pinned NautilusTrader 0.66.0 for execution and accounting. Python also provides minute/daily execution, planning and scenario interfaces.

## Choose your next step

- [Quick start](docs/quickstart.md) and [Python client](docs/python-client.md) for calling the module.
- [Interactive mechanisms](https://runchengxie.github.io/quant-backtest-engine/learn/) for understanding fills, costs and account feedback.
- [Contracts](docs/product/contracts.md) and [acceptance](docs/product/acceptance.md) for inputs, evidence and remaining validation.
- [Development](docs/development.md) for architecture, tests and language boundaries.

[quant-platform](https://github.com/runchengxie/quant-platform) supplies research workflows. [quant-backtest-runtime](https://github.com/runchengxie/quant-backtest-runtime) manages durable jobs. Both can use this module through explicit interfaces.

## Source layout

`apps/` contains the website, `packages/` the independently built libraries, `tests/` shared acceptance inputs, and `scripts/` maintenance tools. Each package owns its `src/`. See [development](docs/development.md#workspace-layout) for commands and historical reproduction.

## License

LGPL-3.0-only. See [LICENSE](LICENSE), [COPYING](COPYING) and [third-party notices](docs/third-party-notices.md). Dependencies retain their own licenses.
