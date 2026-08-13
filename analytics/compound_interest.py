"""
Compound Interest & Financial Independence (FIRE) Analytics Engine.
Provides high-precision mathematical models for wealth accumulation,
inflation discounting, tax drag impact, scenario comparisons, and retirement milestones.
"""
from typing import Dict, List, Any, Optional
import math
import pandas as pd


FREQ_MAP = {
    "Monthly": 12,
    "Quarterly": 4,
    "Semi-annually": 2,
    "Annually": 1
}


def calculate_compound_interest(
    initial_capital: float,
    annual_rate: float,
    years: int,
    pac_amount: float = 0.0,
    pac_freq: str = "Monthly",
    comp_freq: str = "Monthly",
    is_beginning: bool = False,
    inflation_rate: float = 0.0,
    tax_rate: float = 0.0,
    tax_timing: str = "At Exit (Differita)"
) -> Dict[str, Any]:
    """
    Computes yearly wealth accumulation schedule with compounding, periodic contributions (PAC),
    optional real-value inflation adjustments, and tax drag simulations.

    Args:
        initial_capital: Initial lump sum invested.
        annual_rate: Expected nominal annual return (in percent, e.g., 7.0 for 7%).
        years: Investment horizon in years.
        pac_amount: Periodic contribution amount.
        pac_freq: Frequency of contributions ('Monthly', 'Quarterly', 'Semi-annually', 'Annually').
        comp_freq: Compounding frequency ('Monthly', 'Quarterly', 'Semi-annually', 'Annually').
        is_beginning: True if contributions are made at the start of period, False for end of period.
        inflation_rate: Annual inflation rate (in percent, e.g., 2.5 for 2.5%).
        tax_rate: Capital gains tax rate (in percent, e.g., 26.0 for 26%).
        tax_timing: 'At Exit (Differita)' or 'Annual (Annuale)'.

    Returns:
        Dictionary containing yearly progression dataframe, summary metrics, and milestone info.
    """
    n_comp = FREQ_MAP.get(comp_freq, 12)
    n_contrib = FREQ_MAP.get(pac_freq, 12)

    r_nominal = annual_rate / 100.0
    tax_dec = tax_rate / 100.0
    infl_dec = inflation_rate / 100.0

    # Effective annual rate after annual tax if applied annually
    if tax_timing == "Annual (Annuale)" and tax_dec > 0:
        r_eff = r_nominal * (1.0 - tax_dec)
    else:
        r_eff = r_nominal

    r_monthly = ((1.0 + r_eff / n_comp) ** (n_comp / 12.0)) - 1.0
    m_contrib = 12 // n_contrib if n_contrib <= 12 else 1

    current_balance = float(initial_capital)
    initial_invested = float(initial_capital)
    pac_accumulated = 0.0

    records: List[Dict[str, Any]] = [{
        "Year": 0,
        "Initial Capital ($)": round(initial_invested, 2),
        "PAC Contributions ($)": 0.0,
        "Total Invested ($)": round(initial_invested, 2),
        "Interest Earned ($)": 0.0,
        "Gross Balance ($)": round(current_balance, 2),
        "Real Purchasing Power ($)": round(current_balance, 2),
        "Estimated Tax Drag ($)": 0.0,
        "Net Balance ($)": round(current_balance, 2)
    }]

    total_months = years * 12
    for m in range(1, total_months + 1):
        # Contribution at beginning of interval
        if is_beginning and ((m - 1) % m_contrib == 0):
            current_balance += pac_amount
            pac_accumulated += pac_amount

        # Accrue monthly interest
        current_balance *= (1.0 + r_monthly)

        # Contribution at end of interval
        if (not is_beginning) and (m % m_contrib == 0):
            current_balance += pac_amount
            pac_accumulated += pac_amount

        # Record at each annual boundary
        if m % 12 == 0:
            y = m // 12
            tot_invested = initial_invested + pac_accumulated
            gross_gain = max(0.0, current_balance - tot_invested)

            if tax_timing == "At Exit (Differita)":
                tax_drag = gross_gain * tax_dec
                net_balance = current_balance - tax_drag
            else:
                # Taxes already deducted from rate annually
                tax_drag = 0.0
                net_balance = current_balance

            # Inflation adjustment for real purchasing power (Fisher equation)
            inflation_factor = (1.0 + infl_dec) ** y
            real_purchasing_power = net_balance / inflation_factor if inflation_factor > 0 else net_balance

            records.append({
                "Year": y,
                "Initial Capital ($)": round(initial_invested, 2),
                "PAC Contributions ($)": round(pac_accumulated, 2),
                "Total Invested ($)": round(tot_invested, 2),
                "Interest Earned ($)": round(gross_gain, 2),
                "Gross Balance ($)": round(current_balance, 2),
                "Real Purchasing Power ($)": round(real_purchasing_power, 2),
                "Estimated Tax Drag ($)": round(tax_drag, 2),
                "Net Balance ($)": round(net_balance, 2)
            })

    df_results = pd.DataFrame(records)
    final_row = df_results.iloc[-1]

    final_gross = final_row["Gross Balance ($)"]
    final_net = final_row["Net Balance ($)"]
    final_invested = final_row["Total Invested ($)"]
    final_interest = final_row["Interest Earned ($)"]
    final_real = final_row["Real Purchasing Power ($)"]
    final_tax_drag = final_row["Estimated Tax Drag ($)"]

    roi_gross = ((final_gross - final_invested) / final_invested * 100.0) if final_invested > 0 else 0.0
    roi_net = ((final_net - final_invested) / final_invested * 100.0) if final_invested > 0 else 0.0

    return {
        "df": df_results,
        "final_gross": final_gross,
        "final_net": final_net,
        "final_invested": final_invested,
        "final_pac": pac_accumulated,
        "final_interest": final_interest,
        "final_real_purchasing_power": final_real,
        "final_tax_drag": final_tax_drag,
        "roi_gross": roi_gross,
        "roi_net": roi_net,
        "capital_multiplier": (final_net / final_invested) if final_invested > 0 else 1.0
    }


