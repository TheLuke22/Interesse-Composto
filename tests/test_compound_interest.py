"""
Unit tests for Compound Interest, Inflation Discounting, Tax Drag, and FIRE calculations.
"""
import unittest
import math
from analytics.compound_interest import calculate_compound_interest, calculate_fire_milestones


class TestCompoundInterest(unittest.TestCase):

    def test_standard_compound_interest_zero_pac(self):
        # $10,000 at 10% annual nominal return compounded monthly for 1 year
        res = calculate_compound_interest(
            initial_capital=10000.0,
            annual_rate=10.0,
            years=1,
            pac_amount=0.0,
            comp_freq="Monthly"
        )
        # Expected monthly compounded value: 10000 * (1 + 0.10/12)^12 = 11047.13
        self.assertAlmostEqual(res["final_gross"], 11047.13, places=1)
        self.assertEqual(res["final_invested"], 10000.0)
        self.assertAlmostEqual(res["roi_gross"], 10.47, places=1)

    def test_pac_contributions(self):
        # $0 initial, $500 monthly PAC at 0% interest for 2 years
        res = calculate_compound_interest(
            initial_capital=0.0,
            annual_rate=0.0,
            years=2,
            pac_amount=500.0,
            pac_freq="Monthly",
            is_beginning=False
        )
        self.assertEqual(res["final_invested"], 12000.0)
        self.assertEqual(res["final_gross"], 12000.0)
        self.assertEqual(res["final_interest"], 0.0)

    def test_tax_drag_at_exit(self):
        # $10,000 initial invested, gain of $5,000 with 26% exit tax
        res = calculate_compound_interest(
            initial_capital=10000.0,
            annual_rate=10.0,
            years=5,
            pac_amount=0.0,
            tax_rate=26.0,
            tax_timing="At Exit (Differita)"
        )
        gross_gain = res["final_gross"] - res["final_invested"]
        expected_tax = gross_gain * 0.26
        self.assertAlmostEqual(res["final_tax_drag"], expected_tax, places=2)
        self.assertAlmostEqual(res["final_net"], res["final_gross"] - expected_tax, places=2)

    def test_inflation_purchasing_power(self):
        res = calculate_compound_interest(
            initial_capital=10000.0,
            annual_rate=8.0,
            years=10,
            inflation_rate=2.5
        )
        self.assertLess(res["final_real_purchasing_power"], res["final_gross"])
        expected_real = res["final_net"] / ((1.0 + 0.025) ** 10)
        self.assertAlmostEqual(res["final_real_purchasing_power"], expected_real, places=1)

    def test_fire_milestone_calculator(self):
        # $30,000 annual spending with 4.0% SWR -> Target: $750,000
        fire = calculate_fire_milestones(
            current_portfolio=150000.0,
            annual_spending=30000.0,
            annual_savings=20000.0,
            expected_real_return=5.0,
            swr=4.0
        )
        self.assertEqual(fire["fire_target"], 750000.0)
        self.assertEqual(fire["lean_fire_target"], 562500.0) # 75%
        self.assertEqual(fire["fat_fire_target"], 937500.0) # 125%
        self.assertEqual(fire["progress_pct"], 20.0)
        self.assertIsNotNone(fire["years_to_fire"])
        self.assertTrue(10.0 < fire["years_to_fire"] < 25.0)


if __name__ == "__main__":
    unittest.main()
