# 安装可选产品包

[English](installation.md)

Core 0.3.0 提供显式选择的 Rust 执行器和可恢复 Python 分钟执行器。在 Python 3.12 或 3.13 环境中，
安装从同一已审核 Engine 提交构建的 SDK 0.3.0 和 core wheel。
core 的解释器范围为 `>=3.12,<3.14`。Python 3.14 上 pandas 3.0.6 要求
NumPy >=2.3.3，需另行验证数值基线升级。SDK 本身仍支持 Python 3.11。这里不要求、也不表示已发布到 PyPI；
应记录准确的源码提交和 wheel SHA256。

```sh
python -m venv "$ENV"
"$ENV/bin/python" -m pip install --no-index --no-deps \
  "$WHEELS/quant_backtest_engine_client-0.3.0-py3-none-any.whl" \
  "$WHEELS/quant_backtest_core-0.3.0-py3-none-any.whl"
"$ENV/bin/quant-backtest" capabilities rust.nautilus.sessions
```

基础 core 只导入标准库和 SDK，其 wheel 只拥有 `quant_backtest_core` 命名空间；
SDK 继续拥有 `quant_backtest_engine`。Linux 主机需要系统 IANA 时区数据库。
安装不需要 Platform、Runtime、pandas、NumPy、SciPy、Torch 或训练包。

## 构建与验证

环境、wheel、缓存和结果均放在仓库外。`core/uv.lock` 固定实际验证的开发工具和
可选依赖版本。为后续迁移的等价性验证，数值基线固定为 NumPy 2.2.6、pandas 3.0.6、
SciPy 1.18.1；公开 extra 的范围仍如下表所列。其中 `../python` 仅用于同仓库开发，不是发布身份。
分别运行 `uv build --wheel --project python` 和 `uv build --wheel --project core`，
各自指定仓库外的 `--out-dir`。安装验收使用 wheel 路径和 `python -I`，
不使用可编辑安装或 `PYTHONPATH`。消费者切换前必须固定准确的合并提交或已验证的 wheel 摘要。

```sh
"$ENV/bin/python" -I -B project_tools/verify_installed_product.py --mode base
for suite in packaging runner rust_adapter; do
  "$ENV/bin/python" -I -B -m unittest discover -s core/tests -p "test_$suite.py" -v
done
```

开发检查使用锁定的 dev 依赖组：`ruff check core`、`ruff format --check core` 和
`mypy --config-file core/pyproject.toml core/src`。本地验证前将
`UV_PROJECT_ENVIRONMENT`、`UV_CACHE_DIR`、`RUFF_CACHE_DIR`、`MYPY_CACHE_DIR`、
`PYTHONPYCACHEPREFIX`、`TMPDIR`、`CARGO_TARGET_DIR` 指向仓库外。

## 可选依赖

| extra | 依赖范围 |
| --- | --- |
| minute、scenario | pandas >=3.0.5,<3.1 |
| planning、cost | pandas >=3.0.5,<3.1；NumPy >=1.23；SciPy >=1.14 |
| microstructure | pandas >=3.0.5,<3.1；NumPy >=1.23 |
| daily | pandas >=3.0.5,<3.1; NumPy >=1.23; tzdata >=2025.2 |
| all | 上述依赖的并集，不含 Torch、Qlib 或 OSQP |

`scenario` 支持[市场路径与压力变换](../backtest/market-paths.zh-CN.md)，
`cost` 支持[交易成本证据](../backtest/transaction-cost-evidence.zh-CN.md)及适用范围拟合。
这些是独立叶子 API；minute extra 启用 `python.minute`，见[恢复和输入契约](recovery.zh-CN.md)。
daily extra 已在提供方 C 源码中启用独立日频实现及 `python.daily`，发布待完成；未知注册键会被拒绝。
选择请求前请阅读[后端限制](backends.zh-CN.md)。


