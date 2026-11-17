# Joint execution benchmark contract

This additive planning reference compares finite target-weight paths by replaying the existing MinuteSession owner. It owns no second cash ledger. A caller supplies an as-of forecast market scenario, terminal PSD covariance, execution configuration, finite weight choices, and optional observed/committed prefix. Forecast/risk availability must not exceed the planning cutoff. Only the first chosen target is actionable; later targets are contingent.

Minimize `initial_economic_NAV_at_decision - owner_terminal_marked_NAV + risk_aversion * exposure.T @ covariance @ exposure / (2 * initial_economic_NAV_at_decision)`. Forecast prices encode the declared expected price path. Owner-paid fees and impact are already included in NAV and are never debited twice. Terminal marks are not guaranteed liquidation cash. Risk is a terminal-exposure penalty in this first version, not a general dynamic risk model.

Fixed/minimum fees, integer lots, T+1, capacity, delayed delivery, and transient/permanent linear impact reuse the owner. Past bars and committed decisions are replayed by that same owner; no fabricated delivered balance or modified checkpoint is injected. Input arrays/data frames are copied and bound to an explicit request digest.

Complete enumeration certifies only the declared finite scenario/domain. Larger domains use deterministic budgeted coordinate search with a feasible incumbent, explicit evaluation counts and no invented global bound. Computation/validation failures must propagate. Limits and unsupported cases are explicit.

Acceptance covers independent small-domain enumeration, changed decisions under fees/capacity/forecast decay/impact, partial-sale funding, delayed reports, prefix state equivalence, mutation protection, invalid availability/covariance/marks, and exhausted-budget status. Public tests/docs use synthetic inputs only. This is not a calibrated market model or a proprietary algorithm reproduction.
