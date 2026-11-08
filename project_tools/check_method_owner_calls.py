"""Optional actual-owner mutation tests for complete serialized run bindings."""

import copy
import os
import sys
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ["METHOD_PLATFORM"]) / "packages/platform/src"))


class OwnerCallBinding(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("method_owner_calls"),
            "serialized owner-call adapter is missing",
        )
        from method_owner_calls import execute_call, decode, encode
        from method_fixture_common import digest

        self.execute, self.decode, self.encode, self.digest = (
            execute_call,
            decode,
            encode,
            digest,
        )
        self.fixtures = json.loads(
            (ROOT / "docs/assets/method/fixtures.json").read_text()
        )

    def definition(self, scene, index, name):
        return copy.deepcopy(
            self.fixtures["scenes"][scene]["scenarios"][index]["inputs"]["runs"][name]
        )

    def change(self, definition, section, field, value):
        arguments = self.decode(definition["arguments"])
        if section == "config":
            from dataclasses import replace

            arguments["config"] = replace(arguments["config"], **{field: value})
        elif section == "bars":
            arguments["bars"].loc[1, field] = value
        elif section == "targets":
            arguments["targets"].loc[0, field] = value
        elif section == "impact_model":
            setattr(arguments["impact_model"], field, value)
        else:
            arguments[field] = value
        changed = copy.deepcopy(definition)
        changed["arguments"] = self.encode(arguments)
        self.assertNotEqual(self.digest(definition), self.digest(changed))
        return changed

    def test_every_resolved_minute_field_and_input_clock_is_bound(self):
        from dataclasses import fields
        from quant_platform.backtest.minute import MinuteExecutionConfig
        import pandas as pd

        run = self.definition("cost", 0, "execution")
        decoded = self.decode(run["arguments"])
        encoded = run["arguments"]["config"]["fields"]
        self.assertEqual(
            set(encoded), {field.name for field in fields(MinuteExecutionConfig)}
        )
        for field in fields(MinuteExecutionConfig):
            value = getattr(decoded["config"], field.name)
            replacement = 0.2 if field.name == "participation_rate" else value + 1
            source = (
                self.change(run, "config", "sell_fee_bp", 1)
                if field.name == "sell_tax_bp"
                else run
            )
            self.change(source, "config", field.name, replacement)
        self.change(
            run, "bars", "time", pd.Timestamp("2026-01-05 09:33", tz="Asia/Shanghai")
        )
        self.change(
            run,
            "targets",
            "decision_time",
            pd.Timestamp("2026-01-05 09:28", tz="Asia/Shanghai"),
        )
        self.change(run, "impact_model", "permanent", 0.004)
        incomplete = copy.deepcopy(run)
        del incomplete["arguments"]["config"]["fields"]["latency_minutes"]
        with self.assertRaisesRegex(ValueError, "resolved dataclass fields"):
            self.execute(incomplete)

    def test_mutated_definition_drives_real_cash_capacity_latency_and_impact(self):
        run = self.definition("cost", 0, "execution")
        original = copy.deepcopy(run)
        baseline = self.execute(run)
        self.assertEqual(run, original)
        self.assertEqual(baseline.daily.iloc[-1].cash, 10989)
        more_cash = self.execute(self.change(run, "config", "initial_cash", 12300))
        self.assertEqual(more_cash.daily.iloc[-1].cash, 11289)
        more_capacity = self.execute(
            self.change(run, "config", "participation_rate", 0.2)
        )
        self.assertEqual(more_capacity.fills.quantity.sum(), 200)
        delayed = self.execute(self.change(run, "config", "latency_minutes", 10))
        self.assertTrue(delayed.fills.empty)
        impacted = self.execute(self.change(run, "impact_model", "permanent", 0.004))
        self.assertEqual(impacted.fills.iloc[0].price, 10.2)

    def test_delay_policy_and_distinct_action_runs_are_bound(self):
        run = self.definition("risk", 0, "session")
        original = self.execute(run)
        original.run()
        changed = self.change(run, "argument", "report_delay_seconds", 0)
        immediate = self.execute(changed)
        immediate.run()
        self.assertNotEqual(original.policy.rows, immediate.policy.rows)
        actions = self.fixtures["scenes"]["risk"]["scenarios"][3]["inputs"]["runs"]
        self.assertEqual(set(actions), {"baseline", "continuation"})
        baseline = self.decode(actions["baseline"]["arguments"])
        continued = self.decode(actions["continuation"]["arguments"])
        self.assertEqual(baseline["report_delay_seconds"], 0)
        self.assertEqual(continued["report_delay_seconds"], 600)
        self.assertFalse(baseline["bars"].equals(continued["bars"]))
        self.assertTrue(
            baseline["bars"].loc[baseline["bars"].time.dt.day == 7, "tradable"].all()
        )
        self.assertFalse(
            continued["bars"].loc[continued["bars"].time.dt.day == 7, "tradable"].any()
        )
        for name in [
            "targets",
            "bars",
            "config",
            "policy",
            "impact",
            "quantity_locks",
            "corporate_actions",
            "valuation_events",
            "capital_flows",
            "report_delay_seconds",
        ]:
            self.assertIn(name, baseline)
            self.assertIn(name, continued)
        copied = copy.deepcopy(actions["baseline"])
        copied["arguments"]["policy"]["state"]["hold"] = True
        self.assertNotEqual(self.digest(copied), self.digest(actions["baseline"]))


if __name__ == "__main__":
    unittest.main()