安装包叶子模块验收须安装带 `[minute,cost,scenario]` 的 core wheel 及 pytest，
数值依赖使用锁定基线。运行
`python -I -B -m pytest core/tests -q -p no:cacheprovider`，并将
`QUANT_ENGINE_BINARY` 指向已验证内容摘要的 Rust 可执行文件，以运行适配器回归。
测试导入已安装 wheel，不使用源码树 `PYTHONPATH`。
提取代码保留旧签名，mypy 仍检查函数体，仅对缺少 pandas/SciPy 类型桩及
六处字典类型推断诊断作窄范围豁免；新增报价与协议的类型检查保持启用。

`minute` extra 现已提供直接[分钟会话及财务内核](../backtest/minute-session.zh-CN.md)。
最小分钟验收只安装 `[minute]` 和 pytest，执行
`python -I -B -m pytest core/tests/test_minute*.py core/tests/test_quantity_locks.py -q`
及 `python -I -B examples/product/minute_session.py`。
它依赖 pandas 及其 NumPy 依赖，不需要 SciPy、Platform、Runtime 或机器学习框架。
类型检查保留函数体检查；六处旧字典推断问题仅在各自模块内放宽：交易审计三处、分钟内核三处。

确定性订单簿撮合与回放已在提供方 B 源码实现，尚待合并发布。[订单簿 Python 与可选 PyO3 模式](../development/microstructure-rust.zh-CN.md).

## Task 9 执行归属（未发布）

提供方 B 已实现[纸面账户](../backtest/paper-account.zh-CN.md)、[账户事件与完整检查点](../contracts/paper-account-events.zh-CN.md)、[外部对账](../backtest/capital-and-reconciliation.zh-CN.md)、[中立待成交预留](../contracts/pending-allocation.zh-CN.md)和[执行冲击估计](../microstructure/impact-estimation.zh-CN.md)。pandas 账户和预留使用 core 的 `[planning]` 可选依赖；回放/冲击只需标准库。可选原生 wheel 尚无逐笔证据，仍拒绝冲击估计。调用者优化器负责完整研究验证，Engine 不提供 OSQP 优化器。Core 当前源码为 0.2.0；整体审查、合并与发布验证仍须先于消费者切换；旧检查点保留完整固定旧环境。

## 有界规划

尚未发布的 provider B 实现在 `quant_backtest_core.planning` 提供冲击规划、多期权重、
有限持仓与穷举参考、实际成交的策略归属。连续接口需显式安装 `[planning]` extra，
固定 NumPy 2.2.6、pandas 3.0.6、SciPy 1.18.1。有限持仓、仅买入参考及策略分配仅需标准库。
导入 planning 包保持惰性，不要求 Platform、Runtime、Torch 或 OSQP；通用优化器及风险估计
仍在外部。Core 当前源码为 0.2.0；源码实现不等于已合并发布或完成消费者切换。
参见[冲击规划](../concepts/impact-planning.zh-CN.md)、[有限持仓](../concepts/discrete-inventory.zh-CN.md)
和[策略分配](../backtest/sleeve-allocation.zh-CN.md)。

Core 当前源码版本为 0.2.0；仍须完成 B 阶段整体审查、合并及精确 wheel 验证后才可切换消费者。
`[scenario]` 额外支持[独立目标场景组合](scenarios.zh-CN.md)。每个 extra 应单独安装 wheel，
运行 `project_tools/verify_installed_scenarios.py --profile EXTRA`，并以 `--profile all` 检查并集。
`daily` 仅预留依赖，不启用 `python.daily`。

日频验收执行 `python -I -B project_tools/verify_installed_daily.py` 及 `python -I -B -m pytest core/tests/daily -q -p no:cacheprovider`。最小 daily 不依赖 PyArrow；pandas 字符串及标签索引的存储类型可能为 Python。原核算方严格对照另装 PyArrow 26.0.1，逐表逐 dtype 精确比较。两类环境均须保持数值、缺失值语义、顺序和财务汇总一致。
