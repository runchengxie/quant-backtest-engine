import unittest
from profile_workload import canonical, generate, check


class WorkloadTests(unittest.TestCase):
    def test_deterministic_dimensions_and_invalid_sizes(self):
        first = generate(2, 3, 4)
        self.assertEqual(canonical(first), canonical(generate(2, 3, 4)))
        self.assertEqual(sum(len(s['quotes']) for s in first[0]['sessions']), 24)
        self.assertEqual(sum(len(s['orders']) for s in first[0]['sessions']), 6)
        for dimensions in [(0, 3, 4), (2, 0, 4), (2, 3, 1)]:
            with self.assertRaises(ValueError):
                generate(*dimensions)

    def test_accounting_corruption_is_rejected(self):
        with self.assertRaises(AssertionError):
            check({'daily_ledger': [{'cash': '10', 'positions_value': '2', 'nav': '13'}]})


if __name__ == '__main__':
    unittest.main()
