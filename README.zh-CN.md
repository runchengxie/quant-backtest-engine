# Quant Backtest Engine

[English](README.md) · [说明文档与交互示例](https://runchengxie.github.io/quant-backtest-engine/index.zh-CN/)

把历史行情和交易计划交给这个模块，查看订单能成交多少、付出多少成本，以及成交后还剩多少现金和股票。下一次决策可以使用实际账户状态，也可以换一组成交条件，比较结果怎样变化。

这是供其他项目复用的回测模块。你提供策略与数据，通过 Rust、命令行或 Python 调用。引擎可以独立运行，也可以接入配套的研究平台和任务服务。

## 可以用它研究什么

| 你关心的问题 | 已有功能 |
| --- | --- |
| 订单会怎样成交 | 报价回测、多档盘口（L2）与逐笔成交事件回放、限价单、撤单和给定的下单与撤单等待时间 |
| 部分成交后怎样继续决策 | 核对实际持仓、可用现金与未完成订单，再按目标持仓决定下一笔数量 |
| 成本和限制怎样影响交易 | 手续费、滑点与冲击假设、整手等离散约束，以及有限范围的交易规划 |
| 结果受哪些条件影响 | 独立情景账户、给定市场路径、账户核对与恢复测试 |

各入口支持的输入和规则分别列在[能力说明](docs/capabilities.zh-CN.md)与[执行精度说明](docs/product/execution-fidelity.zh-CN.md)。冲击参数和真实排队位置需要各自的校准证据。

## 先跑一个事件级示例

在 Linux 源码目录中运行，需要 Rust 1.99 或更新版本。先选一个仓库外的目录保存构建文件。

```sh
export CARGO_TARGET_DIR=/path/to/your/data/engine-build
cargo run --locked -- depth fixtures/depth.json
```

合成账户从 10,000 元开始，沿两个卖价档位买入五股。手续费合计 0.05 元，结果中的 `account.cash` 为 `"9949.65"`。查看 `account.fills`、订单状态和事件回执，可以逐笔核对成交。这个示例无需下载行情数据。

Python 安装与源码包使用方法见[安装说明](docs/product/installation.zh-CN.md)。原生适配器使用锁定的 NautilusTrader 0.66.0 处理撮合与记账。Python 还提供分钟、日频执行，以及规划和情景接口。

## 接下来从哪里看

- 调用模块，见[快速开始](docs/quickstart.zh-CN.md)与 [Python 客户端](docs/python-client.zh-CN.md)。
- 理解成交、成本和账户反馈，见[交互式机制说明](https://runchengxie.github.io/quant-backtest-engine/learn/zh-CN/)。
- 核对输入、输出与验收范围，见[接口契约](docs/product/contracts.zh-CN.md)和[交付验收](docs/product/acceptance.zh-CN.md)。
- 参与开发，见[开发说明](docs/development.zh-CN.md)，其中收录架构、测试和语言分工。

[quant-platform](https://github.com/runchengxie/quant-platform)承接策略研究，[quant-backtest-runtime](https://github.com/runchengxie/quant-backtest-runtime)管理持久任务。它们通过明确的接口调用本模块。

## 许可证

LGPL-3.0-only。原文见 [LICENSE](LICENSE)、[COPYING](COPYING)和[第三方说明](docs/third-party-notices.zh-CN.md)。依赖保留各自的许可要求。
