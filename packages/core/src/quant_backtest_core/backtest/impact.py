# Extracted from quant-platform/packages/platform/src/quant_platform/backtest/impact.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Uncalibrated linear propagator for research stress scenarios.

Coefficients are price units per signed share; time is elapsed seconds on one
consistent clock. Fees/spread are separate. Half the current fill increment is
included in execution price, preventing same-clock splitting advantages. This
model does not identify a real market's counterfactual response.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass


@dataclass
class _State:
    time: float
    transient: float = 0.0
    permanent: float = 0.0


class LinearImpact:
    def __init__(self, *, transient=0.0, permanent=0.0, decay_seconds=60.0):
        values = (transient, permanent, decay_seconds)
        if any(not math.isfinite(v) or v < 0 for v in values) or decay_seconds == 0:
            raise ValueError("impact coefficients must be nonnegative; decay_seconds positive")
        self.transient = float(transient)
        self.permanent = float(permanent)
        self.decay_seconds = float(decay_seconds)
        self._states: dict[str, _State] = {}

    def _at(self, symbol, time):
        if not isinstance(symbol, str) or not symbol.strip() or not math.isfinite(time):
            raise ValueError("invalid symbol or time")
        previous = self._states.get(symbol, _State(time))
        if time < previous.time:
            raise ValueError("impact time cannot move backwards")
        return _State(
            float(time),
            previous.transient * math.exp(-(time - previous.time) / self.decay_seconds),
            previous.permanent,
        )

    def offset(self, symbol, time):
        """Advance the symbol clock and return its current mid-price displacement."""
        state = self._at(symbol, time)
        self._states[symbol] = state
        return state.transient + state.permanent

    def preview(self, symbol, time, quantity):
        """Average price displacement of a fill without changing state."""
        if not math.isfinite(quantity):
            raise ValueError("invalid quantity")
        state = self._at(symbol, time)
        return (
            state.transient + state.permanent + 0.5 * (self.transient + self.permanent) * quantity
        )

    def execute(self, symbol, time, quantity):
        price_offset = self.preview(symbol, time, quantity)
        state = self._at(symbol, time)
        state.transient += self.transient * quantity
        state.permanent += self.permanent * quantity
        self._states[symbol] = state
        return price_offset

    def checkpoint(self):
        return {
            "schema": "linear-impact.v1",
            "transient": self.transient,
            "permanent": self.permanent,
            "decay_seconds": self.decay_seconds,
            "states": {symbol: asdict(state) for symbol, state in self._states.items()},
        }

    @classmethod
    def restore(cls, checkpoint):
        if checkpoint.get("schema") != "linear-impact.v1":
            raise ValueError("unsupported impact checkpoint")
        model = cls(**{k: checkpoint[k] for k in ("transient", "permanent", "decay_seconds")})
        for symbol, payload in checkpoint["states"].items():
            state = _State(**payload)
            if any(not math.isfinite(v) for v in asdict(state).values()):
                raise ValueError("invalid impact state")
            model._at(symbol, state.time)
            model._states[symbol] = state
        return model
