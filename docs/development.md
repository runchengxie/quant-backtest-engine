# Development and verification

Requires Rust 1.99.0+; upstream crates are pinned to NautilusTrader 0.66.0.
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
publish through GitHub Actions artifacts to GitHub Pages; no force push or generated
site commits are needed. Theme selection persists through Material's built-in storage;
language switching links to the counterpart page and navigation stays in that locale.
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
successor or another maintained MkDocs-compatible theme before that date; the source
content remains Markdown and publication uses standard static Pages artifacts.
