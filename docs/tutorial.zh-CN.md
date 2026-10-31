# 从目标权重到可核对的回测结果

这个合成示例调用 Rust 数量规划工具，把生成的订单交给基于上游的逐日回放引擎，
核对可以手算的结果，并保存完整输入输出。只需要 Python 3 和已构建的引擎，
无需数据源、模型库、平台服务或 runtime 数据库。

```sh
python3 project_tools/tutorial.py \
  --engine /absolute/path/to/quant-backtest-engine \
  --output /absolute/external/path/new-tutorial-run
```

输出必须是源码目录之外的新目录。引擎失败或经济结果与预期不一致时，脚本会失败。
CI 会用实际构建的 CLI 执行这个教程。

## 示例做了什么

假设模型已经给出 10% 的目标权重。这里不训练模型，也不证明策略有效。
用于数量规划的参考价 10 是合成输入，其可用时间早于第一笔可成交报价。

| 步骤 | 计算或实际结果 |
| --- | --- |
| 规划数量 | 人民币 10,000 × 10% ÷ 10 = 100 股；配置每手 100 股 |
| 首次成交 | 以 10 买入 100 股，费用 1，现金剩余 8,999 |
| 首日估值 | 100 × 中间价 11 = 1,100；净资产 10,099 |
| 当日卖出 | 配置的 T+1 规则拒绝订单，`rejections` 保留原因 |
| 下一交易日卖出 | 以 12 卖出 100 股，费用 1.2；最终现金及净资产 10,197.8 |

脚本用数量规划工具的实际输出替换示例中的第一笔买单。后续卖单和报价来自合成输入。
它会核对两天的账目、总费用 2.2、两笔实际成交及被拒订单。
保存的 JSON 包含可执行文件 SHA-256、规划输入输出和回测输入输出。
可以在 `engine_result.json` 查看成交、订单状态、拒单原因和 `daily_ledger`。
任务完成不代表所有订单都成交。

## 接下来从哪里调用

- 本地研究：直接使用 CLI 或 Rust 库。
- Python 分析：显式使用 platform 的 `EngineClient`，校验二进制摘要并转换为 `CanonicalBacktestResult`。
- 持久化批量任务：将保存的 `engine_request.json` 发布为不可变产物，提交 runtime v6 的
  `nautilus.session_replay` 任务。runtime 负责进程限制、状态和结果发布，见[接入说明](runtime.zh-CN.md)。

迁移实际调用方之前，先看[能力矩阵](capabilities.zh-CN.md)和[正确性案例](correctness.zh-CN.md)。
示例没有覆盖公司行动、节假日、日成交量参与率及交易所税费规则，这些工作流继续保留现有 Python 后端。