def calculate_fire_milestones(
    current_portfolio: float,
    annual_spending: float,
    annual_savings: float,
    expected_real_return: float = 5.0,
    swr: float = 4.0
) -> Dict[str, Any]:
    """
    Calculates Financial Independence, Retire Early (FIRE) metrics based on Safe Withdrawal Rate (SWR).

    Args:
        current_portfolio: Current total assets invested ($).
        annual_spending: Desired annual retirement expenses in today's dollars ($).
        annual_savings: Total annual additions to the portfolio ($).
        expected_real_return: Expected net real return after inflation and taxes (%).
        swr: Safe Withdrawal Rate (typically 4.0% - Trinity Study, or 3.5% conservative).

    Returns:
        Dictionary with FIRE target number, years to reach FIRE, and milestones.
    """
    swr_dec = swr / 100.0
    fire_target = annual_spending / swr_dec if swr_dec > 0 else 0.0
    
    lean_fire_target = (annual_spending * 0.75) / swr_dec if swr_dec > 0 else 0.0
    fat_fire_target = (annual_spending * 1.25) / swr_dec if swr_dec > 0 else 0.0

    r = expected_real_return / 100.0
    
    years_to_fire: Optional[float] = None
    if current_portfolio >= fire_target:
        years_to_fire = 0.0
    elif r > 0 and (annual_savings > 0 or current_portfolio > 0):
        balance = current_portfolio
        max_years = 100
        for m in range(1, max_years * 12 + 1):
            balance += (annual_savings / 12.0)
            balance *= (1.0 + r / 12.0)
            if balance >= fire_target:
                years_to_fire = round(m / 12.0, 1)
                break

    progress_pct = min(100.0, (current_portfolio / fire_target * 100.0)) if fire_target > 0 else 100.0

    return {
        "fire_target": fire_target,
        "lean_fire_target": lean_fire_target,
        "fat_fire_target": fat_fire_target,
        "years_to_fire": years_to_fire,
        "progress_pct": progress_pct,
        "monthly_safe_income": (fire_target * swr_dec) / 12.0
    }
