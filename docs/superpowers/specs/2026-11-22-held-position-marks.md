# Held-position endpoint mark evidence

The daily owner must certify valuation endpoints from its live financial state,
not the union of past and future target symbols. This repairs false missing-mark
failures for future targets, exited positions and cash-only portfolios while
preserving unknown intervals for genuinely held missing marks.

Add optional `valuation_marks=None` to `ExecutionAdjustedNavResult`. Successful
ideal and adjusted/sequenced runs emit one row per daily endpoint after orders,
using the existing shares, cash and corporate-action rights ledger. Include held
symbols, outstanding stock-right symbols, required/current/missing marks,
endpoint completeness and reasons. Positive held shares and stock rights require
current finite positive prices. Cash and cash rights must be finite; known cash
rights do not require prices for previously sold shares. No financial arithmetic,
carried NAV, corporate-action checks or execution controls change.

The runner requires aligned owner evidence. Initial cash is the first opening
endpoint; subsequent returns require both adjacent endpoints. A recovered closing
mark alone does not certify its opening interval. Capacity remains unsupported.
The product raw owner result preserves the additive table; this is endpoint
coverage, not a new normalized economic valuation-event ledger. Existing result
construction remains compatible through a default field.

Public synthetic tests cover all three modes, missing/stale/current recovered
marks, future unheld targets, sold-out gaps, all cash, cash/stock rights and
transport. Docs are bilingual. Validate Core/SDK tests, ownership, Rust and the
strict external documentation build. No private research data enters Engine.
