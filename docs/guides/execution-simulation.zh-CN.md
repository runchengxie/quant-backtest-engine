# 执行容量与每日净值模拟 {#_1}

语言：简体中文 · [English](execution-simulation.md)

Core 0.3.0 日频图已实现；发布仍以合并提交和精确 wheel 收据为准。选股、研究统计和报告发布留在 Platform。见[日频输入](../product/daily-inputs.zh-CN.md)。


`quant_backtest_core.daily.execution_sim` 提供容量成交、执行后每日净值和理想每日净值三类模拟。该子包具有独立公开入口，当前没有从包根重新导出。

`CorporateAction` 用于可选的原始价格公司行为账本。它记录现金应收、送转股应收及实际结算日，要求调用者显式提供规范化事件和 `price_basis="raw"`。缺少结算日期或原始价格标记时，模拟会阻断。

## 入口 {#_2}

```python
from quant_backtest_core.daily.execution_sim import (
    ExecutionSimConfig,
    simulate_capacity_execution,
    simulate_execution_adjusted_nav,
    simulate_ideal_daily_nav,
    PreparedExecutionTables,
    to_unified_ledger,
    UnifiedLedger,
)
```

- `simulate_capacity_execution` 输出订单、成交和汇总。`prepare_execution_tables` 预先整理可复用的执行数据表
- `simulate_execution_adjusted_nav` 输出每日净值、订单、成交和汇总
- `simulate_ideal_daily_nav` 假设目标仓位立即完成，用作充分流动性对照
- `to_unified_ledger` 把模拟结果适配为路线图定义的八个统一账本字段，也可通过 `ExecutionSimResult.to_unified_ledger` 与 `ExecutionAdjustedNavResult.to_unified_ledger` 方法调用
- `UnifiedLedger` 是统一账本的数据容器，包含 `targets`、`orders`、`fills`、`daily_positions`、`daily_cash`、`daily_nav`、`cost_breakdown` 和 `turnover_breakdown`

## 配置 {#_3}

`ExecutionSimConfig` 默认关闭。启用后的主要默认值见下表。

| 参数 | 默认值 | 含义 |
| --- | --- | --- |
| `portfolio_value` | 1,000,000 | 组合名义规模 |
| `participation_rate` | 0.05 | 单日成交参与率 |
| `liquidity_cols` | `medadv20_amount`、`amount` | 容量约束使用的流动性列 |
| `liquidity_notional_multiplier` | 1.0 | 将流动性列换算为组合名义货币单位的乘数，Tushare `amount` 为千元时应设为 1,000 |
| `buy_max_days` | 5 | 买单最长等待天数 |
| `sell_max_days` | 10 | 卖单最长等待天数，也可用 `SELL_UNTIL_NEXT_REBALANCE` 延续到下一次调仓 |
| `zero_fill_abort_days_buy` | 5 | 连续零成交后的买单终止天数 |
| `unfilled_buy_action` | `keep_cash` | 未成交买单保留现金 |
| `unfilled_sell_action` | `keep_position` | 未成交卖单保留持仓 |

`build_execution_sim_config` 负责读取配置映射，`required_execution_sim_columns` 返回启用模拟后需要的价格和流动性列。

`audit_delisting_exits` 使用成交名义金额和同日执行价重建模拟股数，核对退市日前仓位归零，且退市当日及之后没有成交。输入是 `fills`、`pricing`、证券到退市日期的映射及 `price_col`。发现残余仓位、退市后成交或缺失执行价时会抛出错误。该审计覆盖模拟账本。交易所现金结算和模型之外的公司行为还需另行核实。

## 输入与结果 {#_4}

目标持仓至少需要调仓日、建仓日、证券代码和权重。当前模拟只处理多头正权重。行情表需要交易日期、证券代码、价格列和配置中的流动性列。买卖方向可分别传入可交易标记。

`ExecutionSimResult` 包含 `summary`、`orders` 和 `fills`。`ExecutionAdjustedNavResult` 额外包含 `daily`，其中记录每日净值、现金和敞口等结果。

其余公开对象包括 `SELL_UNTIL_NEXT_REBALANCE`、`TradeFeeModel`、`PreparedExecutionTables`、`describe_execution_sim_config` 和 `describe_trade_fee_model`。它们分别用于延迟卖出期限、准备后的执行表、费用协议以及配置和费用说明的序列化。

容量模拟根据参与率限制成交，并保留未成交余量。`round_lot`、`enforce_t1`、`enforce_price_limits` 和 `enforce_listing_status` 可显式启用整手、T+1、价格限制与上市状态检查，默认关闭。调用方仍须提供相应的原始价格、涨跌停价格、上市状态和买卖可交易字段。停牌原因与券商拒单规则不会自动补全。

整手数量与价格限制必须使用一致的真实股份和价格单位。不能直接把复权价格对应的合成份额视为真实可交易股数，也不能把原始涨跌停价格与复权成交价格直接比较。使用长期历史数据时，还需单独验证分红、拆并股等公司行动的处理。

## 使用边界 {#_5}

理想每日净值用于比较充分流动性情形。执行后每日净值用于观察延迟成交、未成交和成本拖累。两者都属于研究模拟。真实交易仍需核对订单状态、账户现金账本和券商风控。

在份额账本入口 `simulate_execution_adjusted_nav` 中，`round_lot` 只控制买入。独立参数 `sell_round_lot` 默认为 `None`，保留调整后份额的连续卖出行为。设为正整数后，部分卖出的成交量先受请求量、流动性容量和 T+1 可卖量约束，再向下取整到该股数的整数倍。只有三个约束都容许卖出全部实际持仓时，才允许一次清空整数零股。受容量或结算限制的清仓仍按部分卖出处理。容差不会增加可成交数量，配置描述会序列化此参数。

启用时须使用原始价格和原始股数。显式传入 `price_basis="adjusted"` 会报错。省略时由调用方保证价格单位正确。卖出遇到小数持仓会抛出 `ValueError`，公司行动产生的小数权益须由调用方先行结算，不能静默取整。仅允许 `min(lot_tolerance, 1e-8)` 股以内的浮点运算尾差，并保留其原值，不据此放宽容量。权重账本入口 `simulate_capacity_execution` 无法执行股数约束，因此拒绝此参数。该机制由调用方显式选择，不自动推断交易所规则。
