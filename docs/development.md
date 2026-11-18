# Development and verification

[简体中文](development.zh-CN.md)

Keep builds, environments, caches and results outside the checkout. Rust requires 1.99.0+ and the locked NautilusTrader 0.66.0 dependency. The website is one Astro site: reference documentation and interactive lessons share routes, locales and a single published artifact.

## Validation

```sh
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo run --locked -- run tests/fixtures/roundtrip.json
python -m unittest scripts.verify.test_reusable_ownership -v
python scripts/verify/check_reusable_ownership.py
git diff --check
```

Set `CARGO_TARGET_DIR` to an external task build directory. These checks do not establish calibrated market impact or full exchange parity.

## Build the documentation

Use Node 26.13.0/npm 12.2.2 and the committed frontend lock. Python 3.13 prepares trusted article content and owner-produced learning fixtures; it is not a second site renderer or browser financial engine. The active pipeline does not install or run MkDocs. Python-Markdown and PyMdown remain hash-locked to preserve the existing Markdown dialect and exact heading anchors; Astro owns every HTML route, layout and the final page generation.

Install `docs/requirements/docs.lock` and `learning.lock` with `uv pip sync --require-hashes` into an external environment. Install the unchanged `apps/docs/package-lock.json` in a task-owned external dependency directory and link its `node_modules` into `apps/docs/`. Put generated Astro state and caches outside the checkout. Do not share mutable build caches across concurrent tasks.

## Learning site assembly

```sh
export PYTHON="$TASK_DATA/docs-env/bin/python"
export SITE_INPUT_DIR="$TASK_DATA/reference-input"
export ASTRO_OUT_DIR="$TASK_DATA/site-astro"
export ASTRO_CACHE_DIR="$TASK_DATA/astro-cache"
"$PYTHON" -m unittest discover -s project_tools -p 'test_method_*.py'
"$PYTHON" -m unittest scripts.build.test_prepare_reference scripts.build.test_site_routes scripts.build.test_reference_home scripts.build.test_site_assembly scripts.build.test_learning_assets scripts.build.test_export_opportunity_example -v
node --test scripts/build/test_method_replay.cjs
"$PYTHON" scripts/build/validate_learning_assets.py --manifest docs/assets/learning/manifest.json
npm --prefix apps/docs run check
npm --prefix apps/docs run test:unit
"$PYTHON" scripts/build/prepare_reference.py --output "$SITE_INPUT_DIR"
npm --prefix apps/docs run build
"$PYTHON" scripts/build/assemble_site.py --astro "$ASTRO_OUT_DIR" --learning docs/assets/learning --routes docs/site/route-ownership.json --output "$TASK_DATA/site-assembled"
"$PYTHON" scripts/verify/check_docs.py --site-dir "$TASK_DATA/site-assembled"
"$PYTHON" scripts/verify/check_assembled_site.py --site-dir "$TASK_DATA/site-assembled" --base /quant-backtest-engine/ --legacy docs/site/legacy-route-anchors.json
SITE_DIR="$TASK_DATA/site-assembled" SITE_BASE=/quant-backtest-engine/ BROWSER_OUTPUT_DIR="$TASK_DATA/browser" npm --prefix apps/docs run test:e2e
```

Preparation/output directories must be fresh. Source changes invalidate prepared inputs, so regenerate before rebuilding. Install locked Playwright Chromium, or set `CHROME_EXECUTABLE` to a compatible local browser. The launcher serves the actual built artifact on an assigned loopback port and records it; no permanent preview server is required. Optional DOM tests use the separately locked `scripts/build/method-tests` environment and `NODE_PATH`.

## Theme maintenance

Each of the eight lessons starts with one plain question and one event-linked visual. Advanced charts, original values, source bindings and complete tables remain available through native disclosures. Both learning and lab URLs work. Reference search, old page paths, fragment identifiers and downloads remain preserved. English is the default; Chinese counterparts and the explicit language preference retain their established routes and storage contract. Visible lesson diagrams loop automatically. Previous, Step, Reset, direct seeking and scenario or speed changes pause on an exact recorded event. Leaving the viewport or hiding the page pauses playback until explicit Play. Reduced-motion users use manual controls. No-JavaScript users retain complete recorded tables.

The browser replays owner-produced synthetic evidence and draws geometry. It does not recompute accounting, invent missing outcomes or turn deterministic scenarios into probabilities. Opportunity shortfall is distinct from cash fees; permanent-impact parameters are assumptions; the displayed finite feasible grid is not a general global nonconvex/HJB certificate. The conceptual prediction stage does not claim supplied orders came from a trained strategy.

