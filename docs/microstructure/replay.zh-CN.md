# 确定性回放

[English](replay.md)

`ReplaySession` 消费调用方明确提供的 `BackgroundOrder` 和 `InterventionOrder`，不加载或训练生成模型。
每个情景应使用独立引擎和会话；回放维护订单簿，不维护现金账户或投资组合账本。

```python
from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.replay import InterventionOrder, ReplaySession

session = ReplaySession(MatchingEngine(), (100, 50), (101, 40))
session.add_background(10, 1, 101, 3, "background")
session.add_intervention(InterventionOrder(10, 1, 101, 5, "intervention"))
session.run()
assert [fill.buy_id for fill in session.fills] == ["intervention", "background"]
```

同一时刻干预订单先于背景订单，各输入流内部保持稳定输入顺序。每次调用只消费待处理批次一次。
后续批次可以追加到已处理时刻，但不能回退。可变排队订单的时间戳会在产生撮合效果前重新检查。
布尔值或非整数时钟会被拒绝；大于 2^53 的整数时钟在原生有符号 64 位范围内保持精确。

Python 记录完整逐笔成交价、数量、时刻和来源。原生 v0.1 仅返回汇总成交和盘口轨迹：
原生 `fills` 为空表示证据不可用，不表示没有成交。不能据此推断执行成本或冲击。
此次迁移不重建原生逐笔成交，也不新增财务账本。

参见[撮合](matching.zh-CN.md)的事件包排序及正确性说明，以及
[四种执行模式](../development/microstructure-rust.zh-CN.md)。
提供方 B 源码已实现；发布可用性与消费者迁移尚未完成。
