# Optional microstructure Rust accelerator {#rust-microstructure-kernel}

[简体中文](microstructure-rust.zh-CN.md)

Choose the backend explicitly. These four modes have different contracts:

| Mode | API | Financial / evidence owner |
| --- | --- | --- |
| Minute Python | `python.minute` ProductManifest backend | Minute cash/positions and checkpoint owner |
| LOB Python | `MatchingEngine(backend="python")` | Deterministic book with per-fill evidence |
| Optional LOB PyO3 | `MatchingEngine(backend="rust")` | `_microstructure_rs` ordered per-fill evidence and book ticks |
| Nautilus Rust | `rust.nautilus.sessions` | Existing CLI/Nautilus financial sessions |

LOB Python and LOB PyO3 are low-level APIs, not registered ProductManifest backends.
Neither provides learned order flow or real-market calibration. Rust LOB selection
never selects Nautilus. Missing `_microstructure_rs` raises ImportError; no fallback.
`sort_simulator_events(events, backend="rust")` follows the same explicit policy.

Core `[microstructure]` does not depend on Torch, scikit-learn, models or the native
wheel. The transferred simulator closure itself uses only the standard library.
Core root imports remain lazy with respect to the simulator and optional extension.
The optional distribution remains `quant-microstructure-core` 0.2.0, import
`_microstructure_rs`, PyO3 0.30.1, abi3 Python >=3.12; the supported core matrix is
Python 3.12 and 3.13. The original native Python >=3.12 declaration is retained.

## Build and use {#build-and-use}

Build each wheel from the reviewed provider source, with all outputs outside code:

```sh
export CARGO_TARGET_DIR="$TASK_DATA/native-target"
export UV_CACHE_DIR="$TASK_DATA/uv-cache"
export TMPDIR="$TASK_DATA/tmp"
mkdir -p "$TMPDIR"
uv build --wheel --out-dir "$TASK_DATA/wheels" packages/microstructure-native
uv pip install --python "$ENV/bin/python" "$TASK_DATA"/wheels/quant_microstructure_core-*.whl
TICKNET_REQUIRE_RUST=1 "$ENV/bin/python" -I -m pytest "$TESTS" -q
```

## Correctness and measurement {#correctness-and-measurement}

Install core and SDK as separate regular wheels in `$ENV` before this command;
`$TESTS` is an external copy of the simulator acceptance tests. Do not use editable
installs or source PYTHONPATH as installed evidence. Validate a separate no-native,
no-Torch environment too. The native wheel owns only `_microstructure_rs`; core owns
`quant_backtest_core`; SDK owns `quant_backtest_engine`. License notices ship with
the optional wheel and native sources. Source is implemented in provider B; no
release or consumer cutover is claimed until merged wheel receipts are recorded.

## Fill evidence and impact estimation limits {#fill-evidence-and-impact-estimation-limits}

Native 0.2 adds `apply_order_with_fills` and `replay_with_fills`. Each fill records
buy/sell IDs, integer execution price and quantity in matching order. The legacy
`apply_order` aggregate tuple and `replay` tick tuples retain their contracts.
The Python adapter uses the detailed methods; ReplaySession and ImpactEstimator
retain the resulting evidence, including background fills and passive child fills.
Install Core and the native wheel from the same verified source revision. Core
rejects older native wheels before order submission when the detailed API is absent.

Unique explicit order IDs remain required for Python/native parity. The historical
duplicate-ID differences remain documented in [matching](../microstructure/matching.md).
This work supplies matching evidence. Supplied latency, inferred queue positions,
causal permanent impact and real-market calibration have separate validation scopes.

## Synthetic performance measurements {#synthetic-performance-measurements}

Run the installed wheels with `python -I scripts/release/benchmark_microstructure.py
--output /external/new-report.json`. Defaults are 10,000 events, eight independent
paths and five repetitions. Python and Rust must produce identical complete results
before timing and on every timed run. The report records installed file hashes,
source revision, seed and workload hash, raw timings and medians. Public-call timing
includes Python projections and allocations; result hashing runs outside the timer.
Paths run sequentially with independent books. These local workloads guide profiling
and do not measure market capacity or production throughput.

Next migrations should follow measured workloads. Per-fill native matching and batch
replay are available here. Python keeps orchestration and the independent reference.
The minute ledger, corporate actions and checkpoint state need a separate compatibility
plan before transfer. NumPy/SciPy planning already delegates numerical work to compiled
libraries; a Rust rewrite needs measured benefit and solver-equivalence evidence.
