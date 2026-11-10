# Task 15P 期间与分腿闭包补充计划

[English](2026-11-11-period-leg-closure.md)

在恢复消费方 Task 15 前，补齐提供方 C PR #24 合并后发现的纯源闭包遗漏。
本次是精确兼容迁移，保留 Core/SDK 0.3.0 系列及不可变的源和 wheel 身份。

1. 验证原 7a 与 7ff 源实现，以及已有 helper 的精确语义。
2. 先记录缺失 API 的有效 RED，再迁移限定财务闭包，同时保留两套不同的交易核算 API。
3. 执行真实旧所有者的全字段捕获，以及安装环境中的 3.12/3.13 daily、原依赖严格环境、
   原生扩展和 Rust 的 union 验收；保留 SDK 3.11。
4. 完成源、wheel、RECORD、导入闭包绑定、原始测试、静态检查、Rust 检查、双语文档与所有权记录。
5. 控制方复核并合并 Task 15P，发布精确合并产物，恢复消费方 Task 15，然后开始 Astro Task 19。

[API 边界与兼容细节](../../guides/diagnostic-close-replay.zh-CN.md)
由专属指南维护。筛选、研究指标与编排、输出投影仍属 Platform。本前置任务不包含
消费方、前端、经纪商、生产配置或 PyPI 工作。
