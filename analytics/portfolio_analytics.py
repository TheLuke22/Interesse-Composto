"""
Portfolio Analytics Module:
- Dividend Calendar & Yield on Cost (YoC) projections.
- Historical Stress Testing / Crisis Simulation (2008 GFC, 2020 COVID, 2022 Rate Hikes, 2000 Tech Crash).
"""
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np


def calculate_dividend_projections(
    holdings: List[Dict[str, Any]],
    current_prices: Dict[str, float],
    dividend_yields: Dict[str, float]
) -> Dict[str, Any]:
    """
    Computes Yield on Cost, annual projected dividend income, and monthly distribution schedule.

    Args:
        holdings: List of dicts with 'ticker', 'shares', 'avg_price'.
        current_prices: Dict mapping ticker to current price ($).
        dividend_yields: Dict mapping ticker to annual dividend yield in percent (e.g. 2.5 for 2.5%).

    Returns:
        Dict with summary metrics, holding-by-holding table, and monthly cash flow breakdown.
    """
    rows = []
    total_cost_basis = 0.0
    total_market_val = 0.0
    total_annual_div = 0.0

    for h in holdings:
        ticker = h.get("ticker", "").upper()
        shares = float(h.get("shares", 0.0))
        avg_price = float(h.get("avg_price", 0.0))
        
        if shares <= 0:
            continue

        cost_basis = shares * avg_price
        curr_price = current_prices.get(ticker, avg_price)
        market_val = shares * curr_price
        div_yield_pct = dividend_yields.get(ticker, 0.0)
        
        # Annual dividend per share
        annual_div_per_share = curr_price * (div_yield_pct / 100.0)
        annual_div_income = shares * annual_div_per_share
        
        # Yield on Cost: (Annual dividend / Purchase cost) * 100
        yield_on_cost = (annual_div_per_share / avg_price * 100.0) if avg_price > 0 else 0.0

        total_cost_basis += cost_basis
        total_market_val += market_val
        total_annual_div += annual_div_income

        rows.append({
            "Ticker": ticker,
            "Shares": shares,
            "Avg Cost ($)": round(avg_price, 2),
            "Current Price ($)": round(curr_price, 2),
            "Market Value ($)": round(market_val, 2),
            "Forward Yield (%)": round(div_yield_pct, 2),
            "Yield on Cost (%)": round(yield_on_cost, 2),
            "Annual Dividend ($)": round(annual_div_income, 2),
            "Monthly Est ($)": round(annual_div_income / 12.0, 2)
        })

    df_divs = pd.DataFrame(rows)
    weighted_forward_yield = (total_annual_div / total_market_val * 100.0) if total_market_val > 0 else 0.0
    weighted_yoc = (total_annual_div / total_cost_basis * 100.0) if total_cost_basis > 0 else 0.0

    # Monthly cashflow calendar simulation (standard quarterly payouts)
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_payouts = {m: 0.0 for m in months}
    
    # Distribute evenly across quarters for simplicity or default schedule
    for r in rows:
        q_payout = r["Annual Dividend ($)"] / 4.0
        # Cycle 1: Mar, Jun, Sep, Dec (typical US corporate cycle)
        for m_idx in [2, 5, 8, 11]:
            monthly_payouts[months[m_idx]] += q_payout

    df_monthly = pd.DataFrame({
        "Month": list(monthly_payouts.keys()),
        "Projected Payout ($)": [round(v, 2) for v in monthly_payouts.values()]
    })

    return {
        "df_holdings": df_divs,
        "df_monthly": df_monthly,
        "total_market_val": total_market_val,
        "total_cost_basis": total_cost_basis,
        "total_annual_dividend": total_annual_div,
        "weighted_forward_yield": weighted_forward_yield,
        "weighted_yoc": weighted_yoc
    }


