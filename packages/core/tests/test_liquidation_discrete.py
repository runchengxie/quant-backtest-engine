import unittest

from quant_backtest_core.planning.liquidation_discrete import objective, solve
from quant_backtest_core.planning.liquidation_reference import LiquidationModel, evaluate


class DiscreteLiquidationTests(unittest.TestCase):
    def test_hand_cost_and_capacity(self):
        model = LiquidationModel(2, 2, 3, 1, 1)
        self.assertAlmostEqual(objective(model, [1, 1]), 6 + 8 / 3)
        plan = solve(model, [1, 1])
        self.assertEqual(plan.sales, (1, 1))

    def test_convergence_and_stationarity(self):
        for risk in (0, 0.7):
            model = LiquidationModel(3, 2, 1.5, risk, 0.8)
            previous = float("inf")
            for n in (8, 16, 32, 64):
                plan = solve(model, [3] * n)
                error = plan.cost - evaluate(model, 0).remaining_value
                self.assertGreaterEqual(error, -1e-8)
                self.assertLessEqual(error, previous + 1e-8)
                previous = error
                self.assertLess(
                    max(
                        abs(x - evaluate(model, i * 2 / n).inventory)
                        for i, x in enumerate(plan.inventory)
                    ),
                    0.02,
                )
                for j in (0, n // 2):
                    a, b = list(plan.sales), list(plan.sales)
                    a[j] += 1e-5
                    a[-1] -= 1e-5
                    b[j] -= 1e-5
                    b[-1] += 1e-5
                    self.assertAlmostEqual(
                        (objective(model, a) - objective(model, b)) / 2e-5, 0, places=5
                    )
            self.assertLess(previous, 0.001)

    def test_rejections_and_zero(self):
        model = LiquidationModel(3, 2, 1, 0, 1)
        for caps in ([], [1, 1], [float("nan"), 4], [-1, 4], [[4]]):
            with self.assertRaises(ValueError):
                solve(model, caps)
        self.assertEqual(solve(LiquidationModel(0, 2, 1, 0, 1), [0, 0]).cost, 0)
        with self.assertRaises(ValueError):
            objective(model, [1, 1])

    def test_invalid_models_and_unrepresentable_quadratic(self):
        for model in (
            LiquidationModel(True, 2, 1, 0, 1),
            LiquidationModel(1, 2, float("nan"), 0, 1),
            LiquidationModel(1e150, 1e-150, 1e150, 0, 1),
        ):
            with self.assertRaises(ValueError):
                solve(model, [1e150])

    def test_single_period_zero_risk(self):
        plan = solve(LiquidationModel(3, 2, 1.5, 0, 0.8), [3])
        self.assertEqual(plan.sales, (3,))
        self.assertEqual(plan.cost, 6.75)
