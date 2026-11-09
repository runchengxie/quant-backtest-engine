# 可选微观结构 Rust 加速器 {#rust}

[English](microstructure-rust.md)

显式选择后端。以下四种模式使用不同契约：

| 模式 | API | 财务或证据归属 |
| --- | --- | --- |
| 分钟 Python | `python.minute` ProductManifest 后端 | 分钟现金、持仓与检查点 |
| 订单簿 Python | `MatchingEngine(backend="python")` | 确定性订单簿及逐笔成交证据 |
| 可选订单簿 PyO3 | `MatchingEngine(backend="rust")` | `_microstructure_rs` 汇总成交及盘口轨迹；无逐笔成交证据 |
| Nautilus Rust | `rust.nautilus.sessions` | 现有 CLI/Nautilus 财务会话 |

两种订单簿模式均为底层 API，不是已注册的 ProductManifest 后端；也不提供学习式订单流或真实市场校准。
Rust 订单簿选项不会选择 Nautilus。缺少 `_microstructure_rs` 时抛出 ImportError，不静默回退。
`sort_simulator_events(events, backend="rust")` 遵循相同规则。

Core 的 `[microstructure]` 不依赖 Torch、scikit-learn、模型或原生安装包；迁移的模拟器依赖闭包仅用标准库。
Core 根导入不会加载模拟器或可选扩展。可选发行包仍为 `quant-microstructure-core` 0.1.0，
导入名 `_microstructure_rs`，PyO3 0.30.1，abi3 支持 Python >=3.12；core 验证矩阵为 Python 3.12、3.13。
原生包原有 Python >=3.12 支持声明保留。

## 构建与使用 {#_1}

从经过审查的提供方源码构建，所有产物均放在代码目录之外：

```sh
export CARGO_TARGET_DIR="$TASK_DATA/native-target"
export UV_CACHE_DIR="$TASK_DATA/uv-cache"
export TMPDIR="$TASK_DATA/tmp"
mkdir -p "$TMPDIR"
uv build --wheel --out-dir "$TASK_DATA/wheels" core-native
uv pip install --python "$ENV/bin/python" "$TASK_DATA"/wheels/quant_microstructure_core-*.whl
TICKNET_REQUIRE_RUST=1 "$ENV/bin/python" -I -m pytest "$TESTS" -q
```

## 正确性与测量 {#_2}

先在 `$ENV` 中分别安装 core 与 SDK 的普通 wheel；`$TESTS` 为放在代码目录外的模拟器验收测试副本。
不能以可编辑安装或源码 PYTHONPATH 充当安装验证。还须验证独立的无原生扩展、无 Torch 环境。
原生 wheel 仅拥有 `_microstructure_rs`，core 拥有 `quant_backtest_core`，SDK 拥有 `quant_backtest_engine`。
原生源码与安装包包含许可证声明。提供方 B 源码已实现，合并后安装包收据记录前不宣称发布或消费者切换完成。

## 逐笔成交与冲击估计限制 {#_3}

原生 v0.1 不提供逐笔成交证据；Python 回放会记录这些成交，原生回放不会。
依赖逐笔成交证据的算法必须拒绝原生模式，不能将证据缺失当作零成本或零成交量。
