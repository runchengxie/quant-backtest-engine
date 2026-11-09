# Resumable financial sessions

[简体中文](recovery.zh-CN.md)

Core 0.1.0 exposes `python.minute` through `minute-input.v1`. Install the matching
SDK 0.3.0 and `quant-backtest-core[minute]` wheels on Python 3.12 or 3.13. The SDK
validates transport using only the standard library, including on Python 3.11;
execution explicitly requires the minute extra. No Platform, Runtime or research
package is imported. Rust remains a separate, non-resumable backend.

## Open, observe, recover and finish

Copy the synthetic `fixtures/product/minute-session.json` and
`fixtures/product/minute-calendar.json` from the same revision into an input directory.
Use fresh output directories; recovery keeps the manifest unchanged.

```python
from pathlib import Path
from quant_backtest_engine.product import loads_manifest
from quant_backtest_core import BackendContext
from quant_backtest_core.sessions import open_session, restore_session

inputs = Path("inputs")
manifest = loads_manifest((inputs / "minute-session.json").read_text())
session = open_session(manifest, context=BackendContext(inputs, Path("first-output")))
observation = session.step()
checkpoint = session.checkpoint()  # bytes; persist only after a successful boundary
recovered = restore_session(
    manifest, checkpoint, context=BackendContext(inputs, Path("recovered-output"))
)
result = recovered.finish()
assert recovered.finish() is result  # no second finalization or ledger mutation
```

`step()` returns a deeply immutable `SessionObservation(cursor, as_of_ns, account,
reports)`, or `None` once all events have been processed. `observe()` returns the
last successful snapshot. Its account and pending-order reports reflect the owner's
causal delivery prefix, not undelivered economic fills. Nested mappings and sequences
cannot be mutated. Before the first step, the clock is the manifest availability
clock, or the first event clock when unavailable. `finish()` processes remaining
events and finalizes exactly once; repeated calls return the identical result object.
Checkpointing a finished session is rejected.

## Exact input codec and policies

The manifest requires exactly `targets` and `bars`, inline or SHA256-verified JSON
artifacts. Targets carry `decision_time`, `entry_time`, `symbol`, `weight`, and optional
`information_time`/`order_type`. Bars carry native OHLC, amount, share volume, limits,
strict boolean `tradable`, and optional interval/provenance fields. All transport
clocks are decimal integer nanosecond strings, including native-named `*_time` fields.
They convert directly to integer/pandas Timestamp at the native boundary. Corporate
action `*_date` fields remain calendar-date strings. Monetary values, weights, prices
and model coefficients are decimal strings; config lot/slice/duration counts are integers.
The existing owner's float arithmetic is unchanged; decimal transport is not a claim
of new decimal accounting.

`settings` supplies the complete native `config` except initial cash, explicit
`report_delay_seconds`, and `impact` (null or transient/permanent/decay coefficients).
The initial account is cash-only. All four tapes must be explicit, even when empty:
`quantity_locks`, `corporate_actions`, `valuation_events`, `capital_flows`. The calendar
must exactly describe supplied session dates and timezone. This is a synthetic calendar
declaration, not an exchange-calendar acquisition service. Forecast/risk/scenario
execution is rejected; the only model version key is optional `linear-impact: v1`.
See the [native execution contract](../guides/minute-execution.md) for financial rules.

The only remotely reconstructible policy is `target-weights.v1`: policy id
`target-weights`, version `v1`, state schema `target-weights-state.v1`, empty config/state.
It uses the supplied targets and waits while pending orders/reports remain. There is
no dynamic import. A trusted host may instead pass a `LocalPolicy` object declaring
stable `policy_id`, `version`, `state_schema`, `decide(observation) -> Mapping[str,str]`,
`state() -> JsonValue`, and `restore_state(state)`. Identity must match the manifest.
The bridge provides decimal `proposed_weights` in the immutable decision account and
preserves the owner's delayed-report and pending-order gates. Local policies require
inspectable source files and must faithfully capture all mutable policy state; callers
provide the same trusted type on restore. No serialized executable code is accepted.

## Source-bound checkpoints and failure

The outer schema is `engine-financial-checkpoint.v1`, containing provider, input schema,
manifest/binding SHA256, cursor, policy id/version/state schema, `owner_schema` equal to
`minute-session.v3`, complete `owner_state` and its SHA256, plus an outer integrity hash.
It contains no job, lease, SQLite or scheduler identity. The manifest supplies all expected
inputs on restore; saved content never supplies an expected tape or source identity.
The binding covers complete serialized inputs/tapes/config/delay/impact/calendar,
provider identity, every installed core/SDK Python helper, Python version, actual
installed dependency files (including NumPy/pandas binaries), and local policy source
and initial state. Each restore reads the expected artifacts again. A version label
alone is insufficient. Provider Git revision is null unless independently recorded;
source and wheel receipts identify the installed release without a self-referential hash.

A failed step invalidates the wrapper and its financial owner. The original exception
is retained as `failure` and re-raised by subsequent execution/checkpoint calls;
`last_successful_checkpoint` retains the prior successful bytes. The wrapper never asks
a poisoned owner for another checkpoint. `observe()` still returns the last successful
snapshot. Reconstruct with unchanged inputs and a fresh session, or start a fresh run
when inputs change. Finalization or output persistence failures also invalidate the wrapper;
a partial raw artifact may remain for diagnosis, never as a successful published result.

Checksums detect corruption and drift, not hostile checkpoint authors. Treat checkpoints
as trusted local data. Old schemas remain in the original pinned release environment,
including the complete Runtime/Go executable/dependency closure where applicable;
there is no rebinding, migration default or relabeling of old financial state.

## Complete evidence and acceptance

Available tables are `reports` (terminal orders), `fills`, `positions` (closing holdings),
`valuations`, `capital_flows`, and `daily`. Other economic tables are explicitly unavailable;
empty supported tables differ from unsupported ledgers. Unknown marks and return values
remain null. Fees stay in fill/daily evidence and are never debited a second time. Impact
already in fill price is charged once; descriptive opportunity shortfall is not a debit.
Deposits/withdrawals remain separate from PnL. Planned sale proceeds never fund unfilled buys.

The raw artifact retains all six native tables, summary, and an `owner_result` tagged
lossless native payload including nonfinite values. Its exact bytes are SHA256-bound by
`raw_result` and the normalization receipt. The standard tables use decimal strings and
string-safe clocks. The synthetic fixture has two partial buys, one 5 CNY parent commission,
200 CNY distribution, 200 new shares, and 50 CNY net external capital.

```sh
"$ENV/bin/python" -I -B project_tools/verify_installed_product.py --mode minute \
  --manifest "$INPUTS/minute-session.json" --artifact-root "$INPUTS" \
  --output-root "$OUTPUTS"
"$ENV/bin/python" -I -B -m pytest core/tests/test_product_sessions.py \
  core/tests/test_product_checkpoint.py -q -p no:cacheprovider
```

Acceptance uses separate installed wheels, verifies namespace separation and forbidden
packages, restores every successful event boundary, and compares the entire financial
payload. [Installation](installation.md) describes the locked dependency baseline.
