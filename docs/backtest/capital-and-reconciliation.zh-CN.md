# 资本流、投资收益与外部证据

[English](capital-and-reconciliation.md)

已在提供方 B 工作树实现，须等 B 门合并后才发布。迁移阶段 Core 仍为 0.1.0。[原始固定版本文档](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/capital-and-reconciliation.md)。

`quant_backtest_core.evidence.capital_returns` 从完整资本观测链接收益。输入初始净值、UTC 纳秒起点，以及严格递增时钟的 `CapitalObservation`：外部流入前净值、有符号外部流量、流入后净值。前后必须在浮点 ULP 精度内满足现金恒等式。净值须保持为正；全额赎回或破产前停止，不为重启账户虚构份额。

`capital_performance` 报告精确链接的时间加权收益和净货币收益，并单列明确近似的按时长 Modified Dietz 收益，不假定或搜索唯一资金加权 IRR。股息、费用和行情盈亏属于投资净值，入金和赎回属于外部流量。缺失估值不能用资本流标签掩盖。

`AccountEventAdapter` 接收带非空原因的 `cashflow`（有符号金额）与 `fee_adjustment`（非负费用），且已投影到经济时钟。突破信用额度时原子拒绝。报告延迟和事件 ID 幂等仍适用，调用者须为每次真实资本或费用事件使用统一物理身份。不推断券商资金动作，不以负费用表示退款。股息仍遵循登记、除息、支付生命周期，并含未付权益。

`quant_backtest_core.backtest.reconciliation` 比较调用者提供的不可变 `AccountEvidence`、规范化 `OrderEvidence`、原始整数持仓与场所成交身份。快照须在账户、币种、经济时钟及成交历史覆盖上匹配，声明完整且在决策前可用。超容差的现金或应收差额、持仓差额、未知订单或不等的物理成交集合阻止新单。溢出、缺失或迟到证据阻止比较，不输出非有限 JSON 金额。

一致仅描述所提供的证据。接口不连接场所，不改账，不生成纠正成交，不认证来源或完整性声明。差异由所有者调查；内部检查点恢复不能替代外部对账。

`quant_platform.portfolio.robust_uncertainty` 的 `conservative_score`、`box_worst_case_return`、`add_conservative_score` 及高级资本研究仍归 Platform，既有不确定性数学不代表新估计器或校准风险模型。本次只转移账户反馈和外部证据对账。
