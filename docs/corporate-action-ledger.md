# Raw-share corporate-action ledger

Language: English · [简体中文](corporate-action-ledger.zh-CN.md)

Core 0.3.0 implements the daily owner graph; release availability still requires merged-source and exact-wheel receipts. Selection, research statistics and bundle publication remain Platform. See [daily inputs](product/daily-inputs.md).


`simulate_execution_adjusted_nav` accepts optional caller-supplied
`CorporateAction` events. The feature is opt-in: calls that pass `None` keep
the existing price-return behavior and result shape. Passing an empty iterable
still opts in, requires raw prices, and returns empty `actions` and populated
`holdings` receipts.

## Event contract

- Each event requires `available_date <= record_date < ex_date`.
- Cash distributions require `cash_pay_date`; share distributions require
  `stock_tradable_date`. Settlement dates cannot precede `ex_date`.
- `record_date`, `ex_date`, and any supplied settlement date that falls inside
  the simulation window must match a session in the supplied execution
  calendar. `available_date` is validated as a date but is not checked against
  that calendar.
- Supplying `corporate_actions` requires `price_basis="raw"`, even when the
  iterable is empty. Event IDs must be unique. Symbols and event IDs must be
  nonempty normalized strings; distribution amounts and withholding rates must
  be finite and within their allowed ranges.
- Events distribute cash, additional shares, or both. Fractional shares are
  retained; the ledger does not calculate cash in lieu.

## Entitlement and settlement

The ledger captures entitlement from the shares held at the close of
`record_date`, after that session's fills. It cannot import holdings from
before the simulation, so a record date before the first simulated session
does not create entitlement in that run.

On `ex_date`, cash becomes a receivable and additional shares become a stock
receivable. Stock receivables are valued at the symbol's raw price. Cash becomes
spendable on `cash_pay_date`; additional shares join holdings and become sellable on
`stock_tradable_date`. These events are processed before that session's orders.
Open orders for an affected symbol are canceled on its ex-date.

An optional `withholding_rate` applies one flat rate to that event's cash
distribution. Its default is zero, meaning no withholding is modeled. It is
an analytical assumption, not a historical holding-period tax model.

## Results and limits

When enabled, `actions` records lifecycle stages processed during the run:
`record`, `ex`, `cash_payment`, and `stock_release`. The result also contains
per-day `holdings` receipts. Daily rows add `cash_receivable` and
`stock_receivable_value`; the summary records the accounting conventions.
Missing valid raw marks while a corporate action is outstanding fail closed.

This is a public accounting mechanism tested with synthetic fixtures. It does
not establish historical corporate-action completeness, provide historical
broker fees or board-specific quantity schedules, make a live-trading claim,
infer adjusted prices, fill in missing settlement dates, or calculate
cash-in-lieu proceeds. The caller must source and normalize events. Research
workflows should also retain a hash of the normalized input. Conflicting
revisions or multiple reports for one ex-date need independent resolution
before use.

The new request empty tuple maps to None; direct legacy empty still enables raw-share receipts. The eight unified tables retain original values. Receivables remain in daily/actions/holdings; the old cash-plus-positions reconciler excludes them and cannot certify total NAV while rights are outstanding.
