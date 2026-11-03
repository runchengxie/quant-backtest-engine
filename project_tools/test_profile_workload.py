import unittest
from pathlib import Path
from unittest.mock import patch
from profile_workload import canonical, generate, check, invoke


class WorkloadTests(unittest.TestCase):
    def test_deterministic_dimensions_and_invalid_sizes(self):
        first = generate(2, 3, 4)
        self.assertEqual(canonical(first), canonical(generate(2, 3, 4)))
        self.assertEqual(sum(len(s['quotes']) for s in first[0]['sessions']), 24)
        self.assertEqual(sum(len(s['orders']) for s in first[0]['sessions']), 6)
        for dimensions in [(0, 3, 4), (2, 0, 4), (2, 3, 1)]:
            with self.assertRaises(ValueError):
                generate(*dimensions)

    def test_successful_child_with_invalid_json_retains_failure_record(self):
        class Child:
            pid = 0
            returncode = 0
            def poll(self):
                return 0
            def wait(self):
                return 0
        with patch("profile_workload.subprocess.Popen", return_value=Child()):
            record = invoke(Path("unused"), Path("request"), Path("sizing"), 1)
        self.assertEqual(record["exit_code"], 0)
        self.assertIn("validation_error", record)

    def test_memory_guard_preserves_actual_killed_exit(self):
        class Child:
            pid = 123
            returncode = None
            def poll(self):
                return self.returncode
            def kill(self):
                self.returncode = -9
            def wait(self):
                return self.returncode
        with patch("profile_workload.subprocess.Popen", return_value=Child()), patch("profile_workload.Path.read_text", return_value="VmRSS: 200 kB\n"):
            record = invoke(Path("unused"), Path("request"), Path("sizing"), 1, 100)
        self.assertEqual(record["exit_code"], -9)
        self.assertTrue(record["memory_stopped"])
        self.assertFalse(record["timeout"])

    def test_accounting_corruption_is_rejected(self):
        with self.assertRaises(AssertionError):
            check({'daily_ledger': [{'cash': '10', 'positions_value': '2', 'nav': '13'}]})


if __name__ == '__main__':
    unittest.main()
