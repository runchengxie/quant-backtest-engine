# 能力与兼容性矩阵

当前状态为实验阶段，包版本 0.2.0，上游 NautilusTrader 固定为 0.66.0。
已验证的运行环境为 Linux。下表的支持表示合成案例通过测试，不代表完整交易所规则或真实数据验证。

| 能力 | 状态 | 入口或边界 |
| --- | --- | --- |
| 独立 Rust 库和 CLI | 支持 | 不依赖 platform 或 runtime |
| 美元快照与报价市价单 | 支持 | `engine_request.v1` / runtime v5 |
| 人民币及美元逐日账本 | 支持 | `engine_request.v2` / runtime v6 |
| 目标权重转数量 | 支持，独立估算 | `size`；预计卖出收入不保证实际成交 |
| 只做多现金账户和统一费率 | 支持 | 现金检查包含费用，费率显式配置 |
| 配置的 T+1 和买入手数 | v2 支持 | 调用方提供交易日、开关和每手数量 |
| 停牌和涨跌停权限 | 显式输入 | 不从价格或交易所规则推断 |
| 报价数量约束、部分成交及 IOC 余量 | v2 支持 | 不等同于日成交量参与率模型 |
| 声明时钟上的无前视下单 | 支持 | 无法证明源数据本身在当时已可用 |
| 分红、送转股、应收款和退市政策 | 不支持 | 保留 Python 后端，见[验证记录](migration/corporate-action-conformance.zh-CN.md) |
| 交易日历、税率、融资、做空、换汇 | 不支持 | 选择币种不会自动启用这些规则 |
| 完整 execution-aware 标准结果包 | 未提供 | 仍需研究时钟、生产者和来源证据 |
| 训练、研究验证、调度 | 引擎之外 | 由研究层和 runtime 负责 |

## 已测试的提供方与调用方组合

兼容性记录以源码提交和调用方提交为单位。两个调用方的专门 CI 都会构建引擎提交
`3ee74bfa21d743e595ce61d0ac06b97dd588ebd6` 并执行真实二进制测试。

| 调用方 | 交付记录 | 接入方式 |
| --- | --- | --- |
| quant-backtest-runtime | [v6 PR](https://github.com/runchengxie/quant-backtest-runtime/pull/39) | 保留 v5 快照，显式选择 v6 逐日回放 |
| quant-platform | [适配器 PR](https://github.com/runchengxie/quant-platform/pull/170) | 显式调用 EngineClient，Python 默认后端保留 |

准确的调用方版本以 PR 合并提交及其 CI 记录为准。二进制 SHA-256 只标识文件字节，
不能单独证明源码版本。部署时同时记录源码提交、文件摘要和构建工具链。

## 升级原则

同一协议版本保持输入输出兼容；不支持的语义明确失败，不静默降级。
升级时固定引擎提交，执行[正确性案例](correctness.zh-CN.md)和调用方集成测试。
实验阶段不承诺 Rust API 稳定。只有具体调用方所需的语义和输出验证通过后，才考虑移除对应 Python 兼容路径。

platform 合并提交：`db1ce93d0d311cf28fa087072ad1cedc70df05a1`。
