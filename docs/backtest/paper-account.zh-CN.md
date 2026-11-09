# 有符号纸面账户

[English](paper-account.md)

已在提供方 B 工作树实现，须等 B 门合并后才发布。迁移阶段 Core 仍为 0.1.0。[原始固定版本文档](https://github.com/runchengxie/quant-platform/blob/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355/docs/backtest/paper-account.md)。

`quant_backtest_core.backtest.paper_account.project_paper_account` 从期初 `PaperState` 出发，按显式费用和调用者提供的期末成交更新账户，再按原始价格估值。返回的 `state` 可供下一步记账，`weights` 可供下一次组合决策；它不生成成交，不认证可执行价格，也不推断券商条款。

所有时钟必须为带时区的 `pandas.Timestamp`。每笔成交的 `timestamp` 必须等于本次 `as_of`，同一时点按输入顺序处理；区间内成交须拆成独立步骤。价格、年化小数借券费率、假定可借数量及融资利率以 `Observed(value, available_at)` 提供；`max_age` 必须为显式非负 `Timedelta`。费率在期初已知，价格和可借数量在期末已知。缺失、未来、过期、非有限或非正价格均拒绝；零持仓无需价格。期初与新开空头即使零时长也须提供借券费率和可借数量。零费率只能是显式假设。

现金扣除有符号成交数量乘价格、非负成交费、借券费和融资费，再加有符号股息。正数量买入，负数量卖出。`dividends` 是期初持仓每股非负期末权益，多头收款、空头付款；权益时点或持仓变化不符时应拆分区间。不要把现金股息重复加到已含股息再投资的价格上。

费用按期初余额、期初标价和实际日历时间计提，包含不足一天的部分，年基数为 365。借券费按期初空头市值计算。融资口径须显式选定：`cash` 对负现金绝对值计费；`unrestricted_cash` 对假定空头准备金超过期初现金的部分计费，准备金为期初空头市值乘 `HouseMargin.short_proceeds_fraction`。后者可在现金为正时产生融资费。例如净值 100、多空市值各 350、现金 100、限制比例 1，融资本金为 250；融资和借券年率均为 36.5%，两天费用分别为 0.5 和 0.7，价格不变时净值为 98.8。这是模型假设，并非历史账户证据。

`restricted_proceeds` 是期末空头准备金诊断。卖空所得已计入现金，不再从净值重复扣除；净值始终是现金加有符号持仓市值。保证金为多头市值乘 `long_haircut` 加空头市值乘 `short_haircut`，余额为净值减要求。三项券商假设均由调用者显式提供。违约只报告、不强平。新开或增加空头不能超过假定可借上限；召回后可以回补，剩余超额列入 `borrow_breaches`。不推断真实借券或历史券商保证金。

结果列出 `borrow_cost`、`financing_cost`、`fill_fees`、有符号 `dividend_cash`、`elapsed_days`、融资本金和口径。杠杆与权重只在净值为正时计算；净值非正时 `insolvent=True`，权重和杠杆为 `None`，持仓仍保留。任何余额、费用、敞口或诊断溢出均拒绝。始终 `paper_only=True`、`executable=False`，状态和权重是不可变副本。示例仅为合成数据，策略和私有研究资料仍归研究项目。

## 完整执行恢复

`quant_backtest_core.backtest.checkpoints.ExecutionState` 将账户与 `LinearImpact`、输入游标、按键随机种子、策略状态和物理成交去重组合。检查点包含延迟报告与预留，不可仅凭冲击状态恢复账户。恢复要求配置与来源、输入绑定完全一致，详见[事件契约](../contracts/paper-account-events.zh-CN.md)。[外部对账](capital-and-reconciliation.zh-CN.md)比较调用者证据；[预留](../contracts/pending-allocation.zh-CN.md)只用已送达持仓。

## 迁移后的检查点身份

Engine 账户检查点采用整数 schema **2**，组合检查点采用 **execution-state.v2**。原 Platform schema 1 / execution-state.v1 原样恢复会被拒绝；旧检查点须保留完整固定的 Platform/Runtime/Go 环境，不提供转换器。仅版本身份及由此产生的摘要改变，财务状态和算法保持原样。

`source_binding`、`input_binding` 是调用者声明的字符串，与完整配置、内容摘要一同核验。底层帮助函数不测量已加载代码，也不认证来源；实际源码和 wheel 哈希由安装凭据及产品级提供方绑定记录。重复旧字符串不能让旧格式通过。内容篡改或配置、来源、输入绑定变化均拒绝恢复。
