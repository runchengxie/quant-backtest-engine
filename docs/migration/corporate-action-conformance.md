# Corporate-action conformance: explicit remaining boundary

NautilusTrader 0.66.0 exposes useful public primitives, but the current adapter does
not claim complete corporate-action support. Continue using the existing
quant-platform raw-share corporate-action backend for these scenarios.

## Reproduction and result

Run the committed characterization test:

```sh
cargo test --locked quantity_adjustment_propagates_to_cache_but_does_not_rebase_a_stock_split
```

It buys 10 shares at USD 10 using the real upstream engine, applies the public
quantity-adjustment API to the cached position, then values 20 shares at USD 5.
The cache updates to quantity 20, while upstream open basis stays 10 and unrealized
PnL is -100. A true 2-for-1 split without a market move requires open basis 5 and
unrealized PnL 0. This is a characterization of the available **commission adjustment**
primitive, not an allegation that upstream claims it represents stock splits.

The pinned `PositionAdjustmentType` enum exposes Commission and Funding. Public
`Cache::update_position_from_adjustment` propagates the quantity change to cache;
`Position::apply_adjustment` does not rebase `avg_px_open`. Public
`SimulatedExchange::try_adjust_account` handles balance adjustments, and simulation
modules can return account adjustments, but these alone do not represent a complete
record-date entitlement, ex-date receivable, payment/release and stock-basis lifecycle.

## Cases retained on the Python backend

| Scenario | Required evidence before Rust migration |
| --- | --- |
| Cash dividend | Record-date ownership; ex-date receivable; actual payment date; withholding |
| Split/stock dividend | Quantity plus basis rebasing, released vs receivable shares, cache/portfolio consistency |
| Fractional entitlement | Explicit settlement or cash-in-lieu policy; no implicit integer truncation |
| Adjusted vs raw prices | No double counting of cash or share distributions |
| Delisting | Authoritative recovery/valuation policy; no arbitrary final liquidation |

Requests containing corporate-action fields or requesting a corporate-action capability
are rejected by the new strict schema, rather than ignored. Do not label configured
T+1, quote permissions and board-lot guards as complete A-share execution parity.

## Next extension boundary

A future adapter needs a public, replayable split/basis operation and auditable
receivable stages, plus matched tests against the existing Python lifecycle. Mutating
`avg_px_open` manually or maintaining a parallel cash account would bypass replay
history and violate this repository's thin-adapter boundary. Such a change should be
an explicitly reviewed upstream extension or backend choice, not a hidden fallback.
