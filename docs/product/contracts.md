# Product contracts

[简体中文](contracts.zh-CN.md)

SDK 0.3.0 adds immutable product envelopes in `quant_backtest_engine.product`.
It remains a standard-library-only, Python 3.11+ distribution named
`quant-backtest-engine-client`. These schemas describe requests and evidence;
they do not install a financial backend or extend Rust capabilities.
The [native client](../python-client.md) retains its existing v1/v2 contracts
and NautilusTrader 0.66.0 identity checks.

## Parse and preserve exact values

```python
import json
from pathlib import Path
from quant_backtest_engine.product import loads_manifest, manifest_to_json

# Synthetic repository fixture, copied with its calendar artifact.
manifest = loads_manifest(Path("fixtures/product/rust-session.json").read_text())
wire = manifest_to_json(manifest)
assert wire["clocks"]["available_ns"] == "1760000000000000001"
assert wire["clocks"]["decision_ns"] == "1760000000000000002"
print(json.dumps(wire, sort_keys=True))
```

`parse_manifest(mapping)` and `parse_result(mapping)` validate decoded objects.
`loads_manifest(text)` and `loads_result(text)` also reject duplicate JSON keys
at every depth. A previously decoded mapping cannot recover discarded duplicate
keys. Unknown DTO fields, missing fields (including explicit nullable fields),
nonfinite numbers, invalid literals and duplicate named entries are rejected.
DTO constructors enforce the same value rules. `manifest_to_json` and
`result_to_json` return fresh mutable wire dictionaries and lists.

DTOs are frozen dataclasses. JSON subtrees are copied recursively into read-only
mappings and tuples; neither the original input nor a codec result can mutate a
stored snapshot. `JsonValue` names wire scalars/lists/dicts and
`FrozenJsonValue` names immutable scalars/tuples/mappings.

## Manifest schema

Every object field below is required on the wire; nullable values use JSON
`null`. The schema field is exactly `backtest-product.v1`.
Named tuple pairs in Python encode as JSON objects: `model_versions`,
`inputs`, `units`, `tapes`, and provider `dependencies`.
This is not an array-of-pairs wire format.

| Field | Wire value |
| --- | --- |
| `backend_id`, `input_schema` | Explicit backend registry key and input profile |
| `required_capabilities` | Unique array of capability strings |
| `model_versions` | Object mapping model names to versions |
| `inputs`, `inline_inputs` | Named artifact references and named JSON inputs; names cannot overlap |
| `currency`, `share_basis` | Uppercase three-letter currency; `raw` or `adjusted` |
| `calendar`, `timezone` | Artifact reference; installed IANA timezone |
| `units` | Object mapping field/dimension names to explicit units |
| `clocks` | The seven-field clock object below |
| `initial_account`, `settings` | Profile-specific JSON objects |
| `tapes` | Named artifact references or inline arrays; an empty array is explicit |
| `policy` | `{id, version, state_schema, config}` or null |
| `forecast`, `risk` | Artifact reference or null |
| `scenario` | Scenario identity or null |
| `output_uri` | Output reference, resolved later by a trusted execution context |

An artifact is `{uri, sha256, media_type}`; its digest is lowercase SHA256 of
the exact artifact bytes. Parsing does not read files or fetch URLs.
The synthetic fixture includes `synthetic-calendar.json` with its actual digest.
The runner must resolve paths inside its trusted artifact root and verify bytes.

A policy ID is a fixed lowercase registry key containing letters, digits, hyphens
or underscores. It cannot be an import path such as `os.system` or `os:system`.
Backend keys may also contain dot-separated segments. Keys never cause an import
or execution here; a backend registry must explicitly resolve them.
Requests have no executable-command or serialized-code field.

A scenario is `{id, family, seed, base_input_sha256, transformation_sha256,
forecast_mode}`, where seed is an integer (not a boolean), digests identify
the supplied inputs/transformation, and forecast mode is `fixed` or `recomputed`.
Each scenario must have independent accounts and state in its financial owner.

## Clocks and units

`ClockSet` contains `available_ns`, `information_ns`, `decision_ns`,
`entry_ns`, `effective_ns`, `report_ns`, and `valuation_ns`.
Each is a canonical integer string in UTC nanoseconds, or null when that clock is
semantically unavailable. Negative epochs are representable. Numeric JSON clocks,
fractional/exponential strings, whitespace and leading zeroes are rejected.
`"1760000000000000001"` and `"1760000000000000002"` remain distinct.

The generic clock object imposes no total ordering. For `rust-session.v1`,
the available pairs enforce information ≤ decision ≤ entry and available ≤
decision. Null clocks omit only that unavailable relation. Effective, report and
valuation clocks can describe unrelated events and are not ordered against those
four. Session open ≤ session valuation is a separate profile relation.
An order's information time is not required to precede the session open: native
eligibility against later quotes remains the native engine's responsibility.

Monetary transport uses finite decimal strings: `"0.22"` remains `"0.22"`;
`0.22`, `"NaN"` and exponent notation are rejected for economic columns.
The profile also uses decimal strings for quantities and basis points. The shared
economic column names are exposed as `validation.DECIMAL_FIELDS`; generic JSON
objects may carry other integer/finite-float metadata. Backend row schemas must
declare additional economic columns explicitly; naming a new metadata field
does not establish financial semantics. A `cash: CNY` unit declaration is explicit
and compared with the selected provider's declared units. Currency, share basis,
calendar and timezone remain separate fields.

