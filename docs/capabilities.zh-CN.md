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

兼容性记录以源码提交和调用方提交为单位，不使用 worktree 目录名或可变的二进制路径作为版本身份。

| 组件 | 已合并版本与交付 | 实际测试的提供方与边界 |
| --- | --- | --- |
| 独立 Python SDK | `f0ba2ef193c721c7bd497c4d80a7bc8a01c18a31`，[PR #7](https://github.com/runchengxie/quant-backtest-engine/pull/7) | 无运行时依赖的独立 wheel，返回数量规划和逐日结果字典 |
| quant-backtest-runtime | `bb1f20eeab1105b9001663ec6e39ab523b57d8ea`，[PR #41](https://github.com/runchengxie/quant-backtest-runtime/pull/41) | 真实 CLI 提供方 `341de0177bc3e6b95ff8b4abb8c80c83eaedf207`，基础安装不依赖 platform，旧任务通过 `legacy` extra 安装 |
| quant-platform | `3ac555bbfc8dba69d1a910320d5eefe947122df3`，[PR #171](https://github.com/runchengxie/quant-platform/pull/171) | SDK 与真实 CLI 均固定到 `f0ba2ef193c721c7bd497c4d80a7bc8a01c18a31`，使用 `engine` extra，仅转换平台分析表格 |

platform 的历史源码目录已退役。公开入口为 `quant_platform.portfolio`、
`quant_platform.analytics` 和 `quant_platform.backtest`。
旧 `portfolio_backtester` 命名空间保留为兼容别名，仍需使用的 Python 回测明确位于
`quant_platform.backtest.legacy`，参见[归属与最终删除条件](https://runchengxie.github.io/quant-platform/migration/portfolio-boundaries.zh-CN/)。
导入迁移不能证明 Rust 已覆盖公司行动、容量或完整执行证据。本次源码调整不切换生产任务或数据。

更早的 v6 与适配器基线保留在
[runtime PR #39](https://github.com/runchengxie/quant-backtest-runtime/pull/39) 和
[platform PR #170](https://github.com/runchengxie/quant-platform/pull/170)。
二进制 SHA-256 只标识文件字节，不是源码版本或签名，部署时同时保留源码、构建记录和文件摘要。

## 升级原则

同一协议版本保持输入输出兼容；不支持的语义明确失败，不静默降级。
升级时固定引擎提交，执行[正确性案例](correctness.zh-CN.md)和调用方集成测试。
实验阶段不承诺 Rust API 稳定。只有具体调用方所需的语义和输出验证通过后，才考虑移除对应 Python 兼容路径。

