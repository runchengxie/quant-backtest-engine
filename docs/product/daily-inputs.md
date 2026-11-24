# Daily execution inputs

[中文](daily-inputs.zh-CN.md)

Core 0.3.0 implements the independent daily graph, daily-input.v1 validation and python.daily backend. Release still requires merged-source and exact-wheel receipts. Install [daily] with the matching SDK. Task13 metadata, config and summary are reused unchanged; original financial tables remain.

## Explicit native request

`DailyReplayRequest` takes positions and pricing DataFrames, an
`ExecutionCalendar`, rebalance-date keyed `ClockSet` values, the owned
`ExecutionSimConfig`, mode (`ideal`, `capacity`, `adjusted`, `sequenced`),
price basis, corporate actions and an optional fee model. Keyword-only
`layout` and `decision_timing` are required. No strategy code, provider import,
executable command or serialized code is accepted as a selector.

`DailyInputLayout` names `price_col`, `mark_price_col`, `tradable_col`,
`buy_tradable_col`, `sell_tradable_col`, `currency`, `quantity_unit`,
`price_unit` and each selected column's `liquidity_units`. Unused selectors
are explicitly `None`. The owner uses the same price table for execution and
valuation, so `mark_price_col == price_col` is required; separate marks are
unsupported. For raw CNY prices, units are `raw_share` and `CNY/raw_share`;
adjusted basis uses `adjusted_share` and `CNY/adjusted_share`. Liquidity
units are `CNY` with multiplier 1, or e.g. `1000 CNY` with multiplier 1000.
The manifest adapter must compare currency and share basis against these
declarations. Native metadata alone is not manifest admission.

Lot sizes, T+1, liquidity multiplier and price-limit/listing selectors remain
solely in `ExecutionSimConfig`. Its parser and class were transferred
from Platform commit `7a618bddd8fdeee5dbe37fe5b54a9698e0de5355`, with a
NumPy-only dependency closure. Missing selected columns and enabled rule inputs
fail without source defaults. Instrument/rule columns must be supplied by the
caller. Legacy mode-specific kwargs remain on direct APIs; an adapter must
reject settings it cannot represent. Sparse targets do not imply missing
calendar sessions should be synthesized.

A new request with `corporate_actions=()` means no action request:
`legacy_corporate_actions()` maps it to legacy `None`. Nonempty tuples
require raw prices and the exact existing `CorporateAction` class and
normalization. Direct legacy APIs keep their different opt-in behavior:
raw `()` enables action evidence, while adjusted `()` raises.

## Clocks and supplied sessions

Every strict `YYYY-MM-DD` rebalance date has explicit information, decision
and entry clocks. Require information ≤ decision ≤ entry, and availability
≤ decision when availability is independently evidenced. Entry means earliest
eligible order time, not a realized fill. Other clock fields remain nullable;
there is no generic total ordering of all clocks.

`DailyDecisionTiming` preserves nullable signal, earliest-order, execution
window start/end, timing-policy ID and calendar reference. The mapping may be
empty for native callers with independent clocks. A future ResearchClock
translator preserves every supplied field and source constraint: information
≤ signal ≤ decision ≤ valuation; decision ≤ earliest order; paired window
bounds with decision ≤ start ≤ end ≤ valuation; earliest order ≤ end.
Earliest order may be later than window start. Entry is the maximum of the
two supplied lower bounds, the sole lower bound, or unknown without either.
Unspecified availability stays unknown. `utc_ns` converts aware timestamps
to exact UTC nanosecond strings without float epoch seconds, preserving
nanoseconds even beyond JavaScript's safe integer range.

Calendar dates are labels, not instants. `ExecutionCalendar.from_dates`
sorts and deduplicates strict valid dates. The exact installed IANA timezone
identifier is retained. The semantic digest hashes UTF-8 JSON with ordered keys
`schema`, `timezone`, `open_dates`; schema `execution-calendar.v1`;
`ensure_ascii=True`; compact comma/colon separators; no BOM; exactly one LF.
The constructor rejects mismatches. An `ArtifactRef.sha256` instead hashes
the exact original artifact bytes; it need not equal this semantic digest.

`execution_dates(calendar, start=..., end=...)` is inclusive.
`execution_date_map(signal_dates, shift_days, calendar)` retains original
arithmetic: shift ≤ 0 chooses the first supplied session on/after the signal;
positive shift N chooses the Nth supplied session strictly after it.
Exhausted keys return `None`; legacy wrappers omit those keys.
Empty input never fetches a provider, creates weekdays or invokes a future
callback. A tuple or digest cannot prove the real market-calendar horizon.
The later executable profile must check target coverage against supplied
sessions, without claiming an invented calendar-coverage authority.

## Supported summaries and unknown evidence

