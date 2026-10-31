# From target weight to reconciled results

This synthetic walkthrough calls the Rust sizing utility, feeds its actual order
into the upstream-backed session engine, checks hand-computable results and saves
all requests/results. Python 3 and a prebuilt engine are sufficient; no data feed,
model package, platform service or runtime database is needed.

```sh
python3 project_tools/tutorial.py \
  --engine /absolute/path/to/quant-backtest-engine \
  --output /absolute/external/path/new-tutorial-run
```

Use a new output directory outside the checkout. The tool fails if the engine
fails or any expected economic result changes. CI runs it against the built CLI.

## What happens

A hypothetical model has already produced a 10% target weight. The example does
not train a model or make a research claim. The synthetic reference price of 10
is declared available before the first executable quote.

| Step | Calculation / observed outcome |
| --- | --- |
| Plan | CNY 10,000 × 10% / 10 = 100 shares; declared buy lot 100 |
| First fill | Buy 100 at 10; commission 1; cash 8,999 |
| First valuation | 100 × midpoint 11 = 1,100; NAV 10,099 |
| Same-day sale | Denied by configured T+1; reason retained in `rejections` |
| Next-session sale | Sell 100 at 12; commission 1.2; cash/NAV 10,197.8 |

The script replaces the fixture's first buy with the sizing utility's order.
The subsequent sell intents and quotes are synthetic fixture inputs. It checks
both daily balances, total commission 2.2, two actual fills and the denied order.
Saved JSON includes the executable SHA-256, sizing input/output and engine input/output.
Inspect `engine_result.json` for actual fills, order statuses, denial reasons and
`daily_ledger`; a completed run does not imply every order filled.

## Choose the next entry point

- For local research, call this CLI directly or use the Rust library.
- Python programs can use the [independent SDK](python-client.md) to receive
  dictionaries. Use the platform adapter when analytics need `CanonicalBacktestResult`
  tables. Both paths verify the executable digest.
- For durable batches, submit this saved `engine_request.json` as an immutable
  artifact to runtime v6 (`nautilus.session_replay`). Runtime controls process
  limits, job states and result publication. See [integration](runtime.md).

Use the [capability matrix](capabilities.md) and [correctness cases](correctness.md)
before migrating a real caller. This example does not cover corporate actions,
holidays, daily participation limits or exchange-specific taxes. The existing
Python backend remains available for those workflows.
