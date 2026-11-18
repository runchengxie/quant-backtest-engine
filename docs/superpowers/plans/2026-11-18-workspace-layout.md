# Workspace layout migration

Execute inline. The user explicitly approved apps/packages/tests/scripts with each package owning src, and requested algorithm assurance, Rust migration and website polish. Algorithm provider PR39 must merge before source moves; visual polish is the next separately deliverable task.

## Approved layout

- apps/docs: current web Astro project.
- packages/engine: current Rust src, tests, examples/profile_sessions.rs and package Cargo.toml. Root Cargo.toml becomes a virtual workspace with this default member. Preserve root Cargo.lock. Exclude the separately built PyO3 crate.
- packages/core: current core; packages/python-sdk: current python; packages/microstructure-native: current core-native.
- tests/fixtures: current shared fixtures. Package-only golden fixtures stay with their package.
- tests/acceptance: current verify_installed_*.py and verify_period_leg_parity.py.
- scripts/build, scripts/verify, scripts/release: current project_tools by responsibility, including associated helper tests. Shared workspace path resolution lives under scripts.
- docs and required README/license/manifests stay at the root. Production/data roots and service pins remain unchanged.
- examples/product and examples/diagnostics belong to packages/core/examples. Rust profiling example belongs to packages/engine/examples.

## Historical evidence constraint

Do not rewrite historical source revisions, checkpoints, owner locks or published financial fixture values. Seven pinned method exporters (export_method_fixtures and six HELPERS) must retain exact bytes at their new physical paths. A checked legacy->current source-path mapping resolves their historical logical paths when validating source hashes. Reproduction of that historical exporter stages its unchanged files and fixture inputs in a task-specific external legacy layout, then runs the registered exact owners. This preserves exact fixture bytes and source proof; no new source tree financial imports are permitted. Other active CLI/documentation paths migrate normally. Add explicit migration tests for current paths, provenance resolution, malicious traversal, and unchanged pinned financial code/fixtures.

## Tasks

- [x] Fast-forward task branch after PR39 merge. Snapshot source hashes of financial modules, pinned exporters and public fixtures.
- [x] Add failing layout/path/staging tests, then move packages/apps/tests/tools. Preserve financial source bytes and adjust only repository/build/tooling references.
- [x] Update Cargo workspace, UV path lock, Python tests/fixtures, native manifests, release packaging, CI and paired current docs.
- [ ] Run native, installed wheels/extras, ownership, tool/unit/source-projection, complete site/browser and release package tests. One bounded independent review.
- [ ] Validate current target, PR/merge, cleanup own task. Continue website polish and final exact live verification.

## Rulings

Pinned exporters remain immutable reproduction sources. Their new maintenance wrapper stages old logical paths externally; it never changes installed owner arithmetic or re-labels old evidence as a new experiment.

Review fixes: positional microstructure wheel paths and benchmark fixture roots were corrected. A real benchmark smoke and the existing installed-native CI checks cover these entrypoints. Checkpoint comparison preserves the complete numerical environment because dependency-file hashes can differ between otherwise same-version virtual environments.
