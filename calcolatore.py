import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
from textblob import TextBlob

# --- Initial Configuration ---
st.set_page_config(page_title="Pro Financial Dashboard", layout="wide")

# --- Utility Functions ---
def format_large_numbers(value):
    if value is None or str(value) == 'nan' or value == 'N/A' or isinstance(value, str): return "N/A"
    prefix = ""
    if value < 0: value = abs(value); prefix = "-"
    if value >= 1_000_000_000_000: return f"{prefix}${value/1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000: return f"{prefix}${value/1_000_000_000:.2f}B"
    if value >= 1_000_000: return f"{prefix}${value/1_000_000:.2f}M"
    return f"{prefix}${value:,.2f}"

def format_perc(value):
    if value is None or str(value) == 'nan' or value == 'N/A': return "N/A"
    return f"{value * 100:.2f}%"

def get_sentiment(text):
    """Analizza il sentiment del testo e restituisce un'etichetta visuale."""
    score = TextBlob(text).sentiment.polarity
    if score > 0.1: return "🟢 Positive"
    elif score < -0.1: return "🔴 Negative"
    else: return "⚪ Neutral"

# --- CACHING FUNCTIONS (Per velocità e sicurezza API) ---
@st.cache_data(ttl=3600)
def fetch_stock_info(ticker):
    stock = yf.Ticker(ticker)
    return stock.info

@st.cache_data(ttl=3600)
def fetch_history(ticker, years):
    stock = yf.Ticker(ticker)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=years * 365)
    return stock.history(start=start_date, end=end_date)

@st.cache_data(ttl=3600)
def fetch_financials(ticker):
    stock = yf.Ticker(ticker)
    return stock.financials, stock.balance_sheet, stock.cashflow

@st.cache_data(ttl=3600)
def fetch_news(ticker):
    stock = yf.Ticker(ticker)
    return stock.news

@st.cache_data(ttl=86400)
def fetch_segments(ticker):
    """Scarica i ricavi per segmento da FMP senza nascondere gli errori."""
    if "FMP_KEY" not in st.secrets:
        return "ERRORE: FMP_KEY non trovata nei Secrets di Streamlit!"
    
    api_key = st.secrets["FMP_KEY"]
    url = f"https://financialmodelingprep.com/api/v3/revenue-product-segmentation?symbol={ticker}&apikey={api_key}"
    
    response = requests.get(url)
    
    # Restituiamo il vero testo della risposta, qualunque esso sia!
    try:
        return response.json()
    except:
        return response.text
    
    api_key = st.secrets["FMP_KEY"]
    # Endpoint per i segmenti di prodotto
    url = f"https://financialmodelingprep.com/api/v3/revenue-product-segmentation?symbol={ticker}&apikey={api_key}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

# --- SIDEBAR MENU ---
st.sidebar.title("🧭 Navigation")
page_choice = st.sidebar.radio("Tool:", ["📈 Compound Interest", "📊 Stock Tracker", "📰 Financial News"])
st.sidebar.divider()

drip_active = False
if page_choice == "📊 Stock Tracker":
    st.sidebar.subheader("Strategy Options")
    drip_active = st.sidebar.toggle("Reinvest Dividends (DRIP)", value=False)

# ==========================================
# PAGE 1: COMPOUND INTEREST
# ==========================================
if page_choice == "📈 Compound Interest":
    st.title("💸 Compound Interest Calculator")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        initial_cap = st.number_input("Initial Investment ($)", min_value=0.0, value=1000.0)
        rate = st.number_input("Annual Rate (%)", min_value=0.0, value=5.0)
    with col2:
        years = int(st.number_input("Years", min_value=1, value=10))
        freq = st.selectbox("Compounding Frequency", ["Annually", "Semi-annually", "Quarterly", "Monthly"])
        freq_map = {"Annually": 1, "Semi-annually": 2, "Quarterly": 4, "Monthly": 12}

    if st.button("🚀 Calculate", type="primary", use_container_width=True):
        data = []
        r_dec = rate / 100
        for y in range(years + 1):
            m = initial_cap * (1 + r_dec / freq_map[freq]) ** (freq_map[freq] * y)
            data.append({"Year": y, "Total Capital ($)": round(m, 2)})
        df = pd.DataFrame(data)
        st.success(f"**Final Total:** $ {df.iloc[-1]['Total Capital ($)']:,.2f}")
        st.plotly_chart(px.area(df, x="Year", y="Total Capital ($)", markers=True), use_container_width=True)

