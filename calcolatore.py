import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta
import requests
from scipy.optimize import minimize
from fpdf import FPDF
import io

# --- CONFIGURAZIONE ISTITUZIONALE ---
st.set_page_config(page_title="PRO Quant Dashboard", layout="wide", initial_sidebar_state="expanded")

# Custom CSS per look "Bloomberg Terminal"
st.markdown("""
    <style>
    [data-testid="stMetric"] { background-color: var(--secondary-background-color); padding: 10px; border-radius: 5px; border: 1px solid rgba(128, 128, 128, 0.2); }
    </style>
    """, unsafe_allow_html=True)

import json
import os

PORTFOLIO_FILE = 'portfolio.json'

def load_portfolio():
    if os.path.exists(PORTFOLIO_FILE):
        try:
            with open(PORTFOLIO_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_portfolio(p_list):
    try:
        with open(PORTFOLIO_FILE, 'w') as f:
            json.dump(p_list, f)
    except Exception:
        pass

if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = load_portfolio()

# --- UTILITY QUANTITATIVE E FORMATTAZIONE ---
def format_large_numbers(value, is_currency=True):
    if value is None or str(value) == 'nan' or value == 'N/A' or isinstance(value, str): return "N/A"
    prefix = ""
    if value < 0: value = abs(value); prefix = "-"
    c = "$" if is_currency else ""
    if value >= 1_000_000_000_000: return f"{prefix}{c}{value/1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000: return f"{prefix}{c}{value/1_000_000_000:.2f}B"
    if value >= 1_000_000: return f"{prefix}{c}{value/1_000_000:.2f}M"
    return f"{prefix}{c}{value:,.2f}"

def format_perc(value):
    if value is None or str(value) == 'nan' or value == 'N/A': return "N/A"
    return f"{value * 100:.2f}%"

def calc_cagr(start_val, end_val, years):
    """Calcola il Compound Annual Growth Rate."""
    if start_val <= 0 or years <= 0: return 0
    return (end_val / start_val) ** (1 / years) - 1

def calc_risk_metrics(returns, rf_rate=0.02):
    """
    Calcola Sharpe Ratio e Max Drawdown.
    Ratio: Rendimento in eccesso per unità di rischio.
    """
    if returns.empty: return 0.0, 0.0
    
    # Annualizzazione (252 giorni di trading)
    adj_returns = returns.dropna()
    mean_ret = adj_returns.mean() * 252
    vol = adj_returns.std() * np.sqrt(252)
    
    sharpe = (mean_ret - rf_rate) / vol if vol > 0 else 0.0
    
    # Max Drawdown
    cum_ret = (1 + adj_returns).cumprod()
    peak = cum_ret.cummax()
    drawdown = (cum_ret - peak) / peak
    max_dd = drawdown.min()
    
    return sharpe, max_dd

# --- FUNZIONI AI OLLAMA (LOCALE) ---
def get_sentiment(text):
    """
    Analizza il sentiment passando il testo al modello Gemma tramite Ollama in locale.
    """
    url = "http://localhost:11434/api/generate"
    
    prompt = f"""Sei un esperto analista finanziario. Analizza il sentiment di questo titolo di news. 
    Rispondi SOLO ed ESCLUSIVAMENTE con una di queste tre opzioni esatte: '🟢 Positive', '🔴 Negative', o '⚪ Neutral'.
    Non aggiungere spiegazioni, punteggiatura extra o altre parole.
    
    Titolo: '{text}'
    Risposta:"""

    payload = {
        "model": "gemma:2b", 
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.0 
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status() 
        result = response.json().get('response', '').strip()
        
        if "Positive" in result or "🟢" in result: 
            return "🟢 Positive"
        elif "Negative" in result or "🔴" in result: 
            return "🔴 Negative"
        else: 
            return "⚪ Neutral"
            
    except requests.exceptions.RequestException:
        return "⚪ Neutral (Ollama Offline)"

def analyze_portfolio_diversification(portfolio_df, total_value):
    """Fa analizzare a Gemma la diversificazione del portafoglio."""
    assets_text = ""
    for index, row in portfolio_df.iterrows():
        ticker = row['Ticker']
        peso_perc = (row['Valore Totale ($)'] / total_value) * 100
        assets_text += f"- {ticker}: {peso_perc:.2f}%\n"
        
    prompt = f"""Agisci come un consulente finanziario esperto in gestione del rischio. 
    Analizza la seguente allocazione di portafoglio di un investitore:
    
    {assets_text}
    
    Scrivi un commento professionale (massimo 4-5 frasi) valutando la diversificazione. 
    Rispondi a queste domande: È un portafoglio equilibrato? C'è un rischio di sovraesposizione su un singolo titolo o settore? Qual è il tuo consiglio per bilanciare il rischio?
    Rispondi in italiano in modo chiaro e diretto.
    """
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate", 
            json={
                "model": "gemma:2b", 
                "prompt": prompt, 
                "stream": False
            },
            timeout=25
        )
        
        if response.status_code == 200:
            return response.json()['response'].strip()
        else:
            return "Errore nella generazione dell'analisi."
    except Exception:
        return "Errore di connessione con Ollama. Assicurati che l'app locale sia accesa."

def analyze_financial_statements_ai(ticker, inc_stmt, bal_sheet, cash_flow):
    """Analisi accurata dei bilanci annuali tramite Gemma."""
    def simplify_df(df, name):
        if df is None or df.empty: return f"{name}: Dati non disponibili"
        # Prime 15 metriche, ultimi 2 anni per stare nel context window del modello locale
        df_compact = df.iloc[:15, :2].copy()
        for col in df_compact.columns:
            df_compact[col] = pd.to_numeric(df_compact[col], errors='coerce').apply(
                lambda x: f"${x/1e9:.2f}B" if pd.notna(x) and abs(x) >= 1e8 else str(x)
            )
        return f"--- {name} ---\n" + df_compact.to_string()

    data_str = simplify_df(inc_stmt, "INCOME STATEMENT") + "\n" + \
               simplify_df(bal_sheet, "BALANCE SHEET") + "\n" + \
               simplify_df(cash_flow, "CASH FLOW")

    prompt = f"""Sei un analista finanziario di una prestigiosa banca d'investimento. Analizza i seguenti estratti dei rendiconti di {ticker} (ultimi 2 anni).
    
DATI FINANZIARI:
{data_str}
    
REGOLE TASSATIVE:
- Usa solo un italiano nativo, formale, accademico e perfetto. Non tradurre testualmente dall'inglese.
- Sviluppa argomentazioni corpose: il report deve tassativamente contenere almeno 200 parole di approfondimento critico.
- Non fare la semplice "telecronaca" dei numeri, ma valuta criticamente la direzione dell'azienda.
- Usa termini tecnici (es. margini di profitto, deleveraging, liquidità corrente).

STRUTTURA OBBLIGATORIA DEL REPORT:
1. SOLIDITÀ PATRIMONIALE: Valuta il bilanciamento tra asset e debiti totali.
2. REDDITIVITÀ OPERATIVA: Analizza la forza dei ricavi e l'esito dell'utile netto.
3. DINAMICHE DI CASSA: Giudica la capacità dell'azienda di generare o bruciare Free Cash Flow.
4. VERDETTO FINALE: Esprimi in una frase se l'azienda è solida, in miglioramento o a rischio strutturale.
"""
    try:
        response = requests.post(
            "http://localhost:11434/api/generate", 
            json={
                "model": "gemma:2b", 
                "prompt": prompt, 
                "stream": False,
                "options": {
                    "temperature": 0.25,
                    "top_p": 0.8
                }
            },
            timeout=40
        )
        if response.status_code == 200:
            return response.json()['response'].strip()
        else:
            return "Errore nella generazione dell'analisi."
    except Exception:
        return "Errore di connessione con Ollama. L'intelligenza artificiale locale non risponde."

def ask_financial_chatbot(question, news_context):
    prompt = f"""Sei un assistente finanziario intelligente integrato nella PRO Quant Dashboard. 
Usa ESCLUSIVAMENTE le seguenti notizie recenti per rispondere alla domanda dell'investitore. Non inventare dati.
Se la risposta non è nelle notizie, di' che non hai informazioni sufficienti. Rispondi in italiano in modo formale.

CONTESTO DELLE NEWS RECENTI:
{news_context}

DOMANDA DELL'INVESTITORE:
{question}
"""
    try:
        response = requests.post("http://localhost:11434/api/generate", json={"model": "gemma:2b", "prompt": prompt, "stream": False, "options": {"temperature": 0.2}}, timeout=30)
        if response.status_code == 200: return response.json()['response'].strip()
        else: return "Errore nella generazione."
    except Exception: return "Errore di connessione con Ollama."

def generate_pdf_report(ticker, rt_price, info, sharpe, max_dd):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Institutional Tear Sheet: {ticker}", ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    name = info.get('shortName', ticker)
    pdf.cell(0, 10, f"Company: {name.encode('latin-1', 'replace').decode('latin-1')}", ln=True)
    pdf.cell(0, 10, f"Current Price: ${rt_price:,.2f}", ln=True)
    pdf.cell(0, 10, f"P/E Rating (Trailing): {info.get('trailingPE', 'N/A')}", ln=True)
    pdf.cell(0, 10, "", ln=True)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "Risk & Performance Metrics", ln=True)
    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, f"Sharpe Ratio: {sharpe:.2f}", ln=True)
    pdf.cell(0, 10, f"Max Drawdown: {max_dd*100:.2f}%", ln=True)
    return bytes(pdf.output())

