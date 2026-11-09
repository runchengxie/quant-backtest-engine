# 产品契约

[English](contracts.md)

SDK 0.3.0 在 `quant_backtest_engine.product` 中新增不可变产品封装。
发行包仍是 `quant-backtest-engine-client`，仅依赖 Python 3.11+ 标准库。
这些结构描述请求和证据，不安装财务后端，也不扩展 Rust 的能力。
[原生客户端](../python-client.zh-CN.md) 保留既有 v1/v2 契约及
NautilusTrader 0.66.0 身份检查。

## 解析并保留精确值

```python
import json
from pathlib import Path
from quant_backtest_engine.product import loads_manifest, manifest_to_json

# 仓库中的合成样例；使用时一并复制其日历文件。
manifest = loads_manifest(Path("fixtures/product/rust-session.json").read_text())
wire = manifest_to_json(manifest)
assert wire["clocks"]["available_ns"] == "1760000000000000001"
assert wire["clocks"]["decision_ns"] == "1760000000000000002"
print(json.dumps(wire, sort_keys=True))
```

`parse_manifest(mapping)` 和 `parse_result(mapping)` 校验已解码对象；
`loads_manifest(text)` 和 `loads_result(text)` 还会拒绝任意层级的重复 JSON 键。
如果先前的解码已经丢弃了重复键，映射本身无法恢复这些信息。
DTO 的未知字段、缺失字段（包括应显式写出的可空字段）、非有限数值、
无效枚举值和重复命名项均被拒绝。直接构造 DTO 也应用相同的值校验。
`manifest_to_json` 和 `result_to_json` 返回全新的可变字典与列表。

DTO 使用冻结 dataclass。JSON 子树递归复制为只读映射和元组，
修改原始输入或导出对象都不会改变已保存的快照。
`JsonValue` 表示传输层的标量、列表和字典；
`FrozenJsonValue` 表示不可变标量、元组和映射。

## 清单结构

下表字段在传输层均须出现；可空值写作 JSON `null`。
schema 必须为 `backtest-product.v1`。
Python 中的命名二元组序列在 JSON 中编码为对象：
`model_versions`、`inputs`、`units`、`tapes` 以及提供方的
`dependencies`，不编码为二元组数组。

| 字段 | 传输值 |
| --- | --- |
| `backend_id`、`input_schema` | 显式后端注册键和输入配置版本 |
| `required_capabilities` | 不重复的能力名称数组 |
| `model_versions` | 模型名称到版本的映射 |
| `inputs`、`inline_inputs` | 命名文件引用及命名内联 JSON 输入，名称不可重叠 |
| `currency`、`share_basis` | 三位大写货币代码；`raw` 或 `adjusted` |
| `calendar`、`timezone` | 日历文件引用；本机已安装的 IANA 时区 |
| `units` | 字段或维度到明确单位的映射 |
| `clocks` | 下文的七字段时钟对象 |
| `initial_account`、`settings` | 由输入配置定义的 JSON 对象 |
| `tapes` | 命名文件引用或内联数组；空数组属于显式输入 |
| `policy` | `{id, version, state_schema, config}` 或 null |
| `forecast`、`risk` | 文件引用或 null |
| `scenario` | 情景身份或 null |
| `output_uri` | 稍后由可信执行上下文解析的输出位置 |

文件引用为 `{uri, sha256, media_type}`，摘要是文件精确字节的 SHA256 小写字符串。
解析过程不读取文件或获取 URL。合成样例附带 `synthetic-calendar.json`
及其真实摘要。执行器必须在可信文件根目录内解析路径并核对字节。

策略 ID 是固定的小写注册键，仅含字母、数字、连字符或下划线；
`os.system`、`os:system` 等导入路径会被拒绝。
后端键还允许以点分隔的片段。这里的键不触发任何导入或执行，
后端注册表必须显式解析它们。请求中没有可执行命令或序列化代码字段。

