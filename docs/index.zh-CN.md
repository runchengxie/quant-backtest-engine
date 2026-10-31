# quant-backtest-engine

独立的 Rust 回测库和 CLI，实际撮合、交易事件、手续费和现金账本由 NautilusTrader 完成。
本仓库维护版本化输入输出、校验与薄适配。直接调用引擎不需要启动任务服务。

当前为实验版本，覆盖简化美元现金股票账户、L1 报价回放和市价单。
新增目标权重计划工具和 v2 人民币/美元逐日账本，支持显式配置的 T+1、买入整手与报价权限。
[公司行为与退市等迁移边界](migration/corporate-action-conformance.zh-CN.md)仍明确保留 Python 后端。

## 开始使用

1. [跑通合成示例](quickstart.zh-CN.md)：预期净值 10019.78，手续费 0.22。
2. [查看输入输出](contracts.zh-CN.md)：明确时间、金额和能力边界。
3. [理解成交与估值](execution.zh-CN.md)：了解简化模型的假设。
4. [提交持久化任务](runtime.zh-CN.md)：使用 runtime 的可选 v5 接入。

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
