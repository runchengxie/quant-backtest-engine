# 独立场景执行

[English](scenarios.md)

Core 0.2.0 可将受信任的本地回调输出转为 `python.minute` 实际使用的目标仓位。
请显式安装 `[scenario]`。B 阶段源码与 wheel 仍须完成整体审查和合并后，消费者才能切换；
版本号本身不代表已合并的发布身份。

```sh
python -I -B examples/product/scenarios.py --output-root "$DATA_ROOT/scenario-example"
```

输出目录必须尚不存在。示例依次执行 A、不支持的中间案例、B 和固定目标 B 对照。
每个账户独立持有现金 `1000`，原始目标均为 `0`。早期合成收盘价 `9`、`11` 使外部回调
分别返回目标 `0`、`1`。决策标记价与后续成交价均为 `10`：B 买入 `100` 股，现金归零；
A 与固定目标 B 不买入。中间案例在调用财务所有者前失败，后续 B 仍执行。
09:33 的行情区间从 09:32:30 开始，严格晚于 09:31 入场加一分钟延迟。
成交量 `1000`、参与率 `1`、整手大小 `1`，交易许可、涨跌停和日历均明确，费用、税和冲击为零。
这是可手算的合成检查，不是市场证据。

## API 与能力边界

```python
from quant_backtest_core.scenarios import (
    ScenarioCase, PredictionArtifacts, PredictionProvider, ScenarioAttempt, run_scenarios,
)
# ScenarioCase(identity: ScenarioIdentity, manifest: ProductManifest)
# provider.recompute(case, inputs) -> PredictionArtifacts
# PredictionArtifacts(forecast, risk, policy, provider_id, provider_version,
#                     available_ns, input_sha256)
# run_scenarios(cases, *, context, prediction_provider=None) -> tuple[ScenarioAttempt, ...]
# ScenarioAttempt(identity, status, result, failure, *, composition=None)
```

固定组合注册表仅支持 `python.minute` 与 `scenario-minute-targets.v1`。
`risk` 必须为 null。回调返回 null policy 时保留请求策略；非空策略必须精确等于
`{"id":"target-weights","version":"v1","state_schema":"target-weights-state.v1","config":{}}`。
请求不能加载任意导入路径、命令、估计器、风险模型或优化器。受影响的特征、预测和决策由回调负责，
Engine 只校验并投影可直接执行的目标行，交给原有财务所有者。原始 minute 与 Rust 入口仍拒绝
scenario/forecast/risk 转换。

`forecast_mode` 必须显式为 `recomputed` 或 `fixed`；family 仅接受
`external-market-path`、`execution-perturbation`，它们是调用方的解释，不是经验证的转换算法。
重算模式必须提供受信任回调。固定模式保留请求目标，forecast 可为 null，也可为目标行与请求
精确一致的同类型产物；固定模式不会调用回调。不支持的原始或返回产物、策略、风险和后端均失败。

同一个回调对象服务整个序列，应按案例保持确定性，或自行按案例标识隔离内部状态；它不是独立策略工厂。
每次原始运行创建全新的账户、策略桥、目标策略和配置的冲击实例。顺序不应形成财务状态依赖。
seed 是谱系标识，不会让确定性的 minute 所有者自动随机化。

## 精确输入域

JSON 规范哈希采用 SHA256：UTF-8、键排序、紧凑 `,`/`:` 分隔、不转义 Unicode、仅有限数字，
末尾恰好一个 LF。ArtifactRef 哈希覆盖原文件的精确字节，包括空白。重复键和非有限常量均被拒绝。
金额与 UTC 纳秒时钟始终以字符串传输，时钟不经过浮点转换。

回调 `inputs` 精确包含以下字段：

| 字段 | 含义 |
| --- | --- |
| `schema` | `scenario-inputs.v1` |
| `scenario` | 精确 SDK ScenarioIdentity 对象 |
| `prediction_request_sha256` | `resolved_manifest` 的规范哈希 |
| `resolved_manifest` | 下述严格 SDK 预测输入视图 |
| `calendar` | 解析后的精确合成日历 JSON |
| `sources` | 日历、输入文件和事件带文件的来源描述 |

