# 交易成本证据

语言：简体中文 · [English](transaction-cost-evidence.md)

`quant_backtest_core.evidence.transaction_costs.audit_transaction_costs` 审核已结束的父订单和物理成交，计算经纪费用模型与有方向的基准差额。它不撮合订单、不生成成交、不扣账户现金，也不把校准结果自动发布到生产。函数不修改输入，现有成本范围接口的默认行为保持兼容。

```python
from quant_backtest_core.evidence.transaction_costs import audit_transaction_costs

report = audit_transaction_costs(
    parents,
    fills,
    billing="parent",
    commission_bps=3,
    minimum_commission=5,
    sell_tax_bps=10,
)
observations = report.cost_observations(fee_basis="modeled")
```

示例费率仅用于合成机制测试，不代表券商收费标准。调用方负责保存带版本的费用条款，并确认计费约定。

## 标准化输入

输入是 pandas DataFrame。标识符为非空字符串，时间为非负整数 UTC 纳秒，价格单位为人民币元/原始股，委托和成交数量为正整数股。不隐含手数换算、外币换算、负数量或零股份额契约。存在缺失时钟时，使用可空整数列或 object 列，避免 pandas 将有效整数时钟转换为浮点数。

父订单必需列：

| 列 | 含义 |
| --- | --- |
| `parent_id`, `side`, `requested_shares` | 唯一父订单、`buy`/`sell`、原始委托股数 |
| `reference_price`, `reference_ns`, `reference_available_ns`, `decision_ns` | 参考报价及可用时钟，均不晚于决策 |
| `arrival_price`, `arrival_ns`, `arrival_available_ns` | 到达报价及相关时钟，报价可缺失，已知时钟仍保留 |
| `completed_ns`, `available_ns`, `status` | 执行区间结束、整条证据可用、`completed`/`cancelled` |
| `source_binding`, `evidence_kind` | 调用方来源标识、`synthetic`/`broker_fills` 声明 |
| `quantity_unit`, `currency` | 固定为 `shares`、`CNY` |
| `price_convention` | 固定为 `includes_spread_and_impact` |
| `brokerage_terms_version` | 本次费用条款的调用方版本标识 |

`completed` 表示执行区间结束，不表示全部委托已成交。撤单和零成交父订单均保留在 `report.parents`。参考报价可用时钟不得晚于决策。存在到达报价时，其报价时钟位于决策和执行结束之间。报价可以延迟收到，但报价、成交回报和基准的可用时钟均不得晚于父记录 `available_ns`。累计成交不得超过委托量。

父订单可选证据：

| 列 | 含义 |
| --- | --- |
| `opportunity_price`, `opportunity_ns`, `opportunity_available_ns`, `opportunity_benchmark` | 正值终点基准、执行结束时或之后的比较时点、可用时钟与基准名称。报价未知时，仍可保留已知比较时点和可用时钟 |
| `market_volume_shares`, `market_amount_cny` | 同一执行区间内的市场成交股数和金额，存在时非负 |
| `liquidity_start_ns`, `liquidity_end_ns`, `liquidity_available_ns` | 已知到达时钟时起点须一致，终点等于执行结束，可用时钟不得早于终点 |
| `liquidity_quantity_unit`, `liquidity_amount_unit` | 提供区间流动性时固定为 `shares`、`CNY` |
| `liquidity_bucket`, `execution_minutes` | 调用方明确给出的流动性分组和正整数分钟窗口，用于现有拟合接口 |
| `cluster_id` | 调用方定义的日期或订单聚类标签 |

正值成交量、正值成交额、单位声明、区间时钟与范围标签齐备时，才生成参与率观测。流动性缺失或为零时，`participation=None`，不会推断存在可交易流动性。这里只校验单位声明，不向行情供应方验证。分钟窗口标签也需调用方按执行策略和区间定义核验。

成交必需列为 `fill_id`, `parent_id`, `child_id`, `price`, `shares`, `fill_ns`, `receipt_ns`, `source_binding`, `evidence_kind`, `quantity_unit`, `currency`。每个子订单仅属于一个父订单。成交时钟位于父订单执行区间内，收到回报不得早于成交，也不得晚于父记录的可用时钟。来源和证据声明必须与父订单一致。

`fill_id` 在一次审核中唯一标识一笔物理成交。同一物理成交的相同回报按身份去重，不受行顺序或收到顺序影响，保留最早有效回报时钟。物理内容冲突则报错。比较前会规范化价格和股数的数值表示。空成交表仍需保留必需列。

成交可选列 `recorded_commission` 和 `recorded_tax` 为已分摊到该物理成交的人民币分金额，不得重复填写整笔父订单账单。每笔去重后成交的两项费用均齐备，才生成父订单已记录费用总额。买入税费也需要显式填零。缺失费用保持未知。已记录数值属于调用方提供的证据，不等于已认证券商账单。

## 费用与归因

