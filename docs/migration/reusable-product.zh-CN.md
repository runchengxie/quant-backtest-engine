# 可复用产品的归属与迁移关卡

[English](reusable-product.md)

Core 0.3.0 源码新增完整独立日频财务实现及显式 python.daily 后端，分钟、规划与情景
核算继续保留。SDK 0.3.0 保持标准库命名空间。提供方 B 和 Platform B 已按归属登记表
记录的版本发布；提供方 C 审核、合并、确切合并版 wheel 及 Platform C 切换仍待完成。
请阅读[安装](../product/installation.zh-CN.md)、[后端边界](../product/backends.zh-CN.md)
和[日频输入](../product/daily-inputs.zh-CN.md)。源码实现与发布、消费者验收分别记录。

## 当前实现与待切换消费者

| 组件 | 当前实现 | 发布与后续归属关卡 |
| --- | --- | --- |
| Engine Rust | 0.2.0，NautilusTrader 0.66.0；原生报价、会话与 CLI 语义不变 | Python 能力不扩展 Rust；成交与记账仍以上游为准 |
| Engine SDK | `quant-backtest-engine-client` 0.3.0；`quant_backtest_engine`；Python ≥3.11；标准库产品契约 | 固定确切已审查源码及已验证 wheel；SDK 基础导入不依赖 core |
| 可选 Engine core | Core 0.3.0 源码；Python 3.12/3.13；独立日频、分钟、规划及情景核算 | 提供方 C 审核、合并、确切合并产物待完成 |
| Platform | 保留消费者 B | 消费者 C（Task 15）等待提供方 C 合并验证；研究及发布仍归 Platform |
| Runtime | 保留既有 0.1.0 及 v1–v8 路径 | 可选新增 v9/0.2.0 消费者须等待提供方合并及运行管理验收 |

Core 基础包依赖 SDK `>=0.3.0,<0.4`；仓库构建与消费者固定确切的已合并 VCS 修订
或已验证 wheel 哈希。本地调用必须显式选择。不要求发布到 PyPI；包版本不能替代源码、
可执行文件、依赖、契约和检查点身份。

## 历史 M0 基线 — 2026-11-09

M0 时，Engine Rust 为 0.2.0，SDK 为 0.2.0，Platform 为 0.0.1，Runtime 为 0.1.0。
当时尚未迁入 Python 财务实现，可选 core 尚未实现或发布。这份注明日期的基线解释原始
清单，不代表上文所述的当前提供方 A 实现状态。

