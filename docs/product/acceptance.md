# Delivery acceptance and remaining work

[简体中文](acceptance.zh-CN.md)

Select `rust.nautilus.depth` for the new single-instrument event profile. See [native event-depth scope](execution-fidelity.md#native-event-depth-profile) for contracts, clocks, limits and evidence. Existing session commands keep their original behavior.


Use the standalone Engine first. Its merged Python core owns minute and daily
financial execution, recovery, bounded planning and independent scenarios. Strategy
selection, training and general optimization remain with the caller. The bilingual
learning site is delivered by the same repository.

## Source combination

The following are distinct identities, not interchangeable package-version claims:

| Component | Reviewed merged source | Scope |
| --- | --- | --- |
| Engine financial provider C | `ad0895f1c2015eb31bd364b40741b0f7cd6e0048` | Core/SDK 0.3.0; independent daily graph and period-leg financial closure |
| Engine tutorial | `062a820de013d824686e6b5f6582843618929d27` (PR 26) | Astro lessons and replay lab; preserved eight scenes and 21 presets |
| Platform consumer C | `c211d36167acf7a81fd0c034beb14317e2036b7e` (PR 200) | Compatibility adapters to the Engine provider; research stays outside Engine |
| Runtime Engine v9 | `eb00e0b85459d64719d6dc05bc93a94a4ffbce95` (PR 60) | Runtime 0.2.0 fixed Engine provider; actual process-death recovery validated |
| Runtime retained baseline | `01ed4c34f955ef6cd39d13aa073b6d61b610d321` | Historical recovery retains its complete original release and dependency closure |

The tutorial revision does not change the provider's `packages/core/`, `packages/python-sdk/`, Rust
sources or Cargo lock. Independent wheel acceptance records the actual build
revision and SHA256; it does not rename old checkpoint identities. Build both wheels
from one clean reviewed revision as described in [installation](installation.md).
Core supports Python 3.12/3.13; the standalone SDK also supports 3.11. This delivery
uses source-built wheels and does not require a PyPI publication.

## Acceptance recorded on 2026-11-16

Fresh wheels from tutorial source `062a820` passed isolated SDK 3.11 and all eight
core extra profiles on Python 3.12/3.13. Each full-core run passed 957 tests and
three subtests, with 25 Rust/native cases skipped in the dependency-only profile.
Separate real-backend runs passed all 73 microstructure tests and both Rust adapter
tests on each interpreter. Each minimal daily profile passed 319 tests; the SDK
passed 32 tests against the real Rust executable. Rust fmt, clippy, tests and both
financial walkthroughs passed. All 228 baseline deployed files matched their receipt.
These are overlapping suites, so their counts must not be added as unique tests.

Fresh wheel SHA256 identities:

- Core: `57ed0dc2ede0bbc82dc6298965a5e56f05ffaba9308563f2509d5c2b50d89650`
- SDK: `bb5e3cd7322e2653729c17f856a1a1747f9b999275ce982a5374fd4e39ff616c`

## Reproduce the financial checks

Use a fresh environment for each extra, install regular wheels, and run from a
neutral directory with `python -I -B`. `SOURCE` is the clean checkout; `ENV`,
`WHEELS` and `TASK_DATA` are absolute external paths chosen by the caller.
Use the locked numerical baseline from the installation guide.

| Check | Installed environment | Acceptance |
| --- | --- | --- |
| SDK/base | SDK only / SDK + core without extras | `verify_installed_product.py --mode sdk` / `--mode base`; source namespaces stay separate and no numerical/framework dependencies appear |
| Minute account | `[minute]` | `packages/core/examples/product/minute_session.py`: two fills, CNY 50 net external capital, all recovery ledgers and summary equal uninterrupted execution |
| Independent scenarios | `[scenario]` | `packages/core/examples/product/scenarios.py --output-root NEW_DIRECTORY`: one invalid case fails independently; the hand oracle buys 100 shares at 10 with zero remaining cash |
| Bounded planning | `[planning]` | `verify_installed_planning.py`: exhaustive finite oracle selects `(1, 1)`, spends 12 and reports objective 0.5 |
| Daily financial graph | `[daily]` | `verify_installed_daily.py`, followed by `packages/core/tests/daily`: real installed ownership, complete financial/action/fee/valuation and product regressions |
| Python order book | `[microstructure]` | `verify_installed_microstructure.py --native absent`: real match behavior and explicit missing-native failure |
| Union | `[all]` | Full installed `packages/core/tests`; Rust/native execution checks additionally need their real executable/extension |

All `verify_installed_*.py` scripts above are under `scripts/` in `SOURCE`.
They import the installed wheels, not an editable source tree. For example:

```sh
cd "$TASK_DATA"
"$ENV/bin/python" -I -B "$SOURCE/packages/core/examples/product/minute_session.py"
"$ENV/bin/python" -I -B "$SOURCE/tests/acceptance/verify_installed_daily.py"
"$ENV/bin/python" -I -B -m pytest "$SOURCE/core/tests/daily" -q -p no:cacheprovider
```

Use separate minute and daily environments for those commands. The existing
[Rust target-weight walkthrough](../tutorial.md) checks sizing, T+1 rejection,
both fills, fees and daily cash + positions = NAV. Its final NAV is 10197.8 with
2.2 commission. The smaller quote-only `tests/fixtures/roundtrip.json` instead ends at
10019.78 with 0.22 commission; these are different fixtures.

Preserve commands, exit codes, Python/dependency versions, source revisions,
wheel/executable hashes and generated results in task-specific external data.
A skipped optional native or Rust test is not evidence that its backend passed.
Unavailable daily cash/fee/valuation evidence stays unavailable; never replace it
with zero or infer complete economic equivalence from final NAV alone.

## Verify publication

The existing Documentation workflow remains the sole publisher. It builds one Astro artifact, checks routes/legacy anchors and runs the real built-site browser suite.
After a successful main deployment, verify the expected full merged commit:

```sh
python -B "$SOURCE/scripts/verify/verify_deployed_site.py" \
  --url https://runchengxie.github.io/quant-backtest-engine/ \
  --revision "$MERGED_REVISION" --output "$TASK_DATA/deployed.json"
```

The verifier checks every public receipt-listed response's byte count and SHA256 and
rechecks the receipt after downloading. A stale revision, changed file or mixed
publication fails. This supplements browser behavior and CI; it is not a browser
interaction test or independent authentication of the build's financial claims.

## Runtime integration verified on 2026-11-17

[Runtime PR 60](https://github.com/runchengxie/quant-backtest-runtime/pull/60)
merged the opt-in `engine.minute_session_resume` v9 provider. The exact merged
release passed an actual process-kill recovery with full result and native-ledger
byte equality. The reviewed implementation passed all 25 v9 cases, including four
crash boundaries; its current-target CI and merged main CI passed. Retained v8 and
Rust integration were checked separately. These suites overlap and are not one
unique-test total.

Use the [fixed Runtime provider guide](https://runchengxie.github.io/quant-backtest-runtime/engine-financial-sessions/)
and its exact Engine `ad0895f` source profile or allowlisted wheels. The newer
Engine tutorial revision has identical financial source bytes, but a version number
or different VCS pin is not automatically admitted by Runtime. Keep v9 in an
isolated store; an old worker must not claim its jobs. Production service activation
and historical-release retirement remain separate operator decisions.

## Remaining gates

- Remaining caller releases must retain their own exact provider/consumer receipts.
  Historical recovery requires the original full release; new v9 acceptance does
  not authorize hot rebinding or removal of compatibility aliases.
- The friend's CNY 50 million case still needs original target/order intent,
  submission/arrival clocks, initial cash/holdings/locks, fee terms and executable
  market inputs. Existing fixed-fill diagnostics cannot establish actual capacity.
- Real impact/slippage calibration requires provenance and an identification
  design. Synthetic sensitivity checks do not establish causal market impact.
- Forecast caching, multistart diagnostics, cross-security impact and general
  nonconvex solvers need separately defined problems and acceptance criteria.
  They are not missing prerequisites for this arithmetic-preserving migration.
- Tick acquisition, broker access, production activation, compatibility-alias
  retirement and cleanup of earlier tasks are outside this delivery.

[Execution fidelity and production gates](execution-fidelity.md)

The public verifier checks every receipt-listed public file. The empty root `.nojekyll` is a Pages control artifact and is recorded separately as `artifact_only_files`; its absence over HTTP does not skip any public resource. A nonempty marker, any other missing file or any changed hash fails verification.

## Algorithm follow-up inventory, 2026-11-18

| Work | Current implementation | Concrete next gate |
| --- | --- | --- |
| Account feedback and independent scenarios | Merged financial owners, isolated accounts and supplied-policy target updates | Preserve exact caller/provider wheel identities for each release |
| FIFO and command timing | Standalone supplied-latency replay, partial cancels, exact fills and distinct response clocks | Register a versioned product adapter and test its authoritative account outputs |
| Nautilus L2 execution | Separate versioned profile covers multi-level fills, command latency and actual account feedback with receipts and input digest | Real-feed semantic admission, historical queue calibration and Runtime release integration |
| Historical queue and CNY 50 million capacity | Snapshot depth audit and fixed-fill diagnostics | Obtain original target/order intent, initial account state, fee terms and normalized executable market events; report uncomparable intervals explicitly |
| Impact and slippage calibration | Supplied-coefficient sensitivity and execution-cost evidence APIs | Identify own orders/fills and contemporaneous market observations; validate identification and out-of-sample cohorts |
| General nonconvex optimization | Finite exact oracles, bounded joint execution and a conservative convex cash-bound planner | Specify the objective, constraints and oracle for each new solver before extending its guarantees |

The website groups six primary mechanisms with distinct demonstration destinations.
Account reconciliation and selection/risk diagnostics remain auxiliary topics. The
home animation describes conceptual data flow; executable backend capabilities are
validated separately. The [execution fidelity guide](execution-fidelity.md) records
the new command replay contract and its bounds.

## Synthetic algorithm assurance {#synthetic-assurance}

Run `scripts/verify/synthetic_assurance.py --engine "$ENGINE" --output "$TASK_DATA/assurance.json" --seed 7`
in an environment with the installed SDK/Core and planning dependencies.
The output path is created exclusively. The report retains the executable hash,
source revision, script/runtime source hashes, seed and individual assumptions.
Use fresh outputs for additional seeds; shared data aliases are untouched.

The suite compares native lot planning against retained Fraction enumeration,
and inventory planning against independently enumerated feasible economics.
It checks the impact model against an exponential-kernel quadratic cost, same-clock
splitting and checkpoint restoration. Generated paths retain independent accounts,
seed/batch/prefix reproducibility and frozen training cutoffs. Random native target,
buy, sell and cancel sequences pass independent SDK fill-prefix/account checks.

A feedback example observes four actual shares, cancels the remaining order,
plans six more shares and deterministically replays the full prefix with that next
command. Each run has one Nautilus account. This is prefix replay, with no claim
of native checkpoint restore or an arbitrary in-engine optimization callback.

Twelve assumed-market scenarios combine CNY 20m/50m capital, three depth settings
and two insertion delays. Each records filled/unfilled quantity, fees and benchmark
price difference. Opportunity loss uses an explicitly assumed terminal price of 11.
These cases verify mechanics under supplied conditions. Market capacity, real
queue positions, calibrated latency and causal impact remain unverified.

The historical `feat/method-pages-20261108` PR 19 closed without direct merge.
PR 26 integrated the tutorial in Astro. Its eight original scene identifiers remain
in the current fixtures, and source revision `4820af3` remains recorded. The owner retired that branch/worktree on 2026-11-18 after verifying the annotated
remote tag `archive/method-pages-20261108` resolves to full commit
`4820af3b82940e7697cb8c92154315b1d59ee23d`. The tag preserves the original source.
