import hashlib
import sys

import pytest
from quant_backtest_engine.product.types import ArtifactRef

from quant_backtest_core.daily.calendar import execution_date_map, execution_dates
from quant_backtest_core.daily.contracts import ExecutionCalendar


def test_semantic_digest_and_original_shift_arithmetic():
    raw = b'{"schema":"execution-calendar.v1","timezone":"Asia/Shanghai","open_dates":["2026-01-02","2026-01-05"]}\n'
    c = ExecutionCalendar(
        "Asia/Shanghai", ("2026-01-05", "2026-01-02", "2026-01-05"), hashlib.sha256(raw).hexdigest()
    )
    assert c.semantic_bytes() == raw
    artifact = ArtifactRef(
        "memory://calendar", hashlib.sha256(raw[:-1]).hexdigest(), "application/json"
    )
    assert c.sha256 != artifact.sha256
    assert c.open_dates == ("2026-01-02", "2026-01-05")
    assert execution_dates(c, start="2026-01-02", end="2026-01-05") == c.open_dates
    for shift in (-4, 0):
        assert execution_date_map(["2026-01-02", "2026-01-03"], shift, c) == {
            "2026-01-02": "2026-01-02",
            "2026-01-03": "2026-01-05",
        }
    assert execution_date_map(["2026-01-02", "2026-01-05"], 1, c) == {
        "2026-01-02": "2026-01-05",
        "2026-01-05": None,
    }
    assert execution_date_map(["2026-01-01"], 2, c) == {"2026-01-01": "2026-01-05"}
    assert execution_dates(c, start="2026-01-06", end="2026-01-01") == ()
    assert "rqdatac" not in sys.modules


def test_empty_sessions_never_fabricated():
    c = ExecutionCalendar.from_dates("UTC", ())
    assert execution_date_map(["2026-01-02"], 1, c) == {"2026-01-02": None}
    assert execution_dates(c, start="2026-01-01", end="2026-12-31") == ()
    with pytest.raises(TypeError):
        execution_date_map(["2026-01-02"], 1, c, allow_future=True)


@pytest.mark.parametrize(
    "day", ["20260101", "2026-1-01", "2026-02-30", "2026-01-01T00:00:00", 20260101]
)
def test_strict_dates(day):
    with pytest.raises(ValueError):
        ExecutionCalendar.from_dates("UTC", (day,))


def test_timezone_and_digest():
    for zone in ("", "+08:00", "Not/AZone"):
        with pytest.raises(ValueError):
            ExecutionCalendar.from_dates(zone, ())
    with pytest.raises(ValueError, match="digest"):
        ExecutionCalendar("UTC", (), "0" * 64)
