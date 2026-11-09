# 容量与日频净值执行模拟

[English](execution-simulation.md)

Task 13 已实现[日频输入元数据、显式日历、纯配置和财务证据摘要](../product/daily-inputs.zh-CN.md)。
日频执行实现及完整财务表仍待 Task 14。本页保留约定的目标地址和锚点，
并不表示可执行后端已经交付。

<span id="_1"></span>

## 公共 API

可使用[日频输入](../product/daily-inputs.zh-CN.md)所述叶模块。
SDK 将 `daily-input.v1` 标记为待实现，并拒绝执行准入。

<span id="_2"></span>

## 配置

原有 `ExecutionSimConfig` 和纯解析器位于
`quant_backtest_core.daily.execution_sim.config`，算术和解析行为保持不变。

<span id="_3"></span>

## 输入与输出

中立请求需要显式单位、列选择器、时钟和交易日。保守摘要保留未知值，
不替代原有财务表或 Platform 研究统计。完整退市审计行为及财务表一致性仍待 Task 14；
元数据接口不引入新退市模型，也不推断缺失数据。

<span id="_4"></span>

## 公司行动与价格单位

非空公司行动请求要求原始价格和现有事件类。新中立请求的空元组表示无请求，
旧直接 API 的空元组显式启用语义保持不变。
详见[单位和行动契约](../product/daily-inputs.zh-CN.md)。

<span id="_5"></span>

## 解释执行路径

每次运行由唯一财务执行方负责。Task 13 不执行路径、不重建研究指标，
也不发布前瞻 alpha 证据。Provider C 发布及兼容消费方迁移仍未完成。
