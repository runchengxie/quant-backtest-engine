# 保留共同时间块的合成市场路径

语言：简体中文 · [English](market-paths.md)

通过 `quant_backtest_core.backtest.market_paths` 可生成带有共同时间块的收益与流动性替代路径，
同一抽样时间块同时作用于所有资产。这些是未经真实市场校准的合成情景。
结果分位数仅描述所选生成器，不能解释为未来市场结果的概率。

```python
import pandas as pd
from quant_backtest_core.backtest.market_paths import (
    MarketPathSpec,
    fit_market_paths,
    generate_market_paths,
)

# training_panel 是包含下述必需列的平衡合成面板。
training_panel = pd.DataFrame([
    dict(symbol=symbol, time=time, open=price, high=price, low=price,
         close=price, volume=100, amount=100 * price)
    for symbol in ["A", "B"]
    for time, price in zip(
        pd.date_range("2026-01-01", periods=3, tz="UTC"), [10.0, 11.0, 8.8]
    )
])
model = fit_market_paths(
    training_panel,
    cutoff=pd.Timestamp("2026-01-31", tz="UTC"),
    spec=MarketPathSpec(block_length=2, seed=7),
)
paths = generate_market_paths(
    model,
    calendar=pd.date_range("2026-02-01", periods=8, tz="UTC"),
    scenario_ids=["illustration-1"],
    initial_prices={"A": 100.0, "B": 200.0},
)
```

## 输入与拟合契约

必需列为 `symbol,time,open,high,low,close,volume,amount`。
`time` 和 `cutoff` 必须为带时区的 pandas 时间戳，含义是信息可用时间，内部统一为 UTC。
只有不晚于截止时刻的行参与内容校验、冻结快照和哈希计算。输入的所有时间戳本身均须有效。
额外列不参与生成，也不计入数据身份。

价格为有限且为正的未复权价格，单位是每股报价货币。成交量是有限非负股数，成交额是有限非负报价货币。
OHLC 须满足 `low <= open,close <= high`。成交量大于零时，
`amount / volume` 必须落在最低价和最高价之间。零成交量必须对应零成交额，
其正价格只表示已知标记价格，不证明可以成交。缺失或未知价格被拒绝，不裁剪、不填补无效证据。

首版只支持 `missing_policy="reject"`。每个拟合时刻必须恰好包含每个资产的一行，资产按名称排序。
同一资产的重复时间戳、缺失单元的面板，以及不足 `block_length + 1` 个时刻的历史均被拒绝。
第一个时刻仅提供前收盘价，不作为可抽样的收益观测。

`FrozenPathModel` 保存不可变的嵌套元组和冻结的参数，不保留共享 DataFrame。
`source_hash` 绑定实际消费的规范化数值、资产顺序和可用时间。
`model_hash` 另绑定 UTC 截止时刻、参数、单位和生成器版本 `common-moving-block.v1`。
输入行顺序、同一时刻的不同表示时区以及数值 dtype 不构成不同的数据身份。
截止时刻之后的行不改变模型身份。这些哈希不证明外部数据来源或代码仓库版本，
调用方仍须在运行记录中保存源代码版本。

## 生成与标识

`generate_market_paths(model, calendar, scenario_ids, initial_prices)` 返回情景标识到 DataFrame 的字典。
输出日历必须非空、严格递增、无重复、带时区，且全部晚于拟合截止时刻。
初始价格必须有限且为正，键恰好覆盖拟合资产，含义是第一根生成 bar 之前的收盘价。
情景标识须为非空且不重复的字符串。空标识列表返回空字典。

生成器在所有可用的定长、不回绕的连续观测块中均匀抽样。SHA-256 抽样键绑定模型身份、种子、
情景标识和块序号。所有资产使用同一个块索引。每个抽样 OHLC 价格乘以
`生成路径前收盘价 / 抽样来源前收盘价`。保留来源成交量，成交额乘以同一价格因子，
从而保留来源成交均价相对 OHLC 的关系。零成交量和零成交额仍为零。
来源成交均价仍按浮点数精确不等式校验。只有生成过程中的成交均价算术误差可以越过 OHLC 边界，
且必须同时不超过该边界的四个 ULP（按 `math.ulp(boundary)` 计）和八倍机器精度的相对误差，不设绝对容差下限。
相对误差上限避免在接近零的次正规浮点数区域放行很大的百分比偏差。
数值保持原样，不裁剪，也不修正成交额。成交量大于零时，成交均价仍必须有限且为正。
超过该范围的偏差（包括成交额小到浮点数无法表示而下溢）以及其他不有限或不一致的输出均显式失败。
`vwap_coherence` 属性记录这一数值契约。

