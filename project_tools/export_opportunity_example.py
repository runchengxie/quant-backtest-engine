"""Export a bounded signed-opportunity example from the registered public Core wheel.

No matching, ledger or financial formula is implemented here. All output quantities
are returned by the public descriptive audit API. Inputs are synthetic, not samples
from a market, and recorded fees are caller-supplied assertions.
"""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
import sys
from decimal import Decimal
from importlib import metadata
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
API = "quant_backtest_core.evidence.transaction_costs.audit_transaction_costs"
SOURCE = "core/src/quant_backtest_core/evidence/transaction_costs.py"
EXPORTER = "project_tools/export_opportunity_example.py"
BASE_NS = 1798761600000000000  # 2027-01-01 00:00:00 UTC; synthetic sequence only.


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode()


def serialize(value):
    """Preserve owner decimal representations; never calculate an economic value."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [serialize(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("nonfinite owner output")
    if isinstance(value, (int, float, Decimal)):
        return str(value)
    raise TypeError(f"unsupported owner value: {type(value)}")


def verify_provider():
    """Reject editable/source installs, wheel substitutions and modified installs."""
    lock_raw = (ROOT / "docs/assets/method/owner-lock.json").read_bytes()
    lock = json.loads(lock_raw)
    distribution = metadata.distribution("quant-backtest-core")
    if distribution.version != "0.3.0":
        raise ValueError("wrong Core version")
    direct = json.loads(distribution.read_text("direct_url.json") or "{}")
    url = urlsplit(direct.get("url", ""))
    if url.scheme != "file" or direct.get("dir_info"):
        raise ValueError("ordinary registered wheel installation required")
    wheel = Path(unquote(url.path))
    if wheel.suffix != ".whl" or lock["wheels"].get(wheel.name) != digest(
        wheel.read_bytes()
    ):
        raise ValueError("unregistered Core wheel bytes")
    with ZipFile(wheel) as archive:
        for member in archive.namelist():
            if member.endswith(("/", "/RECORD")):
                continue
            installed = Path(distribution.locate_file(member))
            if not installed.is_file() or installed.read_bytes() != archive.read(
                member
            ):
                raise ValueError(
                    f"installed Core differs from registered wheel: {member}"
                )
    dependencies = {}
    for name, version in lock["dependencies"].items():
        installed_version = metadata.version(name)
        if installed_version != version:
            raise ValueError(f"wrong locked dependency: {name}")
        dependencies[name] = installed_version
    from quant_backtest_core.evidence import transaction_costs

    source = Path(inspect.getfile(transaction_costs)).resolve()
    if not source.is_relative_to(Path(sys.prefix).resolve()):
        raise ValueError("Core source outside installed environment")
    return transaction_costs.audit_transaction_costs, {
        "api": API,
        "provider_revision": lock["provider_revisions"]["core"],
        "wheel": {"name": wheel.name, "sha256": digest(wheel.read_bytes())},
        "source": {"path": SOURCE, "sha256": digest(source.read_bytes())},
        "exporter": {
            "path": EXPORTER,
            "sha256": digest((ROOT / EXPORTER).read_bytes()),
        },
        "owner_lock_sha256": digest(lock_raw),
        "dependencies": dependencies,
    }


def case_inputs(ident, benchmark):
    def clock(offset):
        return str(BASE_NS + offset * 1000000000)

    binding = "synthetic-opportunity-2027-v1"
    parent = {
        "parent_id": ident,
        "side": "buy",
        "requested_shares": "200",
        "reference_price": "10",
        "reference_ns": clock(0),
        "reference_available_ns": clock(1),
        "decision_ns": clock(2),
        "arrival_price": "10",
        "arrival_ns": clock(3),
        "arrival_available_ns": clock(4),
        "completed_ns": clock(10),
        "available_ns": clock(20),
        "status": "cancelled",
        "source_binding": binding,
        "evidence_kind": "synthetic",
        "quantity_unit": "shares",
        "currency": "CNY",
        "price_convention": "includes_spread_and_impact",
        "brokerage_terms_version": "synthetic-recorded-fee-v1",
        "opportunity_price": benchmark,
        "opportunity_ns": clock(15),
        "opportunity_available_ns": clock(16),
        "opportunity_benchmark": "synthetic terminal mid at 2027-01-01T00:00:15Z",
    }
    fill = {
        "fill_id": ident + ".fill",
        "parent_id": ident,
        "child_id": ident + ".child",
        "price": "10.1",
        "shares": "100",
        "fill_ns": clock(6),
        "receipt_ns": clock(7),
        "source_binding": binding,
        "evidence_kind": "synthetic",
        "quantity_unit": "shares",
        "currency": "CNY",
        "recorded_commission": "5",
        "recorded_tax": "0",
    }
    return {
        "parents": [parent],
        "fills": [fill],
        "options": {
            "billing": "parent",
            "commission_bps": "0",
            "minimum_commission": "0",
            "sell_tax_bps": "0",
        },
    }


def dataframe_rows(rows):
    # The public API explicitly requires integral nanosecond arguments. Decimal
    # strings remain unchanged in the published inputs; only clock types adapt.
    return [
        {
            key: int(value) if key.endswith("_ns") else value
            for key, value in row.items()
        }
        for row in rows
    ]


def export():
    audit, provenance = verify_provider()
    import pandas as pd

    cases = []
    for ident, benchmark in [("down", "8"), ("flat", "10"), ("up", "12")]:
        inputs = case_inputs(ident, benchmark)
        report = audit(
            pd.DataFrame(dataframe_rows(inputs["parents"])),
            pd.DataFrame(dataframe_rows(inputs["fills"])),
            **inputs["options"],
        )
        outputs = {
            "parents": report.parents.to_dict("records"),
            "fills": report.fills.to_dict("records"),
            **{
                name: getattr(report, name)
                for name in [
                    "schema",
                    "source_digest",
                    "duplicate_reports",
                    "billing",
                    "real_calibration",
                    "provenance_status",
                ]
            },
        }
        cases.append({"id": ident, "inputs": inputs, "outputs": serialize(outputs)})
    payload = {
        "schema": "engine-opportunity-example.v1",
        "provenance": provenance,
        "limitations": [
            "synthetic_not_market_probability",
            "caller_recorded_fees",
            "descriptive_opportunity_not_cash_debit",
            "real_calibration_unavailable",
            "attribution_not_additive",
        ],
        "cases": cases,
    }
    return payload | {
        "receipt": {
            "payload_sha256": digest(canonical(payload)),
            "canonicalization": "sorted compact UTF-8 JSON excluding receipt",
        }
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path)
    args = parser.parse_args()
    value = export()
    args.output.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    )
    if args.receipt:
        args.receipt.write_text(
            json.dumps(
                {
                    "schema": "engine-opportunity-export-receipt.v1",
                    "fixture_sha256": digest(args.output.read_bytes()),
                    "payload_sha256": value["receipt"]["payload_sha256"],
                    "provenance": value["provenance"],
                },
                sort_keys=True,
                indent=2,
            )
            + "\n"
        )


if __name__ == "__main__":
    main()
