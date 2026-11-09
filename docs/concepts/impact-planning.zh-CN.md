# 考虑冲击状态的滚动规划

语言：简体中文 · [English](impact-planning.md)

`quant_backtest_core.planning.impact_planning.plan_with_impact` 提供连续数量、只做多、
对角暂态冲击下的有限期规划。仅把第一步作为候选交易，由现有执行模块复核数量、
费用、价格和时间后执行，再用实际成交后的持仓、可用现金和冲击状态重新规划。
原有 `quant_backtest_core.planning.multiperiod.plan_trades` 的默认行为保持不变。

支持的模型是采用保守仿射现金约束的凸二次规划（QP）。
它并非在精确的经济现金可行域内求最优解。成交现金随交易量呈二次变化，不能把该
约束称为仿射约束。结果分别报告并检查真实经济现金和保守下界。因此，容量设置可能
使经济上买得起的交易被模型排除。

## 输入与目标函数

`ImpactPlanningRequest` 使用原始股数和人民币（`units="raw_shares_CNY"`）：

- `initial_holdings`、`unaffected_prices`、`initial_transient`、`transient`、
  `decay_seconds` 的形状为 `(N,)`。价格是不受自身交易影响的固定正价格。初始位移
  可正可负，单位是价格单位。冲击系数是每一有符号股数引起的价格变化。衰减时间
  为严格正的秒数，与 `LinearImpact` 的 `linear-impact.v1` 一致。初始位移必须已
  推进至 `decision_ns`，永久冲击为零。
- `expected_returns` 和有限非负的 `capacity` 形状为 `(H,N)`。`covariances`
  为 `(H,N,N)` 的对称半正定收益率协方差矩阵。`1e-12` 内的对称性和特征值舍入误差
  会经过对称化及半正定投影处理。`step_seconds` 包含 `H-1` 个非负秒间隔。第一步
  的相对时间是零，允许同一时刻的多个步骤。预测收益奖励每一步交易后的持仓，
  不计入可花费现金。
- `initial_cash`、`reserved_cash`、`risk_aversion` 有限且非负，预留现金不超过
  初始现金。可选的 `(N,)` 数组 `locked_holdings` 是整个规划期的持仓下限，不能
  高于初始持仓。某一步某个标的容量为零时不能交易。
- `fee_per_share` 和 `spread_per_share` 是非负的固定人民币/股费用，可以是标量
  或 `(N,)` 数组。价差按交易方向进入成交价，手续费单独扣一次。明确拒绝非零
  `fee_rate`、`minimum_fee`、`quantity_step`、`permanent`。整数手数和按成交额
  收费需要由支持相应语义的模块另行处理、复核，不能静默近似。
- `decision_ns`、`forecast_available_ns`、`risk_available_ns`、`state_available_ns`
  是 UTC 整数纳秒，任何输入的可用时间都不能晚于决策时间。这不等于认证数据来源
  或核实模型拟合历史，调用方仍须保留相关记录。数组使用相同的标的顺序。调用期间
  不要修改输入数组。

记有符号交易量为 `q[t]`，交易后持仓为 `h[t] = h[0-] + sum(q[:t+1])`，
固定价格为 `p`，初始净值为 `V = initial_cash + p @ h[0-]`，相对时间为 `s[t]`。
每个标的的成交前暂态位移和成交价格位移为：

```text
d[t] = exp(-s[t]/tau)*d[0-] + k*sum(exp(-(s[t]-s[u])/tau)*q[u], u<t)
offset[t] = d[t] + k*q[t]/2
state_after[t] = d[t] + k*q[t]
```

目标函数以人民币返回：

```text
sum_t (risk_aversion/(2*V) * (p*h[t])' Sigma[t] (p*h[t])
       - alpha[t]' (p*h[t])
       + q[t]' offset[t] + (fee+spread)' abs(q[t]))
```

每个标的的暂态二次核 `k*exp(-abs(s[t]-s[u])/tau)` 是半正定的，风险项也半正定。
绝对值线性成本使用辅助变量表示。程序检查最终 Hessian 矩阵。求解使用净值归一化的
交易金额、解析梯度和 SLSQP。求解器报告成功并不构成独立的数值全局最优证书。
不假设期末清仓，也不把剩余持仓估值当作现金。带符号的初始冲击可能让反向交易受益。
但在零初始冲击和固定未受影响价格下，闭合往返交易不能产生冲击利润。

## 仿射现金下界与执行复核

根据容量 `c[t]`，构造非负的成交位移上界：

```text
B[t] = abs(exp(-s[t]/tau)*d[0-]) + k*c[t]/2
       + k*sum(exp(-(s[t]-s[u])/tau)*c[u], u<t)
cash_lower[t] = initial_cash - sum(p' q[u] + (B[u]+fee+spread)' abs(q[u]), u<=t)
```

