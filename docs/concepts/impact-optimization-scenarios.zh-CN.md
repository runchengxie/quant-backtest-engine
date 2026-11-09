# 冲击与离散优化：合成核对

语言：简体中文 · [English](impact-optimization-scenarios.md)

两个显式选择的实验模块让有限假设可供核查，不改变历史重放、生产账务或优化器注册表。
已实现合成检查，但没有真实历史验证或实际成交校准。本页是新增中文对应页，原站没有中文历史路线。

## 永久冲击敏感性

`quant_backtest_core.backtest.impact_scenarios.linear_impact_scenario` 接收固定未受影响价格下的
带符号股数路径，从零持仓、零位移开始。价格单位为货币/股，永久及临时系数为货币/股²，
`fee_per_share` 为货币/股。输出现金变化、股数、价格位移和逐笔成交，不使用净值比例。

切片前持仓为 x、交易量为 q 时，成交价为
`p + permanent*x + permanent*q/2 + temporary*q`，新位移为 `permanent*(x+q)`，
现金变化为 `-q*execution_price-fee_per_share*abs(q)`。半切片项是线性永久曲线的积分：
从空仓开始总永久成本为 `permanent*Q²/2`，闭合往返时为零；临时成本为
`temporary*sum(q²)`。固定未受影响价格、非负系数不能制造往返利润。
拆单会改变临时成本，没有建模时间或流动性。

模型不改写历史价格，不把位移再次作为现金费用，也不返回账面净值。
以后若与净值集成，须明确参考价避免重复计算。这是未校准的敏感性参考，
不证明历史反事实执行可信，不建模恢复、交叉冲击、买卖价差、流动性、信息效应或内生市场反应。
无效或非正的模型成交价格会被拒绝。

## 既有成本核算审查

以下是仍属于 Platform 的历史边界，Engine 没有迁入这里的旧净值订单处理器。
[固定原始审查](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/impact-optimization-scenarios.md#existing-cost-accounting-audit)。

旧成本和滑点 `cost(...)` 返回组合价值比例，不是账户金额或每股溢价。
`_quote_trade_fee` 以 `notional/portfolio_value` 构造交易权重，将滑点比例乘以组合价值一次，
再纳入成本明细。净值订单处理器买入扣参考成交额及 `total_cost`，卖出收参考所得减费用，
不会同时为这项滑点改变成交价。`CostEvidence` 只描述账户金额，不指示再次扣款。

详细费用模型的价差/滑点基点可能与单独滑点模型叠加，这是既有实现行为，
配置不当会对同一价差重复建模。`temporary_impact` 名称不证明测得了市场冲击。
本审查不保证所有后端或策略无重叠，也不改变原账务语义。

## 连续基线与离散参考

Platform 的 SLSQP 风险后端用两资产凸二次风险加原权重二次惩罚的解析解核对。
该惩罚是正则项，并非校准交易成本。半正定协方差、非负二次惩罚、线性约束保持凸性；
求解成功和可行性不构成独立全局最优证书，原 `optimal` 诊断含义不升级。

`quant_backtest_core.planning.discrete_oracle.enumerate_lot_portfolios` 在有界、仅买入的整数手数
网格上最小化股数目标平方误差。从纯现金开始，不能花费未成交卖出款。
每个非零资产订单支付 `max(minimum_commission, proportional_commission*notional)`，
零订单费用为零。现金预算涵盖全部费用，预算、费用及目标按输入的十进制字符串进行精确有理数比较，
返回浮点金额仅用于显示。因此 0.1 与 0.2 的成本可落在 0.3 预算内，允许剩余现金。
最低费用在零点不连续，手数产生整数决策；市场冲击本身不必然非凸。

结果包含股数、目标值、支出、枚举状态数、候选可行性。可行候选报告相对穷举最优的绝对目标差距；
不可行候选没有差距。`optimal_exhaustive` 只覆盖所声明的有限范围、目标及费用规则。
`search_limit` 在枚举前拒绝过大搜索，不返回解、目标或证书。无借款、风险预算、协方差、初始持仓、
卖出、税务批次或生产级全局 MIQP 求解。佣金按资产订单收一次，不按每笔部分成交或券商订单组收费。

价格 (6,4)、目标 (1.5,1.5)、一股手数、上限 (3,3)、现金 14、最低佣金 1 的合成例子，
选择 (1,1)，支出 12、目标 0.5。取整候选 (2,1) 超预算；可行 (0,2) 的目标为 2.5、差距 2。
这些是正确性例子，不是收益声明或现实投资建议。

安装 SDK/Core wheel，显式选择 `planning` 并固定 NumPy 2.2.6、pandas 3.0.6、SciPy 1.18.1，
在源码树外运行：

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_discrete_oracle.py" "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_impact_scenarios.py" -q -p no:cacheprovider
```

通用风险优化器测试仍在[固定 Platform 测试](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/tests/test_impact_optimization_scenarios.py)。
两个纯辅助模块本身只需标准库，planning 数值 extra 服务于另外的连续规划接口。
当前是未发布的 provider B 代码，Core 当前源码为 0.2.0，整体审查、合并和消费者迁移另行受控。
本页依据上述 Apache-2.0 固定原文翻译改编。

相关原始研究仅供背景阅读，不表示实现等价：
[Boyd 等，多期凸交易优化](https://web.stanford.edu/~boyd/papers/cvx_portfolio.html)；
[Lobo、Fazel 与 Boyd，线性及固定交易成本组合优化](https://stanford.edu/~boyd/papers/portfolio.html)。
