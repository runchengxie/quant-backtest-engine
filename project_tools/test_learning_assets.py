import json
import unittest
from pathlib import Path
from project_tools.export_learning_traces import project_method_trace
from project_tools.validate_learning_assets import validate_trace

ROOT = Path(__file__).resolve().parents[1]


class LearningTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(
            (ROOT / "docs/assets/method/fixtures.json").read_text()
        )

    def test_zero_one_many_named_run_bindings(self):
        for scene, preset, n in [
            ("flow", "roundtrip", 0),
            ("book", "depth", 1),
            ("lots", "grid", 17),
            ("risk", "shared", 3),
            ("risk", "residual", 2),
            ("risk", "actions", 2),
        ]:
            t = project_method_trace(self.fixture, scene, preset)
            self.assertEqual(len(t["bindings"]["calls"]), n)
            validate_trace(t, self.fixture)

    def test_projection_preserves_every_exact_value_and_pointer(self):
        for scene, x in self.fixture["scenes"].items():
            for case in x["scenarios"]:
                validate_trace(
                    project_method_trace(self.fixture, scene, case["id"]), self.fixture
                )

    def test_value_and_table_cells_retain_actual_contributing_calls(self):
        t = project_method_trace(self.fixture, "risk", "shared")
        self.assertEqual(
            t["events"][1]["source_pointers"]["cash"]["run_names"], ["execution"]
        )
        t["events"][1]["source_pointers"]["cash"]["run_names"] = ["allocation"]
        with self.assertRaises(ValueError):
            validate_trace(t, self.fixture)

    def test_unsafe_clocks_nulls_and_unknown_schema_rejected(self):
        for mutation in [
            lambda t: t.update(schema="bad"),
            lambda t: t["events"][0]["clock"].update(value=9007199254740993),
            lambda t: t["bindings"].update(run_sha256="scalar"),
        ]:
            t = project_method_trace(self.fixture, "flow", "roundtrip")
            mutation(t)
            with self.assertRaises(ValueError):
                validate_trace(t, self.fixture)