情景结构为 `{id, family, seed, base_input_sha256, transformation_sha256,
forecast_mode}`。seed 是整数，不接受布尔值；摘要标识所用输入和变换；
forecast_mode 为 `fixed` 或 `recomputed`。
每个情景须由其财务所有者维护独立账户和状态。

## 时钟与单位

`ClockSet` 包含 `available_ns`、`information_ns`、`decision_ns`、
`entry_ns`、`effective_ns`、`report_ns`、`valuation_ns`。
每项为规范整数形式的 UTC 纳秒字符串；仅在语义上不可用时填 null。
可以表示纪元之前的负时间戳。不接受 JSON 数字时钟、小数或指数形式、
空格和前导零。`"1760000000000000001"` 与
`"1760000000000000002"` 始终保持不同。

通用时钟对象不规定全局先后关系。`rust-session.v1` 对可用的时钟对
校验 information ≤ decision ≤ entry，以及 available ≤ decision；
null 只省略对应的不可用关系。effective、report、valuation 可能属于
其他事件，不与前四项强行排序。逐日开盘 ≤ 估值是另一条独立关系。
订单信息时间不必早于当天开盘；它能否用于后续报价，仍由原生引擎判断。

金额采用有限十进制字符串：`"0.22"` 原样保留；经济字段中的
`0.22`、`"NaN"` 和指数形式会被拒绝。该输入配置的数量和基点也用
十进制字符串。通用经济字段名见 `validation.DECIMAL_FIELDS`；
其他 JSON 元数据可以包含整数或有限浮点数。后端行结构必须明确声明额外
经济字段，新增元数据名称本身不构成财务语义。
例如 `cash: CNY` 是显式单位声明，会与所选提供方声明的单位比较。
货币、股份口径、日历和时区各自独立表达。

原生 v1/v2 整数时钟不变。[可选适配器](backends.zh-CN.md) 直接把纳秒字符串转换为 Python
整数，不能经由浮点数或 JavaScript 数字，并须校验转换后的原生请求。

## rust-session.v1 输入配置

SDK 校验以下完整结构，但不因此声称已安装可执行适配器。
样例对应 `fixtures/sessions.json`，只将时钟精确转换为字符串。

| 位置 | 必需键及值 |
| --- | --- |
| `inputs` 与 `inline_inputs` 合集 | 恰好一个 `instruments` 输入，可用文件引用或内联数组 |
| 每项 instrument | `symbol` 字符串；`price_precision` 为 0–4 整数；`buy_lot` 为 1–1,000,000 整数 |
| `initial_account` | 十进制字符串 `cash` |
| `settings` | 十进制字符串 `fee_bps`；布尔值 `enforce_t1` |
| `tapes` | 恰好 `sessions` 一项，值为文件引用或数组 |
| 每个 session | ISO 日期 `session_date`；字符串时钟 `open_ts_ns`、`valuation_ts_ns`；数组 `quotes`、`orders` |
| 每个 quote | `symbol`；字符串时钟 `ts_ns`；十进制字符串 `bid`、`ask`、`bid_size`、`ask_size`；布尔值 `tradable`、`limit_up`、`limit_down` |
| 每个 order | `id`、`symbol`；字符串时钟 `information_ts_ns`；buy/sell 枚举 `side`；十进制字符串 `quantity` |

以上配置对象的所有键均须出现，多余键被拒绝。instrument 的 symbol 不得重复。
显式 `"sessions": []` 是合法结构；缺少 sessions 则被拒绝。
空 sessions 能否实际运行，仍由原生引擎或后端决定。

对于文件输入和 tape，SDK 解析仅检查引用结构及必需名称。
适配器须在核对哈希并读取文件后，将内容替入并再次调用
`validate_rust_session`，然后执行原生语义校验。
解析 URI 并不代表文件内容已通过校验。

未知输入 schema 可以作为通用 DTO 表示，但没有配置校验或执行许可。
`require_capabilities(manifest, descriptor)` 拒绝未注册的 schema、
后端不匹配、不支持的输入或结果 schema、缺失能力及不支持的单位。
它不汇总其他后端的能力，也不会回退到 Python。
描述符包含 `identity, input_schemas, result_schemas, checkpoint_schemas,
capabilities, units, restrictions`；restrictions 是声明性说明，由后端落实。

