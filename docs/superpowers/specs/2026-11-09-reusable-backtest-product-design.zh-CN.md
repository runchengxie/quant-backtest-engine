# 可复用回测产品的架构与分阶段迁移设计

本文为 2026-11-09 提案，供用户审阅。用户已选择“Engine 成为独立可复用回测产品，保留 Rust 后端并纳入可选 Python 实现”的方向。本文把组件边界、接口、迁移和验收要求具体化；文档发布本身不代表代码迁移已获批准或已经完成。

用户已于 2026-11-09 指示执行这份具体设计。上面的提案状态记录审阅时点；现已授权按分阶段计划及其兼容验证、独立审查要求实施，生产和券商操作边界保持不变。

[English](2026-11-09-reusable-backtest-product-design.md)

## 1. 要达到什么效果

新项目按需要安装 Engine，提供行情、目标或订单及明确的策略输入，即可回测并读取结果，不必安装 Platform、Runtime 或私有研究项目。

简单的 Rust 订单回放保持轻量；较完整的 Python 财务会话、情景和执行规划作为 Engine 管理的可选包。Runtime 供需要任务队列和可靠运行的项目选用。迁移是否成功，要用独立安装后的实际回测证明，不能只检查导入成功或网页换了位置。

| 方案 | 代价与限制 | 选择 |
| --- | --- | --- |
| 改名、搬文件，或让 Engine 包装调用 Platform | 很快有统一外观，但独立安装和职责问题仍存在，可能形成循环依赖 | 只允许作为明确登记、可退出的过渡适配 |
| 全部用 Rust 重写 | 同时改变语言、核算和模型，上游也未覆盖全部 Python 规则 | 作为后续逐项实现和验证 |
| Engine 统一产品接口，分批迁入 Python 实现，明确选择后端 | 保留已验证行为，逐步实现独立安装和统一归属 | 已选择的方向；下述具体默认方案待审阅 |

每批代码及其说明、示例、测试和中英文文档一起交付。

## 2. 当前实现的事实

| 组件 | 本次核对版本 | 已有范围 |
| --- | --- | --- |
| Engine | c65548a4ee1e938125cce1edbcc282c760c4c8f2 | Rust 库与 CLI；订单报价 v1、逐日会话 v2、数量规划和会话流；固定 Nautilus 0.66.0 |
| Platform | 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355 | Python 分钟财务会话、冲击、路径、执行规划、成本与分配，以及更广泛的因子和研究工具 |
| Runtime | 01ed4c34f955ef6cd39d13aa073b6d61b610d321 | Go 任务生命周期和持久化接纳、固定 Python 财务适配器、v1 至 v8 任务 |
| 未合并教程 | Engine PR 19，4820af3b82940e7697cb8c92154315b1d59ee23d | 八个双语场景、原实现导出器、无 JS 完整数值表；源码审查通过，尚未成为已发布产品功能 |

现有 quant-backtest-engine-client 使用 quant_backtest_engine 命名空间，支持 Python 3.11 起，运行依赖为空。SDK 和 Runtime 的两套验证器都检查固定 Nautilus 后端及版本。Rust 静态验证器目前只验证报价请求 v1；Rust 会话流没有财务快照恢复。已有公司行动对照还记录了上游持仓成本基础调整不一致的情况，统一接口不能补出缺失的经济能力。

Platform 要求 Python 3.12 起。ticknet 顶层初始化会导入训练模块，纯撮合也可能带入训练依赖。MinuteSession 依赖分钟执行、公司行动、估值和资金流的一组内部实现；子组合分配又依赖执行完整性分析工具。独立迁移必须处理这些实际依赖。

Runtime v8 绑定安装的 Platform 精确版本、财务源码、配置、事件带和依赖版本。源码搬家会改变身份；旧检查点不能自动被当成新 Engine 提供者的检查点。

核对入口包括 Engine 的 src/{contract,session_contract,validation,sizing,session_stream}.rs、Python SDK；Platform 的 quant_platform/{backtest,_portfolio,portfolio,analytics}；Runtime 的 financial_sessions、financial_session_adapter、engine_sessions_protocol 及 Go protocol/app/store 实现。


