# Minute execution scenarios

[简体中文](minute-execution.zh-CN.md)

`quant_backtest_core.backtest.minute` is an opt-in long-only mechanism using raw prices and caller-verified corporate actions. Existing daily APIs are unchanged. Execution uses historical amount divided by share volume, bounded to bar OHLC. This proxy neither proves executable fills nor identifies own-order impact.

Use `MinuteExecutionConfig` and `simulate_minute_execution(targets, bars, config, corporate_actions=())`. Results expose `daily`, `orders`, `fills`, `holdings`, and `summary`. The holdings ledger contains positive closing inventory only. An absent symbol means zero ownership only when the corresponding date exists in `daily`.

Targets are complete snapshots with timezone-aware pandas `decision_time`, `entry_time`, `symbol`, and `weight`. Entry must follow decision. Omitted holdings receive zero target weight; a new snapshot cancels pending earlier orders. Quantities use reference marks available before entry, and release schedules do not depend on future volume.

Bars require `symbol,time,open,high,low,close,volume,amount,up_limit,down_limit,tradable`. Prices and amount use CNY; volume uses shares. `time` is observation availability. Optional `interval_start` identifies the earliest trade time represented by its volume; the default is conservatively `time-1 minute`. The entire interval must start strictly after slice release plus latency. Delayed availability cannot authorize pre-activation liquidity.

`release_slices` and `execution_minutes` determine a fixed schedule. Durations are wall-clock minutes, including lunch. Sibling orders share per-symbol bar participation. Sells fund buys, fees constrain affordability, and rules enforce T+1, configured buy lots, and directional limit touches. Whole-position integer odd lots can be liquidated when capacity permits; fractional entitlements remain separately disclosed.

Existing `CorporateAction` events capture record-date closing ownership, create cash/share receivables on ex-date, and release them on payment/listing dates. Unlisted stock rights count toward target exposure but cannot be sold. Before a fresh ex-date observation, known ordinary distributions adjust reference marks and label them `synthetic_ex_reference`; these are derived references, not observed quotes. Reorganization capitalization and rights issues require separate caller verification.

Missing daily marks for holdings or pending stock rights invalidate NAV and retain symbol diagnostics. Callers must additionally verify terminal marks, the authoritative calendar, historical eligibility, all corporate actions, and versioned inputs. Optional `commission_minimum_cny` defaults to zero and applies once per parent across partial fills. `sell_tax_bp` separates tax from the combined sell rate. Zero fills incur no fee, and both buy affordability and sell proceeds respect available cash. Parent aggregation is an explicit assumption; actual brokers may bill child orders differently. Historical queues and hidden liquidity remain unmodeled. Optional `LinearImpact` supplies explicit synthetic impact scenarios only.


Explicit `ValuationEvent(event_id, symbol, effective_time, available_time, value_per_share, basis, source)` declarations are separate from executable bars. Pass them through `valuation_events=()`; prices may be zero, and both timestamps must be timezone aware with availability no later than effectiveness. Identifiers and symbol/effective-time keys are unique. An event establishes permanent nontrading eligibility, cancels affected pending orders, and blocks later targets. It changes neither cash nor legal share ownership and preserves corporate entitlements. Later events may update the valuation but cannot reopen trading. Nontradable bars do not override declared marks; any tradable bar at or after the declaration is rejected.

Events within the bars/targets window apply at their own instant before sizing. Earlier declarations establish state at the first base instant, retaining their original timestamps. Future declarations are ignored and listed in `summary.ignored_future_event_ids`; they never extend the end date. Persistent declared valuations remain explicit assumptions: opt-in `daily.valuation_marks` retains source, basis, effective/available time, and source/event age, and does not classify them as observed fresh quotes. `valuation_ledger` records each application, actual shares, stock rights, prior/new mark, value change, and unchanged cash. Zero is a valuation declaration, never a zero OHLC bar or assumed disposal.

With valuation events enabled, bar times, interval starts, and target decision/entry times must share one declared market timezone. Event timestamps may use other timezones and are converted to that market timezone without changing their instants, so calendar-day accounting follows the market.

### Conditional orders and declared information time

`simulate_minute_execution` is available through
`quant_backtest_core.backtest.minute`. It consumes complete target
snapshots rather than arbitrary submitted broker orders. An optional target
`order_type` column accepts only `market`; `limit`, `stop`, `stop_limit` and other
conditional instructions fail explicitly. High and low do not reveal which
price occurred first, so this simulator cannot infer stop/limit trigger ordering.
Its existing exchange-limit rule blocks an entire buy bar touching `up_limit`
or sell bar touching `down_limit`; this is a conservative assumption, not queue
matching. `up_limit` and `down_limit` are exchange price bands, not order prices.

An optional timezone-aware `information_time` column declares the latest
information used to form each target and must be at or before `decision_time`.
This checks the supplied declaration only; it cannot certify the underlying
features' availability. Omitting the column preserves the existing caller-owned
point-in-time contract. Entry follows decision, sizing uses marks observed
strictly before entry, and a fill requires the complete bar to begin strictly
after release plus latency. Bar volume/amount become known at the bar end;
VWAP is an ex-post execution proxy rather than an order submission price.

Participation capacity is decremented after each fill within a symbol/bar.
Complete snapshots supersede earlier pending orders, so the public target API
normally has at most one pending parent per symbol. Fee sensitivity should be
checked with fixed targets and sufficient cash headroom when isolating cost;
with binding cash, fees can also change lot-rounded fills. Synthetic regression
examples are in `tests/test_minute_execution_hardening.py`.

## Temporary nontrading mark provenance

Optional paired `mark_source_time` and `mark_basis` bar columns preserve the
observation time behind a declared valuation mark. `raw` requires source time to
equal bar time. `declared_nontrading` requires a flat OHLC price, zero volume and
amount, `tradable=False`, and an aware source time no later than the bar time.
The caller must supply and audit the source and corporate-action policy.

A declaration can value a temporary suspension and later permit trading again.
Later order references retain both the effective mark time and its original
source time/basis. It is not an executable quote or a source-quality certificate.
Permanent nontrading valuation events retain their existing separate contract.
Omitting both columns preserves legacy behavior.

## Engine ownership and synthetic example

Install `quant-backtest-core[minute]` explicitly. Core defines the financial types.
Platform remains on its original provider until the complete type, `LinearImpact`
and compatibility-alias cohort switches in the consumer wave. No Platform, Runtime
or model-training dependency is imported. The product runner minute backend is
not registered by this source transfer.

Run the repository’s synthetic CNY example against installed wheels:

```bash
python -I -B examples/product/minute_session.py
```

It exercises actions, locks, delayed reports and external capital, checking complete
financial tables after recovery. See the [session and capital-flow contract](../backtest/minute-session.md)
for clock and recovery semantics. Old `minute-session.v2` state requires its original
complete pinned provider environment; rewriting digests or silent migration is unsupported.