The design takes inspiration from [Distill's interactive optimization explanation](https://distill.pub/2017/momentum/) and [Seeing Theory's visual teaching](https://github.com/seeingtheory/Seeing-Theory); no source code, illustrations or assets were copied. [Astro content patterns](https://docs.astro.build/en/guides/content-collections/) and [Starlight custom pages](https://starlight.astro.build/guides/pages/) inform separation of reference reading from experiments. No Starlight dependency is added.

## Publication and provenance

The sole deployment owner is `.github/workflows/docs.yml`. PRs validate without publishing; merged main commits publish only the assembled Astro artifact to GitHub Pages. `site-build.json` binds actual source/lock/manifest inputs and delivered file hashes; changed or stale fragments fail admission. Keep original tutorial provenance at PR 19 commit `4820af3b82940e7697cb8c92154315b1d59ee23d`. No generated homepage/site is committed, and financial fixture/source identities are unchanged by renderer migration.

Retired two-renderer/extraction helpers are historical tested utilities, not a hidden MkDocs build dependency. License originals and notices remain in [third-party notices](third-party-notices.md), `LICENSE` and `COPYING`.

[Frontend build security mitigation](frontend-security.md): patch fresh installs before Astro and use the verified audit gate.

The diagram and control spacing draws on [Red Blob Games](https://www.redblobgames.com/pathfinding/a-star/introduction.html) and [Bartosz Ciechanowski](https://ciechanow.ski/mechanical-watch/). The page uses a local CJK sans stack and tabular figures. Transitions connect recorded states for reading, while source event times and exact values remain in the evidence. Chinese teaching prose follows the requested direct-action style. No external artwork or fonts are downloaded at runtime.

The mechanism index and diagram styling follow the restrained typography, thin rules and numbered flow nodes of quant-workspace-standards (reference revision `e63f5d7`). Keep execution scope beside each mechanism; preserve the source-bound experiments and their legacy routes.

The record diagrams borrow the restrained axes and comparison layout of [Observable Plot](https://observablehq.com/plot/) and the staged explanation rhythm of [Motion Canvas](https://motioncanvas.io/docs/), with no new runtime dependency. Paths align only through source comparison mappings with matching clock, stage and currency; selecting a path/event pauses atomically. Event clocks retain nanosecond fractions, and ISO instants display an explicit Shanghai time zone. Animation eases graphical geometry only; account labels and previous/current values remain recorded scalars. The mechanism overview and the eight underlying demonstrations have separate navigation labels.


Select `rust.nautilus.depth` for the new single-instrument event profile. See [native event-depth scope](product/execution-fidelity.md#native-event-depth-profile) for contracts, clocks, limits and evidence. Existing session commands keep their original behavior.

Rust owns the new native event execution path. TypeScript/TSX and Astro own the website. Python retains SDK validation, product orchestration, research interfaces and existing financial implementations. Move financial modules in individually verified batches with arithmetic and checkpoint compatibility checks.

## Workspace layout {#workspace-layout}

The root Cargo manifest selects `packages/engine` as the default workspace member.
Run normal Cargo commands from the repository root. The independent PyO3 crate
keeps its own lock and build entrypoint under `packages/microstructure-native`.

```text
apps/docs/                       Astro application
packages/engine/src/             Rust engine
packages/core/src/               Python financial library
packages/python-sdk/src/         Python client
packages/microstructure-native/  Optional PyO3 extension
tests/fixtures/                  Shared synthetic inputs
tests/acceptance/                Installed cross-package checks
scripts/build/                  Site and fixture preparation
scripts/verify/                 Validation and diagnostics
scripts/release/                Packaging and performance tools
```

Each package keeps its own tests and package-specific examples. The Python
packages retain separate build metadata and Core's numerical lock; the SDK can
still be installed on Python 3.11 independently of Core. Paths recorded in
historical evidence resolve through `workspace-layout.json` with root confinement.

Immutable historical exporters are reproduction sources. Run
`scripts/build/reproduce_method_fixtures.py --engine "$REGISTERED_ENGINE" --output "$TASK_DATA/method.json"`
in the registered exact-owner environment. Add `--kind opportunity` and omit
`--engine` for the opportunity example. The wrapper stages verified original
sources and inputs in a fresh external legacy layout. Published fixture bytes
and owner locks remain unchanged. The inactive MkDocs configuration is archived
at `docs/site/legacy-mkdocs.yml`; Astro remains the sole active renderer.

Checkpoint restore retains its original complete source/dependency binding.
Package relocation was compared within one unchanged numerical environment,
reinstalling only the pre/post-move SDK/Core wheels. A different environment can
change dependency-file hashes even when package versions match.

## Reviewing upstream updates

Dependabot checks the root Cargo workspace and GitHub Actions weekly. Review
the NautilusTrader release notes and verify that the direct `nautilus-*` crates
move together in the manifest and lockfile. If Dependabot cannot resolve the
exact pins together, prepare a single upgrade PR for the crate set.

Use the Rust regression tests, installed L2 depth acceptance, and synthetic
assurance report in CI to review changes to fills, cancellations, commissions,
cash, and positions. Compare financial output with the base revision and explain
any intended differences in the PR before merging.
