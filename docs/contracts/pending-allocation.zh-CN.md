# 待成交订单的纸面分配

[English](pending-allocation.md)

已在提供方 B 工作树实现，B 门合并前未发布。Core 当前源码为 0.2.0；合并发布和消费者切换仍是独立步骤。[原始文档](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/contracts/pending-allocation.md)。

`quant_backtest_core.planning.pending_allocation` 为未完成订单预留资源，再交由调用者提供的 `PendingOptimizer` 计算新增交易。完整请求和结果仍由调用者拥有。接口只用已送达持仓、剩余订单与已知资源，构造保守的单周期条件端点包络，示例均为合成数据。

## 目标与订单语义

h 为已送达持仓按给定原始价格除正净值后的权重，`current_weights` 必须等于 h。b 为不含待成交订单的基准目标，新增交易 delta = b - h。每笔旧订单的权重 p_j = 原始有符号剩余数量 × 原始价 / NAV，各自未知成交比例 f_j 独立处于 [0,1]。

```text
endpoint = b + sum_j(f_j * p_j)
NEW trades = b - h
```

不要再次从 b 扣待单，也不要把 b 当增量订单。`new_trade_weights` 是新增纸面权重，不含整数取整或订单准入。包络仅在新增交易全部成交时成立，不保证中途路径或新增订单部分成交；执行策略由调用者选择。它不撤单、不补造成交、不优化时序、不读取隐藏 actual 账户。

## 观测与时钟

`PendingAllocationState` 提供相同资产索引的 `delivered_quantities`、`raw_prices`、`quote_times`、`sell_capacity_quantities`、`new_fee_rates`，以及 `nav`、`cash_before_reserves`、`outstanding_orders`、`delivered_at`、`orders_as_of`、`complete_order_snapshot=True` 和非空 `assumptions`。

完整快照须含撤单中的订单及未报告成交。每个 `PendingOrder` 有 ID、标的、有符号整数剩余量、假定买入预留价格上限、剩余费用预算和观测时钟。未知标的、重复 ID、未来或无时区时钟、不完整快照、持仓不符及非有限值均拒绝。所有观测不晚于信息时间，`orders_as_of` 等于信息时间，信息时间不晚于决策时间。错误声明完整时无法自动发现漏单；没有自动报价时效阈值，新鲜度由调用者负责。

事件账户接入使用 `visible` 持仓、因果原始报价、按所给价格重估的可见 NAV 和 delivery-visible `pending`。隐藏成交在报告送达前不改变这些输入；不要传 actual、actual_nav、真值订单簿或未送达报告。本模块不依赖账户适配器，不产生第二个撮合器。

## 敞口包络

任意线性载荷 a 的独立成交增量为：

```text
L(a) = sum_j min(0, a[symbol_j] * p_j)
U(a) = sum_j max(0, a[symbol_j] * p_j)
```

端点区间 [lo, hi] 将 a @ b 约束为 [lo-L(a), hi-U(a)]，逐一用于因子、单资产和净敞口（a=1）。反向订单不相抵；同标的买卖各 0.1 的净增量为 [-0.1,0.1] 而非零，负载荷同样处理。`net_target` 仍约束基准净值权重，必填 `net_band` 约束端点区间；基准净值须在收紧区间内。独立成交使严格端点中性通常不可行，不能伪造中性解。

总敞口以 sum(abs(b)) + sum(abs(p_j)) 保守上界，因此基准总上限扣除旧待单总绝对权重。三角界可能拒绝可行抵消，不是精确稳健总敞口优化器，但能覆盖所有旧成交角点；因子和净值区间为线性精确极值。

## 现金、卖出和借券

`cash_before_reserves` 为扣限制现金、未结所得和已有空头抵押后、尚未扣旧订单预留的可用现金，可含调用者政策明确授权的信用。每笔旧单分别预留：

