"""Product boundary tests run under unittest discovery and pytest."""
import copy
from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
import unittest

from quant_backtest_engine.product import (
    ArtifactRef, BackendDescriptor, ClockSet, EvidenceTable, FailureInfo,
    NormalizationReceipt, PolicyRef, ProductManifest, ProductResult,
    ProviderIdentity, ScenarioIdentity, TABLE_NAMES, loads_manifest, loads_result,
    manifest_to_json, parse_manifest, parse_result, require_capabilities,
    result_to_json,
)

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures/product/rust-session.json"
DIGEST = "a" * 64


def provider():
    return ProviderIdentity("rust.nautilus.sessions", "synthetic-provider", "0.2.0",
                            None, None, (("nautilus", "0.66.0"),), DIGEST)


def receipt():
    return NormalizationReceipt(adapter_version="0.1.0", source_schema="engine_result.v2",
                                source_sha256=DIGEST, unavailable_fields=("rights",))


class ProductContractsTests(unittest.TestCase):
    def test_daily_profile_admission_requires_actual_validated_inputs(self):
        from quant_backtest_engine.product.capabilities import PENDING_INPUT_SCHEMAS, VALIDATED_INPUT_SCHEMAS
        self.assertNotIn("daily-input.v1", PENDING_INPUT_SCHEMAS)
        self.assertIn("daily-input.v1", VALIDATED_INPUT_SCHEMAS)
        with self.assertRaises(ValueError):
            replace(parse_manifest(self.wire()), input_schema="daily-input.v1")

    def test_capacity_rejects_unsupported_rules(self):
        for control in (
            "enforce_price_limits",
            "enforce_listing_status",
            "enforce_t1",
            "round_lot",
            "sell_round_lot",
            "unfilled_buy_action",
            "unfilled_sell_action",
        ):
            with self.subTest(control=control):
                wire = json.loads((FIXTURE.parent / "daily.json").read_text())
                wire["settings"]["mode"] = "capacity"
                config = wire["settings"]["config"]
                config[control] = (
                    "cancel"
                    if control.startswith("unfilled_")
                    else 100
                    if control in ("round_lot", "sell_round_lot")
                    else True
                )
                if control == "enforce_price_limits":
                    config.update(limit_up_col="limit_up", limit_down_col="limit_down")
                    for row in wire["inline_inputs"]["pricing"]:
                        row.update(limit_up=True, limit_down=False)
                elif control == "enforce_listing_status":
                    config["listing_status_col"] = "listing_status"
                    for row in wire["inline_inputs"]["pricing"]:
                        row["listing_status"] = "delisted"
                with self.assertRaisesRegex(ValueError, f"capacity.*{control}"):
                    parse_manifest(wire)

    def test_supported_capacity_profile_roundtrips(self):
        wire = json.loads((FIXTURE.parent / "daily.json").read_text())
        wire["settings"]["mode"] = "capacity"
        self.assertEqual(manifest_to_json(parse_manifest(wire)), wire)

    def test_listing_enforcement_rejected_for_adjusted_and_sequenced(self):
        for mode in ("adjusted", "sequenced"):
            for status in ("halt", "delisted"):
                with self.subTest(mode=mode, status=status):
                    value = json.loads((FIXTURE.parent / "daily.json").read_text())
                    value["settings"]["mode"] = mode
                    value["settings"]["config"].update(
                        enforce_listing_status=True, listing_status_col="listing_status")
                    for row in value["inline_inputs"]["pricing"]:
                        row["listing_status"] = status if row["trade_date"] == "2020-01-03" else "listed"
                    with self.assertRaisesRegex(ValueError, f"{mode}.*enforce_listing_status"):
                        parse_manifest(value)

    def wire(self):
        return json.loads(FIXTURE.read_text())

    def digest(self, value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    def descriptor(self, **changes):
        d = BackendDescriptor(provider(), ("rust-session.v1",),
                              ("backtest-product-result.v1",), (),
                              ("session_ledger",), (("cash", "CNY"),), ())
        return replace(d, **changes)

    def test_exact_roundtrip_and_immutable_snapshot(self):
        wire = self.wire()
        wire["clocks"].update(available_ns="1760000000000000001",
                              information_ns="1760000000000000001",
                              decision_ns="1760000000000000002", entry_ns="1760000000000000002")
        wire["settings"]["fee_bps"] = "0.22"
        manifest = parse_manifest(wire)
        self.assertEqual(manifest_to_json(manifest), wire)
        before = self.digest(manifest_to_json(manifest))
        wire["tapes"]["sessions"][0]["quotes"][0]["ask"] = "999"
        wire["inline_inputs"]["instruments"][0]["symbol"] = "CHANGED"
        exported = manifest_to_json(manifest)
        exported["tapes"]["sessions"][0]["quotes"].clear()
        self.assertEqual(self.digest(manifest_to_json(manifest)), before)
        with self.assertRaises((FrozenInstanceError, AttributeError)):
            manifest.currency = "USD"
        with self.assertRaises(TypeError):
            manifest.inline_inputs["instruments"][0]["symbol"] = "OTHER"

    def test_unknown_duplicate_nonfinite_and_code_selection_rejected(self):
        mutations = [
            lambda w: w.update(unknown=True),
            lambda w: w["clocks"].update(unknown=None),
            lambda w: w["inline_inputs"]["instruments"][0].update(unknown=1),
            lambda w: w["settings"].update(fee_bps=0.22),
            lambda w: w["initial_account"].update(cash=10000),
            lambda w: w["tapes"]["sessions"][0]["quotes"][0].update(ask=10),
            lambda w: w["tapes"]["sessions"][0]["quotes"][0].update(ts_ns=1760000000000000001),
            lambda w: w["settings"].update(fee_bps="NaN"),
            lambda w: w.update(policy={"id": "os:system", "version": "1",
                                     "state_schema": "state.v1", "config": {}}),
            lambda w: w.update(policy={"id": "valid-policy", "version": "1",
                                     "state_schema": "state.v1", "config": {}, "import": "os"}),
            lambda w: w.update(backend_id="module:function"),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                wire = self.wire()
                mutate(wire)
                with self.assertRaises(ValueError):
                    parse_manifest(wire)
        raw = json.dumps(self.wire())
        for invalid in ('{"schema":"backtest-product.v1","schema":"x"}',
                        raw.replace('"fee_bps": "10"', '"fee_bps": NaN')):
            with self.assertRaises(ValueError):
                loads_manifest(invalid)

    def test_duplicate_inputs_and_required_tape_presence(self):
        wire = self.wire()
        wire["inputs"]["instruments"] = wire["calendar"]
        with self.assertRaises(ValueError):
            parse_manifest(wire)
        wire = self.wire()
        del wire["tapes"]["sessions"]
        with self.assertRaises(ValueError):
            parse_manifest(wire)
        wire = self.wire()
        wire["tapes"]["sessions"] = []
        self.assertEqual(dict(parse_manifest(wire).tapes)["sessions"], ())
        wire["tapes"]["sessions"] = wire["calendar"]
        self.assertIsInstance(dict(parse_manifest(wire).tapes)["sessions"], ArtifactRef)

    def test_generic_clocks_do_not_invent_total_order(self):
        clocks = ClockSet("20", "10", "21", "22", "1", "2", "0")
        self.assertEqual(clocks.effective_ns, "1")
        for invalid in (1, True, "1.2", "1e3", " 1", "01"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                replace(clocks, available_ns=invalid)
        wire = self.wire()
        wire["clocks"].update(effective_ns="1", report_ns="0", valuation_ns="2")
        parse_manifest(wire)
        wire["clocks"].update(available_ns="30", decision_ns="20")
        with self.assertRaises(ValueError):
            parse_manifest(wire)
        invalid = FIXTURE.with_name("invalid-clock.json")
        with self.assertRaises(ValueError):
            loads_manifest(invalid.read_text())

    def test_profile_session_types_and_causal_order(self):
        for mutate in (
            lambda s: s.update(open_ts_ns=s["valuation_ts_ns"], valuation_ts_ns="1"),
            lambda s: s.update(unknown=[]),
            lambda s: s["orders"][0].update(side="hold"),
            lambda s: s["quotes"][0].update(tradable="true"),
            lambda s: s["orders"][0].update(information_ts_ns=1),
            lambda s: s["orders"][0].update(quantity=100),
        ):
            wire = self.wire()
            mutate(wire["tapes"]["sessions"][0])
            with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                parse_manifest(wire)

    def test_capabilities_require_explicit_backend_schema_units(self):
        manifest = parse_manifest(self.wire())
        require_capabilities(manifest, self.descriptor())
        for descriptor in (
            self.descriptor(identity=replace(provider(), backend_id="other")),
            self.descriptor(input_schemas=("other.v1",)),
            self.descriptor(result_schemas=()),
            self.descriptor(capabilities=()),
            self.descriptor(units=(("cash", "USD"),)),
        ):
            with self.subTest(descriptor=descriptor), self.assertRaises(ValueError):
                require_capabilities(manifest, descriptor)
        wire = self.wire()
        wire["input_schema"] = "future.v1"
        wire["tapes"] = {}
        future = parse_manifest(wire)
        with self.assertRaises(ValueError):
            require_capabilities(future, self.descriptor(input_schemas=("future.v1",)))

    def test_evidence_empty_is_available_unknown_requires_reason(self):
        self.assertEqual(EvidenceTable("fills", "available", (), None).rows, ())
        for args in (
            ("fills", "unavailable", (), None),
            ("fills", "unavailable", ({"price": "0"},), "unsupported"),
            ("fills", "available", (), "unsupported"),
            ("unknown-table", "available", (), None),
            ("fees", "available", ({"amount": 0},), None),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                EvidenceTable(*args)
        self.assertEqual(len(TABLE_NAMES), 14)

    def test_result_roundtrip_identity_and_nested_snapshots(self):
        row = {"price": "0.22", "ts_ns": "1760000000000000001",
               "details": {"labels": ["synthetic"]}}
        result = ProductResult("completed", DIGEST, provider(),
                               (EvidenceTable("fills", "available", (row,), None),
                                EvidenceTable("rights", "unavailable", (), "not reported")),
                               {"final_cash": "10197.8"}, None, receipt(), None, None)
        wire = result_to_json(result)
        self.assertIsNone(wire["provider"]["source_revision"])
        self.assertIsNone(wire["provider"]["source_sha256"])
        self.assertEqual(wire["provider"]["artifact_sha256"], DIGEST)
        self.assertEqual(result_to_json(parse_result(wire)), wire)
        row["details"]["labels"].append("changed")
        self.assertEqual(result_to_json(result), wire)
        wire["tables"][0]["rows"][0]["details"]["labels"].clear()
        self.assertEqual(result.tables[0].rows[0]["details"]["labels"], ("synthetic",))
        with self.assertRaises(ValueError):
            replace(provider(), artifact_sha256=None)
        with self.assertRaises(ValueError):
            replace(provider(), source_revision="unknown")
        with self.assertRaises(ValueError):
            replace(result, status="failed")
        failure = FailureInfo("invalid-input", "synthetic failure", "validate", None)
        self.assertEqual(replace(result, status="failed", failure=failure).failure, failure)
        with self.assertRaises(ValueError):
            replace(result, summary={"final_cash": 0})
        with self.assertRaises(ValueError):
            replace(result, tables=result.tables + result.tables)

    def test_direct_constructors_freeze_and_validate(self):
        config = {"nested": {"values": ["0.22"]}}
        policy = PolicyRef("fixed-policy", "1", "state.v1", config)
        config["nested"]["values"].append("bad")
        self.assertEqual(policy.config["nested"]["values"], ("0.22",))
        scenario = ScenarioIdentity("s1", "synthetic", 7, DIGEST, DIGEST, "fixed")
        self.assertEqual(scenario.seed, 7)
        for call in (
            lambda: replace(scenario, seed=True),
            lambda: replace(scenario, forecast_mode="invented"),
            lambda: ArtifactRef("fixture.json", "bad", "application/json"),
            lambda: replace(provider(), dependencies=(("a", "1"), ("a", "2"))),
            lambda: PolicyRef("os.system", "1", "state.v1", {}),
            lambda: PolicyRef("p", "1", "s", {"x": float("inf")}),
        ):
            with self.subTest(call=call), self.assertRaises(ValueError):
                call()


    def test_raw_result_strict_keys_and_nested_nonfinite(self):
        result = ProductResult("completed", DIGEST, provider(), (),
                               {}, None, receipt(), None, None)
        wire = result_to_json(result)
        self.assertEqual(result_to_json(loads_result(json.dumps(wire))), wire)
        for change in (
            lambda r: r["provider"].update(extra="untrusted"),
            lambda r: r["normalization"].update(schema="wrong.v1"),
            lambda r: r.update(summary={"nested": {"x": float("inf")}}),
            lambda r: r.update(summary={"balance": 1}),
        ):
            invalid = copy.deepcopy(wire)
            change(invalid)
            with self.subTest(change=change), self.assertRaises(ValueError):
                parse_result(invalid)
        with self.assertRaises(ValueError):
            loads_result(json.dumps(wire).replace('"summary": {}', '"summary": {"x": 1, "x": 2}'))

    def test_native_information_time_is_not_reinterpreted_as_session_open(self):
        wire = self.wire()
        session = wire["tapes"]["sessions"][0]
        session["orders"][0]["information_ts_ns"] = str(int(session["open_ts_ns"]) + 1)
        parse_manifest(wire)  # Later eligible quotes are a native execution concern.

    def test_calendar_fixture_has_exact_bytes(self):
        wire = self.wire()
        ref = wire["calendar"]
        self.assertEqual(hashlib.sha256((FIXTURE.parent / ref["uri"]).read_bytes()).hexdigest(),
                         ref["sha256"])

    def test_unrecognized_schema_is_only_generic_representation(self):
        wire = self.wire()
        wire["input_schema"] = "future.v1"
        wire["settings"] = {"nested": {"ratio": float("inf")}}
        with self.assertRaises(ValueError):
            parse_manifest(wire)
        wire["settings"] = {}
        wire["tapes"] = {}
        wire["clocks"].update(available_ns="30", decision_ns="1")
        parse_manifest(wire)  # Unknown profile cannot invent causal semantics.


    def test_profile_instrument_bounds_match_native_v2(self):
        for key, value in (("price_precision", 5), ("buy_lot", 1000001)):
            wire = self.wire()
            wire["inline_inputs"]["instruments"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                parse_manifest(wire)

if __name__ == "__main__":
    unittest.main()
