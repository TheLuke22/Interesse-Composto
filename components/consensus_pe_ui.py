"""
Consensus P/E and Capital Structure UI Component
Renders the Estimated P/E over the years, Consensus EPS Growth Rates,
and Capital Structure matching institutional layout.
"""

from typing import Dict, Any, Optional
import streamlit as st
import plotly.graph_objects as go
from analytics.consensus_pe import extract_consensus_pe_data


def render_consensus_pe_section(
    ticker: str,
    info: Optional[Dict[str, Any]] = None,
    stock_obj: Optional[Any] = None,
    current_price: Optional[float] = None,
    precalculated_data: Optional[Dict[str, Any]] = None,
    *args,
    **kwargs
):
    """
    Renders institutional section showing:
    1. Card 1: {TICKER} PE / PEG RATIO
       - Price/Earnings Ratio (Actual and Forward Estimated across years)
       - Consensus EPS Estimate Growth Rate (% by year)
    2. Card 2: CAPITAL STRUCTURE
       - Market Cap, Total Debt, Cash, Other, Enterprise Value
    3. Interactive Valuation & EPS Trajectory Chart + Target Multiple Simulator
    """
    info = info or {}
    ticker = str(ticker).upper().strip()

    # Extract clean consensus data (use precalculated cached data if available)
    if precalculated_data is not None and isinstance(precalculated_data, dict) and precalculated_data.get("is_valid"):
        data = precalculated_data
    else:
        try:
            data = extract_consensus_pe_data(
                ticker=ticker,
                info=info,
                stock_obj=stock_obj,
                current_price=current_price
            )
        except Exception:
            data = {}

    if not data or not data.get("is_valid"):
        st.warning(f"⚠️ Consensus forecast and P/E data is not currently available for **{ticker}**.")
        return

    company_name = data.get("company_name", ticker)
    pe_rows = data.get("pe_rows", [])
    growth_rows = data.get("growth_rows", [])
    capital_structure = data.get("capital_structure", [])
    price = data.get("current_price", 0.0) or 0.0

    # =========================================================
    # CARD 1: {TICKER} PE / PEG RATIO
    # =========================================================
    pe_rows_list = []
    for row in pe_rows:
        label = row.get("label", "")
        pe_val = f"{row['pe']:.2f}" if row.get("pe") is not None else "-"
        pe_rows_list.append(
            f'<div style="display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid #edf2f7; font-size:14.5px;">'
            f'<span style="font-weight:700; color:#111827;">{label}</span>'
            f'<span style="font-weight:500; color:#111827; text-align:right; font-family:\'JetBrains Mono\', monospace, sans-serif; font-size:14.5px;">{pe_val}</span>'
            f'</div>'
        )
    pe_rows_html = "".join(pe_rows_list)

    growth_rows_list = []
    for row in growth_rows:
        period = row.get("period", "")
        growth_str = row.get("growth_str", "-")
        growth_rows_list.append(
            f'<div style="display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid #edf2f7; font-size:14.5px;">'
            f'<span style="font-weight:700; color:#111827;">{period}</span>'
            f'<span style="font-weight:500; color:#111827; text-align:right; font-family:\'JetBrains Mono\', monospace, sans-serif; font-size:14.5px;">{growth_str}</span>'
            f'</div>'
        )
    growth_rows_html = "".join(growth_rows_list)

    card_1_html = (
        f'<div style="background:#ffffff; color:#111827; border-radius:12px; padding:26px 30px; margin-bottom:20px; box-shadow:0 2px 12px rgba(0,0,0,0.06); border:1px solid #e5e7eb; font-family:\'Inter\', -apple-system, sans-serif;">'
        f'<div style="font-size:15px; font-weight:800; text-transform:uppercase; letter-spacing:0.5px; color:#111827; margin-bottom:6px;">{ticker} PE / PEG RATIO</div>'
        f'<div style="font-size:14px; color:#6b7280; margin-bottom:20px; line-height:1.4;">View {company_name} ({ticker}) current and estimated P/E ratio data provided by Wall Street Consensus & Seeking Alpha models.</div>'
        f'<div style="font-size:16px; font-weight:700; color:#111827; margin-top:20px; margin-bottom:8px;">Price/Earnings Ratio</div>'
        f'{pe_rows_html}'
        f'<div style="font-size:16px; font-weight:700; color:#111827; margin-top:24px; margin-bottom:8px;">Consensus EPS Estimate Growth Rate</div>'
        f'{growth_rows_html}'
        f'</div>'
    )

    st.markdown(card_1_html, unsafe_allow_html=True)

    # =========================================================
    # CARD 2: CAPITAL STRUCTURE
    # =========================================================
    cap_rows_list = []
    for row in capital_structure:
        item = row.get("item", "")
        val_str = row.get("value_str", "-")
        cap_rows_list.append(
            f'<div style="display:flex; justify-content:space-between; align-items:center; padding:12px 0; border-bottom:1px solid #edf2f7; font-size:14.5px;">'
            f'<span style="font-weight:700; color:#111827;">{item}</span>'
            f'<span style="font-weight:500; color:#111827; text-align:right; font-family:\'JetBrains Mono\', monospace, sans-serif; font-size:14.5px;">{val_str}</span>'
            f'</div>'
        )
    cap_rows_html = "".join(cap_rows_list)

    card_2_html = (
        f'<div style="background:#ffffff; color:#111827; border-radius:12px; padding:26px 30px; margin-bottom:20px; box-shadow:0 2px 12px rgba(0,0,0,0.06); border:1px solid #e5e7eb; font-family:\'Inter\', -apple-system, sans-serif;">'
        f'<div style="font-size:15px; font-weight:800; text-transform:uppercase; letter-spacing:0.5px; color:#111827; margin-bottom:12px;">CAPITAL STRUCTURE</div>'
        f'{cap_rows_html}'
        f'</div>'
    )

    st.markdown(card_2_html, unsafe_allow_html=True)

    # =========================================================
    # INTERACTIVE DEEP DIVE: TRAJECTORY & SCENARIO SIMULATOR
    # =========================================================
    with st.expander("📊 Advanced Consensus Visualizer & Target Price Simulator", expanded=False):
        tab_chart, tab_sim = st.tabs(["📈 EPS & P/E Trajectory Chart", "🎯 Target Multiple Simulator"])

        with tab_chart:
            # Build Dual Axis Chart: EPS ($) vs Forward P/E (x)
            chart_years = []
            chart_eps = []
            chart_pe = []

            for r in pe_rows:
                if r.get("eps") is not None and r.get("pe") is not None:
                    chart_years.append(str(r.get("year", "")))
                    chart_eps.append(float(r["eps"]))
                    chart_pe.append(float(r["pe"]))

            if chart_years:
                fig = go.Figure()

                # EPS Bar trace (Left Axis)
                fig.add_trace(go.Bar(
                    x=chart_years,
                    y=chart_eps,
                    name="Consensus EPS ($)",
                    marker=dict(
                        color='rgba(0, 242, 254, 0.75)',
                        line=dict(color='#00f2fe', width=1.5)
                    ),
                    yaxis="y1",
                    text=[f"${v:.2f}" for v in chart_eps],
                    textposition="auto",
                ))

                # P/E Line trace (Right Axis)
                fig.add_trace(go.Scatter(
                    x=chart_years,
                    y=chart_pe,
                    name="Implied Forward P/E",
                    mode="lines+markers+text",
                    line=dict(color='#f59e0b', width=3),
                    marker=dict(size=9, color='#f59e0b', line=dict(color='#ffffff', width=2)),
                    yaxis="y2",
                    text=[f"{v:.1f}x" for v in chart_pe],
                    textposition="top center",
                ))

                fig.update_layout(
                    title=f"<b>{ticker} Consensus EPS Expansion vs Forward P/E Contraction</b>",
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    height=450,
                    margin=dict(l=20, r=20, t=50, b=30),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    yaxis=dict(
                        title="Consensus EPS ($)",
                        title_font=dict(color="#00f2fe"),
                        tickfont=dict(color="#00f2fe"),
                        showgrid=True,
                        gridcolor="rgba(255, 255, 255, 0.08)",
                    ),
                    yaxis2=dict(
                        title="Forward P/E Multiple (x)",
                        title_font=dict(color="#f59e0b"),
                        tickfont=dict(color="#f59e0b"),
                        overlaying="y",
                        side="right",
                        showgrid=False,
                    ),
                    xaxis=dict(
                        title="Fiscal Year",
                        showgrid=False,
                    )
                )

                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Chart data not available.")

        with tab_sim:
            st.markdown("#### 🧮 Target Exit Multiple & Price Projection")
            st.markdown(
                "Estimate the future stock price and compound annualized return (CAGR) based on consensus EPS and your assumed exit P/E multiple."
            )

            # Filter future estimated years
            future_pe_rows = [r for r in pe_rows if not r.get("is_actual") and r.get("eps") is not None]

            if future_pe_rows:
                sim_col1, sim_col2 = st.columns(2)
                with sim_col1:
                    target_year_choice = st.selectbox(
                        "Target Forecast Year",
                        options=[r["year"] for r in future_pe_rows],
                        index=len(future_pe_rows) - 1,
                        key=f"sim_year_{ticker}"
                    )
                selected_row = next((r for r in future_pe_rows if r.get("year") == target_year_choice), future_pe_rows[-1])
                projected_eps = float(selected_row.get("eps", 0.0) or 0.0)

                with sim_col2:
                    current_pe_bench = selected_row.get("pe") or 25.0
                    try:
                        default_sim_pe = round(float(current_pe_bench), 1)
                    except (ValueError, TypeError):
                        default_sim_pe = 25.0
                    target_pe_mult = st.slider(
                        f"Assumed Exit P/E Multiple in {target_year_choice}",
                        min_value=5.0,
                        max_value=80.0,
                        value=float(min(80.0, max(5.0, default_sim_pe))),
                        step=0.5,
                        key=f"sim_pe_slider_{ticker}"
                    )

                # Calculations
                implied_target_price = projected_eps * target_pe_mult
                cur_year = pe_rows[0].get("year", target_year_choice - 1) if pe_rows else (target_year_choice - 1)
                n_years = max(1, target_year_choice - cur_year)
                
                if price > 0:
                    total_return_pct = ((implied_target_price - price) / price) * 100
                    cagr_pct = (((implied_target_price / price) ** (1.0 / n_years)) - 1) * 100
                else:
                    total_return_pct = 0.0
                    cagr_pct = 0.0

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Projected EPS", f"${projected_eps:.2f}")
                m2.metric("Target Exit P/E", f"{target_pe_mult:.1f}x")
                m3.metric(f"Implied Price ({target_year_choice})", f"${implied_target_price:,.2f}", f"{total_return_pct:+.1f}% Total")
                m4.metric("Annualized Return (CAGR)", f"{cagr_pct:+.2f}%/yr")
            else:
                st.info("Simulation requires forward consensus EPS estimates.")
