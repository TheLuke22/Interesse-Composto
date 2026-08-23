"""
Institutional Stock Tracker & Deep Equity Analysis UI Component:
Features 9 institutional tabs:
1. Price & Tech Analysis (Candlestick, Moving Averages, Volumes, vs Benchmark)
2. Dividends & Total Returns (DRIP vs Cash, Snowball Effect, CAGR, Share Growth Breakdown)
3. Forward P/E & Wall Street Consensus (Consensus PE, Growth Decay, Capital Structure)
4. Monte Carlo Projections (GBM, 3D Probability Surface)
5. Ownership & Institutional Holders (Insiders, Top Funds)
6. Financial Health (Multi-Source 10-Year Trends: Rev, NI, EPS, FCF, Debt/Equity, Margins, EBITDA)
7. Fundamentals (Upcoming Earnings, Statements, AI Analysis)
8. DCF Valuation & Fair Value (WACC Sensitivity Matrix)
9. Warren Buffett 10-K Moat Scorecard
"""
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf

from components.ui_utils import (
    render_custom_metric,
    format_large_numbers,
    format_perc,
    calc_cagr,
    calc_risk_metrics
)
from components.consensus_pe_ui import render_consensus_pe_section
from components.dcf_ui import render_dcf_valuation_ui
from components.superinvestors_ui import render_buffett_scorecard_ui


