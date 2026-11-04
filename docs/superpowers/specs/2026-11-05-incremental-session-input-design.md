# Owned incremental session input

The library accepts an owned fallible iterator of whole market sessions through
`run_sessions_iter(SessionConfig, iterator)`. `SessionConfig` contains the v2
request header and instruments, with no session payload. Existing v2 APIs and CLI
schemas keep their current behavior. The selected approach shares the existing
Nautilus 0.66 engine driver; a second simulator or restart mechanism would require
additional financial semantics and is outside this change.

One dedicated worker owns the source and the upstream engine through disposal.
It validates and replays each session before requesting the next. Validation retains
instrument definitions, previous date and valuation boundary, and unique order IDs.
Strategy state loads only current-session pending orders and quote admission rules.
Whole-session boundaries preserve every timestamp group across symbols.

Late validation and source errors return an error with no successful final result.
Final reports, cumulative intent metadata and upstream financial histories remain
collected. Input buffering is session-sized; total process memory is not bounded.
There are no filesystem inputs, scheduling changes, report sinks or snapshot imports.
