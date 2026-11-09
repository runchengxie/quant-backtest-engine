# 第三方声明

本项目直接依赖 NautilusTrader 0.66.0 的回测、交易、模型和执行等 crate。
上游地址为 https://github.com/nautechsystems/nautilus_trader，
版权属于 Nautech Systems Pty Ltd.，采用 LGPL-3.0-only。

本仓库通过公开 API 调用上游，没有复制或 fork 撮合引擎。
Cargo.lock 保存固定版本和校验和，各传递依赖保留各自许可证。
分发时需保留适用的版权、许可文本和源码义务。

LGPL 与其引用的 GPL 原文分别保留在仓库根目录的 LICENSE 与 COPYING。
完整英文声明见[Third-party notices](third-party-notices.md)。

## 从 quant-platform 提取的叶子模块

Python core 包含从
[quant-platform 提交 7a618bd](https://github.com/runchengxie/quant-platform/tree/7a618bddd8fdeee5dbe37fe5b54a9698e0de5355)
提取的代码、测试和文档，原始许可为 Apache-2.0，原源码树没有 NOTICE 文件。
逐文件来源路径及 SHA256 记录于
[core 声明](https://github.com/runchengxie/quant-backtest-engine/blob/main/core/THIRD_PARTY_NOTICES.md)。
原 Apache 许可逐字节保留，并与声明一同装入 wheel 许可元数据。
原条款及署名继续保留，Engine 包许可不替换它们。修改涉及模块及辅助函数位置、
导入和格式，以及新增报价传输类型；财务算术保持原样。双语文档使用 Engine 命名空间
和示例，同时保留来源的适用范围及限制。
