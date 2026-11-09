# 显式选择 Rust 后端

[English](backends.md)

`rust.nautilus.sessions` 是 core 0.1.0 唯一可执行的注册键。
它只调用一次现有 `EngineClient.run_sessions`。NautilusTrader 0.66.0
负责成交与会计，不增加 Python 现金账本，也不自动切换后端。
原生 CLI、SDK 身份、Rust 版本和原生 v1/v2 数据契约均保持不变。

初始产品范围为 `rust-session.v1`、CNY、原始股数、`Asia/Shanghai`，
单位必须恰为 `cash: CNY`。原生 USD 能力保持不变，但这个固定单位的产品配置不暴露 USD。
执行前拒绝策略、模型版本、情景变换、预测与风险输入、公司行动、恢复和检查点请求。
五项声明能力为 `session_ledger`、`configured_t_plus_one`、`buy_lots`、
`quote_trade_permissions`、`quote_liquidity`。安装 extra 不扩展 Rust 能力。

## 执行合成会话

从同一源码提交一起复制 `fixtures/product/rust-session.json` 和
`synthetic-calendar.json`。日历必须是精确对象
`{"schema":"synthetic-calendar.v1","timezone":"Asia/Shanghai","sessions":[...]}`，
日期与请求中的有序会话日期一致。它只声明已提供的会话，不生成交易所日历，也不证明这些日期是交易日。

```sh
"$ENV/bin/quant-backtest" run-manifest "$INPUTS/rust-session.json" \
  --artifact-root "$INPUTS" --output-root "$OUTPUTS" \
  --rust-executable "$ENGINE" --rust-sha256 "$ENGINE_SHA256"
```

`$ENGINE` 是另行验证过的 Rust 可执行文件绝对路径，`$ENGINE_SHA256` 是其小写 SHA256。
二者是可信宿主参数，不来自请求。`examples/product/rust_session.py` 接受同样的参数。
该 100 股 CNY 会话样例的最终现金和净值均为 `10197.8`，费用为 `2.2`。
独立的原生 quote-v1 样例仍为 `10000 -> 10019.78`，费用为 `0.22`。

Python 调用方式为 `run_manifest(manifest, context=BackendContext(artifact_root,
output_root, rust_executable, rust_sha256))`。后端接口包括 `descriptor()`、
`validate(manifest, context)`、`run(manifest, context)`。注册表由固定代码定义，
请求不能选择导入路径或可执行命令。

## 校验与工件

工件 URI 必须是可信输入根目录内的相对本地路径。网络地址、绝对路径、目录穿越和
逃出根目录的符号链接均被拒绝。解析前校验精确文件字节的 SHA256，拒绝重复 JSON 键和
非有限常量。加载工件中的品种与会话后，再执行 SDK 配置校验和原生 v2 语义预检。
字符串时钟直接转换为 Python 整数，不经过浮点数。Rust 在创建财务执行方前还会独立校验请求。

输出根目录也由可信宿主提供。结果 `<output_uri>` 和原生工件
`<output_uri>.native.json` 以独占方式新建，绝不覆盖已有文件或输入。
每次执行使用新的输出名称。可信调用方须确保执行期间根目录和符号链接保持稳定；
这里不提供针对恶意并发文件写入者的沙箱。
原生失败保留原始异常，不产生成功结果，也不触发后备执行。
持久化失败可能留下供排查的原生工件，不能把它当作已发布成功结果。
持久任务监督仍属于 Runtime。

## 证据与身份

| 产品表 | 原生来源 |
| --- | --- |
| fills | fills |
| positions | daily_positions |
| reports | orders（订单终态） |
| daily | daily_ledger |

其他注册表均明确不可用。每日现金与净值观测不是现金流水账本，订单终态也不等于接纳或撤单事件。
费用保留在原生成交佣金和每日证据中，不再扣一次。归一化时钟为十进制整数字符串；
完整原生字段，包括拒绝记录和整数时钟，均保留在原始工件中。

原始工件保存 SDK 返回的完整已校验对象：UTF-8 JSON、键排序、紧凑分隔符和一个末尾换行。
它不是子进程原始 stdout。`normalization.source_sha256` 对应这些实际落盘字节。
`manifest_sha256` 使用同样的序列化规则计算请求编解码输出的摘要，不代表任意输入 JSON 空白格式的摘要。

提供方 distribution/version 标识已安装的 core 适配器，未知 Git 提交为 null。
`source_sha256` 按相对路径排序计算已安装 core 的 `.py` 文件：每个 UTF-8 路径加 NUL，
再加文件字节和 NUL。已验证 Rust 可执行文件摘要放在 `artifact_sha256`，绝不称为 Rust 源码摘要。
SDK 版本来自已安装包元数据。`required-*` 依赖键描述要求的原生契约和 Nautilus 0.66.0，
并非实测的 Rust 包版本。原生结果校验 Nautilus 身份，但任意可执行文件摘要不能证明 Rust 包版本。
不提供可执行文件时，能力查询中的 executable 身份为 null。
准确的发布与源码回执，以及后续 Runtime 的完整依赖闭包，仍需分别记录。
