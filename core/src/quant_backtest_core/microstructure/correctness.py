"""Legacy empty-start, best-quote-only matching diagnostic.

The initial snapshot supplies only the start clock, not the initial book.
Replay interval events and compare the resulting best quotes with the target;
this does not certify arbitrary snapshot-to-snapshot feed reconstruction.
ReplaySession separately seeds its supplied initial bid and ask.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .matching import MatchingEngine
from .pack import SimulatorEvent, SimulatorPack


@dataclass
class CorrectnessResult:
    matched: bool
    bid_error: int
    ask_error: int
    detail: str = ""
    comparable: bool = True

    @property
    def status(self) -> Literal["matched", "mismatched", "not_comparable"]:
        if not self.comparable:
            return "not_comparable"
        return "matched" if self.matched else "mismatched"


def _apply_event(engine: MatchingEngine, ev: SimulatorEvent) -> None:
    if ev.kind == "order":
        engine.apply_order(ev.order_id, ev.side, ev.price, ev.volume)
    elif ev.kind == "cancel":
        engine.cancel_order(ev.order_id)
    # trade 已由撮合引擎在 order 时结算，这里不重复处理


def replay_and_compare(
    pack: SimulatorPack,
    init_snapshot_idx: int = 0,
    target_snapshot_idx: int = 1,
) -> CorrectnessResult:
    """Compare target best quotes after replaying from an empty book.

    The initial snapshot sets only the start clock. Replay events strictly between
    the selected clocks; do not seed its bid/ask state as ReplaySession does.
    Identical nonempty snapshots without interval events remain a comparable
    mismatch, with both quote errors equal to one.
    """
    if not (0 <= init_snapshot_idx < len(pack.snapshots)):
        return CorrectnessResult(False, -1, -1, "init_snapshot 越界")
    if not (0 <= target_snapshot_idx < len(pack.snapshots)):
        return CorrectnessResult(False, -1, -1, "target_snapshot 越界")

    init = pack.snapshots[init_snapshot_idx]
    target = pack.snapshots[target_snapshot_idx]
    t_init = init.time_ms
    t_target = target.time_ms

    engine = MatchingEngine()
    # Legacy diagnostic: init supplies only the clock; its book is not seeded.
    # ReplaySession separately initializes its supplied bid/ask state.

    # Replay only events strictly inside (t_init, t_target).
    for ev in pack.events:
        if ev.time_ms <= t_init:
            continue
        if ev.time_ms >= t_target:
            break
        _apply_event(engine, ev)

    # 对比重建盘口与 target snapshot 期望值
    bid = engine.lob.best_bid()
    ask = engine.lob.best_ask()
    exp_bid = target.expected_bid
    exp_ask = target.expected_ask

    if exp_bid is None or exp_ask is None:
        # 无法对比（数据未携带期望值），返回重建结果供人工检查
        return CorrectnessResult(
            False,
            0,
            0,
            f"重建买一={bid} 卖一={ask}（target 无期望值，跳过严格对比）",
            comparable=False,
        )

    bid_error = 0 if bid == exp_bid else 1
    ask_error = 0 if ask == exp_ask else 1
    matched = bid_error == 0 and ask_error == 0
    return CorrectnessResult(
        matched,
        bid_error,
        ask_error,
        f"重建买一={bid} 期望={exp_bid}；卖一={ask} 期望={exp_ask}",
    )
