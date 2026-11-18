# 联合执行预测基准

[English](joint-execution.md)

`quant_backtest_core.planning.joint_execution` 将有限组目标权重路径逐一交给现有
`MinuteSession` 回放。预测收益、期末风险、整手、母单最低佣金、参与率、T+1、
报告延迟及暂时和永久冲击共同影响决策；现金与持仓始终只由该会话记账。
安装可选 Python 产品的 `planning` extra 后可使用。

这是范围明确的预测基准，不负责估计收益、协方差、容量或冲击参数。场景必须在
规划时点已经可用；真实未来行情只能用于独立的执行评估。未来权重均为条件计划：
实际账户执行第一步、收到报告后，再根据真实状态重新规划。

## 请求与结果

冻结数据类 `JointExecutionRequest` 的必填字段如下：

- `names`：固定且不重复的证券顺序，权重与期末协方差均按此排列。
- `decision_ns`、`forecast_available_ns`、`risk_available_ns`：UTC 纳秒整数；
  预测和风险的可用时间不得晚于决策时间。
- `forecast_bars`：严格晚于决策时点的预测行情；可选 `past_bars` 是不晚于该时点的已知行情。
- `decision_times`、`entry_times`：对齐的 UTC 纳秒序列。首次决策等于 `decision_ns`，
  入场晚于对应决策，下一次决策晚于上次入场。
- `weight_choices`：每次决策对应一组非空候选权重。仅支持多头，每个向量之和不超过一。
  索引零表示调用者列出的第一个选择，不默认表示现金。
- `config`：精确的 `MinuteExecutionConfig` 类型；`terminal_covariance` 是按 `names`
  排列、有限、对称且半正定的收益率协方差。

可选 `committed_targets` 使用已有分钟目标格式：`decision_time`、`entry_time`、
`symbol`、`weight`。两个时钟均不得晚于当前决策，历史决策必须严格早于当前决策。
每次历史决策的权重也必须有限、非负且总和不超过一。持仓、现金、待成交订单、
报告及冲击状态通过回放该前缀得到，不支持任意注入初始持仓或调整现金。
配置中的初始现金是整段回放的起点。

行情沿用分钟格式：带时区的 `time`、`interval_start`，以及 `symbol`、`open`、
`high`、`low`、`close`、`volume`、`amount`；可选涨跌停和可交易字段遵循原账户规则。
价格须为正，OHLC 一致，容量非负，预测必须延伸至最后一次入场之后。决策和执行
缺少参考价时保留原账户的拒绝行为；已有持仓在决策前或期末缺少估值则拒绝评估。
本基准不支持订单簿排队、随机路径分布、空头库存、公司行动或资本流事件。

可选标量默认为 `risk_aversion=0`、`transient=0`、`permanent=0`、
`decay_seconds=1`、`report_delay_seconds=0`、`max_evaluations=4096`。
冲击沿用未经市场校准的 `LinearImpact`：系数单位为每股有符号成交量对应的价格变化，
暂时冲击按经过秒数指数衰减。费用和冲击仅由原账户扣除一次。已交付观测中存在
待成交订单，或财务报告尚未交付时，策略等待。计划卖出收入只有实际成交后才能用于买入。

`evaluate_joint_path(request, indices)` 返回 `JointPathEvaluation`：含真实账户的
`result`、`objective`、`initial_nav`、`terminal_nav`、`risk_penalty`、绑定源码的
`request_digest`、决策与期末检查点，以及 `evidence` 属性中的已交付观测、报告队列、
策略轨迹与冲击状态。每次公开调用都会复制输入表和数组。请求摘要绑定完整问题、
所加载的账户及策略源码，不随选择的路径改变；检查点另行绑定该路径的精确目标。
检查点只能在账户输入和源码完全不变时恢复，不能用于更换预测或目标路径。

`solve_joint_execution(request)` 返回 `JointExecutionPlan`：包含 `indices`、
`first_weights`、选中路径的 `evaluation`、`evaluation_count`、`total_paths`、
`request_digest`、`status`，以及明确的条件计划语义。

## 目标与搜索边界

最小化的人民币目标为：

```text
initial_nav - terminal_nav
+ risk_aversion / (2 * initial_nav) * terminal_exposure' covariance terminal_exposure
```

初始净值是首次决策事件之前账户的经济财富；已交付余额作为独立检查点证据保留。
期末敞口是实际剩余股数乘以账户最终估值。期末净值按市值计量，强制清仓收入需要另行验证可执行退出。
风险项用于期末惩罚，完整跨期风险模型需另行定义与验证。预测价格已经携带收益信号，不再另加一项
重复计算同一涨价的收益奖励。盈利路径的目标可能为负，因此不提供零下界。

上限为八次决策、每次 32 个选择、100,000 次账户评估。完整笛卡尔积不超过预算时，
逐一评估所有路径；`status="optimal_exhaustive"` 仅表示该有限网格上的最优结果。
否则采用确定性坐标搜索，从全部选择**索引**为零的路径开始，保留经过真实账户回放的
可执行结果；除非确实评估了所有路径，否则返回 `status="heuristic_budgeted"`。
坐标选择不再改善时可提前停止。目标相同则选择索引元组字典序最小的路径。
未穷举时没有全局最优证明或下界。输入校验及计算错误直接向上传递；不会悄悄排除
失败路径后宣称完成穷举。

## 合成验收

`core/tests/test_joint_execution.py` 包含手算有限财富对照、费用和整手及期末风险改变首步、
部分成交仅收一次母单最低佣金、A 无法卖出时不能为可交易 B 融资及有现金的 B 对照、
预测信号时点和未来容量改变首步、精确输入绑定下的暂时与永久冲击恢复、报告延迟等待、
输入不变性、未来可用时间拒绝和如实报告搜索预算。这些合成案例证明实现行为，
不证明样本外预测能力或经过市场校准的执行表现。