QP 通过绝对值辅助变量约束 `cash_lower[t] >= reserved_cash`，所有约束都是仿射
约束或变量边界。若 `B[t]+spread >= p`，容量和状态组合可能产生非正成交价，程序
直接拒绝。这些限制和现金下界都是有意采用的保守条件。现金在每一步净结算后检查。
若同一步买入依赖卖出收入，应先执行卖出。真实结算规则、挂单冻结资金和价格变化
仍须由执行模块复核。

返回交易量会独立通过 `LinearImpact` 推进状态，成交价包含本次增量的一半。现金
只扣有符号成交额及固定手续费，不能把冲击再作为额外费用扣一次。`ImpactPlan`
返回交易量、第一步候选量、持仓、成交前后暂态状态、成交价、经济现金、保守现金下界、
目标值、求解器状态和消息、具名残差。残差按初始净值或对应名义金额归一化，无量纲，
不得超过 `1e-7`。求解失败或独立检查不可行时抛出 `ValueError`。
`request_digest` 使用 SHA-256 绑定请求快照的数值 float64 字节、数组形状、精确
整数时间、配置以及版本化模型约定。它不认证数据来源。请同时保存源数据字节、来源
记录和实现提交版本。未知来源仍应标为未知。

第一步数量仍是连续值，不是已提交订单。实际下单前由现有执行模块完成数量取整和
可行性复核，并确认费用、冲击约定与实际时间间隔一致。后续规划量既未预留，也未成交。
实际成交后恢复执行模块状态再规划，不要用假设的未来交易推进真实冲击状态。合成
测试将恰好符合整手要求的第一步送入现有分钟撮合模块，并核对状态恢复和现金单次扣款。

## 复现与限制

`core/tests/test_impact_planning.py` 包含独立手算解、未来容量和收益变化、现金预留、
锁定持仓、精确请求绑定、撮合及状态恢复、失败拒绝等检查，也验证股数单位与货币
缩放、衰减往返交易和同一时刻拆单的半增量约定。拆单不变性针对经济冲击成本。
容量划分变化时，保守现金下界不保证相同。这些是未校准的合成机制测试，不是市场
冲击估计，也不是实际市场最优性的证据。

安装已构建的 SDK 与 Core wheel，显式选择 `planning` extra，固定 NumPy 2.2.6、pandas 3.0.6 和 SciPy 1.18.1。从源码树外使用已安装的解释器执行：

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/core/tests/test_impact_planning.py" -q -p no:cacheprovider
```

改编自 [Apache-2.0 固定原文](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/impact-planning.zh-CN.md)。当前实现位于尚未发布的 provider B 分支；Core 在 Task 11 前仍为 0.1.0，消费者切换另行进行。

## 条件现金与完整会话恢复

带符号的规划现金假设所提买卖全部发生，只是一步净结算后的条件金额，既非到账现金，
也非订单预留。实际订单不能花费尚不可用的卖出款。有限持仓和策略分配要求更严格的预先备款；
必须区分这些范围，不能因此改写 QP 现金公式。受阻卖出测试从十股 A、零现金开始：
假设的换仓可以规划卖 A 买 B，但真实卖出受阻后仍为十股 A、零现金。
下一次请求据此填入真实状态和零卖出容量，不能买入 B。

`core/tests/test_planning_session.py` 经 `sessions.open_session` 执行，保存完整源码绑定检查点，
再调用 `sessions.restore_session` 恢复后重新规划。一次一百股成交价 10.05，现金剩 8995，
暂态状态为 0.1，精确 UTC 纳秒时钟为 1767576720000000000。十进制手算成交额为 1005；
执行方原始二进制浮点成交额保留为 1005.0000000000001。恢复前后的完整检查点和最终结果
严格相等。下一步立即执行的候选返回原始数量 99.99999999999999（手算最优为 100）、价格 10.15、
预计现金 7980；候选本身不改变真实持仓、
现金或冲击。若以后才执行，必须计入实际时间衰减。

## 多期权重规划

`quant_backtest_core.planning.multiperiod.plan_trades(MultiPeriodRequest(...))`
接收调用方提供的收益预测和半正定协方差，不构造估计。权重和成本按固定决策时净值计量，
逐资产成本为 `cost_linear * abs(trade) + 0.5 * cost_quadratic * trade**2`。
只做多持仓、预算、逐资产逐期交易上限、布尔可交易状态、预留现金及累计预计成本共同约束路径。
预测收益永不补充现金，决策和预测时钟拒绝未来才可用的预测。没有期末强制清仓、卖空、
借款、交易所队列或自动读取未来数据。只执行 `first_trade`，再按实际已送达状态重新规划。
SLSQP 使用 ftol 1e-12、maxiter 2000；失败、非有限解或残差超过 1e-7 均报错。
这个有限研究接口不提供独立数值最优证书。使用已安装解释器同时运行
`core/tests/test_multiperiod.py`、`core/tests/test_planning_session.py` 和冲击规划测试。
通用风险估计及带符号优化器仍属于 Platform。
