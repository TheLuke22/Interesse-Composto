"""
Unit tests for DCF Valuation, Sensitivity Matrix, and Reverse DCF.
"""
import unittest
import numpy as np
import pandas as pd
from analytics.dcf import calculate_dcf, generate_dcf_sensitivity_matrix, calculate_reverse_dcf


class TestDCFAnalytics(unittest.TestCase):

    def test_dcf_basic_calculation(self):
        res = calculate_dcf(
            recent_fcf=1000000000.0, # $1B
            shares_outstanding=100000000.0, # 100M shares
            current_price=150.0,
            fcf_growth_rate=10.0, # 10%
            discount_rate=9.0, # 9% WACC
            terminal_growth=2.5, # 2.5%
            total_debt=2000000000.0, # $2B debt
            total_cash=1000000000.0 # $1B cash
        )
        self.assertTrue(res["is_valid"])
        self.assertGreater(res["enterprise_value"], 0)
        self.assertAlmostEqual(res["equity_value"], res["enterprise_value"] - (2e9 - 1e9), places=2)
        self.assertGreater(res["fair_value"], 0)
        self.assertIsNotNone(res["margin_of_safety"])

    def test_dcf_invalid_wacc_terminal_constraint(self):
        res = calculate_dcf(
            recent_fcf=1e9,
            shares_outstanding=1e8,
            current_price=100.0,
            fcf_growth_rate=5.0,
            discount_rate=2.5,
            terminal_growth=3.0 # Invalid: 2.5 <= 3.0
        )
        self.assertFalse(res["is_valid"])
        self.assertIn("strictly greater", res["error"])

    def test_dcf_sensitivity_matrix(self):
        df_fv, df_upside = generate_dcf_sensitivity_matrix(
            recent_fcf=1e9,
            shares_outstanding=1e8,
            current_price=100.0,
            base_growth=8.0,
            base_wacc=9.5,
            base_terminal=2.5
        )
        self.assertEqual(df_fv.shape, (5, 5))
        self.assertEqual(df_upside.shape, (5, 5))
        # Higher WACC (moving down rows) must yield lower Fair Value
        for c in df_fv.columns:
            valid_vals = df_fv[c].dropna().values
            if len(valid_vals) > 1:
                for i in range(len(valid_vals) - 1):
                    self.assertGreaterEqual(valid_vals[i], valid_vals[i+1])

    def test_reverse_dcf_implied_growth(self):
        base_res = calculate_dcf(
            recent_fcf=1e9,
            shares_outstanding=1e8,
            current_price=100.0,
            fcf_growth_rate=10.0,
            discount_rate=9.0,
            terminal_growth=2.5
        )
        target_price = base_res["fair_value"]
        
        rev = calculate_reverse_dcf(
            recent_fcf=1e9,
            shares_outstanding=1e8,
            current_price=target_price,
            discount_rate=9.0,
            terminal_growth=2.5,
            target_price=target_price
        )
        self.assertAlmostEqual(rev["implied_growth"], 10.0, delta=0.5)


if __name__ == "__main__":
    unittest.main()
