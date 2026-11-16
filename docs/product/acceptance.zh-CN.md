# 交付验收与剩余工作

[English](acceptance.md)

先独立使用 Engine。合并后的 Python core 负责分钟与日频财务执行、恢复、有界规划及独立情景；
选股、训练和通用优化由调用方负责。双语教程与回放实验室也由本仓库交付。

## 源码组合

下面分别记录源码身份，不能用同一个包版本号代替：

| 组件 | 已审查的合并源码 | 范围 |
| --- | --- | --- |
| Engine 财务提供方 C | `ad0895f1c2015eb31bd364b40741b0f7cd6e0048` | Core/SDK 0.3.0；独立日频实现与期间分段财务闭包 |
| Engine 教程 | `062a820de013d824686e6b5f6582843618929d27`（PR 26） | Astro 教程与回放实验室；保留八个场景、21 组预设 |
| Platform 消费者 C | `c211d36167acf7a81fd0c034beb14317e2036b7e`（PR 200） | 调用 Engine 的兼容适配；研究仍在 Engine 之外 |
| Runtime 保留基线 | `01ed4c34f955ef6cd39d13aa073b6d61b610d321` | 既有接入；不表示拟议的 v9 消费者已切换 |

教程修订没有改变提供方的 `core/`、`python/`、Rust 源码或 Cargo 锁文件。
独立 wheel 验收记录实际构建提交和 SHA256，不给旧检查点重新命名。
按[安装说明](installation.zh-CN.md)，从同一个干净、经过审查的提交构建两个 wheel。
Core 支持 Python 3.12/3.13，独立 SDK 还支持 3.11；本次采用源码构建的 wheel，不要求发布到 PyPI。

## 2026-11-16 验收记录

从教程源码 `062a820` 新构建的 wheel，通过独立 SDK 3.11 和 Python 3.12/3.13
各八个核心可选依赖环境验收。完整核心测试每个解释器通过 957 项和三个子测试；
仅安装依赖的环境跳过 25 项 Rust/原生后端案例，另用真实后端分别通过全部 73 项
微观结构测试及两项 Rust 适配测试。最小日频环境各通过 319 项；SDK 对真实 Rust
可执行文件的 32 项测试通过。Rust 格式、clippy、测试与两个财务教程检查均通过。
线上基线的 228 个文件均与构建回执一致。这些测试范围有重叠，不能相加当作独立测试总数。

新构建 wheel 的 SHA256：

- Core：`57ed0dc2ede0bbc82dc6298965a5e56f05ffaba9308563f2509d5c2b50d89650`
- SDK：`bb5e3cd7322e2653729c17f856a1a1747f9b999275ce982a5374fd4e39ff616c`

## 复现财务检查

每个可选依赖组使用独立新环境，安装普通 wheel，从中立目录通过 `python -I -B` 执行。
`SOURCE` 是干净检出；`ENV`、`WHEELS`、`TASK_DATA` 是调用方选择的外部绝对路径。
数值依赖使用安装指南中的锁定基线。

| 检查 | 安装环境 | 验收内容 |
| --- | --- | --- |
| SDK/基础核心 | 仅 SDK / SDK + 无可选依赖的 core | `verify_installed_product.py --mode sdk` / `--mode base`；命名空间分离，不引入数值库或训练框架 |
| 分钟账户 | `[minute]` | `examples/product/minute_session.py`：两笔成交、净流入 50 元，恢复后的完整账本和摘要与连续执行相同 |
| 独立情景 | `[scenario]` | `examples/product/scenarios.py --output-root NEW_DIRECTORY`：无效案例单独失败；手算案例以 10 元买入 100 股，剩余现金为零 |
| 有界规划 | `[planning]` | `verify_installed_planning.py`：有限穷举得到 `(1, 1)`，支出 12，目标值 0.5 |
| 日频财务实现 | `[daily]` | `verify_installed_daily.py` 加 `core/tests/daily`：实际安装归属、财务、公司行为、费用、估值及产品回归 |
| Python 订单簿 | `[microstructure]` | `verify_installed_microstructure.py --native absent`：实际撮合行为，以及缺失原生扩展时明确失败 |
| 全部可选依赖 | `[all]` | 运行安装后的完整 `core/tests`；Rust 和原生扩展检查还需要真实可执行文件及扩展 |

上述 `verify_installed_*.py` 均位于 `SOURCE/project_tools/`。
它们导入已安装的 wheel，不依赖可编辑源码安装。例如：

```sh
cd "$TASK_DATA"
"$ENV/bin/python" -I -B "$SOURCE/examples/product/minute_session.py"
"$ENV/bin/python" -I -B "$SOURCE/project_tools/verify_installed_daily.py"
"$ENV/bin/python" -I -B -m pytest "$SOURCE/core/tests/daily" -q -p no:cacheprovider
```

分钟与日频命令应分别使用对应环境。既有 [Rust 目标权重教程](../tutorial.zh-CN.md)
验证下单数量、T+1 拒单、两笔成交、费用，以及逐日现金 + 持仓市值 = 净值；
最终净值 10197.8，佣金 2.2。较小的报价样例 `fixtures/roundtrip.json`
则为最终净值 10019.78、佣金 0.22；两者是不同案例。

命令、退出码、Python 与依赖版本、源码版本、wheel/可执行文件哈希和生成结果保存在独立任务数据目录。
跳过 Rust 或原生扩展测试，不能算对应后端通过。日频现金、费用或估值证据不可用时仍须标记不可用；
不能补零，也不能只凭最终净值相同认定完整财务等价。

## 核对发布

既有 Documentation 工作流仍是唯一发布入口，构建两种页面、检查路由与旧锚点，运行真实构建页面的浏览器测试。
main 部署成功后，用预期的完整合并提交核验：

```sh
python -B "$SOURCE/project_tools/verify_deployed_site.py" \
  --url https://runchengxie.github.io/quant-backtest-engine/ \
  --revision "$MERGED_REVISION" --output "$TASK_DATA/deployed.json"
```

工具核对构建回执中每个线上文件的字节数与 SHA256，下载结束后再次核对回执。
版本过旧、文件变化或发布混杂都会失败。这是对浏览器和 CI 验收的补充，
不替代交互测试，也不能独立认证构建中财务结论的真实性。

## 剩余关卡

- Runtime v9 的进程终止与任务准入验收，以及其他研究调用方，属于独立接入工作。
  完成验证前保留既有支持路径和完整固定的历史恢复环境。
- 朋友的 5000 万元案例仍缺原始目标与下单意图、提交和到达时钟、初始现金/持仓/锁定、费用条款和可执行行情。
  既有固定成交诊断不能证明真实容量。
- 真实冲击与滑点校准需要可追溯数据和识别方案；合成敏感性分析不能证明因果冲击。
- 预测缓存、多起点诊断、跨证券冲击和通用非凸求解器需要单独定义问题及验收标准，
  不属于本次保持原算术口径的迁移前置条件。
- tick 采集、券商接入、生产启用、兼容别名移除和早期任务资源清理不在本次交付范围。
