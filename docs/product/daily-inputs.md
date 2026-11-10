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
solely in `ExecutionSimConfig`. Its parser and class are transferred unchanged
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

The complete synthetic request is fixtures/product/daily.json with daily-calendar.json. Inputs are exactly positions and pricing; an explicit corporate_actions tape is required. Settings contain mode, config, layout, decision_clocks, decision_timing and fee_model; unknown fields fail. Decimal config values, weights, prices, liquidity and fee rates are decimal strings; clocks are exact UTC-nanosecond strings.

Python layout.liquidity_units remains a mapping; the wire uses [{"column":"amount","unit":"CNY"}] to separate dynamic column names from monetary keys. Duplicate columns, unknown record fields and unrepresentable units fail. fee_model accepts only null, fixed detailed or dated structures, never module paths. portfolio_value equals initial cash. The product is restricted to CNY, Asia/Shanghai and explicit raw/adjusted share units.

run_daily has no policy/scenario/flow/risk/forecast transformation and no checkpoint/restore. Ideal rejects trading controls; capacity accepts liquidity/participation limits, general or side-specific tradability, execution windows and zero-fill abort, but rejects `enforce_price_limits`, `enforce_listing_status`, `enforce_t1`, non-null `round_lot`/`sell_round_lot`, corporate actions and fees before execution. Capacity requires `unfilled_buy_action=keep_cash` and `unfilled_sell_action=keep_position`; alternatives are rejected; it has no share/cash/fee ledger; adjusted/sequenced retain the original modeled cash/share path. Row valuation completeness uses a conservative sufficient condition: every target symbol has a positive finite current mark on every ledger date. Missing evidence keeps summary returns unknown.

## Installed synthetic example

Run the committed synthetic fixture using the matching ordinary wheels:

```sh
quant-backtest capabilities python.daily
quant-backtest run-manifest fixtures/product/daily.json \
  --artifact-root fixtures/product --output-root "$DAILY_OUTPUT"
```
