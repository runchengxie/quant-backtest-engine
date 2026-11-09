# 成交记录核验与合并账户探索

[English](execution-integrity.md)

`quant_backtest_core.evidence.execution_integrity` 从成交记录重建现金和原始整数股数，
不撮合、不提交订单。它逐时钟比较账户前缀；即使终点相同，中间账户轨迹也可能不同。
终点一致不能证明整段账户历史一致。

```python
from decimal import Decimal
from quant_backtest_core.evidence.execution_integrity import fill_prefixes, exit_wealth

fills = [dict(fill_id="f", ts_ns=10, symbol="A", side="buy",
              quantity="4", price="101.4", fee="1")]
prefix = fill_prefixes(fills, "1000")
assert prefix[-1]["cash"] == Decimal("593.4")
wealth = exit_wealth("593.4", {"A": 4}, {"A": {"price": "100", "ts_ns": 10}},
                     as_of_ns=21, max_mark_age_ns=10)
assert wealth["marked_wealth"] is None
assert wealth["cash_realized_wealth"] is None
```

`fill_prefixes(fills, initial_cash, initial_quantities=None)` 要求来源成交 ID 唯一，
股数为正整数、价格为正、手续费非负、数值可转换为有限 Decimal，持仓为多头。
相同整数 UTC 纳秒时钟的成交先分组再比较，初始行时钟为零。
该旧接口仍接受整数时钟；公开产品封装使用精确字符串时钟，在边界转换，
不能通过浮点数转换时钟。

`compare_prefixes(left, right, *, cash_atol="0.00000001")` 返回每个存在差异的时钟，
保留左右现金及数量。计算使用独立的 64 位有效数字 Decimal 上下文，
不精确结果抛出 ValueError，不继承调用方精度。
结果只是成交证据重建，不是对上游账户隐藏状态的观测。
现金准入、T+1、队列优先级及手续费正确性仍需原所有者提供独立证据。

`exit_wealth(cash, quantities, marks, *, as_of_ns, max_mark_age_ns, receivable="0")`
保留估值价格、时钟、新鲜度边界、现金、应收款及剩余股数。
持仓估值缺失、过期、来自未来或为零时，估值财富未知。
未卖出的股票不会变成已实现现金；仅无持仓且无应收款时提供已实现现金财富。
输入估值不是可成交的清算报价。

## 外部资金流

`evidence.capital_returns.CapitalObservation` 记录外部资金流发生前的净值、
带符号资金流和流后净值。`capital_performance(initial_nav, start_ns, observations)`
要求完整、严格按时序排列的正估值，并校验资金恒等式。存取款与损益分开。

```python
from quant_backtest_core.evidence.capital_returns import CapitalObservation, capital_performance

result = capital_performance(1000, 0, [
    CapitalObservation(1, 1000, 1000, 2000),
    CapitalObservation(2, 1900, -500, 1400),
])
assert result["net_external_flow"] == 500
assert result["net_monetary_gain"] == -100
assert round(result["time_weighted_return"], 8) == -0.05
assert result["money_weighted_irr"] is None
```

连乘时间加权收益与按经过时间近似加权的 Modified Dietz 收益保持区分。
全额赎回是序列边界，不能静默接续。实现不声称求得唯一内部收益率。

组合分仓规划及真实后端对比实验在各自迁移任务前仍属于 Platform。
本模块不提供分仓成交分配、券商协调或账户执行后端；旧账户及检查点保持固定。
来源见[第三方声明](../third-party-notices.zh-CN.md)。
