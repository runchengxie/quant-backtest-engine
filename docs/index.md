# quant-backtest-engine

Pass quotes, orders and starting cash to this Rust library or run it from the command line.
The engine calls NautilusTrader to simulate fills, calculate fees and update account
balances, then returns orders, fills and positions. This project validates inputs
and translates between the two interfaces. Requests and results carry schema
versions so callers can check the format they receive.

This experimental release supports synthetic USD cash equities, L1 quote ticks and market-order
intents. A sizing utility and v2 CNY/USD session ledger add configured T+1, buy lots and quote
permissions. Corporate actions retain the existing Python backend. See
[target sizing](sizing.md), [session replay](sessions.md) and
[migration limits](migration/corporate-action-conformance.md).

## Start here

1. [Run the synthetic example](quickstart.md). Check for equity of 10019.78 and fees of 0.22.
2. [Read the contracts](contracts.md). Check the time, decimal and capability requirements.
3. [Understand the simulation](execution.md). Review timing, liquidity and valuation limits.
4. [Run durable jobs](runtime.md). Use opt-in v5 jobs with process limits and validated result publication.

## Names used in these docs

CLI means the command-line program. It reads a JSON request and writes a JSON result.
The Python SDK starts that same executable, validates the result and returns dictionaries.
The separate runtime handles job submission and state, starts engine processes,
applies resource limits and handles timeouts, cancellation and result storage. Local examples can call the CLI directly. quant-platform provides
portfolio construction and analytics, and retains Python backtests for unsupported workflows.

An L1 quote gives the best bid and ask with their displayed quantities, without a
full order book. NAV is cash plus marked position value. One basis point (bps) is
0.01%, so 10 bps is 0.1%. Configured T+1 prevents selling shares bought in the same
session until the next session. A contract specifies fields, types and validation
rules. JSON monetary values use decimal strings such as `"10000.00"` to preserve
precision. Timestamps are integer UTC nanoseconds since the Unix epoch and must
be preserved without rounding.

## Responsibilities

| Component | Owns |
| --- | --- |
| This engine | Stable request/result boundary, validation and upstream translation |
| NautilusTrader | Matching, execution events, fees and account balances |
| quant-platform | Portfolio construction, analytics and existing Python references |
| quant-backtest-runtime | Job state, isolated execution, cancellation and publication |

See [development](development.md) and [third-party notices](third-party-notices.md).

## Adoption status

Package 0.2.0, experimental; upstream 0.66.0. Start with the
[weight-to-ledger walkthrough](tutorial.md), then review [capabilities and tested
consumer combinations](capabilities.md), [correctness evidence](correctness.md),
[measured batch costs](benchmarks.md) and [release instructions](releases.md).
