# 可恢复财务会话

[English](recovery.md)

Core 0.1.0 通过 `minute-input.v1` 提供 `python.minute` 后端。在 Python 3.12 或 3.13
安装配套 SDK 0.3.0 与 `quant-backtest-core[minute]` wheel。SDK 的输入校验只依赖标准库，
仍支持 Python 3.11；执行必须显式安装 minute extra，不导入 Platform、Runtime 或研究包。
Rust 是单独的后端，不因此获得恢复能力。

## 打开、观察、恢复和完成

将同一提交中的合成文件 `fixtures/product/minute-session.json` 与
`fixtures/product/minute-calendar.json` 复制到输入目录。恢复时保持 manifest 不变，使用新的输出目录。

```python
from pathlib import Path
from quant_backtest_engine.product import loads_manifest
from quant_backtest_core import BackendContext
from quant_backtest_core.sessions import open_session, restore_session

inputs = Path("inputs")
manifest = loads_manifest((inputs / "minute-session.json").read_text())
session = open_session(manifest, context=BackendContext(inputs, Path("first-output")))
observation = session.step()
checkpoint = session.checkpoint()
recovered = restore_session(
    manifest, checkpoint, context=BackendContext(inputs, Path("recovered-output"))
)
result = recovered.finish()
assert recovered.finish() is result
```

`step()` 返回深层不可变的 `SessionObservation(cursor, as_of_ns, account, reports)`；
事件处理完后返回 `None`。`observe()` 返回最后一次成功观察。账户及待处理订单报告遵循 owner
的因果送达顺序，不泄露尚未送达的经济成交；嵌套映射和序列也不能修改。首个事件前使用
manifest 的可获知时钟；该时钟未知时使用首个事件时钟。`finish()` 执行剩余事件并且只结算
一次，再次调用返回同一个结果对象，不追加账本。已完成会话不能再生成检查点。

## 精确输入与策略

输入恰好包含 `targets` 和 `bars`，可内联，也可引用经 SHA256 校验的 JSON 文件。
目标包含 `decision_time`、`entry_time`、`symbol`、`weight`，可选 `information_time` 与
`order_type`。行情包含原生 OHLC、成交额、股数、涨跌停价、严格布尔值 `tradable`，以及可选
区间和估值来源字段。所有传输时钟都是十进制整数字符串表示的 UTC 纳秒，包括沿用原生名称
的 `*_time` 字段；只在原生边界直接转成整数和 pandas Timestamp，不经过浮点时钟。
公司行动的 `*_date` 仍是日历日期字符串。金额、权重、价格和模型系数使用十进制字符串；
配置中的手数、切片和时长计数使用整数。原有浮点财务运算保持不变，字符串传输不表示改为十进制记账。

`settings` 显式提供除初始现金外的完整原生 `config`、`report_delay_seconds`，以及
`impact`（null 或 transient/permanent/decay 系数）。初始账户只支持现金。四条带必须显式
提供，包括空带：`quantity_locks`、`corporate_actions`、`valuation_events`、`capital_flows`。
日历必须与输入会话日期和时区完全一致；这是合成声明，不负责获取交易所日历。
不支持执行 forecast/risk/scenario 变换；可选模型版本仅为 `linear-impact: v1`。
财务规则见[原生执行契约](../guides/minute-execution.zh-CN.md)。

唯一可从远端请求重建的策略为 `target-weights.v1`：id 是 `target-weights`，version 为
`v1`，state schema 为 `target-weights-state.v1`，配置和状态均为空。它使用输入目标，
在仍有待处理订单或回报时等待，不进行动态导入。可信宿主也可传入 `LocalPolicy` 对象，
声明稳定的 `policy_id`、`version`、`state_schema`，实现
`decide(observation) -> Mapping[str,str]`、`state() -> JsonValue` 和 `restore_state(state)`。
身份必须匹配 manifest。策略桥在不可变账户中提供十进制 `proposed_weights`，保留 owner
的延迟回报与待处理订单限制。策略需有可检查的源码文件，完整保存可变状态；恢复时宿主提供
同一可信类型，不接收序列化代码。

## 来源绑定与失败

外层 schema 是 `engine-financial-checkpoint.v1`，包含 provider、input schema、manifest
与 binding SHA256、cursor、策略 id/version/state schema、值为 `minute-session.v3` 的
`owner_schema`、完整 `owner_state` 及其 SHA256，另有外层完整性摘要。
其中没有任务、租约、SQLite 或调度器身份。恢复预期值均来自调用者 manifest，不能由检查点
提供预期输入带或源码身份。绑定覆盖完整序列化输入、带、配置、延迟、冲击模型、日历、provider、
所有已安装 core/SDK Python 辅助模块、Python 版本、实际依赖文件（含 NumPy/pandas 二进制），
以及本地策略源码和初始状态。每次恢复重新校验输入文件，版本号不能替代来源身份。
未经单独记录的 Git revision 为 null；来源和 wheel 收据确定发布身份，不使用自引用摘要。

一步失败即使 wrapper 及财务 owner 失效。`failure` 保留原始异常，后续执行和 checkpoint
调用重新抛出同一异常；`last_successful_checkpoint` 保留先前成功边界的字节。
wrapper 不再向失效 owner 请求检查点，`observe()` 仍返回最后成功观察。
保持输入不变可新建会话恢复；输入改变则重新开始。结算或持久化失败也使 wrapper 失效，
可能留下供诊断的原生文件，但不能将其视为成功发布的结果。

摘要用于发现损坏和漂移，不防范恶意检查点作者，应将检查点作为可信本地数据。
旧 schema 留在原始固定版本环境中；涉及 Runtime 时须包含完整 Runtime/Go 可执行文件及依赖。
不重绑旧状态、不补迁移默认值，也不改标签冒充新版本。

## 完整证据与验收

支持 `reports`（终态订单）、`fills`、`positions`（收盘持仓）、`valuations`、`capital_flows`
和 `daily`。其他经济表明确不可用；受支持但为空的表与不支持的账本不同。未知估值和收益值保持
null。费用留在成交和日度证据中，不重复扣现金；已经进入成交价格的冲击只收费一次，描述性的
机会损失不另扣款。存取款与 PnL 分开，未成交的计划卖出所得不能为买入融资。

原始结果文件保留六张原生表、summary，以及含非有限值标签的无损 `owner_result`。
`raw_result` 与归一化收据绑定其确切字节。标准表使用十进制字符串与安全的字符串时钟。
合成例包含两次分批买入、一次 5 元父订单最低佣金、200 元分红、200 股新增股票和 50 元净入金。

```sh
"$ENV/bin/python" -I -B project_tools/verify_installed_product.py --mode minute \
  --manifest "$INPUTS/minute-session.json" --artifact-root "$INPUTS" \
  --output-root "$OUTPUTS"
"$ENV/bin/python" -I -B -m pytest core/tests/test_product_sessions.py \
  core/tests/test_product_checkpoint.py -q -p no:cacheprovider
```

验收使用独立安装的 wheel，检查命名空间隔离及禁用依赖，对每个成功事件边界恢复并比较完整
财务结果。锁定依赖基线见[安装说明](installation.zh-CN.md)。
