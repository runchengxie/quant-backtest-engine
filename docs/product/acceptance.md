# Delivery acceptance and remaining work

[简体中文](acceptance.zh-CN.md)

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
| Runtime retained baseline | `01ed4c34f955ef6cd39d13aa073b6d61b610d321` | Existing integration; no claim of the proposed v9 consumer cutover |

The tutorial revision does not change the provider's `core/`, `python/`, Rust
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
| Minute account | `[minute]` | `examples/product/minute_session.py`: two fills, CNY 50 net external capital, all recovery ledgers and summary equal uninterrupted execution |
| Independent scenarios | `[scenario]` | `examples/product/scenarios.py --output-root NEW_DIRECTORY`: one invalid case fails independently; the hand oracle buys 100 shares at 10 with zero remaining cash |
| Bounded planning | `[planning]` | `verify_installed_planning.py`: exhaustive finite oracle selects `(1, 1)`, spends 12 and reports objective 0.5 |
| Daily financial graph | `[daily]` | `verify_installed_daily.py`, followed by `core/tests/daily`: real installed ownership, complete financial/action/fee/valuation and product regressions |
| Python order book | `[microstructure]` | `verify_installed_microstructure.py --native absent`: real match behavior and explicit missing-native failure |
| Union | `[all]` | Full installed `core/tests`; Rust/native execution checks additionally need their real executable/extension |

All `verify_installed_*.py` scripts above are under `project_tools/` in `SOURCE`.
They import the installed wheels, not an editable source tree. For example:

```sh
cd "$TASK_DATA"
"$ENV/bin/python" -I -B "$SOURCE/examples/product/minute_session.py"
"$ENV/bin/python" -I -B "$SOURCE/project_tools/verify_installed_daily.py"
"$ENV/bin/python" -I -B -m pytest "$SOURCE/core/tests/daily" -q -p no:cacheprovider
```

Use separate minute and daily environments for those commands. The existing
[Rust target-weight walkthrough](../tutorial.md) checks sizing, T+1 rejection,
both fills, fees and daily cash + positions = NAV. Its final NAV is 10197.8 with
2.2 commission. The smaller quote-only `fixtures/roundtrip.json` instead ends at
10019.78 with 0.22 commission; these are different fixtures.

Preserve commands, exit codes, Python/dependency versions, source revisions,
wheel/executable hashes and generated results in task-specific external data.
A skipped optional native or Rust test is not evidence that its backend passed.
Unavailable daily cash/fee/valuation evidence stays unavailable; never replace it
with zero or infer complete economic equivalence from final NAV alone.

## Verify publication

The existing Documentation workflow remains the sole publisher. It builds both
renderers, checks routes/legacy anchors and runs the real built-site browser suite.
After a successful main deployment, verify the expected full merged commit:

```sh
python -B project_tools/verify_deployed_site.py \
  --url https://runchengxie.github.io/quant-backtest-engine/ \
  --revision "$MERGED_REVISION" --output "$TASK_DATA/deployed.json"
```

The verifier checks every receipt-listed response's byte count and SHA256 and
rechecks the receipt after downloading. A stale revision, changed file or mixed
publication fails. This supplements browser behavior and CI; it is not a browser
interaction test or independent authentication of the build's financial claims.

## Remaining gates

- Runtime v9 process-kill/admission acceptance and remaining research consumers
  are separate integration work. Preserve their current supported paths and full
  pinned historical recovery environments until independently verified.
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