## 结果与经济证据

`ProductResult` 的 schema 为 `backtest-product-result.v1`，必需字段是
`status, manifest_sha256, provider, tables, summary, raw_result, normalization,
failure, scenario`。status 为 completed、failed 或 partial。
completed 的 failure 必须为 null；failed/partial 必须携带失败信息。
summary 是 JSON 对象；raw_result 为文件引用或 null；scenario 为情景身份或
null。表名不可重复。

每张 `EvidenceTable` 的结构为 `{name, status, rows, reason}`。
available 的 rows 是 JSON 对象数组，reason 为 null；
空数组表示支持该表，但没有观察到记录。
unavailable 必须没有行，并给出非空原因，例如：

```json
{"name": "rights", "status": "unavailable", "rows": [], "reason": "not reported by this provider"}
```

不可用不等于余额为零、受支持的空账本，也不是推算出的成交。
注册表列出证据类别，不代表每个提供方都具备这些能力：

| 表名 | 证据类别 |
| --- | --- |
| intents | 请求的操作 |
| admissions | 请求的接受或拒绝 |
| cancellations | 撤单事件 |
| fills | 实际成交 |
| fees | 现金收费 |
| cash | 现金变动与余额 |
| positions | 持仓观察 |
| reservations | 预留资金或数量 |
| reports | 提供方报告 |
| rights | 公司行动权益 |
| receivables | 已确认但尚未收到的款项 |
| valuations | 估值观察 |
| capital_flows | 存取款，与盈亏分开 |
| daily | 逐日汇总 |

行采用 JSON 对象，注册表不规定统一的账本列集合。
行字段和会计含义由所选提供方及归一化源 schema 决定，
不得用虚构的零值填补不支持的字段。
成交价格中已计入的冲击和现金费用各自只计一次；
描述性的基准或机会成本不是额外扣款。

`NormalizationReceipt` 包含 schema `backtest-normalization.v1` 及
`adapter_version, source_schema, source_sha256, unavailable_fields`；
source_sha256 标识被归一化的源数据精确字节。
`FailureInfo` 包含 `code, message, stage, last_successful_cursor`，
游标为非负整数或 null。此封装不实现检查点恢复，也不允许向已失效的财务
会话再次索取检查点。

## 提供方身份与职责

`ProviderIdentity` 包含 `backend_id, distribution, version, source_revision,
source_sha256, dependencies, artifact_sha256`。
未知 Git 来源保留为 null。wheel 或可执行文件的摘要放在 artifact_sha256，
不能写入 source_revision，也不能冒充源代码摘要。
至少需要源代码闭包摘要或可执行文件/wheel 摘要之一。
已知 Git 版本用 40 位小写完整提交号；解析只检查格式，不证明仓库来源。
后续 Runtime v9 还需更严格的提供方及依赖闭包身份。

| 所有者 | 本次 SDK 新增内容中的职责 |
| --- | --- |
| `quant_backtest_engine.product` | 不可变 DTO、严格编解码、输入配置校验和能力比较 |
| 既有 `EngineClient` | 固定摘要的原生进程通信和不变的原生证据校验 |
| 显式财务后端 | 执行、记账、已加载文件校验和后端专属语义 |
| 消费方或后续执行器 | 可信文件根目录、持久化及已注册策略/后端选择 |

[归属注册表](../migration/reusable-ownership.json) 在记录已审查的源提交前，
仍将这项新增标为 planned，其他迁移项也保持 planned。
SDK 不新增 core、Platform 或 Runtime 导入，不新增撮合引擎或额外现金账本。


## 分钟输入配置

SDK 不依赖 pandas 即可校验 `minute-input.v1`。精确十进制与字符串时钟、显式输入带和固定策略注册表见[恢复与完整字段语义](recovery.zh-CN.md)。
