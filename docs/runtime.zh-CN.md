# Runtime 接入

独立调用引擎不需要 runtime。需要持久化任务和资源管理时，使用
[quant-backtest-runtime v5](https://github.com/runchengxie/quant-backtest-runtime/blob/main/docs/development.zh-CN.md)。

1. 将审核过且已经合并的引擎构建到稳定发布目录。
2. 将 engine_request.v1 JSON 保存到 SHA-256 不可变输入目录。
3. 提交 nautilus.quote_market_orders 类型的 v5 任务，固定二进制哈希。
4. 由运维参数指定引擎绝对路径，请求中不能携带任意命令。
5. 读取校验过的 quant.engine_job_result.v1 结果并检查订单状态。

Python worker 负责写任务数据库和发布结果。它启动 Rust 子进程，并把内存地址空间限制传给子进程。
任务取消或超时时，worker 会终止并回收子进程。父进程被强制杀死时，Linux 会通过 parent-death SIGKILL 终止子进程。
运行前，worker 检查引擎文件并保持文件描述符打开。即使部署程序随后替换同一路径，
本次任务仍运行原先检查过的文件。
这些机制不宣称可以安全运行不可信代码。

旧 v1 到 v4 任务协议和请求指纹保留不变。新引擎最终快照属于诊断证据，
不能标为完整每日执行账本。具体市场限制见[成交与估值假设](execution.zh-CN.md)。

## 静态预检

`validate REQUEST.json` 和 `validate -` 复用 `Request` 的解析与 `Request::validate`，
只检查请求，不运行回测。输入最多 1 MiB，成功后输出 `engine_validation.v1`，
包含 `request_schema=engine_request.v1`、`validator_version=1`、`valid=true` 和
原始输入的 `input_sha256`。`capabilities` 单独声明验证器版本，模拟能力列表保持不变。
无效请求、格式错误或超限返回退出码 2，标准输出为空。文件和内部故障返回 1。

runtime 预检通过已校验摘要并保持打开的描述符启动验证器，限制运行时间和输出，核验回执
后才信任结果。部署文件必须保持不可原地修改。描述符能防止路径替换，却不能阻止对
同一可执行文件的原地写入。已有 `run`、`size` 和会话接口保持兼容。

## 逐日任务与 Python 分析

runtime [PR #39](https://github.com/runchengxie/quant-backtest-runtime/pull/39)
增加显式选择的 v6 `nautilus.session_replay`，接收 `engine_request.v2` 并发布
`quant.engine_job_result.v2`。发布前核对逐日资金和股份流动，并将估值绑定到请求报价。
任务成功仍然可能包含被拒订单。

platform 的[逐日结果客户端](https://github.com/runchengxie/quant-platform/pull/170)
校验所选可执行文件字节，将结果转换后用于 Python 分析。它保留
`execution_aware=False`，现有 Python 后端仍为默认路径。参见
[已测试版本组合](capabilities.zh-CN.md)和[目标权重回测教程](tutorial.zh-CN.md)。
