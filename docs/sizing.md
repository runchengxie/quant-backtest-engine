# Target-weight quantity planning

`size` converts explicit long-only target weights to an estimated quantity plan using
only supplied as-of prices. It does not execute orders or maintain a second account.

```sh
cargo run --locked -- size fixtures/sizing.json
```

The fixture plans 99 shares from CNY 1000 at reference price 10 and 10 bps fees,
leaving projected cash 9.01. The desired quantity is 100; the result reports the
planned 99 explicitly so fee and lot residuals are visible.

## Contract

`sizing_request.v1` requires `currency` (USD/CNY), `cash`, `fee_bps`,
`information_ts_ns`, and `assets`. Each asset provides `symbol`, `held_quantity`,
`reference_price`, `price_ts_ns`, `target_weight`, and `buy_lot`.
All assets, including assets to liquidate, must be explicit and unique. Weights are
nonnegative and sum to at most one. Prices must be known no later than the information
time. Quantities are integers; buy lots are positive integers. Financial values use
decimal strings and input bounds match the engine's conservative order bounds.

Desired quantity is target weight times marked equity divided by the reference price,
rounded down to a buy lot. Sells are planned first, then buys in stable symbol order.
Upstream currency rounding is used for estimated notional and proportional fees.
The output reports marked equity, projected cash, quantity intents and desired/planned
quantities per asset. Full liquidation can sell an existing odd lot; buy quantities
always respect the configured buy lot.

## Estimates and sequencing

Projected sale proceeds can fund planned buys. Callers must execute/settle sells before
relying on their proceeds, then use actual account state for further decisions.
Future execution prices and fills are unknown; the plan does not guarantee target
weights or positive cash after a different realized execution sequence. The engine
always rechecks actual upstream free cash and may deny a planned buy.

Order IDs combine information time and stable asset ordinal. They are scoped to the
plan; do not merge multiple independent plans at the same information time without
assigning distinct IDs. Execution must occur on a quote strictly after the returned
information time. Never size with next-session execution prices.
