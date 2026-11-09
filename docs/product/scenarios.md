# Independent scenario execution

[简体中文](scenarios.zh-CN.md)

Core 0.2.0 composes trusted local scenario callbacks into actual `python.minute`
targets. Install the explicit `[scenario]` extra. Provider B source and wheels
require whole-provider review and integration before consumer cutover; the version
alone is not a merged release identity.

```sh
python -I -B examples/product/scenarios.py --output-root "$DATA_ROOT/scenario-example"
```

The output directory must be new. The executable example runs A, an unsupported
middle case, B, and a fixed B control. Each account starts with CNY `1000` and
historical target `0`. Earlier synthetic closes `9` and `11` make the external
callback return `0` and `1`. Both decision marks and later fill prices are `10`.
B buys `100` shares and ends with cash `0`; A and fixed B do not buy. The middle
case fails before financial dispatch and B still runs. The 09:33 bar starts at
09:32:30, strictly after 09:31 entry plus one-minute latency. Volume `1000`,
participation `1`, lot size `1`, explicit limits/tradability/calendar and zero
fees, tax and impact make this a hand-checkable fixture. It is not market evidence.

## API and capability boundary

```python
from quant_backtest_core.scenarios import (
    ScenarioCase, PredictionArtifacts, PredictionProvider, ScenarioAttempt, run_scenarios,
)
# ScenarioCase(identity: ScenarioIdentity, manifest: ProductManifest)
# provider.recompute(case, inputs) -> PredictionArtifacts
# PredictionArtifacts(forecast, risk, policy, provider_id, provider_version,
#                     available_ns, input_sha256)
# run_scenarios(cases, *, context, prediction_provider=None) -> tuple[ScenarioAttempt, ...]
# ScenarioAttempt(identity, status, result, failure, *, composition=None)
```

The fixed composition registry supports only `python.minute` with
`scenario-minute-targets.v1`. `risk` must be null. A returned null policy retains
the requested policy; an explicit replacement must be exactly
`{"id":"target-weights","version":"v1","state_schema":"target-weights-state.v1","config":{}}`.
No dynamic imports, commands, estimators, risk models or optimizers are instantiated.
The callback owns affected feature, prediction and decision computation. Engine
validates and projects execution-ready rows into the existing financial owner.
Raw minute and Rust runners still reject scenario/forecast/risk transformations.

`ScenarioIdentity.forecast_mode` must explicitly be `recomputed` or `fixed`.
Families are `external-market-path` and `execution-perturbation`; these are caller
interpretations, not verified transformation algorithms. Recomputed mode requires
a supplied trusted callback. Fixed mode retains the explicit requested targets;
forecast may be null or a valid typed artifact whose rows equal those targets
exactly. A fixed typed artifact is validated without invoking the callback.
Unsupported original or returned artifacts, policies, risk and backends fail.

One callback object serves the sequence: it must behave deterministically per case
or key its own state by case. It is not an independent policy factory. Every raw
run creates a fresh account, policy bridge, target policy and configured impact
instance. Case order does not create financial state dependencies. Seeds are
lineage identifiers, not requests to randomize a deterministic minute owner.

## Exact input domain

All JSON hashes use SHA256 over UTF-8, sorted object keys, compact `,`/`:`
separators, unescaped Unicode, finite numbers only, and exactly one trailing LF.
ArtifactRef hashes instead cover exact original bytes, including whitespace.
Duplicate JSON fields and nonfinite constants fail. Monetary values and UTC
nanosecond clocks remain strings; clocks never pass through floating point.

The callback `inputs` has exactly these fields:

| Field | Meaning |
| --- | --- |
| `schema` | `scenario-inputs.v1` |
| `scenario` | Exact SDK ScenarioIdentity wire object |
| `prediction_request_sha256` | Canonical hash of `resolved_manifest` |
| `resolved_manifest` | Strict SDK manifest prediction view described below |
| `calendar` | Resolved exact synthetic calendar JSON value |
| `sources` | Source descriptors for calendar, input artifacts and tape artifacts |

