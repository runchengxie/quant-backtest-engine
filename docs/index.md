# quant-backtest-engine

An independent Rust library and CLI, backed by NautilusTrader. Submit a versioned
request and receive reconciled order, fill, position and cash results. No scheduler
or research platform is required to call the library.

Experimental release: synthetic USD cash equities, L1 quote ticks and market-order
intents. A-share rules, target-weight sizing and a complete daily ledger remain
migration work; existing Python backends are preserved as references.

## Start here

1. [Run the synthetic example](quickstart.md): expected equity **10019.78**, fees **0.22**.
2. [Read the contracts](contracts.md): explicit time, decimal values and capabilities.
3. [Understand the simulation](execution.md): timing, liquidity and valuation limits.
4. [Run durable jobs](runtime.md): opt-in v5 jobs with resource and result supervision.

## Responsibilities

| Component | Owns |
| --- | --- |
| This engine | Stable request/result boundary, validation and upstream translation |
| NautilusTrader | Matching, execution events, fees and account balances |
| quant-platform | Portfolio construction, analytics and existing Python references |
| quant-backtest-runtime | Job state, isolated execution, cancellation and publication |

See [development](development.md) and [third-party notices](third-party-notices.md).
