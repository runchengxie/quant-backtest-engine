"""Owner, schema and exact-clock regressions for the extracted financial graph."""

import json

import pandas as pd
import pytest
from test_minute_execution import bars, targets
from test_minute_session import Policy, make

from quant_backtest_core.backtest._minute_checkpoint import _digest
from quant_backtest_core.backtest.minute import MinuteExecutionConfig
from quant_backtest_core.backtest.minute_session import MinuteSession


def test_relocated_v2_checkpoint_rejected():
    session = make()
    value = session.checkpoint()
    assert value["schema"] == "minute-session.v3"
    value["schema"] = "minute-session.v2"
    value.pop("digest")
    value["digest"] = _digest(value)
    with pytest.raises(ValueError, match="original pinned sources"):
        MinuteSession.restore(session.targets, session.bars, session.config, value, policy=Policy())


@pytest.mark.parametrize("offset,accepted", [(-1, True), (0, False), (1, False)])
def test_decision_entry_one_nanosecond_boundary(offset, accepted):
    t = targets()
    t["decision_time"] = t.entry_time + pd.Timedelta(offset, unit="ns")
    cfg = MinuteExecutionConfig(10000, 0.1, 0, 0)
    if accepted:
        session = MinuteSession(t, bars(), cfg, policy=Policy())
        assert (
            session.targets.entry_time.iloc[0].value - session.targets.decision_time.iloc[0].value
            == 1
        )
        assert not session.run().fills.empty
    else:
        with pytest.raises(ValueError, match="entry must be after decision"):
            MinuteSession(t, bars(), cfg, policy=Policy())


@pytest.mark.parametrize("offset,accepted", [(-1, True), (0, True), (1, False)])
def test_information_decision_one_nanosecond_boundary(offset, accepted):
    t = targets()
    t["information_time"] = t.decision_time + pd.Timedelta(offset, unit="ns")
    cfg = MinuteExecutionConfig(10000, 0.1, 0, 0)
    if accepted:
        assert not MinuteSession(t, bars(), cfg, policy=Policy()).run().fills.empty
    else:
        with pytest.raises(ValueError, match="information_time"):
            MinuteSession(t, bars(), cfg, policy=Policy())


def test_failed_owner_preserves_original_error_and_last_checkpoint():
    session = make()
    before = json.dumps(session.checkpoint(), sort_keys=True)
    original = RuntimeError("synthetic financial step failure")

    def fail():
        raise original

    session._step = fail
    with pytest.raises(RuntimeError) as caught:
        session.step()
    assert caught.value is original
    for operation in (session.step, session.run, session.checkpoint):
        with pytest.raises(ValueError, match="failed session"):
            operation()
    restored = MinuteSession.restore(
        session.targets, session.bars, session.config, json.loads(before), policy=Policy()
    )
    assert not restored.run().fills.empty
