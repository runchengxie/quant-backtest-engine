"""The minute transport contract remains usable with only the SDK on Python 3.11."""

import copy
import json
import unittest
from pathlib import Path

from quant_backtest_engine.product import parse_manifest


class MinuteContractTests(unittest.TestCase):
    def setUp(self):
        self.wire = json.loads(
            (
                Path(__file__).resolve().parents[2]
                / "fixtures/product/minute-session.json"
            ).read_text()
        )

    def test_exact_string_clocks_and_decimals(self):
        manifest = parse_manifest(self.wire)
        self.assertEqual(manifest.input_schema, "minute-input.v1")
        for name in ("time", "interval_start"):
            wire = copy.deepcopy(self.wire)
            wire["inline_inputs"]["bars"][0][name] = int(
                wire["inline_inputs"]["bars"][0][name]
            )
            with self.assertRaises(ValueError):
                parse_manifest(wire)
        wire = copy.deepcopy(self.wire)
        wire["settings"]["config"]["buy_fee_bp"] = 3.0
        with self.assertRaises(ValueError):
            parse_manifest(wire)

    def test_explicit_tapes_and_no_unknown_execution_fields(self):
        for key in self.wire["tapes"]:
            wire = copy.deepcopy(self.wire)
            del wire["tapes"][key]
            with self.assertRaises(ValueError):
                parse_manifest(wire)
        wire = copy.deepcopy(self.wire)
        wire["settings"]["execute"] = "arbitrary.command"
        with self.assertRaises(ValueError):
            parse_manifest(wire)

    def test_unknown_evidence_is_null_but_required_input_cash_is_not(self):
        from quant_backtest_engine.product import EvidenceTable
        table = EvidenceTable("daily", "available", ({"nav": None, "pnl": None},), None)
        self.assertIsNone(table.rows[0]["nav"])
        wire = copy.deepcopy(self.wire)
        wire["initial_account"]["cash"] = None
        with self.assertRaises(ValueError): parse_manifest(wire)
