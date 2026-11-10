# 期间诊断回放 {#_1}

[English](diagnostic-close-replay.md)

`run_period_replay` 在显式期间边界上计算已选定持仓，返回原 `PositionBacktestResult(net_returns, gross_returns, periods, summary)`。它不生成每日现金、股数、订单、成交或现金扣费证据。

    from quant_backtest_core.daily.period_replay import run_period_replay
    result = run_period_replay(
        positions=positions, pricing=pricing, periods=periods,
        calendar=calendar, config={"transaction_cost_bps": 10.0},
    )

实现前计划遗漏了 `periods` 参数，并误用了每日净值结果类型；此处纠正。来源是固定版本的 `_position_backtest_config/_position_backtest_engine` 及纯归一化/权重漂移函数。原净收益、毛收益和期间表的列、重复结束日期、数据类型、跳过期间元数据及运算均保留。期间表显式包含 rebalance_date、entry_date、exit_date；新入口拒绝缺失的调用方交易日覆盖，不查询日历或推断期间边界。

直接 `daily.position_backtest.run_position_backtest` 签名保持，包括可选日内 VWAP 诊断。输入归一化、退出策略及末期专用估值价格保留原语义。选股、策略权重模型和发布留在 Platform。Core 不生成年化、夏普、回撤、H1/H2 等研究统计；`summary["stats"]` 只保留平均换手、成本和敞口等财务字段。Task 15 使用同一个结果类重建旧研究字典。

未变更的液态基准毛收益为 `0.05`、净收益为 `0.049`，初始成本为 10 基点；它明确不提供订单生命周期、部分成交或每日账本。

## 保留的下一收盘价流程 {#_2}

Platform 独立的 `target_close_replay.replay_close_targets` 留在原项目：形成后的首个收盘价、可分割复权单位、调用方选择的默认 25 基点、交易阻断时整篮子延期，以及无券商成交/分红账本。此次迁移不替代它。[固定版本原文](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/guides/diagnostic-close-replay.md) 保留完整时序和敞口契约。

## 敞口变化 {#_3}

敞口决策、波动率目标和目标构造仍由 Platform 提供；Core 不推断现金利息或未来敞口。

## 审计辅助 {#_4}

持仓损益、回撤区间和匹配波动率研究诊断留在原流程。历史可见性、分红复权、退市和可执行性均须独立证据。
