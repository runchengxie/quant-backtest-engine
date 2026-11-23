# 考虑冲击状态的滚动规划

语言：简体中文 · [English](impact-planning.md)

`quant_backtest_core.planning.impact_planning.plan_with_impact` 提供连续数量、只做多、
对角暂态冲击下的有限期规划。仅把第一步作为候选交易，由现有执行模块复核数量、
费用、价格和时间后执行，再用实际成交后的持仓、可用现金和冲击状态重新规划。
原有 `quant_backtest_core.planning.multiperiod.plan_trades` 的默认行为保持不变。

规划器采用保守仿射现金约束，求解凸二次规划（QP）。成交现金随交易量呈二次变化，
规划器用仿射下界控制预算，并分别报告经济现金与保守下界。这组约束会收缩可行范围，
部分经济现金足够的交易也可能被排除。容量设置会影响这一下界。

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
  是 UTC 整数纳秒，任何输入的可用时间都不能晚于决策时间。时间校验检查输入声明，数据来源与模型拟合历史由调用方另行核实并保留记录。数组使用相同的标的顺序。调用期间
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
交易金额、解析梯度和 SLSQP。求解器的成功状态用于报告本次数值求解结果，数值全局最优性仍需独立证书。
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

第一步给出连续数量的候选交易。实际下单前由现有执行模块完成数量取整和
可行性复核，并确认费用、冲击约定与实际时间间隔一致。后续规划量既未预留，也未成交。
实际成交后恢复执行模块状态再规划，不要用假设的未来交易推进真实冲击状态。合成
测试将恰好符合整手要求的第一步送入现有分钟撮合模块，并核对状态恢复和现金单次扣款。

## 复现与限制

`packages/core/tests/test_impact_planning.py` 包含独立手算解、未来容量和收益变化、现金预留、
锁定持仓、精确请求绑定、撮合及状态恢复、失败拒绝等检查，也验证股数单位与货币
缩放、衰减往返交易和同一时刻拆单的半增量约定。拆单不变性针对经济冲击成本。
容量划分变化时，保守现金下界不保证相同。这些检查覆盖合成机制。市场冲击参数和实际市场中的最优性仍需独立验证。

安装已构建的 SDK 与 Core wheel，显式选择 `planning` extra，固定 NumPy 2.2.6、pandas 3.0.6 和 SciPy 1.18.1。从源码树外使用已安装的解释器执行：

```bash
python -I -B -m pytest "$CODE_ROOT/quant/quant-backtest-engine/packages/core/tests/test_impact_planning.py" -q -p no:cacheprovider
```

改编自 [Apache-2.0 固定原文](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/concepts/impact-planning.zh-CN.md)。当前实现位于尚未发布的 provider B 分支；Core 当前源码为 0.2.0，整体审查和合并仍待完成，消费者切换另行进行。

## 条件现金与完整会话恢复

带符号的规划现金假设所提买卖全部发生，只是一步净结算后的条件金额，既非到账现金，
也非订单预留。实际订单不能花费尚不可用的卖出款。有限持仓和策略分配要求更严格的预先备款；
必须区分这些范围，不能因此改写 QP 现金公式。受阻卖出测试从十股 A、零现金开始：
假设的换仓可以规划卖 A 买 B，但真实卖出受阻后仍为十股 A、零现金。
下一次请求据此填入真实状态和零卖出容量，不能买入 B。

`packages/core/tests/test_planning_session.py` 经 `sessions.open_session` 执行，保存完整源码绑定检查点，
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
`packages/core/tests/test_multiperiod.py`、`packages/core/tests/test_planning_session.py` 和冲击规划测试。
通用风险估计及带符号优化器仍属于 Platform。

## 独立场景组合

可运行[类型化目标场景示例](../product/scenarios.zh-CN.md)，检查分钟账户相互独立。预测与风险估计仍在外部，初版适配器只接受 null risk 和既有目标权重策略。计划卖出所得不能资助买入：补充实际所有者测试仅阻止 A 卖出、保持 B 可交易，再用另一个确有现金的 B 对照证明现金约束。连续候选 `99.99999999999999` 仍是条件候选，不做舍入或提交。日频所有者变体仍待后续迁移。

## 安装后的规划示例

按文档固定数值依赖版本并安装 `[planning]` 后，可直接执行以下合成示例。数组使用既有数值叶子 API；
公开场景的金额和纳秒传输字段仍为字符串。本案例的首步数量恰为整数。计划现金按假设成交计算，
可用现金由实际成交及回报送达状态确认。示例输出规划结果，实时所有者保持原状态。

