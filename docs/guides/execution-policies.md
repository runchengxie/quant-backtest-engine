# Execution policies

[简体中文](execution-policies.zh-CN.md)

The minute simulator can release a parent order against a market-volume forecast
known before entry. Set `forecast_slice_weights` on `MinuteExecutionConfig`, or
use the same optional array in `minute-input.v1` settings. The array contains one
nonnegative integer per release slice and at least one positive weight. A
schedule with `release_slices=2` and weights `(1, 4)` releases one fifth at entry
and the remainder at the second release time. Omitting weights keeps the
original equal-slice behavior.

The engine rounds released quantities to lots, carries eligible unfilled
quantity within the window and applies the same latency, market capacity and
account constraints. The forecast weights apply to all parents in this config
and do not change after entry. The caller must bind the forecast's source and
availability. Realized volume from later in the session cannot be used to
construct the forecast. Bar VWAP remains the simulation's fill-price proxy.
The transport advertises the capability as `forecast_volume_slicing`. Historical
checkpoints remain tied to their original source revision and provider.

`quant_backtest_core.backtest.execution_policies` provides two deterministic
policy functions for research or account-based adapters. `checkpoint_sides`
identifies which sides are below a common threshold. `proportional_lots`
allocates an integer budget of interchangeable lots and uses input order to
break remainder ties. Apply cash, inventory and order permissions through the
existing financial owner. In particular, a lot budget cannot pool symbols with
different lot costs without an explicit reservation calculation.

`quant_backtest_core.microstructure.historical_projection` owns two arithmetic
diagnostics moved from Research. `TradeTape` projects participation off integer
trade prints using an exact cumulative volume and Decimal prices.
`sweep_depth` traverses one supplied snapshot in caller-specified order. Neither
helper advances market or account state. Research retains sample selection,
input admission, market feature estimation and comparisons across strategies.
