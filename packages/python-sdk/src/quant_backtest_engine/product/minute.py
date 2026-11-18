"""Standard-library validation for exact minute-input.v1 transport.

Numerical execution and native validation are explicit core[minute] operations.
"""

from .types import ArtifactRef
from .validation import _array, _decimal, _ns, _shape

TAPES = ("quantity_locks", "corporate_actions", "valuation_events", "capital_flows")
CONFIG_DECIMALS = (
    "participation_rate",
    "buy_fee_bp",
    "sell_fee_bp",
    "commission_minimum_cny",
    "sell_tax_bp",
)
CONFIG_INTS = ("lot_size", "release_slices", "execution_minutes", "latency_minutes")


def _rows(rows, required, optional=(), decimals=(), clocks=()):
    for row in _array(rows, "rows"):
        _shape(row, required, optional)
        for key in decimals:
            if key in row:
                _decimal(row[key], key)
        for key in clocks:
            if key in row:
                _ns(row[key], key)


def validate_minute_input(manifest):
    """Validate every inline field; artifact contents are validated after loading."""
    _shape(manifest.initial_account, ("cash",))
    _decimal(manifest.initial_account["cash"], "cash")
    _shape(manifest.settings, ("config", "report_delay_seconds", "impact"))
    config = manifest.settings["config"]
    _shape(config, CONFIG_DECIMALS + CONFIG_INTS)
    for key in CONFIG_DECIMALS:
        _decimal(config[key], key)
    for key in CONFIG_INTS:
        if type(config[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    _decimal(manifest.settings["report_delay_seconds"], "report_delay_seconds")
    impact = manifest.settings["impact"]
    if impact is not None:
        _shape(impact, ("transient", "permanent", "decay_seconds"))
        for key, value in impact.items():
            _decimal(value, key)
    if set(dict(manifest.inputs)) | set(manifest.inline_inputs) != {"targets", "bars"}:
        raise ValueError("minute requires exactly targets and bars")
    if "targets" in manifest.inline_inputs:
        _rows(
            manifest.inline_inputs["targets"],
            ("decision_time", "entry_time", "symbol", "weight"),
            ("information_time", "order_type"),
            ("weight",),
            ("decision_time", "entry_time", "information_time"),
        )
    if "bars" in manifest.inline_inputs:
        nums = (
            "open",
            "high",
            "low",
            "close",
            "volume",
            "amount",
            "up_limit",
            "down_limit",
        )
        _rows(
            manifest.inline_inputs["bars"],
            ("time", "symbol", "tradable") + nums,
            ("interval_start", "mark_source_time", "mark_basis"),
            nums,
            ("time", "interval_start", "mark_source_time"),
        )
        for row in manifest.inline_inputs["bars"]:
            if type(row["tradable"]) is not bool:
                raise ValueError("tradable must be boolean")
    tapes = dict(manifest.tapes)
    if set(tapes) != set(TAPES):
        raise ValueError(
            "all four minute tapes must be explicit, including empty tapes"
        )
    specs = {
        "quantity_locks": (
            ("available_ns", "start_ns", "end_ns", "symbols", "source_binding"),
            (),
            (),
            ("available_ns", "start_ns", "end_ns"),
        ),
        "corporate_actions": (
            (
                "event_id",
                "symbol",
                "available_date",
                "record_date",
                "ex_date",
                "cash_per_share",
                "cash_pay_date",
                "stock_per_share",
                "stock_tradable_date",
                "withholding_rate",
            ),
            (),
            ("cash_per_share", "stock_per_share", "withholding_rate"),
            (),
        ),
        "valuation_events": (
            (
                "event_id",
                "symbol",
                "effective_time",
                "available_time",
                "value_per_share",
                "basis",
                "source",
            ),
            (),
            ("value_per_share",),
            ("effective_time", "available_time"),
        ),
        "capital_flows": (
            ("event_id", "effective_time", "available_time", "amount", "source"),
            (),
            ("amount",),
            ("effective_time", "available_time"),
        ),
    }
    for name, tape in tapes.items():
        if not isinstance(tape, ArtifactRef):
            _rows(tape, *specs[name])
