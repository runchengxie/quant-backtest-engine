# Deterministic replay

[简体中文](replay.zh-CN.md)

`ReplaySession` consumes explicitly supplied `BackgroundOrder` and `InterventionOrder`
values. It does not load or train a generator. Create a separate engine and session
for each scenario; replay owns an order book, not a cash account or portfolio ledger.

```python
from quant_backtest_core.microstructure.matching import MatchingEngine
from quant_backtest_core.microstructure.replay import InterventionOrder, ReplaySession

session = ReplaySession(MatchingEngine(), (100, 50), (101, 40))
session.add_background(10, 1, 101, 3, "background")
session.add_intervention(InterventionOrder(10, 1, 101, 5, "intervention"))
session.run()
assert [fill.buy_id for fill in session.fills] == ["intervention", "background"]
```

Equal-clock interventions precede background events; each input stream retains its
stable input sequence. Runs consume each pending batch once. Subsequent batches may
append at the processed clock but cannot move backwards. Mutable queued timestamps
are rechecked before any matching effect. Boolean and noninteger clocks reject;
integer clocks above 2^53 remain exact within the native signed-64-bit range.

Python records complete per-fill prices, quantities, time and source. Native v0.1
returns aggregate trades and book ticks only: empty native `fills` means unavailable
evidence, not zero executions. Do not infer execution cost or impact from those
empty lists. No fill reconstruction or second financial ledger is added.

See [matching](matching.md) for pack ordering and correctness, and
[the four execution modes](../development/microstructure-rust.md).
Provider B source is implemented; release availability and consumer migration remain pending.