class LearningSemanticGates(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(
            (ROOT / "docs/assets/method/fixtures.json").read_text()
        )

    def test_all_eight_scenes_and_21_presets(self):
        from project_tools.export_learning_traces import PRESETS

        self.assertEqual(len(PRESETS), 8)
        self.assertEqual(sum(map(len, PRESETS.values())), 21)
        for scene, presets in PRESETS.items():
            self.assertEqual(
                [x["id"] for x in self.fixture["scenes"][scene]["scenarios"]], presets
            )

    def test_same_clock_order_and_comparison_missing_event(self):
        import copy

        trace = project_method_trace(self.fixture, "book", "depth")
        self.assertEqual(trace["events"][1]["clock"], trace["events"][2]["clock"])
        self.assertEqual([e["ordinal"] for e in trace["events"]], list(range(4)))
        f = copy.deepcopy(self.fixture)
        f["scenes"]["paths"]["scenarios"][1]["states"].pop()
        t = project_method_trace(f, "paths", "thin")
        self.assertIsNone(t["comparison"]["points"][-1]["events"]["deep"])

    def test_unit_currency_clock_projection_preserved(self):
        import copy

        f = copy.deepcopy(self.fixture)
        values = [9007199254740992, 9007199254740993]
        for i, v in enumerate(values):
            f["scenes"]["flow"]["scenarios"][0]["states"][i]["clock"] = v
        t = project_method_trace(f, "flow", "roundtrip")
        self.assertEqual(
            [e["clock"]["value"] for e in t["events"][:2]], list(map(str, values))
        )
        self.assertEqual(t["currency"], "USD")
        self.assertEqual(project_method_trace(f, "cost", "once")["currency"], "CNY")
        self.assertEqual(
            project_method_trace(f, "book", "depth")["currency"], "unknown"
        )
        self.assertEqual(
            project_method_trace(f, "risk", "residual")["events"][0]["clock"]["kind"],
            "session_date",
        )
        self.assertEqual(
            project_method_trace(f, "risk", "risk-full")["units"]["variance"],
            "squared basis points over one-day target interval",
        )

    def test_source_classes_do_not_imply_calibration(self):
        t = project_method_trace(self.fixture, "impact", "nondecaying")
        self.assertEqual(t["calibration"], "synthetic_only")
        t["calibration"] = "empirical"
        with self.assertRaises(ValueError):
            validate_trace(t, self.fixture)

    def test_optional_projection_digest_does_not_replace_owner_run_hashes(self):
        t = project_method_trace(self.fixture, "lots", "grid")
        self.assertNotIn("projection_ref", t["bindings"])
        t["bindings"]["run_sha256"] = {"aggregate": "0" * 64}
        with self.assertRaises(ValueError):
            validate_trace(t, self.fixture)

    def test_contributing_call_map_is_specific_for_each_grid_and_composed_result(self):
        t = project_method_trace(self.fixture, "lots", "grid")
        grid = t["tables"][0]
        self.assertEqual(
            grid["value_sources"]["/rows/6/cash"]["run_names"], ["grid-1-2"]
        )
        self.assertEqual(
            grid["value_sources"]["/rows/6/shares"]["run_binding_status"],
            "not_applicable",
        )
        t = project_method_trace(self.fixture, "risk", "residual")
        self.assertEqual(
            t["events"][-1]["source_pointers"]["wealth"]["run_names"],
            ["session", "wealth"],
        )
        self.assertEqual(
            t["events"][0]["source_pointers"]["cash_realized_wealth"][
                "run_binding_status"
            ],
            "unavailable",
        )
        t = project_method_trace(self.fixture, "risk", "actions")
        self.assertEqual(
            t["events"][0]["source_pointers"]["cash"]["run_names"], ["baseline"]
        )
        self.assertEqual(
            t["events"][-1]["source_pointers"]["cash"]["run_names"], ["continuation"]
        )
        self.assertEqual(
            t["events"][-1]["source_pointers"]["capital_flow"]["run_binding_status"],
            "not_applicable",
        )

    def test_schema_positive_and_negative_binding_instances(self):
        import copy
        from jsonschema import Draft202012Validator, ValidationError

        schema = json.loads(
            (ROOT / "docs/assets/learning/schemas/trace.schema.json").read_text()
        )
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for scene, preset in [
            ("flow", "roundtrip"),
            ("book", "depth"),
            ("lots", "grid"),
        ]:
            t = project_method_trace(self.fixture, scene, preset)
            validator.validate(t)
            for value in [None, "aggregate", [], {"call": "invalid"}]:
                bad = copy.deepcopy(t)
                bad["bindings"]["run_sha256"] = value
                with self.assertRaises(ValidationError):
                    validator.validate(bad)
        bad = project_method_trace(self.fixture, "flow", "roundtrip")
        bad["bindings"]["run_bindings_reason_key"] = None
        with self.assertRaises(ValidationError):
            validator.validate(bad)

    def test_source_helper_input_config_mutation(self):
        import copy
        from project_tools.validate_learning_assets import validate_fixture

        validate_fixture(self.fixture, ROOT)
        for change in [
            lambda f: f["owners"]["core"].update(revision="0" * 40),
            lambda f: f["exporter_sources"].update(
                {"project_tools/method_market_cases.py": "0" * 64}
            ),
            lambda f: f["scenes"]["cost"]["scenarios"][0]["inputs"].update(
                extra="changed"
            ),
        ]:
            value = copy.deepcopy(self.fixture)
            change(value)
            with self.assertRaises(ValueError):
                validate_fixture(value, ROOT)

    def test_rejects_stale_provider_and_unknown_type(self):
        from project_tools.method_owner_calls import decode

        for value in [
            {"type": "unknown.v1"},
            {
                "type": "dataclass",
                "class": "quant_platform._portfolio.minute_execution.MinuteExecutionConfig",
                "fields": {},
            },
        ]:
            with self.assertRaises(ValueError):
                decode(value)

    def test_trace_hash_is_served_byte_hash(self):
        import hashlib

        manifest = json.loads((ROOT / "docs/assets/learning/manifest.json").read_text())
        for entry in manifest["traces"]:
            self.assertEqual(
                hashlib.sha256((ROOT / "docs" / entry["url"]).read_bytes()).hexdigest(),
                entry["sha256"],
            )

    def test_preset_grid_has_no_missing_selectable_tuple(self):
        from project_tools.export_learning_traces import PRESETS

        grid = json.loads((ROOT / "docs/assets/learning/preset-grid.json").read_text())
        self.assertEqual(
            [(r["scene_id"], r["preset_id"]) for r in grid["presets"]],
            [(s, p) for s, ps in PRESETS.items() for p in ps],
        )
        self.assertTrue(all(len(row["trace_sha256"]) == 64 for row in grid["presets"]))

    def test_no_private_paths_in_public_artifacts(self):
        for path in (ROOT / "docs/assets/learning").rglob("*.json"):
            text = path.read_text()
            for marker in ["/home/", "/run/media/", "quant-research", "account_id"]:
                self.assertNotIn(marker, text)
