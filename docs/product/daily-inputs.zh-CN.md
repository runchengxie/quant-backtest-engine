# 日频执行输入

[English](daily-inputs.md)

Core 0.3.0 已实现独立日频图、daily-input.v1 校验和 python.daily 后端；发布仍需合并提交和精确 wheel 收据。安装 [daily] 及匹配 SDK。Task13 元数据、配置和摘要原样复用；不替代旧财务表。

## 显式原生请求

`DailyReplayRequest` 接收仓位和价格 DataFrame、`ExecutionCalendar`、
按调仓日期索引的 `ClockSet`、归属 Engine 的 `ExecutionSimConfig`、
模式（`ideal`、`capacity`、`adjusted`、`sequenced`）、价格口径、
公司行动及可选费用模型。`layout` 和 `decision_timing` 是必填的仅限关键字参数。
选择器不接受策略代码、提供方导入、可执行命令或序列化代码。

`DailyInputLayout` 显式列出 `price_col`、`mark_price_col`、
`tradable_col`、`buy_tradable_col`、`sell_tradable_col`、
`currency`、`quantity_unit`、`price_unit`，以及各流动性列的
`liquidity_units`。不用的选择器必须写为 `None`。
原有执行方使用同一价格表成交和估值，因此要求 `mark_price_col == price_col`；
尚不支持独立估值价格。人民币原始股数口径使用 `raw_share` 和
`CNY/raw_share`；复权口径使用 `adjusted_share` 和 `CNY/adjusted_share`。
流动性倍数为 1 时单位是 `CNY`，倍数为 1000 时是 `1000 CNY`。
未来 manifest 适配器必须核对币种和股数口径；原生元数据本身并不表示 manifest 已获准执行。

手数、T+1、流动性倍数及涨跌停、上市状态选择器仅保留在 `ExecutionSimConfig`。
类和解析器从 Platform 提交 `7a618bddd8fdeee5dbe37fe5b54a9698e0de5355`
原样迁移，依赖闭包只有 NumPy。缺失选中列或已启用规则所需输入时报错，不使用源默认值补齐。
证券和规则列由调用方提供。未纳入请求的旧模式参数保留在直接 API 中；
适配器必须拒绝无法表达的设置。稀疏目标不表示可以补造缺失交易日。

新请求的 `corporate_actions=()` 表示没有公司行动请求，
`legacy_corporate_actions()` 将其映射为旧接口的 `None`。
非空元组要求原始价格，并使用现有 `CorporateAction` 类及其原有归一化规则。
旧直接 API 保持原来的显式启用语义：原始价格下 `()` 启用行动证据，
复权价格下 `()` 仍报错。

## 时钟与调用方提供的交易日

每个严格的 `YYYY-MM-DD` 调仓日期必须有信息、决策和准入时钟。
要求信息时间 ≤ 决策时间 ≤ 准入时间；若有独立可用时间证据，还要求可用时间 ≤ 决策时间。
准入表示最早允许下单的时间，不是实际成交时间。其他时钟允许为空；
不对所有时钟施加统一全序。

`DailyDecisionTiming` 保存可空的信号、最早下单、执行窗口起止时间、
时序策略 ID 和交易日历引用。原生调用方已有独立时钟时，映射可以为空。
未来 ResearchClock 翻译器须完整保留字段和源约束：信息 ≤ 信号 ≤ 决策 ≤ 估值；
决策 ≤ 最早下单；窗口两端同时提供，且决策 ≤ 开始 ≤ 结束 ≤ 估值；
最早下单 ≤ 窗口结束。最早下单可以晚于窗口开始。
准入时间取两个已提供下界中的较晚者；只有一个时取该值；都没有时仍未知。
没有来源的可用时间保持未知。`utc_ns` 将有时区的时间精确转成 UTC 纳秒字符串，
不经过浮点秒数，超过 JavaScript 安全整数范围时仍保留纳秒精度。

日历日期是日期标签，不是时间瞬间。`ExecutionCalendar.from_dates`
校验严格有效日期并排序、去重，保留系统已安装的 IANA 时区标识原文。
语义摘要对 UTF-8 JSON 计算哈希：键依次为 `schema`、`timezone`、
`open_dates`；schema 为 `execution-calendar.v1`；`ensure_ascii=True`；
逗号和冒号紧凑分隔；无 BOM；末尾恰好一个 LF。构造器拒绝摘要不符。
`ArtifactRef.sha256` 独立标识原始文件的准确字节，不必等于语义摘要。

