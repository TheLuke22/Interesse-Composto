"""
Compound Interest & Wealth Accumulation UI Component:
Features Scenario Comparison, Inflation Adjustment, Tax Drag, and FIRE retirement milestones.
"""
import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from analytics.compound_interest import calculate_compound_interest, calculate_fire_milestones


def render_compound_interest_ui():
    """
    Renders the upgraded Compound Interest & Financial Independence suite.
    """
    with st.container(key="ci_main_root_container"):
        st.title("💸 Compound Interest & Wealth Accumulation Suite")
        st.markdown(
            "<p style='color: #8A929A; font-size: 16px; margin-bottom:20px;'>"
            "Simulate exponential portfolio growth with recurring contributions (PAC/DCA), "
            "tax drag impact, real inflation-adjusted purchasing power, and FIRE retirement milestones."
            "</p>",
            unsafe_allow_html=True
        )
        st.divider()

        mode = st.radio(
            "Simulation Mode:",
            ["🎯 Standard Planner", "⚖️ Scenario Comparison (A vs B)", "🔥 FIRE Retirement Milestones"],
            horizontal=True,
            key="ci_sim_mode"
        )

        if mode == "🎯 Standard Planner":
            _render_standard_planner()
        elif mode == "⚖️ Scenario Comparison (A vs B)":
            _render_scenario_comparison()
        else:
            _render_fire_calculator()


def _render_standard_planner():
    col1, col2, col3 = st.columns(3)
    with col1:
        initial_cap = st.number_input(
            "Initial Investment ($)", min_value=0.0, value=5000.0, step=500.0, help="Starting lump sum capital", key="ci_init_cap")
        rate = st.number_input(
            "Annual Nominal Return (%)", min_value=0.0, max_value=50.0, value=8.0, step=0.5, help="Expected annual investment return rate", key="ci_nom_rate")
    with col2:
        pac_amount = st.number_input(
            "PAC Contribution ($)", min_value=0.0, value=300.0, step=50.0, help="Amount deposited regularly (PAC / DCA)", key="ci_pac_amt")
        pac_freq = st.selectbox(
            "PAC Frequency",
            ["Monthly", "Quarterly", "Semi-annually", "Annually"],
            index=0,
            key="ci_pac_freq"
        )
    with col3:
        years = int(st.number_input(
            "Investment Horizon (Years)", min_value=1, max_value=50, value=15, step=1, key="ci_years"))
        comp_freq = st.selectbox(
            "Compounding Frequency",
            ["Monthly", "Quarterly", "Semi-annually", "Annually"],
            index=0,
            key="ci_comp_freq"
        )

    with st.expander("⚙️ Advanced Economics: Inflation & Tax Drag", expanded=False):
        ec1, ec2, ec3 = st.columns(3)
        with ec1:
            inflation_rate = st.number_input(
                "Expected Inflation Rate (%)",
                min_value=0.0,
                max_value=20.0,
                value=2.5,
                step=0.25,
                help="Annual inflation rate used to calculate future real purchasing power.",
                key="ci_infl_rate"
            )
        with ec2:
            tax_rate = st.number_input(
                "Capital Gains Tax (%)",
                min_value=0.0,
                max_value=50.0,
                value=26.0,
                step=1.0,
                help="Capital gains tax rate (e.g., 26% Italy, 15%-20% US, 0% ISA/Roth).",
                key="ci_tax_rate"
            )
        with ec3:
            tax_timing = st.selectbox(
                "Tax Regime:",
                ["At Exit (Differita)", "Annual (Annuale)"],
                index=0,
                help="At Exit (tax deferred until redemption) vs Annual (tax paid every year on gains).",
                key="ci_tax_timing"
            )

    # Run Calculation
    res = calculate_compound_interest(
        initial_capital=initial_cap,
        annual_rate=rate,
        years=years,
        pac_amount=pac_amount,
        pac_freq=pac_freq,
        comp_freq=comp_freq,
        inflation_rate=inflation_rate,
        tax_rate=tax_rate,
        tax_timing=tax_timing
    )

    df_results = res["df"]
    final_gross = res["final_gross"]
    final_net = res["final_net"]
    final_invested = res["final_invested"]
    final_interest = res["final_interest"]
    final_real = res["final_real_purchasing_power"]
    final_tax_drag = res["final_tax_drag"]
    roi_gross = res["roi_gross"]
    capital_mult = res["capital_multiplier"]

    st.divider()
    st.markdown("### 📊 Wealth Accumulation Summary")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("💰 Net Total Balance", f"${final_net:,.2f}", f"{capital_mult:.2f}x Capital")
    m2.metric("📥 Total Invested", f"${final_invested:,.2f}")
    m3.metric("📈 Gross Interest Earned", f"${final_interest:,.2f}", f"+{roi_gross:.1f}% ROI")
    m4.metric("🛡️ Real Purchasing Power", f"${final_real:,.2f}", f"-{inflation_rate:.1f}% Infl/yr")
    m5.metric("🏛️ Estimated Tax Drag", f"${final_tax_drag:,.2f}", f"{tax_rate:.0f}% Tax")

    st.write("")
    ch_col1, ch_col2 = st.columns([2, 1])
    with ch_col1:
        st.markdown("#### 📈 Wealth Trajectory: Nominal vs Real vs Capital Invested")
        fig_growth = go.Figure()
        
        fig_growth.add_trace(go.Scatter(
            x=df_results["Year"],
            y=df_results["Total Invested ($)"],
            name="Total Invested",
            mode="lines",
            line=dict(width=2, color="#94a3b8", dash="dot")
        ))
        fig_growth.add_trace(go.Scatter(
            x=df_results["Year"],
            y=df_results["Gross Balance ($)"],
            name="Gross Nominal Balance",
            mode="lines",
            line=dict(width=3, color="#10b981")
        ))
        fig_growth.add_trace(go.Scatter(
            x=df_results["Year"],
            y=df_results["Net Balance ($)"],
            name="Net Balance (After Tax)",
            mode="lines",
            line=dict(width=2.5, color="#3b82f6")
        ))
        fig_growth.add_trace(go.Scatter(
            x=df_results["Year"],
            y=df_results["Real Purchasing Power ($)"],
            name="Real Purchasing Power (Inflation-Adjusted)",
            mode="lines",
            line=dict(width=2, color="#f59e0b", dash="dash")
        ))

        fig_growth.update_layout(
            xaxis_title="Years",
            yaxis_title="Capital Value ($)",
            hovermode="x unified",
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            template="plotly_dark"
        )
        st.plotly_chart(fig_growth, use_container_width=True)

    with ch_col2:
        st.markdown("#### 🍰 Final Wealth Composition")
        labels = ["Principal Invested", "Net Interest (Kept)", "Tax Paid"]
        net_interest_kept = max(0.0, final_net - final_invested)
        values = [final_invested, net_interest_kept, final_tax_drag]
        colors = ["#3b82f6", "#10b981", "#ef4444"]

        fig_donut = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=colors),
            textinfo="percent+label",
            hoverinfo="label+value+percent"
        )])
        fig_donut.update_layout(
            showlegend=False,
            margin=dict(l=10, r=10, t=30, b=10),
            template="plotly_dark"
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    st.divider()
    st.markdown("### 📋 Annual Progression Schedule")

    df_display = df_results.copy()
    for col in [
        "Initial Capital ($)", "PAC Contributions ($)", "Total Invested ($)",
        "Interest Earned ($)", "Gross Balance ($)", "Real Purchasing Power ($)",
        "Estimated Tax Drag ($)", "Net Balance ($)"
    ]:
        df_display[col] = df_display[col].apply(lambda x: f"${x:,.2f}")

    tab_col1, tab_col2 = st.columns([4, 1])
    with tab_col1:
        st.dataframe(df_display, use_container_width=True, hide_index=True)
    with tab_col2:
        csv_data = df_results.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Export CSV",
            data=csv_data,
            file_name=f"compound_interest_{years}y.csv",
            mime="text/csv",
            use_container_width=True
        )


