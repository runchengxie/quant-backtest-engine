# 成本证据

[English](cost-evidence.md)

`quant_backtest_core.backtest.costs` 提供附加的 `cost_evidence.v1` 契约。
它描述来源成本，不扣现金、不重新定价成交，也不估计缺失分项；导入时不加载执行模拟器。

```python
from quant_backtest_core.backtest.costs import CostComponents, CostEvidence

evidence = CostEvidence(
    source_id="synthetic-run:fill-0", source_revision="synthetic-owner-and-config-v1",
    stage="actual_fill_model", scope="fill", source_ids=("fill-0",),
    total=5, unallocated_total=2, components=CostComponents(commission=3),
    currency="CNY",
)
assert evidence.components.spread_cost is None
assert evidence.components_status == "partial"
assert evidence.to_mapping()["total"] == 5
```

金额以来源账户货币计量，不是费率。`CostComponents` 用 `None` 表示无法取得的证据；
只有来源明确为零时才使用零。`CostEvidence` 保留来源及版本、阶段、范围、
记账所有者、货币、单位、原始分类和关联成交 ID。来源版本须同时标识代码与配置；
ID 是运行内的证据定位符，不是经过认证的回执。
`actual_fill_model` 表示模拟成交，不是券商实际收费。
其他阶段为 `planned_estimate`、`aggregate_estimate`、`broker_actual`；
最后一项需要独立券商来源，本任务不获取该类数据。

校验要求金额有限且满足 `total = sum(known components) + unallocated_total`。
带符号残差保留来源中的不一致；完整程度分为 `unknown`、`partial`、
`source_identified`。分类名称不能证明因果性的经济影响。
`CostGroup` 保留原最低佣金分组范围、规则版本、累计前后金额，以及可选订单、
市场和有效时间区间。前后金额必须成对存在且不递减。
成交级分组不能证明券商统一采用订单/交易日规则。

机会成本证据须使用独立的 `economic_opportunity` 记账所有者和
`opportunity_status="modeled"`；未知或未建模的机会成本分项保持 `None`。
基准短缺只是描述，不会额外扣款。成交价中已有的冲击和现金手续费分别只计一次。

## 报价与原收费所有者

`CostQuote(currency, side, effective_ns, quantity, notional, commission, tax,
total, model_id, rounding)` 是冻结的类型化传输记录。
金额与数量使用十进制字符串；`effective_ns` 使用保留精度的 UTC 纳秒字符串。
`CostModel.quote(*, currency, side, effective_ns, quantity, price)` 是返回此记录的协议。
二者不定义手续费公式、不校验券商费率、不记账，也不把预览变成成交。
具体收费适配器必须调用原收费所有者，保留其舍入、分组及来源身份；
本次叶子模块迁移不转移任何此类所有者。

旧 `CostBreakdown`、`ExecutionSimResult`、`ExecutionAdjustedNavResult`
适配器在各自迁移前仍属于 Platform，其证据保持原所有者。
Core 不导入这些类或伪造其结果。明确已知的空成交集合与不支持或缺失证据不同。

## 适用范围内的拟合证据

`evidence.cost_scope.fit_cost_scope`、`validate_cost_scope`、
`validate_cost_scope_uncertainty` 保留原有仅使用过去数据的拟合、冻结适用范围检查
及按聚类重采样。安装 `[cost]` 以取得 pandas、NumPy 和 SciPy。
输入列、完成/可用时钟、带符号短缺单位、种子、聚类数量与不确定性边界，
见[交易成本证据](transaction-cost-evidence.zh-CN.md)。
较晚可用不等于此前未见的执行区间；不自动晋级模型，也不保证未来校准有效。
风险校准及零信号研究仍留在 Platform。来源见[第三方声明](../third-party-notices.zh-CN.md)。
