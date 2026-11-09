"""生成式回放闭环。

以初始盘口为 prefix，将背景订单流（Transformer 生成）与外部干预订单
（如 TWAP 子单）按时间顺序送入确定性撮合引擎，产出合成市场轨迹。
"""

from __future__ import annotations

from dataclasses import dataclass
from numbers import Integral

from .matching import Fill, MatchingEngine, Trade


def _integer_time_ms(value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise ValueError("replay time_ms must be an integer")
    return int(value)


@dataclass
class InterventionOrder:
    """外部干预订单（如算法拆单子单），由用户显式插入模拟上下文。"""

    time_ms: int
    side: int
    price: int
    volume: int
    order_id: str = "INTERVENE"


@dataclass
class BackgroundOrder:
    """背景订单流中的一笔（模型自回归生成）。"""

    time_ms: int
    side: int
    price: int
    volume: int
    order_id: str = ""


@dataclass(frozen=True)
class ReplayFill(Fill):
    """Actual execution evidence in replay order (Python backend only)."""

    time_ms: int
    source: str


@dataclass
class Tick:
    time_ms: int
    best_bid: tuple[int, int] | None
    best_ask: tuple[int, int] | None
    source: str  # "background" | "intervention" | "init"


class ReplaySession:
    """初始盘口 prefix + 背景流 + 外部干预 → 撮合回放 → 轨迹。"""

    def __init__(
        self,
        engine: MatchingEngine,
        initial_bid: tuple[int, int],
        initial_ask: tuple[int, int],
        init_time_ms: int = 0,
    ) -> None:
        self._processed_time_ms = _integer_time_ms(init_time_ms)
        self.engine = engine
        self._background: list[BackgroundOrder] = []
        self._interventions: list[InterventionOrder] = []
        self.ticks: list[Tick] = []
        self.fills: list[ReplayFill] = []
        self._background_sequence = 0
        self._order_ids = {"INIT_BID", "INIT_ASK"}
        # 注入初始盘口 prefix
        bid_px, bid_vol = initial_bid
        ask_px, ask_vol = initial_ask
        self.engine.apply_order("INIT_BID", 1, bid_px, bid_vol)
        self.engine.apply_order("INIT_ASK", -1, ask_px, ask_vol)
        self.ticks.append(
            Tick(init_time_ms, self.engine.lob.best_bid(), self.engine.lob.best_ask(), "init")
        )

    def add_background(
        self, time_ms: int, side: int, price: int, volume: int, order_id: str = ""
    ) -> None:
        self.validate_timestamp(time_ms)
        if order_id:
            self._order_ids.add(order_id)
        self._background.append(BackgroundOrder(time_ms, side, price, volume, order_id))

    def add_intervention(self, order: InterventionOrder) -> None:
        self.validate_timestamp(order.time_ms)
        self._order_ids.add(order.order_id)
        self._interventions.append(order)

    def validate_timestamp(self, time_ms: int) -> None:
        """Check a proposed timestamp without changing queued or executed state."""
        timestamp = _integer_time_ms(time_ms)
        if timestamp < self._processed_time_ms:
            raise ValueError("event time_ms precedes processed replay time")

    def validate_pending(self) -> None:
        """Recheck mutable queued orders before allocating IDs or matching."""
        order: BackgroundOrder | InterventionOrder
        for order in self._background:
            self.validate_timestamp(order.time_ms)
        for order in self._interventions:
            self.validate_timestamp(order.time_ms)

    def reserve_order_id(self, candidate: str) -> str:
        """Reserve a child ID disjoint from queued, historical and live order IDs."""
        order_id = candidate
        suffix = 0
        while order_id in self._order_ids or self.engine.has_order(order_id):
            suffix += 1
            order_id = f"{candidate}_{suffix}"
        self._order_ids.add(order_id)
        return order_id

    def run(self) -> list[Tick]:
        """Consume queued orders once; ticks and Python fill evidence are cumulative."""
        self.validate_pending()
        for order in sorted(self._background, key=lambda o: o.time_ms):
            if not order.order_id:
                order.order_id = self.reserve_order_id(f"BG{self._background_sequence}")
            self._background_sequence += 1
        if self.engine.backend == "rust":
            background = [
                (o.time_ms, o.side, o.price, o.volume, o.order_id) for o in self._background
            ]
            interventions = [
                (o.time_ms, o.side, o.price, o.volume, o.order_id) for o in self._interventions
            ]
            self.ticks.extend(Tick(*row) for row in self.engine.replay(background, interventions))
            self._processed_time_ms = max(
                (_integer_time_ms(o.time_ms) for o in self._background + self._interventions),
                default=self._processed_time_ms,
            )
            self._background.clear()
            self._interventions.clear()
            return self.ticks
        bg = sorted(self._background, key=lambda o: o.time_ms)
        iv = sorted(self._interventions, key=lambda o: o.time_ms)
        bi = ivi = 0
        o: BackgroundOrder | InterventionOrder
        while bi < len(bg) or ivi < len(iv):
            next_bg = bg[bi].time_ms if bi < len(bg) else None
            next_iv = iv[ivi].time_ms if ivi < len(iv) else None
            if next_iv is not None and (next_bg is None or next_iv <= next_bg):
                o = iv[ivi]
                trade = self.engine.apply_order(o.order_id, o.side, o.price, o.volume)
                self._record_fills(trade, o.time_ms, "intervention")
                self.ticks.append(
                    Tick(
                        o.time_ms,
                        self.engine.lob.best_bid(),
                        self.engine.lob.best_ask(),
                        "intervention",
                    )
                )
                self._processed_time_ms = _integer_time_ms(o.time_ms)
                ivi += 1
            else:
                o = bg[bi]
                trade = self.engine.apply_order(o.order_id, o.side, o.price, o.volume)
                self._record_fills(trade, o.time_ms, "background")
                self.ticks.append(
                    Tick(
                        o.time_ms,
                        self.engine.lob.best_bid(),
                        self.engine.lob.best_ask(),
                        "background",
                    )
                )
                self._processed_time_ms = _integer_time_ms(o.time_ms)
                bi += 1
        self._background.clear()
        self._interventions.clear()
        return self.ticks

    def _record_fills(self, trade: Trade | None, time_ms: int, source: str) -> None:
        if trade is not None:
            self.fills.extend(
                ReplayFill(f.buy_id, f.sell_id, f.price, f.volume, time_ms, source)
                for f in trade.fills
            )
