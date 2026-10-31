# Experimental releases

[简体中文](releases.zh-CN.md)

The first downloadable release is experimental: Linux x86_64 with glibc, built on
Ubuntu 22.04 (glibc 2.35) using Rust 1.99.0 and locked NautilusTrader 0.66.0 crates.
Other operating systems and musl binaries are not packaged. This is a CLI archive,
not a crates.io publication. Until the first prerelease is published, build from
source using the [quickstart](quickstart.md).

Use the [GitHub Releases page](https://github.com/runchengxie/quant-backtest-engine/releases)
for published prereleases. Download all three assets from the same release:

- `quant-backtest-engine-0.2.0-x86_64-unknown-linux-gnu.tar.gz`: executable,
  LGPL/GPL texts, dependency notices and build metadata.
- `quant-backtest-engine-0.2.0-x86_64-unknown-linux-gnu-source.tar.gz`: matching
  application source, `Cargo.lock`, all vendored Rust dependencies with published
  license texts, Cargo offline configuration and `REBUILD.md`.
- `SHA256SUMS`: checksums of both archives. Run `sha256sum --check SHA256SUMS`
  before extracting them. Checksums detect corruption; they are not signatures.

Extract the binary archive and run `./quant-backtest-engine capabilities` inside
its directory. Pass a request JSON to `./quant-backtest-engine run REQUEST.json`;
the source archive includes `fixtures/roundtrip.json` for a synthetic trial.
Build metadata records the exact Git revision, lockfile hash, compiler, Cargo,
platform and glibc. Linux binaries still depend on the system C runtime.

The executable statically links Rust dependencies, including LGPL NautilusTrader
crates. Matching complete sources let recipients change dependencies and rebuild
and relink the application. Read `REBUILD.md` in the source archive for offline
commands and how to modify vendored crates without checksum rejection. Install
Rust 1.99.0 and native build prerequisites first; these tools are not bundled.
The package supports repeatable source builds, without claiming byte-identical
binaries across machines or a legal guarantee. Preserve applicable copyright and
license notices when redistributing; see [third-party notices](third-party-notices.md).

## Maintainer packaging

Commit changes first, then run from a clean Linux x86_64 checkout with Python 3.11+:

```bash
python3 project_tools/package_release.py --output /absolute/external/release-output
```

Use the project's configured data directory for retained outputs. The script
archives the committed Git tree, vendors the lockfile dependencies, rejects crates
without license/notice files, and builds from those sources. A small explicit list
of published crates omits repository-wide license files; the packager supplements
these from the exact upstream source revisions (plus the Apache license text
explicitly offered by objc2). Downloaded texts are SHA-256 pinned; their URLs,
source revisions and hashes are recorded in `dependency-licenses.json` and the
texts are preserved in both archives without changing vendored crate files. It runs offline
release-profile `cargo test` and compilation with an empty Cargo home, then
executes capabilities and checks the synthetic fixture’s equity (10019.78) and
commission (0.22) from an extracted binary archive. Network access is needed for the initial vendor step and toolchain
setup. Build directories are temporary and removed after packaging.

The `Experimental Linux release` workflow runs this process on pull requests and
uploads artifacts for seven days. Manual dispatch defaults to `publish=false`,
which also only uploads artifacts. After merge and review, dispatch on `main` with
`publish=true` and a fresh tag such as `v0.2.0-alpha.1`. The publish job has
`contents: write`; the build job only has `contents: read`. Publication creates a
GitHub prerelease targeting the tested revision, never a crates.io release. Existing
release/tag names must not be reused. If a publication request loses its response,
inspect the remote release and tag before attempting it again.
