# 确定性撮合开发指南 {#_1}

[English](matching.md)

独立确定性模拟器已在提供方 B 的当前源码中实现；消费者切换仍须等待 B 合并及安装包验证。
迁移保留固定 Platform 版本的算法、整数价格、数量和时钟契约。
这是底层限价订单簿 API，不是已注册的 ProductManifest 财务后端。

## 代码结构 {#_2}

`quant_backtest_core.microstructure.matching` 提供 `LimitOrderBook`、`MatchingEngine`、
`Fill`、`Trade`；`pack` 提供 `SimulatorEvent`、`SimulatorPack`、`build_simulator_pack`；
`ordering` 提供 `sort_simulator_events` 及排序依据；`correctness.replay_and_compare`
比较重建快照。目标快照缺少买卖一侧时仍标记为不可比较，不视为空盘口匹配成功。

价格单位为整数分、数量为整数股、模拟器时钟为整数毫秒，不是 ProductManifest 的 UTC 纳秒时钟。
价格优先、同价 FIFO、逐笔成交价、部分撤单和原有重复 ID 行为均保留；汇总成交价格仍为最后一笔成交价。
调用方应提供唯一 ID：重复挂单 ID 不会被拒绝，可能共用撤单索引，不代表已去重。
重复 ID 的撤单不在后端一致性保证范围内：Python 索引指向最后一笔重复订单，原生撤单选择队列中第一笔匹配订单。
同价 5 股和 7 股共用 ID 时，先撤 3 股再全撤该 ID，Python 盘口为空，原生仍剩 7 股且该 ID 已无索引。
这是保留并纳入测试的历史差异；调用方须使用唯一挂单 ID。

```python
from quant_backtest_core.microstructure.matching import MatchingEngine

engine = MatchingEngine(backend="python")
engine.apply_order("sell", -1, 101, 10)
trade = engine.apply_order("buy", 1, 101, 4)
assert trade.fills[0].volume == 4
assert engine.lob.best_ask() == (101, 6)
```

同一时刻，单通道且序号完整时按交易所序号、源索引排序；跨通道或缺失序号时按源顺序排列。
所有排序键相同则保留输入顺序。同一时刻快照排在非快照事件之后。
这些规则不证明跨通道交易所总顺序，也不证明行情完整。

## 本地验证 {#_3}

运行 `uv run --project core --locked pytest core/tests/test_microstructure*.py -q`。
仅在独立原生扩展未安装时跳过原生测试；必测原生环境设置 `TICKNET_REQUIRE_RUST=1`。
参见[原生构建](../development/microstructure-rust.zh-CN.md)与[回放](replay.zh-CN.md)。
测试仅使用合成样本。

[原始源码与许可证](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/packages/microstructure)
仍为 Apache-2.0。学习式 `OrderGenerator`、模型、数据集、Torch 和事件流训练仍由 Platform 负责；
这里不提供经过真实市场校准的内生市场模拟。