Each source descriptor has exactly `pointer`, `reference`, `snapshot`, `sha256`.
The pointer names its original manifest field (`/calendar`, `/inputs/<name>` or
`/tapes/<name>`). Both refs are standard `{uri,sha256,media_type}` objects; the
snapshot URI is `artifacts/<sha256>.json` within the case source root. Its hash
binds the preserved original bytes. Inline inputs are bound by the envelope hash.

The prediction view normalizes the case identity, resolves every input and tape
artifact into inline JSON, preserves all other declarations and replaces the
calendar ref with its same-byte snapshot ref. Only `forecast` is nullified to
exclude output evidence from its own input hash. Forecast source descriptors and
any full-request hash that transitively contains that ref are excluded from this
hashed domain. `risk` must already be null; scenario, policy, account, market,
tapes, settings, units, clocks and required capabilities remain bound.

The detached ScenarioCase passed to the callback contains exactly the same
manifest as `inputs.resolved_manifest`. The receipt separately retains full
original and normalized requested manifests and hashes, including original
forecast refs and snapshot bytes. Changing only the attached forecast URI/hash
changes full request identity but not the prediction-view hash; changing a
nonforecast input changes the input hash. This permits constructing a fixed typed
artifact from the view and attaching it without a self-referential hash cycle.
Callback-visible values are detached and compared after invocation; observed
mutation or changed artifact bytes fails before owner dispatch.

## Typed target artifact

The forecast must reference `application/json`, at most 16 MiB of exact bytes, with exactly these fields:

| Field | Contract |
| --- | --- |
| `schema` | `scenario-minute-targets.v1` |
| `scenario` | Exact case identity |
| `provider_id`, `provider_version` | Nonempty strings equal to returned PredictionArtifacts |
| `available_ns` | Canonical integer string equal to returned and requested availability |
| `input_sha256` | Exact pre-callback envelope hash, equal to returned input hash |
| `targets` | Nonempty list of strict target rows |
| `source_records` | Nonempty declared source list |
| `consumed_inputs` | Nonempty source-pointer list |

Target rows require `information_time`, `decision_time`, `entry_time`, `symbol`,
`weight`; only optional `order_type` is allowed. Weight is an SDK decimal string.
Each clock is a canonical UTC nanosecond integer string. This initial profile has
one availability cut and one explicit information/decision/entry clock triplet;
all target rows must match the manifest clocks. It requires
`information <= availability <= decision <= entry`; existing owner timing and
market validation remain stricter where applicable.

Source records have exactly `{id, kind, sha256}`; IDs are unique, kind is
`implementation`, `dependency` or `artifact`, and SHA256 is lowercase hexadecimal.
These are caller declarations, not verified dependency/source authenticity.
The actual callback class file is separately measured and copied when inspectable;
a class file hash does not establish its hidden dependency closure or instance state.

Consumed records have exactly `{pointer, sha256, available_ns}`. The pointer must
identify an entire row `/resolved_manifest/inline_inputs/bars/<canonical-index>`;
its SHA256 covers that row's canonical JSON. Duplicate pointers and unresolved,
noncanonical or differently hashed pointers fail. `available_ns` must equal the
supplied bar `time` and must not exceed returned availability. This is the explicit
`synthetic-bar-close-convention.v1`: event-time equality is verified, while data
arrival/availability is a declared synthetic convention. It is **not independently
observed real data availability**. Arbitrary field pointers and real arrival-time
carriers are outside v1. The complete input still contains future execution bars;
a trusted callback is not sandboxed and this evidence is not a proof against
hidden look-ahead, external state, or omitted dependencies.

## Projection, files and receipt

All cases and source artifacts are snapshotted before any callback runs. Each
case reserves `case-<canonical-identity-sha256>/` exclusively beneath output_root.
The source and output roots must be disjoint and contain no symlink aliases.
Duplicate case IDs, existing namespaces, noncanonical paths and escapes fail
without overwrite. Each namespace contains `sources/`, `execution/` and
`receipt.json`. Source refs are relative to `sources/`; owner result refs remain
relative to `execution/`. `ScenarioAttempt.composition` is relative to the outer
output root. Use a fresh outer root for deterministic reruns.

