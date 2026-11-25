# 账户 owner 控制实验实施计划

[English](2026-11-25-owner-control.md)

目标：让固定执行控制通过同一个财务 owner，并验证压力与恢复行为。
架构：合成输入和策略桥接既有 `MinuteSession`，事后审计只读取 owner 表；外部产物绑定代码和输入。
设计：[约定范围](../specs/2026-11-25-owner-control-design.zh-CN.md)。

- [ ] 测试先行创建 `owner_control.py`、`owner_control_case.py` 与对应测试，提供验证后的 `OwnerControlCase`、`build_session`、`restore_case`、`run_case`；不新增现金账本。
- [ ] 观察失败后实现四种策略、已送达状态及挂单门控、固定数量不追补、LQ代理与整数目标权重编码。检查点绑定配置、辅助源码和依赖版本。
- [ ] 测试先行实现 `owner_control_audit.py`，验证手算案例、逐笔/累计手续费及数量守恒；禁止重复计入冲击成本。
- [ ] 验证四个延迟/容量中断代表情景所有边界恢复，及未来 bar 前缀不变性；拒绝配置、依赖和畸形状态。
- [ ] 实现 `scripts/verify/export_owner_control.py`，保留104面板行/96唯一情景、全部 owner 表与轨迹、失败状态和恢复证据；不选参数。
- [ ] 独立复核策略、财务边界和导出算术，运行锁定 Core/SDK 全套、Rust必需检查与CLI、归属检查、静态和严格中英文文档检查。源码指纹测试期间冻结源码。
- [ ] 提交并推送 owner 仓库 PR，核对当前目标及必需检查后合并，只清理本任务分支和工作树，保留外部证据。

文件分工：root负责审计、导出、实验、文档、产物和Git；有界实现者只负责控制器、情景模块及其测试；独立复核者不改源码，避免交叉写入。