# --- DATA ENGINE (WITH CACHING) ---
@st.cache_data(ttl=3600)
def get_batch_prices(tickers):
    """Recupera i prezzi correnti per una lista di ticker in un'unica chiamata per efficienza portafogli."""
    if not tickers: return {}
    data = yf.download(tickers, period="1d", progress=False)
    
    if data.empty:
        return {}
        
    if 'Close' in data:
        data = data['Close']
        
    if isinstance(data, pd.Series): 
        # Se c'è un solo ticker, le colonne non ci sono più
        return {tickers[0]: data.iloc[-1]}
        
    # Se ci sono più ticker, costruiamo il dizionario
    return data.iloc[-1].to_dict()

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


# --- SIDEBAR MENU ---
st.sidebar.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;700&display=swap');
.sidebar-logo {
    font-family: 'Outfit', sans-serif;
    font-size: 26px;
    margin-top: -60px; /* Sposta il logo più in alto */
    margin-bottom: 20px;
    line-height: 1.15;
    pointer-events: none; /* Impedisce che il logo blocchi il tasto Chiudi Sidebar della UI di Streamlit */
}
.sidebar-logo .intelligent {
    font-weight: 300;
}
.sidebar-logo .finance {
    font-weight: 700;
}
/* Stile base delle schede di navigazione */
[data-testid="stSidebar"] [data-baseweb="radio"] {
    padding: 10px 14px;
    margin-bottom: 6px;
    border-radius: 4px;
    transition: background-color 0.2s;
    position: relative;
    cursor: pointer;
}

/* Nascondi i cerchi nativi di Streamlit per un look piatto da menu a tendina */
[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
    display: none !important;
}

/* Hover pulito per i bottoni in Dark Mode */
[data-testid="stSidebar"] [data-baseweb="radio"]:hover {
    background-color: rgba(255, 255, 255, 0.05);
}

/* Elemento attivo: Arancione Seeking Alpha */
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    background-color: rgba(242, 114, 0, 0.1) !important;
    border-left: 4px solid #f27200;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
    color: #f27200;
    font-weight: 700;
}

/* Spazio extra per far respirare i titoli */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1) { margin-top: 40px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(3) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6) { margin-top: 55px; } /* Stacco lungo per linea divisoria Macro */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7) { margin-top: 35px; }

/* Formattazione Testo Titoli INIETTATI (non interagibili) */
[data-testid="stSidebar"] div[role="radiogroup"] > label::before {
    position: absolute;
    top: -26px;
    left: 2px;
    font-size: 11px;
    font-weight: 800;
    color: #7b8084;
    letter-spacing: 0.8px;
    pointer-events: none; /* Rende il titolo insensibile al mouse! */
    text-transform: uppercase;
}