`execution_dates(calendar, start=..., end=...)` 包含两端。
`execution_date_map(signal_dates, shift_days, calendar)` 保留原有算术：
位移 ≤ 0 时选信号当日或之后第一个已提供交易日；正位移 N 时选严格晚于信号的第 N 个。
耗尽时新映射保留键并返回 `None`，旧封装省略这些键。
空日历不会访问提供方、生成工作日或调用未来日期回调。
日期元组和摘要不能证明真实市场日历的覆盖范围。未来可执行输入校验须对照已提供交易日
检查目标覆盖，不能凭空增加“日历覆盖权威”字段或承诺。

## 有支持证据的摘要与未知值

`summarize_execution(daily, fills, evidence=...)` 只返回
`daily_return`、`cumulative_return`、`turnover`、`total_fees` 和
`valuation_complete`。`DailySummaryEvidence` 不可变，
schema 为 `daily-summary-evidence.v1`，声明两张表分别可用或不可用，
估值完整性和外部资金流为零的标志与日表行序严格对齐。
可用表示覆盖声明运行区间的完整支持证据，包括显式空结果，而不是“有一个 DataFrame”。
这些是执行方或调用方的断言，不是 Engine 推断的来源认证。状态矛盾或行数不符时报错。

估值标志 True 表示该收益区间的期初、期末价格、现金、持仓和应收项完整。
零资金流标志 True 表示整个区间有完整的无外部注资证据，包括初始到首行的区间。
只有两个标志均为 True 且有限的执行方 `executed_return` 才能保留；
未知位置保留 `None`。累计收益按完整、有支持的有序序列执行原来的乘积减一，
不能删除未知行后复合。例如初始净值 100、两期末净值 110 和 99、
执行方收益 0.1 与 -0.1，累计收益为 -0.01。

估值完整但有存入资金时，`valuation_complete` 仍可为 True，收益则未知。
此接口不做资金流调整；精确 `CapitalObservation` 路径仍要求原有的完整初始、
有序资金流前后观测。显式支持的空日表返回 `()`、0.0、True；
不可用的空日表返回 `()`、None、False。

在支持具名的原始计算口径之前，换手率保持未知，不能把货币成交额当作比率。
费用只汇总单一、声明完整的实际成交表中的有限 `cost_commission`、
`cost_stamp_tax` 和 `cost_transfer_fee`。有这三列且显式支持的空成交表费用为零；
缺少状态、列或分项时为未知。不回退日表，不叠加日表与成交表，
不再加入 `transaction_cost`，也不二次扣除现金费用或冲击。

原有财务表、期间和换手率口径、算术仍由迁移的执行实现负责。
IC、alpha 和广泛研究统计仍归 Platform；Task 15 通过兼容封装从归属明确的财务结果
重建原有研究统计，包括 H1/H2 求和，并保留结果类身份。
此保守摘要不表示与原有研究统计字典等价。

## 产品协议和示例

完整合成请求见仓库 fixtures/product/daily.json，日历为 daily-calendar.json。输入必须恰好是 positions、pricing；corporate_actions 带必须显式存在。settings 包含 mode、config、layout、decision_clocks、decision_timing、fee_model，拒绝未知字段。配置十进制参数、权重、价格、流动性和费率使用十进制字符串；时钟是精确 UTC 纳秒字符串。

Python layout.liquidity_units 仍是映射；协议将其编码为 [{"column":"amount","unit":"CNY"}]，避免动态列名与金额键冲突。拒绝重复列、未知记录字段及单位不匹配。fee_model 仅接受 null、detailed 或 dated 固定结构，不接受模块路径。portfolio_value 必须等于初始现金。产品限定 CNY、Asia/Shanghai、显式原始/复权股数单位。

run_daily 不支持 policy、scenario、flow、risk 或 forecast 转换，也不支持检查点/恢复。ideal 不能带交易限制；capacity 支持流动性/参与率限制、通用或分买卖方向的交易许可、执行窗口及连续零成交中止，但在执行前拒绝 `enforce_price_limits`、`enforce_listing_status`、`enforce_t1`、非空 `round_lot`/`sell_round_lot`、公司行动及费用。capacity 要求 `unfilled_buy_action=keep_cash` 和 `unfilled_sell_action=keep_position`，拒绝其他策略；该模式没有股数/现金/费用账本；调整/顺序模式保留真实模拟股数和现金路径。按行估值完整性是保守充分条件：每个目标证券在所有账本日均有正的有限当前价格；缺失时摘要收益保持未知。

## 已安装合成样例

使用对应的普通 wheel 执行仓库中的合成样例：

```sh
quant-backtest capabilities python.daily
quant-backtest run-manifest fixtures/product/daily.json \
  --artifact-root fixtures/product --output-root "$DAILY_OUTPUT"
```
