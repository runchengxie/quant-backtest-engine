# 期间诊断回放 {#_1}

[English](diagnostic-close-replay.md)

`run_period_replay` 在显式期间边界上计算已选定持仓，返回原 `PositionBacktestResult(net_returns, gross_returns, periods, summary)`。它不生成每日现金、股数、订单、成交或现金扣费证据。

    from quant_backtest_core.daily.period_replay import run_period_replay
    result = run_period_replay(
        positions=positions, pricing=pricing, periods=periods,
        calendar=calendar, config={"transaction_cost_bps": 10.0},
    )

实现前计划遗漏了 `periods` 参数，并误用了每日净值结果类型；此处纠正。来源是固定版本的 `_position_backtest_config/_position_backtest_engine` 及纯归一化/权重漂移函数。原净收益、毛收益和期间表的列、重复结束日期、数据类型、跳过期间元数据及运算均保留。期间表显式包含 rebalance_date、entry_date、exit_date；新入口拒绝缺失的调用方交易日覆盖，不查询日历或推断期间边界。

直接 `daily.position_backtest.run_position_backtest` 签名保持，包括可选日内 VWAP 诊断。输入归一化、退出策略及末期专用估值价格保留原语义。选股、策略权重模型和发布留在 Platform。Core 不生成年化、夏普、回撤、H1/H2 等研究统计；`summary["stats"]` 只保留平均换手、成本和敞口等财务字段。Task 15 使用同一个结果类重建旧研究字典。

未变更的液态基准毛收益为 `0.05`、净收益为 `0.049`，初始成本为 10 基点；它明确不提供订单生命周期、部分成交或每日账本。

## 保留的下一收盘价流程 {#_2}

Platform 独立的 `target_close_replay.replay_close_targets` 留在原项目：形成后的首个收盘价、可分割复权单位、调用方选择的默认 25 基点、交易阻断时整篮子延期，以及无券商成交/分红账本。此次迁移不替代它。[固定版本原文](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/guides/diagnostic-close-replay.md) 保留完整时序和敞口契约。

## 敞口变化 {#_3}

敞口决策、波动率目标和目标构造仍由 Platform 提供；Core 不推断现金利息或未来敞口。

## 审计辅助 {#_4}

持仓损益、回撤区间和匹配波动率研究诊断留在原流程。历史可见性、分红复权、退市和可执行性均须独立证据。


## 纯期间与分腿财务闭包（Task 15P）

提供方 C（PR #24）合并后的源闭包检查发现，部分纯财务 helper 仍留在 Platform。
Task 15P 在消费方 Task 15 恢复前迁移这些原始实现；它不改写 PR #24 的历史证据，
也不引入新的财务模型。

- `daily.leg_financial._build_backtest_leg_result` 接收显式持仓、目标与实际权重、
  入场和退出价格、前序状态、日期及费用和滑点模型，保留多空诊断收益符号、
  全部换手层次、费用方法参数、目标与实际名称、敞口及现金字段。
  `_build_leg_turnover_report` 保留前序已记录目标与实际持仓的区别；
  `_next_position_state` 保留初始现金和已记录目标标志。
- `daily.pricing.slippage_pricing_row` 仅查询调用方提供的参与率成交额表；
  缺列或缺日期时保留原有查表异常。
- `daily.period_turnover.period_result_from_leg/period_result_from_legs` 返回 Core
  所有的 `daily.types.BacktestPeriodResult`，保留原字段顺序、默认值，并使用
  同一个 Core `CostBreakdown` 类。费用和滑点各汇总一次，未知可选诊断仍为未知，
  名称按原规则合并，较晚的分腿退出决定期间退出日期。
- `daily.trade_accounting.compute_trade_summary/drift_previous_weights` 及其
  `_compute_trade_summary/_drift_previous_weights` 别名保留独立的旧 API：
  空目标返回零换手；前序为 `None` 或空组合时，完整归一化目标计为初始换手。
  这不同于 `daily._period_helpers` 的未初始化账户、显式现金区分和敞口保留语义。
  既有 `TradeCostConfig`、`TradeAccounting`、`drift_weights`、
  `compute_trade_accounting` 与 `compute_trade_accounting_frame` 不变。

筛选、排序、分组、目标权重构建、研究期间编排、广义指标、日历获取及
`period_turnover_fields` 研究投影继续由 Platform 所有。多空诊断分腿不为
`python.daily` 增加融券、保证金、成交记录或每日现金账本。每次运行只有一个
财务所有者，调用方不得再次扣除费用、滑点或描述性执行差额。

Core/SDK 保持 0.3.0，Rust 保持 0.2.0，原生扩展保持 0.1.0。Task 15P wheel 有
独立的不可变哈希和源版本；包版本本身不能识别此次闭包。消费方迁移须等待复核、
合并后的后续提交及其精确 VCS/wheel 固定标识，不涉及 PyPI 发布。Platform 兼容
别名须保留两个次版本周期，**且**直到所有已记录支持的消费方完成迁移。旧检查点
继续使用原有完整环境。

验收在真实固定的旧所有者环境，以及 Python 3.12/3.13 的普通 Core wheel 安装
环境执行合成显式调用，比较全部数据类字段和属性、Series 值及索引和 dtype、
签名、查表异常及费用调用参数。`project_tools/verify_period_leg_parity.py`
记录真实导入闭包；仅做静态源匹配不构成验收。

严格对比环境同时安装原有 PyArrow 26.0.1、pandas 3.0.6 与 NumPy 2.2.6。精简 daily/union 环境不安装 PyArrow；实际出现的 Arrow 到 Python 的 StringDtype 存储差异按 Series 索引逐项登记，只对这一明确存储差异转换后严格比较值和 dtype，不全局关闭 dtype 检查。
