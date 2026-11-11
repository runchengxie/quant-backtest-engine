# 能力与兼容性矩阵

[English](capabilities.md)

当前状态为实验阶段，包版本 0.2.0，上游 NautilusTrader 固定为 0.66.0。
已验证的运行环境为 Linux。下表的支持表示合成案例通过测试，不代表完整交易所规则或真实数据验证。

| 能力 | 状态 | 入口或边界 |
| --- | --- | --- |
| 独立 Rust 库和 CLI | 支持 | 不依赖 platform 或 runtime |
| 美元快照与报价市价单 | 支持 | `engine_request.v1` / runtime v5 |
| 人民币及美元逐日账本 | 支持 | `engine_request.v2` / runtime v6 |
| 目标权重转数量 | 支持，独立估算 | `size`。预计卖出收入不保证实际成交 |
| 只做多现金账户和统一费率 | 支持 | 现金检查包含费用，费率显式配置 |
| 配置的 T+1 和买入手数 | v2 支持 | 调用方提供交易日、开关和每手数量 |
| 停牌和涨跌停权限 | 显式输入 | 不从价格或交易所规则推断 |
| 报价数量约束、部分成交及 IOC 余量 | v2 支持 | 不等同于日成交量参与率模型 |
| 声明时钟上的无前视下单 | 支持 | 无法证明源数据本身在当时已可用 |
| 分红、送转股、应收款和退市政策 | 不支持 | 保留 Python 后端，见[验证记录](migration/corporate-action-conformance.zh-CN.md) |
| 交易日历、税率、融资、做空、换汇 | 不支持 | 选择币种不会自动启用这些规则 |
| 完整 execution-aware 标准结果包 | 未提供 | 仍需研究时钟、生产者和来源证据 |
| 训练和研究验证 | 引擎之外 | 由研究层负责 |
| 任务提交、状态及进程管理 | 引擎之外 | runtime 提供，常驻调度与全局队列需另行实现 |

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
SHA-256 用于检查二进制文件的字节是否一致。部署时还要记录源码提交和构建过程，
并按发布方提供的签名方式核实来源（如有签名）。

## 升级原则

同一协议版本保持输入输出兼容。不支持的语义明确失败，不静默降级。
升级时固定引擎提交，执行[正确性案例](correctness.zh-CN.md)和调用方集成测试。
实验阶段不承诺 Rust API 稳定。只有具体调用方所需的语义和输出验证通过后，才考虑移除对应 Python 兼容路径。

## 可选 Python 叶子 API

Core 0.2.0 包含[合成路径、压力与冲击](backtest/market-paths.zh-CN.md)、
[中立成本证据](backtest/cost-evidence.zh-CN.md)、
[交易审计与适用范围拟合](backtest/transaction-cost-evidence.zh-CN.md)，以及
[成交与资金流证据](backtest/execution-integrity.zh-CN.md)。这些能力属于可选 Python 库，
不属于 Rust 后端；不会注册 Python 日频账户，也不证明旧检查点可以迁移。
提供者关卡前代码仍待审核，发布可用性单独记录。

可选 Python 库还提供完整的[分钟会话](backtest/minute-session.zh-CN.md)与
[同步执行接口](guides/minute-execution.zh-CN.md)，包含公司行动、估值、资金流、数量锁和延迟账户视图。
直接 Python 接口及产品运行器的 `python.minute` 均已提供，后者支持[来源绑定的恢复](product/recovery.zh-CN.md)。

确定性订单簿撮合与回放已在提供方 B 源码实现，尚待合并发布。[订单簿 Python 与可选 PyO3 模式](development/microstructure-rust.zh-CN.md).

## Task 9 执行归属（未发布）

提供方 B 已实现[纸面账户](backtest/paper-account.zh-CN.md)、[账户事件与完整检查点](contracts/paper-account-events.zh-CN.md)、[外部对账](backtest/capital-and-reconciliation.zh-CN.md)、[中立待成交预留](contracts/pending-allocation.zh-CN.md)和[执行冲击估计](microstructure/impact-estimation.zh-CN.md)。pandas 账户和预留使用 core 的 `[planning]` 可选依赖；回放/冲击只需标准库。可选原生 wheel 尚无逐笔证据，仍拒绝冲击估计。调用者优化器负责完整研究验证，Engine 不提供 OSQP 优化器。Core 当前源码为 0.2.0；整体审查、合并和精确产物验证先于消费者切换；旧检查点保留完整固定旧环境。

## 独立场景组合

`[scenario]` 中的 `run_scenarios` 仅支持 `python.minute` / `scenario-minute-targets.v1`
组合配置：消费外部实际目标，每次使用独立账户、策略和冲击实例，保留精确输入、目标与投影收据。
risk 必须为 null，策略必须是已有的空配置目标权重身份。可用性是声明的合成收盘约定，并非观测到达时间。
原始 minute 与 Rust 守卫保持不变，任一后端都不继承 Python 叶子能力的并集。
见[完整后端矩阵](product/backends.zh-CN.md)、[场景示例](product/scenarios.zh-CN.md)和
[规划示例](concepts/impact-planning.zh-CN.md)。

学习前端回放八个主题中的 21 个固定合成预设，不增加执行后端、市场校准或浏览器财务计算。求解器证据覆盖有限网格，连续求解迭代仍不可用。
