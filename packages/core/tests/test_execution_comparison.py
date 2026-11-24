import unittest

from quant_backtest_core.planning.execution_comparison import compare, fixed_study


class ExecutionComparisonTests(unittest.TestCase):
    def test_fixed_rows_and_shared_constraints(self):
        rows = fixed_study()
        self.assertEqual(len(rows), 32)
        for row in rows:
            self.assertEqual(len(row.fills), 8)
            self.assertTrue(
                all(0 <= q <= cap + 1e-9 for q, cap in zip(row.fills, row.actual_capacity))
            )
            self.assertAlmostEqual(sum(row.fills) + row.residual, 10)
            self.assertEqual(row.completed, abs(row.residual) < 1e-8)
            self.assertGreaterEqual(row.realized_cost, 0)
        incomplete = [r for r in rows if not r.completed]
        self.assertTrue(incomplete)
        rolling = [r for r in rows if r.policy == "rolling" and r.actual_capacity[0] == 0]
        self.assertTrue(all(r.completed for r in rolling))
        failed = compare(0.5, 1, (0, 0, 0, 0, 2, 2, 2, 2))
        self.assertTrue(next(r for r in failed if r.policy == "rolling").failures)
        no_shock = [r for r in rows if r.actual_capacity[0] == 2]
        self.assertTrue(all(r.completed for r in no_shock if r.policy != "immediate"))
        for row in no_shock:
            if row.policy == "rolling":
                once = next(
                    r
                    for r in no_shock
                    if r.policy == "open_loop" and r.eta == row.eta and r.risk == row.risk
                )
                self.assertAlmostEqual(row.realized_cost, once.realized_cost, places=6)

    def test_immediate_is_clipped_once_and_is_not_a_feasible_plan(self):
        row = next(r for r in compare(0.5, 0, (2,) * 8) if r.policy == "immediate")
        self.assertEqual(row.fills, (2, 0, 0, 0, 0, 0, 0, 0))
        self.assertEqual(row.residual, 8)
        self.assertFalse(row.completed)
        self.assertFalse(row.planned_capacity_feasible)
        self.assertIsNone(row.planned_cost)
        outage = next(
            r for r in compare(0.5, 0, (0, 0, 2, 2, 2, 2, 2, 2)) if r.policy == "immediate"
        )
        self.assertEqual(outage.residual, 10)
