# Engine delivery acceptance

Goal: close the existing reusable Engine delivery with reproducible installed
financial examples and verified deployed bytes. This resumes the approved reusable
product design and Tasks 19–20; it adds no financial model or consumer cutover.

Source baseline: `062a820de013d824686e6b5f6582843618929d27` (PR 26).

- [ ] Build independent SDK/core wheels; run isolated SDK 3.11 and core 3.12/3.13
  profiles from neutral directories. Execute the existing Rust account walkthrough,
  minute recovery, scenario callback, bounded-planning oracle and daily financial
  fixture. Preserve exact source, wheel, dependency and result identities externally.
- [ ] Add a standard-library deployed-site verifier with tests for stale revision,
  changed bytes and invalid receipt paths. Compare all receipt-listed files,
  including both renderers and evidence assets. Network failures and hash mismatches
  remain failures. Integrate its tests into the existing docs workflow.
- [ ] Update paired product entry documentation with the verified source combination,
  executable acceptance commands and explicit remaining gates. Keep original dated
  migration/checkpoint history. Do not imply PyPI publication, Runtime v9 readiness,
  empirical calibration or general nonconvex solver support.
- [ ] Run required Engine checks, review the whole diff once, deliver through an
  owner PR, verify current-target CI, merge, verify deployed exact-source bytes,
  and remove only this task's clean branch/worktree.

Review focus: never treat unavailable ledgers as zero; install wheels without
Platform/Runtime/Research; preserve source-specific legacy recovery; do not fetch
receipt paths outside the declared HTTPS site; do not retry a content mismatch into
success. Original task resources are preserved because they were not created by this
continuation. Generated evidence belongs under the configured Engine DATA_ROOT.
