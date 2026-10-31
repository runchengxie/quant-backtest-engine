# quant-backtest-engine

[English](README.md) · [在线文档](https://runchengxie.github.io/quant-backtest-engine/index.zh-CN/)

你可以把报价、订单和初始资金交给这个 Rust 回测库，也可以在命令行运行它。
引擎把请求交给 NautilusTrader，由它处理撮合、成交费用和账户余额，再返回订单、成交和持仓结果。
本项目负责检查输入，并把双方的数据格式互相转换。每份请求和结果都有版本号，调用方可以据此检查格式。

当前为实验版本，覆盖简化美元现金股票账户、L1 报价回放、预先生成的市价单和最终估值。
新增目标权重计划工具和人民币/美元逐日账本，支持显式配置的 T+1、买入整手与报价权限。
分红、送转股和退市等场景继续使用 Python 后端。具体支持范围见[能力矩阵](docs/capabilities.zh-CN.md)。
Python 用户可通过独立 SDK 调用引擎，需要排队和保存任务结果时再接入 runtime。
[文档首页](docs/index.zh-CN.md#几个常用名称)解释这些名称和常用单位。

## 运行示例

需要 Rust 1.99.0 或以上，上游固定为 NautilusTrader 0.66.0。

```sh
cargo build --locked
cargo run --locked -- capabilities
cargo run --locked -- run fixtures/roundtrip.json
```

合成样例初始资金为 10000 美元，以 10 美元买入 10 股，再以 12 美元卖出。
买卖各收 10 个基点手续费，最终现金和净值为 10019.78，手续费合计 0.22。

金额使用十进制字符串，时间使用 UTC 纳秒整数。执行成功不代表每个订单都已成交，
调用方必须检查订单状态。

## 文档

- [快速开始](https://runchengxie.github.io/quant-backtest-engine/quickstart.zh-CN/)
- [输入输出契约](https://runchengxie.github.io/quant-backtest-engine/contracts.zh-CN/)
- [成交与估值假设](https://runchengxie.github.io/quant-backtest-engine/execution.zh-CN/)
- [Runtime 接入](https://runchengxie.github.io/quant-backtest-engine/runtime.zh-CN/)
- [开发与验证](https://runchengxie.github.io/quant-backtest-engine/development.zh-CN/)

组合构造属于调用方。runtime 负责排队、任务状态、资源控制、取消和结果发布，
独立引擎不依赖它们。runtime 已有可选 v5/v6 接入，保留旧任务协议与指纹。

许可证为 LGPL-3.0-only，原文保留在根目录的 LICENSE 与 COPYING。
第三方说明见 [docs/third-party-notices.md](docs/third-party-notices.md)。

`validate REQUEST.json` 或 `validate -`（标准输入）只做静态校验，不运行回测。
它复用执行入口的请求解析与语义校验，输入上限为 1 MiB。成功时仅输出
`engine_validation.v1` 回执，包含 `validator_version=1`、
`request_schema=engine_request.v1`、`valid=true` 和原始字节的 `input_sha256`。
`capabilities` 单独声明 `validator_version`，不改变模拟能力列表。
格式、语义或大小不合要求时退出码为 2，标准输出为空。文件或内部故障退出码为 1。
