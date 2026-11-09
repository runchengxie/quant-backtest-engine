# 安装可选产品包

[English](installation.md)

Core 0.1.0 提供显式选择的 Rust 会话执行器。在 Python 3.12 或 3.13 环境中，
安装从同一已审核 Engine 提交构建的 SDK 0.3.0 和 core wheel。
core 的解释器范围为 `>=3.12,<3.14`。Python 3.14 上 pandas 3.0.6 要求
NumPy >=2.3.3，需另行验证数值基线升级。SDK 本身仍支持 Python 3.11。这里不要求、也不表示已发布到 PyPI；
应记录准确的源码提交和 wheel SHA256。

```sh
python -m venv "$ENV"
"$ENV/bin/python" -m pip install --no-index --no-deps \
  "$WHEELS/quant_backtest_engine_client-0.3.0-py3-none-any.whl" \
  "$WHEELS/quant_backtest_core-0.1.0-py3-none-any.whl"
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
| microstructure、daily | pandas >=3.0.5,<3.1；NumPy >=1.23 |
| all | 上述依赖的并集，不含 Torch、Qlib 或 OSQP |

`scenario` 支持[市场路径与压力变换](../backtest/market-paths.zh-CN.md)，
`cost` 支持[交易成本证据](../backtest/transaction-cost-evidence.zh-CN.md)及适用范围拟合。
这些是独立叶子 API；其他 extra 仍为后续迁移预留依赖组。安装 extra 不会在 core 0.1.0 中实现或注册 Python 后端。
`python.minute`、`python.daily` 会明确报告不可用，未知注册键也会被拒绝。
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