每条来源描述精确包含 `pointer`、`reference`、`snapshot`、`sha256`。
指针指向原 manifest 字段 `/calendar`、`/inputs/<name>` 或 `/tapes/<name>`。
两种 ref 均为 `{uri,sha256,media_type}`；快照 URI 为案例来源目录内的
`artifacts/<sha256>.json`，哈希覆盖保留的原始字节。内联值由整个 envelope 哈希绑定。

预测视图补入案例标识，将输入文件和事件带解析为内联 JSON，保留其他声明，并把日历引用改为
内容字节相同的快照引用。只将 `forecast` 置 null，避免输出证据参与自己的输入哈希。
forecast 来源描述以及间接包含该引用的完整请求哈希也不进入此哈希域。
`risk` 本来就必须为 null；scenario、policy、账户、行情、事件带、设置、单位、时钟和必需能力仍被绑定。

传给回调的独立 ScenarioCase，其 manifest 与 `inputs.resolved_manifest` 完全相同。
收据另行保留完整原请求、补入标识后的请求及各自哈希，包括原 forecast 引用与快照字节。
只改变 forecast 的 URI/哈希会改变完整请求身份，不改变预测视图哈希；非 forecast 输入变化会改变输入哈希。
因此可先按视图制作固定目标产物，再附上引用，而无需自引用哈希。回调输入为独立副本，调用后再次比较；
发现输入修改或产物字节变化时，在财务执行前失败。

## 类型化目标产物

forecast 必须引用 `application/json`，精确字节大小最多 16 MiB，对象精确包含以下字段：

| 字段 | 合同 |
| --- | --- |
| `schema` | `scenario-minute-targets.v1` |
| `scenario` | 精确案例标识 |
| `provider_id`、`provider_version` | 非空字符串，与 PredictionArtifacts 相同 |
| `available_ns` | 规范整数字符串，与返回值和请求可用时钟相同 |
| `input_sha256` | 回调调用前实际 envelope 哈希，与返回值相同 |
| `targets` | 非空严格目标行列表 |
| `source_records` | 非空声明来源列表 |
| `consumed_inputs` | 非空消费来源指针列表 |

目标行必须包含 `information_time`、`decision_time`、`entry_time`、`symbol`、`weight`，
只允许额外的可选 `order_type`。权重为 SDK 十进制字符串，时钟为规范 UTC 纳秒整数字符串。
初版限制为一个可用性切点和一组明确的信息/决策/入场时钟，所有目标行必须匹配 manifest 时钟。
要求 `information <= availability <= decision <= entry`；原有所有者更严格的时序与行情规则继续适用。

来源记录精确为 `{id,kind,sha256}`：id 唯一，kind 为 `implementation`、`dependency` 或 `artifact`，
SHA256 使用小写十六进制。这些是调用方声明，不证明依赖或来源真实性。
可检查时，另行计算并复制回调类文件的实际字节；类文件哈希不证明隐藏依赖、外部状态或实例状态。

消费记录精确为 `{pointer,sha256,available_ns}`。指针只允许完整行情行
`/resolved_manifest/inline_inputs/bars/<规范索引>`，哈希覆盖该行的规范 JSON。
重复、无法解析、不规范或哈希不同的指针失败。`available_ns` 必须等于所给行情的 `time`，
且不晚于返回的可用时钟。这明确采用 `synthetic-bar-close-convention.v1`：只验证所给事件时间相等，
数据到达/可用性仍是合成约定，**不是独立观测到的真实数据可用时间**。
任意字段指针及真实到达时间载体不属于 v1。输入还包含未来执行行情；受信任回调不是沙箱，
这些证据不能证明没有隐藏前视、外部状态或遗漏依赖。

## 投影、文件和收据

所有案例及来源文件先做快照，再开始调用回调。每个案例独占 output_root 下的
`case-<案例规范哈希>/`。来源根与输出根必须分离，路径不能含符号链接别名。
重复案例 ID、已有目录、不规范路径与越界访问均失败且不覆盖。
每个目录包含 `sources/`、`execution/` 和 `receipt.json`。来源 ref 相对 `sources/`，
所有者结果 ref 仍相对 `execution/`，`ScenarioAttempt.composition` 相对最外层输出根。
复现运行应使用新的外层输出根。

