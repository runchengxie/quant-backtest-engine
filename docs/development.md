# Development and verification

[简体中文](development.zh-CN.md)

Keep builds, environments, caches and results outside the checkout. Rust requires 1.99.0+ and the locked NautilusTrader 0.66.0 dependency. The website is one Astro site: reference documentation and interactive lessons share routes, locales and a single published artifact.

## Validation

```sh
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo run --locked -- run fixtures/roundtrip.json
python -m unittest project_tools.test_reusable_ownership -v
python project_tools/check_reusable_ownership.py
git diff --check
```

Set `CARGO_TARGET_DIR` to an external task build directory. These checks do not establish calibrated market impact or full exchange parity.

## Build the documentation

Use Node 26.13.0/npm 12.2.2 and the committed frontend lock. Python 3.13 prepares trusted article content and owner-produced learning fixtures; it is not a second site renderer or browser financial engine. The active pipeline does not install or run MkDocs. Python-Markdown and PyMdown remain hash-locked to preserve the existing Markdown dialect and exact heading anchors; Astro owns every HTML route, layout and the final page generation.

Install `docs/requirements/docs.lock` and `learning.lock` with `uv pip sync --require-hashes` into an external environment. Install the unchanged `web/package-lock.json` in a task-owned external dependency directory and link its `node_modules` into `web/`. Put generated Astro state and caches outside the checkout. Do not share mutable build caches across concurrent tasks.

## Learning site assembly

```sh
export PYTHON="$TASK_DATA/docs-env/bin/python"
export SITE_INPUT_DIR="$TASK_DATA/reference-input"
export ASTRO_OUT_DIR="$TASK_DATA/site-astro"
export ASTRO_CACHE_DIR="$TASK_DATA/astro-cache"
"$PYTHON" -m unittest discover -s project_tools -p 'test_method_*.py'
"$PYTHON" -m unittest project_tools.test_prepare_reference project_tools.test_site_routes project_tools.test_reference_home project_tools.test_site_assembly project_tools.test_learning_assets project_tools.test_export_opportunity_example -v
node --test project_tools/test_method_replay.cjs
"$PYTHON" project_tools/validate_learning_assets.py --manifest docs/assets/learning/manifest.json
npm --prefix web run check
npm --prefix web run test:unit
"$PYTHON" project_tools/prepare_reference.py --output "$SITE_INPUT_DIR"
npm --prefix web run build
"$PYTHON" project_tools/assemble_site.py --astro "$ASTRO_OUT_DIR" --learning docs/assets/learning --routes docs/site/route-ownership.json --output "$TASK_DATA/site-assembled"
"$PYTHON" project_tools/check_docs.py --site-dir "$TASK_DATA/site-assembled"
"$PYTHON" project_tools/check_assembled_site.py --site-dir "$TASK_DATA/site-assembled" --base /quant-backtest-engine/ --legacy docs/site/legacy-route-anchors.json
SITE_DIR="$TASK_DATA/site-assembled" SITE_BASE=/quant-backtest-engine/ BROWSER_OUTPUT_DIR="$TASK_DATA/browser" npm --prefix web run test:e2e
```

Preparation/output directories must be fresh. Source changes invalidate prepared inputs, so regenerate before rebuilding. Install locked Playwright Chromium, or set `CHROME_EXECUTABLE` to a compatible local browser. The launcher serves the actual built artifact on an assigned loopback port and records it; no permanent preview server is required. Optional DOM tests use the separately locked `project_tools/method-tests` environment and `NODE_PATH`.

## Theme maintenance

Each of the eight lessons starts with one plain question and one event-linked visual. Advanced charts, original values, source bindings and complete tables remain available through native disclosures. Both learning and lab URLs work. Reference search, old page paths, fragment identifiers and downloads remain preserved. English is the default; Chinese counterparts and the explicit language preference retain their established routes and storage contract. Motion remains optional and respects reduced-motion settings; no-JavaScript users retain complete recorded tables.

The browser replays owner-produced synthetic evidence and draws geometry. It does not recompute accounting, invent missing outcomes or turn deterministic scenarios into probabilities. Opportunity shortfall is distinct from cash fees; permanent-impact parameters are assumptions; the displayed finite feasible grid is not a general global nonconvex/HJB certificate. The conceptual prediction stage does not claim supplied orders came from a trained strategy.

The design takes inspiration from [Distill's interactive optimization explanation](https://distill.pub/2017/momentum/) and [Seeing Theory's visual teaching](https://github.com/seeingtheory/Seeing-Theory); no source code, illustrations or assets were copied. [Astro content patterns](https://docs.astro.build/en/guides/content-collections/) and [Starlight custom pages](https://starlight.astro.build/guides/pages/) inform separation of reference reading from experiments. No Starlight dependency is added.

## Publication and provenance

The sole deployment owner is `.github/workflows/docs.yml`. PRs validate without publishing; merged main commits publish only the assembled Astro artifact to GitHub Pages. `site-build.json` binds actual source/lock/manifest inputs and delivered file hashes; changed or stale fragments fail admission. Keep original tutorial provenance at PR 19 commit `4820af3b82940e7697cb8c92154315b1d59ee23d`. No generated homepage/site is committed, and financial fixture/source identities are unchanged by renderer migration.

Retired two-renderer/extraction helpers are historical tested utilities, not a hidden MkDocs build dependency. License originals and notices remain in [third-party notices](third-party-notices.md), `LICENSE` and `COPYING`.

[Frontend build security mitigation](frontend-security.md): patch fresh installs before Astro and use the verified audit gate.
