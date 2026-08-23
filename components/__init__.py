"""
UI components package for Streamlit rendering, charts, sensitivity tables, and glassmorphism cards.
"""

from components.dcf_ui import render_dcf_valuation_ui
from components.portfolio_ui import (
    render_portfolio_dividend_suite,
    render_portfolio_stress_test_suite,
    render_my_portfolio_ui
)
from components.compound_ui import render_compound_interest_ui
from components.consensus_pe_ui import render_consensus_pe_section
from components.home_ui import render_home_ui
from components.macro_ui import render_macro_market_ui
from components.news_ui import render_financial_news_ui
from components.screener_ui import render_stock_screener_ui
from components.superinvestors_ui import render_superinvestors_ui, render_buffett_scorecard_ui
from components.segments_ui import render_business_segments_ui
from components.stock_tracker_ui import render_stock_tracker_ui
from components.ui_utils import (
    render_custom_metric,
    render_premium_portfolio_table,
    render_premium_screener_table,
    format_large_numbers,
    format_perc,
    calc_cagr,
    calc_risk_metrics,
    get_sentiment,
    WALL_STREET_QUOTES
)

__all__ = [
    "render_dcf_valuation_ui",
    "render_portfolio_dividend_suite",
    "render_portfolio_stress_test_suite",
    "render_my_portfolio_ui",
    "render_compound_interest_ui",
    "render_consensus_pe_section",
    "render_home_ui",
    "render_macro_market_ui",
    "render_financial_news_ui",
    "render_stock_screener_ui",
    "render_superinvestors_ui",
    "render_buffett_scorecard_ui",
    "render_business_segments_ui",
    "render_stock_tracker_ui",
    "render_custom_metric",
    "render_premium_portfolio_table",
    "render_premium_screener_table",
    "format_large_numbers",
    "format_perc",
    "calc_cagr",
    "calc_risk_metrics",
    "get_sentiment",
    "WALL_STREET_QUOTES",
]
