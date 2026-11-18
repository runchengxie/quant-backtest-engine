# 可选微观结构 Rust 加速器 {#rust}

[English](microstructure-rust.md)

显式选择后端。以下四种模式使用不同契约：

| 模式 | API | 财务或证据归属 |
| --- | --- | --- |
| 分钟 Python | `python.minute` ProductManifest 后端 | 分钟现金、持仓与检查点 |
| 订单簿 Python | `MatchingEngine(backend="python")` | 确定性订单簿及逐笔成交证据 |
| 可选订单簿 PyO3 | `MatchingEngine(backend="rust")` | `_microstructure_rs` 逐笔成交证据及盘口轨迹 |
| Nautilus Rust | `rust.nautilus.sessions` | 现有 CLI/Nautilus 财务会话 |

两种订单簿模式通过底层 API 调用，ProductManifest 仍使用已注册的后端。学习式订单流与真实市场校准属于待补能力。
Rust 订单簿选项不会选择 Nautilus。缺少 `_microstructure_rs` 时抛出 ImportError，不静默回退。
`sort_simulator_events(events, backend="rust")` 遵循相同规则。

Core 的 `[microstructure]` 不依赖 Torch、scikit-learn、模型或原生安装包；迁移的模拟器依赖闭包仅用标准库。
Core 根导入不会加载模拟器或可选扩展。可选发行包仍为 `quant-microstructure-core` 0.2.0，
导入名 `_microstructure_rs`，PyO3 0.30.1，abi3 支持 Python >=3.12；core 验证矩阵为 Python 3.12、3.13。
原生包原有 Python >=3.12 支持声明保留。

## 构建与使用 {#_1}

从经过审查的提供方源码构建，所有产物均放在代码目录之外：

```sh
export CARGO_TARGET_DIR="$TASK_DATA/native-target"
export UV_CACHE_DIR="$TASK_DATA/uv-cache"
export TMPDIR="$TASK_DATA/tmp"
mkdir -p "$TMPDIR"
uv build --wheel --out-dir "$TASK_DATA/wheels" packages/microstructure-native
uv pip install --python "$ENV/bin/python" "$TASK_DATA"/wheels/quant_microstructure_core-*.whl
TICKNET_REQUIRE_RUST=1 "$ENV/bin/python" -I -m pytest "$TESTS" -q
```

## 正确性与测量 {#_2}

先在 `$ENV` 中分别安装 core 与 SDK 的普通 wheel；`$TESTS` 为放在代码目录外的模拟器验收测试副本。
不能以可编辑安装或源码 PYTHONPATH 充当安装验证。还须验证独立的无原生扩展、无 Torch 环境。
原生 wheel 仅拥有 `_microstructure_rs`，core 拥有 `quant_backtest_core`，SDK 拥有 `quant_backtest_engine`。
原生源码与安装包包含许可证声明。提供方 B 源码已实现，合并后安装包收据记录前不宣称发布或消费者切换完成。

## 逐笔成交与冲击估计限制 {#_3}

原生 0.2 新增 `apply_order_with_fills` 和 `replay_with_fills`。每笔成交按撮合顺序记录买卖订单标识、整数成交价和数量。原有 `apply_order` 汇总返回值与 `replay` 盘口返回值保持兼容。

Python 适配层调用明细接口，ReplaySession 和 ImpactEstimator 保留对应证据，包括背景订单成交和被动子单成交。Core 与原生 wheel 应从同一已验证版本构建。旧原生包缺少明细接口时，Core 会在提交订单前报错。

Python 与 Rust 的一致性范围要求显式订单标识唯一。历史重复标识差异继续记录在[撮合说明](../microstructure/matching.zh-CN.md)。本轮补齐撮合证据，给定延迟、真实排队位置、永久冲击因果估计和市场校准各有独立验收范围。

## 合成性能测量 {#synthetic-performance-measurements}

安装普通 wheel 后运行 `python -I scripts/release/benchmark_microstructure.py --output /external/new-report.json`。默认使用一万条事件、八条独立路径和五次重复。计时前和每轮运行都核对 Python 与 Rust 的完整结果。

报告记录安装文件哈希、源码版本、种子、输入哈希、原始耗时和中位数。计时包含公开接口的 Python 结果转换与内存分配，结果哈希计算放在计时之外。各路径顺序运行，每条路径使用独立订单簿。这些本机合成测量用于安排性能分析，实际市场容量和生产吞吐量需要各自的证据。

后续迁移按测量结果推进。本轮已提供原生逐笔撮合与批量回放，Python 保留编排和独立参考实现。分钟账本、公司行动与检查点需要先确定兼容方案。NumPy／SciPy 规划已经调用编译后的数值库，迁到 Rust 前应测量收益并验证求解器等价性。