def _render_scenario_comparison():
    st.markdown("#### ⚖️ Compare Two Investment Strategies Side-by-Side")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px;'>"
        "Evaluate lump-sum vs dollar-cost averaging (DCA), conservative vs aggressive returns, or short vs long time horizons."
        "</p>",
        unsafe_allow_html=True
    )

    sc_col1, sc_col2 = st.columns(2)
    with sc_col1:
        st.markdown("##### 🟢 Strategy A (e.g. S&P 500 DCA)")
        init_a = st.number_input("Initial Lump Sum ($)", value=2000.0, step=500.0, key="sc_a_init")
        pac_a = st.number_input("Monthly Contribution ($)", value=400.0, step=50.0, key="sc_a_pac")
        rate_a = st.number_input("Annual Return (%)", value=8.5, step=0.5, key="sc_a_rate")
        years_a = int(st.number_input("Horizon (Years)", value=20, step=1, key="sc_a_yrs"))

    with sc_col2:
        st.markdown("##### 🔵 Strategy B (e.g. Lump Sum Conservative)")
        init_b = st.number_input("Initial Lump Sum ($)", value=25000.0, step=1000.0, key="sc_b_init")
        pac_b = st.number_input("Monthly Contribution ($)", value=100.0, step=50.0, key="sc_b_pac")
        rate_b = st.number_input("Annual Return (%)", value=6.0, step=0.5, key="sc_b_rate")
        years_b = int(st.number_input("Horizon (Years)", value=20, step=1, key="sc_b_yrs"))

    max_years = max(years_a, years_b)
    res_a = calculate_compound_interest(init_a, rate_a, max_years, pac_amount=pac_a)
    res_b = calculate_compound_interest(init_b, rate_b, max_years, pac_amount=pac_b)

    st.write("")
    comp_kpi1, comp_kpi2, comp_kpi3, comp_kpi4 = st.columns(4)
    with comp_kpi1:
        st.metric("Strategy A Final Balance", f"${res_a['final_net']:,.2f}", f"{res_a['capital_multiplier']:.2f}x")
    with comp_kpi2:
        st.metric("Strategy B Final Balance", f"${res_b['final_net']:,.2f}", f"{res_b['capital_multiplier']:.2f}x")
    with comp_kpi3:
        diff_bal = res_a['final_net'] - res_b['final_net']
        winner = "Strategy A" if diff_bal > 0 else "Strategy B"
        st.metric("Delta (A vs B)", f"${diff_bal:+,.2f}", f"Leader: {winner}")
    with comp_kpi4:
        diff_invested = res_a['final_invested'] - res_b['final_invested']
        st.metric("Out-of-Pocket Diff", f"${diff_invested:+,.2f}")

    fig_comp = go.Figure()
    fig_comp.add_trace(go.Scatter(
        x=res_a["df"]["Year"], y=res_a["df"]["Net Balance ($)"],
        name="Strategy A Balance", line=dict(color="#10b981", width=3)
    ))
    fig_comp.add_trace(go.Scatter(
        x=res_b["df"]["Year"], y=res_b["df"]["Net Balance ($)"],
        name="Strategy B Balance", line=dict(color="#3b82f6", width=3)
    ))
    fig_comp.add_trace(go.Scatter(
        x=res_a["df"]["Year"], y=res_a["df"]["Total Invested ($)"],
        name="Strategy A Out-of-Pocket", line=dict(color="#10b981", width=1.5, dash="dot")
    ))
    fig_comp.add_trace(go.Scatter(
        x=res_b["df"]["Year"], y=res_b["df"]["Total Invested ($)"],
        name="Strategy B Out-of-Pocket", line=dict(color="#3b82f6", width=1.5, dash="dot")
    ))

    fig_comp.update_layout(
        xaxis_title="Years",
        yaxis_title="Total Value ($)",
        template="plotly_dark",
        hovermode="x unified",
        margin=dict(l=20, r=20, t=30, b=20)
    )
    st.plotly_chart(fig_comp, use_container_width=True)