# ==========================================
# PAGE 2: STOCK TRACKER
# ==========================================
elif page_choice == "📊 Stock Tracker":
    st.title("📈 Fundamental Analysis & Performance")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1: ticker_input = st.text_input("Stock Ticker", value="KO").upper()
    with col2: invested_cap = st.number_input("Initial Investment ($)", min_value=100.0, value=1000.0)
    with col3: backtest_years = st.slider("Years of History", min_value=1, max_value=20, value=10)
    with col4: benchmark_ticker = st.text_input("Benchmark (Compare)", value="SPY").upper()

    # MEMORIA DI SESSIONE: Salviamo i parametri quando l'utente preme il bottone
    if st.button("🚀 Analyze Stock", type="primary", use_container_width=True):
        st.session_state['active_ticker'] = ticker_input
        st.session_state['active_cap'] = invested_cap
        st.session_state['active_years'] = backtest_years
        st.session_state['active_bench'] = benchmark_ticker

    # Eseguiamo il codice SOLO se c'è un ticker in memoria (così i toggle non resettano la pagina!)
    if 'active_ticker' in st.session_state:
        a_ticker = st.session_state['active_ticker']
        a_cap = st.session_state['active_cap']
        a_years = st.session_state['active_years']
        a_bench = st.session_state['active_bench']

        info = fetch_stock_info(a_ticker)
        stock = yf.Ticker(a_ticker) 
        
        if not info or ('regularMarketPrice' not in info and 'previousClose' not in info and 'currentPrice' not in info):
            st.error("Ticker not found.")
        else:
            st.markdown(f"### 🏢 {info.get('shortName', a_ticker)}")
            
            # --- TOP METRICS BAR ---
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Market Cap", format_large_numbers(info.get('marketCap')))
            m2.metric("P/E (Trailing)", round(info.get('trailingPE'), 2) if info.get('trailingPE') else 'N/A')
            m3.metric("EPS (TTM)", f"${info.get('trailingEps'):.2f}" if info.get('trailingEps') else 'N/A')
            m4.metric("Div Rate", f"${info.get('dividendRate'):.2f}" if info.get('dividendRate') else 'N/A')

            st.write("")
            m5, m6, m7, m8 = st.columns(4)
            m5.metric("Prev. Close", f"${info.get('previousClose', info.get('currentPrice', 'N/A'))}")
            m6.metric("P/E (Forward)", round(info.get('forwardPE'), 2) if info.get('forwardPE') else 'N/A')
            m7.metric("EPS (Forward)", f"${info.get('forwardEps'):.2f}" if info.get('forwardEps') else 'N/A')
            
            raw_yield = info.get('dividendYield')
            if raw_yield is not None:
                div_yield_str = f"{raw_yield:.2f}%" if raw_yield > 0.5 else f"{raw_yield * 100:.2f}%"
            else:
                div_yield_str = "N/A"
                
            m8.metric("Div Yield (FWD)", div_yield_str)
            st.divider() 

            # --- RECUPERO DATI STORICI VIA CACHE ---
            hist_data = fetch_history(a_ticker, a_years)
            
            if not hist_data.empty:
                shares_with_drip = a_cap / hist_data['Close'].iloc[0]
                shares_no_drip = shares_with_drip
                cash_no_drip = 0
                val_with_drip_series, val_no_drip_series, val_price_only_series = [], [], []
                div_history = []

                for i in range(len(hist_data)):
                    price = hist_data['Close'].iloc[i]
                    div = hist_data['Dividends'].iloc[i]
                    date = hist_data.index[i]
                    
                    div_incassato = div * (shares_with_drip if drip_active else shares_no_drip)
                    if div > 0:
                        div_history.append({"Date": date, "Amount": div_incassato})
                        if drip_active:
                            shares_with_drip += div_incassato / price
                        else:
                            cash_no_drip += div_incassato
                            
                    val_with_drip_series.append(shares_with_drip * price)
                    val_no_drip_series.append((shares_no_drip * price) + cash_no_drip)
                    val_price_only_series.append(shares_no_drip * price)

                hist_data['Chosen Value'] = val_with_drip_series if drip_active else val_no_drip_series

                # --- SISTEMA DI TAB ---
                tab_price, tab_divs, tab_mc, tab_holders, tab_funds = st.tabs([
                    "📊 Price & Tech Analysis", 
                    "💰 Dividends & Returns", 
                    "🎲 Projections", 
                    "🏦 Ownership", 
                    "📅 Fundamentals"
                ])

                # ==========================================
                # TAB 1: PRICE, BENCHMARK & CANDLESTICKS
                # ==========================================
                with tab_price:
                    col_t1, col_t2 = st.columns([3, 1])
                    with col_t1: st.subheader("Historical Performance")
                    with col_t2: chart_type = st.toggle("Mostra Analisi Tecnica (Candele)", value=False)
                    
                    if chart_type:
                        # GRAFICO A CANDELE CON VOLUMI E MEDIE MOBILI
                        fig_cand = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                        
                        # Candele
                        fig_cand.add_trace(go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name='Price'), row=1, col=1)
                        
                        # Medie Mobili (SMA 50 e 200)
                        sma50 = hist_data['Close'].rolling(window=50).mean()
                        sma200 = hist_data['Close'].rolling(window=200).mean()
                        fig_cand.add_trace(go.Scatter(x=hist_data.index, y=sma50, line=dict(color='orange', width=1.5), name='SMA 50'), row=1, col=1)
                        fig_cand.add_trace(go.Scatter(x=hist_data.index, y=sma200, line=dict(color='purple', width=1.5), name='SMA 200'), row=1, col=1)
                        
                        # Volumi
                        colors = ['#27AE60' if c >= o else '#E74C3C' for c, o in zip(hist_data['Close'], hist_data['Open'])]
                        fig_cand.add_trace(go.Bar(x=hist_data.index, y=hist_data['Volume'], marker_color=colors, name='Volume'), row=2, col=1)
                        
                        fig_cand.update_layout(xaxis_rangeslider_visible=False, height=600, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_cand, use_container_width=True)
                        
                    else:
                        # GRAFICO LINEARE STANDARD VS BENCHMARK
                        bench_raw = yf.download(a_bench, start=hist_data.index[0], end=hist_data.index[-1], progress=False)
                        if not bench_raw.empty:
                            bench_close = bench_raw['Close'].squeeze()
                            stock_close = hist_data['Close'].squeeze()
                            
                            norm_stock = (stock_close / stock_close.iloc[0]) * 100
                            norm_bench = (bench_close / bench_close.iloc[0]) * 100
                            
                            fig_comp = go.Figure()
                            fig_comp.add_trace(go.Scatter(x=norm_stock.index, y=norm_stock, name=a_ticker, line=dict(color='#2E86C1', width=2)))
                            fig_comp.add_trace(go.Scatter(x=norm_bench.index, y=norm_bench, name=a_bench, line=dict(color='#E74C3C', width=2)))
                            fig_comp.update_layout(yaxis_title="Value of 100$ Investment", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=0, r=0, t=30, b=0))
                            st.plotly_chart(fig_comp, use_container_width=True)
                        else:
                            st.warning("Dati benchmark non disponibili.")

                # ==========================================
                # TAB 2: DIVIDENDS & TOTAL RETURN
                # ==========================================
                with tab_divs:
                    st.subheader("Total Return & Dividend Compounding")
                    tot_ret_drip = (val_with_drip_series[-1] / a_cap) - 1
                    tot_ret_no_drip = (val_no_drip_series[-1] / a_cap) - 1
                    div_rate_val = info.get('dividendRate', 0) or 0
                    yoc_drip = (div_rate_val * shares_with_drip) / a_cap
                    yoc_no_drip = (div_rate_val * shares_no_drip) / a_cap

                    pm1, pm2 = st.columns(2)
                    pm1.metric("Total Return (with DRIP)", format_perc(tot_ret_drip))
                    pm1.metric("Yield on Cost (with DRIP)", format_perc(yoc_drip))
                    pm2.metric("Total Return (w/o DRIP)", format_perc(tot_ret_no_drip))
                    pm2.metric("Yield on Cost (w/o DRIP)", format_perc(yoc_no_drip))
                    
                    fig_perf = go.Figure()
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=hist_data['Chosen Value'], name='Total Return Value', fill='tozeroy', line=dict(color='#27AE60')))
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

                # ==========================================
                # TAB 3: PROJECTIONS (MONTE CARLO)
                # ==========================================
                with tab_mc:
                    st.subheader("🎲 Monte Carlo Simulation (5Y Projection)")
                    st.write("Simulazione basata sul Geometric Brownian Motion (GBM).")
                    
                    log_returns = np.log(1 + hist_data['Close'].pct_change().dropna())
                    mu, sigma = log_returns.mean(), log_returns.std()
                    
                    sim_days, num_sim = 252 * 5, 100
                    last_price = hist_data['Close'].iloc[-1]
                    last_date = hist_data.index[-1]
                    
                    daily_sim_returns = np.exp(np.random.normal(mu - 0.5 * sigma**2, sigma, (sim_days, num_sim)))
                    sims = np.zeros_like(daily_sim_returns)
                    sims[0] = last_price
                    for t in range(1, sim_days):
                        sims[t] = sims[t-1] * daily_sim_returns[t]
                        
                    future_dates = pd.date_range(start=last_date, periods=sim_days, freq='B')
                    
                    fig_mc = go.Figure()
                    for i in range(num_sim):
                        fig_mc.add_trace(go.Scatter(x=future_dates, y=sims[:, i], mode='lines', line=dict(width=1, color='rgba(46, 134, 193, 0.05)'), showlegend=False, hoverinfo='skip'))
                    fig_mc.add_trace(go.Scatter(x=future_dates, y=sims.mean(axis=1), mode='lines', name='Expected Average', line=dict(width=3, color='#E74C3C')))
                    
                    fig_mc.update_layout(xaxis_title="Date", yaxis_title="Projected Price ($)", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_mc, use_container_width=True)

                # ==========================================
                # TAB 4: OWNERSHIP
                # ==========================================
                with tab_holders:
                    st.subheader("Major Shareholders")
                    col_h1, col_h2 = st.columns(2)
                    
                    with col_h1:
                        st.write("**Share Ownership Breakdown**")
                        holders = stock.major_holders
                        if holders is not None and not holders.empty:
                            holders_df = holders.copy()
                            val_col = holders_df.columns[0]
                            holders_df[val_col] = (pd.to_numeric(holders_df[val_col], errors='coerce') * 100).map("{:.2f}%".format)
                            st.dataframe(holders_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Ownership data not available.")
                    
                    with col_h2:
                        st.write("**Top Institutional Holders**")
                        inst_holders = stock.institutional_holders
                        if inst_holders is not None and not inst_holders.empty:
                            inst_df = inst_holders.copy()
                            for col in ['pctHeld', '% Out']:
                                if col in inst_df.columns:
                                    inst_df[col] = (pd.to_numeric(inst_df[col], errors='coerce') * 100).map("{:.2f}%".format)
                            st.dataframe(inst_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Institutional data not available.")

                # ==========================================
                # TAB 5: EARNINGS E FULL FINANCIALS
                # ==========================================
                with tab_funds:
                    st.subheader("📅 Upcoming Earnings & Estimates")
                    # Abbiamo reinserito la tabella degli Earnings!
                    earn_data = stock.earnings_dates
                    if earn_data is not None:
                        st.dataframe(earn_data, use_container_width=True)
                    else:
                        st.info("Upcoming earnings dates not available.")

                    st.divider()
                    st.subheader("🧩 Revenue by Segment (Business Segments)")
                    
                    segment_data = fetch_segments(a_ticker)

                    st.warning(segment_data)
                    
                    if segment_data and isinstance(segment_data, list) and len(segment_data) > 0:
                        # Estraiamo l'anno più recente
                        latest_data = segment_data[0]
                        date_str = latest_data.pop("date", "Latest")
                        
                        # Rimuoviamo eventuali chiavi vuote o non numeriche
                        clean_data = {k: v for k, v in latest_data.items() if isinstance(v, (int, float)) and v > 0}
                        
                        if clean_data:
                            # Prepariamo i dati per il grafico a torta
                            df_seg = pd.DataFrame(list(clean_data.items()), columns=['Segment', 'Revenue'])
                            
                            col_s1, col_s2 = st.columns([1, 1])
                            with col_s1:
                                fig_pie = px.pie(df_seg, values='Revenue', names='Segment', hole=0.4, 
                                                 title=f"Segment Breakdown ({date_str[:4]})",
                                                 color_discrete_sequence=px.colors.qualitative.Pastel)
                                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                                fig_pie.update_layout(showlegend=False, margin=dict(t=30, b=0, l=0, r=0))
                                st.plotly_chart(fig_pie, use_container_width=True)
                            
                            with col_s2:
                                st.write("**Detailed Revenue (Latest Year)**")
                                # Formattiamo i numeri per renderli leggibili
                                df_seg['Revenue'] = df_seg['Revenue'].apply(format_large_numbers)
                                st.dataframe(df_seg, use_container_width=True, hide_index=True)
                        else:
                            st.info("I dati sui segmenti non contengono valori numerici validi per questo ticker.")
                    else:
                        st.info("Dati sui segmenti di business non disponibili per questo ticker o limite API raggiunto.")
                    st.divider()
                    
                    st.subheader("Financial Highlights")
                    h1, h2, h3 = st.columns(3)
                    with h1:
                        st.write("**Profitability**")
                        st.metric("Profit Margin", format_perc(info.get('profitMargins')))
                        st.metric("ROE (ttm)", format_perc(info.get('returnOnEquity')))
                    with h2:
                        st.write("**Balance Sheet**")
                        st.metric("Total Cash", format_large_numbers(info.get('totalCash')))
                        st.metric("Debt/Equity", info.get('debtToEquity', 'N/A'))
                    with h3:
                        st.write("**Cash Flow**")
                        st.metric("Free Cash Flow", format_large_numbers(info.get('leveredFreeCashFlow')))
                        
                    st.divider()
                    st.subheader("📑 Full Financial Statements (Annual)")
                    
                    # Recupero dati di bilancio completi
                    inc_stmt, bal_sheet, cash_flow = fetch_financials(a_ticker)
                    
                    # Funzione per formattare DataFrames finanziari
                    def format_fin_df(df):
                        if df is None or df.empty: 
                            return df
                        # Creiamo una copia per non alterare i dati nella cache di Streamlit
                        df_fmt = df.copy()
                        # Formattiamo le date delle colonne (es. da '2023-12-31 00:00:00' a '2023-12-31')
                        df_fmt.columns = [c.strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c) for c in df_fmt.columns]
                        # Applichiamo la conversione in B/M/T a ogni singola cella
                        for col in df_fmt.columns:
                            df_fmt[col] = df_fmt[col].apply(format_large_numbers)
                        return df_fmt

                    # Applichiamo la formattazione
                    inc_stmt_fmt = format_fin_df(inc_stmt)
                    bal_sheet_fmt = format_fin_df(bal_sheet)
                    cash_flow_fmt = format_fin_df(cash_flow)
                    
                    sub_t1, sub_t2, sub_t3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
                    with sub_t1: 
                        if not inc_stmt_fmt.empty: st.dataframe(inc_stmt_fmt, use_container_width=True)
                        else: st.info("Dati non disponibili.")
                    with sub_t2: 
                        if not bal_sheet_fmt.empty: st.dataframe(bal_sheet_fmt, use_container_width=True)
                        else: st.info("Dati non disponibili.")
                    with sub_t3: 
                        if not cash_flow_fmt.empty: st.dataframe(cash_flow_fmt, use_container_width=True)
                        else: st.info("Dati non disponibili.")

# ==========================================
# PAGE 3: FINANCIAL NEWS (CON AI SENTIMENT)
# ==========================================
elif page_choice == "📰 Financial News":
    st.title("📰 Financial News Feed")
    st.write("Stay up-to-date with the latest market news and **AI-powered sentiment analysis**.")
    st.divider()
    
    col_news, _ = st.columns([1, 2])
    with col_news:
        ticker_news = st.text_input("Enter Ticker (e.g., AAPL, MSFT, TSLA)", value="AAPL").upper()
    
    if st.button("Search News", type="primary"):
        with st.spinner("Fetching latest news and analyzing sentiment..."):
            news_items = fetch_news(ticker_news)
            
            if news_items:
                for item in news_items:
                    if 'content' in item:
                        news_data = item['content']
                        title = news_data.get('title', 'No Title')
                        
                        provider_dict = news_data.get('provider') or {}
                        publisher = provider_dict.get('displayName', 'Unknown Source')
                        
                        url_dict = news_data.get('clickThroughUrl') or news_data.get('canonicalUrl') or {}
                        link = url_dict.get('url', f"https://finance.yahoo.com/quote/{ticker_news}/news")
                        
                        pub_date_str = news_data.get('pubDate', '')
                        if pub_date_str:
                            try:
                                pub_date = pd.to_datetime(pub_date_str).strftime('%d %b %Y - %H:%M')
                            except:
                                pub_date = pub_date_str[:10]
                        else:
                            pub_date = "Date not available"
                    
                    else:
                        title = item.get('title', 'No Title')
                        publisher = item.get('publisher', 'Unknown Source')
                        link = item.get('link', f"https://finance.yahoo.com/quote/{ticker_news}/news")
                        
                        timestamp = item.get('providerPublishTime', 0)
                        if timestamp > 0:
                            pub_date = datetime.fromtimestamp(timestamp).strftime('%d %b %Y - %H:%M')
                        else:
                            pub_date = "Date not available"
                    
                    if title != 'No Title':
                        # AI Sentiment Analysis applicato al titolo della notizia
                        sentiment_label = get_sentiment(title)
                        
                        with st.container():
                            st.subheader(title)
                            st.caption(f"✍️ **Source:** {publisher} | 🕒 **Published:** {pub_date} | 🧠 **AI Sentiment:** {sentiment_label}")
                            st.markdown(f"[🔗 Read the full article on {publisher}]({link})")
                            st.divider()
            else:
                st.warning(f"No recent news found for ticker {ticker_news}.")
