"""Pure supplied-session arithmetic from the pinned Platform execution calendar.

Source: quant-platform 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355,
packages/platform/src/quant_platform/_portfolio/execution_calendar.py.
The original <=0/positive shift arithmetic is retained. Provider/weekday/future
resolution is deliberately outside this neutral supplied-date seam.
SPDX-License-Identifier: Apache-2.0
"""

from collections.abc import Sequence

from .contracts import ExecutionCalendar, strict_date


def execution_dates(calendar: ExecutionCalendar, *, start: str, end: str) -> tuple[str, ...]:
    strict_date(start)
    strict_date(end)
    return tuple(day for day in calendar.open_dates if start <= day <= end)


def execution_date_map(
    signal_dates: Sequence[str], shift_days: int, calendar: ExecutionCalendar
) -> dict[str, str | None]:
    if type(shift_days) is not int:
        raise ValueError("shift_days must be an integer")
    dates = sorted({strict_date(day) for day in signal_dates})
    result: dict[str, str | None] = {}
    for signal in dates:
        if shift_days <= 0:
            candidates = [day for day in calendar.open_dates if day >= signal]
            offset = 0
        else:
            candidates = [day for day in calendar.open_dates if day > signal]
            offset = shift_days - 1
        result[signal] = candidates[offset] if offset < len(candidates) else None
    return result
