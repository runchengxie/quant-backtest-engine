"""Pure explicit-input financial closure from pinned Platform (Apache-2.0)."""

from __future__ import annotations

import pandas as pd

from ._execution_models import ParticipationSlippageModel, SlippageModel


def slippage_pricing_row(
    *,
    slippage_model: SlippageModel,
    amount_tables: dict[str, pd.DataFrame],
    entry_date: pd.Timestamp,
) -> pd.Series | None:
    if not isinstance(slippage_model, ParticipationSlippageModel):
        return None
    return amount_tables[slippage_model.amount_col].loc[entry_date]
