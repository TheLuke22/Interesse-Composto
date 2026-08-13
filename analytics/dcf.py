"""
Discounted Cash Flow (DCF) Valuation Engine.
Includes 5-year explicit projection, terminal value, 5x5 WACC vs Terminal Growth
sensitivity matrix heatmap, and Reverse DCF (implied market growth rate).
"""
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import numpy as np


def calculate_dcf(
    recent_fcf: float,
    shares_outstanding: float,
    current_price: float,
    fcf_growth_rate: float,
    discount_rate: float,
    terminal_growth: float,
    total_debt: float = 0.0,
    total_cash: float = 0.0,
    projection_years: int = 5
) -> Dict[str, Any]:
    """
    Performs institutional 2-stage Discounted Cash Flow valuation.

    Args:
        recent_fcf: Most recent annual Free Cash Flow in $.
        shares_outstanding: Number of shares outstanding.
        current_price: Current market price per share in $.
        fcf_growth_rate: Expected annual FCF growth for years 1-5 (in %, e.g., 8.0 for 8%).
        discount_rate: Weighted Average Cost of Capital / Discount rate (in %, e.g., 9.5 for 9.5%).
        terminal_growth: Long-term perpetual terminal growth rate (in %, e.g., 2.5 for 2.5%).
        total_debt: Total debt on balance sheet ($).
        total_cash: Total cash and cash equivalents ($).
        projection_years: Explicit projection period (default 5 years).

    Returns:
        Dictionary containing enterprise value, equity value, fair value, margin of safety,
        projected cash flows, and error flags.
    """
    g = fcf_growth_rate / 100.0
    wacc = discount_rate / 100.0
    g_term = terminal_growth / 100.0

    if wacc <= g_term:
        return {
            "error": "Discount Rate (WACC) must be strictly greater than Terminal Growth Rate.",
            "is_valid": False
        }

    if shares_outstanding <= 0:
        return {
            "error": "Shares outstanding must be positive.",
            "is_valid": False
        }

    # Year-by-year projected cash flows
    projected_fcf = []
    pv_fcf_list = []
    
    for t in range(1, projection_years + 1):
        fcf_t = recent_fcf * ((1.0 + g) ** t)
        pv_t = fcf_t / ((1.0 + wacc) ** t)
        projected_fcf.append(fcf_t)
        pv_fcf_list.append(pv_t)

    sum_pv_fcf = sum(pv_fcf_list)
    fcf_terminal_base = projected_fcf[-1]
    
    # Gordon Growth Terminal Value
    terminal_value = (fcf_terminal_base * (1.0 + g_term)) / (wacc - g_term)
    pv_terminal_value = terminal_value / ((1.0 + wacc) ** projection_years)

    enterprise_value = sum_pv_fcf + pv_terminal_value
    net_debt = total_debt - total_cash
    equity_value = enterprise_value - net_debt

    raw_fair_value = equity_value / shares_outstanding
    fair_value = max(0.0, raw_fair_value)

    if fair_value > 0:
        margin_of_safety = ((fair_value - current_price) / fair_value) * 100.0
    else:
        margin_of_safety = -100.0

    upside_pct = ((fair_value - current_price) / current_price * 100.0) if current_price > 0 else 0.0

    return {
        "is_valid": True,
        "recent_fcf": recent_fcf,
        "sum_pv_fcf": sum_pv_fcf,
        "terminal_value": terminal_value,
        "pv_terminal_value": pv_terminal_value,
        "enterprise_value": enterprise_value,
        "net_debt": net_debt,
        "equity_value": equity_value,
        "raw_fair_value": raw_fair_value,
        "fair_value": fair_value,
        "current_price": current_price,
        "margin_of_safety": margin_of_safety,
        "upside_pct": upside_pct,
        "projected_fcf": projected_fcf,
        "pv_fcf_list": pv_fcf_list,
        "terminal_value_weight": (pv_terminal_value / enterprise_value * 100.0) if enterprise_value > 0 else 0.0
    }