```sh
python -I -B - <<'PY'
import numpy as np
from quant_backtest_core.planning.impact_planning import ImpactPlanningRequest, plan_with_impact

clock = int("1767576540000000000")
request = ImpactPlanningRequest(
    initial_holdings=np.array([0.0]), initial_cash=10000.0,
    unaffected_prices=np.array([10.0]), expected_returns=np.array([[0.1]]),
    covariances=np.array([[[1.0]]]), step_seconds=np.array([]),
    initial_transient=np.array([0.0]), transient=np.array([0.001]),
    decay_seconds=np.array([10.0]), capacity=np.array([[100.0]]),
    risk_aversion=0, decision_ns=clock, forecast_available_ns=clock,
    risk_available_ns=clock, state_available_ns=clock,
)
plan = plan_with_impact(request)
assert plan.first_action == (100.0,)
assert plan.cash == (8995.0,)
print({"first_action": plan.first_action, "conditional_cash": plan.cash,
       "request_digest": plan.request_digest})
PY
```

## 连续控制参考与后续路线

Engine 已有多期规划：`planning.multiperiod` 和 `planning.impact_planning`
使用调用者提供的预测进行有限范围数值规划，后者还包含瞬态冲击与保守现金边界。
首个动作经账户所有者复核后执行，再重新规划。这与
[Boyd 等人的多期凸优化交易框架](https://web.stanford.edu/~boyd/papers/cvx_portfolio.html)
中的 MPC 思路一致，并不表示 Engine 负责预测估计。

独立模块 `quant_backtest_core.planning.liquidation_reference` 只依赖标准库，
提供单资产连续控制的解析基准，求解

```text
最小化 0 到 T 上 [eta*v(t)^2 + lambda*sigma^2*x(t)^2] 的积分
约束 x'(t)=-v(t)，x(0)=X>=0，x(T)=0。
```

时间单位为秒，库存为原始股数，`sigma` 为绝对价格波动率，单位为
币种/(股*sqrt(秒))，`lambda` 为 1/币种，`eta` 为币种*秒/股²。
目标值及剩余目标值以同一币种计量，`v` 为股/秒；公式没有隐含的二分之一。
这个简化案例体现了 [Almgren–Chriss 的执行成本与风险权衡](https://doi.org/10.21314/JOR.2001.041)，
并不复现该论文的全部设定，也不是经过市场数据校准的模型。

记 `a=lambda*sigma²`，`k=sqrt(a/eta)`，数学上的精确解为
`x(t)=X*sinh(k*(T-t))/sinh(k*T)`、
`v(t)=X*k*cosh(k*(T-t))/sinh(k*T)`。
到期前、任意当前库存 `y` 的价值函数为 `V(t,y)=A(t)*y²`，其中
`A(t)=eta*k*coth(k*(T-t))`。它满足
`V_t + a*y² - V_y²/(4*eta)=0`，即 `A'=A²/eta-a`，
终端边界为 `V(T,0)=0`、`V(T,y>0)=infinity`。
风险为零时取 TWAP 极限：`x=X*(T-t)/T`、`v=X/T`、`A=eta/(T-t)`。
`evaluate` 返回的是从初始状态出发、沿最优路径的剩余目标值，
不能将其解释为任意实际成交后库存的价值。

```python
from quant_backtest_core.planning.liquidation_reference import LiquidationModel, evaluate

model = LiquidationModel(100.0, 10.0, 2.0, 0.0, 3.0)
point = evaluate(model, 4.0)
assert (point.inventory, point.sell_rate, point.remaining_value) == (60.0, 10.0, 1200.0)
```

到期库存和剩余值为零，卖出速率取左极限。实现采用指数比值避免双曲函数溢出，
在 `k*T < 1e-8` 时采用 TWAP 极限（修正量处于舍入误差尺度），
允许极小的尾部库存下溢为零。非有限或非法输入、不可表示的系数与时间尺度、
正风险、初始速率或初始成本尺度的次正规或下溢中间值、溢出的初始目标值或输出均明确抛出 `ValueError`。
这些是浮点规划结果，不改变账户的十进制定点金额运算。

| 要回答的问题 | 已有能力或基准 | 下一步所需证据 |
| --- | --- | --- |
| 多期规划是否有帮助？ | 给定预测的多期/QP/MPC 与合成回归案例 | 用相同预测、约束及账户成交规则比较样本外首个动作 |
| 简单案例的成本风险清算是否正确？ | 解析 LQ 参考；手算零风险 TWAP、成本数值积分、沿路径 HJB 残差、终端与极端尺度测试 | 先统一单位与目标函数，再验证离散化收敛 |
| 瞬态冲击规划是否应与参考相同？ | 模型不同：逐笔瞬态成本包含 `k*q²/2`、衰减及状态 | 不能直接等同于速率成本 `eta`；先推导时间步转换并消除瞬态、现金与预测差异 |
| 是否已解一般随机控制或 HJB PDE？ | 尚未实现；此处只是闭式特例 | 增加求解器前先定义状态、动作、随机动态、边界及独立收敛检查 |
| 做市报价能否直接采用清算路径？ | 参考没有报价与成交到达模型 | [Avellaneda–Stoikov](https://math.nyu.edu/inmemoriam/avellaneda/HighFrequencyTrading.pdf) 研究库存相关的双边报价和到达强度，需单独验证做市问题 |

下一步应先用合成参数检查基准一致性与敏感性。实证参数估计仍在本参考之外。
这里不增加现金账本、成交、学习型 alpha、整手约束、参与率上限、费用、永久冲击、
瞬态冲击状态或生产订单接入。测试通过只支持这个有限案例，不能推出一般 HJB
最优性或实际盈利。

## 离散收敛与配对执行证据

可选 planning 模块 `planning.liquidation_discrete.solve(model, capacities)`
增加单资产、只卖不买、期末库存归零的参考求解器。每个容量是等长周期内的最大
成交股数；不可行容量及求解失败会被拒绝。库存端点 `x,y`、卖出数量 `q=x-y`
的精确分段线性积分为
`eta*q*q/dt + lambda*sigma*sigma*dt*(x*x+x*y+y*y)/3`，与连续参考目标完全一致，
不调整系数。它独立于前述使用给定预测的瞬态冲击规划器。

固定收敛案例为库存3、期限2秒、eta 1.5、波动率0.8。零风险在四种网格上均为
TWAP，目标值6.75。风险厌恶0.7时解析目标值为9.245677060235423：

| 周期数 | 离散目标超额 | 最大库存节点误差 |
| --- | --- | --- |
| 8 | 0.003603958 | 0.000285046 |
| 16 | 0.000902730 | 0.000071120 |
| 32 | 0.000225791 | 0.000017805 |
| 64 | 0.000056455 | 0.000004410 |

网格翻倍时正风险目标差约缩小至四分之一。这只是限定数值检验，不是通用
HJB/PDE 求解器，也没有完成市场校准。

`planning.execution_comparison.fixed_study()` 保留预先确定的32行合成结果：
目标10股、期限4秒、8期、波动率1、eta为0.5或2、风险厌恶为0或1；实际容量
为每期2股，或前两期为零、其后每期2股。所有方法初始预测容量均为每期2股，
alpha为零。开环规划提交最优日程，TWAP每期提交1.25股；两者均只提交一次，
受限部分不重试。滚动方法根据已成交库存重算，只观察过去成交，不预知未来
实际容量。重算不可行则记录失败并提交零，不在最后一期强制补齐。

eta 0.5、零风险且无停顿时，开环、TWAP与滚动方法都完成，成本12.5。前两期停顿时，一次
规划与TWAP剩余2.5股，累计成本9.375；滚动方法完成，成本16.666667。
较低的部分成本**不代表**更优的清仓目标值。只比较相同初始状态、相同期限且
完成清仓的日程。滚动方法的表现同时包含适应能力；完成取决于容量场景。
风险为1且无停顿时，开环规划与滚动成本为101.571275，TWAP为145.833333。
这些数字描述假设的成本泛函，不是投资收益。

没有新增现金账本、随机价格模拟、训练预测或净收益结论。在锁定安装的Core环境
运行 `python scripts/verify/export_execution_comparison.py --output <external.json>`
导出全部行及源码身份。源码中的配对实施计划
`docs/superpowers/plans/2026-11-24-execution-comparison.zh-CN.md`
保留了结果产生前固定的协议。


最初实现用 once 指定一份固定最优日程，现明确命名为 `open_loop`（开环）。
按原要求补充字面意义的 `immediate`（一次成交）：第0期请求10股，其后提交零。
同样受预测与实际容量限制，无停顿时只成交2股、剩余8股；初始停顿时不成交、
剩余10股。意图日程违反预测容量，故 `planned_capacity_feasible=false`、
`planned_cost=null`。其他方法也报告容量可行标记。不假设一次全部成交，不与
完成清仓的目标值直接排名。此修正只补齐方法范围，不改变成本、风险、容量或
原24条路径的数值。主网格保留32行，不可行诊断保留四行。