清点的源码修订为 Engine
[`c65548a`](https://github.com/runchengxie/quant-backtest-engine/tree/c65548a4ee1e938125cce1edbcc282c760c4c8f2)、
Platform [`7a618bd`](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355)
和 Runtime [`01ed4c3`](https://github.com/runchengxie/quant-backtest-runtime/tree/01ed4c34f955ef6cd39d13aa073b6d61b610d321)。
设计 PR 20 已合并为
[`c5cbb88`](https://github.com/runchengxie/quant-backtest-engine/commit/c5cbb885a6abb90b7cc6b41e111be71bd8b41069)。
这些是历史源码观察记录，不是当前发布版本或线上部署的认证。

## 每次运行只有一个财务归属方

每次运行只有一个财务归属方，不同场景使用独立账户和状态。
Rust 继续使用 Nautilus 上游记账；可选 Python 分钟提供方负责已经迁入的财务状态。
完成后的 Engine 运行时不导入 Platform、Runtime 或私有研究代码。
临时兼容提供方必须由调用方显式传入、登记移除关卡，不能通过独立运行验收。

Engine 获准承接确定性会话与检查点、执行成本和冲击、显式输入的市场路径、
回测专用规划、资金预留、分配与结果证据。分钟依赖闭包一起迁移：分钟与会话、
检查点、冲击、数量锁、撮合状态与校验、资金流、公司行为和估值事件。
有状态类只能随整个闭包一起切换。

通用因子与风险估计、模型训练、选股、通用有符号及稀疏优化、研究准入与成果发布仍归 Platform。
Engine 接受其显式输入或公开优化器回调。日频执行必须先分离选股、研究指标、
行情供应商日历获取和成果发布。确定性微观结构撮合必须摆脱训练模块的提前导入；
其可选 PyO3 加速扩展与 Nautilus 是不同后端。
Runtime 保留队列、任务与尝试身份、租约、进程监督、资源限制、持久化准入和发布。
Engine 财务检查点不接管 Runtime 数据库职责。

## 关卡与可执行验收

| 阶段 | 交付与停止条件 |
| --- | --- |
| M0 | 固定源码、别名、路由和调用方清单；独立审查本归属记录 |
| M1 | SDK 契约与可选 core 运行器；显式后端、精确时钟，保持旧 SDK/CLI 语义 |
| M2–M3 / A | 迁移叶子机制与完整分钟会话；独立安装 wheel，验证完整账本与恢复一致性，配齐双语文档，再切换 Platform A |
| M4 / B | 撮合、账户反馈、外部优化器协议、有界规划和独立场景；验证可选依赖、预先备资和实际成交证据，再切换 Platform B |
| M5 / C | 中立日频输入、日历与汇总，再迁移完整财务图和黄金账本；Platform C 保留目标构造与发布编排 |
| M6 / R | 固定新增 Runtime 提供方并真实杀进程验证准入；代表性调用方按确切已合并提供方版本验证 |
| M7 / T 与交付 | 保留并重新导出八场景教程，再验证安装组合、双语线上页面并只清理本任务资源 |

每一阶段先交付实现、测试、英文权威文档与中文对应页，再切换调用方。
提供方先合并并生成已验证产物。迁移时保持算术、舍入和模型语义；新增能力另做一致性验收。
调用方关卡失败时保留旧路径和默认行为，或使用明确固定的完整旧版本环境。

## 登记表与历史路由

[机器可读登记表](reusable-ownership.json)使用 `engine-ownership.v1`，记录各模块或符号的
旧归属与计划归属、提供方版本、源码修订、旧新双语 URL 与锚点、兼容路径、阶段与关卡、
移除条件和具名可执行验收命令。它还记录源码与文档簇、已清点的全部公开旧别名、
保留或拆分的归属，以及公开调用接口形态。私有文件的确切路径只留在私有任务数据中；
登记不授权修改无关调用方。

`status: planned` 允许空源码修订和未来的文件、测试、路由。
`status: implemented` 要求真实完整且经审查的源码提交存在于 Git 中，
提供方文件同时存在于该修订和当前树中，并有实际的 Engine 中英文文档。
发布与部署可用性在提供方合并后单独记录，不能用占位哈希或自引用提交暗示已可用。
校验器不认证财务语义、审查批准或线上 URL。

历史语言必须明确声明。例如 Platform 的 `guides/minute-execution.en/` 是英文，
`guides/minute-execution/` 是中文；目标分别是 Engine 的
`guides/minute-execution/` 和 `guides/minute-execution.zh-CN/`。
保留 `.en`、`.en-US`、无后缀中文和 `.zh-CN` 的旧拼写。
多个符号可以共享同一旧页和同一目标；映射冲突则失败。
原来没有中文页的来源应补新中文页，不能虚构历史中文 URL。
提供方发布后，Platform 旧页改为语言正确的简短迁移说明，并保留稳定锚点；
旧源码链接和注明日期的验收记录仍指向原修订。

兼容别名至少保留**两个次版本周期，且所有已登记的受支持调用方均已迁移**。
删除还需要发布说明、文档链接迁移和测试。静态导入次数不代表线上调用方或可退役范围。
调用方群组包括分钟与公司行为、账户恢复、待成交反馈、有界规划、日频与持仓适配、
Runtime 客户端、独立信号验收持仓重放、市场研究的分钟/日频/公司行为，以及工作台导入检查。
每组切换前都需实际验证，或明确固定完整旧版本恢复路径。
内部分钟导入还需要受支持的公开替代接口。

旧检查点留在其原有确切提供方、版本及完整 Runtime/Go 可执行文件与依赖环境中。
不承诺跨归属方或跨后端透明恢复。财务步骤失败后，不能再向已失效的归属方请求新检查点。

## 保留已审查教程

[PR 19](https://github.com/runchengxie/quant-backtest-engine/pull/19) 的
[`4820af3`](https://github.com/runchengxie/quant-backtest-engine/tree/4820af3b82940e7697cb8c92154315b1d59ee23d)
仍是保留的、已审查但尚未合并的源码。八个场景标识全部保留：
`selection`、`paths`、`cost`、`impact`、`lots`、`flow`、`book`、`risk`。
同时保留双语目录与页面、导出器及辅助源码和哈希、精确时钟投影、无 JavaScript 财务表格、
重放/DOM/夹具测试，以及许可和源码历史。

现有财务夹具绑定真实的 Platform 归属方，不能改标签冒充新实现的 Engine 机制。
每次迁移都需更新类型调用白名单、类和模块绑定、归属标签、源码修订与 URL，
以及所有执行过的辅助文件哈希；只从干净的已合并提供方和锁定可选环境重新导出，保留旧来源记录。
风险与空信号教学可以继续使用 Platform 这一独立可选分析归属方。
集成时，把仅为哈希 Runtime 文档而强制需要的检出改为可选的版本化引用。
浏览器只展示导出的真实归属方结果，不计算另一套财务模型。
本次 M0 修改不触碰教程分支或工作树。

## 校验本记录

```sh
python -m unittest project_tools.test_reusable_ownership -v
python project_tools/check_reusable_ownership.py
mkdocs build --strict --site-dir "$TASK_DATA/site"
python project_tools/check_docs.py --site-dir "$TASK_DATA/site"
git diff --check
```

使用锁定文档环境，把站点输出放在外部任务数据目录。
校验器只读，不执行登记的验收命令。后续财务关卡见已批准的实施计划
`docs/superpowers/plans/2026-11-09-reusable-backtest-product-implementation.md`。
公开示例只用合成输入；本任务不包含券商连接与下单、生产配置、调度器、真实成本校准或新增数据采集。
