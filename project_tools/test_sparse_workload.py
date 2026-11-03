import unittest

from sparse_workload import generate_sparse, validate_run, workload_plan


class SparseWorkloadTests(unittest.TestCase):
    def test_planned_dimensions_and_preallocation_guard(self):
        plan = workload_plan(63, 5577, 20, 241, "orders-and-valuation", 2_000_000)
        self.assertEqual(plan["quote_rows"], 653751)
        self.assertFalse(plan["over_quote_budget"])
        full = workload_plan(63, 5577, 20, 241, "all", 2_000_000)
        self.assertEqual(full["quote_rows"], 84675591)
        self.assertTrue(full["over_quote_budget"])
        with self.assertRaisesRegex(ValueError, "budget"):
            generate_sparse(63, 5577, 20, 241, "all", 2_000_000)

    def test_route_only_removes_idle_intraday_quotes(self):
        full, _ = generate_sparse(4, 7, 2, 4, "all", 1000)
        routed, _ = generate_sparse(4, 7, 2, 4, "orders-and-valuation", 1000)
        self.assertEqual(full["instruments"], routed["instruments"])
        for left, right in zip(full["sessions"], routed["sessions"]):
            self.assertEqual(left["orders"], right["orders"])
            active = {o["symbol"] for o in left["orders"]}
            expected = [q for q in left["quotes"] if q["symbol"] in active
                        or q["ts_ns"] == left["valuation_ts_ns"]]
            self.assertEqual(expected, right["quotes"])
            self.assertEqual(len([q for q in right["quotes"]
                                  if q["ts_ns"] == right["valuation_ts_ns"]]), 7)

    def test_rotation_keeps_next_session_sales_in_same_pair(self):
        request, _ = generate_sparse(4, 9, 2, 3, "orders-and-valuation", 1000)
        groups = [{o["symbol"] for o in s["orders"]} for s in request["sessions"]]
        self.assertEqual(groups[0], groups[1])
        self.assertEqual(groups[2], groups[3])
        self.assertNotEqual(groups[0], groups[2])
        self.assertTrue(all(o["side"] == "buy" for o in request["sessions"][0]["orders"]))
        self.assertTrue(all(o["side"] == "sell" for o in request["sessions"][1]["orders"]))

    def test_invalid_shapes_rejected(self):
        for values in [(0, 4, 2, 3), (2, 4, 5, 3), (2, 4, 2, 1), (2, True, 1, 3)]:
            with self.assertRaises(ValueError):
                workload_plan(*values, "all", 1000)

    def test_operation_regression_rejects_idle_quote_snapshot_growth(self):
        record = {"exit_code": 0, "checks": {"orders": 4, "fills": 4, "rejections": 0},
                  "profile": {"phases": {"strategy_cache_reads": 100}}}
        self.assertFalse(validate_run(record, 4))
        self.assertIn("snapshot", record["validation_error"])


if __name__ == "__main__":
    unittest.main()
