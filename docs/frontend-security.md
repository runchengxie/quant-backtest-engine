# Frontend build dependency mitigation

[简体中文](frontend-security.zh-CN.md)

The site is static. Its build currently uses a local mitigation for [GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf), because the upstream advisory lists no patched picomatch release. This is not an upstream fixed version and a raw `npm audit` still reports the affected version.

All transitive copies are pinned to picomatch 4.0.7. After a clean locked install, `npm --prefix web run security:patch` verifies every original package file against `web/security/picomatch.json` and inserts an explicit rejection of every repeated extglob (`+(...)` and `*(...)`). Ordinary wildcards, globstars, braces and non-repeated extglobs remain supported. Rejected patterns raise an error rather than silently skipping files. This deliberately restricts build-tool semantics, including escaped or nested patterns that parse as repeated extglobs. The guard applies before recursion options can disable analysis. It does not change the financial backend or published browser data.

```sh
# Install the locked web dependencies in an external task directory and link web/node_modules first.
npm --prefix web run security:patch
node --test project_tools/test_frontend_security.cjs
FRONTEND_AUDIT_RECEIPT="$TASK_DATA/frontend-audit.json" npm --prefix web run audit:locked
```

The security manifest records the registry tarball integrity and the complete original/patched file identities; it does not rename the package or claim a new release. Patch installation is idempotent and rejects unexpected bytes. Astro verifies all installed copies and the lock graph before loading build configuration. A fresh install must be patched before Astro check/build.

This mitigation protects tooling after installation. npm installation lifecycle scripts run before patching; it is not an install-time sandbox.

The audit gate retains the original npm report. It admits this advisory and its transitive metadata reports only when every installed copy has the exact mitigation. Unknown advisories, missing copies, modified entrypoints, malformed results, unresolved dependency chains, command failures and registry errors stop publication. Do not replace this gate with an unrestricted advisory allowlist or change its threshold to make a build pass.

Regression checks exercise public matching/parse/regex APIs, nested and multi-branch repeated patterns, capture and disabled recursion options in a bounded child process, ordinary glob compatibility, package tampering and negative audit cases. Full site/browser acceptance validates the restricted dependency graph. This does not establish the absence of every possible regular-expression vulnerability in third-party tooling.

Retire the local patch, manifest and single-advisory handling together after an upstream release addresses the advisory: update the lock, require the ordinary audit to pass, and rerun security and site/browser acceptance. Preserve the patch's source history and verification receipts.
