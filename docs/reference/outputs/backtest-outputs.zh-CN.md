# 回测输出参考 {#_1}

[English](backtest-outputs.md)

产品结果 backtest-product-result.v1 引用按 SHA256 绑定的 daily-owner-result.v1 原始结果。标准表明确区分 available 与 unavailable；支持但零行的表不会冒充缺失证据。金额使用不带指数的十进制字符串，决策时钟使用 UTC 纳秒字符串。

原始结果保存 daily/orders/fills/actions/holdings 和全部八张 UnifiedLedger 表；owner_tables 与 owner_unified_ledger 另保留列顺序、dtype、索引和非有限值标签，归一化表中的未知值为 null。没有行动请求时 actions/holdings 为 null。

## 策略构造对照 {#_2}

选股、构造网格、因子和研究报告发布仍在 Platform。

## 基准阶梯 {#benchmark}

研究基准、alpha、IC 和事后风险调整不属于执行摘要。

## 持仓 {#_3}

显式 positions 是调用方选定的输入；引擎不重新排名或计算策略权重。

## 执行模拟与容量 {#_4}

日频 adjusted/sequenced/ideal 提供 daily、fills、fees 和终态 reports；capacity 仅提供 fills 和 reports，不声称现金/每日/费用账本。admissions、reservations、cash 交易流水、capital_flows 和独立 valuations 均不可用。原审计时间仍为合成日期标签，不是实际日内时钟。

| Table | Columns |
| --- | --- |
| order | rebalance_date, entry_date, side, symbol, requested_weight, filled_weight, unfilled_weight, requested_notional, filled_notional, unfilled_notional, fill_ratio, status, first_fill_date, last_fill_date, fill_days, max_days, zero_fill_days, participation_rate |
| fill | rebalance_date, entry_date, trade_date, day_number, side, symbol, remaining_before_weight, capacity_weight, filled_weight, capacity_notional, filled_notional, signal_time, decision_time, order_time, fill_time, valuation_time |
| executed_daily | trade_date, executed_return, executed_nav, portfolio_value, cash, invested_value, cash_weight, target_cash_weight, execution_shortfall_cash_weight, gross_exposure, traded_notional, transaction_cost, cost_commission, cost_stamp_tax, cost_transfer_fee, cost_spread, cost_temporary_impact, cost_permanent_impact, cost_opportunity, cost_financing, open_orders |
| nav_order | rebalance_date, entry_date, side, symbol, requested_notional, filled_notional, unfilled_notional, fill_ratio, status, first_fill_date, last_fill_date, closed_date, fill_days, max_days, zero_fill_days, participation_rate |
| nav_fill | rebalance_date, entry_date, trade_date, day_number, side, symbol, remaining_before_notional, capacity_notional, filled_notional, transaction_cost, cost_commission, cost_stamp_tax, cost_transfer_fee, cost_spread, cost_temporary_impact, cost_permanent_impact, cost_opportunity, cost_financing, fee_market, fee_period_start, fee_period_end, fee_order_id, fee_group_id, fee_group_notional_before, fee_group_notional_after, signal_time, decision_time, order_time, fill_time, valuation_time |

统一账本八表：targets、orders、fills、daily_positions、daily_cash、daily_nav、cost_breakdown、turnover_breakdown。后两者保留按买卖方向及 total 聚合的原成本/成交额；不重新扣费。公司行动的 cash_receivable、stock_receivable_value 和生命周期回执须单独检查。

执行摘要只在期初和期末估值均完整、且已知外部净流入为零时报告收益；全序列完整才复合。首期期初以有限正数的配置现金开始，没有持仓或应收项。缺价使当期的期末和下一期的期初均不完整；当前价格恢复本身不能补齐期初证据。原有净值和收益表保持不变。仅按成交表已知 commission/stamp/transfer 三项求总费用，换手率未知。不以日频汇总补齐缺失成交，也不将机会损失再次扣款。
