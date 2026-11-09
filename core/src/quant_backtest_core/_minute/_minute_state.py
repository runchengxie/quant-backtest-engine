# SPDX-License-Identifier: Apache-2.0
# Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# Original: packages/platform/src/quant_platform/_portfolio/_minute_state.py
# Original SHA256: a14428a9ea216697a77dee31bd35389988afcde73442976e3eb58973114f777b
"""Immutable policy-visible minute account contract."""

from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MinuteDecisionState:
    """Synchronous delivered account, strictly before the decision-clock bar.

    No exchange-report delay is modeled. Raw marks may be stale: consumers must
    inspect mark_times. Pending orders remain live until entry supersession.
    """

    time: pd.Timestamp
    cash: float
    nav: float
    holdings: Mapping
    marks: Mapping
    mark_times: Mapping
    pending_orders: tuple
    cash_receivable: float
    stock_receivable_value: float
    locked_symbols: tuple[str, ...] = ()
    quantity_locks: tuple = ()