# Historical Crisis Benchmarks & Sector Drawdown Models
HISTORICAL_SCENARIOS = {
    "2008 Global Financial Crisis": {
        "description": "Subprime mortgage collapse & banking liquidity freeze (Sep 2008 - Mar 2009)",
        "sp500_drawdown": -50.2,
        "sector_multipliers": {
            "Financial Services": 1.45,
            "Real Estate": 1.40,
            "Consumer Cyclical": 1.15,
            "Technology": 0.95,
            "Healthcare": 0.65,
            "Consumer Defensive": 0.55,
            "Utilities": 0.60,
            "Energy": 1.05,
            "Industrials": 1.10
        },
        "default_drawdown": -48.0
    },
    "2020 COVID-19 Flash Crash": {
        "description": "Global pandemic lockdowns & liquidity shock (Feb 2020 - Mar 2020)",
        "sp500_drawdown": -33.9,
        "sector_multipliers": {
            "Energy": 1.60,
            "Consumer Cyclical": 1.20,
            "Financial Services": 1.15,
            "Industrials": 1.10,
            "Real Estate": 1.15,
            "Technology": 0.85,
            "Healthcare": 0.70,
            "Consumer Defensive": 0.60,
            "Utilities": 0.75
        },
        "default_drawdown": -32.0
    },
    "2022 Inflation & Rate Hike Shock": {
        "description": "Rapid Fed monetary tightening & inflation spike (Jan 2022 - Oct 2022)",
        "sp500_drawdown": -24.5,
        "sector_multipliers": {
            "Technology": 1.45,
            "Consumer Cyclical": 1.35,
            "Real Estate": 1.30,
            "Communication Services": 1.50,
            "Financial Services": 0.90,
            "Industrials": 0.75,
            "Healthcare": 0.50,
            "Consumer Defensive": 0.40,
            "Energy": -1.80  # Energy gained +50% during 2022!
        },
        "default_drawdown": -23.0
    },
    "2000 Dot-Com Tech Bubble Burst": {
        "description": "Speculative tech valuation collapse (Mar 2000 - Oct 2002)",
        "sp500_drawdown": -49.1,
        "sector_multipliers": {
            "Technology": 1.70,
            "Communication Services": 1.55,
            "Consumer Cyclical": 1.05,
            "Financial Services": 0.70,
            "Healthcare": 0.45,
            "Consumer Defensive": 0.35,
            "Utilities": 0.50,
            "Energy": 0.40,
            "Industrials": 0.80
        },
        "default_drawdown": -45.0
    }
}


def simulate_portfolio_stress_test(
    holdings_df: pd.DataFrame,
    total_portfolio_value: float
) -> Dict[str, Any]:
    """
    Simulates portfolio loss and resilience across major historical crisis scenarios.

    Args:
        holdings_df: DataFrame with columns ['Ticker', 'Weight (%)', 'Sector', 'Value ($)'].
        total_portfolio_value: Total value in $.

    Returns:
        Dict of results per scenario with estimated drawdown (%), value loss ($), and resilience score.
    """
    if total_portfolio_value <= 0 or holdings_df.empty:
        return {"scenarios": [], "summary": {}}

    scenario_results = []

    for name, scen in HISTORICAL_SCENARIOS.items():
        base_dd = scen["sp500_drawdown"]
        sec_mults = scen["sector_multipliers"]
        
        simulated_loss_dollars = 0.0
        
        for _, row in holdings_df.iterrows():
            sec = str(row.get("Sector", "Unknown"))
            val = float(row.get("Value ($)", 0.0))
            
            mult = sec_mults.get(sec, 1.0)
            asset_dd = max(-95.0, min(100.0, base_dd * mult))
            loss_asset = val * (asset_dd / 100.0)
            simulated_loss_dollars += loss_asset

        portfolio_dd_pct = (simulated_loss_dollars / total_portfolio_value * 100.0) if total_portfolio_value > 0 else 0.0
        post_crisis_value = max(0.0, total_portfolio_value + simulated_loss_dollars)
        relative_resilience = "🟢 Outperformed S&P 500" if portfolio_dd_pct > base_dd else "🔴 Underperformed S&P 500"

        scenario_results.append({
            "Scenario": name,
            "Description": scen["description"],
            "S&P 500 Benchmark Loss": f"{base_dd:.1f}%",
            "Simulated Portfolio Loss (%)": round(portfolio_dd_pct, 1),
            "Estimated Loss ($)": round(abs(simulated_loss_dollars), 2),
            "Post-Crash Portfolio Value ($)": round(post_crisis_value, 2),
            "Relative Resilience": relative_resilience
        })

    return {
        "scenarios": scenario_results,
        "df_results": pd.DataFrame(scenario_results)
    }