源码依据见 [Engine](https://github.com/runchengxie/quant-backtest-engine/tree/c65548a4ee1e938125cce1edbcc282c760c4c8f2), [Platform](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355), [Runtime](https://github.com/runchengxie/quant-backtest-runtime/tree/01ed4c34f955ef6cd39d13aa073b6d61b610d321), [保留的教程 PR 19](https://github.com/runchengxie/quant-backtest-engine/pull/19).

## 3. 目标职责和依赖方向

~~~mermaid
flowchart LR
    A[其他项目] --> E[Engine 公开 API / CLI / SDK]
    P[Platform 因子研究与分析] --> E
    R[可选 Runtime 任务管理] --> E
    D[调用方提供行情与模型产物] --> E
    E --> C[契约 / 能力声明 / 结果]
    E --> S[情景与执行规划]
    E --> B[明确选择执行后端]
    B --> N[Rust / Nautilus]
    B --> Y[可选 Engine Python 财务后端]
~~~

Engine 负责通用回测契约、确定性的执行和账户状态、执行成本与冲击、情景运行及回测专用规划。一次运行只有一个财务核算主体，不同情景各有独立账户和状态。

Platform 保留因子、特征、训练、通用因子风险估计、事后统计风险校准、组合研究和分析，通过公开接口提供预测、风险快照或规划器，并消费 Engine 结果。私有策略、参数、选择与晋升规则以及权威研究试验登记库留在研究层。

Runtime 保留任务和尝试身份、租约令牌、队列、进程和资源控制、文件写入与同步、数据库接纳、最终发布。Engine 提供财务状态，直接运行和恢复无需 Runtime 数据库。

完成后的 Engine 在运行时不导入 Platform、Runtime 或私有研究项目。过渡期可以由调用方明确注册兼容后端，但必须注明中间依赖和退出条件，且不能拿这种环境证明 Engine 已经独立。

## 4. 安装包与依赖

下列新包名是设计占位，发布前检查最终名称。不同 wheel 不得安装重叠的模块文件。

| 安装方式 | 归属及依赖 | 验收 |
| --- | --- | --- |
| 原有传输 SDK | 保留 quant-backtest-engine-client / quant_backtest_engine；Python 3.11 起、标准库 | 原有数量规划和会话调用兼容 |
| Rust 执行 | 原有 Engine 可执行文件和库，保留现有实验发行平台限制 | 订单、会话、CLI 与上游核算对照 |
| 产品运行入口和 Python 参考模块 | 新增 Engine 包，暂称 quant-backtest-core / quant_backtest_core；初期 Python 3.12 起；基础仅依赖轻量 SDK，分钟、路径、规划依赖按 extra 安装 | 基础导入不引入科学计算或训练栈；分钟 extra 不安装 Platform、Runtime、私有研究包也能运行财务会话 |
| 可选规划与情景 | 独立声明数值库、求解器等依赖 | 基础 SDK 和普通文档构建不引入求解器或训练栈 |
| 可选微观结构 | 从训练包初始化中分离盘口和撮合；原生加速明确选择 | 不安装 Torch 也能使用纯撮合；保留参考实现对照 |
| Runtime 集成 | 独立、可选的调用方 | 普通回测无需队列、数据库或服务 |

保留现有 SDK 的包及命名空间归属。Python 核心采用独立命名空间，避免两个 wheel 写入同一目录。产品接口可延迟加载可选本地能力，基础安装和导入仍保持独立。

产品运行清单、结果 DTO 和能力描述符作为现有 SDK 的新增标准库模块，由核心包依赖。SDK 基础导入不加载核心，可选本地产品调用要明确启用。完整本地运行器和暂称 quant-backtest 的 CLI 位于新核心包；原 Rust 可执行文件继续作为底层后端与工具，原命令不变。完整回测使用产品运行器，现有简单调用仍可使用 SDK 加 Rust。暂称 run-manifest 的新操作属于产品 CLI，不悄悄改变原 Rust 命令含义。

首先认证现有 Linux 目标；Python 核心分别验证 3.12、3.13，SDK 保留 3.11 支持。不能把当前 main、可下载可执行文件、安装包版本混为一谈，也不提前宣称跨平台支持。

## 5. 统一接口和契约

保留现有 run、size、capabilities、session-capabilities、validate、session-stream 的含义。新增独立版本的产品操作，暂称 run-manifest；该名称是提议，尚未实现。

本地库和 CLI 使用同一运行清单，至少包含。

- 产品契约版本、明确的后端 ID、所需能力及模型和结果版本。
- 输入产物或小型内联数据及字节哈希，币种、原始或复权股数基准、日历、时区和单位。
- 信息可见、决策、入场、生效、报告与估值时间；初始账户及完整状态。
- 全部解析后的执行、费用、冲击设置和外部事件带，空事件带也要明确提供。
- 策略、预测和风险输入的来源、可见时间及状态版本；情景类型、随机种子和变化规则。
- 预测固定或随路径重算的方式、输出位置，以及实际提供者和配置的完整身份。

行情接入、认证和私有配置由调用方负责。Engine 不自动读取用户研究配置或抓取受权限保护的数据。公开样例使用合成输入；Runtime 继续执行自己的任务产物和资源边界。

产品传输使用明确的金额十进制字符串，以及能完整表示 UTC 纳秒的字符串。现有 v1/v2 整数时间戳协议保持不变，通过精确适配转换，不经过 JavaScript 浮点数。原实现使用浮点计算时，必须保留其数值和舍入口径；改成字符串传输不会使运算自动变成十进制精确计算。

后端描述符分别声明后端、实现和源码、依赖、请求和结果版本、检查点版本、能力、单位及限制。调用方明确选择后端。缺少可选包或不支持所需规则，在开始财务执行前报错。产品的能力集合不代表每个后端都具备，不能静默从 Rust 切换 Python。

请求只能选择经过审阅的固定提供者 ID，不能指定任意导入路径、命令或序列化代码。受信任的本地程序可传入明确构造的策略对象；远程可恢复任务采用登记的策略工厂和版本化状态格式。

## 6. 核算主体和结果

Python 后端初期保留迁出的财务实现；Rust 后端继续依赖上游核算。不另造一个现金账本来补上游不支持的行为。

统一结果包说明支持哪些经济证据，并显式表示无法提供的内容。

- 订单意图、接纳、拒绝、取消、实际成交和现金费用。
- 经济账户与持仓，可用、锁定、可卖、预留数量，以及延迟送达后的可见状态。
- 公司行动权益、应收款、支付与释放、估值、外部资金流。
- 净值与收益口径、标记时效、残余持仓和未知的完全变现财富。
- 情景、输入、提供者、配置身份，以及尝试、完成、失败和部分证据。
- 原后端结果引用和版本化规范转换记录。

未知不能填成零，也不能用空表冒充已经支持的账本。运行完成不等于订单全部成交或策略通过研究准入。目前能力有限的 Engine 适配器也不能直接被标成完整 execution-aware 结果。

成交价中的冲击只体现一次；现金费用只扣一次；机会短缺用于比较，不重复扣款。入金、出金与盈亏分开；未成交卖单的预计所得不能支付买单。

现有 research-contracts 包物理上位于 Platform，还包含晋升与发布概念。优先定义 Engine 最小执行时钟和结果 DTO（跨组件传递的数据结构），由 Platform 适配；也可使用已独立发布且验证过依赖闭包的中立包。不能为了检查时钟而要求 Platform 源码检出或迁入研究准入规则。

所需执行完整性工具应迁到 Engine 较低层结果接口，消除对 Platform 分析内部实现的反向依赖。通用风险校准统计仍由 Platform 负责。

## 7. 成本、规划、情景和策略

成本分别提供估计与实际扣款接口，说明币种、方向、生效时间、股数或金额基准、最低费、税和舍入。每个后端列出支持范围，估计与实际费用需要勾稽，不能假设永远相等。

冲击保留单位、衰减时钟、不衰减敏感性假设、模型状态及检查点身份。不能把非零永久或跨证券冲击自动称为真实校准结果；Rust 支持另行实现验收。

执行规划读取真实现金、预留、可卖量、锁定、容量及实际成交反馈。保留暂态冲击规划器的保守现金可行域，以及有限整数求解器的预备资金域、搜索上限和最优性范围。因子协方差估计和通用研究优化器继续由 Platform 负责，除非后续有明确独立需求再提取。

同一行情下改变执行条件，与改变外部市场路径是两种实验，都要使用独立账户。外部路径变化后，受影响的特征和预测必须通过调用方接口重算；否则明确标为固定预测敏感性实验。不能沿用原历史预测却声称检验了完整的另一段研究历史。

初期提供本地顺序情景运行即可；Runtime 以后可调度同一清单，不在 Engine 再建调度器、研究登记库或私有训练流程。全部尝试和失败要保留，固定复现不增加独立市场观察。

## 8. 会话和恢复兼容

公开会话工厂提供 step、不可变观察与报告、checkpoint、带外部预期输入和模型身份的 restore，以及 finish。完整状态包括现金、持仓、权益、未结订单和报告、预留、锁定、冲击、策略、游标与去重信息。

财务步骤失败后，该对象失效；保留原异常和最后成功的检查点，不再向失效对象索要新检查点。缺失或不支持的事件带明确拒绝。

三类恢复必须分开。

1. Rust 会话流。提供临时报告与前缀验证，不导入财务快照。
2. Runtime v7。保留原排队会话的终止失败语义。
3. Runtime v8。从已接纳、源码绑定的失败前驱创建新令牌拥有的后继任务。

Engine 新包采用新增提供者、绑定和任务协议路径；原 SDK 和 Runtime v1 至 v8 的语义、严格身份校验及黄金结果保持有效，不能放宽 Nautilus 检查来接受 Python 结果。

旧检查点仍由原来固定的提供者和发行环境读取。跨生产者、跨后端恢复默认不支持，除非单独的显式转换器通过完整状态和经济等价验证。只保留 minute-session.v2 这个名字不构成兼容迁移。

原固定环境包含完整 Runtime、Go 可执行文件及依赖，不仅是一份旧 Platform 安装包。这里承诺明确的旧版恢复和复现路径，不承诺更换 worker 后可以透明恢复。运维切换只向 worker 分配其支持的任务、提供者和绑定版本，旧 worker 不能直接抢领新版队列。无法证明安全共存时，使用隔离的旧版恢复环境并保留原发行版本。本次设计任务不修改运行中的任务库或生产部署。

Engine 管财务状态；Runtime 继续管候选文件写入、同步、重命名、数据库接纳、尝试隔离和发布。源码兼容不能绕过持久化和所有权控制。

## 9. 分批迁移与停止条件

每批都包括代码、测试、英文说明及中文对照。先发布或合并提供者，再切换消费者；验证实际组合版本。

| 阶段 | 交付 | 继续前的验收 |
| --- | --- | --- |
| M0 设计批准 | 决定边界、包、接口和文档清单，保留 PR 19 | 用户审阅具体设计，再写任务实施计划及更新相应规则 |
| M1 产品接口 | 能力、运行清单、结果及明确后端和会话接口；原 API 不变 | 跨语言契约、缺包与不支持能力拒绝、旧 SDK/CLI 兼容 |
| M2 独立机制 | 路径、执行成本与冲击，以及必要的中立完整性工具 | 安装包独立测试、来源和配置身份、手算与旧新对照，无反向依赖 |
| M3 财务实现组 | 分钟会话、账户、公司行动、估值、资金流、锁定与延迟状态；分离撮合和训练初始化 | 每事件边界恢复、现金股数费用权益守恒、估值未知和不依赖训练栈 |
| M4 规划与情景 | 有界执行规划、实际成交分配、有限退出、独立情景和外部策略接口 | 预备资金、容量、反馈、依赖闭包及失败留痕 |
| M5 日级执行解耦 | 分离选股、研究指标、供应商日历和发布后，迁入日级成交与核算 | 完整日账、日期费用与公司行动，明确目标和日历，无供应商登录依赖 |
| M6 调用方和 Runtime | Platform 转发新 owner；Runtime 新固定提供者；独立消费样例 | 精确依赖组合、真实进程终止验收、旧 v1 至 v8 保持有效 |
| M7 产品交付 | Engine 文档、教程、发行和 Platform 兼容页、Runtime 运维说明 | 双语实浏览器、移动布局、主题、键盘、减少动态效果、导航及部署版本核对，最后清理任务资源 |
| 后续 Rust 对齐 | 按上游支持逐项增加成本、冲击、公司行动或状态恢复 | 每个能力独立验收，不从 Python 支持推断 Rust 支持 |

搬迁与算术、舍入或模型改写分开。新增经济行为另有版本与测试。先选择最小闭合依赖，再扩大范围。

同一迁移版本内的兼容转发指向同一个新类对象，不代表旧版本检查点或序列化类可跨版本通用。旧产物继续使用原固定发行环境。

旧接口至少保留两个次版本发布周期，并等待所有已登记受支持调用方完成迁移。删除需要发布说明、文档迁移和测试，不能只看目录年龄。调用方检查失败时保留旧路径与默认值，修复提供者或使用旧版本，不强行切换。

## 10. 文档与代码共同迁移

每个转移的公开符号都登记。旧模块、新 owner 与版本、旧文档 URL、新中英文 URL、兼容适配、退出条件和可执行验收。

Engine 的权威说明覆盖产品与安装、后端能力、契约和时钟、成本冲击、财务会话与事件、有限规划、情景含义、恢复、结果解释和独立项目教程。Platform 保留因子、模型、风险和分析说明；迁出的机制页在新代码及文档发布后改为简短兼容入口，保留旧地址和语言，不维持两套完整正文。

Runtime 保留进程、资源、任务、持久化接纳和发布说明，示例只在对应提供者真实切换后更新。严格区分前缀重放、快照恢复、main 上功能及已发行二进制能力。

历史源码链接、日期化验收和实验收据继续绑定原版本；增加当前解释和新 owner 链接，不把旧结果改写成新包运行所得。

保留 PR 19 的八场景教程、导出器、精确时间戳、翻译目录、无 JS 表格和测试，并在实施时有意识地整合。迁移完成前，场景仍标明真实实现归属。此前教程放 Platform 的选择，在新的统一 Engine 产品方向下重新规划；页面位置和能力声明随批准后的边界调整。本次设计不会丢弃已审查成果。

README、API、示例、能力和发行矩阵、导航、语言登记、源码链接、文档检查及相关 AGENTS.md 在同批更新。公开资料不包含私人聊天、账户或策略输入。

### 实际代码与文档对应表

M3 初始依赖组为 Platform 的 quant_platform/backtest/{minute,minute_session,_minute_checkpoint,impact,quantity_locks}.py，以及 _portfolio/{minute_execution,_minute_state,_minute_validation,capital_flows,corporate_actions,valuation_events}.py。兼容转发必须保留类身份。account-events、paper-account、checkpoints 与 pending-allocation 的优化器接口按 M4 单独梳理，不能因此迁入整套通用研究优化器。

日级 reporting 目前会导入研究统计，持仓回放混有选股，日历也可能抓供应商数据。M5 先定义执行摘要、明确目标和调用方提供的日历，再搬财务实现；因子 IC、top-k 选股和供应商认证留在各自原有职责层。

| 当前 Platform 文档 | 对应迁移后归属 |
| --- | --- |
| backtest/market-paths 中英文 | Engine 同名路径说明，随 M2 |
| backtest/minute-session；guides/minute-execution 英文与中文原文 | Engine 对应会话、分钟执行说明，随 M3 |
| transaction-cost-evidence；cost-scope 分析 | Engine 执行成本证据说明，随 M2/M4，保留统计限制 |
| concepts/impact-planning、discrete-inventory 中英文 | Engine 可选执行规划，随 M4 |
| sleeve-allocation、execution-integrity、paper-account、account-feedback、capital/reconciliation | Engine 分配、账户和证据说明，随 M3/M4；补缺失中文入口 |
| pending-allocation 和 signed/sparse 优化说明 | 执行预留接口进 Engine，通用优化器说明留 Platform |
| 日级执行、顺序执行、公司行动、日期费用、结果说明 | M5 后由 Engine 解释机制，Platform 保留构造目标和分析流程 |
| risk-calibration、因子风险和模型说明 | Platform 保持权威 owner，Engine 外链引用 |
| Platform 安装、公开 API、入口、概览及归属图 | 留 Platform，更新消费者和兼容入口 |
| Runtime 财务会话、流式会话、排队会话与归属说明 | 留 Runtime，随实际提供者切换更新 |

对 .en、.en-US、无后缀中文和 .zh-CN 建立明确路由映射，不能把历史无后缀页面一律当英文。历史版本矩阵旁新增当前已测组合，不覆盖旧结果。

PR 19 导出器目前允许 quant_platform 类型，并记录相应类和模块源码哈希。每批迁移同步更新类型允许表、owner 版本和 URL、导出器及全部执行源码哈希，从干净且已合并的提供者重新生成。旧样例身份作为历史证据保留。当前强制 Runtime 检出只为哈希一份文档，应改为可选的版本化文档引用；风险或无信号教学场景仍可把 Platform 标为独立分析 owner，不使 Engine 的运行依赖于它。

## 10.1 静态产品前端与保留的技术参考

`web/` 使用 Astro 静态输出，React 是唯一的客户端组件框架。Astro 在构建时生成产品导航、解释、证据边界和完整结果表；React islands 负责事件回放、同步图表和预设控制。普通构建读取已提交的公开合成数据产物，不需要常驻服务器、券商、Platform 源码或 Runtime 服务。先验证兼容性，再在 `web/package.json` 和锁文件中固定依赖、Node 和包管理器版本，不凭记忆指定框架主版本。

MkDocs 继续生成现有技术参考和保留的八场景教程。本次选择 Astro 是为了组件和交互状态易于维护，并非认为 MkDocs 无法执行 JavaScript。不同时迁移到 Starlight，也不把所有旧页面统一搬到 `/docs/`。静态交互边界参照 [Astro islands](https://docs.astro.build/en/concepts/islands/)，部署参数参照 [官方 Pages 指南](https://docs.astro.build/en/guides/deploy/github/)；以下拼装规则属于本项目设计，并非 Astro 自带功能。

## 10.2 首页、路由与静态资源的归属

以下路径均相对站点基础路径 `/quant-backtest-engine/`；生产站点域名为 `https://runchengxie.github.io`。Astro 采用静态输出和末尾斜杠目录路由。本地验收必须在同一基础路径下运行，不能只验证根路径 `/`。

| 公开路径 | 归属与行为 |
| --- | --- |
| `/`、`/index.zh-CN/` | Astro 英文与中文产品首页；新产品介绍之后保留对应 MkDocs 概览文章的完整渲染内容及旧标题 ID。正文来源仍为 `docs/index{,.zh-CN}.md`。 |
| `/reference/`、`/reference/zh-CN/` | Astro 技术参考导航，链接实际未变更的 MkDocs 地址，不复制完整参考正文。 |
| `/learn/`、`/learn/zh-CN/` | Astro 学习总览；八张场景入口各给出结论、来源类别、证据阶段、样本范围和主要未解问题。 |
| `/learn/{scene}/`、`/learn/zh-CN/{scene}/` | Astro 场景解释及完整静态结果表；scene 为 `flow,book,impact,cost,lots,paths,selection,risk`。 |
| `/lab/{scene}/`、`/lab/zh-CN/{scene}/` | 同一产物的同步回放工作区，链接对应学习页。 |
| 其余已有 HTML，包括 `/backtesting-explained/`、`/backtesting-explained.zh-CN/` | MkDocs，保留公开地址和锚点；包括 `tutorial`、`contracts`、`migration/...`、`.zh-CN` 及后续增加的技术文档。 |
| `/_astro/**` | Astro 独占的客户端资源。 |
| `/assets/learning/**` | 已提交的公开轨迹、清单、来源记录和词条投影，由拼装工具统一复制，Astro 不再输出一份。 |
| `/assets/method/**`、`/javascripts/**`、`/stylesheets/**`、`/search/**`、主题资源、`/404.html`、`/sitemap.xml`、`/sitemap.xml.gz` | 保留 MkDocs 归属；拼装时只生成一次包含 Astro 路由的站点地图，并检查搜索结果链接。旧 fixture 下载地址不变。 |
| `/site-build.json` | 拼装工具输出的版本及逐文件 SHA-256 收据，不包含自己的递归哈希。 |

唯一允许替换的 HTML 文件是 `index.html` 和 `index.zh-CN/index.html`。`extract_reference_home(site_dir, output_dir)` 只提取可信 MkDocs 构建的 `<article>` 内容，去掉编辑按钮和脚本，保留正文标题 ID，按照原页面地址解析并重写相对链接，检查 ID 唯一性。`LegacyOverview.astro` 静态呈现正文，样式限制在 `.legacy-overview`，不加载 MkDocs 导航和 JS。Astro 新标题采用 `product-` 前缀。英文首页继续支持 `#quant-backtest-engine`、`#start-here`、`#names-used-in-these-docs`、`#responsibilities`、`#adoption-status`；中文继续支持 `#quant-backtest-engine` 和 `#_1`–`#_4`。新增标题以更新后的实际构建清单为准，不能猜测中文 slug。

先提取并排除这两个旧首页，再合并输出；不得靠复制顺序覆盖。其他路径冲突一律失败，即使重复文件内容相同。拒绝符号链接、越界路径和未声明的资源命名空间。保留现有输出支持的 `.html` 访问形式和编码后的片段链接。旧教程的标题和控件 ID 不变，不能把带旧锚点的 URL 重定向到新的通用入口。补充材料中的 `route-anchor-inventory.json` 来自实际 HTML；Task 19 必须用干净的 PR 19 和当时已合并主分支重新构建并更新。

## 10.3 八场景复用及有限预设

保留 PR 19（`4820af3b82940e7697cb8c92154315b1d59ee23d`）的署名、提交历史、导出器、语义词条、精确证据和测试。控制者证明完整集成之前，不删除原分支或工作树。历史产物保持原提供方信息，不能将旧字节改称当前 Engine 的结果。

| 场景 | 保留的精确预设 ID | 新呈现及边界 |
| --- | --- | --- |
| `flow` | `roundtrip` | 因果阶段及真实 Rust 行情、订单、成交、账户事件；已有订单样例没有拟合预测和优化器。无对应证据的阶段只作概念说明，不补数字。 |
| `book` | `depth` | 深度消耗、部分成交、订单到达、报告可见性；原 600 ms 延迟仍标明为演示假设，不能称为撮合提供方实测。 |
| `impact` | `small,large,nondecaying,close` | 同轴显示无冲击价格、暂态、非衰减状态与成交偏移；已计入价格的冲击不重复扣费。 |
| `cost` | `once` | 分开现金扣款与描述性价差、冲击和机会损失，保持唯一核算主体。 |
| `lots` | `no-minimum,minimum,grid` | 整数可行域、启发式与有限域精确结果；最优性只适用于枚举域。 |
| `paths` | `thin,deep,market-up,feedback` | 同步展示独立账户、预测和市场哈希、策略改变及可见待处理状态。 |
| `selection` | `null-search` | 保留全部六次尝试及真实 Platform 分析/教学归属，不声称 PBO 或样本外结果。 |
| `risk` | `recovery,shared,residual,actions,risk-full,risk-missing` | 分开状态恢复、分配、剩余库存、资本/权利与风险诊断；未知保持未知。 |

第一版固定网格就是这 21 个预设，不能将参数自由交叉组合。标签以导出的实际配置为准：`impact.large` 同时把数量改成 200、间隔改成 120 秒；`small` 为 100/60 秒，`close` 为 100/10 秒，`nondecaying` 为 100/60 秒并使用 0.001 的非衰减系数。不能把 large 说成只改变数量。四者暂态系数均为 0.002、衰减时间 60 秒。整数域为 `{0,1,2,3}²`，现金 14、价格 `(6,4)`、最低费用为 0 或 1，目标为 `(1.6,1.6)` 或 `(1.5,1.5)`。路径参与率为 0.1/0.5；`market-up` 把最后外部价格改为 10.5；`feedback` 改变声明的策略。必须明确展示这些差异。

扩展延迟、流动性、冲击或初始值控制前，先提供版本化 `preset-grid.json`，逐一记录可选参数组合、完整输入、登记过的提供方调用、种子（确定性案例明确为 null）、能力要求和对应产物哈希。缺失组合禁用并解释，不能凭空算出。连续滑块只控制动画进度，不生成中间现金、成交、价格、成本、优化器状态或收益。

## 10.4 轨迹、来源和哈希契约

保留 `engine-method-replay.v1` 及其既有 input/config/run 摘要定义。新增 `engine-learning-manifest.v1` 和 `engine-learning-trace.v1`，模式置于 `docs/assets/learning/schemas/`；同目录的 `2026-11-09-learning-trace.schema.json` 给出具体设计初稿。清单引用原 fixture 精确字节和各场景/预设轨迹，不使用自引用哈希。

manifest 字段为 `schema`、`provider_revisions`、`exporter_sources`、`fixture:{url,sha256}`、`sources:{url,sha256}`、`catalogs:{en:{url,sha256},zh-CN:{url,sha256}}`、`preset_grid:{url,sha256}` 和有序 `traces:[{scene_id,preset_id,url,sha256}]`。URL 为同站基础路径相对地址，不含私有路径。SHA 是实际提供的 UTF-8 字节的 SHA-256 小写十六进制值，不对解析后重新序列化的 JSON 校验。原提供方配置摘要继续使用原规范；传输哈希不取代语义摘要。

原始运行绑定是**零个、一个或多个具名调用**，不是单个场景摘要。`bindings.run_sha256` 原样复制所选原场景的 `run_sha256` 字典，保留每个名称和摘要；`bindings.run_bindings_pointer` 指向哈希绑定 fixture 中的原字典。字典非空时 `run_bindings_status` 为 `available`、`run_bindings_reason_key` 为 null；原字典为空时必须为 `unavailable`，并提供非空原因键 `provenance.named_run_binding_not_recorded`。这里“不可用”只指具名调用摘要证据，原结果、源码、输入、配置和 fixture 证据仍然有效。意外输入模式中完全缺失 `run_sha256` 必须报错，不能默默当作已知空字典。不能挑一个调用、改名、删贡献者，也不能把字典整体再哈希成替代标量。

`bindings.calls` 的键必须与 `bindings.run_sha256` 完全一致。每项为 `{input_pointer,digest_pointer,owner_id,source_ids}`，分别指向原 `inputs/runs/<name>` 调用定义和 `run_sha256/<name>` 摘要；来源 ID 标明真实、固定版本的导出器与提供方调用路径。JSON Pointer 使用 RFC 6901 转义，场景数组下标根据稳定 ID 定位，不能全局写死。保留原摘要语义：`method_fixture_common.scenario` 哈希的是序列化后的**调用定义**，不是该调用产生的财务输出；原完整 input/config 摘要也保持不变。顶层 `provider` 只是主要展示/分发身份，不能取代每个调用的真实归属和来源。一个场景可以包含多个不同调用，每个财务运行仍只有一个核算主体。

事件的 `source_pointers` 为每个 `values` 键提供 `ValueSource` 记录 `{source_pointer,run_names,run_binding_status,reason_key}`。`source_pointer` 指向原 fixture 中真实展示值，不指向推测结果；`run_names` 根据固定版本导出器的调用路径，列出全部且仅有的实际贡献调用，其定义和摘要必须已经绑定，允许多个贡献者。`available` 要求至少一个名称且原因为 null；`unavailable` 要求名称为空并说明为何没有具名调用证据；`not_applicable` 要求名称为空，且解释该值确为静态元数据/输入而非财务结果。状态不能用来省略已知贡献者。校验器检查调用到结果的实际对应关系，不能只检查名称存在。

每个表保留原 `source_pointer`，新增整表的 `run_names`、`run_binding_status`、`reason_key`，以及按投影单元格 JSON Pointer（例如 `/rows/0/cash`）索引的 `value_sources`，每个展示单元格都必须有 `ValueSource`。整表调用集合必须等于单元格贡献者并集；混合表中的静态单元格分别记录 `not_applicable` 原因。整表和单元格指针必须能在同一声明 fixture 中解析，单元格值须按已声明的序列化投影与原值一致。不能用整表并集掩盖单元格归属缺失或错误。即使某个视图没显示某次调用的结果，`bindings` 也保留原调用。原数值型纳秒/索引必须在任何 JavaScript-number 解析前，以任意精度整数精确转十进制字符串；保留原 `units`、明确货币/未知货币、时钟种类/时区、股数、收益分数、基点平方和无量纲比值。语义检查拒绝单位标签、缩放和时钟转换错误，不增加经济计算。

必须覆盖的真实案例：`flow.roundtrip` 保留 `{}` 和空 `calls`，说明未记录具名摘要，同时保留真实 Rust 结果；`book.depth` 只保留 `matcher`；每个 `lots` 预设保留 `planning` 和全部 16 个 `grid-i-j`。规划状态的单元格关联 `planning`，网格单元格关联实际对应网格调用，常量另行标识。`risk.shared` 保留 `allocation,execution,netting`；`risk.residual` 保留 `session,wealth`；`risk.actions` 保留 `baseline,continuation`。必须审计导出器，把每个结果/单元格关联到真实产生它的调用；组合结果使用上游调用输出时，保留其传递贡献。不能无差别附上全部名称，也不能因为最后还有分析或分配调用，就抹去此前执行的贡献。

可选 `bindings.projection_ref:{url,sha256}` 指向**独立**的安全客户端投影文件，SHA-256 覆盖它实际提供的 UTF-8 字节；被引用投影不包含该摘要/引用，且不能就是轨迹文件本身。这个字节契约与每个具名提供方调用摘要分开。该字段可以省略，不能生成它来填补缺失的原运行绑定。manifest 中的轨迹 SHA 仍覆盖完整轨迹字节，不自引用。本补充不引入聚合运行摘要。

轨迹包含场景/预设、主要提供方/后端/版本、原具名运行/input/config/forecast/market 摘要、执行源码和依赖身份、种子、策略模式、能力和证据状态以及来源引用；包含有序 `events`、保存完整账本/网格/尝试的 `tables` 和可选 `comparison`。每个事件有稳定 `event_id`、连续 `ordinal`、`clock:{kind,value,timezone}`、`stage`、真实前置事件 `depends_on` 及 `values`。时钟种类为 `utc_ns`、`elapsed_ms`、`elapsed_s`、`session_date`、`iso_datetime`、`event_index`、`trial_index`；值为字符串，绝对时间明确使用 UTC。事件序号和交易日期不能冒充 UTC 纳秒。同刻事件保持提供方顺序。财务值使用十进制字符串或 null，布尔值保持布尔值；禁止 NaN/Infinity 和不安全的数值纳秒。缺失或不支持的证据用状态和原因表达，不填零。

`project_method_trace(fixture, scene_id, preset_id)` 只投影已有数据，每个展示值记录原 JSON Pointer，不能计算成交、余额、成本、风险或优化结果。新的因果阶段和优化迭代需要真实提供方导出，不能从终值反推。`validate_learning_assets(manifest_path)` 检查模式、原零/一/多调用字典及缺失原因、完整调用身份、逐值/整表贡献者指针与并集、全部引用、预设覆盖、单位/货币及精确时钟转换/依赖顺序、指针与原值相等、公开链接、提供方身份和全部文件摘要。未知模式或哈希不符让构建失败；客户端投影验证失败则停止交互，保留静态表并显示本地化错误。测试必须证明内嵌数据与下载产物引用同一 manifest 和原值。

来源类别为 `academic_background`、`documented_discussion`、`project_interpretation`、`implemented_model`、`synthetic_execution_evidence`、`real_market_calibration`。记录具有 `id,class,title,url,locator,claim,limitations,availability`，可执行证据还含版本/哈希。讨论提出假设，学术教程解释方法，二者都不自动证明财务模型已实现或市场响应已校准。相位恢复教程不能当作金融模型验证。私下讨论没有可公开来源时，只能呈现公开安全的本项目解释，不发布聊天原文、账户/订单、主机路径或个人来源位置。

每个场景直接显示来源类别、`calibration: unavailable|synthetic_only|empirical`、样本范围、假设、实际提供方和不支持的能力。本任务没有实证校准产物；没有另外核验的样本/方法/覆盖证据时，校验器必须拒绝 empirical。多个预设只是敏感性集合，不是独立市场观察或市场概率分布；图中显示样本数，不能把频数图称为市场概率。

能力边界：已实现的暂态冲击规划器及其声明的凸 QP 域、有限离散搜索、启发式/当前找到的最佳结果，均保留真实求解范围。`impact.nondecaying` 中执行的是合成数据非衰减敏感性假设，不能据此声称已完成经过校准的永久冲击机制；本任务没有经过校准的永久或跨资产冲击证据。跨资产冲击概念图必须标为概念说明，不附虚构执行轨迹。网站列出的主题不能直接当作算法能力完成清单。

## 10.5 React 状态与同步交互

每个 lab 只有一个 `ReplayWorkbench` island，内部统一管理控件、因果图、时间线、账本、图表和场景对比；不让多个独立 hydration 的组件持有竞争游标。输入为校验后的 `LearningTrace[]`、词条、语言、manifest 身份；状态为 `{presetId,eventOrdinal,playing,speed,comparisonPresetIds,reducedMotion}`。速度仅影响播放，为 `0.5|1|2`，默认 1，默认不自动播放。`reduceReplay(state, action, traceIndex)` 只接受 `SELECT_PRESET, SELECT_EVENT, NEXT, PREVIOUS, RESET, PLAY, PAUSE, SET_SPEED, SET_COMPARISON, SET_REDUCED_MOTION`。

前进/后退不越界，重置回事件 0 并暂停；改变预设或对比集先暂停，再回到第一个有效对齐点。最后事件的播放按钮不隐式重头开始。手动步进/定位均暂停播放。定时器只推进真实事件，卸载或页面隐藏时取消；返回标签页不自动恢复。金额文本只在事件边界改变。0–1 的连续进度只能插值画面几何，不能让财务文字或图表看似出现新的经济状态。减少动态效果模式取消插值和定时播放；播放按钮禁用并解释，保留前后步进、重置和选择。

对比使用导出器给定的 `comparison:{axis,points:[{id,label_key,events:{preset_id:event_id|null}}]}`。同一对齐点读取各自独立账户，null 表示没有对应事件。不机械配对长度不同的历史、不向前填充未知财务证据、不混用时间轴。已有 paths 按实际决策/成交阶段对齐并验证时钟兼容；四个案例不能凭空变成概率分布或随机种子。选择尝试和恢复边界使用各自标明的索引轴。

已有有限整数网格可以讲解离散非凸可行域。连续非凸动画还需要真实求解器回调，导出初始值、每次迭代、目标函数、约束残差、终止原因和找到的最佳可行解，使用登记过的有限多起点网格；各起点使用同一目标和约束。浏览器只画记录，不能求目标函数曲面或优化组合。通用研究优化器仍归 Platform，作为可选导出依赖；Engine 只拥有自己的执行规划器。如果真实求解器没有迭代接口，只展示真实起点/终点并标明中间轨迹不可用，不伪造下降路径、不声称全局最优。以后补充多起点轨迹需要新版本证据，不能因此暂停已授权财务迁移，也不能把尚未实现的动画算作完成。

## 10.6 语言、可访问性与正文

Astro 无语言后缀路径默认为英文，中文使用明确路径和双向切换链接。保留 `docs/assets/method/en.json`、`zh-CN.json` 为共享语义词条来源，增加 `learning.*`、`source.*`、`evidence.*` 和控件键。新增解释正文置于 `web/src/content/learn/{en,zh-CN}/`。机器 ID、摘要和财务存储值不随语言改变。缺失中文回退英文，测试报告缺失键。时间显示必须使用声明的时钟语义和时区；方便阅读的格式旁保留精确纳秒/十进制下载值。

`engine.site.locale.v1` 仅保存 `en` 或 `zh-CN`，存储失败不能让页面失效。URL 优先，不自动重定向深链接和片段；已保存语言决定后续生成导航的语言，以及英文首页“继续阅读中文/英文”链接。显式切换保存偏好并跳转到对应页面/场景锚点。浏览器语言不能覆盖默认英文。旧 MkDocs 使用同一小型无框架偏好脚本和双语路由表；React 仍是唯一客户端组件框架。跨 MkDocs/Astro 采用普通页面链接，不叠加竞争的 SPA 生命周期。

全部正文、来源、21 个预设的每一行、完整整数域和全部尝试均存在静态 HTML 中，不依赖 hydration。只有 hydration 成功才启用交互。原生按钮/选择/范围控件有标签、可见焦点、键盘操作和当前事件提示；箭头步进只作用于获得焦点的时间线，不抢占输入框/选择框按键。遵从减少动态效果偏好，每个图表有表格替代。测试 320px 和桌面、明暗主题、无 JS、禁用存储、hydration 失败、离开返回和场景中切语言；静态 `<details>` 无 JS 仍可打开。

## 10.7 构建、发布及验收

`.github/workflows/docs.yml` 保持唯一 Pages 发布归属。MkDocs 输出到 `TASK_DATA/site-mkdocs`，提取首页并验证产物，Astro 输出到 `TASK_DATA/site-astro`，`assemble_site(mkdocs_dir,astro_dir,learning_dir,route_manifest,output_dir)` 创建全新的 `TASK_DATA/site-assembled`。不能将现有生产目录当作暂存区。拼装生成 `site-build.json`、包含两边路由的唯一站点地图，并验证基础路径下全部本地链接/片段/资源。现有 MkDocs 搜索明确标为技术参考搜索；学习导航涵盖八场景，不假称已实现统一搜索。

PR 构建执行完整拼装和验收但不发布；main 只上传一个 assembled artifact，由现有 deploy job 发布一次。不新增 Astro 发布工作流、Pages 分支或常驻服务器。CI 使用 `RUNNER_TEMP`，本地输出、缓存和浏览器配置使用 Engine 任务数据目录。保留锁定的 MkDocs 检查和全部经济测试；Astro 不取代它们。固定 action 和前端依赖版本，记录审计结果，未解释的生产依赖高危/严重问题阻止发布。

验收要求从当时干净已合并 Engine 提供方重新导出，保留可选分析提供方真实身份；检查字节、源码、模式和 typed-call 变异、八场景 fixture、全部旧地址/锚点、固定预设和同步状态、真实构建站浏览器行为以及无 JS 精确表格。保留 MkDocs 原 DOM/replay 测试，增加 React reducer/component 和真实 Playwright 拼装站测试。Task 20 核对线上收据、HTML、fixture 下载哈希与合并版本，并检查首页片段、语言保存和两套渲染页面；不能凭工作流绿灯或截图通过。证明 PR 19 工作完整集成且无独有未保存内容后，控制者才能关闭旧 PR 并清理。

实现细节：首页片段每次由当前源码生成的文章重新提取，保留在仓库外的构建目录，不提交冻结的 HTML 存档。`docs/assets/learning/**` 在暂存阶段只由 MkDocs 输出；拼装工具根据原 `learning_dir` 校验后只复制一次。Astro 读取数据，但不得另行输出 `public/assets/learning` 副本。两套渲染输入和首页提取必须对应同一干净源码版本及预期 manifest/锁文件哈希；工作目录名称不是版本身份。共享资源同样受路径冲突检查约束。

## 11. 证明可复用的验收

所有独立例子从仓库外安装已构建产物运行。

1. 标准库 SDK 加固定 Rust 二进制，不装 Platform、Runtime 或研究包；原例从 10,000 美元到 10,019.78，费用 0.22。
2. 可选 Python 核心不装上述项目和 Torch，跑人民币部分成交、费用、锁定、权益、资金流、未知估值和每事件恢复。
3. 可选规划与情景安装，跑独立账户、有界求解、执行与市场路径区分，以及明确的调用方回调。
4. Platform 与另一个最小项目使用同一公开接口，在支持且对齐的输入上通过独立手算对照。
5. Runtime 新提供者在写入、同步、重命名、接纳与确认边界经历真实进程终止，恢复后的完整财务结果与连续运行一致。

检查安装包文件和执行时导入。仅延迟导入不能证明消除了 Platform 依赖；不能用源码路径或可编辑工作树冒充独立安装包。

保留独立账本、一纳秒因果边界、来源和事件带变化拒绝、失败记录、配置变化哈希测试、实际与可见账户、受限退出。搬迁保持运算时完整经济表应精确一致；身份或版本差异逐字段列明审阅，不能大范围删列或放宽误差取通过。

跨后端只在费用、时钟、手数、容量、估值和规则对齐的域内比较。原来的周期收益对照不构成完整财务等价。记录精确源码、提供者、消费者、依赖、二进制、命令、退出码和跳过。文档与浏览器检查不能替代核算测试。保留搬迁文件的原许可证和归属说明，核对构建包及源码内容。

## 12. 本次范围与待审阅决定

本设计不增加 tick 获取、券商连接或下单、生产配置与定时任务修改、真实成本冲击校准、历史竞价排队、真实借贷条款或前瞻收益证据。架构迁移不改变合成验证的证据等级。

提请审阅的具体默认方案。

- 独立零依赖 SDK，加独立命名空间的可选 Engine Python 核心。
- Platform 保留通用因子、风险统计和研究；Engine 接收回测专用机制。
- 明确后端、增量版本接口，不静默切换或重绑检查点。
- 财务依赖组整体迁移，可独立的机制先行。
- 代码、可执行示例和中英文文档同步迁移；保留历史证据与旧链接。
- Runtime 运维职责和研究登记权威继续在 Engine 外。

用户批准本设计后，再编写包含精确文件、契约、测试、跨仓顺序和逐批审查门槛的实施计划。本文不声称新包、接口或任何迁移已经存在。
