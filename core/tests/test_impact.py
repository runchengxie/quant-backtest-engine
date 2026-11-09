# Extracted from quant-platform/tests/test_impact_state.py at 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355.
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
import math

import pytest

from quant_backtest_core.backtest.impact import LinearImpact


def test_round_trip_has_nonnegative_cost_and_checkpoint_restores():
    model = LinearImpact(transient=0.02, permanent=0.01, decay_seconds=10)
    buy = model.execute("A", 0, 100)
    restored = LinearImpact.restore(model.checkpoint())
    sell = restored.execute("A", 10, -100)
    assert 100 * buy - 100 * sell >= 0
    assert sell == pytest.approx(2 * math.exp(-1) + 1 - 1.5)
    assert restored.offset("B", 10) == 0


def test_mechanical_splitting_cannot_reduce_cost():
    whole = LinearImpact(transient=0.02, permanent=0.01, decay_seconds=10)
    split = LinearImpact(transient=0.02, permanent=0.01, decay_seconds=10)
    cost = whole.execute("A", 0, 100) * 100
    assert sum(split.execute("A", 0, 10) * 10 for _ in range(10)) == pytest.approx(cost)


def test_permanent_state_does_not_decay_and_clock_cannot_reverse():
    model = LinearImpact(transient=0, permanent=0.01, decay_seconds=1)
    model.execute("A", 1, 100)
    assert model.offset("A", 1000) == 1
    with pytest.raises(ValueError, match="time"):
        model.execute("A", 999, 1)


@pytest.mark.parametrize(
    "kwargs", [{"transient": -1}, {"permanent": float("nan")}, {"decay_seconds": 0}]
)
def test_invalid_parameters(kwargs):
    with pytest.raises(ValueError):
        LinearImpact(**kwargs)


def test_independent_scenario_states_and_restored_state_do_not_alias():
    first = LinearImpact(transient=0.02, permanent=0.01, decay_seconds=10)
    second = LinearImpact(transient=0.02, permanent=0.01, decay_seconds=10)
    assert first.execute("A", 0, 100) == 1.5
    assert second.offset("A", 0) == 0
    checkpoint = first.checkpoint()
    restored = LinearImpact.restore(checkpoint)
    assert restored.execute("A", 0, -100) == 1.5
    assert restored.offset("A", 0) == 0
    assert first.offset("A", 0) == 3
    assert checkpoint["states"]["A"]["permanent"] == 1
