# Extracted from quant-platform/packages/platform/src/quant_platform/analytics/transaction_costs.py
# Source revision: 7a618bddd8fdeee5dbe37fe5b54a9698e0de5355
# SPDX-License-Identifier: Apache-2.0; see core/licenses/quant-platform-Apache-2.0.txt.
"""Descriptive parent-order cost evidence, with no matching or cash mutation.

All money is CNY and quantities are raw shares. Modeled brokerage fees are not
recorded actual fees. Evidence labels and cluster identities are caller assertions.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from numbers import Integral

import pandas as pd

_PARENT_COLUMNS = {
    "parent_id",
    "side",
    "requested_shares",
    "reference_price",
    "reference_ns",
    "reference_available_ns",
    "decision_ns",
    "arrival_price",
    "arrival_ns",
    "arrival_available_ns",
    "completed_ns",
    "available_ns",
    "status",
    "source_binding",
    "evidence_kind",
    "quantity_unit",
    "currency",
    "price_convention",
    "brokerage_terms_version",
}
_FILL_COLUMNS = {
    "fill_id",
    "parent_id",
    "child_id",
    "price",
    "shares",
    "fill_ns",
    "receipt_ns",
    "source_binding",
    "evidence_kind",
    "quantity_unit",
    "currency",
}
_OBSERVATION_COLUMNS = [
    "available_ns",
    "completed_ns",
    "participation",
    "filled_notional",
    "shortfall_bps",
    "side",
    "liquidity_bucket",
    "execution_minutes",
    "cluster_id",
    "parent_id",
    "source_binding",
    "evidence_kind",
    "fee_basis",
    "source_digest",
]


def _missing(value):
    return value is None or bool(pd.isna(value))


def _number(value, name, *, optional=False, positive=False, integer=False):
    if optional and _missing(value):
        return None
    try:
        result = Decimal(str(value))
    except Exception as exc:
        raise ValueError(f"{name} requires a finite number") from exc
    if isinstance(value, bool) or not result.is_finite() or result < 0:
        raise ValueError(f"{name} requires a finite nonnegative number")
    if (positive and result == 0) or (integer and result != result.to_integral_value()):
        raise ValueError(f"{name} requires positive values / integer shares")
    return result


def _clock(value, name):
    if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
        raise ValueError(f"{name} requires integer UTC nanoseconds")
    return int(value)


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"explicit {name} required")
    return value


def _identity(row):
    _text(row["source_binding"], "source binding")
    if row["evidence_kind"] not in {"synthetic", "broker_fills"}:
        raise ValueError("explicit evidence_kind required")
    if row["quantity_unit"] != "shares" or row["currency"] != "CNY":
        raise ValueError("only raw shares and CNY units are supported")


def _optional_quote(row, prefix, *, earliest, latest):
    price = _number(row.get(f"{prefix}_price"), f"{prefix}_price", positive=True, optional=True)
    clock = row.get(f"{prefix}_ns")
    available = row.get(f"{prefix}_available_ns")
    if _missing(clock) and _missing(available) and price is None:
        return None
    clock = _clock(clock, f"{prefix}_ns")
    if not earliest <= clock <= latest:
        raise ValueError(f"invalid {prefix} benchmark clock")
    if not _missing(available) or price is not None:
        available = _clock(available, f"{prefix}_available_ns")
        if not clock <= available <= latest:
            raise ValueError(f"invalid {prefix} benchmark availability")
    return price


def _parent(row):
    _identity(row)
    _text(row["parent_id"], "parent id")
    _text(row["brokerage_terms_version"], "brokerage terms version")
    if row["side"] not in {"buy", "sell"} or row["status"] not in {"completed", "cancelled"}:
        raise ValueError("explicit side and terminal status required")
    if row["price_convention"] != "includes_spread_and_impact":
        raise ValueError("execution prices must include spread and impact once")
    _number(row["requested_shares"], "requested_shares", positive=True, integer=True)
    _number(row["reference_price"], "reference_price", positive=True)
    for name in (
        "reference_ns",
        "reference_available_ns",
        "decision_ns",
        "completed_ns",
        "available_ns",
    ):
        row[name] = _clock(row[name], name)
    if not (
        row["reference_ns"]
        <= row["reference_available_ns"]
        <= row["decision_ns"]
        <= row["completed_ns"]
        <= row["available_ns"]
    ):
        raise ValueError("invalid reference/decision/completion/availability clocks")
    _optional_quote(row, "arrival", earliest=row["decision_ns"], latest=row["available_ns"])
    if not _missing(row["arrival_ns"]) and row["arrival_ns"] > row["completed_ns"]:
        raise ValueError("arrival after completion")
    opportunity = _optional_quote(
        row, "opportunity", earliest=row["completed_ns"], latest=row["available_ns"]
    )
    if opportunity is not None:
        _text(row.get("opportunity_benchmark"), "opportunity benchmark and horizon")
    _liquidity(row)
    return row


def _liquidity(row):
    volume = _number(row.get("market_volume_shares"), "market_volume_shares", optional=True)
    amount = _number(row.get("market_amount_cny"), "market_amount_cny", optional=True)
    if volume is None and amount is None:
        return None
    if row.get("liquidity_quantity_unit") != "shares" or row.get("liquidity_amount_unit") != "CNY":
        raise ValueError("verified liquidity shares/CNY unit declarations required")
    start = _clock(row.get("liquidity_start_ns"), "liquidity_start_ns")
    end = _clock(row.get("liquidity_end_ns"), "liquidity_end_ns")
    available = _clock(row.get("liquidity_available_ns"), "liquidity_available_ns")
    if not row["decision_ns"] <= start <= end == row["completed_ns"] <= available <= row[
        "available_ns"
    ] or (not _missing(row["arrival_ns"]) and start != row["arrival_ns"]):
        raise ValueError("same execution interval liquidity and availability required")
    if volume is None or amount is None or volume == 0 or amount == 0:
        return None
    _text(row.get("liquidity_bucket"), "liquidity bucket")
    _number(row.get("execution_minutes"), "execution_minutes", integer=True, positive=True)
    return volume


def _fill(row, parent):
    _identity(row)
    for name in ("fill_id", "parent_id", "child_id"):
        _text(row[name], name)
    if any(row[name] != parent[name] for name in ("source_binding", "evidence_kind")):
        raise ValueError("fill and parent source/evidence mismatch")
    row["price"] = _number(row["price"], "price", positive=True).normalize()
    row["shares"] = int(_number(row["shares"], "shares", integer=True, positive=True))
    fill_clock, receipt = _clock(row["fill_ns"], "fill_ns"), _clock(row["receipt_ns"], "receipt_ns")
    start = parent["decision_ns"] if _missing(parent["arrival_ns"]) else parent["arrival_ns"]
    if (
        not start <= fill_clock <= parent["completed_ns"]
        or not fill_clock <= receipt <= parent["available_ns"]
    ):
        raise ValueError("invalid fill/receipt/completion clocks")
    for name in ("recorded_commission", "recorded_tax"):
        value = _number(row.get(name), name, optional=True)
        if value is not None and value != value.quantize(Decimal("0.01")):
            raise ValueError("recorded allocated fees must be exact CNY cents")
        row[name] = None if value is None else value.normalize()


def _canonical(value):
    if isinstance(value, dict):
        return {str(key): _canonical(item) for key, item in value.items()}
    if _missing(value):
        return None
    if isinstance(value, Integral):
        return int(value)
    if isinstance(value, (float, Decimal)):
        return str(value)
    return value


def _digest(parents, fills, terms):
    def rows(frame):
        return sorted(
            json.dumps(_canonical(row), sort_keys=True) for row in frame.to_dict("records")
        )

    payload = {
        "schema": "transaction-cost-evidence.v1",
        "parents": rows(parents),
        "fills": rows(fills),
        "terms": terms,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _deduplicate(fills, by_parent):
    unique, children = {}, {}
    for row in fills.to_dict("records"):
        if row["parent_id"] not in by_parent:
            raise ValueError("fill references unknown parent")
        _fill(row, by_parent[row["parent_id"]])
        child = row["child_id"]
        if children.setdefault(child, row["parent_id"]) != row["parent_id"]:
            raise ValueError("child id belongs to multiple parents")
        previous = unique.get(row["fill_id"])
        if previous is not None:
            fields = (set(previous) | set(row)) - {"receipt_ns"}
            if any(_canonical(previous.get(key)) != _canonical(row.get(key)) for key in fields):
                raise ValueError("conflicting physical fill reports")
            previous["receipt_ns"] = min(previous["receipt_ns"], row["receipt_ns"])
        else:
            unique[row["fill_id"]] = row.copy()
    return sorted(unique.values(), key=lambda row: row["fill_id"])


def _cents(value):
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _fees(rows, side, billing, commission, minimum, tax):
    groups = {}
    for fill in rows:
        key = fill["parent_id"] if billing == "parent" else fill["child_id"]
        notional = Decimal(str(fill["price"])) * Decimal(str(fill["shares"]))
        groups[key] = groups.get(key, Decimal(0)) + notional
    commissions = sum(
        (_cents(max(minimum, value * commission / 10000)) for value in groups.values()), Decimal(0)
    )
    taxes = (
        sum((_cents(value * tax / 10000) for value in groups.values()), Decimal(0))
        if side == "sell"
        else Decimal(0)
    )
    return commissions, taxes


def _recorded_fees(rows):
    if not rows:
        return None
    if any(
        _missing(row.get(name)) for row in rows for name in ("recorded_commission", "recorded_tax")
    ):
        return None
    return sum(
        (
            Decimal(str(row[name]))
            for row in rows
            for name in ("recorded_commission", "recorded_tax")
        ),
        Decimal(0),
    )


def _components(parent, rows, terms):
    requested = Decimal(str(parent["requested_shares"]))
    shares = sum((Decimal(str(row["shares"])) for row in rows), Decimal(0))
    if shares > requested:
        raise ValueError("physical fills exceed requested shares")
    notional = sum(
        (Decimal(str(row["shares"])) * Decimal(str(row["price"])) for row in rows), Decimal(0)
    )
    reference = Decimal(str(parent["reference_price"]))
    sign = Decimal(1 if parent["side"] == "buy" else -1)
    price_shortfall = sign * (notional - shares * reference)
    arrival = _number(parent["arrival_price"], "arrival_price", optional=True)
    opportunity = _number(parent.get("opportunity_price"), "opportunity_price", optional=True)
    commission, tax = _fees(rows, parent["side"], **terms)
    modeled, recorded = commission + tax, _recorded_fees(rows)
    volume = _liquidity(parent)
    unavailable = [
        name
        for name, missing in (
            ("arrival_quote", arrival is None),
            ("opportunity_benchmark", opportunity is None),
            ("liquidity", volume is None),
            ("recorded_fees", recorded is None),
        )
        if missing
    ]
    return parent | {
        "filled_shares": int(shares),
        "unfilled_shares": int(requested - shares),
        "filled_notional": float(notional),
        "completion": float(shares / requested),
        "modeled_commission": float(commission),
        "modeled_tax": float(tax),
        "modeled_cash_fees": float(modeled),
        "recorded_cash_fees": None if recorded is None else float(recorded),
        "fee_evidence": "unavailable" if recorded is None else "caller_recorded",
        "reference_price_shortfall": float(price_shortfall),
        "arrival_price_shortfall": None
        if arrival is None
        else float(sign * (notional - shares * arrival)),
        "delay_shortfall": None
        if arrival is None
        else float(sign * shares * (arrival - reference)),
        "reference_shortfall_with_modeled_fees": float(price_shortfall + modeled),
        "reference_shortfall_with_recorded_fees": None
        if recorded is None
        else float(price_shortfall + recorded),
        "opportunity_shortfall": None
        if opportunity is None
        else float(sign * (requested - shares) * (opportunity - reference)),
        "participation": None if volume is None else float(shares / volume),
        "attribution_additive": False,
        "unavailable_reasons": tuple(unavailable),
    }


@dataclass(frozen=True)
class CostEvidenceReport:
    """Descriptive tables. Consumers retain ownership of their economic ledger."""

    parents: pd.DataFrame
    fills: pd.DataFrame
    source_digest: str
    duplicate_reports: int
    billing: str
    schema: str = "transaction-cost-evidence.v1"
    real_calibration: str = "unavailable"
    provenance_status: str = "caller_asserted"

    def cost_observations(self, *, fee_basis: str) -> pd.DataFrame:
        """Adapt supported filled parents to the existing past-only scope API.

        An explicit basis prevents modeled fees from becoming actual fee evidence.
        Zero fills and missing same-interval liquidity remain in ``parents`` only.
        """
        if fee_basis not in {"modeled", "recorded"}:
            raise ValueError("explicit modeled or recorded fee basis required")
        result = []
        for row in self.parents.to_dict("records"):
            shortfall = row[f"reference_shortfall_with_{fee_basis}_fees"]
            if row["filled_shares"] == 0 or row["participation"] is None or shortfall is None:
                continue
            result.append(
                {name: row.get(name) for name in _OBSERVATION_COLUMNS}
                | {
                    "shortfall_bps": float(
                        Decimal(str(shortfall))
                        / (Decimal(str(row["reference_price"])) * row["filled_shares"])
                        * 10000
                    ),
                    "fee_basis": fee_basis,
                    "source_digest": self.source_digest,
                }
            )
        return pd.DataFrame(result, columns=_OBSERVATION_COLUMNS)


def audit_transaction_costs(
    parents: pd.DataFrame,
    fills: pd.DataFrame,
    *,
    billing: str,
    commission_bps: float,
    minimum_commission: float,
    sell_tax_bps: float,
) -> CostEvidenceReport:
    """Audit terminal parent orders and deduplicate physical reports, without debits.

    See ``docs/backtest/transaction-cost-evidence.md`` for normalized columns,
    availability constraints, cent rounding, benchmark overlap and limitations.
    """
    if billing not in {"parent", "child"}:
        raise ValueError("explicit parent or child billing required")
    terms = {
        "billing": billing,
        "commission": _number(commission_bps, "commission_bps"),
        "minimum": _number(minimum_commission, "minimum_commission"),
        "tax": _number(sell_tax_bps, "sell_tax_bps"),
    }
    if not set(parents) >= _PARENT_COLUMNS or not set(fills) >= _FILL_COLUMNS:
        raise ValueError("missing normalized parent/fill columns")
    if parents.columns.duplicated().any() or fills.columns.duplicated().any():
        raise ValueError("duplicate normalized column names")
    records = [_parent(row) for row in parents.to_dict("records")]
    by_parent = {row["parent_id"]: row for row in records}
    if len(records) != len(by_parent):
        raise ValueError("duplicate parent ids")
    unique = _deduplicate(fills, by_parent)
    normalized = [
        _components(row, [f for f in unique if f["parent_id"] == row["parent_id"]], terms)
        for row in sorted(records, key=lambda row: row["parent_id"])
    ]
    digest = _digest(parents, fills, {key: str(value) for key, value in terms.items()})
    return CostEvidenceReport(
        pd.DataFrame(normalized, dtype=object),
        pd.DataFrame(unique, columns=fills.columns, dtype=object),
        digest,
        len(fills) - len(unique),
        billing,
    )