投影删除旧的文件/内联目标绑定，安装精确校验后的目标行。其他输入及事件带只做等值解析，
能力、账户、设置、单位和时钟全部保留；scenario/forecast/risk 移至组合证据后，在原始请求中置 null。
不新增算术、舍入、优化器或财务账本。原 ProductResult 对象和两份所有者输出文件保持原样：
哈希对应实际执行 manifest，原始 scenario 为 null，原生结果哈希不变；不发明 `run_sha256` 字段。

严格的 `scenario-composition.v1` 收据精确包含下表字段；尚未到达的阶段对应值为 null：

| 字段 | 证据 |
| --- | --- |
| `schema`、`identity`、`status`、`stage` | 模式、案例、completed/failed 和最终阶段 |
| `original_manifest`、`original_manifest_sha256` | 原请求与规范身份 |
| `requested_manifest`、`requested_manifest_sha256` | 补入案例身份的请求与哈希 |
| `prediction_request_manifest`、`prediction_request_sha256` | 回调案例视图与哈希 |
| `input_view_projection` | `{removed:["forecast"],reason}`，解释自引用排除 |
| `source_artifacts` | 全部来源描述，包含原有 `/forecast` |
| `callback_inputs`、`callback_input_sha256` | 调用前实际 envelope 与规范哈希 |
| `prediction` | 原样 PredictionArtifacts 字段或 null |
| `target_artifact` | `{reference,snapshot,payload,sha256,source_records_status,consumed_inputs_status,availability_status,validation_status}` |
| `callback_source` | `{status,type,sha256}`；可检查文件另含 snapshot ref，否则为 unavailable |
| `lineage` | `{status,base_input_sha256,transformation_sha256,reason}`；没有载体时始终为 declared |
| `projection` | 每个变动字段的 `{field,requested,executed}` 列表 |
| `adapter` | `{id,version,source_sha256,source_files}`；实际 contracts/runner 文件哈希映射及其规范哈希 |
| `executed_manifest`、`executed_manifest_sha256` | 实际原始所有者请求与哈希 |
| `owner_call` | `{callable,manifest_sha256,artifact_root,output_root}`，唯一财务调用 |
| `owner_result` | 未改动的 SDK ProductResult JSON，含安装提供方/源码身份 |
| `failure` | 原 SDK FailureInfo `{code,message,stage,last_successful_cursor}` 或 null |
| `last_successful_checkpoint`、`checkpoint_scope` | null 和 unavailable；该原始入口不暴露保存的检查点 |
| `trust` | 受信任回调与隐藏状态限制 |

返回目标的字节先保存快照，再校验模式和时钟。拒绝的产物标为 `validation_status=rejected`，消费/可用性未验证，且不调用所有者；通过者标为 `accepted`。实测字节 SHA 与引用声明 SHA 分别保留。路径、读取、大小或哈希失败可以使目标证据不可用，不能虚构快照引用。

composition ArtifactRef 覆盖收据实际保存字节，收据不包含自己的哈希。
manifest/输入的规范身份与原始产物字节哈希是不同概念。
base/transformation 哈希没有对应载体，仍为调用方声明。重复合成路径不是独立市场观测或概率。

普通准备、回调或所有者失败会保留一个失败 attempt，后续案例继续执行。不会为获取检查点而再次调用
已失效的所有者，也不会替换原始异常。取消信号直接传播。收据保存失败不返回虚构引用；若所有者已完成，
失败 attempt 中仍保留其实际结果。已有更早失败时保留原 code/message/stage。部分文件仅用于诊断，
不代表成功发布。持久调度仍属于 Runtime。

规划接口见[冲击规划](../concepts/impact-planning.zh-CN.md)。计划卖出所得不是现金：补充的 B 对照
只阻止 A 卖出，B 行情仍可交易且有充足容量；只有确实留有现金的对照能买入 B。
原 Task 10 浮点算术、原始二进制输出和条件候选数量均未改动。
