# Execution and valuation assumptions

## Timing and execution assumptions

- An intent becomes eligible on the **first quote for its instrument strictly after
  `information_ts_ns`**. It is submitted from that quote callback. Upstream executes
  against its current simulated market. Equal-time information cannot trade that quote.
- At a shared timestamp, quote input order and then order-intent input order determine
  processing order and cash availability. This is part of the reproducibility contract.
- Buy market orders cross the ask; sells cross the bid. This is an L1 quote model,
  not a daily-bar open/close model, volume participation model or order-book replay.
- Quote size is a fixed 1,000,000 shares per side. It is synthetic liquidity;
  **no real capacity or partial-fill realism is claimed**.
- Requests contain precomputed intents, not executable strategies or target weights.
  Portfolio construction and conversion from weights to quantities belong to callers.
- The upstream proportional fee model rounds commission using USD precision.
  A pretrade cash guard uses that same upstream fee function and upstream `deny_order`
  API to reject buys whose notional plus commission exceeds available cash. Buys
  queued in one quote callback reserve this amount; sell proceeds from that callback
  become reusable on a later callback after upstream accounting has processed them.
  This guard addresses upstream 0.66.0 notional-only cash admission, without
  changing matching, fills or account balances.
- No forced liquidation occurs at the end. A remaining position is marked at its
  instrument's last bid/ask midpoint; positions may therefore have stale marks if
  instrument histories end at different times. This is a valuation convention,
  not a claim that liquidation can occur at midpoint.
- Information timestamps are caller assertions. They do not prove that features,
  prices or model training inputs were historically available.

