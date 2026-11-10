# 多次决策的顺序执行 {#_1}

[English](sequenced-execution.md)

使用 `run_daily(request)` 和 `mode="sequenced"` 将已选定的目标依次送入同一个原有日频现金/股数账本。每次新调用创建独立账户。`ExecutionAdjustedNavResult` 保留 daily、orders、fills 和可选的 actions/holdings 表。

每个 ISO 调仓日期对应一个 SDK `ClockSet`，同时显式提供入场日期、`DailyDecisionTiming`、`ExecutionCalendar` 和 `DailyInputLayout`。信息截止日期匹配调仓日期，信息≤决策≤入场。来源时序限制入场交易日和估值范围。模拟仅精确到日期：旧成交审计时间是上海时区的合成午夜标签，不是实际事件时间，也不能证明日内成交资格。

入场必须有显式价格及交易日覆盖。重复证券目标、同一天覆盖多个决策、非有限/负数/超额权重、时钟缺失、越过估值范围的价格和缺失的已启用规则字段都会被拒绝。未成交卖单不能为买入融资：股数账本先使用实际卖出所得，再按含费用的可用现金限制买入。

    from quant_backtest_core.daily.runner import run_daily
    result = run_daily(request)
    ledger = result.to_unified_ledger()

完整合成示例为 `fixtures/product/daily.json`；参见[日频输入](../product/daily-inputs.zh-CN.md)。显式选择 `python.daily`；无日频检查点、恢复接口或运行数据库。

旧 Platform `SequencedExecutionRequest` / `research.clock.v1` 适配器和研究报告写入器仍由消费者维护，序列化标识不变。单时钟研究报告仍须拒绝多决策结果。调用方时钟和日历不能认证历史数据可见性。
