# Explicit suspended last-quote valuation

Add generic opt-in owner evidence over the existing adjusted daily ledger's carried marks. Keep executable price tables and all ledger arithmetic untouched. Default remains current-mark-only; no data, strategies or private parameters belong here.

ExecutionSimConfig adds valuation_policy='current_mark_only', valuation_suspension_col=None and valuation_max_stale_sessions=None. Opt-in policy 'suspended_last_quote' requires a nonempty selected suspension column and a positive integer session limit. Only adjusted sequenced NAV without corporate-action events is supported. Raw, ideal and capacity opt-in requests fail explicitly.

An actual positive finite current mark always wins. A missing current mark qualifies only if the selected row contains explicit boolean True, the live owner's last_prices contains a positive finite price matching an actual strictly prior quote, and quote age is within the declared global-session limit. Missing/unknown flag, prior mark, age or unsupported action remains unresolved. Do not infer suspension from a missing quote or buy/sell flags.

Endpoint evidence retains current-mark counts and missing-current symbols, and separately exposes policy, policy-valued symbols/quote ages and unresolved symbols. Completeness means complete under the declared policy; never relabel carried marks as current. No future price search, second ledger, filled execution quote or raw-share corporate-action claim.

Transport fields are optional extensions: old v1 manifests retain omission defaults, malformed opt-in fields reject, public direct/request/backend paths agree. Linked English/Chinese docs and synthetic tests accompany the change. Stable owner output/time/source contracts remain explicit.
