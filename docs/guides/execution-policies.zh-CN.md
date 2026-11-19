# 下单规则

[English](execution-policies.md)

分钟回测可以按下单前预测的成交量分批释放订单。在
`MinuteExecutionConfig` 里加上 `forecast_slice_weights`，也可以把同名数组
传给 `minute-input.v1`。每批对应一个非负整数，至少有一批大于零。比如分两批，
权重为 `(1, 4)`，第一批释放五分之一，第二批释放剩余量。省略权重时仍按原来的
均匀切单规则执行。

引擎按整手计算当时能下多少。已释放但没做完的部分可在窗口内继续下单，同时受
延迟、成交容量和账户限制。这组预测权重对同一配置里的所有母单生效，入场后不变。
使用方负责记录预测来源和实际可用时点。下单时只用当时能看到的数据。分钟报价的
成交价仍以事后计算的分钟 VWAP 估算。传输能力名为 `forecast_volume_slicing`。
历史检查点仍由原始代码版本和提供方复现。

`quant_backtest_core.backtest.execution_policies` 提供两个确定性函数。
`checkpoint_sides` 查买卖哪一侧还没达到门槛。`proportional_lots` 按需求比例
分配同单位的整手额度，余数相同按输入顺序处理。现金、库存和交易权限继续交给
账户核算器。每手成本不同的股票需要先算各自的资金预留。

`quant_backtest_core.microstructure.historical_projection` 接收从 Research
迁出的两项计算。`TradeTape` 按逐笔成交量和参与率估算成交。`sweep_depth`
按调用者给出的顺序扫描一份盘口。两项计算都只返回估算，不推进委托或账户状态。
样本选择、数据准入、成交量预测及路线比较仍由 Research 负责。
