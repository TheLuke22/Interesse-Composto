"""
Portfolio Intelligence UI Component:
Renders Projected Dividend Calendar, Yield on Cost (YoC), and Historical Stress Testing Simulations.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from analytics.portfolio_analytics import calculate_dividend_projections, simulate_portfolio_stress_test


def render_portfolio_dividend_suite(holdings: list, current_prices: dict, dividend_yields: dict):
    """
    Renders the Dividend Calendar and Yield on Cost breakdown.
    """
    st.subheader("❄️ Dividend Income Calendar & Yield on Cost (YoC)")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px; margin-bottom: 20px;'>"
        "Track forward dividend cash flow and compare current yields against your purchase cost basis."
        "</p>",
        unsafe_allow_html=True
    )

    div_res = calculate_dividend_projections(holdings, current_prices, dividend_yields)
    
    if div_res["total_market_val"] <= 0 or div_res["df_holdings"].empty:
        st.info("No active holdings found in your portfolio.")
        return

    # KPI Metrics
    dk1, dk2, dk3, dk4 = st.columns(4)
    with dk1:
        st.metric("💵 Projected Annual Dividends", f"${div_res['total_annual_dividend']:,.2f}")
    with dk2:
        st.metric("🗓️ Monthly Average Cash Flow", f"${div_res['total_annual_dividend']/12.0:,.2f}")
    with dk3:
        st.metric("📈 Portfolio Forward Yield", f"{div_res['weighted_forward_yield']:.2f}%")
    with dk4:
        st.metric("🎯 Portfolio Yield on Cost", f"{div_res['weighted_yoc']:.2f}%", 
                  delta=f"{div_res['weighted_yoc'] - div_res['weighted_forward_yield']:+.2f}% vs Market",
                  delta_color="normal")

    st.write("")
    div_c1, div_c2 = st.columns([1, 2])
    with div_c1:
        st.markdown("##### 📅 Estimated Monthly Cashflow Distribution")
        df_m = div_res["df_monthly"]
        fig_bar = go.Figure(data=[go.Bar(
            x=df_m["Month"],
            y=df_m["Projected Payout ($)"],
            marker_color="#00f2fe",
            text=[f"${v:,.0f}" if v > 0 else "" for v in df_m["Projected Payout ($)"]],
            textposition="outside"
        )])
        fig_bar.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title="Payout ($)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with div_c2:
        st.markdown("##### 📋 Holdings Dividend Breakdown & YoC")
        st.dataframe(div_res["df_holdings"], use_container_width=True, hide_index=True)


def render_portfolio_stress_test_suite(holdings_df: pd.DataFrame, total_portfolio_value: float):
    """
    Renders the Historical Crisis Simulation & Macro Stress Test.
    """
    st.subheader("⚡ Historical Crisis & Macro Stress Testing")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px; margin-bottom: 20px;'>"
        "Simulate how your current portfolio allocation would have performed during major historical market crashes."
        "</p>",
        unsafe_allow_html=True
    )

    stress_res = simulate_portfolio_stress_test(holdings_df, total_portfolio_value)
    scenarios = stress_res.get("scenarios", [])

    if not scenarios:
        st.info("Add holdings to your portfolio to run stress test simulations.")
        return

    # Render each scenario in visually distinct cards
    cols = st.columns(2)
    for idx, sc in enumerate(scenarios):
        col = cols[idx % 2]
        with col:
            loss_pct = sc["Simulated Portfolio Loss (%)"]
            loss_dollars = sc["Estimated Loss ($)"]
            post_val = sc["Post-Crash Portfolio Value ($)"]
            resilience = sc["Relative Resilience"]
            bench_loss = sc["S&P 500 Benchmark Loss"]

            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 18px; margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h4 style="margin: 0; color: #FFFFFF; font-size: 16px;">{sc['Scenario']}</h4>
                    <span style="font-size: 12px; font-weight: 700; color: #94a3b8;">Benchmark: {bench_loss}</span>
                </div>
                <p style="color: #94a3b8; font-size: 12px; margin-bottom: 12px;">{sc['Description']}</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; text-align: center;">
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 8px; padding: 8px;">
                        <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase;">Simulated Loss</div>
                        <div style="color: #ef4444; font-size: 16px; font-weight: 800;">{loss_pct:+.1f}%</div>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 8px;">
                        <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase;">Est. Dollar Loss</div>
                        <div style="color: #f87171; font-size: 16px; font-weight: 800;">-${loss_dollars:,.0f}</div>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 8px;">
                        <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase;">Post-Crash Value</div>
                        <div style="color: #00f2fe; font-size: 16px; font-weight: 800;">${post_val:,.0f}</div>
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: #10b981;">{resilience}</div>
            </div>
            """, unsafe_allow_html=True)
