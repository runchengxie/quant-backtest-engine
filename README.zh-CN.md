# quant-backtest-engine

[English](README.md) · [中文文档](https://runchengxie.github.io/quant-backtest-engine/index.zh-CN/)

把报价、计划下单和初始资金交给这个引擎，就能查看订单怎样成交，以及成交后账户还剩多少资金和持仓。
引擎使用 NautilusTrader 处理撮合与记账，返回成交、手续费、持仓和账户余额。
你可以通过 Rust 库、命令行或独立 Python 客户端调用它。

如果你已经确定要测试哪些订单，可以从这里开始。仓库中的合成示例无需行情数据、策略代码或任务服务。

当前源码已实现提供方 A：可选 Python core 0.1.0 提供独立分钟会话、来源绑定的恢复以及
已迁入的财务叶子 API；SDK 0.3.0 保留既有客户端命名空间。请从
[可选产品安装](docs/product/installation.zh-CN.md)和[恢复示例](docs/product/recovery.zh-CN.md)开始，
使用确切的已审查源码和 wheel 摘要。提供方 C 的集成、发布验证及其消费者切换仍待完成；这不表示已经在 PyPI 发布或完成消费者版本发布。

## 先跑一个小回测

在 Linux 的源码仓库根目录运行，需要 Rust 1.99.0 或更新版本。
依赖已锁定，其中 NautilusTrader 固定为 0.66.0。请将编译目录放在源码之外。

```sh
export CARGO_TARGET_DIR=/absolute/external/engine-build
cargo run --locked -- run fixtures/roundtrip.json
```

将示例编译路径替换为你自己的目录，第一次运行会先编译引擎。
样例从 10000 美元开始，以 10 美元买入 10 股，再以 12 美元卖出。
扣除手续费后，JSON 结果中的 `cash` 和 `equity` 均为 `"10019.78"`，
`commission` 为 `"0.22"`。回测完成仍可能包含拒单，换成自己的输入后要检查订单状态。

想直接使用可执行文件，可以按[实验版本安装说明](docs/releases.zh-CN.md)操作。
文档中的 alpha.2 版本提供静态校验功能，alpha.1 没有这项功能。

## 当前能做什么

这是实验版本，面向简化现金股票账户和 L1 报价，也就是最优买卖价。
输入是预先生成的市价单，选股和组合构造由调用方负责。
逐日接口提供人民币或美元账户记录，并支持显式配置的 T+1、买入整手等规则。
Rust 后端仍不支持公司行为、退市和完整市场规则；单独的 Python 分钟后端在文档规定的范围内支持显式公司行为输入带。用于新场景前，请先看[能力矩阵](docs/capabilities.zh-CN.md)。

引擎负责运行回测。[quant-backtest-runtime](https://github.com/runchengxie/quant-backtest-runtime)
增加队列、任务状态、取消、资源限制和结果保存。
[quant-platform](https://github.com/runchengxie/quant-platform)目前保留 Python 后端，作为兼容对照并处理暂不支持的场景。
[可复用产品迁移](docs/migration/reusable-product.zh-CN.md)记录了已实现的财务核算与后续消费者关卡。
Core 0.3.0 增加[独立日频实现](docs/product/daily-inputs.zh-CN.md)；提供方 C 发布和
消费者切换仍须完成审核、合并及确切产物验证。
本引擎可以独立使用，不需要安装这两个项目。

## 接下来

- [快速开始与 Rust API](docs/quickstart.zh-CN.md)，或 [Python 客户端](docs/python-client.zh-CN.md)
- [目标权重教程](docs/tutorial.zh-CN.md)。生成订单并查看逐日账本
- [输入输出契约](docs/contracts.zh-CN.md)和[成交假设](docs/execution.zh-CN.md)。理解请求与结果
- [Runtime 接入](docs/runtime.zh-CN.md)。校验请求并提交引擎任务
- [性能实验与分析](docs/benchmarks.zh-CN.md)，或[开发检查](docs/development.zh-CN.md)

## 许可证

LGPL-3.0-only。原文见 [LICENSE](LICENSE)、[COPYING](COPYING)，
依赖声明见[第三方说明](docs/third-party-notices.zh-CN.md)。上游依赖保留各自的版权与许可要求。

确定性订单簿撮合与回放已在提供方 B 源码实现，尚待合并发布。[订单簿 Python 与可选 PyO3 模式](docs/development/microstructure-rust.zh-CN.md).
