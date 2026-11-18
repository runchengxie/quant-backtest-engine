# Extracted from quant-platform/packages/platform/src/quant_platform/analytics/execution_integrity.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Internal exact arithmetic helpers retained from execution_integrity."""

from decimal import (
    Context,
    Decimal,
    DecimalException,
    Inexact,
    InvalidOperation,
    Overflow,
    localcontext,
)
from functools import wraps


def _exact(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            with localcontext(Context(prec=64, traps=[Inexact, InvalidOperation, Overflow])):
                return function(*args, **kwargs)
        except DecimalException as error:
            raise ValueError("decimal accounting exceeds exact 64-digit contract") from error

    return wrapped


def _decimal(value, *, minimum=None):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as error:
        raise ValueError("finite decimal required") from error
    if not number.is_finite() or (minimum is not None and number < minimum):
        raise ValueError("finite decimal within bounds required")
    return number


def _clock(value):
    if type(value) is not int or not 0 < value < 2**63:
        raise ValueError("integer UTC nanosecond clock required")
    return value