`summarize_execution(daily, fills, evidence=...)` returns only
`daily_return`, `cumulative_return`, `turnover`, `total_fees` and
`valuation_complete`. `DailySummaryEvidence` is immutable, uses schema
`daily-summary-evidence.v1`, declares each table available/unavailable, and
aligns valuation/zero-flow flags exactly to daily row order. Availability
attests the entire declared run interval, including explicit empty evidence,
not simply that a DataFrame exists. These are owner/caller assertions, not
source authentication inferred by Engine. Contradictory status or row
alignment fails.

A True valuation flag attests complete opening/closing marks, cash, holdings
and receivables for that return interval. A True zero-flow flag proves no
external capital throughout the interval, including initial-to-first-row.
Only finite owner `executed_return` values with both flags True survive;
unknown positions stay `None`. Full supported ordered returns compound
using the original product-minus-one. Never compound a dropna subset.
For literal initial NAV 100, closing NAVs 110 and 99 and owner returns
0.1 and -0.1, the cumulative return is -0.01.

Complete marks with a deposit can still give `valuation_complete=True`
and unknown return. This seam does not implement flow adjustment; the exact
`CapitalObservation` path still requires its existing complete initial and
ordered before/after-flow observations. Supported empty daily evidence gives
`()`, 0.0, True; unavailable empty gives `()`, None, False.

Turnover remains unknown until a named original basis is supported; gross
currency notional is not a rate. Fees sum finite `cost_commission`,
`cost_stamp_tax` and `cost_transfer_fee` from one declared complete
actual-fills source. Explicit supported empty fills with all three columns
give zero. Missing status, column or component gives unknown. No daily
fallback, daily-plus-fill addition, `transaction_cost` addition, second cash
debit or additional impact debit is performed.

Original financial tables, period/turnover conventions and arithmetic remain
owned by the extracted execution implementation. IC, alpha and broad research
statistics remain Platform; Task 15 reconstructs the original statistics,
including H1/H2 sums, from owned results with compatible wrappers retaining
the owned result-class identity. This conservative summary is not a claim of
parity with that research dictionary.

## Product wire and example

The complete synthetic request is tests/fixtures/product/daily.json with daily-calendar.json. Inputs are exactly positions and pricing; an explicit corporate_actions tape is required. Settings contain mode, config, layout, decision_clocks, decision_timing and fee_model; unknown fields fail. Decimal config values, weights, prices, liquidity and fee rates are decimal strings; clocks are exact UTC-nanosecond strings.

Python layout.liquidity_units remains a mapping; the wire uses [{"column":"amount","unit":"CNY"}] to separate dynamic column names from monetary keys. Duplicate columns, unknown record fields and unrepresentable units fail. fee_model accepts only null, fixed detailed or dated structures, never module paths. portfolio_value equals initial cash. The product is restricted to CNY, Asia/Shanghai and explicit raw/adjusted share units.

run_daily has no policy/scenario/flow/risk/forecast transformation and no checkpoint/restore. Ideal rejects trading controls; capacity accepts liquidity/participation limits, general or side-specific tradability, execution windows and zero-fill abort, but rejects `enforce_price_limits`, `enforce_listing_status`, `enforce_t1`, non-null `round_lot`/`sell_round_lot`, corporate actions and fees before execution. Capacity requires `unfilled_buy_action=keep_cash` and `unfilled_sell_action=keep_position`; alternatives are rejected; it has no share/cash/fee ledger; adjusted/sequenced retain the original modeled cash/share path. Each return requires complete opening and closing valuations. The fresh run opens with finite positive configured cash and no holdings or receivables. Under the default valuation policy, later interval endpoints require positive finite current marks for actual held shares and outstanding stock rights on both adjacent ledger dates. Future targets and exited zero-share symbols do not require marks. A missing mark makes that interval and the next interval unknown; support resumes after two complete endpoints. Original carried NAV/returns remain unchanged in raw owner tables. Adjusted/sequenced reject active `enforce_listing_status` before execution because the preserved buy path does not enforce it.

## Installed synthetic example

Run the committed synthetic fixture using the matching ordinary wheels:

```sh
quant-backtest capabilities python.daily
quant-backtest run-manifest tests/fixtures/product/daily.json \
  --artifact-root tests/fixtures/product --output-root "$DAILY_OUTPUT"
```

The neutral adapter preserves explicit liquidity selectors and their unit declarations; it disables the legacy parser's automatic `amount` addition. A custom `turnover_cny` column needs only its own CNY unit, with no `amount` column. Direct legacy parser defaults remain unchanged.

## Held-position endpoint coverage

`ExecutionAdjustedNavResult.valuation_marks` is an additive optional DataFrame
(default `None` for older constructors). Successful ideal, adjusted and sequenced
owners emit one row per `daily` row, after execution, directly from the live
shares, cash and rights ledger. No targets or fills are replayed to infer holdings.
The original daily, order, fill, cash and corporate-action arithmetic is unchanged.

