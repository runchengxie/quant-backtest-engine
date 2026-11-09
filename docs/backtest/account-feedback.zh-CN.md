# 账户反馈与冲击压力

[English](account-feedback.md)

已在提供方 B 工作树实现，须等 B 门合并后才发布。迁移阶段 Core 仍为 0.1.0。[原始固定版本文档](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/account-feedback.md)。

显式从 `quant_backtest_core.backtest.minute` 导入分钟执行。`decision_policy(state, proposed_weights)` 在每个决策时钟、该时钟结束的 K 线之前运行。只读快照包含实际现金、持仓、原始价格及时间、待处理父订单与应收款。完整目标权重冻结到入场时，遗漏的已有持仓目标为零；空映射清仓；返回 `None` 保留待处理订单而不重复提交。

分钟模拟器中的报告和撤单同步完成，目标替换在入场时取消剩余父订单，不模拟延迟确认或真实排队。外部策略对未来信息的使用仍由调用者负责，不补造缺失数据。

`quant_backtest_core.backtest.impact.LinearImpact` 是未校准的线性压力模型。瞬时和永久系数的单位为每有符号股的价格单位，衰减常数以秒计。有符号成交 q 的平均价差为此前瞬时与永久状态，加本次线性增量的一半。真实提供的成交更新两部分，仅瞬时部分衰减。同刻拆单保持总成本；非负系数和指数衰减下，平价往返成本非负。这不识别真实市场冲击。

每个场景使用独立 `impact_model`。模型改变成交价格及后续成交，现金按该价格记账，不再扣一次冲击。超限价格阻止相应成交。估值与策略观察使用不含自身冲击的外部原始价格，因此是执行价格压力而非内生市场模拟。摘要保留语义和冲击检查点，但后者不能恢复完整账户。

参与率滑点默认 `coverage_policy="raise"`：启用冲击时，缺失、非正或非有限流动性及超出 `max_participation` 均失败。此上限是校准边界，不是成交容量控制。`coverage_policy="legacy"` 保留原先缺失流动性和截断行为；正式研究应显式采用严格覆盖。构建器和说明保留所选策略。价格内含成本不能再作为现金费用；校准截止日和适用性仍需研究证据。

分钟摘要说明 `execution_ledger_daily_nav`、账户送达和估值口径，不认证规范执行结果包、市场完整性、数据可用性或策略盈利。

## 延迟纸面反馈与预留

独立的[纸面事件适配器](../contracts/paper-account-events.zh-CN.md)可模拟报告与撤单确认延迟，其 `visible`、`pending` 视图用于[中立预留接口](../contracts/pending-allocation.zh-CN.md)。上述分钟执行仍为同步。`ExecutionState` 同时保存策略、成交去重、冲击、账户和待送达报告。[订单簿冲击估计](../microstructure/impact-estimation.zh-CN.md)报告实际回放成交与描述性执行价差，不对该账户再次扣款。