块内保留来源收益、流动性观测的先后顺序和跨资产配对。块边界不保留来源连续性，
不能声称准确保留长期依赖结构。输出时间间隔由调用方提供。生成器保留观测顺序，
不保留来源的实际时间间隔，也不模拟观测之间的连续路径或市场内生响应。

输出按日历、规范资产顺序排列，附带 `event_id`、`sampled_block_id`、`source_time`、
`block_offset` 和 `block_boundary`。块标识包含情景和块序号，重复抽中同一来源仍属于不同输出块。
`generation_hash` 绑定模型、情景和规范化初始价格。事件标识绑定该生成哈希、输出序号、UTC 时刻和资产。
改变初始价格会改变证据身份，但不改变抽样块。情景请求顺序、分批请求方式以及初始价格字典的
插入顺序不影响路径。延长相同日历会保留原有前缀。相同参数的重复调用具有相同的规范化表格序列化结果，
但不保证跨 pandas 版本的 pickle 字节相同。

表格属性记录合成范围、证据类别、来源/模型/生成哈希、截止时刻、单位、种子、情景、块策略、初始价格和连续性限制。
导出时须保留属性或与行数据一并保存。CSV 本身不保留属性。
调用方须在其试验登记表保留所有尝试与失败。确定性路径的重复运行是复现，不是新的独立市场样本。

## 执行边界

输出只包含收益与流动性路径，不提供公司行动、涨跌停或可交易性语义，元数据明确记录这些缺口。
额外的来源列不会自动补齐执行语义。执行前，调用方必须补充并验证一致的合成执行契约，
拒绝不支持的路径，并重新计算受影响的特征、标签和决策。撮合、账户核算和费用仍归既有模块负责。
本模块不新增模拟器，不提供真实市场校准或样本外结论。


## 独立的压力与冲击模块

市场路径和 `JointStress` / `stress_bars` 需要 core 的 `scenario` extra。
压力变换保留输入的每日涨跌停价，将合成 OHLC 和 VWAP 限制在该区间，
把缩减后的成交量向下取整为股数。`keyed_uniform` 使用种子、证券、
UTC 时钟和随机流名称作为键，行顺序不会改变冲击结果。
风险和冲击倍数由调用方明确使用；本模块不运行风险估计或修改账户。

`quant_backtest_core.backtest.impact.LinearImpact` 的系数单位为每带符号股数
对应的价格变化，时间是同一时钟上的经过秒数。暂态影响指数衰减，永久影响不衰减。
每笔成交价包含本次线性增量的一半，避免通过同一时刻拆单降低模型成本。
`preview` 不修改状态；`execute` 和 `offset` 推进对应证券的状态，时钟不能倒退。
检查点保存系数及各证券状态，但不意味着旧账户检查点可迁移。
不同情景必须使用独立模型实例和账户。

`backtest.impact_scenarios.linear_impact_scenario` 是另一项固定无冲击价格、
无时间衰减的敏感性计算。永久和临时系数单位为货币/股²；每片临时成本呈二次关系，
没有时间或成交量校准。非正成交价会被拒绝，手续费是单独的货币金额。
这些是未校准的敏感性假设，不是实测冲击参数或未来发生概率。

```python
from quant_backtest_core.backtest.impact_scenarios import linear_impact_scenario

result = linear_impact_scenario(
    [4, -4], unaffected_price=100, permanent=0.5,
    temporary=0.1, fee_per_share=0.25,
)
assert [fill.execution_price for fill in result.fills] == [101.4, 100.6]
assert [fill.fee for fill in result.fills] == [1, 1]
assert round(result.cash_change, 8) == -5.2
```

Engine 模块具有独立身份。旧 Platform 分钟账户、绑定源码哈希的冲击模型及固定旧环境，
在消费者迁移关卡前保持原样。数据或模型哈希不能授权把检查点恢复到另一财务所有者。
来源见[第三方声明](../third-party-notices.zh-CN.md)。

## 执行独立目标场景

[场景执行器](../product/scenarios.zh-CN.md)通过固定分钟配置消费外部可执行目标产物。交易许可、涨跌停、日历和事件带必须明确；生成路径不会自动补齐这些语义。固定与重算模式必须显式选择。收盘时点可用性是合成约定，base/transformation 哈希是声明谱系，重复路径不是独立观测。
