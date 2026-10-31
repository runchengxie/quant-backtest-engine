# Runtime 接入

独立调用引擎不需要 runtime。需要持久化任务和资源管理时，使用
[quant-backtest-runtime v5](https://github.com/runchengxie/quant-backtest-runtime/blob/main/docs/development.zh-CN.md)。

1. 将审核过且已经合并的引擎构建到稳定发布目录。
2. 将 engine_request.v1 JSON 保存到 SHA-256 不可变输入目录。
3. 提交 nautilus.quote_market_orders 类型的 v5 任务，固定二进制哈希。
4. 由运维参数指定引擎绝对路径，请求中不能携带任意命令。
5. 读取校验过的 quant.engine_job_result.v1 结果并检查订单状态。

Python worker 独占任务数据库和结果发布。Rust 子进程继承地址空间限制，
取消和超时会终止并回收子进程，父进程硬杀使用 Linux parent-death SIGKILL 清理。
执行前固定已校验的文件句柄，路径原子更新不会替换本次执行的二进制。
这些机制不宣称可以安全运行不可信代码。

旧 v1–v4 任务协议和请求指纹保留不变。新引擎最终快照属于诊断证据，
不能标为完整每日执行账本。具体市场限制见[成交与估值假设](execution.zh-CN.md)。

## 逐日任务与 Python 分析

runtime [PR #39](https://github.com/runchengxie/quant-backtest-runtime/pull/39)
增加显式选择的 v6 `nautilus.session_replay`，接收 `engine_request.v2` 并发布
`quant.engine_job_result.v2`。发布前核对逐日资金和股份流动，并将估值绑定到请求报价。
任务成功仍然可能包含被拒订单。

platform 的[逐日结果客户端](https://github.com/runchengxie/quant-platform/pull/170)
校验所选可执行文件字节，将结果转换后用于 Python 分析。它保留
`execution_aware=False`，现有 Python 后端仍为默认路径。参见
[已测试版本组合](capabilities.zh-CN.md)和[目标权重回测教程](tutorial.zh-CN.md)。
