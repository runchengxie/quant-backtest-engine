# quant-backtest-engine

[English](README.md) · [在线文档](https://runchengxie.github.io/quant-backtest-engine/index.zh-CN/)

独立的 Rust 回测库和 CLI，内部直接调用 NautilusTrader。
撮合、手续费与账户记账由上游完成，本仓库维护版本化输入输出、校验与薄适配。

当前为实验版本，覆盖简化美元现金股票账户、L1 报价回放、预先生成的市价单和最终估值。
A 股规则、目标权重换算和每日完整账本仍需迁移验证，现有 Python 后端保留作对照。

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
独立引擎不依赖它们。runtime 已有可选 v5 接入，保留旧任务协议与指纹。

许可证为 LGPL-3.0-only，原文保留在根目录的 LICENSE 与 COPYING。
第三方说明见 [docs/third-party-notices.md](docs/third-party-notices.md)。
