# Request and result contracts

## Request `engine_request.v1`

See [the complete synthetic request](https://github.com/runchengxie/quant-backtest-engine/blob/main/fixtures/roundtrip.json) and the public
[Rust contract](https://github.com/runchengxie/quant-backtest-engine/blob/main/src/contract.rs). All fields are required; unknown fields fail.

| Field | Meaning |
| --- | --- |
| `initial_cash` | Positive USD decimal string, at most 2 decimal places, <= 10^12 |
| `fee_bps` | Proportional fee in basis points, decimal string from 0 to 10000, <= 4 decimal places |
| `instruments` | Unique symbols with `price_precision` from 0 to 4 |
| `quotes` | `symbol`, `ts_ns`, positive decimal `bid` and `ask` |
| `orders` | Unique `id`, `symbol`, `information_ts_ns`, `side` (`buy`/`sell`), integer-string `quantity` |
| `required_capabilities` | Explicit list; unknown/unsupported capabilities fail |

Symbols and order IDs contain 1 to 40 ASCII letters, digits, `_` or `-`.
Quotes must be globally nondecreasing in time, strictly increasing per instrument.
Every instrument requires a quote. Timestamps are UTC nanoseconds after epoch and
no later than 2100-01-01; JSON consumers must preserve 64-bit integers (JavaScript
callers should use a lossless JSON library). Prices are <= 10^6; quantities <= 10^6.
There is one synthetic venue `SIM`, USD currency, cash accounting, netted positions,
unit lots, no starting positions and no short selling. Values outside these bounds
are rejected before upstream constructors are called.

## Result `engine_result.v1`

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
The v1 result records the state at the end of the run. Use the [v2 session ledger](sessions.md)
for daily cash, positions and NAV. Callers calculate Sharpe ratios and drawdowns separately.

The declared capabilities are `quote_market_orders`, `multi_asset`, `final_balances`,
`proportional_fees`. A-share T+1, limit bands, suspension rules, corporate actions,
delistings, multiple currencies, leverage, shorts, limit orders and realistic
capacity constraints are not supported. Do not silently translate those requests.

