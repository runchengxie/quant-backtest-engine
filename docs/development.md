# Development and verification

Requires Rust 1.99.0+. Upstream crates are pinned to NautilusTrader 0.66.0.
Cargo.toml and Cargo.lock stay at the project root. Keep build outputs outside the
source tree when your workspace requires it, using CARGO_TARGET_DIR.

## Validation

```sh
cargo fmt --all --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
cargo run --locked -- run fixtures/roundtrip.json
git diff --check
```

Tests cover strict validation, no lookahead, fees, rejected orders, open/multiple
positions, repeatability and the real CLI protocol. CI runs the same checks.
No performance advantage or production parity is claimed without measurement.

## Build the documentation

Python 3.13 and uv are used only for documentation tooling, not engine execution.

```sh
uv venv --python 3.13 .venv-docs
uv pip sync --python .venv-docs/bin/python docs/requirements/docs.lock
.venv-docs/bin/mkdocs build --strict
.venv-docs/bin/python project_tools/check_docs.py --site-dir site
.venv-docs/bin/mkdocs serve
```

Set `--site-dir` to an external task data directory for retained builds.
PRs build and verify documentation without publishing. Only merged main commits
publish through GitHub Actions artifacts to GitHub Pages. No force push or generated
site commits are needed. Theme selection persists through Material's built-in storage.
Language switching links to the counterpart page and navigation stays in that locale.
English is the fallback if a translated counterpart is unavailable.

Site styling follows the restrained warm neutral palette in quant-platform, with
system fonts, brown accents and both light and dark palettes. The language-specific
navigation follows the behavior of quant-backtest-runtime. Translation labels are
kept in the locale hook catalog rather than financial data or protocol identifiers.

Third-party attribution lives in [third-party-notices.md](third-party-notices.md).
License originals stay at the repository root as LICENSE and COPYING.

## Theme maintenance

Material for MkDocs [announces end of life on May 5, 2027](https://squidfunk.github.io/mkdocs-material/).
The current locked version matches the sibling project sites. Review the upstream
successor or another maintained MkDocs-compatible theme before that date. The source
content remains Markdown and publication uses standard static Pages artifacts.

## Learning site assembly

The same sequence runs for PRs and main; only main publishes. Use a fresh external `TASK_DATA` directory, Node 26.13.0/npm 12.2.2 and the locked `web/package-lock.json`. Install frontend dependencies in an external directory and link its `node_modules` into `web/`; keep Astro generated state outside the repository too. Install the hash-locked `docs/requirements/docs.lock` and `learning.lock` into the docs environment.

```sh
python -m unittest project_tools.test_site_routes project_tools.test_reference_home project_tools.test_site_assembly project_tools.test_learning_assets -v
python project_tools/validate_learning_assets.py --manifest docs/assets/learning/manifest.json
npm --prefix web run check
npm --prefix web run test:unit
mkdocs build --strict --site-dir "$TASK_DATA/site-mkdocs"
python project_tools/check_docs.py --site-dir "$TASK_DATA/site-mkdocs"
python project_tools/extract_reference_home.py --site-dir "$TASK_DATA/site-mkdocs" --output "$TASK_DATA/reference-home"
SITE_INPUT_DIR="$TASK_DATA/reference-home" ASTRO_OUT_DIR="$TASK_DATA/site-astro" ASTRO_CACHE_DIR="$TASK_DATA/astro-cache" npm --prefix web run build
python project_tools/assemble_site.py --mkdocs "$TASK_DATA/site-mkdocs" --astro "$TASK_DATA/site-astro" --learning docs/assets/learning --routes docs/site/route-ownership.json --output "$TASK_DATA/site-assembled"
python project_tools/check_assembled_site.py --site-dir "$TASK_DATA/site-assembled" --base /quant-backtest-engine/ --legacy docs/site/legacy-route-anchors.json
SITE_DIR="$TASK_DATA/site-assembled" SITE_BASE=/quant-backtest-engine/ BROWSER_OUTPUT_DIR="$TASK_DATA/browser" npm --prefix web run test:e2e
```

Install the locked Playwright Chromium browser before the browser gate, or explicitly set `CHROME_EXECUTABLE` to a compatible installed Chrome. The test launcher serves the built artifact on a recorded free loopback port. Search remains scoped to MkDocs technical references. Shared locale preference never redirects a deep link.

The sole deployment owner is `.github/workflows/docs.yml`; it uploads only `site-assembled`. `site-build.json` binds the source revision, source/lock/manifest inputs and delivered file hashes. Original tutorial incorporation retains [PR 19](https://github.com/runchengxie/quant-backtest-engine/pull/19) and commit `4820af3b82940e7697cb8c92154315b1d59ee23d`. No historical rendered homepage is committed.
