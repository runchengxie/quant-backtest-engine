# 正确性证据与迁移判断

主要基线是一组可以手算的合成案例，实际调用上游引擎核对经济结果。
升级时必须通过这些案例，但它们不能证明所有市场机制或生产数据都正确。

| 案例 | 预期行为 | 可执行证据 |
| --- | --- | --- |
| 以 10 买 10 股，以 12 卖出，每笔费率 10 bps | 最终现金及净资产 10019.78，费用 0.22 | `tests/engine.rs::upstream_roundtrip_accounts_for_fees_and_no_lookahead` |
| 未平仓持仓按最后报价估值 | 现金 9899.9 + 持仓 110 = 净资产 10009.9 | `tests/engine.rs::upstream_marks_open_positions_and_is_repeatable` |
| 现金恰好够本金但不够费用 | 拒单，不虚构成交 | `tests/engine.rs::cash_admission_includes_upstream_rounded_commission` |
| 10% 权重与配置的 T+1 | 首日净资产 10099，当日卖出被拒，最终 10197.8 | [可运行教程](tutorial.zh-CN.md)和 `tests/sessions.rs` |
| 显示报价数量不足 | 真实部分成交，IOC 未成交余量取消 | `tests/sessions.rs::quote_liquidity_is_shared_and_ioc_does_not_invent_capacity` |
| 估值报价缺失、过期或使用复权价 | 明确失败 | `tests/sessions.rs::rejects_missing_or_stale_session_valuation_and_adjusted_prices` |
| 相同输入重复运行 | 标准化 JSON 一致 | 引擎测试和[批量摘要核对](benchmarks.zh-CN.md) |
| 用数量调整事件模拟送转股 | 成本没有正确重基 | [公司行动验证](migration/corporate-action-conformance.zh-CN.md)，继续保留 Python |

修改上游版本之前执行 `cargo test --locked` 和教程。调用方还会核对成交、现金和持仓，
把估值价格绑定到请求中的估值时点报价中间价。即使账面平衡，虚高估值也必须被拒绝。

## 一个范围明确的 Python 对照

在另一个已安装 `quant-platform` 的 Python 环境中执行：

```sh
/path/to/platform-python project_tools/compare_python.py \
  --engine /absolute/path/to/quant-backtest-engine \
  --output /absolute/external/path/new-comparison.json
```

案例将人民币 10,000 全仓以 10 买入，再以 12 卖出，不收费用。
现有 Python `NativePositionReplayBackend` 给出浮点收益 `0.19999999999999996`，
固定版本的 Rust 引擎给出十进制收益 `0.2`，净资产 `12000`。
脚本对 Python 浮点收益使用 `1e-12` 的绝对容差。
本次使用引擎提交 `3ee74bfa21d743e595ce61d0ac06b97dd588ebd6`，
Python 参考后端对应 platform 提交 `35055445ffcbd86c26cd4d3017b3fe0e14b4ee2a`。
后续新增的适配器不改变这个参考后端。

对照仅覆盖区间收益。Python 区间收盘价回放与 Rust 显式报价回放的时间和输入形式不同，
这里没有比较逐日估值、含费数量规划、部分成交、税费、公司行动或完整账本。
未统一假设和完成验证的机制，不能把任一后端当作绝对标准。

## 切换调用方之前

列出其数据可用时间、成交与估值约定、币种、费用、结算、公司行动和输出要求，
逐项核对[能力矩阵](capabilities.zh-CN.md)。用有代表性的合成案例同时运行两条路径，
解释差异后再切换。关键机制不支持时保留 Python 路径。
收益表现不能替代现金、股份和成交的核对。
