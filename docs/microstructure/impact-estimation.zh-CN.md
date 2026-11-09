# 执行冲击估计

[English](impact-estimation.md)

`quant_backtest_core.microstructure.impact` 拥有确定性执行估计器，已在提供方 B 工作树实现，**B 门合并前未发布**。它复用[订单簿回放](replay.zh-CN.md)中的同一 `ReplaySession`、`ReplayFill`。[原始代码](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/packages/microstructure/src/ticknet/simulator/impact.py)是真实历史参考；原项目没有专门的 impact-estimation 文档页。本次保留包括 `_mid` 在内的原模块函数体。

## 计划与单位

`ExecutionSchedule(side, total_volume, n_child=1, start_time_ms=1000, end_time_ms=5000)` 的 +1 为买、-1 为卖，数量为原始整数股，时间为整数回放毫秒，价格为原始整数单位。这是限价子单计划，不保证成交，也不是已校准交易算法。

总量整除子单数，余量给最后一单；第 i 单时钟为 `start_time_ms + max(end_time_ms-start_time_ms, 1)*i//n_child`。运行前，各子单限价取当时对手最优价；缺失时买用 `int(mid_before+1)`、卖用 `int(mid_before-1)`。排入子单时选择限价，不先把市场推进至各未来时钟。随后跑完全部已排队事件，包括计划结束后的背景事件。

顺序保持原样：先检查 Python 逐笔成交能力，再校验方向、数量、子单数、待处理队列、起始和子单时钟，取得初始中价与成交游标，最后预留子单 ID。`IMPACT{i}` 避开队列历史、已预留名和活跃订单簿 ID。显式静态订单 ID 的唯一性仍由调用者负责；本次不收紧旧重复 ID 准入，也不消除已刻画的后端差异。

```python
from quant_backtest_core.microstructure.impact import ExecutionSchedule, ImpactEstimator
from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.replay import ReplaySession

session = ReplaySession(MatchingEngine(backend="python"), (100, 50), (101, 30))
result = ImpactEstimator(session).estimate(ExecutionSchedule(1, 40))
assert (result.filled_volume, result.unfilled_volume) == (30, 10)
assert result.execution_vwap == 101.0
```

## 实际成交和描述性价差

`ImpactResult` 保留 `mid_before`、`mid_after`、方向调整的 `slippage_bps`、`filled_volume`，以及 `unfilled_volume=0`、`execution_vwap=None`、`execution_slippage_bps=None`、`fills=()` 默认值。fills 仅含本次新增的实际子单成交，包括运行中稍后被动成交，排除纯背景交易。按买卖方向选择 buy_id 或 sell_id 归属。数量和成交量加权价直接来自这些逐笔成交，不以汇总交易替代；未成量为请求量减已归属成交量。连续运行不重复计入此前成交。

初始中价为正时，中价滑点为 `side * (mid_after-mid_before)/mid_before * 10000`，执行滑点为 `side * (execution_vwap/mid_before-1) * 10000`，单位基点。无成交时 VWAP 与执行价差为 `None`，不是零。它们描述合成回放干预，不构成已校准的真实市场因果冲击。

## 原生与空订单簿限制

原生回放目前没有逐笔成交证据。非 Python 引擎在计划验证、ID 预留、订单簿变更**之前**抛原始 `NotImplementedError`，不汇总替代、不静默回退。原生拒绝验收在 Python 3.12/3.13 的真实安装 wheel 上运行；缺少原生执行不能算一致性通过。

`_mid` 在双边取均价，单边取唯一最优价，空簿返回原始哨兵 **0.0**。初始中价非正时旧中价滑点仍为 **0.0**，执行价差不可得。空簿零数量计划的前后中价和滑点均零，无执行价格证据。买子单可按回退价 1 挂单，因此即使无成交，mid_after 也可为 1。这些哨兵**不表示测得零市场冲击**；耗尽唯一有量的一侧还会得到 mid_after=0，买方原始中价滑点为 -10000 基点，卖方为 +10000 基点，即使成交价格等于起始报价也如此。本次刻画原输出而不修写。

估计器不扣账户现金。中价变化和执行价差仅供描述，不可另加现金费用；它不同于[LinearImpact 与纸面账户反馈](../backtest/account-feedback.zh-CN.md)中已嵌入成交价格的冲击，费用只计一次。学习模型 `generator.py` 和消费者诊断 `sqrt_law.py` 留在 Platform，不宣称校准平方根冲击规律。

## 验证与归属

完整迁移原 11 个冲击测试、2 个回放时钟准入测试、1 个原生逐笔拒绝测试，并新增空簿刻画。验收在仓库外使用常规安装的 core wheel，设置 `TICKNET_REQUIRE_RUST=1`，共 15 项冲击测试且原生零跳过。来源/输出一致性仅容许归属身份差异，回放算法及价格时间单位不变。回放与冲击导入只需标准库及基础 SDK 依赖，无需科学计算、训练、Platform 或 Runtime 包。
