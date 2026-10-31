# Python 客户端

`quant-backtest-engine-client` 支持 Python 3.11 及以上版本，运行时只使用标准库，无需 quant-platform、pandas、NumPy 或 runtime 服务。在引擎源码目录安装：

```sh
python -m pip install ./python
```

通过 `from quant_backtest_engine import EngineClient, EngineProtocolError` 导入。构造参数为可执行文件的绝对路径、已核对发布清单的 SHA256 摘要，以及可选的 `timeout=30` 和 `source_revision=None`。源码版本仅用于调用方记录，不能替代摘要校验。

`size(request)` 接收 `sizing_request.v1`，返回 `sizing_result.v1`；`run_sessions(request)` 接收 `engine_request.v2`，返回 `engine_result.v2`。返回值为字典，保留金额字符串和 UTC 纳秒整数，不转换为 DataFrame。

客户端校验程序摘要并运行独立快照，严格解析 JSON，核对状态、订单覆盖、成交时钟、估值报价、逐日现金、持仓、费用、净值以及声明的 T+1 限制。程序失败或证据不一致时抛出 `EngineProtocolError`；构造参数错误抛出 `ValueError`。请求的业务约束仍由引擎执行。仓位规划只是估计，不保证能够成交。

SDK 负责进程通信和契约核验；消费方负责策略接口、表格转换与持久化。SDK 不实现第二套撮合或组合模拟器，也不改变 Rust 引擎的算法。代码遵循本仓库 LGPL-3.0-only 许可，边界校验来自同一作者的 quant-platform 客户端。

测试仅使用合成数据。CI 构建 wheel 后，在独立环境中无依赖安装并运行测试；设置 `QUANT_ENGINE_BINARY` 可额外验证已选择的真实引擎程序。

[English and usage example](python-client.md)
