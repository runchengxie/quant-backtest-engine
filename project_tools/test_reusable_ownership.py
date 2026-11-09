"""Behavioral tests for the read-only ownership migration validator."""
import copy
import importlib.util
import json
import subprocess
from pathlib import Path
import tempfile
import unittest


class OwnershipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "docs/migration/reusable-ownership.json"
        self.path.parent.mkdir(parents=True)
        self.row = {
            "symbol": "MinuteSession", "old_module": "quant_platform.backtest.minute_session",
            "new_module": "quant_backtest_core.minute_session", "provider_version": "0.1.0",
            "source_revision": None, "status": "planned", "wave": "M3", "gate": "A",
            "old_urls": [
                {"locale": "en", "url": "https://example.test/guides/minute-execution.en/", "anchors": []},
                {"locale": "zh-CN", "url": "https://example.test/guides/minute-execution/", "anchors": []}],
            "new_urls": [
                {"locale": "en", "url": "https://example.test/backtest/minute-session/", "anchors": []},
                {"locale": "zh-CN", "url": "https://example.test/backtest/minute-session.zh-CN/", "anchors": []}],
            "compatibility_path": "quant_platform.backtest.minute_session.MinuteSession",
            "removal_gate": "two-minors-and-all-consumers",
            "acceptance_test": "python -m unittest core.tests.test_minute_session -v",
            "provider_sources": ["core/src/quant_backtest_core/minute_session.py"]}
        self.data = {"schema": "engine-ownership.v1", "rows": [self.row],
                     "historical_routes": copy.deepcopy(self.row["old_urls"])}

    def check(self):
        spec = importlib.util.find_spec("project_tools.check_reusable_ownership")
        self.assertIsNotNone(spec, "ownership checker is not implemented")
        from project_tools.check_reusable_ownership import check_ownership
        self.path.write_text(json.dumps(self.data))
        before = self.path.read_bytes()
        errors = check_ownership(self.path)
        self.assertEqual(self.path.read_bytes(), before, "checker mutated its input")
        return errors

    def test_missing_locale_or_acceptance_rejects_row(self):
        self.row["new_urls"].pop()
        self.row["acceptance_test"] = ""
        errors = self.check()
        self.assertTrue(any("new_urls missing locale zh-CN" in e for e in errors), errors)
        self.assertTrue(any("acceptance_test must name an executable command" in e for e in errors), errors)

    def test_historical_routes_preserve_declared_language(self):
        self.assertEqual(self.check(), [])
        self.row["old_urls"][1]["locale"] = "en"
        self.assertTrue(any("historical route language changed" in e for e in self.check()))

    def test_planned_future_row_accepts_null_revision(self):
        self.assertEqual(self.check(), [])

    def test_implemented_requires_real_revision_sources_and_docs(self):
        self.row.update(status="implemented", source_revision="0" * 40)
        errors = self.check()
        self.assertTrue(any("source_revision" in e for e in errors), errors)
        self.assertTrue(any("provider source missing" in e for e in errors), errors)
        self.assertTrue(any("destination documentation missing" in e for e in errors), errors)

    def test_consistent_shared_route_passes_but_conflicting_mapping_fails(self):
        other = copy.deepcopy(self.row)
        other["symbol"] = "MinuteExecutionConfig"
        self.data["rows"].append(other)
        self.assertEqual(self.check(), [])
        other["new_urls"][0]["url"] = "https://example.test/conflict/"
        self.assertTrue(any("conflicting route mapping" in e for e in self.check()))

    def test_duplicate_symbol_unknown_wave_gate_and_placeholder_revision_fail(self):
        self.data["rows"].append(copy.deepcopy(self.row))
        self.row.update(wave="M99", gate="unknown", source_revision="TBD")
        errors = self.check()
        for expected in ["duplicate symbol", "unknown wave", "unknown gate", "source_revision"]:
            self.assertTrue(any(expected in e for e in errors), errors)

    def test_malformed_input_returns_errors(self):
        self.data["rows"] = [None]
        self.assertTrue(self.check())

    def test_destination_languages_cannot_share_one_page(self):
        self.row["new_urls"][1]["url"] = self.row["new_urls"][0]["url"]
        self.assertTrue(any("destination locales share one page" in e for e in self.check()))

    def test_malformed_fields_return_errors_without_crashing(self):
        for field in ["wave", "gate", "status", "removal_gate"]:
            with self.subTest(field=field):
                original = self.row[field]
                self.row[field] = []
                try:
                    self.assertTrue(self.check())
                finally:
                    self.row[field] = original

    def test_implemented_accepts_real_committed_sources_and_paired_docs(self):
        (self.root / "core/src/quant_backtest_core").mkdir(parents=True)
        (self.root / self.row["provider_sources"][0]).write_text("class MinuteSession: pass\n")
        for suffix in ["", ".zh-CN"]:
            doc = self.root / f"docs/backtest/minute-session{suffix}.md"
            doc.parent.mkdir(exist_ok=True)
            doc.write_text("# Session\n")
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "core", "docs/backtest"], check=True)
        subprocess.run(["git", "-C", str(self.root), "-c", "user.name=Fixture",
                        "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"], check=True)
        revision = subprocess.check_output(["git", "-C", str(self.root), "rev-parse", "HEAD"], text=True).strip()
        self.row.update(status="implemented", source_revision=revision)
        for route in self.row["new_urls"]:
            route["url"] = route["url"].replace("example.test/", "runchengxie.github.io/quant-backtest-engine/")
        self.assertEqual(self.check(), [])
        (self.root / self.row["provider_sources"][0]).unlink()
        self.assertTrue(any("provider source missing" in e for e in self.check()))

    def test_registry_preserves_audited_historical_languages(self):
        registry = Path(__file__).resolve().parents[1] / "docs/migration/reusable-ownership.json"
        data = json.loads(registry.read_text())
        languages = {route["url"]: route["locale"] for route in data["historical_routes"]}
        base = "https://runchengxie.github.io/quant-platform/"
        for route, locale in [
            ("guides/minute-execution/", "zh-CN"),
            ("guides/minute-execution.en/", "en"),
            ("alpha/concepts/factor-risk-model/", "zh-CN"),
            ("alpha/concepts/factor-risk-model.en-US/", "en"),
        ]:
            self.assertEqual(languages[base + route], locale)

    def test_required_revision_and_historical_route_are_not_omitted(self):
        del self.row["source_revision"]
        self.row["old_urls"] = []
        errors = self.check()
        self.assertTrue(any("source_revision field is required" in e for e in errors), errors)
        self.assertTrue(any("old_urls must name a historical route" in e for e in errors), errors)

    def test_invalid_historical_catalog_returns_errors(self):
        self.data["historical_routes"] = None
        self.assertTrue(self.check())

    def test_repository_registry_passes(self):
        spec = importlib.util.find_spec("project_tools.check_reusable_ownership")
        self.assertIsNotNone(spec, "ownership checker is not implemented")
        from project_tools.check_reusable_ownership import check_ownership
        registry = Path(__file__).resolve().parents[1] / "docs/migration/reusable-ownership.json"
        self.assertTrue(registry.is_file(), "ownership registry is absent")
        self.assertEqual(check_ownership(registry), [])


if __name__ == "__main__":
    unittest.main()