/* Testi specifici dei titoli decorativi e linea separatrice */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1)::before { content: '🧮 Calculator'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2)::before { content: '📉 Analytics'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(3)::before { content: '💼 Management'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4)::before { content: '📰 Insights'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5)::before { content: '👑 Hedge Funds'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6)::before { 
    content: '';
    height: 1px;
    background-color: rgba(255, 255, 255, 0.2);
    top: -28px;
    left: -15px;
    right: -65px;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7)::before { content: '🔍 Discovery'; }
</style>
<div class="sidebar-logo">
    <span class="intelligent">The Intelligent</span><br>
    <span class="finance">Finance</span>
</div>
""", unsafe_allow_html=True)
page_choice = st.sidebar.radio("Tool:", [
    "📈 Compound Interest", 
    "📊 Stock Tracker", 
    "📁 My Portfolio", 
    "📰 Financial News", 
    "👑 Super Investors", 
    "🌍 Macro & Market", 
    "🔍 Stock Screener"
], label_visibility="collapsed")


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
    st.title("📊 Institutional Equity Analysis")
    st.divider()

    col1, col2, col3, col4 = st.columns(4)
    with col1: ticker_input = st.text_input("Stock Ticker", value="KO").upper()
    with col2: invested_cap = st.number_input("Initial Investment ($)", min_value=100.0, value=1000.0)
    with col3: backtest_years = st.slider("Years of History", min_value=1, max_value=20, value=10)
    with col4: benchmark_ticker = st.text_input("Benchmark (Compare)", value="SPY").upper()

    # Salviamo i parametri in sessione per non perderli al ricarico della pagina (es. al toggle DRIP)
    if st.button("🚀 Run Deep Analysis", type="primary", use_container_width=True):
        st.session_state['active_ticker'] = ticker_input
        st.session_state['active_cap'] = invested_cap
        st.session_state['active_years'] = backtest_years
        st.session_state['active_bench'] = benchmark_ticker

    if 'active_ticker' in st.session_state:
        a_ticker = st.session_state['active_ticker']
        a_cap = st.session_state['active_cap']
        a_years = st.session_state['active_years']
        a_bench = st.session_state['active_bench']

        with st.spinner("Caricamento in corso..."):
            info = fetch_stock_info(a_ticker)
            hist_data = fetch_history(a_ticker, a_years)
            stock = yf.Ticker(a_ticker) 
            
            if hist_data.empty:
                st.error("Dati non disponibili o Ticker non trovato.")
            else:
                st.markdown(f"### 🏢 {info.get('shortName', a_ticker)}")
                
                # --- TOP METRICS BAR (REAL-TIME) ---
                # Bypasso la cache per ottenere il prezzo realmente vivo dal mercato
                rt_hist = stock.history(period="1d")
                rt_price = rt_hist['Close'].iloc[-1] if not rt_hist.empty else info.get('currentPrice', hist_data['Close'].iloc[-1])
                
                prev_close = info.get('previousClose', hist_data['Close'].iloc[-2] if len(hist_data) > 1 else rt_price)
                if prev_close > 0:
                    change = ((rt_price - prev_close) / prev_close) * 100
                else: 
                    change = 0
                
                # Se vogliamo una Market Cap viva al 100%, dobbiamo moltiplicare il prezzo attuale vivo per le azioni correnti:
                shares_out = info.get('sharesOutstanding')
                if shares_out and shares_out > 0:
                    rt_mcap = rt_price * shares_out
                else:
                    rt_mcap = info.get('marketCap', 0)
                
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Market Cap", format_large_numbers(rt_mcap))
                m2.metric("P/E (Trailing)", round(info.get('trailingPE'), 2) if info.get('trailingPE') else 'N/A')
                m3.metric("EPS (TTM)", f"${info.get('trailingEps'):.2f}" if info.get('trailingEps') else 'N/A')
                m4.metric("Div Rate", f"${info.get('dividendRate'):.2f}" if info.get('dividendRate') else 'N/A')

                st.write("")
                m5, m6, m7, m8 = st.columns(4)
                m5.metric("Current Price", f"${rt_price:,.2f}", f"{change:.2f}%")
                m6.metric("P/E (Forward)", round(info.get('forwardPE'), 2) if info.get('forwardPE') else 'N/A')
                m7.metric("EPS (Forward)", f"${info.get('forwardEps'):.2f}" if info.get('forwardEps') else 'N/A')
                
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
                drip_active = st.session_state.get('drip_active', False)
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
                # Scarica report istituzionale
                st.divider()
                with st.expander("📄 Genera Report PDF (Tear Sheet)"):
                    pdf_bytes = generate_pdf_report(a_ticker, rt_price, info, sharpe, max_dd)
                    st.download_button(
                        label="Scarica PDF Tear Sheet",
                        data=pdf_bytes,
                        file_name=f"{a_ticker}_TearSheet.pdf",
                        mime="application/pdf"
                    )

                tab_price, tab_divs, tab_mc, tab_holders, tab_funds, tab_dcf = st.tabs([
                    "📊 Price & Tech Analysis", 
                    "💰 Dividends & Returns", 
                    "🎲 Projections", 
                    "🏦 Ownership", 
                    "📅 Fundamentals",
                    "🧮 DCF Valuation"
                ])

                # --- TAB 1: PRICE & TECH ---
                with tab_price:
                    col_t1, col_t2 = st.columns([3, 1])
                    with col_t1: st.subheader("Historical Performance")
                    with col_t2: chart_type = st.toggle("Mostra Analisi Tecnica (Candele)", value=False)
                    
                    if chart_type:
                        fig_cand = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                        
                        # Candele
                        fig_cand.add_trace(go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name='Price'), row=1, col=1)
                        # Medie Mobili
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
                        bench_raw = yf.download(a_bench, start=hist_data.index[0], end=hist_data.index[-1], progress=False)
                        if not bench_raw.empty:
                            if 'Close' in bench_raw.columns:
                                bench_close = bench_raw['Close'].squeeze()
                            else: bench_close = bench_raw.squeeze() # Se non usa multistrato
                            
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

                # --- TAB 2: DIVIDENDS ---
                with tab_divs:
                    col_tot, col_tog = st.columns([0.65, 0.35])
                    col_tot.subheader("Total Return & Dividend Compounding")
                    col_tog.write("") # Spacer 
                    col_tog.toggle("Reinvest Dividends (DRIP)", key="drip_active")
                    
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

                # --- TAB 3: PROJECTIONS ---
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
                        
                    future_dates = pd.date_range(start=last_date, periods=sim_days, freq='B')
                    
                    fig_mc = go.Figure()
                    for i in range(num_sim):
                        fig_mc.add_trace(go.Scatter(x=future_dates, y=sims[:, i], mode='lines', line=dict(width=1, color='rgba(46, 134, 193, 0.05)'), showlegend=False, hoverinfo='skip'))
                    fig_mc.add_trace(go.Scatter(x=future_dates, y=sims.mean(axis=1), mode='lines', name='Expected Average', line=dict(width=3, color='#E74C3C')))
                    
                    fig_mc.update_layout(xaxis_title="Date", yaxis_title="Projected Price ($)", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_mc, use_container_width=True)

                # --- TAB 4: OWNERSHIP ---
                with tab_holders:
                    st.subheader("Major Shareholders")
                    col_h1, col_h2 = st.columns(2)
                    
                    with col_h1:
                        st.write("**Share Ownership Breakdown**")
                        holders = stock.major_holders
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
                                    if pd.isna(val): return row['Valore']
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
                        inst_holders = stock.institutional_holders
                        if inst_holders is not None and not inst_holders.empty:
                            inst_df = inst_holders.copy()
                            
                            inst_df.rename(columns={'pctHeld': '% Held', 'pctChange': '% Change'}, inplace=True)
                            
                            for col in ['% Held', '% Out', '% Change']:
                                if col in inst_df.columns:
                                    inst_df[col] = (pd.to_numeric(inst_df[col], errors='coerce') * 100).map("{:.2f}%".format)
                            if 'Shares' in inst_df.columns:
                                inst_df['Shares'] = pd.to_numeric(inst_df['Shares'], errors='coerce').apply(lambda x: format_large_numbers(x, is_currency=False))
                            if 'Value' in inst_df.columns:
                                inst_df['Value'] = pd.to_numeric(inst_df['Value'], errors='coerce').apply(format_large_numbers)
                            st.dataframe(inst_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Institutional data not available.")

                # --- TAB 5: EARNINGS & FUNDS ---
                with tab_funds:
                    st.subheader("📅 Upcoming Earnings & Estimates")
                    earn_data = stock.earnings_dates
                    if earn_data is not None:
                        st.dataframe(earn_data, use_container_width=True)
                    else:
                        st.info("Upcoming earnings dates not available.")
                        
                    st.divider()
                    
                    st.subheader("Financial Highlights")
                    h1, h2, h3 = st.columns(3)
                    with h1:
                        st.metric("Profit Margin", format_perc(info.get('profitMargins')))
                        st.metric("ROE (ttm)", format_perc(info.get('returnOnEquity')))
                    with h2:
                        st.metric("Total Cash", format_large_numbers(info.get('totalCash')))
                        st.metric("Debt/Equity", info.get('debtToEquity', 'N/A'))
                    with h3:
                        st.metric("Free Cash Flow", format_large_numbers(info.get('leveredFreeCashFlow')))
                        
                    st.divider()
                    st.subheader("📑 Full Financial Statements (Annual)")
                    
                    inc_stmt, bal_sheet, cash_flow = fetch_financials(a_ticker)
                    
                    def format_fin_df(df):
                        if df is None or df.empty: return df
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
                        if not inc_stmt_fmt.empty: st.dataframe(inc_stmt_fmt, use_container_width=True)
                        else: st.info("Dati non disponibili.")
                    with sub_t2: 
                        if not bal_sheet_fmt.empty: st.dataframe(bal_sheet_fmt, use_container_width=True)
                        else: st.info("Dati non disponibili.")
                    with sub_t3: 
                        if not cash_flow_fmt.empty: st.dataframe(cash_flow_fmt, use_container_width=True)
                        else: st.info("Dati non disponibili.")

                    st.divider()
                    st.subheader("🤖 AI Financial Analysis")
                    st.write(f"Sfrutta l'intelligenza artificiale locale di Gemma per analizzare i bilanci di **{a_ticker}** e ottenerne una valutazione della solidità.")
                    if st.button("⚖️ Genera Report Fondamentale", type="secondary"):
                        with st.spinner(f"Gemma sta scansionando i rendiconti annuali di {a_ticker} per elaborare un'analisi..."):
                            ai_report = analyze_financial_statements_ai(a_ticker, inc_stmt, bal_sheet, cash_flow)
                            st.info(ai_report)


                # --- TAB 6: DCF VALUATION ---
                with tab_dcf:
                    st.subheader("🧮 Valutazione Fair Value (DCF Model)")
                    st.write("Calcolo a flussi di cassa scontati (Discounted Cash Flow).")
                    try:
                        inc_stmt_dcf, bal_sheet_dcf, cash_flow_dcf = fetch_financials(a_ticker)
                        if not cash_flow_dcf.empty and 'Free Cash Flow' in cash_flow_dcf.index:
                            recent_fcf = cash_flow_dcf.loc['Free Cash Flow'].dropna().iloc[0]
                        else:
                            recent_fcf = info.get('freeCashflow')
                            
                        shares_out_dcf = info.get('sharesOutstanding')
                        
                        if recent_fcf and shares_out_dcf and shares_out_dcf > 0:
                            dcf_col1, dcf_col2 = st.columns(2)
                            with dcf_col1:
                                fcf_growth_rate = st.number_input("Tasso Crescita FCF (Anni 1-5) %", value=8.0) / 100
                                discount_rate = st.number_input("Tasso di Sconto (WACC) %", value=10.0) / 100
                            with dcf_col2:
                                terminal_growth = st.number_input("Tasso Crescita Terminale %", value=2.5) / 100
                            
                            pv_fcf = sum([recent_fcf * (1 + fcf_growth_rate)**t / (1 + discount_rate)**t for t in range(1, 6)])
                            fcf_year_5 = recent_fcf * (1 + fcf_growth_rate)**5
                            tv = (fcf_year_5 * (1 + terminal_growth)) / (discount_rate - terminal_growth)
                            pv_tv = tv / (1 + discount_rate)**5
                            
                            enterprise_value = pv_fcf + pv_tv
                            total_debt = info.get('totalDebt', 0)
                            total_cash = info.get('totalCash', 0)
                            net_debt = total_debt - total_cash
                            equity_value = enterprise_value - net_debt
                            
                            fair_value = equity_value / shares_out_dcf
                            
                            st.metric("Fair Value per Azione Stimato", f"${fair_value:,.2f}")
                            margin_of_safety = ((fair_value - rt_price) / fair_value) if fair_value > 0 else 0
                            st.metric("Margine di Sicurezza", f"{margin_of_safety*100:.2f}%")
                            
                            if margin_of_safety > 0:
                                st.success("🟢 Il titolo sembra istituzionalmente **SOTTOVALUTATO** rispetto al Fair Value.")
                            else:
                                st.error("🔴 Il titolo sembra istituzionalmente **SOPRAVVALUTATO** rispetto al Fair Value.")
                        else:
                            st.info("Dati di cassa non sufficienti per il modello DCF.")
                    except Exception as e:
                        st.error("Errore nel calcolo DCF: " + str(e))

# ==========================================
# PAGE 3: MY PORTFOLIO
# ==========================================
elif page_choice == "📁 My Portfolio":
    st.title("📁 Institutional Portfolio Manager")
    st.write("Gestisci le tue posizioni e visualizza la diversificazione del tuo capitale.")
    st.divider()

    # --- INPUT PER AGGIUNGERE TITOLI ---
    with st.expander("➕ Aggiungi Nuova Posizione", expanded=False):
        c1, c2, c3 = st.columns(3)
        new_ticker = c1.text_input("Ticker (es. AAPL)").upper()
        new_shares = c2.number_input("Quantità (Azioni/Quote)", min_value=0.0, step=0.1)
        if c3.button("Aggiungi al Book") and new_ticker:
            try:
                check_df = yf.Ticker(new_ticker).history(period="1d")
                if check_df.empty:
                    st.error("Ticker non valido. Riprova.")
                else:
                    st.session_state['portfolio'].append({"ticker": new_ticker, "shares": new_shares})
                    save_portfolio(st.session_state['portfolio'])
                    st.toast(f"{new_ticker} aggiunto con successo!", icon="✅")
                    st.rerun()
            except Exception as e:
                st.error("Errore imprevisto durante la validazione. Riprova.")

    # --- VISUALIZZAZIONE PORTAFOGLIO ---
    if st.session_state['portfolio']:
        st.subheader("Le tue posizioni")
        
        tickers = [item['ticker'] for item in st.session_state['portfolio']]
        
        with st.spinner("Aggiornamento prezzi batch..."):
            # FETCH PREZZI IN BATCH PIÙ EFFICIENTE
            prices_dict = get_batch_prices(list(set(tickers)))
            
            portfolio_data = []
            total_portfolio_value = 0

            for item in st.session_state['portfolio']:
                ticker = item['ticker']
                shares = item['shares']
                
                # Otteniamo il prezzo dalla cache batch
                current_price = prices_dict.get(ticker, 0.0) 
                # Float check per sicurezza
                if isinstance(current_price, pd.Series):
                    current_price = current_price.iloc[0]

                current_value = shares * current_price
                total_portfolio_value += current_value
                
                portfolio_data.append({
                    "Ticker": ticker,
                    "Quantità": shares,
                    "Prezzo Attuale": current_price,
                    "Valore Totale ($)": current_value
                })

        df_portfolio = pd.DataFrame(portfolio_data)

        # Tabella formattata in stile Bloomberg
        st.dataframe(df_portfolio.style.format({
            'Prezzo Attuale': '${:,.2f}',
            'Valore Totale ($)': '${:,.2f}'
        }), use_container_width=True, hide_index=True)

        st.metric("Total Assets Under Management (AUM)", format_large_numbers(total_portfolio_value))

        st.divider()
        st.subheader("⚖️ Risk Concentration")
        
        fig_pie = px.pie(
            df_portfolio, 
            values='Valore Totale ($)', 
            names='Ticker', 
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_traces(textinfo='percent+label', pull=[0.05] * len(df_portfolio))
        fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)

        
        st.divider()
        st.subheader("🎯 Frontiera Efficiente di Markowitz")
        st.write("Calcolo dei pesi ottimali per massimizzare lo Sharpe Ratio (Maximum Risk-Adjusted Return).")
        if len(df_portfolio) > 1:
            if st.button("🚀 Ottimizza Portafoglio", type="primary"):
                with st.spinner("Ottimizzazione covarianza in corso..."):
                    try:
                        data_batch = yf.download(tickers, period="3y", progress=False)['Close']
                        if not data_batch.empty:
                            if isinstance(data_batch, pd.Series): # edge case
                                st.error("Errore download batch.")
                            else:
                                ret_df = data_batch.pct_change().dropna()
                                active_tickers = list(ret_df.columns)
                                num_assets = len(active_tickers)
                                mean_ret = ret_df.mean() * 252
                                cov_mat = ret_df.cov() * 252
                                rf_rate = 0.02
                                
                                def neg_sharpe(w):
                                    p_ret = np.sum(mean_ret * w)
                                    p_vol = np.sqrt(np.dot(w.T, np.dot(cov_mat, w)))
                                    return - (p_ret - rf_rate) / p_vol
                                    
                                constraints = ({'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
                                bounds = tuple((0, 1) for _ in range(num_assets))
                                init_guess = num_assets * [1. / num_assets]
                                res = minimize(neg_sharpe, init_guess, bounds=bounds, constraints=constraints)
                                opt_weights = res.x
                                
                                opt_df = pd.DataFrame({'Ticker': active_tickers, 'Peso Ottimale (%)': (opt_weights*100).round(2)})
                                p_ret = np.sum(mean_ret * opt_weights)
                                p_vol = np.sqrt(np.dot(opt_weights.T, np.dot(cov_mat, opt_weights)))
                                shorp = (p_ret - rf_rate) / p_vol
                                
                                c1, c2 = st.columns(2)
                                c1.dataframe(opt_df, hide_index=True)
                                c2.metric("Sharpe Ratio Atteso", f"{shorp:.2f}")
                                c2.metric("Rendimento Annuo Atteso", f"{p_ret*100:.2f}%")
                    except Exception as e:
                        st.error("Errore nell'ottimizzazione: " + str(e))
        else:
            st.info("Aggiungi almeno 2 titoli per l'ottimizzazione.")

        # --- AI PORTFOLIO ANALYSIS ---
        st.divider()
        st.subheader("🤖 AI Risk & Diversification Analysis")
        st.write("Chiedi a Gemma di valutare il rischio delle tue posizioni.")
        
        if st.button("⚖️ Analizza Diversificazione", type="secondary"):
            with st.spinner("Gemma sta analizzando i pesi del tuo portafoglio..."):
                ai_advice = analyze_portfolio_diversification(df_portfolio, total_portfolio_value)
                st.success(ai_advice)

        if st.button("🗑️ Svuota Portafoglio"):
            st.session_state['portfolio'] = []
            save_portfolio([])
            st.rerun()

    else:
        st.info("Nessuna posizione in portafoglio.")

# ==========================================
# PAGE 4: FINANCIAL NEWS
# ==========================================
elif page_choice == "📰 Financial News":
    st.title("📰 Financial News Feed")
    st.write("Stay up-to-date with the latest market news and **AI-powered sentiment analysis**.")
    st.divider()
    
    col_news, _ = st.columns([1, 2])
    with col_news:
        ticker_news = st.text_input("Enter Ticker (e.g., AAPL, MSFT)", value="AAPL").upper()
    
    if 'news_contexts' not in st.session_state:
        st.session_state['news_contexts'] = []

    if st.button("Search News", type="primary"):
        with st.spinner("Fetching latest news and analyzing sentiment..."):
            news_items = fetch_news(ticker_news)
            st.session_state['news_contexts'] = []
            
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
                        # AI Sentiment logic
                        sentiment_label = get_sentiment(title)
                        st.session_state['news_contexts'].append(f"Titolo: {title} | Data: {pub_date}")
                        
                        with st.container():
                            st.markdown(f"#### {title}")
                            st.caption(f"✍️ **Source:** {publisher} | 🕒 **Published:** {pub_date} | 🧠 **AI Sentiment:** {sentiment_label}")
                            st.markdown(f"[🔗 Read full article]({link})")
                            st.divider()
            else:
                st.warning(f"No recent news found for ticker {ticker_news}.")

    st.divider()
    st.subheader("💡 Chiedi all'Assistente AI Sulle Notizie")
    st.write("Fai una domanda usando solo i contenuti freschi estratti qui sopra (RAG Locale).")
    user_q = st.text_input("La tua domanda (Es. 'Perché il titolo è sceso oggi?')")
    if user_q and st.button("Consulta AI", key="btn_rag"):
        if st.session_state.get('news_contexts'):
            with st.spinner("Riflessione in corso..."):
                ctx_str = "\n".join(st.session_state['news_contexts'][:15])
                ans = ask_financial_chatbot(user_q, ctx_str)
                st.success(ans)
        else:
            st.warning("Cerca prima le notizie per caricare il contesto dell'AI.")

# ==========================================
# ==========================================
# PAGE 5: MACRO & MARKET
# ==========================================
elif page_choice == "🌍 Macro & Market":
    st.title("🌍 Macro & Market Pulse")
    st.write("Visione globale istituzionale per il contesto di mercato.")
    st.divider()
    
    with st.spinner("Acquisizione dati macroeconomici..."):
        macro_tickers = {
            "S&P 500 (Trend US)": "^GSPC",
            "Nasdaq 100": "^NDX",
            "US 10Y Treasury (Risk-Free)": "^TNX",
            "VIX (Fear Index)": "^VIX",
            "Oro (Bene Rifugio)": "GC=F"
        }
        
        macro_data = {}
        for name, tk in macro_tickers.items():
            hist = yf.Ticker(tk).history(period="6mo")
            if not hist.empty: macro_data[name] = hist['Close']
                
        items = list(macro_data.items())
        cols_per_row = 3
        
        for i in range(0, len(items), cols_per_row):
            chunk = items[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for j, (name, series) in enumerate(chunk):
                with cols[j]:
                    val = series.iloc[-1]
                    prev = series.iloc[-2]
                    pct = ((val - prev)/prev)*100
                    st.metric(name, f"{val:.2f}", f"{pct:.2f}%")
                    fig = px.line(series, x=series.index, y=series.values)
                    fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=150, margin=dict(l=0, r=0, t=45, b=0), showlegend=False)
                    st.plotly_chart(fig, use_container_width=True)
            
            st.write("") # Spazio extra verticale
            st.write("")

# ==========================================
# PAGE 6: STOCK SCREENER
# ==========================================
elif page_choice == "🔍 Stock Screener":
    st.title("🔍 S&P 500 Stock Screener")
    st.write("Esplora l'intero **S&P 500** alla ricerca di opportunità Value e Dividend.")
    st.divider()
    
    @st.cache_data(ttl=3600*24)
    def get_sp500_tickers():
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
        return pd.read_html(io.StringIO(html))[0]['Symbol'].tolist()
        
    try:
        sp500_tickers = get_sp500_tickers()
    except Exception as e:
        st.error("Impossibile caricare S&P 500.")
        sp500_tickers = []
    
    sc1, sc2, sc3 = st.columns(3)
    max_pe = sc1.number_input("P/E Ratio Massimo", value=25.0)
    min_div = sc2.number_input("Dividend Yield Minimo (%)", value=2.0)
    min_cap = sc3.number_input("Market Cap Min. (Billion $)", value=100)
    
    if st.button("🚀 Esegui Screen", type="primary"):
        if sp500_tickers:
            with st.spinner(f"Scansione parallela di {len(sp500_tickers)} titoli dell'S&P 500 in corso (richiederà 15-20 secondi)..."):
                
                def evaluate_ticker(tkr):
                    try:
                        tk_info = fetch_stock_info(tkr)
                        if not tk_info: return None
                        pe = tk_info.get('trailingPE')
                        d_yield = tk_info.get('dividendYield', 0)
                        d_yield = d_yield if d_yield else 0
                        mcap_b = tk_info.get('marketCap', 0) / 1e9
                        
                        if pe and pe <= max_pe and d_yield >= min_div and mcap_b >= min_cap:
                            return {
                                "Ticker": tkr,
                                "Azienda": tk_info.get('shortName', ''),
                                "P/E": round(pe, 2),
                                "Div Yield %": round(d_yield, 2),
                                "Market Cap (B)": round(mcap_b, 2),
                                "Prezzo": tk_info.get('currentPrice', 'N/A')
                            }
                    except:
                        pass
                    return None
                    
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    results = list(executor.map(evaluate_ticker, sp500_tickers))
                    
                screener_res = [r for r in results if r is not None]
                            
                if screener_res:
                    df_screen = pd.DataFrame(screener_res).sort_values(by="Div Yield %", ascending=False)
                    st.success(f"Trovate {len(screener_res)} aziende che rispettano i tuoi parametri istituzionali.")
                    st.dataframe(df_screen, use_container_width=True, hide_index=True)
                else:
                    st.warning("Nessuna azienda rispetta queste query severe!")

# ==========================================
# PAGE 7: SUPER INVESTORS
# ==========================================
elif page_choice == "👑 Super Investors":
    if 'active_investor' not in st.session_state:
        st.session_state['active_investor'] = None

    if st.session_state['active_investor']:
        inv_name = st.session_state['active_investor']
        
        if st.button("⬅️ Torna alla lista Investitori"):
            st.session_state['active_investor'] = None
            st.rerun()
            
        st.title(f"💼 Portafoglio: {inv_name}")
        
        bios = {
            "Warren Buffett": "Il leggendario 'Oracolo di Omaha', maestro del Value Investing a lungo termine. La sua filosofia si basa sull'acquisto di aziende storiche con vantaggi competitivi inattaccabili (moat) e flussi di cassa solidi.",
            "Michael Burry": "Pioniere della crisi dei mutui subprime ('The Big Short'). Dottore e investitore quantitativo, eccelle nel trovare asimmetrie estreme nei mercati, ricercando valore o vendendo allo scoperto settori ad altissimo rischio.",
            "Cathie Wood": "CEO di ARK Invest, specializzata esclusivamente in tecnologie iper-disruptive e innovazione profonda (Genetica, IA, Robotica, Blockchain). Il suo approccio punta a cicli di crescita esponenziale e rendimenti ultra-aggressivi.",
            "Bill Ackman": "Magnate di Pershing Square e celebre investitore attivista. Costruisce portafogli ad altissima 'conviction' con pochissimi titoli chiave, esercitando pressioni sui Board e proteggendo i capitali tramite complesse tutele macroeconomiche.",
            "David Tepper": "Fondatore di Appaloosa e re indiscusso del 'Distressed Debt'. Costruisce incredibile ricchezza comprando aggressivamente nei momenti di puro panico finanziario, combinando fiuto macroeconomico e scommesse altamente cicliche.",
            "Ray Dalio": "Fondatore di Bridgewater Associates, il più maestoso hedge fund algoritmico macroeconomico globale. Teorico del portafoglio 'All-Weather', gestisce i capitali focalizzandosi sul bilanciamento assoluto del rischio e della stagionalità.",
            "Stanley Druckenmiller": "Leggenda Macro operante tramite il Duquesne Family Office. Rinomato per non aver mai chiuso un anno in perdita, adotta uno stile top-down per concentrare enormi capitali dovunque l'asimmetria sia più favorevole.",
            "Ken Griffin": "Fondatore di Citadel, uno dei colossi quantitativi e market-making più influenti di Wall Street. Sfrutta modelli matematici complessi e arbitraggio ad alta frequenza per generare profitti in ogni condizione.",
            "Carl Icahn": "Titano dell'investimento attivista (Icahn Enterprises). Compra enormi quote di società sottovalutate per imporre violente riforme manageriali, estraendo puro valore nascosto per gli azionisti tramite riorganizzazioni brutali."
        }
        
        aum_map = {
            "Warren Buffett": "$274.1 Miliardi",
            "Michael Burry": "$54.9 Milioni",
            "Cathie Wood": "$13.4 Miliardi",
            "Bill Ackman": "$10.5 Miliardi",
            "David Tepper": "$5.9 Miliardi",
            "Ray Dalio": "$19.6 Miliardi",
            "Stanley Druckenmiller": "$4.5 Miliardi",
            "Ken Griffin": "$96.4 Miliardi",
            "Carl Icahn": "$12.1 Miliardi"
        }
        
        if inv_name in bios:
            st.markdown(f"<p style='color: #A0A0A0; font-size: 16px; margin-bottom: 20px;'><i>{bios[inv_name]}</i></p>", unsafe_allow_html=True)
            
        if inv_name in aum_map:
            st.metric(label="📊 Asset Under Management (13F)", value=aum_map[inv_name])
            
        st.divider()
        
        portfolio_details = {
            "Warren Buffett": [
                {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology", "Allocazione %": 22.60, "Quote": "227.9M", "Valore": "$61.9B"},
                {"Ticker": "AXP", "Azienda": "American Express", "Settore": "Financial", "Allocazione %": 20.46, "Quote": "151.6M", "Valore": "$56.0B"},
                {"Ticker": "BAC", "Azienda": "Bank of America", "Settore": "Financial", "Allocazione %": 10.38, "Quote": "517.2M", "Valore": "$28.4B"},
                {"Ticker": "KO", "Azienda": "Coca-Cola", "Settore": "Consumer", "Allocazione %": 10.20, "Quote": "400.0M", "Valore": "$27.9B"},
                {"Ticker": "CVX", "Azienda": "Chevron", "Settore": "Energy", "Allocazione %": 7.24, "Quote": "130.1M", "Valore": "$19.8B"},
                {"Ticker": "MCO", "Azienda": "Moody's Corp.", "Settore": "Financial", "Allocazione %": 4.60, "Quote": "24.6M", "Valore": "$12.6B"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 24.52, "Quote": "-", "Valore": "$67.2B"},
            ],
            "Michael Burry": [
                {"Ticker": "MOH", "Azienda": "Molina Healthcare Inc.", "Settore": "Health", "Allocazione %": 43.49, "Quote": "125K", "Valore": "$23.9M"},
                {"Ticker": "LULU", "Azienda": "Lululemon Athletica", "Settore": "Consumer", "Allocazione %": 32.35, "Quote": "100K", "Valore": "$17.7M"},
                {"Ticker": "SLM", "Azienda": "SLM Corp.", "Settore": "Financial", "Allocazione %": 24.16, "Quote": "480K", "Valore": "$13.2M"},
            ],
            "Cathie Wood": [
                {"Ticker": "TSLA", "Azienda": "Tesla", "Settore": "Auto", "Allocazione %": 11.20, "Quote": "3.8M", "Valore": "$680M"},
                {"Ticker": "COIN", "Azienda": "Coinbase", "Settore": "Crypto", "Allocazione %": 8.50, "Quote": "4.2M", "Valore": "$590M"},
                {"Ticker": "ROKU", "Azienda": "Roku", "Settore": "Communication", "Allocazione %": 8.00, "Quote": "9.1M", "Valore": "$520M"},
                {"Ticker": "SQ", "Azienda": "Block", "Settore": "Financial", "Allocazione %": 7.10, "Quote": "8.5M", "Valore": "$500M"},
                {"Ticker": "CRSP", "Azienda": "CRISPR Therapeutics", "Settore": "Health", "Allocazione %": 5.60, "Quote": "6.3M", "Valore": "$380M"},
                {"Ticker": "PLTR", "Azienda": "Palantir", "Settore": "Software", "Allocazione %": 5.40, "Quote": "15.4M", "Valore": "$350M"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 54.20, "Quote": "-", "Valore": "$4.1B"},
            ],
            "Bill Ackman": [
                {"Ticker": "BN", "Azienda": "Brookfield Corp.", "Settore": "Financial", "Allocazione %": 18.15, "Quote": "61.4M", "Valore": "$2.8B"},
                {"Ticker": "UBER", "Azienda": "Uber Technologies", "Settore": "Tech", "Allocazione %": 15.90, "Quote": "30.2M", "Valore": "$2.4B"},
                {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce", "Allocazione %": 14.28, "Quote": "9.6M", "Valore": "$2.2B"},
                {"Ticker": "GOOG", "Azienda": "Alphabet Inc.", "Settore": "Communication", "Allocazione %": 12.46, "Quote": "6.1M", "Valore": "$1.9B"},
                {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication", "Allocazione %": 11.37, "Quote": "2.6M", "Valore": "$1.7B"},
                {"Ticker": "QSR", "Azienda": "Restaurant Brands", "Settore": "Consumer", "Allocazione %": 10.05, "Quote": "22.8M", "Valore": "$1.5B"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 17.79, "Quote": "-", "Valore": "$2.9B"},
            ],
            "David Tepper": [
                {"Ticker": "BABA", "Azienda": "Alibaba Group", "Settore": "E-Commerce", "Allocazione %": 10.99, "Quote": "5.1M", "Valore": "$753M"},
                {"Ticker": "GOOG", "Azienda": "Alphabet Inc.", "Settore": "Communication", "Allocazione %": 8.18, "Quote": "1.7M", "Valore": "$560M"},
                {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce", "Allocazione %": 7.34, "Quote": "2.1M", "Valore": "$503M"},
                {"Ticker": "MU", "Azienda": "Micron Technology", "Settore": "Technology", "Allocazione %": 6.25, "Quote": "1.5M", "Valore": "$428M"},
                {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication", "Allocazione %": 5.78, "Quote": "600K", "Valore": "$396M"},
                {"Ticker": "TSM", "Azienda": "Taiwan Semi", "Settore": "Technology", "Allocazione %": 5.01, "Quote": "1.1M", "Valore": "$343M"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 56.45, "Quote": "-", "Valore": "$3.8B"},
            ],
            "Ray Dalio": [
                {"Ticker": "IVV", "Azienda": "iShares Core S&P 500", "Settore": "ETF", "Allocazione %": 20.30, "Quote": "18.4M", "Valore": "$4.1B"},
                {"Ticker": "IEMG", "Azienda": "iShares Core MSCI EM", "Settore": "ETF", "Allocazione %": 10.50, "Quote": "25.1M", "Valore": "$2.1B"},
                {"Ticker": "SPY", "Azienda": "SPDR S&P 500 ETF", "Settore": "ETF", "Allocazione %": 5.10, "Quote": "3.5M", "Valore": "$1.8B"},
                {"Ticker": "PG", "Azienda": "Procter & Gamble", "Settore": "Consumer", "Allocazione %": 4.20, "Quote": "5.6M", "Valore": "$800M"},
                {"Ticker": "JNJ", "Azienda": "Johnson & Johnson", "Settore": "Health", "Allocazione %": 3.50, "Quote": "4.2M", "Valore": "$650M"},
                {"Ticker": "PEP", "Azienda": "PepsiCo", "Settore": "Consumer", "Allocazione %": 3.10, "Quote": "3.1M", "Valore": "$510M"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 53.30, "Quote": "-", "Valore": "$10.4B"},
            ],
            "Stanley Druckenmiller": [
                {"Ticker": "NTRA", "Azienda": "Natera, Inc.", "Settore": "Health", "Allocazione %": 24.50, "Quote": "8.1M", "Valore": "$1.1B"},
                {"Ticker": "XLF", "Azienda": "Financial Select SPDR", "Settore": "ETF", "Allocazione %": 15.20, "Quote": "12.4M", "Valore": "$680M"},
                {"Ticker": "INSM", "Azienda": "Insmed Incorporated", "Settore": "Health", "Allocazione %": 10.10, "Quote": "9.5M", "Valore": "$452M"},
                {"Ticker": "RSP", "Azienda": "Invesco S&P 500 Equal", "Settore": "ETF", "Allocazione %": 8.00, "Quote": "2.2M", "Valore": "$359M"},
                {"Ticker": "TEVA", "Azienda": "Teva Pharmaceutical", "Settore": "Health", "Allocazione %": 5.10, "Quote": "11.1M", "Valore": "$229M"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 37.10, "Quote": "-", "Valore": "$1.6B"},
            ],
            "Ken Griffin": [
                {"Ticker": "SPY", "Azienda": "SPDR S&P 500 ETF", "Settore": "ETF", "Allocazione %": 12.50, "Quote": "35.1M", "Valore": "$12.0B"},
                {"Ticker": "QQQ", "Azienda": "Invesco QQQ Trust", "Settore": "ETF", "Allocazione %": 10.20, "Quote": "25.2M", "Valore": "$9.8B"},
                {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology", "Allocazione %": 6.80, "Quote": "8.5M", "Valore": "$6.5B"},
                {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology", "Allocazione %": 5.10, "Quote": "22.3M", "Valore": "$4.9B"},
                {"Ticker": "TSLA", "Azienda": "Tesla", "Settore": "Auto", "Allocazione %": 4.20, "Quote": "15.1M", "Valore": "$4.0B"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 61.20, "Quote": "-", "Valore": "$59.2B"},
            ],
            "Carl Icahn": [
                {"Ticker": "IEP", "Azienda": "Icahn Enterprises", "Settore": "Conglomerate", "Allocazione %": 60.50, "Quote": "298M", "Valore": "$7.3B"},
                {"Ticker": "OXY", "Azienda": "Occidental Petroleum", "Settore": "Energy", "Allocazione %": 15.20, "Quote": "35.6M", "Valore": "$1.8B"},
                {"Ticker": "CVI", "Azienda": "CVR Energy", "Settore": "Energy", "Allocazione %": 10.10, "Quote": "31.2M", "Valore": "$1.2B"},
                {"Ticker": "IFF", "Azienda": "Intl Flavors", "Settore": "Materials", "Allocazione %": 5.50, "Quote": "7.5M", "Valore": "$665M"},
                {"Ticker": "SWX", "Azienda": "Southwest Gas", "Settore": "Utilities", "Allocazione %": 3.20, "Quote": "5.1M", "Valore": "$387M"},
                {"Ticker": "ALTRI", "Azienda": "Resto del Portafoglio", "Settore": "Multiplo", "Allocazione %": 5.50, "Quote": "-", "Valore": "$665M"},
            ]
        }
        
        if inv_name in portfolio_details:
            df_port = pd.DataFrame(portfolio_details[inv_name])
            
            c1, c2 = st.columns([1.5, 1])
            with c1:
                st.subheader("📋 Top Holdings (13F Filings)")
                st.dataframe(df_port, use_container_width=True, hide_index=True)
                
            with c2:
                st.subheader("🥧 Allocazione Asset")
                fig_pie = px.pie(
                    df_port, 
                    names='Ticker', 
                    values='Allocazione %', 
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        else:
            st.error("Dati portafoglio non ancora digitalizzati per questo investitore.")
        
    else:
        st.markdown("""
        <style>
        .super-title { font-size: 38px; font-weight: 800; text-align: center; margin-top: 10px; margin-bottom: 5px; }
        .super-sub { font-size: 18px; color: #7b8084; text-align: center; margin-bottom: 30px; font-weight: 300; }
        .inv-card {
            background-color: var(--secondary-background-color);
            padding: 24px;
            border-radius: 12px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
            border: 1px solid rgba(255, 255, 255, 0.05);
            margin-bottom: 10px;
        }
        .inv-name { font-size: 22px; font-weight: 700; margin-bottom: 2px; }
        .inv-company { font-size: 14px; color: #8A929A; margin-bottom: 15px; }
        .inv-perf { font-size: 14px; font-weight: 600; margin-bottom: 15px; border-bottom: 1px solid rgba(255, 255, 255, 0.1); padding-bottom: 15px; }
        .inv-port { font-size: 14px; font-weight: 700; margin-bottom: 15px; }
        .holding-row { display: flex; align-items: center; margin-bottom: 10px; }
        .holding-icon { 
            width: 28px; height: 28px; border-radius: 4px; margin-right: 12px; display: flex; align-items: center; justify-content: center; 
            color: white; font-weight: 800; font-size: 12px; text-shadow: 0px 1px 2px rgba(0,0,0,0.5);
        }
        .holding-name { font-size: 14px; color: #E0E0E0; flex-grow: 1; margin: 0;}
        </style>
        <div class="super-title">Decode the Smart Money</div>
        <div class="super-sub">Uncover the portfolio strategies of elite hedge fund managers and top institutional investors.</div>
        """, unsafe_allow_html=True)
        
        t1, t2, t3, t4 = st.tabs(["Top Investors", "Congress Trades", "Insider Trades", "Stock Picks"])
        
        with t1:
            st.write("")
            category_choice = st.radio("Filtra per stile di investimento:", 
                ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors", "🏛️ Value Investors", "📉 Contrarians / Short", "⏳ Long-Term"], 
                horizontal=True,
                label_visibility="collapsed"
            )
            st.write("")
            
            super_data = [
                {
                    "name": "Warren Buffett", "company": "Berkshire Hathaway", 
                    "perf": "26.17%", "size": "$274.1B", 
                    "categories": ["🌟 Popular", "🏛️ Value Investors", "⏳ Long-Term"],
                    "holdings": [("AAPL", "Apple", "#000000"), ("AXP", "American Express", "#006fcf"), ("BAC", "Bank of America", "#E31837")],
                    "more": 39
                },
                {
                    "name": "Michael Burry", "company": "Scion Asset Management", 
                    "perf": "28.20%", "size": "$54.9M", 
                    "categories": ["🌟 Popular", "📉 Contrarians / Short"],
                    "holdings": [("MOH", "Molina Healthcare", "#00A99D"), ("LULU", "Lululemon Athletica", "#E60028"), ("SLM", "SLM", "#004B87")],
                    "more": 0
                },
                {
                    "name": "Cathie Wood", "company": "ARK Invest", 
                    "perf": "48.75%", "size": "$13.4B", 
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("TSLA", "Tesla", "#E82127"), ("COIN", "Coinbase", "#0052FF"), ("ROKU", "Roku", "#662D91")],
                    "more": 180
                },
                {
                    "name": "Bill Ackman", "company": "Pershing Square", 
                    "perf": "31.42%", "size": "$10.5B", 
                    "categories": ["🌟 Popular", "📈 Best Performance", "🏛️ Value Investors"],
                    "holdings": [("BN", "Brookfield Corp", "#002F6C"), ("UBER", "Uber", "#000000"), ("AMZN", "Amazon", "#FF9900")],
                    "more": 4
                },
                {
                    "name": "David Tepper", "company": "Appaloosa Management", 
                    "perf": "35.10%", "size": "$5.9B", 
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("BABA", "Alibaba Group", "#FF6A00"), ("GOOG", "Alphabet Inc.", "#DB4437"), ("AMZN", "Amazon", "#FF9900")],
                    "more": 25
                },
                {
                    "name": "Ray Dalio", "company": "Bridgewater Associates", 
                    "perf": "14.80%", "size": "$19.6B", 
                    "categories": ["🌟 Popular", "⏳ Long-Term"],
                    "holdings": [("IVV", "iShares S&P 500", "#000000"), ("IEMG", "iShares MSCI EM", "#000000"), ("SPY", "SPDR S&P 500", "#0B2664")],
                    "more": 450
                },
                {
                    "name": "Stanley Druckenmiller", "company": "Duquesne Family Office", 
                    "perf": "41.60%", "size": "$4.5B", 
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("NTRA", "Natera", "#00A9E0"), ("XLF", "Fin Select SPDR", "#000000"), ("INSM", "Insmed", "#8A929A")],
                    "more": 42
                },
                {
                    "name": "Ken Griffin", "company": "Citadel Advisors", 
                    "perf": "21.30%", "size": "$96.4B", 
                    "categories": ["🌟 Popular", "📉 Contrarians / Short", "⏳ Long-Term"],
                    "holdings": [("SPY", "SPDR S&P 500", "#0B2664"), ("QQQ", "Invesco QQQ", "#000000"), ("NVDA", "NVIDIA", "#76B900")],
                    "more": 4500
                },
                {
                    "name": "Carl Icahn", "company": "Icahn Enterprises", 
                    "perf": "12.40%", "size": "$12.1B", 
                    "categories": ["🌟 Popular", "🏛️ Value Investors", "📉 Contrarians / Short"],
                    "holdings": [("IEP", "Icahn Ent.", "#000000"), ("OXY", "Occidental", "#E31837"), ("CVI", "CVR Energy", "#006fcf")],
                    "more": 12
                }
            ]
            
            filtered_data = [inv for inv in super_data if category_choice in inv['categories']]
            
            if not filtered_data:
                st.warning("Nessun investitore trovato per questa categoria.")
            else:
                for i in range(0, len(filtered_data), 3):
                    cols = st.columns(3)
                    for j, inv in enumerate(filtered_data[i:i+3]):
                        idx = i + j
                        with cols[j]:
                            holdings_html = ""
                            for h in inv['holdings']:
                                holdings_html += f'<div class="holding-row"><div class="holding-icon" style="background-color: {h[2]}; ">{h[0][0]}</div><div class="holding-name">{h[1]}</div></div>'
                            
                            st.markdown(f'<div class="inv-card"><div class="inv-name">{inv["name"]}</div><div class="inv-company">{inv["company"]}</div><div class="inv-perf">📈 Performance: {inv["perf"]} last year</div><div class="inv-port">{inv["size"]} portfolio</div>{holdings_html}</div>', unsafe_allow_html=True)
                            
                            if inv['more'] > 0:
                                btn_text = f"+ {inv['more']} more stocks"
                            else:
                                btn_text = "View Portfolio (100%)"
                                
                            if st.button(btn_text, key=f"filter_btn_{inv['name']}", use_container_width=True):
                                st.session_state['active_investor'] = inv['name']
                                st.rerun()
                    
        with t2:
            st.info("Congress Trades (Senators & Representatives) verranno implementati incrociando i database House/Senate Disclosures.")
        with t3:
            st.info("Insider Trades (CEO, CFO, Board Members) verranno implementati leggendo i form SEC 4.")
        with t4:
            st.info("Le Stock Picks istituzionali verranno generate filtrando l'universo del S&P 500 in base alle logiche dell'Hedge Fund selezionato.")

