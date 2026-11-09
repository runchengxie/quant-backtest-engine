# Transaction cost evidence

Language: English · [简体中文](transaction-cost-evidence.zh-CN.md)

`quant_backtest_core.evidence.transaction_costs.audit_transaction_costs` audits terminal
parent orders and physical fills. It calculates modeled brokerage fees and signed
benchmark shortfalls. It never matches orders, invents fills, debits an account, or
promotes a calibration to production. Inputs and the existing cost-scope defaults
remain unchanged.

```python
from quant_backtest_core.evidence.transaction_costs import audit_transaction_costs

report = audit_transaction_costs(
    parents,
    fills,
    billing="parent",
    commission_bps=3,
    minimum_commission=5,
    sell_tax_bps=10,
)
observations = report.cost_observations(fee_basis="modeled")
```

These example terms are synthetic mechanics, not a broker tariff. Caller-owned
versioned terms must describe the actual intended billing convention.

## Normalized inputs

Inputs are pandas DataFrames. Identifiers are nonempty strings, timestamps are
nonnegative integer UTC nanoseconds, prices are positive CNY per raw share, and
requested/fill quantities are positive integer raw shares. No lot conversion,
foreign currency conversion, signed negative quantities, or fractional-share
contract is implied. Use nullable integer/object columns when clocks are missing,
so pandas does not coerce valid integer clocks to floating point.

Required parent columns:

| Columns | Meaning |
| --- | --- |
| `parent_id`, `side`, `requested_shares` | Unique parent, `buy`/`sell`, original requested shares |
| `reference_price`, `reference_ns`, `reference_available_ns`, `decision_ns` | Reference quote and availability, both no later than the decision |
| `arrival_price`, `arrival_ns`, `arrival_available_ns` | Arrival quote and clocks. Missing prices may retain known clocks |
| `completed_ns`, `available_ns`, `status` | Terminal execution interval, availability of the entire evidence record, `completed`/`cancelled` |
| `source_binding`, `evidence_kind` | Caller source identity, `synthetic`/`broker_fills` assertion |
| `quantity_unit`, `currency` | Exactly `shares`, `CNY` |
| `price_convention` | Exactly `includes_spread_and_impact` |
| `brokerage_terms_version` | Caller identifier for the supplied brokerage terms |

`completed` means the parent execution interval has ended, not that every
requested share filled. Cancelled and zero-fill parents remain in `report.parents`.
Reference availability precedes the decision. An available arrival quote follows
the decision and precedes completion. Quote availability may follow its quote
clock, but all quote, fill receipt and benchmark availability clocks must be no
later than parent `available_ns`. Filled shares cannot exceed requested shares.

Optional parent evidence:

| Columns | Meaning |
| --- | --- |
| `opportunity_price`, `opportunity_ns`, `opportunity_available_ns`, `opportunity_benchmark` | Positive terminal benchmark, horizon at/after completion, availability and explicit benchmark name. An unknown price may retain the declared horizon and availability clocks |
| `market_volume_shares`, `market_amount_cny` | Same execution interval volume and amount, nonnegative when present |
| `liquidity_start_ns`, `liquidity_end_ns`, `liquidity_available_ns` | Start equals arrival when known, end equals completion, availability follows the end |
| `liquidity_quantity_unit`, `liquidity_amount_unit` | Exactly `shares`, `CNY` when interval liquidity is supplied |
| `liquidity_bucket`, `execution_minutes` | Explicit caller scope label and positive integer minute window used by the existing fitter |
| `cluster_id` | Caller-defined date/order cluster label for the uncertainty API |

Both positive volume and positive amount, unit declarations, interval clocks and
scope labels are needed to produce a participation observation. Missing or zero
liquidity returns `participation=None`, never an inferred liquid market. Amount
and volume units are checked by declaration, not independently verified against
a market-data provider. Minute-window labels likewise require caller validation
against their execution policy and interval definition.

Required fill columns are `fill_id`, `parent_id`, `child_id`, `price`, `shares`,
`fill_ns`, `receipt_ns`, `source_binding`, `evidence_kind`, `quantity_unit`, `currency`.
Each child belongs to one parent. Fill clocks lie within the parent interval,
receipt is no earlier than fill, and receipts are available by the parent record
clock. Source/evidence assertions must match their parent.

`fill_id` identifies one physical fill globally within the audit. Identical
physical reports are deduplicated regardless of row order or receipt order,
retaining the earliest valid receipt. Conflicting physical payloads fail. Numeric
price/share representations are normalized before this comparison. An empty
fills table must still contain its required columns.

Optional fill columns `recorded_commission` and `recorded_tax` are already
allocated CNY-cent fees for that physical fill, not repeated whole-parent bills.
Both must be present for every unique fill to produce a parent recorded-fee total.
An explicit zero tax is required even for buys. Missing recorded fees remain
unknown. Recorded values are caller evidence, not independently authenticated
broker records.