Projection removes superseded artifact/inline target bindings and installs the
exact validated rows. It materializes other inputs/tapes without changing values,
retains capabilities/account/settings/units/clocks, and moves scenario/forecast/risk
into composition evidence before setting those raw fields null. No arithmetic,
rounding, optimizer or financial ledger is added. The original owner ProductResult
object and both output files remain unchanged: executed manifest SHA, null raw
scenario and native-result SHA. There is no invented `run_sha256`.

The strict `scenario-composition.v1` receipt has exactly the following fields;
nullable fields are null when their stage was not reached:

| Fields | Evidence |
| --- | --- |
| `schema`, `identity`, `status`, `stage` | Schema, exact case, completed/failed and last stage |
| `original_manifest`, `original_manifest_sha256` | Submitted manifest and canonical identity |
| `requested_manifest`, `requested_manifest_sha256` | Identity-normalized request and hash |
| `prediction_request_manifest`, `prediction_request_sha256` | Exact callback case view and hash |
| `input_view_projection` | `{removed:["forecast"],reason}` defining self-reference exclusion |
| `source_artifacts` | Full source descriptors, also including original `/forecast` when supplied |
| `callback_inputs`, `callback_input_sha256` | Actual pre-callback envelope and canonical hash |
| `prediction` | Exact PredictionArtifacts fields or null |
| `target_artifact` | `{reference,snapshot,payload,sha256,source_records_status,consumed_inputs_status,availability_status,validation_status}` |
| `callback_source` | `{status,type,sha256}` and inspectable file `snapshot` ref; otherwise unavailable |
| `lineage` | `{status,base_input_sha256,transformation_sha256,reason}`; always declared without payload carriers |
| `projection` | List of `{field,requested,executed}` for every changed manifest field |
| `adapter` | `{id,version,source_sha256,source_files}`; canonical map of actual contracts/runner file SHA256 |
| `executed_manifest`, `executed_manifest_sha256` | Actual raw owner request and hash |
| `owner_call` | `{callable,manifest_sha256,artifact_root,output_root}` identifying the sole raw call |
| `owner_result` | Unchanged SDK ProductResult JSON, including installed provider/source identity |
| `failure` | Original SDK FailureInfo `{code,message,stage,last_successful_cursor}` or null |
| `last_successful_checkpoint`, `checkpoint_scope` | Null and unavailable: this raw runner does not expose saved checkpoints |
| `trust` | Trusted callback and hidden-state limitation |

Returned target bytes are snapshotted before schema/clock validation. Rejected payloads retain `validation_status=rejected`, unverified consumption/availability, and no owner call. Accepted payloads record `validation_status=accepted`; the measured byte SHA remains separate from the declared ref SHA. Path, read, size or hash failures may leave target evidence unavailable and never fabricate a snapshot ref.

The receipt's ArtifactRef hashes its exact persisted bytes; the receipt does not
contain its own hash. Canonical manifest/input identities and raw artifact hashes
are distinct. Base/transformation digests remain caller-declared lineage. Repeated
synthetic paths are not independent observations or probabilities.

Ordinary preparation, callback and owner errors retain one failed attempt and let
later cases execute. The original failure is never replaced by a checkpoint request
on a poisoned owner. Cancellation propagates. Receipt persistence failure returns
no fictional reference; if an owner already completed, its actual result remains
available in the failed attempt. If an earlier failure already exists, its code,
message and stage remain the original failure. Partial files are retained for
diagnosis and are not a successful publication. Durable scheduling belongs to Runtime.

For planning, see [impact planning](../concepts/impact-planning.md). Planned sales
are not cash: the supplementary funded-B control blocks only A's sale while B
remains tradable/capacious. B buys only in the control with actual spare cash.
The original Task 10 raw binary arithmetic and contingent quantities are unchanged.