def generate_dcf_sensitivity_matrix(
    recent_fcf: float,
    shares_outstanding: float,
    current_price: float,
    base_growth: float,
    base_wacc: float,
    base_terminal: float,
    total_debt: float = 0.0,
    total_cash: float = 0.0,
    wacc_steps: Optional[List[float]] = None,
    terminal_steps: Optional[List[float]] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generates a 5x5 Sensitivity Matrix Heatmap varying WACC (rows) and Terminal Growth (columns).

    Returns:
        Tuple of (fair_value_df, upside_pct_df)
    """
    if wacc_steps is None:
        wacc_steps = [
            round(base_wacc - 2.0, 1),
            round(base_wacc - 1.0, 1),
            round(base_wacc, 1),
            round(base_wacc + 1.0, 1),
            round(base_wacc + 2.0, 1)
        ]
    if terminal_steps is None:
        terminal_steps = [1.5, 2.0, 2.5, 3.0, 3.5]

    fv_matrix = []
    upside_matrix = []

    for w in wacc_steps:
        fv_row = []
        up_row = []
        for tg in terminal_steps:
            if w <= tg:
                fv_row.append(np.nan)
                up_row.append(np.nan)
            else:
                res = calculate_dcf(
                    recent_fcf=recent_fcf,
                    shares_outstanding=shares_outstanding,
                    current_price=current_price,
                    fcf_growth_rate=base_growth,
                    discount_rate=w,
                    terminal_growth=tg,
                    total_debt=total_debt,
                    total_cash=total_cash
                )
                if res.get("is_valid"):
                    fv_row.append(round(res["fair_value"], 2))
                    up_row.append(round(res["upside_pct"], 1))
                else:
                    fv_row.append(np.nan)
                    up_row.append(np.nan)
        fv_matrix.append(fv_row)
        upside_matrix.append(up_row)

    col_names = [f"g_term {tg:.1f}%" for tg in terminal_steps]
    row_names = [f"WACC {w:.1f}%" for w in wacc_steps]

    df_fv = pd.DataFrame(fv_matrix, index=row_names, columns=col_names)
    df_upside = pd.DataFrame(upside_matrix, index=row_names, columns=col_names)

    return df_fv, df_upside


def calculate_reverse_dcf(
    recent_fcf: float,
    shares_outstanding: float,
    current_price: float,
    discount_rate: float,
    terminal_growth: float,
    total_debt: float = 0.0,
    total_cash: float = 0.0,
    target_price: Optional[float] = None
) -> Dict[str, Any]:
    """
    Calculates the Reverse DCF: solves for the 5-year FCF growth rate implied by the current market price.

    Args:
        recent_fcf: Most recent annual FCF ($).
        shares_outstanding: Number of shares outstanding.
        current_price: Current market price ($).
        discount_rate: WACC (%).
        terminal_growth: Terminal growth rate (%).
        total_debt: Total debt ($).
        total_cash: Cash ($).
        target_price: Target stock price to solve for (defaults to current_price).

    Returns:
        Dictionary with implied growth rate (%) and assessment.
    """
    target = target_price if target_price is not None else current_price
    
    if target <= 0 or recent_fcf <= 0 or shares_outstanding <= 0:
        return {
            "implied_growth": None,
            "error": "Reverse DCF requires positive market price, positive FCF, and positive share count."
        }

    # Binary search for implied growth rate between -40% and +80%
    low, high = -40.0, 80.0
    implied_g = None

    for _ in range(100):
        mid = (low + high) / 2.0
        res = calculate_dcf(
            recent_fcf=recent_fcf,
            shares_outstanding=shares_outstanding,
            current_price=target,
            fcf_growth_rate=mid,
            discount_rate=discount_rate,
            terminal_growth=terminal_growth,
            total_debt=total_debt,
            total_cash=total_cash
        )
        if not res.get("is_valid"):
            break

        fv = res["fair_value"]
        if abs(fv - target) < 0.01:
            implied_g = mid
            break
        elif fv < target:
            low = mid
        else:
            high = mid
            
    if implied_g is None:
        implied_g = (low + high) / 2.0

    # Valuation context / assessment
    if implied_g > 25.0:
        sentiment = "🚀 Extremely High Expectations (Aggressive growth required to sustain price)"
    elif implied_g > 15.0:
        sentiment = "📈 High Growth Priced In (Expects double-digit compounding)"
    elif implied_g > 5.0:
        sentiment = "⚖️ Moderate / Reasonable Expectations (Market expects steady expansion)"
    elif implied_g >= 0.0:
        sentiment = "🛡️ Low / Conservative Expectations (Value territory)"
    else:
        sentiment = "⚠️ Contraction Priced In (Market expects FCF decline)"

    return {
        "implied_growth": round(implied_g, 2),
        "target_price": target,
        "sentiment": sentiment
    }
