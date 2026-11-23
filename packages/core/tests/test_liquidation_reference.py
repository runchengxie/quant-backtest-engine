"""Independent checks of the continuous liquidation benchmark."""

import math
import unittest

from quant_backtest_core.planning.liquidation_reference import LiquidationModel, evaluate


class LiquidationReferenceTests(unittest.TestCase):
    def test_zero_risk_is_hand_computed_twap(self):
        model = LiquidationModel(100.0, 10.0, 2.0, 0.0, 3.0)
        point = evaluate(model, 4.0)
        self.assertEqual((point.inventory, point.sell_rate, point.remaining_value), (60, 10, 1200))
        self.assertEqual(evaluate(model, 10).remaining_value, 0)

    def test_positive_risk_frontloads_and_finishes(self):
        model = LiquidationModel(100, 10, 2, 0.5, 2)
        points = [evaluate(model, t) for t in (0, 2, 5, 9, 10)]
        self.assertEqual(points[0].inventory, 100)
        self.assertEqual(points[-1].inventory, 0)
        self.assertGreater(points[0].sell_rate, 10)
        self.assertTrue(all(a.inventory > b.inventory for a, b in zip(points, points[1:])))
        self.assertTrue(all(p.sell_rate >= 0 for p in points))

    def test_cost_integral_and_hjb_independent_finite_differences(self):
        model = LiquidationModel(3, 2, 1.5, 0.7, 0.8)
        n = 20000
        dt = model.horizon_seconds / n
        cost = 0.0
        for i in range(n):
            p = evaluate(model, (i + 0.5) * dt)
            cost += (1.5 * p.sell_rate**2 + 0.7 * 0.8**2 * p.inventory**2) * dt
        self.assertAlmostEqual(cost, evaluate(model, 0).remaining_value, places=7)
        # Along the optimal path, dV/dt equals minus the running cost.
        t, h = 0.7, 1e-5
        p = evaluate(model, t)
        derivative = (
            evaluate(model, t + h).remaining_value - evaluate(model, t - h).remaining_value
        ) / (2 * h)
        self.assertAlmostEqual(
            derivative + 1.5 * p.sell_rate**2 + 0.7 * 0.8**2 * p.inventory**2, 0, places=7
        )

    def test_small_and_large_dimensionless_risk(self):
        tiny = evaluate(LiquidationModel(10, 2, 1, 1e-300, 1), 1)
        self.assertAlmostEqual(tiny.inventory, 5)
        large = evaluate(LiquidationModel(10, 1000, 1, 1, 1), 1)
        self.assertAlmostEqual(large.inventory, 10 / math.e, places=12)
        self.assertTrue(math.isfinite(large.remaining_value))
        zero = evaluate(LiquidationModel(0, 10, 1, 1, 1), 10)
        self.assertEqual((zero.inventory, zero.sell_rate, zero.remaining_value), (0, 0, 0))

    def test_reject_positive_risk_coefficient_underflow(self):
        # Multiplying sqrt(risk)*sigma first loses a material kappa*T=1.
        with self.assertRaises(ValueError):
            evaluate(LiquidationModel(1e150, 1e200, 1e-300, 1e-300, 1e-200), 5e199)
        with self.assertRaises(ValueError):
            evaluate(LiquidationModel(1, 1e170, 1e-300, 1e-300, 1e-170), 0)

    def test_reject_initial_scale_underflow(self):
        with self.assertRaises(ValueError):
            evaluate(LiquidationModel(1e-200, 1e200, 1e308, 0, 1), 0)
        with self.assertRaises(ValueError):
            evaluate(LiquidationModel(1e-200, 1e200, 1e300, 1e-40, 1), 0)
        with self.assertRaises(ValueError):
            evaluate(LiquidationModel(1e-100, 1, 1e-300, 1e100, 1), 0)
        with self.assertRaises(ValueError):
            evaluate(LiquidationModel(1e-150, 1e150, 1e-150, 0, 1), 0)

    def test_reject_invalid_and_unrepresentable_domains(self):
        for args in (
            (1, 0, 1, 0, 1),
            (-1, 1, 1, 0, 1),
            (1, 1, 0, 0, 1),
            (1, 1, 1, -1, 1),
            (1, 1, 1, 1, -1),
            (1, math.inf, 1, 1, 1),
            (1e308, 1, 1e308, 0, 1),
            (1, 1, 1, 1e308, 1e308),
        ):
            with self.subTest(args=args), self.assertRaises(ValueError):
                evaluate(LiquidationModel(*args), 0)
        for t in (-1, 11, math.nan):
            with self.assertRaises(ValueError):
                evaluate(LiquidationModel(1, 10, 1, 0, 1), t)


if __name__ == "__main__":
    unittest.main()
