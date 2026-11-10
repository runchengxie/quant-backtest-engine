# Explicit financial backends

[简体中文](backends.zh-CN.md)

Core 0.3.0 registers `rust.nautilus.sessions`, `python.minute` and `python.daily`.
For the minute profile, explicit capabilities and resumable API, see [financial recovery](recovery.md).
The following sections describe the Rust backend.
It calls the existing `EngineClient.run_sessions` once. NautilusTrader 0.66.0 owns
execution and accounting; there is no Python cash ledger or fallback. The native
CLI, SDK identities, Rust version and native v1/v2 wire contracts are unchanged.

The initial product subset is `rust-session.v1`, CNY, raw shares,
`Asia/Shanghai`, and exactly `cash: CNY` units. Native USD support is unchanged
but is not exposed by this fixed-unit product profile. Policies, model versions,
scenario transformations, forecast/risk inputs, corporate actions, restore and
checkpoints are rejected before execution. The five declared capabilities are
`session_ledger`, `configured_t_plus_one`, `buy_lots`, `quote_trade_permissions`
and `quote_liquidity`. Installing extras does not extend Rust capabilities.

## Run synthetic sessions

Copy `fixtures/product/rust-session.json` and `synthetic-calendar.json` together
from the same source revision. The calendar profile is the exact object
`{"schema":"synthetic-calendar.v1","timezone":"Asia/Shanghai","sessions":[...]}`
with the ordered session dates in the manifest. It declares supplied sessions;
it does not generate exchange calendars or certify trading days.

```sh
"$ENV/bin/quant-backtest" run-manifest "$INPUTS/rust-session.json" \
  --artifact-root "$INPUTS" --output-root "$OUTPUTS" \
  --rust-executable "$ENGINE" --rust-sha256 "$ENGINE_SHA256"
```

`$ENGINE` is an absolute path to the separately verified Rust executable;
`$ENGINE_SHA256` is its lowercase SHA256. These are trusted host arguments, never
manifest fields. The same arguments work through `examples/product/rust_session.py`.
This 100-share CNY session fixture yields final cash and NAV `10197.8`, fees `2.2`.
The separate native quote-v1 fixture remains `10000 -> 10019.78`, fees `0.22`.

Python callers use `run_manifest(manifest, context=BackendContext(artifact_root,
output_root, rust_executable, rust_sha256))`. A backend implements `descriptor()`,
`validate(manifest, context)` and `run(manifest, context)`. Registry selection is
fixed code, never an import path or executable command from the request.

## Validation and artifacts

Artifact URIs must be relative local paths confined to the trusted artifact root.
Network URLs, absolute paths, traversal and symlinks escaping the root are rejected.
SHA256 covers exact file bytes before parsing; duplicate JSON keys and nonfinite
constants are rejected. Artifact-backed instruments and sessions are loaded and
revalidated with the SDK profile and native v2 semantic preflight. String clocks
become Python integers directly; there is no float timestamp intermediate.
Rust independently validates the request before constructing its financial owner.

The output root is separately trusted. Result `<output_uri>` and native artifact
`<output_uri>.native.json` are created exclusively; existing files, including
inputs, are never overwritten. Use a fresh output name for each run. Trusted
callers must keep these roots and their symlinks stable during execution; this is
not a sandbox for hostile concurrent filesystem writers. Native failures retain
the original exception, produce no successful result and never trigger fallback.
A persistence failure can leave a native artifact for diagnosis; do not interpret
it as a published successful result. Durable job supervision belongs to Runtime.

## Evidence and identity

| Product table | Native source |
| --- | --- |
| fills | fills |
| positions | daily_positions |
| reports | orders (terminal order states) |
| daily | daily_ledger |

All other registered tables are explicitly unavailable. Daily cash/NAV
observations do not establish a cash-movement ledger; terminal orders do not
establish admission or cancellation events. Fees remain in native fill commission
and daily evidence, with no additional debit. Normalized clocks are decimal integer
strings. Full native fields, including rejections and integer clocks, remain in
the raw artifact.

The raw artifact is the complete validated object returned by the SDK, serialized
as UTF-8 JSON with sorted keys, compact separators and one trailing newline. It is
not the original subprocess stdout. `normalization.source_sha256` hashes these exact
persisted bytes. `manifest_sha256` hashes the manifest codec output with that same
serialization; it is not the hash of arbitrary input JSON whitespace.

Provider distribution/version identify the installed core adapter. Unknown Git
revision is null. `source_sha256` hashes installed core `.py` files in sorted path
order, each relative UTF-8 path plus NUL then file bytes plus NUL. The verified
Rust executable digest is `artifact_sha256`; it is never called a Rust source digest.
SDK dependency version comes from installed distribution metadata. `required-*`
dependency keys describe required native contracts and Nautilus 0.66.0, not measured
Rust package versions. The native result validates the Nautilus identity; an
arbitrary executable hash cannot establish a Rust package version. Capability
inspection without a binary has null executable identity. Exact release/source
receipts and later Runtime dependency closure remain separate requirements.

Deterministic LOB matching/replay is implemented in provider B source, pending merged release. [LOB Python / optional PyO3 modes](../development/microstructure-rust.md).

## Provider B capability matrix

| Entry point | Supported scope | Explicit limits |
| --- | --- | --- |
| `run_manifest`, `rust.nautilus.sessions` | Native session ledger, configured T+1, buy lots, quote permissions/liquidity | No scenario, forecast/risk, Python policy or checkpoints |
| `run_manifest` / `open_session`, `python.minute` | Declared minute capabilities and exact recovery | Raw runner rejects scenario/forecast/risk transformations |
| `run_scenarios`, `scenario-minute-targets.v1` | External typed target projection into independent minute owners | One availability/decision cut, null risk, exact target-weights policy; trusted callback, declared synthetic availability |
| Planning/cost/market-path/microstructure leaf APIs | Their individually documented scope | No union-of-leaves capability claim for any raw backend |
| `python.daily` | Source implemented; release pending | `[daily]`; explicit CNY/Shanghai targets, calendars and units; no restore |

See [scenario contracts and exact receipts](scenarios.md), including declared lineage
and hidden-state limits. Core 0.3.0 source does not by itself imply merged release availability.

[Daily input contract](daily-inputs.md) and [complete owner outputs](../reference/outputs/backtest-outputs.md) describe ideal, capacity, adjusted and sequenced limits. Capacity has no cash/fee ledger; diagnostic period replay is a separate Python API, not an executable backend capability.
