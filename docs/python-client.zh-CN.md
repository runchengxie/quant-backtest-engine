# Python 客户端

`quant-backtest-engine-client` 支持 Python 3.11 及以上版本，运行时只使用标准库，无需 quant-platform、pandas、NumPy 或 runtime 服务。在引擎源码目录运行下面的安装命令。

```sh
python -m pip install ./python
```

在 Python 中用 `from quant_backtest_engine import EngineClient, EngineProtocolError` 导入。
创建客户端时，传入引擎程序的绝对路径和 SHA256 摘要。先用发布清单核对这个摘要，客户端会在运行前再次检查文件。
还可以设置 `timeout=30` 和 `source_revision=None`。前者控制超时秒数，后者记录源码提交。
客户端始终用文件摘要检查程序，源码提交供调用方追溯版本。

`size(request)` 接收 `sizing_request.v1`，返回 `sizing_result.v1`。`run_sessions(request)` 接收 `engine_request.v2`，返回 `engine_result.v2`。返回值为字典，保留金额字符串和 UTC 纳秒整数，不转换为 DataFrame。

客户端先检查程序摘要，再复制出一份已核对的程序供本次调用使用。程序结束后，客户端严格解析 JSON，
检查每笔请求订单是否都有对应结果，成交时间是否合格，估值是否使用请求中的报价。
它还核对每日现金、持仓、费用和净值，并检查配置的 T+1 卖出限制。
程序失败或结果对不上时，客户端抛出 `EngineProtocolError`。构造参数错误抛出 `ValueError`。
引擎负责执行请求中的交易约束。数量规划根据参考价估算订单，实际成交还取决于后续报价和可用资金。

SDK 负责进程通信和契约核验。消费方负责策略接口、表格转换与持久化。SDK 不实现第二套撮合或组合模拟器，也不改变 Rust 引擎的算法。代码遵循本仓库 LGPL-3.0-only 许可，边界校验来自同一作者的 quant-platform 客户端。

测试仅使用合成数据。CI 构建 wheel 后，在独立环境中无依赖安装并运行测试。设置 `QUANT_ENGINE_BINARY` 可额外验证已选择的真实引擎程序。

[英文说明与调用示例](python-client.md)

CNY 逐日账本核验需要主机时区数据库包含 `Asia/Shanghai`，通常由系统 tzdata 提供。精简容器和 Windows 环境需要自行提供数据库。缺失时抛出带安装提示的 `EngineProtocolError`。
