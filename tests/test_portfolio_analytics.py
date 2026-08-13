"""
Unit tests for Dividend Income Calendar, Yield on Cost (YoC), and Historical Crisis Stress Testing.
"""
import unittest
import pandas as pd
from analytics.portfolio_analytics import calculate_dividend_projections, simulate_portfolio_stress_test


class TestPortfolioAnalytics(unittest.TestCase):

    def test_dividend_projections(self):
        holdings = [
            {"ticker": "AAPL", "shares": 10, "avg_price": 150.0},
            {"ticker": "MSFT", "shares": 5, "avg_price": 300.0}
        ]
        prices = {"AAPL": 200.0, "MSFT": 400.0}
        yields = {"AAPL": 0.5, "MSFT": 1.0} # Yields in %

        res = calculate_dividend_projections(holdings, prices, yields)
        
        self.assertEqual(res["total_market_val"], 4000.0)
        self.assertEqual(res["total_cost_basis"], 3000.0)
        self.assertEqual(res["total_annual_dividend"], 30.0)
        self.assertAlmostEqual(res["weighted_forward_yield"], 0.75, places=2)
        self.assertAlmostEqual(res["weighted_yoc"], 1.00, places=2)
        self.assertEqual(len(res["df_monthly"]), 12)

    def test_stress_test_simulation(self):
        df_holdings = pd.DataFrame({
            "Ticker": ["AAPL", "JNJ", "XOM"],
            "Value ($)": [50000.0, 30000.0, 20000.0],
            "Sector": ["Technology", "Healthcare", "Energy"]
        })
        total_val = 100000.0

        res = simulate_portfolio_stress_test(df_holdings, total_val)
        scenarios = res.get("scenarios", [])
        
        self.assertEqual(len(scenarios), 4)
        for sc in scenarios:
            self.assertLessEqual(sc["Simulated Portfolio Loss (%)"], 0)
            self.assertLessEqual(sc["Post-Crash Portfolio Value ($)"], total_val)


if __name__ == "__main__":
    unittest.main()
