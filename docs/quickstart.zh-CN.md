# 快速开始

需要 Rust 1.99.0 或更新版本。上游固定为 NautilusTrader 0.66.0，Cargo.lock 固定传递依赖。
在仓库根目录执行：

```sh
cargo build --locked
cargo run --locked -- capabilities
cargo run --locked -- run fixtures/roundtrip.json
```

合成样例初始资金为 10000 美元，以 10 美元买入 10 股，再以 12 美元卖出。
买卖各收 10 个基点手续费，最终现金和净值为 10019.78，手续费合计 0.22。
数值由真实上游执行测试核对，仓库不包含私有策略或真实市场数据。

`run` 读取一份 JSON 文件，标准输出只有一份结果 JSON。错误写入标准错误，退出码非零。
任务成功不代表所有订单都成交，调用方必须检查订单状态。

Rust 调用方可以反序列化 `Request` 后调用同步的 `run(&request)`。
每次调用使用独立线程隔离上游线程局部状态，线程本身不是资源沙箱。
需要超时、取消和内存限制时，由 runtime 启动独立 CLI 进程。

完整 Rust 调用示例见[英文页面](quickstart.md#library)。
