# 分期执行费率

语言：简体中文 · [English](dated-execution-fees.md)

Core 0.3.0 日频图已实现；发布仍以合并提交和精确 wheel 收据为准。选股、研究统计和报告发布留在 Platform。见[日频输入](product/daily-inputs.zh-CN.md)。


`DatedTradeFeeModel` 根据调用方提供的费率时段，为实际成交计算费用，并接入连续执行调整 NAV 账本。模型不内置市场费率、供应商数据、凭证或策略设置。未传入分期费率模型的现有调用继续沿用原交易成本行为。

## 公共接口

从 `quant_backtest_core.daily.execution` 导入分期费率接口：

```python
from quant_backtest_core.daily.execution import (
    DatedFeeSchedule,
    DatedTradeFeeModel,
    FeeQuoteContext,
    FeeSchedulePeriod,
)
```

每个 `FeeSchedulePeriod` 对一个明确的市场标识生效，日期范围包含 `start_date`，但不包含 `end_date`。调用方提供买入和卖出佣金率、最低佣金、卖出印花税率、过户费率，以及买卖两侧的价差率。费率使用基点。最低佣金使用成交金额相同的货币单位。

同一市场的费率时段不能重叠。交易日期缺少费率、日期匹配不唯一，或证券没有对应的市场映射时，模型会报错，不会回退到默认费率。费率配置对象及复制后的证券市场映射均不可变。

## 纯报价

报价不会修改模型或费率表：

```python
periods = (
    FeeSchedulePeriod(
        start_date="2030-01-01",
        end_date="2030-07-01",
        market="SYNTH-X",
        buy_commission_bps=2.0,
        sell_commission_bps=2.0,
        minimum_commission=5.0,
        sell_stamp_bps=10.0,
        transfer_bps=0.1,
        buy_spread_bps=0.0,
        sell_spread_bps=0.0,
    ),
    FeeSchedulePeriod(
        start_date="2030-07-01",
        end_date="2031-01-01",
        market="SYNTH-X",
        buy_commission_bps=2.0,
        sell_commission_bps=2.0,
        minimum_commission=5.0,
        sell_stamp_bps=5.0,
        transfer_bps=0.1,
        buy_spread_bps=0.0,
        sell_spread_bps=0.0,
    ),
)
model = DatedTradeFeeModel(
    schedule=DatedFeeSchedule(periods=periods),
    symbol_markets={"SYNTH-AAA": "SYNTH-X"},
)
quote = model.quote(
    FeeQuoteContext(
        trade_date="2030-07-01",
        side="sell",
        symbol="SYNTH-AAA",
        market="SYNTH-X",
        executed_notional=1_000.0,
        cumulative_group_notional=0.0,
    )
)
```

佣金按增量计算。设 `before` 为同一费用组此前的累计成交金额，`fill` 为本次成交金额，本次佣金等于 `before + fill` 对应的累计佣金，减去 `before` 已累计的佣金。累计金额为零时佣金也为零，因此零成交不会触发最低佣金。印花税、过户费和价差只按本次实际成交金额计算。

## 接入连续账本

将模型通过 `trade_fee_model` 传给 `simulate_execution_adjusted_nav`。执行前，模拟会检查所有目标证券是否都有市场映射，并检查每个实际使用的市场在所有模拟交易日是否都有且仅有一个有效费率时段。日期覆盖不完整时会直接报错。

费用累计属于单次模拟，不保存在可复用模型中。账本按原始订单和成交日分组累计佣金。这是明确采用的通用 broker 分组假设：同一订单跨多个交易日成交时，每个成交日分别计算最低佣金。可负担性检查使用纯报价预览。只有记录为实际成交后，才推进费用组累计金额。按整手调整后会再次检查含费用的现金余额，不可负担的成交不会扣款。

如果卖出费用超过当前现金与卖出所得之和，该笔卖出会延后。持仓、订单进度、费用累计和成交回执都不会因此改变，订单可在之后现金充足的交易日成交。

成交回执包含费用分项、`fee_market`、费率时段边界、`fee_order_id`、`fee_group_id`，以及费用组累计成交金额的前后值。运行摘要会序列化完整费率表和证券市场映射。

## 范围与限制

该模型已接入连续执行调整 NAV 路径，但这不代表完整模拟了真实执行、券商账单或股息。模型不会根据代码格式推断市场、填补费率日期缺口、合并互不相关的订单、模拟日内成交先后，也不提供按司法辖区设置的默认值。示例和测试使用合成费率。真实应用应提供经过外部核验的公开费率输入。
