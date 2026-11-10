# Backtest output reference {#backtest-output-reference}

[简体中文](backtest-outputs.zh-CN.md)

The backtest-product-result.v1 envelope references a SHA256-bound daily-owner-result.v1 raw artifact. Available empty tables remain distinct from unavailable evidence. Monetary transport uses non-exponent decimal strings; decision clocks use UTC-nanosecond strings.

Raw output preserves daily/orders/fills/actions/holdings and all eight UnifiedLedger tables. owner_tables and owner_unified_ledger additionally retain column order, dtypes, indices and tagged nonfinite values; normalized unknowns are null. Without an action request, actions/holdings are null.

## Construction-grid comparison {#construction-grid-comparison}

Selection, construction grids, factors and research bundle publication remain Platform.

## Benchmark ladder {#benchmark-ladder}

Research benchmarks, alpha, IC and ex-post risk adjustment are not execution summaries.

## Positions {#positions}

Explicit positions are caller-chosen inputs; Engine does not rerank holdings or construct strategy weights.

## Execution simulation and capacity {#execution-simulation-and-capacity}

Adjusted/sequenced/ideal provide daily, fills, fees and terminal reports. Capacity provides fills and reports only; it does not claim cash/daily/fee ledgers. Admissions, reservations, cash transactions, capital flows and standalone valuations are unavailable. Legacy audit times remain synthetic date labels, not observed intraday clocks.

| Table | Columns |
| --- | --- |
| order | rebalance_date, entry_date, side, symbol, requested_weight, filled_weight, unfilled_weight, requested_notional, filled_notional, unfilled_notional, fill_ratio, status, first_fill_date, last_fill_date, fill_days, max_days, zero_fill_days, participation_rate |
| fill | rebalance_date, entry_date, trade_date, day_number, side, symbol, remaining_before_weight, capacity_weight, filled_weight, capacity_notional, filled_notional, signal_time, decision_time, order_time, fill_time, valuation_time |
| executed_daily | trade_date, executed_return, executed_nav, portfolio_value, cash, invested_value, cash_weight, target_cash_weight, execution_shortfall_cash_weight, gross_exposure, traded_notional, transaction_cost, cost_commission, cost_stamp_tax, cost_transfer_fee, cost_spread, cost_temporary_impact, cost_permanent_impact, cost_opportunity, cost_financing, open_orders |
| nav_order | rebalance_date, entry_date, side, symbol, requested_notional, filled_notional, unfilled_notional, fill_ratio, status, first_fill_date, last_fill_date, closed_date, fill_days, max_days, zero_fill_days, participation_rate |
| nav_fill | rebalance_date, entry_date, trade_date, day_number, side, symbol, remaining_before_notional, capacity_notional, filled_notional, transaction_cost, cost_commission, cost_stamp_tax, cost_transfer_fee, cost_spread, cost_temporary_impact, cost_permanent_impact, cost_opportunity, cost_financing, fee_market, fee_period_start, fee_period_end, fee_order_id, fee_group_id, fee_group_notional_before, fee_group_notional_after, signal_time, decision_time, order_time, fill_time, valuation_time |

UnifiedLedger fields: targets, orders, fills, daily_positions, daily_cash, daily_nav, cost_breakdown and turnover_breakdown. The last two preserve original buy/sell/total cost and filled-notional aggregation without another debit. Inspect corporate-action cash_receivable, stock_receivable_value and lifecycle receipts separately.

Execution summaries report returns only when both opening and closing valuations are complete and external flows are known zero; compounding requires the entire sequence. The supported first opening is finite positive configured cash with no holdings or receivables. A missing mark invalidates both its closing interval and the following opening interval; a recovered current mark alone cannot repair that opening. Raw owner NAV and returns are preserved unchanged. Total fees use known actual-fill commission/stamp/transfer components only; turnover is unknown. Daily aggregates never fill missing execution evidence and opportunity shortfall is never another debit.


## Pure period-leg financial closure (Task 15P)

Task 15P closes a pure-source omission discovered after provider C PR #24. Explicit-input leg construction, state rollover, supplied participation lookup, period aggregation and the separate legacy trade accounting APIs move to Core 0.3.0 unchanged. Every period field/default and the owned CostBreakdown identity remain; unknown diagnostics stay unknown and costs aggregate once. Selection, weight construction, research projection/metrics and orchestration remain Platform. Diagnostic long/short periods add no daily cash, borrow or margin capability. [Exact APIs, compatibility semantics and evidence](../../guides/diagnostic-close-replay.md) describe the boundary. Review/merge and exact follow-up artifacts precede Task 15 consumer resumption, then Astro Task 19; versions alone are not source identity. No PyPI publication.