Native v1/v2 integer clocks are unchanged. The [optional adapter](backends.md) converts string
nanoseconds directly to Python integers, never through floats or JavaScript
numbers, and validates the resulting native request.

## rust-session.v1 input profile

This SDK profile validates the following complete shape, without claiming an
installed executable adapter. The fixture mirrors `fixtures/sessions.json`
with clocks converted exactly to strings.

| Location | Required keys and values |
| --- | --- |
| `inputs` plus `inline_inputs` | Exactly one `instruments` input, artifact-backed or inline array |
| Each instrument | `symbol` string; `price_precision` integer 0–4; `buy_lot` integer 1–1,000,000 |
| `initial_account` | `cash` decimal string |
| `settings` | `fee_bps` decimal string; `enforce_t1` boolean |
| `tapes` | Exactly `sessions`: artifact reference or array |
| Each session | `session_date` ISO date; `open_ts_ns`, `valuation_ts_ns` string clocks; `quotes`, `orders` arrays |
| Each quote | `symbol`; `ts_ns` string clock; `bid`, `ask`, `bid_size`, `ask_size` decimal strings; `tradable`, `limit_up`, `limit_down` booleans |
| Each order | `id`, `symbol`; `information_ts_ns` string clock; `side` buy/sell; `quantity` decimal string |

All keys in these profile objects are required, and additional keys are rejected.
Instrument symbols must be unique. Explicit `"sessions": []` is valid schema
representation; missing sessions is rejected. Whether a run with no sessions is
executable remains a native/backend decision.

For an artifact-backed input/tape, SDK parsing checks only reference structure and
required-name presence. After hash-checked loading, the adapter must substitute
the content and call `validate_rust_session` again, then apply native semantic
validation. No artifact content has been validated merely by parsing its URI.

Unknown input schemas can be represented by generic DTOs. They have no profile
validation or execution permission. `require_capabilities(manifest, descriptor)`
rejects unregistered schemas, a mismatched backend, unsupported input/result
schemas, missing capabilities, or unsupported units. It never unions different
providers' capabilities or falls back to Python. A descriptor contains
`identity, input_schemas, result_schemas, checkpoint_schemas, capabilities, units,
restrictions`; restrictions are declarative explanations, enforced by the backend.

## Results and economic evidence

`ProductResult` has schema `backtest-product-result.v1` and required fields
`status, manifest_sha256, provider, tables, summary, raw_result, normalization,
failure, scenario`. Status is completed, failed or partial. Completed results
have null failure; failed/partial results require failure information.
`summary` is a JSON object. `raw_result` is an artifact reference or null;
`scenario` is the scenario identity or null. Table names are unique.

Every `EvidenceTable` is `{name, status, rows, reason}`.
Available evidence has an array of JSON object rows and null reason.
An empty available array means the table is supported with zero observed rows.
Unavailable evidence has no rows and a nonempty reason, for example:

```json
{"name": "rights", "status": "unavailable", "rows": [], "reason": "not reported by this provider"}
```

Unavailable is not a zero balance, an empty supported ledger, or a derived fill.
The registry lists evidence categories, not capabilities that every provider has:

| Table | Evidence category |
| --- | --- |
| intents | Requested actions |
| admissions | Accepted or rejected requests |
| cancellations | Cancellation events |
| fills | Actual executions |
| fees | Cash charges |
| cash | Cash movements and balances |
| positions | Position observations |
| reservations | Reserved cash or quantities |
| reports | Provider reports |
| rights | Corporate-action entitlements |
| receivables | Recognized amounts not yet received |
| valuations | Valuation observations |
| capital_flows | Deposits and withdrawals, separate from PnL |
| daily | Daily aggregates |

Rows are JSON objects; this registry does not prescribe a universal ledger column
set. The selected provider and normalization source schema define row columns and
their accounting meaning. Never fill unsupported columns with invented zeros.
Impact already in fill price and cash fees are charged once; descriptive
benchmark/opportunity shortfall is not another debit.

`NormalizationReceipt` contains schema `backtest-normalization.v1`,
`adapter_version, source_schema, source_sha256, unavailable_fields`.
Its source digest identifies the exact normalized source bytes.
`FailureInfo` contains `code, message, stage, last_successful_cursor`; the cursor
is a nonnegative integer or null. This envelope does not implement checkpoint
recovery or permit another checkpoint from a poisoned financial owner.

## Provider identity and ownership

`ProviderIdentity` has `backend_id, distribution, version, source_revision,
source_sha256, dependencies, artifact_sha256`. Unknown Git provenance is null;
a wheel or executable hash belongs in `artifact_sha256`, never in
`source_revision` or mislabeled as a source digest. At least a source-closure
digest or executable/wheel digest is required. A supplied Git revision is a full
40-character lowercase revision; parsing checks representation, not repository
provenance. Runtime v9 later needs stronger exact provider/dependency closure.

| Owner | Responsibility in this SDK addition |
| --- | --- |
| `quant_backtest_engine.product` | Immutable DTOs, strict codecs, input profile checks, capability comparison |
| Existing `EngineClient` | Pinned native process transport and unchanged native evidence validation |
| Explicit financial backend | Execution, accounting, loaded artifact validation and provider-specific semantics |
| Consumer / optional runner | Trusted artifact roots, persistence and registered policy/backend selection |

The [ownership registry](../migration/reusable-ownership.json) keeps this addition
planned until a reviewed source revision is recorded. Existing migration rows
remain planned. No core/Platform/Runtime import, matching engine or extra cash
ledger is added by the SDK.
