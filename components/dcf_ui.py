"""
DCF Valuation UI Component:
Renders interactive 2-stage DCF, 5x5 Sensitivity Matrix Heatmap, and Reverse DCF Implied Growth rate.
"""
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from analytics.dcf import calculate_dcf, generate_dcf_sensitivity_matrix, calculate_reverse_dcf


def render_dcf_valuation_ui(
    ticker: str,
    recent_fcf: float,
    shares_outstanding: float,
    current_price: float,
    total_debt: float = 0.0,
    total_cash: float = 0.0
):
    """
    Renders institutional DCF valuation tab with Sensitivity Matrix and Reverse DCF.
    """
    st.subheader(f"🧮 Valuation Model: 2-Stage Discounted Cash Flow ({ticker})")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px; margin-bottom: 20px;'>"
        "Intrinsic value calculation based on projected Free Cash Flow (FCF), "
        "Weighted Average Cost of Capital (WACC), and perpetual Terminal Value."
        "</p>",
        unsafe_allow_html=True
    )

    if not recent_fcf or shares_outstanding <= 0:
        st.warning(f"⚠️ Free Cash Flow or Share Count data is not available for {ticker} to compute DCF.")
        return

    if recent_fcf < 0:
        st.warning(
            f"⚠️ **Negative Free Cash Flow Warning**: {ticker} generated negative FCF (${recent_fcf/1e6:,.1f}M) "
            "in the most recent fiscal year. DCF valuation results will reflect structural cash burn unless positive growth is assumed."
        )

    # Valuation Assumption Sliders
    c1, c2, c3 = st.columns(3)
    with c1:
        growth_rate = st.number_input(
            "FCF Growth Rate (Y1-Y5) %",
            min_value=-20.0,
            max_value=100.0,
            value=8.0,
            step=0.5,
            help="Expected compound annual growth rate of Free Cash Flow over the next 5 years.",
            key=f"dcf_growth_{ticker}"
        )
    with c2:
        wacc = st.number_input(
            "Discount Rate / WACC %",
            min_value=1.0,
            max_value=30.0,
            value=9.5,
            step=0.25,
            help="Weighted Average Cost of Capital: required hurdle rate of return.",
            key=f"dcf_wacc_{ticker}"
        )
    with c3:
        terminal_growth = st.number_input(
            "Terminal Growth Rate %",
            min_value=0.5,
            max_value=6.0,
            value=2.5,
            step=0.25,
            help="Perpetual growth rate after Year 5 (typically aligns with long-term GDP growth: 2.0% - 3.0%).",
            key=f"dcf_term_{ticker}"
        )

    if wacc <= terminal_growth:
        st.error("⚠️ Mathematical Error: Discount Rate (WACC) must be strictly greater than Terminal Growth Rate.")
        return

    # Calculate Base DCF
    dcf_res = calculate_dcf(
        recent_fcf=recent_fcf,
        shares_outstanding=shares_outstanding,
        current_price=current_price,
        fcf_growth_rate=growth_rate,
        discount_rate=wacc,
        terminal_growth=terminal_growth,
        total_debt=total_debt,
        total_cash=total_cash
    )

    if not dcf_res.get("is_valid"):
        st.error(dcf_res.get("error", "Error calculating DCF."))
        return

    fair_value = dcf_res["fair_value"]
    mos = dcf_res["margin_of_safety"]
    upside = dcf_res["upside_pct"]
    ent_val = dcf_res["enterprise_value"]
    net_debt = dcf_res["net_debt"]
    eq_val = dcf_res["equity_value"]

    # KPI Summary Cards
    st.write("")
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
    
    with kpi_col1:
        st.metric(
            label="🎯 Estimated Fair Value",
            value=f"${fair_value:,.2f}",
            delta=f"{upside:+.1f}% vs Market" if current_price > 0 else None
        )
    with kpi_col2:
        st.metric(
            label="💵 Current Market Price",
            value=f"${current_price:,.2f}"
        )
    with kpi_col3:
        mos_color = "normal" if mos > 0 else "inverse"
        st.metric(
            label="🛡️ Margin of Safety",
            value=f"{mos:+.1f}%",
            delta="Undervalued" if mos > 0 else "Overvalued",
            delta_color=mos_color
        )
    with kpi_col4:
        st.metric(
            label="🏢 Implied Enterprise Value",
            value=f"${ent_val/1e9:,.2f}B"
        )

    st.divider()

    # Tabs for Deep Dive: Projection Waterfall, Sensitivity Matrix, Reverse DCF
    tab_sens, tab_waterfall, tab_rev = st.tabs([
        "🌡️ Sensitivity Matrix (Heatmap)",
        "📊 Cash Flow Waterfall",
        "🔄 Reverse DCF (Market Expectations)"
    ])

    with tab_sens:
        st.markdown("#### 🌡️ Fair Value Sensitivity Heatmap (WACC vs Terminal Growth)")
        st.markdown(
            "<p style='color: #8A929A; font-size: 13px;'>"
            "Inspect how the estimated Fair Value changes across a grid of required discount rates (rows) and perpetual growth assumptions (columns)."
            "</p>",
            unsafe_allow_html=True
        )
        
        df_fv_matrix, df_up_matrix = generate_dcf_sensitivity_matrix(
            recent_fcf=recent_fcf,
            shares_outstanding=shares_outstanding,
            current_price=current_price,
            base_growth=growth_rate,
            base_wacc=wacc,
            base_terminal=terminal_growth,
            total_debt=total_debt,
            total_cash=total_cash
        )

        # Render Heatmap with Plotly
        z_vals = df_fv_matrix.values
        x_labels = list(df_fv_matrix.columns)
        y_labels = list(df_fv_matrix.index)

        # Custom text annotations
        text_matrix = []
        for r_idx, row in enumerate(df_fv_matrix.values):
            text_row = []
            for c_idx, val in enumerate(row):
                up_val = df_up_matrix.iloc[r_idx, c_idx]
                if pd.isna(val):
                    text_row.append("N/A")
                else:
                    sign = "+" if up_val > 0 else ""
                    text_row.append(f"${val:,.1f}<br>({sign}{up_val:.0f}%)")
            text_matrix.append(text_row)

        fig_heat = go.Figure(data=go.Heatmap(
            z=z_vals,
            x=x_labels,
            y=y_labels,
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 12, "color": "white"},
            colorscale=[[0, "#dc2626"], [0.5, "#2563eb"], [1, "#059669"]],
            showscale=True,
            colorbar=dict(title="Fair Value ($)")
        ))
        fig_heat.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=20, b=10),
            xaxis_title="Terminal Growth Rate",
            yaxis_title="Discount Rate (WACC)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    with tab_waterfall:
        st.markdown("#### 📊 Present Value Decomposition of Enterprise Value")
        pv_fcf_sum = dcf_res["sum_pv_fcf"]
        pv_tv = dcf_res["pv_terminal_value"]
        
        wf_x = ["Y1 FCF", "Y2 FCF", "Y3 FCF", "Y4 FCF", "Y5 FCF", "PV Terminal Value", "Less Net Debt", "Equity Value"]
        wf_y = [
            dcf_res["pv_fcf_list"][0] / 1e9,
            dcf_res["pv_fcf_list"][1] / 1e9,
            dcf_res["pv_fcf_list"][2] / 1e9,
            dcf_res["pv_fcf_list"][3] / 1e9,
            dcf_res["pv_fcf_list"][4] / 1e9,
            pv_tv / 1e9,
            (-net_debt) / 1e9,
            eq_val / 1e9
        ]
        wf_measures = ["relative", "relative", "relative", "relative", "relative", "relative", "relative", "total"]

        fig_wf = go.Figure(go.Waterfall(
            name="DCF Breakdown",
            orientation="v",
            measure=wf_measures,
            x=wf_x,
            textposition="outside",
            text=[f"${v:+,.2f}B" if i < 7 else f"${v:,.2f}B" for i, v in enumerate(wf_y)],
            y=wf_y,
            connector={"line": {"color": "rgba(255,255,255,0.2)"}},
            decreasing={"marker": {"color": "#ef4444"}},
            increasing={"marker": {"color": "#10b981"}},
            totals={"marker": {"color": "#3b82f6"}}
        ))
        fig_wf.update_layout(
            height=360,
            margin=dict(l=10, r=10, t=30, b=10),
            yaxis_title="Billions ($B)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_wf, use_container_width=True)

        st.caption(
            f"💡 **Terminal Value Weight**: PV of Terminal Value represents "
            f"**{dcf_res['terminal_value_weight']:.1f}%** of total Enterprise Value."
        )

    with tab_rev:
        st.markdown("#### 🔄 Reverse DCF: What Expectations Are Priced In?")
        st.markdown(
            "<p style='color: #8A929A; font-size: 13px;'>"
            "Instead of predicting the future, Reverse DCF calculates the exact 5-year FCF compound growth rate "
            "required to justify the current market price of $" + f"{current_price:,.2f}."
            "</p>",
            unsafe_allow_html=True
        )

        rev_res = calculate_reverse_dcf(
            recent_fcf=recent_fcf,
            shares_outstanding=shares_outstanding,
            current_price=current_price,
            discount_rate=wacc,
            terminal_growth=terminal_growth,
            total_debt=total_debt,
            total_cash=total_cash
        )

        implied_g = rev_res.get("implied_growth")
        if implied_g is not None:
            rc1, rc2 = st.columns([1, 2])
            with rc1:
                st.metric(
                    label="Implied 5Y FCF Growth Rate",
                    value=f"{implied_g:+.1f}% / yr",
                    help="The annual FCF growth rate the company must achieve over the next 5 years to justify its current stock price."
                )
            with rc2:
                st.info(f"**Market Sentiment Assessment**:\n\n{rev_res.get('sentiment')}")
        else:
            st.warning(rev_res.get("error", "Unable to compute reverse DCF."))
