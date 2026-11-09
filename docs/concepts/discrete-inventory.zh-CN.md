# 有限持仓与交易手数比较

语言：简体中文 · [English](discrete-inventory.md)

`quant_backtest_core.planning.discrete_inventory` 为小规模、明确限定的只做多持仓问题，
提供确定性的可行启发式方案和有界穷举参考。这些是合成条件下的规划结果。
现有[仅买入的参考求解器](impact-optimization-scenarios.md)保留原有行为。

## 预先备足现金的优化范围

所有买入金额以及每笔非零订单的费用，都必须由已提供现金减去预留现金支付。
计划卖出的收入不能用于买入，也不能支付这笔卖出本身的费用。
例如，现金为零且最低费用为正时，即使卖出收入足以支付费用，本模型也不会选择卖出。
这一保守规则排除了部分依靠卖出收入融资的有效执行顺序。
有限域最优仅指在这个预先备款规则下的最优。

`projected_cash` 包含假设卖出收入并扣除假设订单成本，只是情景金额，
不代表已到账或可用现金。`unreserved_cash` 不包含卖出收入，也不包含已预留现金。
执行方报告实际成交和结算后，才使用实际持仓、实际可卖股数和实际现金提交新请求。
未成交或受阻的卖出不能增加下一次请求的现金。

## 输入、目标函数与数量

创建 `DiscreteInventoryRequest`，调用 `solve_discrete_inventory(request)`。
各向量采用声明的资产顺序。`holdings`、`available_sell_shares`、
`locked_shares` 和手数上限均为非负整数。
买入数量上限为 `max_buy_lots * buy_lot_sizes`。
普通卖出使用 `sell_lot_sizes`，同时受原始持仓的可卖数量和未锁定数量限制，禁止卖空。
调用方必须按结算规则及 T+1 规则提供可卖数量。
可选的完整零股退出仅在全部原始整数持仓均可卖且未锁定时，允许一次卖完。
关闭此选项后，仅允许普通卖出网格内的数量。

`fractional_entitlements` 单独记录 [0, 1) 内的零碎权益，始终原样保留。
这些权益参与跟踪误差计算，不进入交易变量。总目标股数应包括这些权益。
构造整数持仓前，应精确拆分来源持仓中的零碎部分。

目标函数为逐资产求和：
`tracking_weight * (final_integer_holdings + entitlement - target_shares)²
+ turnover_penalty * abs(trade_shares)`。
权重和惩罚均非负，默认跟踪权重为一、换手惩罚为零。
跟踪项单位为股数平方，换手惩罚单位为每股对应的目标函数单位。
不支持协方差、预测效用、税务、零碎股交易、借款或一般非凸目标。

每笔非零资产交易支付
`fixed_fee + max(minimum_fee, proportional_fee * absolute_notional)`。
零交易不收费，费率单位为成交金额的比例而非基点。
费用约束可行性，不直接加入跟踪目标函数。
价格、目标、权重、惩罚和金额均精确转换为 `Fraction(str(value))`，
已有 `Fraction` 输入原样保留。因此浮点输入声明的是其显示十进制值，不采用二进制金额容差。
价格必须为正，所有输入必须有限。

## 搜索结果与证明范围

启发式从不交易开始，按声明的资产顺序进行一轮坐标搜索，
在每个资产的有限网格中选择最佳可行数量，可能停在局部解。
两种搜索在目标函数相同时，都选择带符号交易数量元组中字典序较小的方案。
启发式有独立的评估预算，预算用尽时可返回已完成部分搜索的可行方案。

| 参考搜索状态 | 含义 |
| --- | --- |
| `optimal_exhaustive` | 已评估所声明范围内的全部状态。 |
| `budget_exhausted` | 仅评估了部分状态，保留启发式或已枚举方案中的最佳可行解。 |
| `domain_too_large` | 超过穷举状态数上限，但已运行有界启发式。 |
| `asset_domain_limit` | 分配网格前发现单个资产超限，未构造方案。 |
| `asset_limit` | 超过资产数上限，未构造方案。 |

`max_assets`、`max_asset_states`、`max_domain_states`、
`max_evaluations` 和 `max_heuristic_evaluations` 都是正整数上限。
无效契约抛出 `ValueError`。预算耗尽或范围过大时绝不声称最优。
可支持但未完成的搜索给出由目标非负性保证的零下界，以及当前可行解目标值作为上界。
完整穷举给出相等的上下界和启发式的精确差距。
未证明的差距为 `None`，即使未完成搜索的当前方案目标值为零也是如此。

方案金额和目标值均为精确 `Fraction`。
传输时可编码为 `{"numerator": value.numerator, "denominator": value.denominator}`。
只有在明确接受近似显示或适配执行接口时才转换为浮点数，不能根据四舍五入后的值判断可行性。

## 独立核对与执行归属

公开测试列出两资产的字面可行集合，并核对费用、手数、锁定、零碎权益、十进制边界和搜索上限。
另一个合成比较使用价格 (4, 6)、目标 (1.9, 1.9)、现金 14 和最低佣金 1。
一轮启发式买入 (2, 0)，含费支出 9，剩余现金 5，平方跟踪误差 3.62。
穷举买入 (1, 1)，含费支出 12，剩余现金 2，误差 1.62。
两种方案的目标均交给现有公开原始股数执行方，使用一股手数和匹配的最低佣金。
测试将实际成交、换手金额、扣费、现金、持仓价值和剩余跟踪误差与独立字面结果比较。
另一个执行测试分别阻止或完成存量卖出，仅按实际到账现金和剩余持仓重新规划。

规划器不扣账、不撮合。提交目标前必须核对执行方能力。
通用固定单笔费用、独立买卖网格、公司行动零碎权益、部分成交或按日费用分组，
可能与执行方支持的语义不同。执行比较仅使用受支持的最低佣金，不设置固定费用或税费。
执行后应重新核对实际成本、手数、限制、现金和剩余持仓。
这些合成核对不构成市场校准、可执行清仓或一般全局最优证明。

原始 `test_both_plans_use_public_owner_fills_fees_cash_and_residual_tracking` 与 `test_actual_public_owner_sale_controls_later_buy_funding` 的按日费用和日频执行版本，仍是 Task 14/15 的明确对齐义务，以以下固定源码为准。分钟测试保留全部字面经济断言，并在退出前恢复整个账户；这不证明日频或按日费用已经迁移。

安装已构建的 SDK 与 Core wheel，显式选择 `planning` extra，固定 NumPy 2.2.6、pandas 3.0.6 和 SciPy 1.18.1。从源码树外使用已安装的解释器执行：

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_discrete_inventory.py" -q -p no:cacheprovider
```

改编自 [Apache-2.0 固定原文](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/discrete-inventory.zh-CN.md)。当前实现位于尚未发布的 provider B 分支；Core 在 Task 11 前仍为 0.1.0，消费者切换另行进行。
