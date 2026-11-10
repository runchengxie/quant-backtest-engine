# Capacity and Daily NAV Execution Simulation

Language: English · [简体中文](execution-simulation.zh-CN.md)

Core 0.3.0 implements the daily owner graph; release availability still requires merged-source and exact-wheel receipts. Selection, research statistics and bundle publication remain Platform. See [daily inputs](../product/daily-inputs.md).


`quant_backtest_core.daily.execution_sim` provides capacity-limited fills, execution-adjusted daily NAV, and an ideal daily NAV baseline. It is a public subpackage; these objects are not re-exported from the package root.

The simulator is disabled by default. It supports long-only positive target weights. It models research scenarios and does not represent live broker orders, account cash, or broker risk controls.

## Public API

```python
from quant_backtest_core.daily.execution_sim import (
    CorporateAction,
    ExecutionSimConfig,
    PreparedExecutionTables,
    TradeFeeModel,
    UnifiedLedger,
    audit_delisting_exits,
    prepare_execution_tables,
    simulate_capacity_execution,
    simulate_execution_adjusted_nav,
    simulate_ideal_daily_nav,
    to_unified_ledger,
)
```

`simulate_capacity_execution` returns orders, fills, and a summary. `prepare_execution_tables` prepares reusable execution inputs. `simulate_execution_adjusted_nav` also returns daily NAV, cash, and exposure. `simulate_ideal_daily_nav` assumes each rebalance reaches its target immediately and serves as a full-liquidity comparison.

Both result types can be converted with `to_unified_ledger` or their `to_unified_ledger` method. The `UnifiedLedger` contains `targets`, `orders`, `fills`, `daily_positions`, `daily_cash`, `daily_nav`, `cost_breakdown`, and `turnover_breakdown`.

Other public helpers include `SELL_UNTIL_NEXT_REBALANCE`, `build_execution_sim_config`, `required_execution_sim_columns`, `describe_execution_sim_config`, and `describe_trade_fee_model`.

## Configuration

`ExecutionSimConfig` is disabled by default. When enabled, its main defaults are:

| Field | Default | Meaning |
| --- | ---: | --- |
| `portfolio_value` | `1_000_000` | Portfolio notional value |
| `participation_rate` | `0.05` | Maximum daily participation in available liquidity |
| `liquidity_cols` | `("medadv20_amount", "amount")` | Candidate liquidity columns |
| `liquidity_notional_multiplier` | `1.0` | Converts the source liquidity unit to the portfolio notional unit |
| `buy_max_days` | `5` | Maximum waiting period for a buy order |
| `sell_max_days` | `10` | Maximum waiting period for a sell order; `SELL_UNTIL_NEXT_REBALANCE` can wait until the next rebalance |
| `zero_fill_abort_days_buy` | `5` | Abort a buy after this many consecutive zero-fill days; `None` disables the limit |
| `unfilled_buy_action` | `keep_cash` | Keep unfilled buy value in cash |
| `unfilled_sell_action` | `keep_position` | Keep the unfilled position |

For example, TuShare's `amount` is conventionally in thousands of CNY. Set `liquidity_notional_multiplier` to `1_000` when portfolio notional is in CNY. `build_execution_sim_config` reads a configuration mapping, and `required_execution_sim_columns` reports required price and liquidity columns for an enabled simulation.

The optional market-rule fields `round_lot`, `enforce_t1`, `enforce_price_limits`, and `enforce_listing_status` all default to disabled. Callers must supply the relevant raw prices, limit prices, listing status, and buy or sell tradability flags. The simulator does not infer suspension reasons or broker rejection rules.

## Inputs and outputs

Target positions need a rebalance date, entry date, security symbol, and weight. Pricing data needs a trade date, symbol, price column, and configured liquidity columns. Buy and sell tradability can be supplied separately.

`ExecutionSimResult` contains `summary`, `orders`, and `fills`. `ExecutionAdjustedNavResult` also contains `daily`; corporate-action-enabled runs can include `actions` and `holdings`.

## Delisting audit

`audit_delisting_exits` reconstructs simulated shares from `filled_notional` divided by the same-day execution price. It checks that holdings are zero before the delisting date and that there are no fills on or after that date. It raises an error for residual shares, later fills, or missing/invalid execution prices.

This check audits the simulated fills only. It does not establish an exchange cash settlement or account for corporate actions that the input data does not model.

## Corporate actions and price units

`CorporateAction` is an optional caller-normalized event for raw-share accounting. It records cash or additional shares per record-date closing share, along with availability, record, ex, payment, and tradable dates. Pass `price_basis="raw"` when using corporate actions; the simulator rejects a missing raw-price declaration or required settlement dates. `withholding_rate` is an explicit flat analytical rate, not a historical holding-period tax model.

Lot sizes and price limits require consistent real-share and price units. Adjusted-price synthetic shares are not real tradable quantities, and raw limit prices cannot be compared directly with adjusted execution prices. For long histories, validate dividend, split, and other corporate-action treatment separately.

## Interpreting the paths

Use ideal daily NAV to compare against an immediate-fill, full-liquidity scenario. Use execution-adjusted daily NAV to inspect delayed fills, unfilled orders, and transaction-cost drag. Both are research simulations and cannot replace live order state, an account cash ledger, or broker controls.

For the share-ledger `simulate_execution_adjusted_nav` entrypoint, `round_lot` controls buys only. The independent `sell_round_lot` option defaults to `None`, preserving continuous adjusted-share sells. Set a positive integer to floor partial sell fills to that many raw shares after request, liquidity capacity, and T+1 constraints. An integer odd-lot holding can be liquidated only when the entire actual holding fits all three constraints; a capacity- or settlement-limited liquidation remains a partial sell. No tolerance increases executable quantity. The config description serializes this option.

Use raw prices and raw-share quantities with this option. Explicit `price_basis="adjusted"` is rejected; omitted `price_basis` leaves price-unit correctness to the caller. Fractional holdings encountered by a sell raise `ValueError`: settle corporate-action fractions externally rather than silently rounding them. Only floating arithmetic residue within `min(lot_tolerance, 1e-8)` shares is accepted and preserved, never rounded or used to relax capacity. `simulate_capacity_execution` rejects `sell_round_lot` because its weight ledger cannot enforce share lots. This policy is caller-selected and does not infer exchange rules.