def render_stock_tracker_ui(
    fetch_stock_info_fn,
    fetch_history_fn,
    fetch_realtime_price_fn,
    fetch_benchmark_history_fn,
    fetch_consensus_data_fn,
    fetch_ownership_data_fn,
    fetch_earnings_dates_cached_fn,
    fetch_macrotrends_financials_fn,
    fetch_fmp_financials_fn,
    fetch_financials_extended_fn,
    merge_financial_dfs_fn,
    fetch_financials_fn,
    generate_pdf_report_fn,
    analyze_financial_statements_ai_fn,
):
    """
    Renders the comprehensive 9-tab institutional Stock Tracker.
    """
    st.title("📊 Institutional Equity Analysis")
    st.divider()

    with st.form("stock_tracker_form", enter_to_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        default_ticker = st.session_state.get('active_ticker', 'KO')
        with col1:
            ticker_input = st.text_input("Stock Ticker", value=default_ticker).upper()
        with col2:
            invested_cap = st.number_input("Initial Investment ($)", min_value=100.0, value=1000.0)
        with col3:
            backtest_years = st.slider("Years of History", min_value=1, max_value=20, value=10)
        with col4:
            benchmark_ticker = st.text_input("Benchmark (Compare)", value="SPY").upper()

        submitted = st.form_submit_button("🚀 Run Deep Analysis", type="primary", use_container_width=True)
        if submitted:
            st.session_state['active_ticker'] = ticker_input.strip().upper()
            st.session_state['active_cap'] = invested_cap
            st.session_state['active_years'] = backtest_years
            st.session_state['active_bench'] = benchmark_ticker.strip().upper()
            st.rerun()

    if 'active_ticker' in st.session_state:
        a_ticker = st.session_state['active_ticker']
        a_cap = st.session_state['active_cap']
        a_years = st.session_state['active_years']
        a_bench = st.session_state['active_bench']

        with st.spinner("Caricamento in corso..."):
            info = fetch_stock_info_fn(a_ticker)
            hist_data = fetch_history_fn(a_ticker, a_years)
            stock = yf.Ticker(a_ticker)

            if hist_data.empty:
                st.error("Dati non disponibili o Ticker non trovato.")
            else:
                st.markdown(f"### 🏢 {info.get('shortName', a_ticker)}")

                # --- TOP METRICS BAR (REAL-TIME) ---
                rt_live = fetch_realtime_price_fn(a_ticker)
                rt_price = rt_live if rt_live is not None and rt_live > 0 else (
                    info.get('currentPrice') or (hist_data['Close'].iloc[-1] if not hist_data.empty else 0.0)
                )

                prev_close = info.get('previousClose', hist_data['Close'].iloc[-2] if len(hist_data) > 1 else rt_price)
                if prev_close > 0:
                    change = ((rt_price - prev_close) / prev_close) * 100
                else:
                    change = 0

                shares_out = info.get('sharesOutstanding')
                if shares_out and shares_out > 0:
                    rt_mcap = rt_price * shares_out
                else:
                    rt_mcap = info.get('marketCap', 0)

                def _safe_num(val):
                    if val is None:
                        return None
                    try:
                        if pd.isna(val):
                            return None
                    except Exception:
                        pass
                    return val if isinstance(val, (int, float)) else None

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Market Cap", format_large_numbers(rt_mcap))

                val_tpe = _safe_num(info.get('trailingPE'))
                if val_tpe is None:
                    e_ttm = _safe_num(info.get('trailingEps'))
                    if e_ttm and e_ttm > 0 and rt_price:
                        val_tpe = rt_price / e_ttm
                m2.metric("P/E (Trailing)", round(val_tpe, 2) if val_tpe is not None else 'N/A')

                eps_ttm = _safe_num(info.get('trailingEps'))
                m3.metric("EPS (TTM)", f"${eps_ttm:.2f}" if eps_ttm is not None else 'N/A')

                div_rate = _safe_num(info.get('dividendRate'))
                m4.metric("Div Rate", f"${div_rate:.2f}" if div_rate is not None else 'N/A')

                st.write("")

                m5, m6, m7, m8 = st.columns(4)
                m5.metric("Current Price", f"${rt_price:,.2f}", f"{change:.2f}%")

                val_fpe = _safe_num(info.get('forwardPE'))
                if val_fpe is None:
                    e_fwd = _safe_num(info.get('forwardEps'))
                    if e_fwd and e_fwd > 0 and rt_price:
                        val_fpe = rt_price / e_fwd
                m6.metric("P/E (Forward)", round(val_fpe, 2) if val_fpe is not None else 'N/A')

                eps_fwd = _safe_num(info.get('forwardEps'))
                m7.metric("EPS (Forward)", f"${eps_fwd:.2f}" if eps_fwd is not None else 'N/A')

                div_rate = info.get('dividendRate')
                if div_rate and rt_price > 0:
                    div_yield_str = f"{(div_rate / rt_price) * 100:.2f}%"
                else:
                    div_yield_str = "N/A"
                m8.metric("Div Yield (FWD)", div_yield_str)

                # --- QUANTITATIVE RISK METRICS ---
                st.divider()
                st.markdown("#### ⚖️ Quantitative Risk Profile")
                returns = hist_data['Close'].pct_change().dropna()
                sharpe, max_dd = calc_risk_metrics(returns)

                q1, q2, q3 = st.columns(3)
                q1.metric(f"Sharpe Ratio ({a_years}Y)", f"{sharpe:.2f}")
                q2.metric(f"Max Drawdown ({a_years}Y)", f"{max_dd*100:.2f}%")
                q3.metric("Volatility (Annual)", f"{returns.std()*np.sqrt(252)*100:.2f}%")
                st.divider()

                # --- SIMULATORE PREZZO (DRIP VS NO DRIP) ---
                shares_with_drip = a_cap / hist_data['Close'].iloc[0]
                shares_no_drip = shares_with_drip
                cash_no_drip = 0
                val_with_drip_series, val_no_drip_series, val_price_only_series = [], [], []
                div_history = []

                sim_shares_drip = shares_no_drip
                reinvested_shares_by_year = {}
                div_by_year = {}
                shares_at_year_end = {}

                for i in range(len(hist_data)):
                    price = hist_data['Close'].iloc[i]
                    div = hist_data['Dividends'].iloc[i]
                    date = hist_data.index[i]
                    year = date.year

                    if year not in reinvested_shares_by_year:
                        reinvested_shares_by_year[year] = 0.0
                        div_by_year[year] = 0.0

                    div_incassato_drip_sim = div * sim_shares_drip
                    if div > 0:
                        shares_bought_sim = div_incassato_drip_sim / price
                        sim_shares_drip += shares_bought_sim
                        reinvested_shares_by_year[year] += shares_bought_sim
                        div_by_year[year] += div_incassato_drip_sim

                    shares_at_year_end[year] = sim_shares_drip

                    if div > 0:
                        div_incassato_drip = div * shares_with_drip
                        shares_with_drip += div_incassato_drip / price

                        div_incassato_no_drip = div * shares_no_drip
                        cash_no_drip += div_incassato_no_drip

                        div_history.append({"Date": date, "Amount": div_incassato_drip})

                    val_with_drip_series.append(shares_with_drip * price)
                    val_no_drip_series.append((shares_no_drip * price) + cash_no_drip)
                    val_price_only_series.append(shares_no_drip * price)

                st.divider()
                with st.expander("📄 Genera Report PDF (Tear Sheet)"):
                    pdf_bytes = generate_pdf_report_fn(a_ticker, rt_price, info, sharpe, max_dd)
                    st.download_button(
                        label="Scarica PDF Tear Sheet",
                        data=pdf_bytes,
                        file_name=f"{a_ticker}_TearSheet.pdf",
                        mime="application/pdf"
                    )

                tab_price, tab_divs, tab_consensus, tab_mc, tab_holders, tab_fhealth, tab_funds, tab_dcf, tab_buffett = st.tabs([
                    "📊 Price & Tech Analysis",
                    "💰 Dividends & Returns",
                    "🎯 Forward P/E & Consensus",
                    "🎲 Projections",
                    "🏦 Ownership",
                    "📈 Financial Health",
                    "📅 Fundamentals",
                    "🧮 DCF Valuation",
                    "🧙‍♂️ Buffett Scorecard"
                ])

                # --- TAB 1: PRICE & TECH ---
                with tab_price:
                    col_t1, col_t2 = st.columns([3, 1])
                    with col_t1:
                        st.subheader("Historical Performance")
                    with col_t2:
                        chart_type = st.toggle("Mostra Analisi Tecnica (Candele)", value=False)

                    if chart_type:
                        fig_cand = make_subplots(
                            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3]
                        )
                        fig_cand.add_trace(
                            go.Candlestick(
                                x=hist_data.index, open=hist_data['Open'], high=hist_data['High'],
                                low=hist_data['Low'], close=hist_data['Close'], name='Price'
                            ),
                            row=1, col=1
                        )
                        sma50 = hist_data['Close'].rolling(window=50).mean()
                        sma200 = hist_data['Close'].rolling(window=200).mean()
                        fig_cand.add_trace(go.Scatter(x=hist_data.index, y=sma50, line=dict(color='orange', width=1.5), name='SMA 50'), row=1, col=1)
                        fig_cand.add_trace(go.Scatter(x=hist_data.index, y=sma200, line=dict(color='purple', width=1.5), name='SMA 200'), row=1, col=1)

                        colors = ['#27AE60' if c >= o else '#E74C3C' for c, o in zip(hist_data['Close'], hist_data['Open'])]
                        fig_cand.add_trace(go.Bar(x=hist_data.index, y=hist_data['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

                        fig_cand.update_layout(xaxis_rangeslider_visible=False, height=600, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_cand, use_container_width=True)

                    else:
                        bench_start = str(hist_data.index[0])[:10]
                        bench_end = str(hist_data.index[-1])[:10]
                        bench_raw = fetch_benchmark_history_fn(a_bench, bench_start, bench_end)
                        if not bench_raw.empty:
                            if 'Close' in bench_raw.columns:
                                bench_close = bench_raw['Close'].squeeze()
                            else:
                                bench_close = bench_raw.squeeze()

                            stock_close = hist_data['Close'].squeeze()
                            norm_stock = (stock_close / stock_close.iloc[0]) * 100
                            norm_bench = (bench_close / bench_close.iloc[0]) * 100

                            fig_comp = go.Figure()
                            fig_comp.add_trace(go.Scatter(x=norm_stock.index, y=norm_stock, name=a_ticker, line=dict(color='#2E86C1', width=2)))
                            fig_comp.add_trace(go.Scatter(x=norm_bench.index, y=norm_bench, name=a_bench, line=dict(color='#E74C3C', width=2)))
                            fig_comp.update_layout(
                                yaxis_title="Value of 100$ Investment", hovermode="x unified",
                                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                margin=dict(l=0, r=0, t=30, b=0)
                            )
                            st.plotly_chart(fig_comp, use_container_width=True)
                        else:
                            st.warning("Dati benchmark non disponibili.")

                # --- TAB 2: DIVIDENDS ---
                with tab_divs:
                    st.subheader("Total Return & Dividend Compounding")

                    tot_ret_drip = (val_with_drip_series[-1] / a_cap) - 1
                    tot_ret_no_drip = (val_no_drip_series[-1] / a_cap) - 1

                    div_rate_val = info.get('dividendRate')
                    if div_rate_val is None or div_rate_val == 0:
                        div_rate_val = info.get('trailingAnnualDividendRate')
                    if div_rate_val is None or div_rate_val == 0:
                        if not hist_data.empty:
                            last_date = hist_data.index[-1]
                            one_year_ago = last_date - pd.DateOffset(years=1)
                            recent_divs = hist_data.loc[one_year_ago:last_date, 'Dividends']
                            if not recent_divs.empty:
                                div_rate_val = recent_divs.sum()
                    if div_rate_val is None:
                        div_rate_val = 0.0

                    yoc_drip = (div_rate_val * shares_with_drip) / a_cap
                    yoc_no_drip = (div_rate_val * shares_no_drip) / a_cap

                    pm1, pm2 = st.columns(2)
                    pm1.metric("Total Return (with DRIP)", format_perc(tot_ret_drip))
                    pm1.metric("Yield on Cost (with DRIP)", format_perc(yoc_drip))
                    pm2.metric("Total Return (w/o DRIP)", format_perc(tot_ret_no_drip))
                    pm2.metric("Yield on Cost (w/o DRIP)", format_perc(yoc_no_drip))

                    fig_perf = go.Figure()
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=val_with_drip_series, name='Total Return (with DRIP)', fill='tozeroy', line=dict(color='#27AE60')))
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=val_no_drip_series, name='Total Return (w/o DRIP)', line=dict(color='#2E86C1')))
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=val_price_only_series, name='Price Only', line=dict(color='#95A5A6', dash='dash')))
                    fig_perf.update_layout(yaxis_title="Portfolio Value ($)", margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_perf, use_container_width=True)

                    st.divider()
                    st.subheader("❄️ The Dividend Snowball Effect")
                    if div_history:
                        df_div = pd.DataFrame(div_history)
                        df_div['Year'] = df_div['Date'].dt.year
                        yearly_div = df_div.groupby('Year')['Amount'].sum().reset_index()

                        fig_snow = px.bar(yearly_div, x='Year', y='Amount', text_auto='.2f', color_discrete_sequence=['#F1C40F'])
                        fig_snow.update_layout(xaxis_title="Year", yaxis_title="Dividends Received ($)", margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_snow, use_container_width=True)
                    else:
                        st.info("Questo titolo non ha distribuito dividendi nel periodo selezionato.")

                    st.divider()
                    st.subheader("📈 Dividend Growth (CAGR)")

                    raw_divs = hist_data['Dividends'][hist_data['Dividends'] > 0]
                    if not raw_divs.empty:
                        annual_divs = raw_divs.groupby(raw_divs.index.year).sum()
                        current_year = datetime.today().year
                        annual_divs = annual_divs[annual_divs.index < current_year]

                        if len(annual_divs) >= 2:
                            latest_div = annual_divs.iloc[-1]
                            c1, c2, c3 = st.columns(3)

                            anni_totali = len(annual_divs) - 1
                            primo_div = annual_divs.iloc[0]
                            cagr_tot = calc_cagr(primo_div, latest_div, anni_totali)
                            c1.metric(f"CAGR ({anni_totali} Anni)", format_perc(cagr_tot))

                            if len(annual_divs) >= 6:
                                div_5y_ago = annual_divs.iloc[-6]
                                cagr_5y = calc_cagr(div_5y_ago, latest_div, 5)
                                c2.metric("CAGR (5 Anni)", format_perc(cagr_5y))
                            else:
                                c2.metric("CAGR (5 Anni)", "N/A")

                            if len(annual_divs) >= 4:
                                div_3y_ago = annual_divs.iloc[-4]
                                cagr_3y = calc_cagr(div_3y_ago, latest_div, 3)
                                c3.metric("CAGR (3 Anni)", format_perc(cagr_3y))
                            else:
                                c3.metric("CAGR (3 Anni)", "N/A")
                        else:
                            st.info("Storico di anni completi insufficiente per calcolare la crescita annuale composta (CAGR).")

                    st.divider()
                    st.subheader("❄️ Reinvestment & Share Ownership Details")

                    initial_shares = a_cap / hist_data['Close'].iloc[0]
                    current_shares_actual = shares_with_drip

                    st.write("Analizziamo in dettaglio come l'investimento iniziale ha generato e accumulato quote azionarie nel tempo.")

                    oc1, oc2 = st.columns(2)
                    with oc1:
                        st.markdown(f"""
                        <div class="custom-kpi-card" style="background: rgba(46, 134, 193, 0.05); border: 1px solid rgba(46, 134, 193, 0.15); min-height: 125px;">
                            <div style="font-size: 13px; font-weight: 500; color: #8A929A; text-transform: uppercase;">Stato Azioni Finali (con DRIP)</div>
                            <div style="font-size: 28px; font-weight: 700; color: #ffffff; margin-top: 10px;">{current_shares_actual:.3f} <span style="font-size: 16px; font-weight: 500; color: #cbd5e1;">Azioni</span></div>
                            <div style="color: #8A929A; font-size: 12px; margin-top: 6px;">
                                Investimento iniziale di <b>${a_cap:,.2f}</b> = {initial_shares:.3f} azioni acquistate all'inizio.
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    with oc2:
                        extra_shares = sim_shares_drip - initial_shares
                        pct_increase = (extra_shares / initial_shares) * 100 if initial_shares > 0 else 0
                        st.markdown(f"""
                        <div class="custom-kpi-card" style="background: rgba(0, 255, 127, 0.05); border: 1px solid rgba(0, 255, 127, 0.15); min-height: 125px;">
                            <div style="font-size: 13px; font-weight: 500; color: #8A929A; text-transform: uppercase;">Moltiplicatore DRIP (Potenziale)</div>
                            <div style="font-size: 28px; font-weight: 700; color: #00FF7F; margin-top: 10px;">+{extra_shares:.3f} <span style="font-size: 16px; font-weight: 500; color: #cbd5e1;">Azioni</span></div>
                            <div style="color: #00FF7F; font-size: 12px; margin-top: 6px; font-weight: 600;">
                                Incremento del +{pct_increase:.2f}% nel numero di azioni possedute!
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                    st.write("")
                    st.markdown("#### 📅 Piano di Accumulo Reinvestimenti (DRIP)")
                    st.write("Dettaglio anno per anno delle azioni riacquistate e della crescita del portafoglio grazie al reinvestimento automatico dei dividendi:")

                    total_divs_all_years = sum(div_by_year.values())
                    if reinvested_shares_by_year and total_divs_all_years > 0:
                        table_html = """
                        <table class="premium-portfolio-table">
                            <thead>
                                <tr>
                                    <th>Anno</th>
                                    <th style="text-align: right;">Dividendi Ricevuti ($)</th>
                                    <th style="text-align: right;">Azioni Riacquistate</th>
                                    <th style="text-align: right;">Totale Azioni Fine Anno</th>
                                </tr>
                            </thead>
                            <tbody>
                        """
                        sorted_years = sorted(reinvested_shares_by_year.keys())
                        for yr in sorted_years:
                            div_rec = div_by_year.get(yr, 0.0)
                            shares_b = reinvested_shares_by_year.get(yr, 0.0)
                            total_sh = shares_at_year_end.get(yr, initial_shares)

                            table_html += f"""
                            <tr>
                                <td><span class="ticker-badge" style="background: rgba(255, 255, 255, 0.08); box-shadow: none; color: #ffffff !important;">{yr}</span></td>
                                <td style="text-align: right; font-weight: 600; color: #00FF7F;">${div_rec:,.2f}</td>
                                <td style="text-align: right; font-weight: 600; color: #00f2fe;">+{shares_b:.3f}</td>
                                <td style="text-align: right; font-weight: 700; color: #ffffff;">{total_sh:.3f}</td>
                            </tr>
                            """

                        table_html += "</tbody></table>"
                        clean_table_html = "\n".join([line.strip() for line in table_html.split("\n")])
                        st.markdown(clean_table_html, unsafe_allow_html=True)
                    else:
                        st.info("Questo titolo non ha distribuito dividendi nel periodo selezionato, quindi non ci sono riacquisti da mostrare.")

                # --- TAB 3: FORWARD P/E & CONSENSUS ---
                with tab_consensus:
                    try:
                        consensus_data = fetch_consensus_data_fn(a_ticker, rt_price)
                        render_consensus_pe_section(
                            ticker=a_ticker,
                            info=info,
                            stock_obj=stock,
                            current_price=rt_price,
                            precalculated_data=consensus_data
                        )
                    except Exception:
                        st.info(f"Consensus forecast data temporarily unavailable for {a_ticker}.")

                # --- TAB 4: PROJECTIONS ---
                with tab_mc:
                    st.subheader("🎲 Monte Carlo Simulation (5Y Projection)")
                    st.write("Simulazione basata sul Geometric Brownian Motion (GBM).")

                    log_returns = np.log(1 + returns)
                    mu, sigma = log_returns.mean(), log_returns.std()

                    sim_days, num_sim = 252 * 5, 100
                    last_price = hist_data['Close'].iloc[-1]
                    last_date = hist_data.index[-1]

                    daily_sim_returns = np.exp(np.random.normal(mu - 0.5 * sigma**2, sigma, (sim_days, num_sim)))
                    sims = np.zeros_like(daily_sim_returns)
                    sims[0] = last_price
                    for t in range(1, sim_days):
                        sims[t] = sims[t-1] * daily_sim_returns[t]

                    time_idx = np.repeat(np.arange(sim_days), num_sim)
                    price_vals = sims.flatten()

                    try:
                        H, xedges, yedges = np.histogram2d(time_idx, price_vals, bins=[50, 50])
                        H_z = H.T

                        try:
                            from scipy.ndimage import gaussian_filter
                            H_z = gaussian_filter(H_z, sigma=1.5)
                        except Exception:
                            pass

                        fig_mc = go.Figure(data=[go.Surface(
                            z=H_z,
                            x=xedges[:-1],
                            y=yedges[:-1],
                            colorscale='Plasma',
                            opacity=0.9
                        )])

                        fig_mc.update_layout(
                            scene=dict(
                                xaxis_title='Days in Future',
                                yaxis_title='Projected Price ($)',
                                zaxis_title='Probability Heat',
                                xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)", showticklabels=False)
                            ),
                            margin=dict(l=0, r=0, b=0, t=0),
                            height=600
                        )
                        st.plotly_chart(fig_mc, use_container_width=True)
                    except Exception as e:
                        st.error(f"Impossibile generare la topografia 3D: {e}")

                # --- TAB 5: OWNERSHIP ---
                with tab_holders:
                    st.subheader("Major Shareholders")
                    col_h1, col_h2 = st.columns(2)
                    holders, inst_holders = fetch_ownership_data_fn(a_ticker)

                    with col_h1:
                        st.write("**Share Ownership Breakdown**")
                        if holders is not None and not holders.empty:
                            holders_df = holders.copy()
                            if isinstance(holders_df, pd.Series):
                                holders_df = holders_df.to_frame()

                            holders_df = holders_df.reset_index()
                            if len(holders_df.columns) >= 2:
                                holders_df.columns = ["Descrizione", "Valore"] + list(holders_df.columns[2:])
                                label_map = {
                                    'insidersPercentHeld': '% Held by Insiders',
                                    'institutionsPercentHeld': '% Held by Institutions',
                                    'institutionsFloatPercentHeld': '% Float Held by Institutions',
                                    'institutionsCount': 'Number of Institutions'
                                }
                                holders_df['Descrizione'] = holders_df['Descrizione'].replace(label_map)

                                def format_holder_val(row):
                                    val = pd.to_numeric(row['Valore'], errors='coerce')
                                    if pd.isna(val):
                                        return row['Valore']
                                    if "Number" in str(row['Descrizione']) or val > 1.5:
                                        return f"{int(val):,}"
                                    else:
                                        return f"{val * 100:.2f}%"
                                holders_df['Valore'] = holders_df.apply(format_holder_val, axis=1)

                            st.dataframe(holders_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Ownership data not available.")

                    with col_h2:
                        st.write("**Top Institutional Holders**")
                        if inst_holders is not None and not inst_holders.empty:
                            inst_df = inst_holders.copy()
                            inst_df.rename(columns={'pctHeld': '% Held', 'pctChange': '% Change'}, inplace=True)

                            for col in ['% Held', '% Out', '% Change']:
                                if col in inst_df.columns:
                                    inst_df[col] = (pd.to_numeric(inst_df[col], errors='coerce') * 100).map("{:.2f}%".format)
                            if 'Shares' in inst_df.columns:
                                inst_df['Shares'] = pd.to_numeric(inst_df['Shares'], errors='coerce').apply(
                                    lambda x: format_large_numbers(x, is_currency=False)
                                )
                            if 'Value' in inst_df.columns:
                                inst_df['Value'] = pd.to_numeric(inst_df['Value'], errors='coerce').apply(format_large_numbers)
                            st.dataframe(inst_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Institutional data not available.")

                # --- TAB 6: FINANCIAL HEALTH ---
                with tab_fhealth:
                    st.subheader("📈 Financial Health — Trend Analysis")
                    st.markdown("<p style='color: #8A929A; margin-top:-10px; margin-bottom:20px;'>Andamento storico dei principali indicatori fondamentali anno per anno.</p>", unsafe_allow_html=True)

                    _FMP_API_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"
                    mt_inc, mt_bal, mt_cash = fetch_macrotrends_financials_fn(a_ticker, limit_years=10)
                    fmp_inc, fmp_bal, fmp_cash = fetch_fmp_financials_fn(a_ticker, _FMP_API_KEY)
                    yf_inc, yf_bal, yf_cash = fetch_financials_extended_fn(a_ticker)

                    if not mt_inc.empty:
                        fh_inc = merge_financial_dfs_fn(mt_inc, merge_financial_dfs_fn(fmp_inc, yf_inc))
                        fh_bal = merge_financial_dfs_fn(mt_bal, merge_financial_dfs_fn(fmp_bal, yf_bal))
                        fh_cash = merge_financial_dfs_fn(mt_cash, merge_financial_dfs_fn(fmp_cash, yf_cash))
                        n_years = len(fh_inc.columns)
                        st.caption(f"📡 Sorgente: **Multi-Source ({n_years} anni)**")
                    elif not fmp_inc.empty:
                        fh_inc = merge_financial_dfs_fn(fmp_inc, yf_inc)
                        fh_bal = merge_financial_dfs_fn(fmp_bal, yf_bal)
                        fh_cash = merge_financial_dfs_fn(fmp_cash, yf_cash)
                        n_years = len(fh_inc.columns)
                        st.caption(f"📡 Sorgente: **FMP + Yahoo Finance ({n_years} anni)**")
                    elif yf_inc is not None and not yf_inc.empty:
                        fh_inc, fh_bal, fh_cash = yf_inc, yf_bal, yf_cash
                        n_years = len(fh_inc.columns)
                        st.caption(f"📡 Sorgente: **Yahoo Finance ({n_years} anni)**")
                    else:
                        fh_inc, fh_bal, fh_cash = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
                        st.warning("⚠️ Nessuna sorgente dati disponibile.")

                    def _extract_annual_series(df, row_name):
                        if df is None or df.empty:
                            return None
                        if row_name not in df.index:
                            return None
                        row = df.loc[row_name].dropna()
                        row = pd.to_numeric(row, errors='coerce').dropna()
                        if row.empty:
                            return None
                        row.index = [c.year if hasattr(c, 'year') else str(c) for c in row.index]
                        row = row.groupby(level=0).last()
                        return row.sort_index()

                    _chart_layout = dict(
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#e0e0e0', family='Inter, sans-serif'),
                        margin=dict(l=20, r=20, t=40, b=40),
                        height=380,
                        xaxis=dict(gridcolor='rgba(255,255,255,0.06)', dtick=1),
                        yaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
                        hovermode='x unified',
                        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
                    )

                    has_any_chart = False

                    # Revenue & Net Income
                    revenue = _extract_annual_series(fh_inc, 'Total Revenue')
                    net_income = _extract_annual_series(fh_inc, 'Net Income')

                    ch_col1, ch_col2 = st.columns(2)
                    with ch_col1:
                        if revenue is not None and len(revenue) >= 2:
                            has_any_chart = True
                            fig_rev = go.Figure()
                            colors_rev = ['#3b82f6' if v >= 0 else '#ef4444' for v in revenue.values]
                            fig_rev.add_trace(go.Bar(
                                x=[str(y) for y in revenue.index], y=revenue.values,
                                marker_color=colors_rev, name='Revenue',
                                text=[format_large_numbers(v) for v in revenue.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_rev.update_layout(title='💵 Total Revenue', **_chart_layout)
                            st.plotly_chart(fig_rev, use_container_width=True)
                        else:
                            st.info("Revenue data not available.")

                    with ch_col2:
                        if net_income is not None and len(net_income) >= 2:
                            has_any_chart = True
                            fig_ni = go.Figure()
                            colors_ni = ['#22c55e' if v >= 0 else '#ef4444' for v in net_income.values]
                            fig_ni.add_trace(go.Bar(
                                x=[str(y) for y in net_income.index], y=net_income.values,
                                marker_color=colors_ni, name='Net Income',
                                text=[format_large_numbers(v) for v in net_income.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_ni.update_layout(title='📊 Net Income', **_chart_layout)
                            st.plotly_chart(fig_ni, use_container_width=True)
                        else:
                            st.info("Net Income data not available.")

                    # EPS & FCF
                    basic_eps = _extract_annual_series(fh_inc, 'Basic EPS')
                    diluted_eps = _extract_annual_series(fh_inc, 'Diluted EPS')
                    eps_series = basic_eps if basic_eps is not None else diluted_eps
                    fcf = _extract_annual_series(fh_cash, 'Free Cash Flow')

                    ch_col3, ch_col4 = st.columns(2)
                    with ch_col3:
                        if eps_series is not None and len(eps_series) >= 2:
                            has_any_chart = True
                            fig_eps = go.Figure()
                            colors_eps = ['#a78bfa' if v >= 0 else '#ef4444' for v in eps_series.values]
                            fig_eps.add_trace(go.Bar(
                                x=[str(y) for y in eps_series.index], y=eps_series.values,
                                marker_color=colors_eps, name='EPS',
                                text=[f"${v:.2f}" for v in eps_series.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_eps.update_layout(title='💰 Earnings Per Share (EPS)', **_chart_layout)
                            st.plotly_chart(fig_eps, use_container_width=True)
                        else:
                            st.info("EPS data not available.")

                    with ch_col4:
                        if fcf is not None and len(fcf) >= 2:
                            has_any_chart = True
                            fig_fcf = go.Figure()
                            colors_fcf = ['#06b6d4' if v >= 0 else '#ef4444' for v in fcf.values]
                            fig_fcf.add_trace(go.Bar(
                                x=[str(y) for y in fcf.index], y=fcf.values,
                                marker_color=colors_fcf, name='FCF',
                                text=[format_large_numbers(v) for v in fcf.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_fcf.update_layout(title='🏦 Free Cash Flow', **_chart_layout)
                            st.plotly_chart(fig_fcf, use_container_width=True)
                        else:
                            st.info("Free Cash Flow data not available.")

                    # Debt vs Equity & Margins
                    total_debt = _extract_annual_series(fh_bal, 'Total Debt')
                    total_equity = _extract_annual_series(fh_bal, 'Stockholders Equity')
                    if total_equity is None:
                        total_equity = _extract_annual_series(fh_bal, 'Total Stockholders Equity')
                    gross_profit = _extract_annual_series(fh_inc, 'Gross Profit')
                    operating_income = _extract_annual_series(fh_inc, 'Operating Income')

                    ch_col5, ch_col6 = st.columns(2)
                    with ch_col5:
                        if total_debt is not None and total_equity is not None:
                            has_any_chart = True
                            common_years = sorted(set(total_debt.index) & set(total_equity.index))
                            if len(common_years) >= 2:
                                fig_de = go.Figure()
                                fig_de.add_trace(go.Bar(
                                    x=[str(y) for y in common_years], y=[total_debt[y] for y in common_years],
                                    name='Total Debt', marker_color='#ef4444',
                                    text=[format_large_numbers(total_debt[y]) for y in common_years],
                                    textposition='outside', textfont=dict(size=10)
                                ))
                                fig_de.add_trace(go.Bar(
                                    x=[str(y) for y in common_years], y=[total_equity[y] for y in common_years],
                                    name='Equity', marker_color='#22c55e',
                                    text=[format_large_numbers(total_equity[y]) for y in common_years],
                                    textposition='outside', textfont=dict(size=10)
                                ))
                                fig_de.update_layout(title='⚖️ Debt vs Equity', barmode='group', **_chart_layout)
                                st.plotly_chart(fig_de, use_container_width=True)
                            else:
                                st.info("Not enough common years for Debt vs Equity chart.")
                        else:
                            st.info("Debt / Equity data not available.")

                    with ch_col6:
                        if revenue is not None and len(revenue) >= 2:
                            fig_margins = go.Figure()
                            margin_plotted = False

                            if gross_profit is not None:
                                common = sorted(set(revenue.index) & set(gross_profit.index))
                                if len(common) >= 2:
                                    gm = [(gross_profit[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=gm, name='Gross Margin %',
                                        mode='lines+markers', line=dict(color='#3b82f6', width=2.5), marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if operating_income is not None:
                                common = sorted(set(revenue.index) & set(operating_income.index))
                                if len(common) >= 2:
                                    om = [(operating_income[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=om, name='Operating Margin %',
                                        mode='lines+markers', line=dict(color='#f59e0b', width=2.5), marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if net_income is not None:
                                common = sorted(set(revenue.index) & set(net_income.index))
                                if len(common) >= 2:
                                    nm = [(net_income[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=nm, name='Net Margin %',
                                        mode='lines+markers', line=dict(color='#22c55e', width=2.5), marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if margin_plotted:
                                has_any_chart = True
                                fig_margins.update_layout(title='📐 Profitability Margins (%)', yaxis_title='Margin %', **_chart_layout)
                                st.plotly_chart(fig_margins, use_container_width=True)
                            else:
                                st.info("Margin data not available.")
                        else:
                            st.info("Revenue data insufficient for margin calculation.")

                    # EBITDA Trend
                    ebitda = _extract_annual_series(fh_inc, 'EBITDA')
                    if ebitda is not None and len(ebitda) >= 2:
                        has_any_chart = True
                        fig_ebitda = go.Figure()
                        fig_ebitda.add_trace(go.Scatter(
                            x=[str(y) for y in ebitda.index], y=ebitda.values,
                            mode='lines+markers+text',
                            line=dict(color='#f97316', width=3),
                            marker=dict(size=10, color='#f97316', line=dict(width=2, color='#ffffff')),
                            text=[format_large_numbers(v) for v in ebitda.values],
                            textposition='top center', textfont=dict(size=11),
                            fill='tozeroy', fillcolor='rgba(249, 115, 22, 0.08)',
                            name='EBITDA'
                        ))
                        fig_ebitda.update_layout(title='🔥 EBITDA Trend', height=350, **{k: v for k, v in _chart_layout.items() if k != 'height'})
                        st.plotly_chart(fig_ebitda, use_container_width=True)

                    if not has_any_chart:
                        st.warning("⚠️ Nessun dato fondamentale disponibile per questo ticker. Potrebbe trattarsi di un ETF o di un titolo con dati limitati.")

                # --- TAB 7: FUNDAMENTALS ---
                with tab_funds:
                    st.subheader("📅 Upcoming Earnings & Estimates")
                    earn_data = fetch_earnings_dates_cached_fn(a_ticker)
                    if earn_data is not None and not (isinstance(earn_data, pd.DataFrame) and earn_data.empty):
                        st.dataframe(earn_data, use_container_width=True)
                    else:
                        st.info("Upcoming earnings dates not available.")

                    st.subheader("Financial Highlights")
                    h1, h2, h3 = st.columns(3)
                    with h1:
                        render_custom_metric("Profit Margin", format_perc(info.get('profitMargins')), icon="💰")
                        render_custom_metric("ROE (ttm)", format_perc(info.get('returnOnEquity')), icon="📈")
                    with h2:
                        render_custom_metric("Total Cash", format_large_numbers(info.get('totalCash')), icon="💵")
                        render_custom_metric("Debt/Equity", str(info.get('debtToEquity', 'N/A')), icon="⚖️")
                    with h3:
                        render_custom_metric("Free Cash Flow", format_large_numbers(info.get('leveredFreeCashFlow')), icon="💸")

                    st.divider()
                    st.subheader("📑 Full Financial Statements (Annual)")

                    inc_stmt, bal_sheet, cash_flow = fetch_financials_fn(a_ticker)

                    def format_fin_df(df):
                        if df is None or df.empty:
                            return df
                        df_fmt = df.copy()
                        df_fmt.columns = [c.strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c) for c in df_fmt.columns]
                        for col in df_fmt.columns:
                            df_fmt[col] = df_fmt[col].apply(format_large_numbers)
                        return df_fmt

                    inc_stmt_fmt = format_fin_df(inc_stmt)
                    bal_sheet_fmt = format_fin_df(bal_sheet)
                    cash_flow_fmt = format_fin_df(cash_flow)

                    sub_t1, sub_t2, sub_t3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
                    with sub_t1:
                        if not inc_stmt_fmt.empty:
                            st.dataframe(inc_stmt_fmt, use_container_width=True)
                        else:
                            st.info("Dati non disponibili.")
                    with sub_t2:
                        if not bal_sheet_fmt.empty:
                            st.dataframe(bal_sheet_fmt, use_container_width=True)
                        else:
                            st.info("Dati non disponibili.")
                    with sub_t3:
                        if not cash_flow_fmt.empty:
                            st.dataframe(cash_flow_fmt, use_container_width=True)
                        else:
                            st.info("Dati non disponibili.")

                    st.divider()
                    st.subheader("🤖 AI Financial Analysis")
                    st.write(f"Sfrutta l'intelligenza artificiale locale di Gemma per analizzare i bilanci di **{a_ticker}** e ottenerne una valutazione della solidità.")
                    if st.button("⚖️ Genera Report Fondamentale", type="secondary"):
                        with st.spinner(f"Gemma sta scansionando i rendiconti annuali di {a_ticker} per elaborare un'analisi..."):
                            ai_report = analyze_financial_statements_ai_fn(a_ticker, inc_stmt, bal_sheet, cash_flow)
                            st.info(ai_report)

                # --- TAB 8: DCF VALUATION ---
                with tab_dcf:
                    try:
                        inc_stmt_dcf, bal_sheet_dcf, cash_flow_dcf = fetch_financials_fn(a_ticker)
                        if not cash_flow_dcf.empty and 'Free Cash Flow' in cash_flow_dcf.index:
                            recent_fcf = cash_flow_dcf.loc['Free Cash Flow'].dropna().iloc[0]
                        else:
                            recent_fcf = info.get('freeCashflow') or 0.0

                        shares_out_dcf = info.get('sharesOutstanding') or 0.0
                        total_debt_dcf = info.get('totalDebt') or 0.0
                        total_cash_dcf = info.get('totalCash') or 0.0

                        render_dcf_valuation_ui(
                            ticker=a_ticker,
                            recent_fcf=recent_fcf,
                            shares_outstanding=shares_out_dcf,
                            current_price=rt_price,
                            total_debt=total_debt_dcf,
                            total_cash=total_cash_dcf
                        )
                    except Exception as e:
                        st.error(f"Errore nel modulo DCF: {e}")

                # --- TAB 9: BUFFETT SCORECARD ---
                with tab_buffett:
                    render_buffett_scorecard_ui(a_ticker)
