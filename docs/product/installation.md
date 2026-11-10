# Install the optional product

[简体中文](installation.zh-CN.md)

Core 0.3.0 provides explicit Rust and resumable Python minute runners. Install the SDK 0.3.0 wheel
and core wheel built from the same reviewed Engine revision into a Python 3.12 or
3.13 environment (`>=3.12,<3.14`). Python 3.14 needs a separate numerical
baseline upgrade: pandas 3.0.6 requires NumPy >=2.3.3 on that interpreter. The SDK itself still supports Python 3.11. No PyPI release is
required or implied; record exact source revisions and wheel SHA256 hashes.

```sh
python -m venv "$ENV"
"$ENV/bin/python" -m pip install --no-index --no-deps \
  "$WHEELS/quant_backtest_engine_client-0.3.0-py3-none-any.whl" \
  "$WHEELS/quant_backtest_core-0.3.0-py3-none-any.whl"
"$ENV/bin/quant-backtest" capabilities rust.nautilus.sessions
```

Base core imports only the standard library and SDK. Its wheel owns only
`quant_backtest_core`; SDK continues to own `quant_backtest_engine`. Linux hosts
need the system IANA timezone database. Neither install needs Platform, Runtime,
pandas, NumPy, SciPy, Torch or model-training packages.

## Build and verify

Use external directories for environments, wheels, caches and generated results.
`core/uv.lock` fixes tested development and optional dependency resolutions.
The numerical baseline is constrained to NumPy 2.2.6, pandas 3.0.6 and SciPy 1.18.1
for later extraction parity; public extra ranges remain as declared below.
Its `../python` source is a monorepo development convenience, not a release pin.
Build SDK and core independently with `uv build --wheel --project python` and
`uv build --wheel --project core`, each with an external `--out-dir`. Installed
acceptance uses wheel paths, `python -I` and no editable install or `PYTHONPATH`.
Consumers must pin the exact merged revision or verified wheel hashes before cutover.

```sh
"$ENV/bin/python" -I -B project_tools/verify_installed_product.py --mode base
for suite in packaging runner rust_adapter; do
  "$ENV/bin/python" -I -B -m unittest discover -s core/tests -p "test_$suite.py" -v
done
```

Development checks use the locked dev group: `ruff check core`, `ruff format
--check core`, and `mypy --config-file core/pyproject.toml core/src`. Set external
`UV_PROJECT_ENVIRONMENT`, `UV_CACHE_DIR`, `RUFF_CACHE_DIR`, `MYPY_CACHE_DIR`,
`PYTHONPYCACHEPREFIX`, `TMPDIR` and `CARGO_TARGET_DIR` before local validation.

## Optional dependencies

| Extra | Dependency bounds |
| --- | --- |
| minute, scenario | pandas >=3.0.5,<3.1 |
| planning, cost | pandas >=3.0.5,<3.1; NumPy >=1.23; SciPy >=1.14 |
| microstructure | pandas >=3.0.5,<3.1; NumPy >=1.23 |
| daily | pandas >=3.0.5,<3.1; NumPy >=1.23; tzdata >=2025.2 |
| all | Union of the above; no Torch, Qlib or OSQP |

The `scenario` extra supports [market paths and stress](../backtest/market-paths.md);
`cost` supports [transaction cost evidence](../backtest/transaction-cost-evidence.md)
and scoped fitting. These are independent leaf APIs. The `minute` extra now provides the direct
[minute session and financial kernels](../backtest/minute-session.md). The minute extra enables `python.minute`; see [recovery and exact input codec](recovery.md).
Planning and microstructure extras enable their documented leaf APIs. The daily group enables `python.daily` in provider C source (release pending);
unknown keys are rejected.
See [backend limits](backends.md) before choosing a manifest.


For installed leaf acceptance, install the core wheel with `[minute,cost,scenario]`
and pytest, resolving numerical packages from the locked baseline. Run
`python -I -B -m pytest core/tests -q -p no:cacheprovider` with
`QUANT_ENGINE_BINARY` pointing to the content-verified Rust binary for adapter
regressions. Tests import installed wheels, never source-tree `PYTHONPATH`.
Extracted legacy signatures remain unchanged: mypy still checks their bodies,
with narrowly scoped allowances for absent pandas/SciPy stubs and six
dictionary-inference diagnostics (three transaction-audit locals and three minute-kernel locals). New typed quote/protocol code is checked.

For minimal minute acceptance, install `[minute]` alone plus pytest and run
`python -I -B -m pytest core/tests/test_minute*.py core/tests/test_quantity_locks.py -q`
and `python -I -B examples/product/minute_session.py`. This install needs pandas
and its NumPy dependency, but no SciPy, Platform, Runtime or ML framework.

Deterministic LOB matching/replay is implemented in provider B source, pending merged release. [LOB Python / optional PyO3 modes](../development/microstructure-rust.md).

## Task 9 execution ownership (unreleased)

Provider B now implements [paper accounts](../backtest/paper-account.md),
[account events and full checkpoints](../contracts/paper-account-events.md),
[external reconciliation](../backtest/capital-and-reconciliation.md),
[neutral pending reservations](../contracts/pending-allocation.md), and
[execution-impact estimation](../microstructure/impact-estimation.md).
Use the `[planning]` optional core dependencies for pandas-based accounts and
reservations. Replay/impact is standard-library-only; the optional native wheel
still rejects impact estimation because per-fill evidence is unsupported. A supplied
optimizer owns full research validation; Engine supplies no OSQP optimizer.
Core source is now 0.2.0; whole-provider review and integration still precede release availability and consumer cutover. Old checkpoints retain their full pinned legacy environment.

## Bounded planning

The unreleased provider B implementation includes optional leaf APIs under
`quant_backtest_core.planning`: impact planning, multiperiod weights, finite
inventory/oracle comparison and actual sleeve-fill attribution. Install Core's
explicit `[planning]` extra with NumPy 2.2.6, pandas 3.0.6 and SciPy 1.18.1 for the
continuous APIs. Finite inventory/oracle and sleeve attribution use only the
standard library. Importing the planning package stays lazy. No Platform, Runtime,
Torch or OSQP is required; generic optimizers and risk estimators remain external.
Core source is 0.2.0; a source implementation is not a merged release or consumer cutover.
See [impact planning](../concepts/impact-planning.md),
[finite inventory](../concepts/discrete-inventory.md), and
[sleeve allocation](../backtest/sleeve-allocation.md).

The `[scenario]` extra also supports [independent typed-target composition](scenarios.md).
Validate every extra separately with `project_tools/verify_installed_scenarios.py --profile EXTRA`,
using independently installed wheels, and validate the union with `--profile all`.
The `daily` extra enables the independent daily graph and `python.daily`.

Daily acceptance: `python -I -B project_tools/verify_installed_daily.py` and `python -I -B -m pytest core/tests/daily -q -p no:cacheprovider`. Minimal daily deliberately excludes PyArrow. Pandas may choose Python rather than PyArrow string storage; this changes storage dtype only, including label indexes. Oracle parity additionally uses original PyArrow 26.0.1 and checks every dtype and table exactly. Numeric values, NA semantics, ordering and financial summaries must match in both profiles.
