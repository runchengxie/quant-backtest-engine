# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/backtest/quantity_locks.py
# Original SHA256: 743767b66958def9b0b424747058906039a9da4e6126e06f25a340d19ca66435
"""Declared receipt-clock restrictions on physical share trading, not weights."""

from dataclasses import dataclass


@dataclass(frozen=True)
class QuantityLock:
    """Block both directions over an inclusive UTC nanosecond interval.

    Effect starts at max(available_ns, start_ns). Ending a notice never revives
    cancelled orders. source_binding identifies the caller's evidence; it does
    not certify that evidence or imply a broker-side restriction.
    """

    available_ns: int
    start_ns: int
    end_ns: int
    symbols: tuple[str, ...]
    source_binding: str

    def __post_init__(self):
        clocks = (self.available_ns, self.start_ns, self.end_ns)
        if (
            any(type(t) is not int or not 0 < t < 2**63 - 1 for t in clocks)
            or self.start_ns > self.end_ns
            or not isinstance(self.symbols, tuple)
            or not self.symbols
            or any(not isinstance(s, str) or not s.strip() for s in self.symbols)
            or len(set(self.symbols)) != len(self.symbols)
            or not isinstance(self.source_binding, str)
            or not self.source_binding.strip()
        ):
            raise ValueError("valid integer clocks, unique symbols and source binding required")

    def overlaps(self, start_ns: int, end_ns: int) -> bool:
        return max(self.available_ns, self.start_ns, start_ns) <= min(self.end_ns, end_ns)
