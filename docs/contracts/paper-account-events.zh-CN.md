# PAPER 账户事件生命周期

[English](paper-account-events.md)

已在提供方 B 工作树实现，B 门合并前未发布。迁移阶段 Core 仍为 0.1.0。[原始文档](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/contracts/paper-account-events.md)。

`quant_backtest_core.backtest.account_events.AccountEventAdapter` 在 `project_paper_account` 上增加原始整数股订单、财务报告延迟、公司行动和恢复。成交由调用者提供，不含撮合器、券商执行接口或历史校准保证。

初始化提供 `PaperState` 和 `EventAccountConfig(source_binding=..., input_binding=...)`，显式声明源码/配置和输入清单身份。恢复检查身份相等，但字符串和摘要不能证明输入在历史上可得。

## 财务状态与时钟

`actual` 为模型真值，`visible` 为已送达的不可变 `PaperState`。`actual_nav`、`visible_nav`、`visible_receivables` 含除息至支付间有符号权益。`actual_margin`、`visible_margin` 报告保证金要求、余额、违约与 `nav_including_signed_receivables` 权益口径。`pending`、`entitlements`、`reductions`、`visible_reductions` 返回副本。策略仅用 `visible`、`visible_receivables`、`pending`、`available_cash(as_of)`，不可读取未送达的 actual 状态。

`AccountEvent(event_id, kind, occurred_at, available_at, payload)` 要求带时区时钟及有限 JSON 数据。发生时间不倒退，报告不得先于发生，不可追加入最后送达时间之前的报告。同一 ID 和完整内容重放为无操作，恢复后亦然；复用 ID 改内容则失败。无效事件不改变状态。准入、撤单请求、事件与送达共享单调控制时钟。离线驱动应先处理该刻真值，再推进策略时钟，不能先准入未来订单再补早先拆股。同一事件重放仍保持幂等。

`apply(event)` 更新真值，`deliver(as_of)` 释放已知报告。财务报告采用因果前缀：早期报告延迟时，后续快照即使更早可用也等待，避免泄漏隐藏成交或旧快照覆盖新状态。独立行情可直接送策略。`visible.as_of` 保留最后送达快照的端点，deliver 另记单调送达时钟。

## 提供投影与成交

`projection` 载荷为 `{"inputs": ...}`；`fill` 还需 `order_id`、有符号整数 `quantity`、正 `price`，可选非负 `fee`、`fill_id`、带时区 ISO `cash_available_at`。例如合成输入：

```python
{
    "price_basis": "raw",
    "marks": {"A": {"value": 10.0, "available_at": "2025-01-01T00:00:00+00:00"}},
    "borrow_rates": {"A": {"value": 0.10, "available_at": "2025-01-01T00:00:00+00:00"}},
    "locate_quantities": {"A": {"value": 100, "available_at": "2025-01-01T00:00:00+00:00"}},
    "financing_rate": {"value": 0.05, "available_at": "2025-01-01T00:00:00+00:00"},
}
```

包括零时长在内，每步都调用投影器；期初利率、期末价格和可借数量遵守可用性及新鲜度检查。借券融资按每个实际区间计提一次，融资口径和保证金是假设配置。必须声明 raw，复权声明拒绝，价格来源仍由调用者负责。成交须满足订单限价、方向、剩余数量和准入时钟。`fill_id` 标识跨报告的同一经济成交，一致重报不重复记账，内容变化失败；未提供时使用事件 ID。

## 订单与预留

`admit_order(order_id, symbol, quantity, limit_price, as_of=..., locate_quantity=..., risk_limit=..., risk_price=None, fee_budget=0)` 使用已送达持仓、现金和价格，接受已知可借数量和以货币计价的总敞口上限。相反订单不抵消现金和风险预留；已送达多头只能支持一次卖出，待买和隐藏成交不能补充卖出或借券额度。回补需现金但无需新借券。

现金预留为正剩余数量乘限价加剩余费用预算。风险预留为剩余绝对数量乘 `risk_price`，保守加到可见总持仓。风险价格默认限价，至少等于限价；高于风险价的成交均失败，包括卖空价格改善，应显式放宽假定风险价。成交费用不能超过预算，剩余预算随完成或撤单报告释放。信用额度是假定融资安排，不是券商购买力。

`request_cancel` 保留全部预留；其后的 `cancel_ack` 只有送达才释放。部分成交仅释放已成交部分。全成可先于撤单赢得竞态，稍后确认保持已完成订单关闭；确认后的成交失败。不存在按墙钟自动到期的预留。

## 公司行动、减仓与结算

行动前先投影到其时钟，防止新库存参与旧区间计息。

| kind | 载荷与行为 |
| --- | --- |
| `dividend_record` | `entitlement_id`、`symbol`，记录实际有符号股数。 |
| `dividend_ex` | `entitlement_id`、非负每登记股 `amount`，生成应收/应付。 |
| `dividend_pay` | `entitlement_id`，恰好一次支付登记权益。 |
| `split` | `symbol`、正整数 `numerator`、`denominator`、`price_basis="raw"`；按比例改股数、未结订单、可借量，反向缩放原始价与限价。 |
| `recall` | `symbol`，为实际空头生成需回补意图。 |

平仓不删除登记权益，登记股数在后续拆股后仍用登记日单位，股息金额须与之匹配。拆股造成任何非整数持仓、剩余数量或借券数时整步拒绝，不隐式取整或现金替代；整数受底层浮点投影器的精确整数范围约束。拆股报告只影响发生时开放的订单，之后准入的订单即使同一时钟也不追溯调整。

借券违约和每次事件后的保证金不足产生 `required` 减仓意图，保证金权益含有符号未付股息，所以空头股息可在除息即触发。恢复实际保证金余额至非负才改为 `resolved`，送达状态随报告变化。这是诊断而非已成交回补或执行计划；失败成交保持敞口，调用者决定减仓及提供成交，意图历史保留。

结算与卖出资格独立。卖出所得可用时点由成交覆盖，或成交时钟加 `settlement_delay_seconds`（默认零）决定，是通用日历秒政策而非 A 股 T+1。`available_cash` 扣已送达未结所得、空头所得限制和待买预留。每次卖出记录所得及新增空头部分，费用按股数分摊。同标的未结空头所得与当前空头抵押占用取并集，重叠取两者较小值；不同标的不共享重叠。这是汇总抵押假设，不是券商逐笔税务或结算模型。账面现金与净值在成交时立即确认，利息使用投影器融资口径，不另造结算信用模型。

## 检查点

`checkpoint()` 返回确定性 JSON 的 schema **2**、完整配置和 SHA-256 摘要，含 actual/visible、待单及预留、未送达快照、事件和成交去重、权益、减仓历史、结算记录与时钟。`restore(checkpoint, config)` 校验版本、完整摘要、配置及来源/输入绑定。结果应存项目数据根，是复现记录而非市场认证。

组合 `ExecutionState` 采用 **execution-state.v2**，同时保存账户、冲击、游标、种子和策略状态。原 Platform schema 1 / execution-state.v1 原样拒绝，旧记录保留完整固定 Platform/Runtime/Go 环境，不提供转换器。仅版本及由此产生的摘要改变，不改财务状态或算法。`source_binding` 和 `input_binding` 是调用者声明，底层函数不测量已加载代码；实际代码/wheel 哈希由安装凭据与产品提供方绑定记录。重复旧字符串不能让旧格式通过。内容篡改及配置、来源、输入变化均拒绝。