Rows contain `trade_date` (the same YYYYMMDD label as `daily`), `held_symbols`,
`held_count`, `stock_receivable_symbols`, `required_marks`, `current_marks`,
`missing_symbols`, `cash_complete`, `receivables_complete`, `endpoint_complete`
and `reason`. Symbol collections are sorted tuples (arrays on the JSON wire).
Required marks cover the union of positive held shares and positive outstanding
stock rights. Under the default `current_mark_only` policy, only the current supplied finite
positive quote certifies an endpoint. A cached last price may preserve raw NAV
but does not count as a current mark. The explicit suspension policy below can
certify an endpoint using separately reported carried-price evidence.

Cash and cash/stock receivable amounts must be finite. A known cash receivable
after selling the shares needs no stock quote. Pending stock rights still need
their current raw mark; existing corporate-action rejection rules remain active.
Success reasons are `current_marks`, `cash_only` or `cash_and_receivables`.
Failures are semicolon-separated `missing_current_price`,
`invalid_position_quantity`, `nonfinite_cash` or `nonfinite_receivable`.

`run_daily` fails closed when owner coverage is absent and rejects misaligned
rows. It certifies an interval only when both adjacent endpoints are complete,
using the known fresh-run cash state for the first opening endpoint. Recovery
therefore leaves the return from the last incomplete endpoint unknown. This
evidence checks supplied prices, not their independent source authenticity.
The product preserves `valuation_marks` in raw `tables` and `owner_tables`;
the normalized economic `valuations` event ledger remains unavailable. Capacity
has no such ledger and does not gain valuation certification.


## Explicit suspension valuation {#explicit-suspension-valuation}

`ExecutionSimConfig` accepts three optional fields. Old `daily-input.v1`
manifests may omit all three and retain the default behavior.

| Field | Default | Opt-in requirement |
| --- | --- | --- |
| `valuation_policy` | `current_mark_only` | `suspended_last_quote` |
| `valuation_suspension_col` | `None` | A normalized, nonempty separate Boolean column |
| `valuation_max_stale_sessions` | `None` | A positive integer, excluding Boolean values |

The opt-in applies only to `adjusted`/`sequenced` replay using adjusted synthetic
total-return units, with no corporate-action events. Raw-share, ideal and capacity
requests reject it. Referenced action tapes are loaded and checked before
execution; only an empty tape is accepted. Direct `simulate_execution_adjusted_nav` callers must pass
`price_basis="adjusted"` and leave `corporate_actions=None`; direct adjusted `()`
retains its existing rejection. A suspension column must differ from the price
and general/directional tradability selectors. It is a caller assertion of
suspension, never inferred from a missing quote or blocked buy/sell permission.
On the wire the selected column is required on each pricing row and accepts
Boolean or null values. Missing rows, nulls and unknown native values do not
prove suspension; only an actual Boolean `True` qualifies.

For example, synthetic callers can explicitly choose:

```python
config = ExecutionSimConfig(
    enabled=True,
    valuation_policy="suspended_last_quote",
    valuation_suspension_col="is_suspended",
    valuation_max_stale_sessions=2,
)
```

A positive finite current quote always wins. With no valid current quote, an
actual held symbol qualifies only when its suspension flag is explicitly true,
the live ledger already holds a positive finite cached price matching the
latest actual strictly prior valid quote, and its age does not exceed the
configured limit. Age counts all supplied replay sessions, including sessions
with no quote for that symbol; the previous session has age 1. The owner checks
only strictly prior dates and never substitutes a future observation.
`prepare_execution_tables` must enable the policy and use the suspension selector
declared by the replay; tables prepared without this evidence are rejected.

This policy attests existing ledger valuation and changes no cash, holdings,
fees, target sizing, fill logic or executable price. A missing executable quote
still produces no fill. Suspended prices can be stale; a complete endpoint means
complete **under the declared policy**, not independently verified fair value or
liquidation proceeds. Corporate actions, stock rights, delisting recovery values
and unknown suspension metadata are outside this opt-in. Raw-share support would
need a separate corporate-action and rights valuation contract.

`valuation_marks` additionally reports `valuation_policy`,
`policy_valued_symbols`, `policy_quote_dates`, `policy_quote_ages` and
`unresolved_symbols`. The policy symbols are sorted; quote dates (ISO date
labels) and integer session ages are parallel tuples in the same symbol order.
Empty collections are `()`, represented as arrays on JSON transport, so columns
remain compatible with Parquet even when all rows have no carried marks.
Numeric ages use decimal strings on the product result wire. `current_marks`
and `missing_symbols` retain their current-quote meanings; a carried symbol
remains in `missing_symbols` but leaves `unresolved_symbols`. The success reason
`suspended_last_quote` identifies carried evidence; incomplete mixed endpoints
can also include `missing_current_price`. Both adjacent endpoint requirements
still apply to summary returns. The normalized `valuations` event table remains
unavailable.
