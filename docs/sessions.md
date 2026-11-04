# Reconciled session replay

[中文](sessions.zh-CN.md)

`engine_request.v2` adds explicit sessions and raw-price market constraints while
preserving the v1 request/result wire contracts.

```sh
cargo run --locked -- session-capabilities
cargo run --locked -- run fixtures/sessions.json
```

The synthetic CNY example buys 100 at 10, denies a same-day sale under T+1, then sells
at 12 in the next declared session. With 10 bps per fill, first-session cash is 8999,
NAV is 10099, and final cash/NAV is 10197.8 with total commission 2.2.

## Inputs and clock

The required top-level fields are `schema_version`, `currency` (CNY/USD), `price_basis`
(`raw` only), `initial_cash`, `fee_bps`, `enforce_t1`, `instruments`, `sessions`,
`required_capabilities`. Instruments declare symbol, price precision and buy lot.

Each session provides an increasing ISO `session_date`, `open_ts_ns`,
`valuation_ts_ns`, quotes and quantity orders. CNY session dates use Asia/Shanghai.
USD uses UTC as an explicit simulation convention. The caller supplies trading
sessions. The engine does not infer holidays, exchanges or instrument settlement rules.

Quotes declare symbol, time, bid/ask, bid/ask size, `tradable`, `limit_up` and
`limit_down`. Times are nondecreasing and unique per instrument. Every instrument
needs a fresh quote at the common session valuation timestamp, including no-trade
sessions. Stale marks and adjusted-price requests fail. Data sharing a timestamp
stays in one upstream streaming batch. All session quotes must be processed before valuation.
The v2 request and CLI hold the complete input in memory. Library callers can use
the owned session iterator described below.

An order belongs to one session. Its information time is no earlier than the prior
session's valuation and no later than this session's valuation. It becomes eligible
only on a strictly later quote for its own instrument. No implicit next-day retry
occurs. The caller must submit a new intent for a later session.

## Configured trade admission

- Long-only cash account. Actual free cash plus upstream-rounded fee admission.
- Buy quantities must be multiples of the instrument's declared buy lot.
- `tradable=false` denies both sides. Limit-up denies buys and limit-down denies sells.
  These are caller-supplied quote permissions, not limits inferred from prices.
- With `enforce_t1=true`, only prior-session holdings are sellable. Actual fills drive
  eligibility. Outstanding sells reserve it, with unused reservations released on
  upstream denial, rejection, cancellation or expiry. Competing sells cannot reuse it.
- With T+1 disabled, actual buy fills may become sellable within the session.
- Market orders use immediate-or-cancel (IOC). Shares available at the current quote
  can fill and the remainder is canceled. Submit a new order to trade in a later session.
  Quote sizes and upstream liquidity consumption bound displayed liquidity.

Displayed quote liquidity is not daily volume participation. Upstream 0.66.0 can
retain consumed liquidity across identical-size, same-price quotes and reset it when
size changes. No daily ADV/capacity parity is claimed. The uniform fee is caller-supplied.
Exchange-specific stamp duty, minimum fees and historical tax changes are not inferred.

These configurable guards are not a claim of complete A-share market compliance.
[Corporate-action and delisting migration limits](migration/corporate-action-conformance.md)
remain explicit and retain the Python backend.

## Result engine_result.v2

The result declares currency, raw-price basis, valuation timezone and active T+1 flag.
It contains initial cash, final cash/NAV, total commission, actual normalized orders
and fills, actual denial/rejection event reasons, daily balance rows and daily holdings.

Each daily balance records session/date/time, cash, positions value, NAV and that
session's commission. Holdings record quantity, mark and market value. All values
come from upstream cache/account state, with last bid/ask midpoint marks at the
validated valuation boundary. Every row satisfies NAV = cash + positions value.
Finalization must not change completed economic state. Otherwise the run fails.

This is a reconciled session ledger. It does not automatically become the platform's
`execution_aware` bundle. Callers must still provide the required research clock,
producer identity, complete canonical mapping and provenance. v5 runtime jobs remain
v1 snapshot jobs. Use an explicitly compatible runtime job version for v2 results.

## Owned library input

`run_sessions_iter(config, sessions)` accepts `SessionConfig` and an owned
`Iterator<Item = anyhow::Result<MarketSession>> + Send + 'static`. The header has
the v2 request fields except `sessions`; unknown fields are rejected. Construct it
directly for a lazy source, or copy an existing request header with
`SessionConfig::from(&request)`.

```rust
use quant_backtest_engine::{run_sessions_iter, session_contract::SessionConfig};
fn example(request: quant_backtest_engine::session_contract::SessionRequest) -> anyhow::Result<()> {
let config = SessionConfig::from(&request);
let sessions = request.sessions.into_iter().map(Ok);
let result = run_sessions_iter(config, sessions)?;
assert_eq!(result.schema_version, "engine_result.v2");
Ok(()) }
```

This example moves existing sessions. A lazy producer can generate or load each
owned session in its iterator's `next` method. The source runs on a dedicated
worker thread, which also owns the single Nautilus engine until disposal. The call
blocks until completion. Each session is validated, replayed and snapshotted before
the next source item is requested. Empty sources, source errors and invalid late
sessions return `Err` and provide no successful final result. The engine stops
consuming the source at the first error. External side effects in the producer
remain the producer's responsibility.

Quotes and quote admission rules are retained for the current session. The source
must provide a whole session, including complete timestamp groups across symbols.
Global order IDs and cumulative intent metadata remain retained, along with the
collected final orders, fills, ledgers and upstream account/order/position histories.
Memory can grow with these records and with source-owned buffers. This API makes
no bounded total RSS, speedup or restart guarantee. The CLI and Python v2 client
continue to accept complete requests. There is no interactive wire transport or
financial snapshot import.
