import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ruin  # noqa: E402


class TestRuin(unittest.TestCase):
    def test_kelly_formula(self):
        self.assertAlmostEqual(ruin.kelly(0.6, 1.0), 0.2)
        self.assertAlmostEqual(ruin.kelly(0.5, 1.0), 0.0)
        self.assertAlmostEqual(ruin.kelly(0.45, 1.5), 0.0833333, places=6)

    def test_gamblers_ruin_matches_theory(self):
        # Fair 1:1 bets, fixed floor: P(reach +3000 before -2000) = 2000 / 5000 = 40%
        pnl = ruin.outcomes(0.5, 1.0, 5000, 40000, np.random.default_rng(5)) * 100
        pr, fail = ruin.evaluation(pnl, 3000, 2000, trailing=False)
        self.assertAlmostEqual(pr, 0.40, delta=0.01)
        self.assertAlmostEqual(pr + fail, 1.0, delta=0.001)

    def test_trailing_is_harder_than_fixed(self):
        pnl = ruin.daily_pnl(0.0, 400, 250, 20000, np.random.default_rng(6))
        fixed, _ = ruin.evaluation(pnl, 3000, 2000, trailing=False)
        trail, _ = ruin.evaluation(pnl, 3000, 2000, trailing=True)
        self.assertLess(trail, fixed)

    def test_kelly_maximises_growth(self):
        rows = ruin.kelly_table(0.45, 1.5, 500, 20000, np.random.default_rng(7))
        best = max(rows, key=lambda r: r["growth_per_trade"])
        self.assertEqual(best["mult"], 1.0)

    def test_over_betting_turns_growth_negative(self):
        rows = {r["mult"]: r for r in ruin.kelly_table(0.45, 1.5, 500, 20000, np.random.default_rng(8))}
        self.assertLess(rows[3.0]["growth_per_trade"], 0)


if __name__ == "__main__":
    unittest.main()
