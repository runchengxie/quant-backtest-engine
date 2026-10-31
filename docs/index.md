# quant-backtest-engine

An independent Rust library and CLI, backed by NautilusTrader. Submit a versioned
request and receive reconciled order, fill, position and cash results. No scheduler
or research platform is required to call the library.

Experimental release: synthetic USD cash equities, L1 quote ticks and market-order
intents. A sizing utility and v2 CNY/USD session ledger add configured T+1, buy lots and quote
permissions. Corporate actions retain the existing Python backend. See
[target sizing](sizing.md), [session replay](sessions.md) and
[migration limits](migration/corporate-action-conformance.md).

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

## Adoption status

Package **0.2.0**, experimental; upstream **0.66.0**. Start with the
[weight-to-ledger walkthrough](tutorial.md), then review [capabilities and tested
consumer combinations](capabilities.md), [correctness evidence](correctness.md),
[measured batch costs](benchmarks.md) and [release instructions](releases.md).
