# 逐日回放与账本

[English](sessions.md)

engine_request.v2 增加明确的交易日、人民币/美元账户和原始价格约束，
旧 v1 请求与结果契约保持不变。

```sh
cargo run --locked -- session-capabilities
cargo run --locked -- run fixtures/sessions.json
```

合成样例以 10 元买入 100 股，同日卖单因 T+1 被拒绝，下一交易日按 12 元卖出。
买卖各收 10 个基点费用。首日现金 8999、净值 10099，最终现金和净值 10197.8，
费用合计 2.2。所有结果来自真实上游执行。

## 时间和行情

调用方明确提供交易日序列、开盘时间、估值时间、报价和订单。
人民币交易日按 Asia/Shanghai 解释，美元按 UTC 解释，这属于本版本的模拟约定。
引擎不自行推断交易所、节假日或不同证券的交收规则。

报价带有买卖价、买卖量、是否可交易及涨跌停方向标记。
每个标的都必须在同一个日终估值时间有新报价，无交易日也不能缺少估值输入。
陈旧价格、重复报价、跨日边界不合法或复权价格会报错。
订单仅在信息时间之后的对应标的报价上提交，不使用等时或更早的报价。

## 明确配置的约束

- 只做多现金账户，买入检查真实资金和上游取整后的费用。
- 买入股数必须符合标的声明的整手单位。
- 不可交易时双向拒单，涨停标记阻止买入，跌停标记阻止卖出。
- 开启 T+1 时，只能卖出前一交易日已有的持仓。可卖额度按实际成交和撤销维护，
  未完成卖单预占额度，竞争订单不能重复使用同一批股份。
- 市价单采用立即成交或取消（IOC）。当次报价能成交多少就成交多少，剩余数量取消。下一日仍需交易时，调用方提交新订单。
- 报价数量交给上游共享流动性消耗机制处理，不自行伪造成交。

报价流动性不等于日成交量参与率。相同价格和相同数量的后续报价可能继续保留
此前消耗，显示数量变化时上游会重置。不能据此宣称已有 ADV 容量模型。
费用由调用方提供，不自动推断印花税、最低佣金或历史税率。
这些配置约束不代表完整 A 股合规仿真。

## 输出

engine_result.v2 保存币种、原始价格约定、估值时区和本次启用的 T+1 标志，
以及初始资金、最终资金净值、总费用、订单、成交、拒单原因、每日资金与每日持仓。
每日净值等于现金加持仓价值。未平仓持仓按估值时刻买卖报价中间价计算。
上游结束流程如果改变已完成的经济状态，任务会失败。

逐日账本不会自动成为 platform 的 execution_aware bundle，仍需要调用方补齐
研究时钟、生产者、来源记录和完整标准映射。旧 runtime v5 只接收 v1 快照结果，
v2 需要显式兼容的任务版本。

分红、送转股、零股权益与退市的缺口见[公司行为兼容记录](migration/corporate-action-conformance.zh-CN.md)。

## 库接口的逐日输入

`run_sessions_iter(config, sessions)` 接收 `SessionConfig` 和具有所有权的
`Iterator<Item = anyhow::Result<MarketSession>> + Send + 'static`。
配置包含 v2 请求中除 `sessions` 外的字段，拒绝未知字段。
惰性数据源可以直接构造配置；已有请求可以用 `SessionConfig::from(&request)`
复制请求头，再用 `request.sessions.into_iter().map(Ok)` 移交交易日。

调用会阻塞至完成。专用工作线程依次读取、校验、回放交易日并生成快照，
之后才读取下一项。该线程始终持有同一个 Nautilus 引擎直至释放。
空数据源、读取错误或后续交易日校验失败都会返回 `Err`，不返回成功的最终结果。
遇到首个错误就停止读取。数据源自身产生的外部副作用由调用方负责。

报价和报价准入规则仅保留当前交易日。每项必须包含完整交易日，
同一时间戳下所有标的的数据必须放在一起。
全局订单编号、累计订单元数据、最终订单、成交、每日账本以及上游账户、订单和持仓历史
仍会累积，数据源自身的缓冲也可能占用内存。因此总内存仍可能增长。
本接口不承诺总内存有固定上限、运行提速或状态恢复。
原有 CLI 和 Python v2 客户端继续接收完整请求。下文介绍独立的交互式传输入口。
引擎暂不支持金融状态快照导入。

## 交互式交易时段传输

`quant-backtest-engine session-stream` 从标准输入读取以 LF 换行结尾的 UTF-8 NDJSON，
每处理一帧就在标准输出写入并刷新一条 JSON 响应。诊断信息写入标准错误。
客户端发送一帧、收到响应后再发下一帧，发送 finish 后关闭标准输入，供引擎验证 EOF。
每个 session 帧必须包含完整交易时段，包括相同时间戳的全部报价、订单和最新估值报价。

输入均包含 `schema_version: "engine_session_stream.v1"`、`type` 和 `sequence`。
start 帧使用 `type: "start"`、序号 0，`config` 为现有 `SessionConfig`，即去掉
`sessions` 的 v2 请求。session 帧使用 `type: "session"`、序号 1 至 N，`session`
为 `MarketSession`。finish 帧使用 `type: "finish"`、序号 N+1，不含其他载荷。
至少需要一个交易时段。未知字段、重复字段、错误序号、重复 start、非法或截断行、
finish 后的其他帧均会导致失败。

响应使用 `engine_session_stream_result.v1`，并回传 `sequence`。ready 帧包含
`type: "ready"`、`header_sha256` 和 `max_frame_bytes: 67108864`。session 响应包含
`type: "session"`、`prefix_sha256` 和 `report`。报告字段包括从 0 开始的
`session_index`、`session_date`、`valuation_ts_ns`、`balance`（现有日结余额）、
`positions`（当日持仓），以及当前时段的 `orders`、`fills` 和 `rejections`。
收到 finished 前，这些报告均为暂定结果。finished 帧包含 `type: "finished"`、
`prefix_sha256` 和保持原有结构的 v2 `result`。

头部摘要为 start 帧原始 JSON 字节（不含 LF）的 SHA256。每个 session 和 finish
帧将摘要更新为 SHA256（前一摘要的原始 32 字节 + 当前帧原始 JSON 字节，不含 LF）。
空白字符会影响摘要。输入和输出单帧上限均为 67108864 字节，包含 LF。
最终结果超限时失败，不会输出部分成功帧。报价仅保留当前时段，上游历史和最终汇总
输出仍会增长。此传输不提供财务检查点或恢复保证。

库接口为 `run_sessions_iter_with_reports(config, sessions, callback)`。
回调接收拥有所有权的 `SessionReport`，返回 `anyhow::Result<()>`，在回放和快照完成后、
读取下一时段之前执行。数据源或回调出错会中止执行，不返回最终结果。
原有 `run_sessions_iter` 保持兼容。
