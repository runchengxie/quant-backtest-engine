# Interactive Session Transport Implementation Plan

The parent agent executes the authorized design with the current engine worker.

Goal is an independently usable bounded interactive transport.
Architecture adds report callbacks to the existing iterator runner and a separate
strict framing module. Tech stack is Rust, serde and SHA256.
Spec is [the design](../specs/2026-11-05-session-stream-design.md).

## Global constraints

Preserve v1/v2 APIs and results, upstream accounting and whole-session boundaries.
Use the fixed 67108864-byte line limit including newline. Finish requires EOF.

## Review focus

Reports must precede the next source read. Callback and source errors suppress final
success. Duplicate keys must survive deserialization until rejected. A large response
must never emit a partial frame. Raw bytes determine the digest, including whitespace.

## Steps

- [x] Add callback tests proving snapshot equality, current-session selection and
  callback failure before the next pull; observe failure then extend the runner.
- [x] Add framing tests for exact limits, strict keys, hashes and invalid sequencing;
  observe failure then implement a bounded parser and writer in `src/session_stream.rs`.
- [x] Add real binary interactive tests for ready before EOF, reports before finish,
  final equality, missing finish and trailing input; add the CLI command.
- [x] Document the protocol in aligned English and Chinese session guides.
- [x] Run format, clippy, the complete Rust suite, CLI examples, SDK/project tools,
  strict documentation and locale validation; inspect the diff and commit.

## Validation record

Validated the implementation based on main revision `c0e14a8` with 67 passing Rust
unit and integration tests, including real binary interaction and fixed input limits.
`cargo fmt --all --check`, `cargo clippy --locked --all-targets -- -D warnings`,
`cargo test --locked`, the documented roundtrip CLI and the synthetic tutorial passed.
All 11 SDK tests passed both from source and from an installed wheel against the real
binary, and all 12 project tooling tests passed. The strict documentation build and
rendered locale, counterpart, theme and local asset checks passed. `git diff --check`
passed. Build, tutorial, wheel and site outputs are retained outside the repository.

The old financial fixtures run through the batch, iterator and callback APIs with
their original assertions preserved. New tests cover snapshot timing, callback failure,
input source errors, exact byte limits, duplicate and unknown fields, invalid UTF-8,
truncation, invalid sequences, missing finish, trailing frames and oversized final
output without partial serialization. Earlier report frames remain provisional.