def _render_fire_calculator():
    st.markdown("#### 🔥 Financial Independence, Retire Early (FIRE) Planner")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px;'>"
        "Compute your target financial independence number using the Trinity Study 4% Safe Withdrawal Rule (SWR)."
        "</p>",
        unsafe_allow_html=True
    )

    fc1, fc2, fc3, fc4 = st.columns(4)
    with fc1:
        curr_assets = st.number_input("Current Invested Assets ($)", value=25000.0, step=2500.0, key="fire_curr_assets")
    with fc2:
        monthly_exp = st.number_input("Desired Monthly Expenses ($)", value=2500.0, step=250.0, key="fire_monthly_exp")
    with fc3:
        monthly_sav = st.number_input("Monthly Savings / PAC ($)", value=800.0, step=100.0, key="fire_monthly_sav")
    with fc4:
        swr = st.number_input("Safe Withdrawal Rate (%)", value=4.0, step=0.25, help="4.0% standard Trinity rule or 3.5% conservative.", key="fire_swr")

    annual_exp = monthly_exp * 12.0
    annual_sav = monthly_sav * 12.0

    fire_res = calculate_fire_milestones(
        current_portfolio=curr_assets,
        annual_spending=annual_exp,
        annual_savings=annual_sav,
        expected_real_return=5.5,
        swr=swr
    )

    st.write("")
    fk1, fk2, fk3, fk4 = st.columns(4)
    with fk1:
        st.metric("🎯 Full FIRE Target", f"${fire_res['fire_target']:,.0f}", f"At {swr:.1f}% SWR")
    with fk2:
        st.metric("🥪 Lean FIRE (75% budget)", f"${fire_res['lean_fire_target']:,.0f}")
    with fk3:
        st.metric("🏖️ Fat FIRE (125% budget)", f"${fire_res['fat_fire_target']:,.0f}")
    with fk4:
        yrs = fire_res["years_to_fire"]
        yrs_txt = f"{yrs:.1f} Years" if yrs is not None else "Reached!"
        st.metric("⏳ Time to Freedom", yrs_txt, f"{fire_res['progress_pct']:.1f}% Complete")

    st.progress(min(1.0, fire_res["progress_pct"] / 100.0))
