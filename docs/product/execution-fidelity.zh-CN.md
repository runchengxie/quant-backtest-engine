# 执行机制与生产验收

[English](execution-fidelity.md)

每次运行按实际后端核对能力。目前没有把 HftBacktest 或 Backtrader 接入生产。
Nautilus 适配器当前使用 L1 会话。上游具备的 L2、排队和延迟功能，需要通过产品适配与验收后才能使用。

## 当前实现范围

| 模块 | 已有证据 | 待补验收 |
| --- | --- | --- |
| 独立 Python 订单簿 | 价格与时间优先、逐笔成交、逐档撮合和剩余数量 | 交易所特定订单类型与真实排队位置校准 |
| 可选 PyO3 订单簿 | 显式后端、汇总成交和盘口轨迹 | 尚无完整逐笔成交证据，不能用于要求该证据的验收 |
| 分钟执行 | 独立账户记账与回报延迟 | 没有网络撤单延迟与交易所排队模型 |
| Nautilus 适配 | 锁定 0.66.0、L1_MBP 和显式流动性消耗 | 产品深度输入、命令延迟配置及账户全流程验收 |
| 深度重建诊断 | 从初始快照开始，逐档核对目标快照 | 完整行情规范化和保留历史订单身份的队列重建 |
| 场景与规划接口 | 独立账户、有限候选搜索和明确的冲击假设 | 真实成交校准与反事实路径验证 |

锁定版本中的 Nautilus `SimulatedVenueConfig` 已有 `queue_position` 与 `latency_model`。
这些接口可用于后续适配。新增产品输入需要版本化，并与 Nautilus 自己的账户结果一起验收。
旧的请求、结果协议和历史检查点继续保留。

## 从快照开始核对深度

`quant_backtest_core.microstructure.depth_audit.audit_depth(pack)` 是显式调用的 Python 诊断接口。
旧的 `correctness.replay_and_compare` 保留原有行为。旧接口从空簿开始，只比较买一和卖一，不能证明快照间深度重建正确。

输入采用 `SimulatorPack`，事件已按顺序排列，两张快照带有整数价格与数量的 `bid_levels` 和 `ask_levels`。
该接口约定普通限价委托产生撮合，成交记录只用于观察，避免再次扣减同一笔成交。接口尚未独立核对成交记录本身。
`order_type=0` 表示调用方已经按这个约定规范化。其他交易所编码需要单独转换。
撤单沿用现有 pack 的按订单 ID 全撤约定。

初始聚合深度不包含历史订单身份。无法识别的撤单、频道序号不连续或跨频道同刻事件都会返回 `not_comparable`。
快照缺少深度，或事件与任一快照同刻，也会返回无法核对。
价格非法、订单 ID 重复和时间倒退会报错。接口不会用匿名 FIFO 扣减来凑出匹配结果。

匹配结果只覆盖目标快照提供的前 N 档价格与数量。显式空的一侧需要实际为空。
更深的未报告档位和隐藏订单仍不可见。队列身份、完整行情与延迟校准也需要其他证据。
局部序号连续不能证明行情完整，两张快照相同也可能遗漏中间往返变化。

## 排队与时间顺序验收

`core/tests/test_execution_fidelity.py` 用手算情景核对给定到达顺序。
订单晚于成交到达，会错过这次排队机会。撤单到达前发生的成交仍然有效。
逐档撮合同时核对每笔价格和数量。
这些测试验证撮合基础行为，尚未实现网络延迟模型，也不能从聚合 L2 数据确认真实排队位置。

```sh
PYTHONPATH=core/src:python/src python -m pytest \
  core/tests/test_depth_audit.py core/tests/test_execution_fidelity.py \
  core/tests/test_microstructure_matching.py -q -p no:cacheprovider
```

使用隔离的 Python 3.12 或 3.13 测试环境。生产验收还要核对正常安装的 wheel，步骤见[交付验收](acceptance.zh-CN.md)。

## 外部框架对照

继续以 NautilusTrader 作为主要原生执行底座。优先核对其[深度订单簿](https://nautilustrader.io/docs/latest/concepts/order_book/)与[命令延迟](https://nautilustrader.io/docs/latest/concepts/backtesting/execution-flow/)在锁定 0.66.0 中的接口，再决定是否新增生产后端。
这些链接指向上游当前文档，不能代替锁定版本验收。

[HftBacktest](https://hftbacktest.readthedocs.io/en/latest/reference/initialization.html) 的队列和订单延迟模型适合独立对照。
它的[历史行情回放](https://hftbacktest.readthedocs.io/en/latest/order_fill.html)对自身订单改变市场的能力有明确限制。
每次对照要记录软件版本与输入哈希，列明事件时钟和成交假设。
先比较成交数量与时间，再看盈亏。模型结果有差异时，需要解释差异来源。
每个引擎分别记账，不能合并两套现金账本。

[Backtrader](https://www.backtrader.com/docu/) 提供策略研究接口，以及成交量和滑点扩展。
目前这些验收缺口没有显示出必须新增 Backtrader 生产依赖的理由。

## 复现独立队列对照

`examples/diagnostics/compare_queue.py` 使用隔离环境中的 `hftbacktest==2.4.4` 与 Python 3.13。
通过 `PYTHONPATH` 加载本版本的订单簿模块。对照版本不符会报错，生产包不会导入对照依赖。

```sh
PYTHONPATH=core/src:python/src python examples/diagnostics/compare_queue.py
```

手算情景中，前面排着 5 股，自己挂 3 股，对手单数量为 7 股。
在合成发送时刻 110 纳秒下，延迟 1 纳秒到达会成交 2 股。
延迟 150 纳秒到达，会错过 200 纳秒的成交，结果为零。
HftBacktest 使用保守排队与部分成交模型，自有 Python 订单簿使用对应的给定到达顺序。
这次只对照单笔被动订单的队列结果，没有证明共同历史行情或账户完全一致。
脚本断言启动时钟和预期数量，输出版本、输入哈希与观察时刻，同时保留剩余数量。
运行时还需保留完整环境版本。这些纳秒数用于合成验收，不表示真实基础设施的延迟。

## 面向 2,000 万至 5,000 万元的验收

总资产不能单独说明成交容量。需要记录每只股票的订单量、参与率与执行时间，并按流动性分组。
以下步骤分别验收。

1. 在有代表性的交易时段重建盘口。把无法核对的区间与不匹配区间一起报告，保留断档、集合竞价和排序边界。
2. 验证选定产品后端的完整深度输入与账户输出。覆盖部分成交和撤单途中成交，核对实际费用。
3. 改变参与率与延迟假设，检查价差和冲击敏感性。保留未完成数量，机会成本单独报告。
4. 有券商或交易所订单记录后，对照影子订单。按流动性分组估计成交率、执行价差和延迟分布。
5. 上线前验证实际交易系统的敞口限制与故障处理，完成账务核对和恢复测试。引擎验收不代表券商连接已经通过，也不授权真实下单。

合成测试证明具体实现性质。历史重建核对的是明确行情解释下的一致性。实际订单校准属于后续证据。
当前页面不构成管理真实资产的生产就绪认证。
