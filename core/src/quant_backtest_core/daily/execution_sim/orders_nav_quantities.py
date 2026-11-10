"""Raw-share sell quantization after request, capacity and settlement constraints."""

from .config import ExecutionSimConfig


def _quantize_nav_sell_quantity(
    quantity: float, *, held_quantity: float, config: ExecutionSimConfig
) -> float:
    if config.sell_round_lot is None:
        return quantity
    # Fractional entitlement settlement belongs to the caller. The bounded
    # tolerance recognizes floating arithmetic only; it never expands a fill.
    if abs(held_quantity - round(held_quantity)) > min(config.lot_tolerance, 1e-8):
        raise ValueError(
            "execution_sim.sell_round_lot requires integral share holdings; "
            "resolve fractional corporate-action entitlements before selling."
        )
    # Only a fill covering the actual entire holding may use the odd-lot exception.
    if quantity >= held_quantity:
        return quantity
    lot = float(config.sell_round_lot)
    return (quantity // lot) * lot