```text
old cash reserve = sum_j(max(quantity_j, 0) * max(reserve_price_j, raw_price_j)
                         + fee_budget_j)
remaining cash = cash_before_reserves - old cash reserve
new cash = NAV * sum_i((abs(delta_i) + delta_i) / 2
                       + new_fee_rate_i * abs(delta_i))
```

买卖均计费用，旧单和新单的卖出所得都不能资助买入。比例 `new_fee_rates` 独立于研究效用 trade_costs。新增买入现金按固定原始价；旧 reserve_price 是假定买入价格上限，至少预留原始价。这不防新增单逆向重定价；最低费和非线性成本需要另模型。调用者优化器实施现金约束，旧 Platform 稀疏 QP 用绝对交易辅助变量实现。回执直接按 delta 重算现金。不要传已扣预留的现金以免重复预留；无额外信用时账户的 `available_cash(info_time) + sum(pending_order["reserved_cash"])` 提供基础，预留价格假设仍需核对。

卖出能力是可卖已送达多头加确认的增量可借数量，尚未扣旧卖单。增量可借量排除已被空头耗用的部分：已空 10、总可借 13 时仅余 3。全额扣旧卖单，新负交易不能超余量。待买、新买和回补均不补回本次决策能力。模块不能建立借券权限或推断结算/T+1 资格。

## 调用与结果

```python
from quant_backtest_core.planning.pending_allocation import solve_pending_allocation

result = solve_pending_allocation(
    optimizer,  # 调用者提供 PendingOptimizer
    request,  # 原始完整请求，基线为已送达持仓
    observation,  # PendingAllocationState，无隐藏真值
    net_band=(-0.15, 0.15),
)
if result.status == "optimal":
    additional_paper_weights = result.new_trade_weights
    conditional_endpoint_net = result.endpoint_net_bounds
```

`pending_allocation_envelope` 只生成包络。成功时 `base_result` 保留实际结构化结果及其研究特有字段，换手基于已送达持仓；端点净区间、因子区间、总敞口上界和新现金分别列示。优化目标仍为基准目标风险/收益，不是旧单所有角点最坏经济结果。因子回执只含已约束因子。无效观测抛 `ValueError`；资源不足或不可能包络为 `infeasible`；求解和残差失败为 `numerical_failure`，均不释放目标或新交易。价格与 NAV 只在单期固定；不覆盖逆向价格、净值变化、新单部分路径、保证金变化、公司行动、融资、快照后召回或多周期适应。始终 `paper_only=True`、`executable=False`。

## 优化器归属

`PendingRequest` 仅暴露 `current_weights`、`lower_bounds`、`upper_bounds`、`expected_returns`、`factor_loadings`、`factor_bounds`、`gross_limit`、`net_target`、`information_time`、`decision_time`。Engine 校验这些执行字段、完整观察及返回端点的既有 `1e-7` 残差；不检查协方差、风险厌恶、期限、研究成本目标或因子估计。单独构造包络不等于完整研究请求验证。

`PendingOptimizer.validate(request)` 必须验证完整请求；`solve_pending_allocation` 在生成可能不可行的包络之前也先调用它，随后将同一请求对象原样传给 `solve_pending(request, *, envelope, cash_limit)`。cash_limit 为 `(available_cash / NAV, new_fee_rates.to_numpy(dtype=float))`。适配器实施收紧的资产、因子、总敞口界，并保留基准净值等式和完整验证。旧 Platform 适配器使用自身 `_validate`、dataclass `replace`、`_solve`；旧公开包络包装器也须先全量 `_validate` 再调 Engine 中立包络。这一消费者适配在提供方门之后的 Task 12 交付。Engine 不导入 OSQP 或有符号优化器。结果协议只要求 status、message、可选 weights；成功的 base_result 保留原对象而非重建通用结果。

协议字段只读，因此既有冻结请求和结果 dataclass 无需增加 setter 或复制字段即可满足结构契约。