## Fees and attribution

For each billing group, calculate notional `N = sum(price * shares)`, commission
`round_cent(max(minimum_commission, N * commission_bps / 10000))`, and sell-only
tax `round_cent(N * sell_tax_bps / 10000)`. Decimal arithmetic uses half-up cent
rounding separately for each commission and tax bill. `billing="parent"` groups
all child fills and charges one minimum. `billing="child"` groups by child id,
with one minimum and separately rounded tax per child. Zero-fill groups incur no
modeled fee. Other billing rules, rebates and negative fee rates are unsupported.

`modeled_commission`, `modeled_tax`, `modeled_cash_fees` are estimates under these
terms. `recorded_cash_fees` is the deduplicated recorded allocation total or
`None`. `fee_evidence` is `caller_recorded` or `unavailable`. Reporting values are
floats for analysis, not an exact-cent account ledger.

With `s=+1` for buys and `s=-1` for sells, `q` filled shares, `Q` requested shares,
`N` fill notional, reference `R`, arrival `A` and terminal benchmark `H`:

| Output | CNY definition |
| --- | --- |
| `reference_price_shortfall` | `s * (N - q * R)` |
| `arrival_price_shortfall` | `s * (N - q * A)` |
| `delay_shortfall` | `s * q * (A - R)` |
| `reference_shortfall_with_modeled_fees` | Reference price shortfall plus modeled fees once |
| `reference_shortfall_with_recorded_fees` | Reference price shortfall plus recorded fees once, or unknown |
| `opportunity_shortfall` | `s * (Q - q) * (H - R)`, descriptive only |
| `completion`, `unfilled_shares` | `q/Q`, `Q-q` |

Signed improvement can be negative. Missing arrival/terminal benchmarks produce
`None` and `unavailable_reasons`, including for zero-fill parents. Opportunity
shortfall cannot change any fee or cash balance. Changing the terminal benchmark
changes only that descriptive benchmark comparison.

Arrival and delay sum algebraically to the filled reference price comparison.
They overlap with that comparison and do not establish causal spread, delay or
impact estimates. `attribution_additive=False` prevents treating all displayed
components as independent costs. Execution prices already include crossing and
impact. No additional spread/impact cash debit is calculated. A fee embedded into
price is equivalent only when callers explicitly use zero corresponding cash
fees and consistent prices. A recorded fee and modeled fee are alternative
bases, never summed.

## Existing scope fitting and clustered uncertainty

`cost_observations(fee_basis="modeled"|"recorded")` adapts supported filled
parents for existing `fit_cost_scope` and `validate_cost_scope`. It excludes zero
fills, unavailable participation and unavailable chosen fee evidence. Other
parents remain visible in the full completion/opportunity table. Observation
shortfall is `10000 * chosen_reference_shortfall / (reference_price * filled_shares)`.
`filled_notional` remains execution notional for fitting weights. Parent source
identity, evidence kind, digest, cluster id and explicit fee basis travel with the
observations. Callers must keep these scopes separate when fitting.

Existing fitting uses records available by its cutoff and enforces completion
before availability. Later validation freezes coefficients and preserves
source/side/liquidity/window/participation support checks. The existing definition
of holdout is later availability, which can include late reports of earlier
executions. It is not automatically a genuinely unseen market interval.

The additive `cost_scope.validate_cost_scope_uncertainty` API accepts the same
model/observations/source binding plus `cluster_column`, `cluster_kind="date"` or
`"order"`, `min_clusters=3`, `bootstrap_samples=1000`, and `seed=0`. It retains the
legacy point estimates and unsupported counts, then resamples whole supported
clusters with replacement, retaining notional weights. It reports percentile 95%
intervals for signed residual bias and RMSE, conditional on the frozen fit.
Independent-cluster count replaces row count for sufficiency. Absent/blank cluster
labels return `unavailable_clusters`, too few clusters return
`insufficient_clusters`, and both leave intervals `None`. The minimum is an
engineering guard, not a power or coverage guarantee. At least 100 draws are
required. A fixed seed and sorted cluster labels make resampling repeatable.

The caller must justify cluster independence, including common-date effects
across orders. Cluster labels do not establish independence. Intervals do not
cover coefficient-estimation uncertainty, model selection or future market
probabilities. The API neither refits using later data nor promotes the model.

`source_digest` binds canonical parsed input records, all receipt reports,
additional scalar columns and numerical fee terms, independent of row order.
It is not a hash of an original file's bytes. Callers retain raw-byte digests,
provider provenance, code/consumer revisions and versioned term records in their
own evidence manifest. Neither the label `broker_fills` nor a good synthetic fit
verifies provenance. Reports always return `provenance_status="caller_asserted"`
and `real_calibration="unavailable"`. No broker-record verification, historical
queue identification, permanent-impact calibration or new OOS claim is provided.
