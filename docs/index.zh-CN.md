# quant-backtest-engine

你可以把报价、订单和初始资金交给这个 Rust 回测库，也可以在命令行运行它。
引擎把请求交给 NautilusTrader，由它处理撮合、成交费用和账户余额，再返回订单、成交和持仓结果。
本项目负责检查输入，并把双方的数据格式互相转换。每份请求和结果都有版本号，调用方可以据此检查格式。

当前为实验版本，覆盖简化美元现金股票账户、L1 报价回放和市价单。
新增目标权重计划工具和 v2 人民币/美元逐日账本，支持显式配置的 T+1、买入整手与报价权限。
[公司行为与退市等迁移边界](migration/corporate-action-conformance.zh-CN.md)仍明确保留 Python 后端。

## 开始使用

1. [跑通合成示例](quickstart.zh-CN.md)，预期净值 10019.78，手续费 0.22。
2. [查看输入输出](contracts.zh-CN.md)，明确时间、金额和能力边界。
3. [理解成交与估值](execution.zh-CN.md)，了解简化模型的假设。
4. [提交持久化任务](runtime.zh-CN.md)，使用 runtime 的可选 v5 接入。

## 几个常用名称

CLI 指命令行程序。你给它一个 JSON 文件，它输出一份 JSON 结果。
SDK 指供 Python 程序调用的客户端。它启动同一个引擎程序，检查结果，并把数据作为字典返回。
runtime 是单独的任务服务，负责排队、超时、取消和保存结果。本地运行示例时可以直接使用 CLI。
quant-platform 提供组合构造和结果分析，也保留尚未迁入 Rust 的 Python 回测功能。

L1 报价只有最优买价、卖价及相应数量，不包含完整订单簿。
净值（NAV）是现金加持仓估值。一个基点（bps）是万分之一，10 个基点即 0.1%。
T+1 在这里指开启该配置后，当天买入的股份要到下一交易日才能卖出。
「契约」指请求和结果必须遵守的字段、类型和校验规则。
金额在 JSON 中使用十进制字符串，例如 `"10000.00"`，以免读取时损失小数精度。
时间使用从 Unix 纪元起算的 UTC 纳秒整数，调用方需要完整保留这个整数。

## 项目分工

| 组件 | 职责 |
| --- | --- |
| 本引擎 | 输入输出契约、校验与上游适配 |
| NautilusTrader | 撮合、成交、费用与账户状态 |
| quant-platform | 组合构造、分析工具和 Python 兼容对照 |
| quant-backtest-runtime | 任务状态、进程隔离、取消与结果发布 |

参见[开发与验证](development.zh-CN.md)及[第三方声明](third-party-notices.zh-CN.md)。

## 接入状态

包版本 0.2.0，处于实验阶段，上游固定为 0.66.0。先运行
[目标权重到逐日账本教程](tutorial.zh-CN.md)，再查看[能力与已测试版本组合](capabilities.zh-CN.md)、
[正确性证据](correctness.zh-CN.md)、[批量运行成本](benchmarks.zh-CN.md)和[版本发布说明](releases.zh-CN.md)。
