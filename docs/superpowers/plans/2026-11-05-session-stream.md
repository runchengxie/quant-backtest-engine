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

- [ ] Add callback tests proving snapshot equality, current-session selection and
  callback failure before the next pull; observe failure then extend the runner.
- [ ] Add framing tests for exact limits, strict keys, hashes and invalid sequencing;
  observe failure then implement a bounded parser and writer in `src/session_stream.rs`.
- [ ] Add real binary interactive tests for ready before EOF, reports before finish,
  final equality, missing finish and trailing input; add the CLI command.
- [ ] Document the protocol in aligned English and Chinese session guides.
- [ ] Run format, clippy, the complete Rust suite, CLI examples, SDK/project tools,
  strict documentation and locale validation; inspect the diff and commit.