每个计费组先计算成交额 `N = sum(price * shares)`，佣金为 `round_cent(max(minimum_commission, N * commission_bps / 10000))`，卖出税为 `round_cent(N * sell_tax_bps / 10000)`。使用 Decimal 计算，每笔佣金和税分别按四舍五入保留到分。`billing="parent"` 合并所有子成交，仅收一次最低佣金。`billing="child"` 按子订单分别计算最低佣金和舍入税费。零成交不生成模型费用。不支持其他计费规则、返佣和负费率。

`modeled_commission`、`modeled_tax`、`modeled_cash_fees` 是这些条款下的估算。`recorded_cash_fees` 是去重后的已记录分摊费用之和，证据不全则为 `None`。`fee_evidence` 为 `caller_recorded` 或 `unavailable`。输出使用浮点数方便分析，不是精确到账户分的经济账本。

令买入 `s=+1`、卖出 `s=-1`，成交股数为 `q`、委托量为 `Q`、成交额为 `N`、参考价为 `R`、到达价为 `A`、终点基准为 `H`：

| 输出 | 人民币金额定义 |
| --- | --- |
| `reference_price_shortfall` | `s * (N - q * R)` |
| `arrival_price_shortfall` | `s * (N - q * A)` |
| `delay_shortfall` | `s * q * (A - R)` |
| `reference_shortfall_with_modeled_fees` | 参考价格差额加一次模型费用 |
| `reference_shortfall_with_recorded_fees` | 参考价格差额加一次已记录费用，或未知 |
| `opportunity_shortfall` | `s * (Q - q) * (H - R)`，仅作描述 |
| `completion`, `unfilled_shares` | `q/Q`、`Q-q` |

价格改善可以得到负差额。缺失到达或终点报价时，相关值为 `None`，并在 `unavailable_reasons` 中说明，零成交父订单也遵守该规则。机会差额不改变费用或现金余额，改变终点基准只改变该描述性比较。

到达差额与延迟差额在代数上相加等于已成交部分的参考价格差额。它们与参考比较重叠，不能据此识别价差、延迟或冲击的因果贡献。`attribution_additive=False` 明确提示不可把全部展示项当作独立成本相加。执行价格已含跨价差和冲击，不再另扣价差或冲击现金。把费用折入价格，仅在调用方显式将对应现金费用设为零、并统一价格约定时才等价。模型费用和已记录费用是两种替代口径，不可相加。

## 现有范围拟合与聚类不确定性

`cost_observations(fee_basis="modeled"|"recorded")` 将证据充分的已成交父订单转换为现有 `fit_cost_scope` 和 `validate_cost_scope` 输入。零成交、参与率未知、所选费用证据未知的父订单不进入成交成本校准，但仍保留在完整成交比例和机会差额表中。观测差额为 `10000 * chosen_reference_shortfall / (reference_price * filled_shares)`。`filled_notional` 保持为执行成交额，用于拟合加权。父订单来源、证据类型、摘要、聚类标签和显式费用口径随观测一起输出。调用方需在拟合时区分这些范围。

现有拟合使用截止时刻已可用、且已完成执行的记录。后续验证冻结系数，并保留来源、买卖方向、流动性分组、分钟窗口和参与率范围检查。现有 holdout 按较晚的可用时钟定义，可以包含早期成交的迟到回报，不能自动视为真正未见的市场区间。

新增的 `cost_scope.validate_cost_scope_uncertainty` 接收相同模型、观测和来源绑定，另加 `cluster_column`、`cluster_kind="date"` 或 `"order"`、`min_clusters=3`、`bootstrap_samples=1000`、`seed=0`。保留原有点估计和范围外数量，再按整个受支持聚类有放回抽样，维持成交额权重。输出冻结拟合条件下残差偏差和 RMSE 的 95% 百分位区间。样本充分性看独立聚类数，不看行数。标签缺失或为空时返回 `unavailable_clusters`，聚类太少时返回 `insufficient_clusters`，两者区间均为 `None`。最低聚类数只是工程门槛，不保证统计功效或覆盖率。抽样次数至少为 100，固定随机种子和排序标签保证可重复。

调用方必须证明所选日期或订单聚类之间的独立性，包括不同订单受共同日期影响的情形。标签本身不能证明独立。区间不包含系数估计不确定性、模型选择或未来市场概率。不使用后续数据重新拟合，也不自动晋升模型。

`source_digest` 绑定规范序列化后的输入记录、全部收到的回报、附加标量列和数值费用条款，不受行顺序影响。它不是原始文件字节摘要。调用方需在自己的证据清单中保留原始字节摘要、供应方来源、代码和消费方版本、带版本的费用条款。`broker_fills` 标签或优秀的合成拟合均不能证明来源真实。报告始终返回 `provenance_status="caller_asserted"` 和 `real_calibration="unavailable"`。此接口不验证券商记录，不识别历史队列，不校准永久冲击，也不产生新的样本外主张。
