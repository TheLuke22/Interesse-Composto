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
from textblob import TextBlob
import json
import random
import os
import textwrap

WALL_STREET_QUOTES = [
    "Governments don't rule the world, Goldman Sachs rules the world. - Alessio Rastani",
    "Markets can remain irrational longer than you can remain solvent. - John Maynard Keynes",
    "Bulls make money, bears make money, pigs get slaughtered. - Wall Street Adage",
    "The stock market is a device for transferring money from the impatient to the patient. - Warren Buffett",
    "Only when the tide goes out do you discover who's been swimming naked. - Warren Buffett",
    "Risk comes from not knowing what you're doing. - Warren Buffett",
    "In investing, what is comfortable is rarely profitable. - Robert Arnott",
    "Money never sleeps, pal. - Wall Street (1987)",
    "We simply attempt to be fearful when others are greedy and to be greedy only when others are fearful. - Warren Buffett"
]

# --- CONFIGURAZIONE ISTITUZIONALE ---
st.set_page_config(page_title="PRO Quant Dashboard", layout="wide", initial_sidebar_state="expanded")

# --- MOTORE PER MARQUEE DATA ---
@st.cache_data(ttl=3600)
def get_marquee_data():
    tickers = {
        "S&P 500": "SPY", "NASDAQ": "QQQ", "DOW J": "DIA", "GOLD": "GLD", 
        "BTC": "BTC-USD", "10Y YIELD": "^TNX", "NVIDIA": "NVDA", "APPLE": "AAPL", 
        "TESLA": "TSLA", "DOLLAR": "DX-Y.NYB", "OIL": "CL=F", "EURO": "EURUSD=X"
    }
    marquee_items = []
    
    # Per essere robusti in caso d'errore di Rete
    try:
        data = yf.download(list(tickers.values()), period="5d", progress=False)['Close']
        if not data.empty and len(data) >= 2:
            for name, tk in tickers.items():
                if tk in data.columns:
                    series = data[tk].dropna()
                    if len(series) >= 2:
                        last_prc = series.iloc[-1]
                        prev_prc = series.iloc[-2]
                        pct = ((last_prc - prev_prc) / prev_prc) * 100
                        color = "#00FF00" if pct >= 0 else "#FF0000"
                        sign = "+" if pct >= 0 else ""
                        marquee_items.append(f"<span style='margin-right: 40px;'><b>{name}</b> ${last_prc:,.2f} <span style='color: {color};'>{sign}{pct:.2f}%</span></span>")
        return " ".join(marquee_items) if marquee_items else "MARKET DATA LIMITED"
    except:
        return "MARKET DATA UNAVAILABLE"

marquee_html = get_marquee_data()

# --- INIETTA STYLE.CSS (Design AI Insights) ---
def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")

# Custom CSS per look "Fintech Premium Glassmorphic" e "Marquee"
# Custom CSS per look "Institutional Premium" e Leggibilità Avanzata
st.markdown(f"""
    <style>
    /* Global Background & Smooth Animation */
    @keyframes gradientShift {{
        0%   {{ background-position: 0% 50%; }}
        50%  {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}

    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(-45deg, #0a0a12, #171924, #0f0c29, #050510) !important;
        background-size: 400% 400% !important;
        animation: gradientShift 30s ease infinite !important;
        color: #e0e0e0 !important;
    }}

    /* Overlay per profondità e texture */
    [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background: radial-gradient(circle at center, transparent 0%, rgba(0,0,0,0.4) 100%);
        pointer-events: none;
        z-index: 0;
    }}

    /* Fix Leggibilità Testo */
    .stMarkdown, p, span, label, .stMetric label {{
        color: #e0e0e0 !important;
        font-weight: 300;
    }}
    
    h1, h2, h3 {{
        color: #ffffff !important;
        text-shadow: 0 0 15px rgba(255,255,255,0.1);
        letter-spacing: -0.5px;
    }}

    /* Enhanced Glassmorphic Containers */
    [data-testid="stMetric"], .stDataFrame, .stExpander, div[data-testid="stVerticalBlock"] > div[style*="background-color"] {{ 
        background: rgba(255, 255, 255, 0.05) !important; 
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        padding: 20px !important; 
        border-radius: 16px !important; 
        border: 1px solid rgba(255, 255, 255, 0.12) !important; 
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37) !important;
    }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: #050510 !important;
        border-right: 1px solid rgba(255,255,255,0.05);
    }}
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {{
        background: transparent !important;
    }}

    /* Ticker Tape Animation Refined */
    @keyframes ticker {{
        0% {{ transform: translate3d(0, 0, 0); }}
        100% {{ transform: translate3d(-50%, 0, 0); }}
    }}
    .ticker-wrap {{
        width: 100%;
        overflow: hidden;
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(5px);
        padding: 10px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        margin-top: -30px; 
        margin-bottom: 20px;
        white-space: nowrap;
        position: sticky;
        top: 0;
        z-index: 1000;
    }}
    .ticker-move {{
        display: inline-block;
        white-space: nowrap;
        animation: ticker 60s linear infinite;
    }}
    .ticker-move:hover {{
        animation-play-state: paused;
    }}
    
    /* Header Transparency */
    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    /* Custom Scrollbar for Premium Feel */
    ::-webkit-scrollbar {{
        width: 8px;
    }}
    ::-webkit-scrollbar-track {{
        background: rgba(0,0,0,0.1);
    }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(255,255,255,0.1);
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: rgba(255,255,255,0.2);
    }}
    </style>
    <div class="ticker-wrap">
        <div class="ticker-move">
            {marquee_html}{marquee_html}
        </div>
    </div>
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

WATCHLIST_FILE = 'watchlist.json'

def load_watchlist():
    if os.path.exists(WATCHLIST_FILE):
        try:
            with open(WATCHLIST_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_watchlist(w_list):
    try:
        with open(WATCHLIST_FILE, 'w') as f:
            json.dump(w_list, f)
    except Exception:
        pass

if 'portfolio' not in st.session_state:
    st.session_state['portfolio'] = load_portfolio()

if 'watchlist' not in st.session_state:
    st.session_state['watchlist'] = load_watchlist()

# --- UTILITY QUANTITATIVE E FORMATTAZIONE ---
def format_large_numbers(value, is_currency=True):
    # Se il valore è una Series o lista, prendi il primo elemento (evita errori di ambiguità pandas)
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        if len(value) > 0:
            import pandas as pd
            value = value.iloc[0] if isinstance(value, (pd.Series, pd.DataFrame)) else value[0]
        else:
            return "N/A"
            
    if value is None or str(value) == 'nan' or value == 'N/A' or isinstance(value, str): return "N/A"
    prefix = ""
    if value < 0: value = abs(value); prefix = "-"
    c = "$" if is_currency else ""
    if value >= 1_000_000_000_000: return f"{prefix}{c}{value/1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000: return f"{prefix}{c}{value/1_000_000_000:.2f}B"
    if value >= 1_000_000: return f"{prefix}{c}{value/1_000_000:.2f}M"
    return f"{prefix}{c}{value:,.2f}"

def format_perc(value):
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        if len(value) > 0:
            import pandas as pd
            value = value.iloc[0] if isinstance(value, (pd.Series, pd.DataFrame)) else value[0]
        else:
            return "N/A"
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
    """Analizza il sentiment del testo usando Gemma in locale tramite Ollama."""
    prompt = f"""Agisci come un analista finanziario esperto. 
    Leggi il seguente titolo di una notizia e dimmi se per il prezzo delle azioni dell'azienda è una notizia POSITIVA, NEGATIVA o NEUTRA. 
    Rispondi SOLO con una di queste tre parole: Positive, Negative, Neutral.
    
    Titolo notizia: "{text}"
    """
    
    try:
        response = requests.post(
            "http://localhost:11434/api/generate", 
            json={
                "model": "gemma:2b", 
                "prompt": prompt, 
                "stream": False
            },
            timeout=10
        )
        
        if response.status_code == 200:
            ai_reply = response.json()['response'].strip().lower()
            if "positive" in ai_reply: 
                return "🟢 Positive"
            elif "negative" in ai_reply: 
                return "🔴 Negative"
            else: 
                return "⚪ Neutral"
        else:
            return "⚪ Neutral (Errore API)"
    except Exception:
        score = TextBlob(text).sentiment.polarity
        if score > 0.1: return "🟢 Positive (TextBlob Fallback)"
        elif score < -0.1: return "🔴 Negative (TextBlob Fallback)"
        else: return "⚪ Neutral (TextBlob Fallback)"

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
        response = requests.post("http://localhost:11434/api/generate", json={"model": "gemma:2b", "prompt": prompt, "stream": False, "options": {"temperature": 0.2}}, timeout=30)
        if response.status_code == 200: return response.json()['response'].strip()
        else: return "Errore nella generazione."
    except Exception: return "Errore di connessione con Ollama."

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
    try:
        out = pdf.output(dest='S')
        if isinstance(out, (bytes, bytearray)):
            return bytes(out)
        return out.encode('latin-1')
    except Exception:
        try:
            return bytes(pdf.output())
        except TypeError:
            return pdf.output().encode('latin-1')

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


@st.cache_data(ttl=300)
def fetch_watchlist_prices(ticker_tuple):
    """Fetch 5-day price data for watchlist tickers (cached 5 min)."""
    if not ticker_tuple: return {}
    ticker_list = list(ticker_tuple)
    try:
        data = yf.download(ticker_list, period="5d", progress=False)['Close']
        if isinstance(data, pd.Series):
            data = data.to_frame(name=ticker_list[0])
        result = {}
        for tk in ticker_list:
            if tk in data.columns:
                series = data[tk].dropna()
                if len(series) >= 2:
                    result[tk] = (float(series.iloc[-1]), float(series.iloc[-2]))
        return result
    except:
        return {}


@st.cache_data(ttl=3600)
def fetch_stock_info(ticker):
    stock = yf.Ticker(ticker)
    try:
        info = stock.info
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            raise ValueError("Empty info (rate limited)")
        return info
    except Exception:
        # Fallback primario: API FMP Istituzionale
        API_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"
        try:
            import requests
            p_data = requests.get(f"https://financialmodelingprep.com/api/v3/profile/{ticker}?apikey={API_KEY}", timeout=5).json()
            q_data = requests.get(f"https://financialmodelingprep.com/api/v3/quote/{ticker}?apikey={API_KEY}", timeout=5).json()
            
            p = p_data[0] if p_data and isinstance(p_data, list) else {}
            q = q_data[0] if q_data and isinstance(q_data, list) else {}
            
            if p or q:
                return {
                    'symbol': ticker,
                    'shortName': p.get('companyName', ticker),
                    'currentPrice': q.get('price', 0),
                    'marketCap': p.get('mktCap', 0),
                    'previousClose': q.get('previousClose', 0),
                    'sharesOutstanding': q.get('sharesOutstanding', 0),
                    'trailingPE': q.get('pe'),
                    'forwardPE': None,
                    'dividendRate': p.get('lastDiv', 0),
                    'sector': p.get('sector', 'Unknown'),
                    'industry': p.get('industry', 'Unknown'),
                    'trailingEps': q.get('eps'),
                    '_rate_limited': False
                }
        except:
            pass

        # Ultimate fallback a fast_info locale
        try:
            fast = stock.fast_info
            return {
                'symbol': ticker,
                'shortName': ticker,
                'currentPrice': getattr(fast, 'last_price', 0),
                'marketCap': getattr(fast, 'market_cap', 0),
                'previousClose': getattr(fast, 'previous_close', 0),
                'sharesOutstanding': getattr(fast, 'shares', 0),
                'trailingPE': None,
                'forwardPE': None,
                'dividendYield': 0,
                'sector': 'Unknown (Rate Limited)',
                'industry': 'Unknown',
                '_rate_limited': True
            }
        except:
            return {'symbol': ticker, 'shortName': ticker, '_rate_limited': True}

@st.cache_data(ttl=3600)
def fetch_history(ticker, years):
    stock = yf.Ticker(ticker)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=years * 365)
    return stock.history(start=start_date, end=end_date)

@st.cache_data(ttl=3600)
def fetch_financials(ticker):
    stock = yf.Ticker(ticker)
    try:
        f1, f2, f3 = stock.financials, stock.balance_sheet, stock.cashflow
        if f1 is None or f1.empty: raise ValueError()
        return f1, f2, f3
    except Exception:
        try:
            API_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"
            return fetch_fmp_financials(ticker, API_KEY)
        except:
            return None, None, None

@st.cache_data(ttl=3600)
def fetch_financials_extended(ticker):
    """Fetch extended financial data by combining annual + quarterly from yfinance (~5-8 years)."""
    stock = yf.Ticker(ticker)
    try:
        inc_a = stock.income_stmt
        bal_a = stock.balance_sheet
        cf_a = stock.cashflow
    except Exception:
        inc_a, bal_a, cf_a = None, None, None
    try:
        inc_q = stock.quarterly_income_stmt
        bal_q = stock.quarterly_balance_sheet
        cf_q = stock.quarterly_cashflow
    except Exception:
        return inc_a, bal_a, cf_a

    def _q_to_annual(q_df, method='sum'):
        """Aggregate quarterly DataFrame to annual periods."""
        if q_df is None or q_df.empty:
            return pd.DataFrame()
        try:
            qt = q_df.T.copy()
            qt.index = pd.to_datetime(qt.index)
            qt = qt.apply(pd.to_numeric, errors='coerce')
            qt['_yr'] = qt.index.year
            if method == 'sum':
                cnts = qt.groupby('_yr').size()
                full = cnts[cnts >= 4].index
                if full.empty:
                    return pd.DataFrame()
                agg = qt[qt['_yr'].isin(full)].groupby('_yr').sum()
            else:
                agg = qt.sort_index().groupby('_yr').last()
            agg.drop(columns=['_yr'], inplace=True, errors='ignore')
            res = agg.T
            res.columns = [pd.Timestamp(year=int(y), month=12, day=31) for y in res.columns]
            return res
        except Exception:
            return pd.DataFrame()

    def _merge(annual_df, q_agg_df):
        """Merge annual + quarterly-aggregated, preferring annual for overlapping years."""
        if annual_df is None or annual_df.empty:
            return q_agg_df if q_agg_df is not None and not q_agg_df.empty else pd.DataFrame()
        if q_agg_df is None or q_agg_df.empty:
            return annual_df
        try:
            a_years = {c.year for c in annual_df.columns if hasattr(c, 'year')}
            extra = [c for c in q_agg_df.columns if hasattr(c, 'year') and c.year not in a_years]
            if extra:
                m = pd.concat([annual_df, q_agg_df[extra]], axis=1)
                return m.reindex(sorted(m.columns), axis=1)
            return annual_df
        except Exception:
            return annual_df

    inc_qa = _q_to_annual(inc_q, 'sum')
    bal_qa = _q_to_annual(bal_q, 'last')
    cf_qa = _q_to_annual(cf_q, 'sum')
    return _merge(inc_a, inc_qa), _merge(bal_a, bal_qa), _merge(cf_a, cf_qa)

@st.cache_data(ttl=3600)
def fetch_fmp_financials(ticker, api_key):
    """Fetch annual financials from Financial Modeling Prep (stable API)."""
    base_url = "https://financialmodelingprep.com/stable"

    def _get(endpoint):
        try:
            url = f"{base_url}/{endpoint}?symbol={ticker}&apikey={api_key}"
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    return data
        except Exception:
            pass
        return None

    inc_raw = _get("income-statement")
    bal_raw = _get("balance-sheet-statement")
    cf_raw = _get("cash-flow-statement")

    def _build_df(raw_data, field_map):
        """Convert FMP JSON to a yfinance-compatible DataFrame (rows=items, cols=dates)."""
        if not raw_data:
            return pd.DataFrame()
        records = {}
        for item in raw_data:
            try:
                col_date = pd.Timestamp(item['date'])
            except Exception:
                continue
            for fmp_key, yf_key in field_map.items():
                if yf_key not in records:
                    records[yf_key] = {}
                val = item.get(fmp_key)
                if val is not None:
                    records[yf_key][col_date] = val
        if not records:
            return pd.DataFrame()
        df = pd.DataFrame(records).T
        df = df.apply(pd.to_numeric, errors='coerce')
        df = df.reindex(sorted(df.columns), axis=1)
        return df

    inc_map = {
        'revenue': 'Total Revenue', 'netIncome': 'Net Income',
        'grossProfit': 'Gross Profit', 'operatingIncome': 'Operating Income',
        'ebitda': 'EBITDA', 'eps': 'Basic EPS', 'epsDiluted': 'Diluted EPS',
    }
    bal_map = {
        'totalDebt': 'Total Debt', 'totalStockholdersEquity': 'Stockholders Equity',
        'totalAssets': 'Total Assets',
    }
    cf_map = {
        'freeCashFlow': 'Free Cash Flow', 'operatingCashFlow': 'Operating Cash Flow',
    }
    return _build_df(inc_raw, inc_map), _build_df(bal_raw, bal_map), _build_df(cf_raw, cf_map)


def _merge_financial_dfs(df_primary, df_secondary):
    """Merge two financial DataFrames, preferring primary for overlapping years and adding extra years from secondary."""
    if df_primary is None or df_primary.empty:
        return df_secondary if df_secondary is not None and not df_secondary.empty else pd.DataFrame()
    if df_secondary is None or df_secondary.empty:
        return df_primary
    try:
        p_years = {c.year for c in df_primary.columns if hasattr(c, 'year')}
        extra_cols = [c for c in df_secondary.columns if hasattr(c, 'year') and c.year not in p_years]
        if extra_cols:
            # Only keep rows that exist in primary (avoid mismatched row names)
            common_rows = df_primary.index.intersection(df_secondary.index)
            if not common_rows.empty:
                merged = pd.concat([df_primary, df_secondary.loc[common_rows, extra_cols]], axis=1)
            else:
                merged = pd.concat([df_primary, df_secondary[extra_cols]], axis=1)
            return merged.reindex(sorted(merged.columns), axis=1)
        return df_primary
    except Exception:
        return df_primary


@st.cache_data(ttl=3600)
def fetch_macrotrends_financials(ticker, limit_years=10):
    """Scrape 10-15 years of key annual financials from macrotrends.net."""
    from bs4 import BeautifulSoup
    import re as _re

    headers_req = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    # Step 1: Resolve company slug (macrotrends URLs require company-name in path)
    def _resolve_slug(tk):
        try:
            test_url = f'https://www.macrotrends.net/stocks/charts/{tk}/x/revenue'
            r = requests.get(test_url, headers=headers_req, timeout=10, allow_redirects=True)
            if r.status_code == 200:
                m = _re.search(rf'/stocks/charts/{tk}/([^/]+)/', r.url, _re.IGNORECASE)
                if m:
                    return m.group(1)
                m2 = _re.search(rf'/stocks/charts/{tk}/([^/"]+)/revenue', r.text, _re.IGNORECASE)
                if m2:
                    return m2.group(1)
        except Exception:
            pass
        return tk.lower()

    slug = _resolve_slug(ticker)

    # Step 2: Metrics to scrape
    metric_slugs = {
        'Total Revenue': 'revenue',
        'Net Income': 'net-income',
        'Diluted EPS': 'eps-earnings-per-share-diluted',
        'EBITDA': 'ebitda',
        'Total Debt': 'total-long-term-debt',
        'Free Cash Flow': 'free-cash-flow',
    }

    def _parse_value(text):
        text = text.strip().replace(',', '').replace('$', '')
        if not text or text == '-':
            return None
        try:
            return float(text)
        except ValueError:
            return None

    def _scrape_metric(metric_slug):
        url = f'https://www.macrotrends.net/stocks/charts/{ticker}/{slug}/{metric_slug}'
        try:
            r = requests.get(url, headers=headers_req, timeout=10)
            if r.status_code != 200:
                return {}
            soup = BeautifulSoup(r.text, 'html.parser')
            for t in soup.find_all('table'):
                rows = t.find_all('tr')
                if len(rows) < 3:
                    continue
                first_data_row = rows[1].find_all(['th', 'td'])
                if not first_data_row:
                    continue
                first_text = first_data_row[0].get_text(strip=True)
                if len(first_text) != 4 or not first_text.isdigit():
                    continue
                result = {}
                for row in rows[1:]:
                    cells = [td.get_text(strip=True) for td in row.find_all(['th', 'td'])]
                    if len(cells) >= 2 and len(cells[0]) == 4 and cells[0].isdigit():
                        year = int(cells[0])
                        val = _parse_value(cells[1])
                        if val is not None:
                            result[year] = val
                return result
        except Exception:
            pass
        return {}

    # Step 3: Scrape all metrics
    all_data = {}
    for row_name, ms in metric_slugs.items():
        data = _scrape_metric(ms)
        if data:
            all_data[row_name] = data

    if not all_data:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Step 4: Build DataFrames
    million_scale = {'Total Revenue', 'Net Income', 'EBITDA', 'Free Cash Flow', 'Total Debt'}

    all_years = set()
    for data in all_data.values():
        all_years.update(data.keys())
    all_years = sorted(all_years)
    if len(all_years) > limit_years:
        all_years = all_years[-limit_years:]

    col_dates = [pd.Timestamp(year=y, month=12, day=31) for y in all_years]

    inc_rows = ['Total Revenue', 'Net Income', 'Diluted EPS', 'EBITDA']
    inc_data = {}
    for rn in inc_rows:
        if rn in all_data:
            vals = []
            for y in all_years:
                raw = all_data[rn].get(y)
                if raw is not None and rn in million_scale:
                    vals.append(raw * 1_000_000)
                else:
                    vals.append(raw)
            inc_data[rn] = vals

    bal_data = {}
    if 'Total Debt' in all_data:
        bal_data['Total Debt'] = [
            (all_data['Total Debt'].get(y, None) or 0) * 1_000_000 if all_data['Total Debt'].get(y) is not None else None
            for y in all_years
        ]

    cf_data = {}
    if 'Free Cash Flow' in all_data:
        cf_data['Free Cash Flow'] = [
            (all_data['Free Cash Flow'].get(y, None) or 0) * 1_000_000 if all_data['Free Cash Flow'].get(y) is not None else None
            for y in all_years
        ]

    def _build(data_dict):
        if not data_dict:
            return pd.DataFrame()
        df = pd.DataFrame(data_dict, index=col_dates).T
        df = df.apply(pd.to_numeric, errors='coerce')
        return df

    if 'Diluted EPS' in inc_data:
        inc_data['Basic EPS'] = inc_data['Diluted EPS']

    return _build(inc_data), _build(bal_data), _build(cf_data)

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
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(8)::before { content: '🧠 AI'; }
</style>
<div class="sidebar-logo">
    <span class="intelligent">The Intelligent</span><br>
    <span class="finance">Finance</span>
</div>
""", unsafe_allow_html=True)
page_choice = st.sidebar.radio("Tool:", [
    "🏠 Home",
    "📈 Compound Interest", 
    "📊 Stock Tracker", 
    "📁 My Portfolio", 
    "📰 Financial News", 
    "👑 Super Investors", 
    "🌍 Macro & Market", 
    "🔍 Stock Screener",
    "🧠 AI Insights"
], label_visibility="collapsed")


# ==========================================
# PAGE 0: HOME
# ==========================================
if page_choice == "🏠 Home":
    st.title("🏠 Market Dashboard")
    st.markdown("<p style='color: #8A929A; font-size: 16px; margin-bottom:20px;'>Live Snapshot of the S&P 500 Heavyweights</p>", unsafe_allow_html=True)
    
    # --- WATCHLIST SECTION ---
    with st.expander("⭐ My Watchlist", expanded=bool(st.session_state.get('watchlist'))):
        wl_c1, wl_c2, wl_c3 = st.columns([3, 1, 1])
        with wl_c1:
            new_watch_ticker = st.text_input("Ticker", key="wl_input", label_visibility="collapsed", placeholder="Add ticker to watchlist (e.g. NVDA)...").upper().strip()
        with wl_c2:
            if st.button("➕ Add", key="wl_add_btn", use_container_width=True) and new_watch_ticker:
                if new_watch_ticker not in st.session_state['watchlist']:
                    st.session_state['watchlist'].append(new_watch_ticker)
                    save_watchlist(st.session_state['watchlist'])
                    st.toast(f"{new_watch_ticker} added to watchlist!", icon="⭐")
                    st.rerun()
                else:
                    st.toast(f"{new_watch_ticker} is already in your watchlist", icon="⚠️")
        with wl_c3:
            if st.button("🗑️ Clear", key="wl_clear_btn", use_container_width=True) and st.session_state['watchlist']:
                st.session_state['watchlist'] = []
                save_watchlist([])
                st.rerun()
        
        if st.session_state['watchlist']:
            wl_prices = fetch_watchlist_prices(tuple(st.session_state['watchlist']))
            if wl_prices:
                wl_html = '<div style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px;">'
                for wl_tk in st.session_state['watchlist']:
                    if wl_tk in wl_prices:
                        wl_curr, wl_prev = wl_prices[wl_tk]
                        wl_chg = ((wl_curr - wl_prev) / wl_prev) * 100 if wl_prev != 0 else 0
                        wl_color = "#22c55e" if wl_chg >= 0 else "#ef4444"
                        wl_sign = "+" if wl_chg >= 0 else ""
                        wl_arrow = "▲" if wl_chg >= 0 else "▼"
                        wl_html += f'<div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-left: 3px solid {wl_color}; border-radius: 10px; padding: 14px 20px; min-width: 170px; flex: 1; max-width: 220px;"><div style="font-weight: 700; font-size: 15px; color: #3b82f6;">{wl_tk}</div><div style="font-size: 20px; font-weight: 700; margin-top: 6px;">${wl_curr:,.2f}</div><div style="color: {wl_color}; font-weight: 600; font-size: 14px; margin-top: 2px;">{wl_arrow} {wl_sign}{wl_chg:.2f}%</div></div>'
                    else:
                        wl_html += f'<div style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 14px 20px; min-width: 170px; flex: 1; max-width: 220px;"><div style="font-weight: 700; font-size: 15px; color: #3b82f6;">{wl_tk}</div><div style="font-size: 14px; color: #64748b; margin-top: 6px;">Data unavailable</div></div>'
                wl_html += '</div>'
                st.markdown(wl_html, unsafe_allow_html=True)
            
            # Remove buttons for each ticker
            st.write("")
            max_wl_cols = min(len(st.session_state['watchlist']), 8)
            wl_rem_cols = st.columns(max_wl_cols)
            for wi, wl_tk in enumerate(st.session_state['watchlist'][:8]):
                with wl_rem_cols[wi]:
                    if st.button(f"✕ {wl_tk}", key=f"wl_rem_{wl_tk}", use_container_width=True):
                        st.session_state['watchlist'].remove(wl_tk)
                        save_watchlist(st.session_state['watchlist'])
                        st.rerun()
    
    st.markdown("""
    <style>
    .market-table { width: 100%; border-collapse: collapse; color: #E2E8F0; font-family: 'Inter', sans-serif; }
    .market-table th { text-align: left; padding: 12px 15px; color: #64748b; font-size: 12px; text-transform: uppercase; border-bottom: 2px solid #334155; letter-spacing: 0.05em; }
    .market-table td { padding: 15px 15px; border-bottom: 1px solid #1e293b; font-size: 15px; vertical-align: middle; }
    .market-table tbody tr { transition: background-color 0.15s ease; }
    .market-table tbody tr:hover { background-color: rgba(255, 255, 255, 0.04); }
    .tk-name-link { color: #3b82f6; text-decoration: none; font-weight: 600; }
    .img-logo { width: 28px; height: 28px; border-radius: 50%; vertical-align: middle; margin-right: 12px; background-color: white; object-fit: contain; padding: 2px; }
    .pill { padding: 6px 14px; border-radius: 6px; font-weight: 600; font-size: 14px; display: inline-block; min-width: 85px; text-align: center; }
    .pill-green { background-color: rgba(34, 197, 94, 0.15); color: #22c55e; }
    .pill-red { background-color: rgba(239, 68, 68, 0.15); color: #ef4444; }
    .pill-neutral { background-color: rgba(148, 163, 184, 0.15); color: #94a3b8; }
    .home-filter-btn { display: inline-block; padding: 8px 20px; border-radius: 8px; font-weight: 600; font-size: 14px; margin-right: 8px; cursor: pointer; border: 1px solid #334155; color: #94a3b8; transition: all 0.2s ease; }
    .home-filter-active { background-color: #3b82f6; color: white; border-color: #3b82f6; }
    .mcap-val { color: #94a3b8; font-weight: 500; }
    .rank-num { color: #475569; font-weight: 600; font-size: 13px; margin-right: 10px; }
    </style>
    """, unsafe_allow_html=True)
    
    TOP_25_SP500_TICKERS = [
        "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "BRK-B", "TSLA", "AVGO", "WMT", 
        "LLY", "JPM", "V", "UNH", "XOM", "MA", "PG", "JNJ", "COST", "HD", "ABBV", "MRK", 
        "BAC", "CRM", "NFLX"
    ]
    
    # Mapping statico nome azienda -> dominio per loghi (evita chiamate tk.info lentissime)
    COMPANY_INFO = {
        "NVDA": ("NVIDIA", "nvidia.com"), "AAPL": ("Apple", "apple.com"), "MSFT": ("Microsoft", "microsoft.com"),
        "GOOGL": ("Alphabet", "abc.xyz"), "AMZN": ("Amazon.com", "amazon.com"), "META": ("Meta Platforms", "meta.com"),
        "BRK-B": ("Berkshire Hathaway", "berkshirehathaway.com"), "TSLA": ("Tesla", "tesla.com"),
        "AVGO": ("Broadcom", "broadcom.com"), "WMT": ("Walmart", "walmart.com"), "LLY": ("Eli Lilly", "lilly.com"),
        "JPM": ("JPMorgan Chase", "jpmorganchase.com"), "V": ("Visa", "visa.com"), "UNH": ("UnitedHealth", "unitedhealthgroup.com"),
        "XOM": ("Exxon Mobil", "exxonmobil.com"), "MA": ("Mastercard", "mastercard.com"),
        "PG": ("Procter & Gamble", "pg.com"), "JNJ": ("Johnson & Johnson", "jnj.com"),
        "COST": ("Costco", "costco.com"), "HD": ("Home Depot", "homedepot.com"),
        "ABBV": ("AbbVie", "abbvie.com"), "MRK": ("Merck", "merck.com"),
        "BAC": ("Bank of America", "bankofamerica.com"), "CRM": ("Salesforce", "salesforce.com"),
        "NFLX": ("Netflix", "netflix.com"),
    }
    
    SECTOR_MAP = {
        "NVDA": "Technology", "AAPL": "Technology", "MSFT": "Technology", "GOOGL": "Technology",
        "AMZN": "Consumer Cyclical", "META": "Technology", "BRK-B": "Financials", "TSLA": "Consumer Cyclical",
        "AVGO": "Technology", "WMT": "Consumer Defensive", "LLY": "Healthcare", "JPM": "Financials",
        "V": "Financials", "UNH": "Healthcare", "XOM": "Energy", "MA": "Financials",
        "PG": "Consumer Defensive", "JNJ": "Healthcare", "COST": "Consumer Defensive", "HD": "Consumer Cyclical",
        "ABBV": "Healthcare", "MRK": "Healthcare", "BAC": "Financials", "CRM": "Technology", "NFLX": "Communication Services",
    }
    
    if 'show_all_sp500' not in st.session_state:
        st.session_state.show_all_sp500 = False
    if 'home_filter' not in st.session_state:
        st.session_state.home_filter = "S&P 500"
        
    @st.cache_data(ttl=300)
    def fetch_home_data(ticker_tuple):
        """Hybrid: batch yf.download per i prezzi + fast_info parallelo per market cap."""
        import concurrent.futures
        import time as _time
        ticker_list = list(ticker_tuple)
        
        # STEP 1: Batch download prezzi (una sola chiamata HTTP per tutti)
        try:
            raw = yf.download(ticker_list, period="5d", progress=False, threads=True)
            if isinstance(raw.columns, pd.MultiIndex):
                batch_prices = raw['Close']
            else:
                batch_prices = raw[['Close']].rename(columns={'Close': ticker_list[0]}) if len(ticker_list) == 1 else raw['Close']
        except:
            batch_prices = pd.DataFrame()
        
        if batch_prices.empty:
            return pd.DataFrame()
        
        # Se è un solo ticker, yf.download ritorna una Series
        if isinstance(batch_prices, pd.Series):
            batch_prices = batch_prices.to_frame(name=ticker_list[0])
        
        # Identifica ticker con dati validi
        valid_tickers = []
        failed_tickers = []
        price_data = {}
        for tkr in ticker_list:
            if tkr not in batch_prices.columns:
                failed_tickers.append(tkr)
                continue
            series = batch_prices[tkr].dropna()
            if len(series) >= 2:
                curr = float(series.iloc[-1])
                prev = float(series.iloc[-2])
                pct = ((curr - prev) / prev) * 100 if prev != 0 else 0.0
                price_data[tkr] = (curr, pct)
                valid_tickers.append(tkr)
            else:
                failed_tickers.append(tkr)
        
        # Retry singolo per ticker rate-limited dal batch
        if failed_tickers:
            _time.sleep(0.5)
            for tkr in failed_tickers:
                try:
                    hist = yf.Ticker(tkr).history(period="5d")
                    if not hist.empty and len(hist) >= 2:
                        curr = float(hist['Close'].iloc[-1])
                        prev = float(hist['Close'].iloc[-2])
                        pct = ((curr - prev) / prev) * 100 if prev != 0 else 0.0
                        price_data[tkr] = (curr, pct)
                        valid_tickers.append(tkr)
                except:
                    pass
        
        if not valid_tickers:
            return pd.DataFrame()
        
        # STEP 2: Fetch market caps in parallelo con retry + throttle
        def get_mcap(tkr):
            for attempt in range(3):
                try:
                    mcap = float(yf.Ticker(tkr).fast_info.market_cap)
                    return tkr, mcap
                except:
                    _time.sleep(0.3 * (attempt + 1))
            return tkr, 0.0
        
        # Limita concorrenza per evitare rate-limit Yahoo Finance
        workers = min(15, len(valid_tickers))
        mcap_map = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            for tkr, mcap in executor.map(get_mcap, valid_tickers):
                mcap_map[tkr] = mcap
        
        # STEP 3: Assembla risultati
        results = []
        for tkr in valid_tickers:
            curr, pct = price_data[tkr]
            mcap = mcap_map.get(tkr, 0.0)
            
            if tkr in COMPANY_INFO:
                name, domain = COMPANY_INFO[tkr]
            else:
                name, domain = tkr, ""
            
            results.append({
                "Ticker": tkr, "Name": name, "Price": curr, 
                "Change": pct, "MarketCap": mcap, "Domain": domain
            })
        
        df = pd.DataFrame(results)
        if not df.empty:
            df.sort_values(by="MarketCap", ascending=False, inplace=True)
            df.reset_index(drop=True, inplace=True)
        return df

    @st.cache_data(ttl=3600*24)
    def get_full_sp500_list():
        """Scarica la lista completa S&P 500 da Wikipedia, con cleanup ticker."""
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        html_table = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
        raw_tickers = pd.read_html(io.StringIO(html_table))[0]['Symbol'].tolist()
        
        # Converti punti in trattini (es. BRK.B -> BRK-B, BF.B -> BF-B)
        cleaned = [t.replace('.', '-') for t in raw_tickers]
        
        # Rimuovi duplicati classe azioni (GOOG/GOOGL -> tieni solo GOOGL)
        seen_base = set()
        deduped = []
        for t in cleaned:
            base = t.split('-')[0] if t not in ('BRK-B', 'BF-B') else t
            # Gestione specifica Alphabet: GOOG e GOOGL
            if base == 'GOOG' and 'GOOGL' in cleaned:
                if t != 'GOOGL':
                    continue  # Salta GOOG, tieni solo GOOGL
            if t not in deduped:
                deduped.append(t)
        return deduped

    @st.cache_data(ttl=3600*24)
    def get_sp500_sectors():
        """Fetch GICS sector mapping from Wikipedia for all S&P 500 tickers."""
        try:
            url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
            html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
            df_wiki = pd.read_html(io.StringIO(html))[0]
            return dict(zip(df_wiki['Symbol'].str.replace('.', '-', regex=False), df_wiki['GICS Sector']))
        except:
            return {}

    # --- Filter Tabs ---
    filter_col1, filter_col2, filter_col3 = st.columns([1, 1, 1])
    with filter_col1:
        if st.button("📊 S&P 500", key="filter_sp500", type="primary" if st.session_state.home_filter == "S&P 500" else "secondary"):
            st.session_state.home_filter = "S&P 500"
            st.rerun()
    with filter_col2:
        if st.button("🟢 Gainers", key="filter_gainers", type="primary" if st.session_state.home_filter == "Gainers" else "secondary"):
            st.session_state.home_filter = "Gainers"
            st.rerun()
    with filter_col3:
        if st.button("🔴 Losers", key="filter_losers", type="primary" if st.session_state.home_filter == "Losers" else "secondary"):
            st.session_state.home_filter = "Losers"
            st.rerun()
    
    st.write("")

    tks_to_fetch = TOP_25_SP500_TICKERS
    
    if st.session_state.show_all_sp500:
        with st.spinner(f"Scaricamento composizione intero S&P 500... | '{random.choice(WALL_STREET_QUOTES)}'"):
            try:
                tks_to_fetch = get_full_sp500_list()
            except:
                st.error("Wikipedia Data non disponibile.")

    with st.spinner(f"Sincronizzazione dati live... | '{random.choice(WALL_STREET_QUOTES)}'"):
        df_display = fetch_home_data(tuple(tks_to_fetch))
    
    # Applica filtro Gainers/Losers
    if not df_display.empty:
        if st.session_state.home_filter == "Gainers":
            df_display = df_display[df_display['Change'] > 0].sort_values(by='Change', ascending=False)
        elif st.session_state.home_filter == "Losers":
            df_display = df_display[df_display['Change'] < 0].sort_values(by='Change', ascending=True)
    
    # Market Summary bar
    if not df_display.empty:
        avg_change = df_display['Change'].mean()
        total_mcap = df_display['MarketCap'].sum()
        gainers_count = (df_display['Change'] > 0).sum()
        losers_count = (df_display['Change'] < 0).sum()
        
        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("Stocks Loaded", f"{len(df_display)}")
        sm2.metric("Avg Change", f"{avg_change:+.2f}%")
        sm3.metric("Gainers", f"{gainers_count}", delta=f"{gainers_count}", delta_color="normal")
        sm4.metric("Losers", f"{losers_count}", delta=f"-{losers_count}", delta_color="normal")
        st.write("")
        
    if not df_display.empty:
        html_str = '<table class="market-table"><thead><tr><th style="width:5%">#</th><th style="width:30%">NAME</th><th style="width:15%">TICKER</th><th style="width:18%">LAST PRICE</th><th style="width:17%">PRICE CHANGE</th><th style="width:15%">MARKET CAP</th></tr></thead><tbody>'
        for idx, (_, row) in enumerate(df_display.iterrows(), 1):
            tkr = row['Ticker']
            name = row['Name']
            if len(name) > 28: name = name[:25] + "..."
            price = row['Price']
            change = row['Change']
            mcap = row['MarketCap']
            domain = row['Domain']
            
            if mcap >= 1e12: mcap_str = f"${mcap/1e12:.3f}T"
            elif mcap >= 1e9: mcap_str = f"${mcap/1e9:.3f}B"
            elif mcap >= 1e6: mcap_str = f"${mcap/1e6:.1f}M"
            else: mcap_str = "N/A"
            
            if change > 0:
                pill_class = "pill-green"
                sign = "+"
            elif change < 0:
                pill_class = "pill-red"
                sign = ""
            else:
                pill_class = "pill-neutral"
                sign = ""
            
            if domain:
                logo_img = f"<img src='https://logo.clearbit.com/{domain}' class='img-logo' onerror=\"this.onerror=null; this.src='https://ui-avatars.com/api/?name={tkr}&background=1e293b&color=3b82f6&rounded=true&font-size=0.33';\">"
            else:
                logo_img = f"<img src='https://ui-avatars.com/api/?name={tkr}&background=1e293b&color=3b82f6&rounded=true&font-size=0.33' class='img-logo'>"
            
            html_str += f'''<tr>
                <td><span class="rank-num">{idx}</span></td>
                <td>{logo_img}<strong>{name}</strong></td>
                <td><span class="tk-name-link">{tkr}</span></td>
                <td><strong>${price:,.2f}</strong></td>
                <td><span class="pill {pill_class}">{sign}{change:.2f}%</span></td>
                <td><span class="mcap-val">{mcap_str}</span></td>
            </tr>'''
        html_str += "</tbody></table>"
        st.markdown(html_str, unsafe_allow_html=True)
    else:
        if st.session_state.home_filter != "S&P 500":
            st.info(f"Nessun titolo trovato nella categoria '{st.session_state.home_filter}' al momento.")
        else:
            st.error("Nessun dato di mercato disponibile al momento.")
        
    st.write("")
    if st.session_state.show_all_sp500:
        if st.button("🔼 Show Top 25 Only", key="btn_show_less", use_container_width=True):
            st.session_state.show_all_sp500 = False
            st.rerun()
    else:
        if st.button("⬇️ See all S&P 500", key="btn_see_all", use_container_width=True):
            st.session_state.show_all_sp500 = True
            st.rerun()

    # --- S&P 500 HEATMAP ---
    if not df_display.empty:
        st.divider()
        st.subheader("🗺️ Market Heatmap")
        st.caption("Size = Market Cap | Color = Daily Change %")
        
        # Get sector data
        try:
            wiki_sectors = get_sp500_sectors()
        except:
            wiki_sectors = {}
        
        df_heat = df_display.copy()
        df_heat['Sector'] = df_heat['Ticker'].map(
            lambda t: wiki_sectors.get(t, SECTOR_MAP.get(t, 'Other'))
        )
        df_heat = df_heat[df_heat['MarketCap'] > 0]
        
        if not df_heat.empty:
            df_heat['Root'] = 'S&P 500'
            
            fig_heatmap = px.treemap(
                df_heat,
                path=['Root', 'Sector', 'Ticker'],
                values='MarketCap',
                color='Change',
                color_continuous_scale=[
                    [0.0, '#b71c1c'], [0.2, '#e53935'],
                    [0.4, '#616161'], [0.5, '#424242'], [0.6, '#616161'],
                    [0.8, '#43a047'], [1.0, '#1b5e20']
                ],
                range_color=[-4, 4],
            )
            fig_heatmap.update_traces(
                texttemplate='<b>%{label}</b><br>%{color:+.2f}%',
                textfont=dict(size=13),
                marker=dict(cornerradius=3)
            )
            fig_heatmap.update_layout(
                margin=dict(t=30, b=0, l=0, r=0),
                height=550,
                coloraxis_colorbar=dict(
                    title="Change %",
                    ticksuffix="%",
                    thickness=15,
                    len=0.6
                )
            )
            st.plotly_chart(fig_heatmap, use_container_width=True)

# ==========================================
# PAGE 1: COMPOUND INTEREST
# ==========================================
elif page_choice == "📈 Compound Interest":
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

    with st.form("stock_tracker_form", enter_to_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        with col1: ticker_input = st.text_input("Stock Ticker", value="KO").upper()
        with col2: invested_cap = st.number_input("Initial Investment ($)", min_value=100.0, value=1000.0)
        with col3: backtest_years = st.slider("Years of History", min_value=1, max_value=20, value=10)
        with col4: benchmark_ticker = st.text_input("Benchmark (Compare)", value="SPY").upper()

        # Salviamo i parametri in sessione per non perderli al ricarico della pagina (es. al toggle DRIP)
        submitted = st.form_submit_button("🚀 Run Deep Analysis", type="primary", use_container_width=True)
        if submitted:
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
                val_tpe = info.get('trailingPE')
                m2.metric("P/E (Trailing)", round(val_tpe, 2) if isinstance(val_tpe, (int, float)) else 'N/A')
                m3.metric("EPS (TTM)", f"${info.get('trailingEps'):.2f}" if info.get('trailingEps') else 'N/A')
                m4.metric("Div Rate", f"${info.get('dividendRate'):.2f}" if info.get('dividendRate') else 'N/A')

                st.write("")
                m5, m6, m7, m8 = st.columns(4)
                m5.metric("Current Price", f"${rt_price:,.2f}", f"{change:.2f}%")
                val_fpe = info.get('forwardPE')
                m6.metric("P/E (Forward)", round(val_fpe, 2) if isinstance(val_fpe, (int, float)) else 'N/A')
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

                tab_price, tab_divs, tab_mc, tab_holders, tab_fhealth, tab_funds, tab_dcf = st.tabs([
                    "📊 Price & Tech Analysis", 
                    "💰 Dividends & Returns", 
                    "🎲 Projections", 
                    "🏦 Ownership", 
                    "📈 Financial Health",
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
                    
                    # --- 3D MONTE CARLO PROBABILITY SURFACE ---
                    # Appiattiamo le simulazioni per formare una matrice di densità 2D
                    time_idx = np.repeat(np.arange(sim_days), num_sim)
                    price_vals = sims.flatten()
                    
                    try:
                        H, xedges, yedges = np.histogram2d(time_idx, price_vals, bins=[50, 50])
                        H_z = H.T
                        
                        # Sfoca la superficie per renderla più 'rocciosa' e naturale se c'è scipy
                        try:
                            from scipy.ndimage import gaussian_filter
                            H_z = gaussian_filter(H_z, sigma=1.5)
                        except:
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

                # --- TAB 4: OWNERSHIP ---
                with tab_holders:
                    st.subheader("Major Shareholders")
                    col_h1, col_h2 = st.columns(2)
                    
                    with col_h1:
                        st.write("**Share Ownership Breakdown**")
                        try:
                            holders = stock.major_holders
                        except:
                            holders = None
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
                        try:
                            inst_holders = stock.institutional_holders
                        except:
                            inst_holders = None
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

                # --- TAB 5: FINANCIAL HEALTH (VISUAL CHARTS) ---
                with tab_fhealth:
                    st.subheader("📈 Financial Health — Trend Analysis")
                    st.markdown("<p style='color: #8A929A; margin-top:-10px; margin-bottom:20px;'>Andamento storico dei principali indicatori fondamentali anno per anno.</p>", unsafe_allow_html=True)

                    # --- Fetch 10+ Years Financial Data (Multi-Source) ---
                    _FMP_API_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"

                    # Source 1: Macrotrends (10-15 anni, scraping)
                    mt_inc, mt_bal, mt_cash = fetch_macrotrends_financials(a_ticker, limit_years=10)
                    # Source 2: FMP API (5 anni)
                    fmp_inc, fmp_bal, fmp_cash = fetch_fmp_financials(a_ticker, _FMP_API_KEY)
                    # Source 3: Yahoo Finance Extended (5-8 anni)
                    yf_inc, yf_bal, yf_cash = fetch_financials_extended(a_ticker)

                    # Combine: macrotrends primary -> FMP fills gaps -> yfinance fills remaining
                    if not mt_inc.empty:
                        fh_inc = _merge_financial_dfs(mt_inc, _merge_financial_dfs(fmp_inc, yf_inc))
                        fh_bal = _merge_financial_dfs(mt_bal, _merge_financial_dfs(fmp_bal, yf_bal))
                        fh_cash = _merge_financial_dfs(mt_cash, _merge_financial_dfs(fmp_cash, yf_cash))
                        n_years = len(fh_inc.columns)
                        st.caption(f"📡 Sorgente: **Multi-Source ({n_years} anni)**")
                    elif not fmp_inc.empty:
                        fh_inc = _merge_financial_dfs(fmp_inc, yf_inc)
                        fh_bal = _merge_financial_dfs(fmp_bal, yf_bal)
                        fh_cash = _merge_financial_dfs(fmp_cash, yf_cash)
                        n_years = len(fh_inc.columns)
                        st.caption(f"📡 Sorgente: **FMP + Yahoo Finance ({n_years} anni)**")
                    elif yf_inc is not None and not yf_inc.empty:
                        fh_inc, fh_bal, fh_cash = yf_inc, yf_bal, yf_cash
                        n_years = len(fh_inc.columns)
                        st.caption(f"📡 Sorgente: **Yahoo Finance ({n_years} anni)**")
                    else:
                        fh_inc, fh_bal, fh_cash = pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
                        st.warning("⚠️ Nessuna sorgente dati disponibile.")

                    # Helper: extract a row from a financial statement, sorted by year
                    def _extract_annual_series(df, row_name):
                        """Return a sorted Series (index=year, values=float) or None."""
                        if df is None or df.empty:
                            return None
                        if row_name not in df.index:
                            return None
                        row = df.loc[row_name].dropna()
                        row = pd.to_numeric(row, errors='coerce').dropna()
                        if row.empty:
                            return None
                        # Convert column dates to year labels
                        row.index = [c.year if hasattr(c, 'year') else str(c) for c in row.index]
                        # Deduplicate by taking the most recent entry for each year
                        row = row.groupby(level=0).last()
                        return row.sort_index()

                    # --- Shared chart layout template ---
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

                    # ──── CHART 1 & 2: Revenue + Net Income ────
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

                    # ──── CHART 3 & 4: EPS + Free Cash Flow ────
                    # EPS: derive from Net Income / shares outstanding (basic)
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

                    # ──── CHART 5 & 6: Debt vs Equity + Margins ────
                    total_debt = _extract_annual_series(fh_bal, 'Total Debt')
                    total_equity = _extract_annual_series(fh_bal, 'Stockholders Equity')
                    if total_equity is None:
                        total_equity = _extract_annual_series(fh_bal, 'Total Stockholders Equity')

                    # Margins from income statement
                    gross_profit = _extract_annual_series(fh_inc, 'Gross Profit')
                    operating_income = _extract_annual_series(fh_inc, 'Operating Income')

                    ch_col5, ch_col6 = st.columns(2)

                    with ch_col5:
                        if total_debt is not None and total_equity is not None:
                            has_any_chart = True
                            # Align on common years
                            common_years = sorted(set(total_debt.index) & set(total_equity.index))
                            if len(common_years) >= 2:
                                fig_de = go.Figure()
                                fig_de.add_trace(go.Bar(
                                    x=[str(y) for y in common_years],
                                    y=[total_debt[y] for y in common_years],
                                    name='Total Debt',
                                    marker_color='#ef4444',
                                    text=[format_large_numbers(total_debt[y]) for y in common_years],
                                    textposition='outside', textfont=dict(size=10)
                                ))
                                fig_de.add_trace(go.Bar(
                                    x=[str(y) for y in common_years],
                                    y=[total_equity[y] for y in common_years],
                                    name='Equity',
                                    marker_color='#22c55e',
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
                        # Compute margins %
                        if revenue is not None and len(revenue) >= 2:
                            fig_margins = go.Figure()
                            margin_plotted = False

                            if gross_profit is not None:
                                common = sorted(set(revenue.index) & set(gross_profit.index))
                                if len(common) >= 2:
                                    gm = [(gross_profit[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=gm,
                                        name='Gross Margin %', mode='lines+markers',
                                        line=dict(color='#3b82f6', width=2.5),
                                        marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if operating_income is not None:
                                common = sorted(set(revenue.index) & set(operating_income.index))
                                if len(common) >= 2:
                                    om = [(operating_income[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=om,
                                        name='Operating Margin %', mode='lines+markers',
                                        line=dict(color='#f59e0b', width=2.5),
                                        marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if net_income is not None:
                                common = sorted(set(revenue.index) & set(net_income.index))
                                if len(common) >= 2:
                                    nm = [(net_income[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=nm,
                                        name='Net Margin %', mode='lines+markers',
                                        line=dict(color='#22c55e', width=2.5),
                                        marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if margin_plotted:
                                has_any_chart = True
                                fig_margins.update_layout(
                                    title='📐 Profitability Margins (%)',
                                    yaxis_title='Margin %',
                                    **_chart_layout
                                )
                                st.plotly_chart(fig_margins, use_container_width=True)
                            else:
                                st.info("Margin data not available.")
                        else:
                            st.info("Revenue data insufficient for margin calculation.")

                    # ──── CHART 7 (Full Width): EBITDA Trend ────
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

                # --- TAB 6: EARNINGS & FUNDS ---
                with tab_funds:
                    st.subheader("📅 Upcoming Earnings & Estimates")
                    try:
                        earn_data = stock.earnings_dates
                    except Exception:
                        earn_data = None
                    if earn_data is not None:
                        st.dataframe(earn_data, use_container_width=True)
                    else:
                        st.info("Upcoming earnings dates not available.")
                    
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
                            
                            if discount_rate <= terminal_growth:
                                st.error("⚠️ Errore Matematico: Il Tasso di Sconto (WACC) deve essere strettamente maggiore del Tasso Terminale per calcolare il Terminal Value.")
                            else:
                                if recent_fcf < 0:
                                    st.warning("⚠️ L'azienda presenta un Free Cash Flow recente negativo. Il Fair Value risultante potrebbe essere negativo o inaffidabile, poiché il modello sconta perdite anziché profitti.")
                                
                                pv_fcf = sum([recent_fcf * (1 + fcf_growth_rate)**t / (1 + discount_rate)**t for t in range(1, 6)])
                                fcf_year_5 = recent_fcf * (1 + fcf_growth_rate)**5
                                tv = (fcf_year_5 * (1 + terminal_growth)) / (discount_rate - terminal_growth)
                                pv_tv = tv / (1 + discount_rate)**5
                                
                                enterprise_value = pv_fcf + pv_tv
                                total_debt = info.get('totalDebt') or 0
                                total_cash = info.get('totalCash') or 0
                                net_debt = total_debt - total_cash
                                equity_value = enterprise_value - net_debt
                                
                                raw_fair_value = equity_value / shares_out_dcf
                                fair_value = max(0, raw_fair_value)
                                
                                if raw_fair_value < 0:
                                    st.info(f"Nota: Il valore teorico del capitale netto sarebbe negativo (${raw_fair_value:,.2f}), limitato a zero nel calcolo.")
                                
                                st.metric("Fair Value per Azione Stimato", f"${fair_value:,.2f}")
                                margin_of_safety = ((fair_value - rt_price) / fair_value) if fair_value > 0 else 0
                                st.metric("Margine di Sicurezza", f"{margin_of_safety*100:.2f}%")
                                
                                if fair_value == 0:
                                    st.error("🔴 Il Fair Value teorico è zero (o inferiore) a causa di flussi di cassa negativi o debito eccessivo.")
                                elif margin_of_safety > 0:
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

        # --- CORRELATION MATRIX ---
        st.divider()
        st.subheader("🔗 Correlation Matrix")
        st.write("Correlazioni tra i rendimenti giornalieri dei tuoi titoli (ultimi 12 mesi). Valori vicini a **1.0** indicano asset che si muovono insieme — poca diversificazione reale.")
        
        unique_portfolio_tickers = list(set(tickers))
        if len(unique_portfolio_tickers) >= 2:
            try:
                corr_data = yf.download(unique_portfolio_tickers, period="1y", progress=False)['Close']
                if isinstance(corr_data, pd.Series):
                    st.info("Aggiungi almeno 2 titoli diversi per la matrice di correlazione.")
                elif not corr_data.empty:
                    corr_returns = corr_data.pct_change().dropna()
                    corr_matrix = corr_returns.corr()
                    
                    fig_corr = px.imshow(
                        corr_matrix,
                        text_auto='.2f',
                        color_continuous_scale=[
                            [0.0, '#1a237e'], [0.25, '#42a5f5'],
                            [0.5, '#e0e0e0'],
                            [0.75, '#ef5350'], [1.0, '#b71c1c']
                        ],
                        aspect='auto',
                        zmin=-1, zmax=1
                    )
                    fig_corr.update_layout(
                        margin=dict(t=30, b=0, l=0, r=0),
                        height=max(350, len(corr_matrix) * 50),
                        coloraxis_colorbar=dict(title="ρ", thickness=15)
                    )
                    st.plotly_chart(fig_corr, use_container_width=True)
                    
                    # Highlight highly correlated pairs
                    high_corr_pairs = []
                    for i in range(len(corr_matrix.columns)):
                        for j in range(i+1, len(corr_matrix.columns)):
                            val = corr_matrix.iloc[i, j]
                            if abs(val) >= 0.75:
                                high_corr_pairs.append((corr_matrix.columns[i], corr_matrix.columns[j], val))
                    
                    if high_corr_pairs:
                        st.warning("⚠️ **Coppie ad alta correlazione (|ρ| ≥ 0.75):**")
                        for t1, t2, rho in sorted(high_corr_pairs, key=lambda x: abs(x[2]), reverse=True):
                            emoji = "🔴" if rho > 0 else "🔵"
                            st.markdown(f"{emoji} **{t1}** ↔ **{t2}**: ρ = {rho:.3f}")
                    else:
                        st.success("✅ Buona diversificazione! Nessuna coppia con correlazione superiore a ±0.75.")
            except Exception as e:
                st.error(f"Errore nel calcolo delle correlazioni: {e}")
        else:
            st.info("Aggiungi almeno 2 titoli al portafoglio per visualizzare la matrice di correlazione.")

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
                                
                                st.write("")
                                st.subheader("🌌 3D Risk/Return Constellation")
                                
                                # Prep 3D scatter data
                                asset_vols = ret_df.std() * np.sqrt(252)
                                asset_rets = mean_ret
                                opt_weights_pct = (opt_weights * 100).round(2)
                                
                                df_3d = pd.DataFrame({
                                    "Ticker": active_tickers,
                                    "Volatility (Risk) %": asset_vols * 100,
                                    "Expected Return %": asset_rets * 100,
                                    "Optimal Weight %": opt_weights_pct
                                })
                                
                                fig_3d = px.scatter_3d(
                                    df_3d, 
                                    x='Volatility (Risk) %', 
                                    y='Expected Return %', 
                                    z='Optimal Weight %',
                                    color='Optimal Weight %',
                                    size=np.maximum(df_3d['Optimal Weight %'], 1),
                                    hover_name="Ticker",
                                    color_continuous_scale=px.colors.sequential.Viridis,
                                    opacity=0.8
                                )
                                fig_3d.update_layout(
                                    margin=dict(l=0, r=0, b=0, t=0), height=500,
                                    scene=dict(
                                        xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                        yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                        zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
                                    )
                                )
                                st.plotly_chart(fig_3d, use_container_width=True)
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

    # --- AI PORTFOLIO TREEMAP ---
    if st.session_state.get('portfolio'):
        with st.expander("🌌 Genera S&P AI Sentiment Treemap (Sperimentale)", expanded=False):
            st.write("Crea una mappa di calore del tuo portafoglio analizzando il sentiment generale di mercato tramite l'AI di Gemma.")
            if st.button("🚀 Esegui Analisi Treemap"):
                with st.spinner(f"Estrazione news e calcolo inferenziale Sentiment in corso... | '{random.choice(WALL_STREET_QUOTES)}'"):
                    tickers = [item['ticker'] for item in st.session_state['portfolio']]
                    prices_dict = get_batch_prices(list(set(tickers))) if tickers else {}
                    
                    tree_data = []
                    for item in st.session_state['portfolio']:
                        tk = item['ticker']
                        shares = item['shares']
                        
                        current_price = prices_dict.get(tk, 1.0)
                        if isinstance(current_price, pd.Series): current_price = current_price.iloc[0]
                        valore_monetario = shares * current_price
                        
                        tk_news = fetch_news(tk)
                        sentiment_score = 0
                        valid_news = 0
                        
                        if tk_news:
                            for n in tk_news[:8]: # Ampliato a 8 notizie come richiesto
                                # Gestizione formati news misti
                                title = ""
                                if 'content' in n: title = n['content'].get('title', '')
                                else: title = n.get('title', '')
                                
                                if title:
                                    lbl = get_sentiment(title)
                                    if "Positive" in lbl: sentiment_score += 1
                                    elif "Negative" in lbl: sentiment_score -= 1
                                    valid_news += 1
                        
                        avg_score = (sentiment_score / valid_news) if valid_news > 0 else 0
                        
                        if avg_score > 0.3: human_lbl = "🟢 Rialzista"
                        elif avg_score < -0.3: human_lbl = "🔴 Ribassista"
                        else: human_lbl = "⚪ Incerto/Neutro"
                        
                        tree_data.append({"Ticker": tk, "Valore ($)": max(valore_monetario, 0.01), "AI Score": avg_score, "Giudizio": human_lbl})
                    
                    df_tree = pd.DataFrame(tree_data)
                    if not df_tree.empty:
                        df_tree["Portafoglio"] = "Mio Portafoglio" # Crea il Nodo Root genitore per Plotly
                        fig_tree = px.treemap(
                            df_tree, 
                            path=['Portafoglio', 'Ticker'], 
                            values='Valore ($)', 
                            color='AI Score',
                            hover_name='Ticker',
                            hover_data={"AI Score": False, "Giudizio": True, "Valore ($)": ':$,.2f'},
                            color_continuous_scale=[
                                [0.0, '#E74C3C'], [0.35, '#E74C3C'],  # Da -1.0 a -0.3 (Rosso)
                                [0.35, '#2E2E2E'], [0.65, '#2E2E2E'], # Da -0.3 a 0.3 (Grigio Scuro/Neutro)
                                [0.65, '#27AE60'], [1.0, '#27AE60']   # Da 0.3 a 1.0 (Verde)
                            ],
                            range_color=[-1, 1],
                            title="AI Portfolio Sentiment Heatmap (Proporzionata per Capitale Investito)"
                        )
                        st.plotly_chart(fig_tree, use_container_width=True)
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
    st.subheader("💡 Terminale AI Conversazionale (RAG sulle Notizie)")
    st.write("Interroga Gemma simulando l'esperienza di un terminale avanzato usando le notizie caricate qui sopra come base di conoscenza.")
    
    if 'chat_history' not in st.session_state:
        st.session_state['chat_history'] = []

    # Rendering dei messaggi passati (se stiamo navigando tra i tab, si mantengono)
    for msg in st.session_state['chat_history']:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Elemento nativo nativo Chat Input di Streamlit
    if prompt := st.chat_input("Es. 'Perché il titolo è crollato?' oppure 'Fai un riassunto sulle acquisizioni recenti...'"):
        # Salva la logica utente
        st.session_state['chat_history'].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Risposta IA
        with st.chat_message("assistant"):
            if st.session_state.get('news_contexts'):
                with st.spinner(f"Riflessione quantitativa profonda... | '{random.choice(WALL_STREET_QUOTES)}'"):
                    ctx_str = "\n".join(st.session_state['news_contexts'][:15])
                    ans = ask_financial_chatbot(prompt, ctx_str)
                    st.markdown(ans)
                    st.session_state['chat_history'].append({"role": "assistant", "content": ans})
            else:
                warning_msg = "Attenzione: Cerca prima le notizie del titolo usando la barra di ricerca in alto, altrimenti Gemma non avrà alcun contesto su cui basarsi."
                st.warning(warning_msg)
                st.session_state['chat_history'].append({"role": "assistant", "content": warning_msg})

# ==========================================
# ==========================================
# PAGE 5: MACRO & MARKET
# ==========================================
elif page_choice == "🌍 Macro & Market":
    st.title("🌍 Macro & Market Pulse")
    st.markdown(f"<p style='color: #8A929A; font-style: italic; font-size: 18px;'>« Governments don't rule the world, Goldman Sachs rules the world. »</p>", unsafe_allow_html=True)
    st.divider()
    
    with st.spinner(f"Acquisizione dati macroeconomici... | '{random.choice(WALL_STREET_QUOTES)}'"):
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
            with st.spinner(f"Scansione parallela di {len(sp500_tickers)} titoli S&P 500 (15-20 sec)... | '{random.choice(WALL_STREET_QUOTES)}'"):
                

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
                    
                    if len(df_screen) >= 4:
                        st.subheader("🧲 K-Means AI Clustering (S&P 500)")
                        st.write("Aggreghiamo matematicamente queste aziende in cluster spaziali in base al loro DNA finanziario (P/E, Dividendo, Grandezza).")
                        with st.spinner("Addestramento modello ML K-Means in puro NumPy..."):
                            # Preparazione e normalizzazione dati
                            data = df_screen[['P/E', 'Div Yield %', 'Market Cap (B)']].values
                            # Prevenzione division by zero sui dev.std
                            std_devs = np.std(data, axis=0)
                            std_devs[std_devs == 0] = 1 
                            data_norm = (data - np.mean(data, axis=0)) / std_devs
                            
                            k = min(4, len(df_screen))
                            np.random.seed(42)
                            centroids = data_norm[np.random.choice(data_norm.shape[0], k, replace=False)]
                            
                            for _ in range(100): # Hard cap a 100 iterazioni
                                distances = np.sqrt(((data_norm - centroids[:, np.newaxis])**2).sum(axis=2))
                                labels = np.argmin(distances, axis=0)
                                new_centroids = np.array([data_norm[labels == i].mean(axis=0) if len(data_norm[labels == i])>0 else centroids[i] for i in range(k)])
                                if np.allclose(centroids, new_centroids): break
                                centroids = new_centroids
                                
                            df_screen['Cluster ID'] = [f"Ammasso {L+1}" for L in labels]
                            
                            fig_clust = px.scatter_3d(
                                df_screen, x='P/E', y='Div Yield %', z='Market Cap (B)',
                                color='Cluster ID', hover_name='Ticker', hover_data=['Azienda'],
                                title="Costellazione S&P 500 Segmentata",
                                color_discrete_sequence=px.colors.qualitative.Bold
                            )
                            fig_clust.update_layout(
                                margin=dict(l=0, r=0, b=0, t=30), height=600,
                                scene=dict(
                                    xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
                                )
                            )
                            st.plotly_chart(fig_clust, use_container_width=True)
                else:
                    st.warning("Nessuna azienda rispetta queste query severe!")

# ==========================================
# PAGE 7: SUPER INVESTORS
# ==========================================
elif page_choice == "👑 Super Investors":
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
            
            if st.button("🌌 Esplora Galassia 3D Super Investitori", type="primary"):
                with st.spinner(f"Calcolo Rischio/Rendimento su dati in blocco a 1 anno... | '{random.choice(WALL_STREET_QUOTES)}'"):
                    try:
                        all_tickers = []
                        inv_owner = []
                        allocs = []
                        for inv, port in portfolio_details.items():
                            for item in port:
                                if item['Ticker'] != 'ALTRI':
                                    all_tickers.append(item['Ticker'])
                                    inv_owner.append(inv)
                                    allocs.append(item['Allocazione %'])
                        
                        unique_tkrs = list(set(all_tickers))
                        data_1y = yf.download(unique_tkrs, period="1y", progress=False)['Close']
                        
                        if not data_1y.empty:
                            if isinstance(data_1y, pd.Series):
                                rets_1y = data_1y.to_frame().pct_change().dropna()
                            else:
                                rets_1y = data_1y.pct_change().dropna()
                                
                            ann_ret = (rets_1y.mean() * 252) * 100
                            ann_vol = (rets_1y.std() * np.sqrt(252)) * 100
                            
                            df_galaxy = pd.DataFrame({
                                "Ticker": all_tickers,
                                "Investitore": inv_owner,
                                "Allocazione %": allocs
                            })
                            
                            df_galaxy["Rendimento Annuo %"] = df_galaxy["Ticker"].map(ann_ret).fillna(0)
                            df_galaxy["Volatilità %"] = df_galaxy["Ticker"].map(ann_vol).fillna(0)
                            
                            fig_gal = px.scatter_3d(
                                df_galaxy, x="Volatilità %", y="Rendimento Annuo %", z="Allocazione %",
                                color="Investitore", hover_name="Ticker", size="Allocazione %",
                                size_max=40, opacity=0.8,
                                title="Galassia Costellazioni 13F (Rischio vs Rendimento vs Peso)",
                                color_discrete_sequence=px.colors.qualitative.Alphabet
                            )
                            fig_gal.update_layout(
                                margin=dict(l=0, r=0, b=0, t=30), height=600,
                                scene=dict(
                                    xaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    yaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    zaxis=dict(backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
                                )
                            )
                            st.plotly_chart(fig_gal, use_container_width=True)
                        else:
                            st.error("Errore download Yahoo Finance.")
                    except Exception as e:
                        st.error(f"Errore rendering Galassia: {e}")
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


# ==========================================
# PAGE: AI INSIGHTS & REPORTING
# ==========================================
def render_ai_insights():
    """Renders the AI Insights & Reporting UI translated from React."""
    
    # SVGs for Icons
    sparkles_svg = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/><path d="M5 3v4"/><path d="M19 17v4"/><path d="M3 5h4"/><path d="M17 19h4"/></svg>'
    filetext_svg = '<svg class="w-full h-full" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>'
    download_svg = '<svg class="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
    alert_svg = '<svg class="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    network_svg = '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="16" y="16" width="6" height="6" rx="1"/><rect x="2" y="16" width="6" height="6" rx="1"/><rect x="9" y="2" width="6" height="6" rx="1"/><path d="M5 16v-3a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v3"/><path d="M12 11V8"/></svg>'
    leaf_svg = '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg>'
    rocket_svg = '<svg class="w-7 h-7" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.71-2.13.09-3.05a3.91 3.91 0 0 0-3.09-.95Z"/><path d="M12 12 2.5 21.5"/><path d="m11 2 9 2 2 9-9 9-2-9-9-2 9-9Z"/><path d="M13 8a2 2 0 1 0-4 0 2 2 0 0 0 4 0Z"/></svg>'

    # Chart Bars Generation
    bars_html = "".join([f'<div class="chart-bar" style="height: {h}%"></div>' for h in [40, 60, 30, 80, 50, 90, 70, 40, 60, 80, 50]])

    html_content = f"""
    <div class="ai-report-container space-y-12">
      <header style="margin-bottom: 3rem;">
        <div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem;">
          <div style="width: 2.5rem; height: 2px; background-color: var(--primary-navy);"></div>
          <span class="font-label" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.4em; color: var(--slate-500); font-weight: 800;">Q3 Strategic Intelligence</span>
        </div>
        <h2 style="font-size: 3rem; font-weight: 800; letter-spacing: -0.025em; margin-bottom: 1.25rem; line-height: 1.1;">AI Insights & Reporting</h2>
        <p style="color: var(--slate-500); font-size: 1.125rem; max-width: 48rem; line-height: 1.625;">Advanced algorithmic synthesis of your institutional ledger. This report highlights key fiscal pivots, risk vectors, and expansionary opportunities identified by the Sovereign engine.</p>
      </header>

      <div class="ai-grid">
        <section class="lg-col-span-8 bg-white rounded-3xl p-12 editorial-shadow" style="position: relative; overflow: hidden;">
          <div style="position: absolute; top: 0; right: 0; width: 20rem; height: 20rem; background-color: var(--slate-100); border-radius: 9999px; transform: translate(50%, -50%); opacity: 0.3;"></div>
          
          <div style="position: relative; z-index: 10;">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2.5rem;">
              <div>
                <span class="font-label" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--orange-600); font-weight: 800; margin-bottom: 0.75rem; display: block;">Executive Editorial</span>
                <h3 style="font-size: 2.25rem; font-weight: 800; letter-spacing: -0.025em; line-height: 1.1; max-width: 36rem;">Market Outlook: Resilience in Volatility</h3>
              </div>
              <div class="bg-slate-100 rounded-xl" style="padding: 0.625rem 1.25rem; display: flex; align-items: center; gap: 0.75rem;">
                <div style="color: var(--primary-navy); fill: rgba(15, 23, 42, 0.1);">{sparkles_svg}</div>
                <span style="font-size: 10px; font-family: 'Outfit', sans-serif; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em;">Live Analysis</span>
              </div>
            </div>

            <div class="editorial-columns" style="color: var(--slate-600); line-height: 1.8; font-size: 15px;">
              <p style="margin-bottom: 2rem;">The current fiscal landscape demonstrates a remarkable decoupling from traditional cyclical pressures. Our engine observes a significant shift toward <strong style="color: var(--primary-navy);">decentralized liquidity pools</strong> which are insulating mid-tier assets from macro volatility. Institutional sentiment remains cautiously optimistic as the sovereign debt markets stabilize.</p>
              <p style="margin-bottom: 2rem;">While primary indicators suggest a slowing of hyper-growth in the technology sector, we are seeing a recursive pattern in sustainable infrastructure. Capital flows have shifted from speculative R&D toward resilient, cash-flow positive industrial automation systems. This pivot represents a <strong style="color: var(--primary-navy);">maturation of the intelligence economy</strong>.</p>
              <p>We advise a strategic rebalancing toward non-correlated alternative assets. The Sovereign Ledger's proprietary volatility index suggests a 14% decrease in drawdown risk for portfolios integrated with automated hedge triggers over the next 180 days. The outlook remains fundamentally robust.</p>
            </div>

            <div style="margin-top: 3rem; padding-top: 2.5rem; border-top: 1px solid var(--slate-100); display: flex; align-items: center; justify-content: space-between;">
              <div style="display: flex; gap: 4rem;">
                <div>
                  <p style="font-size: 10px; font-family: 'Outfit', sans-serif; color: var(--slate-400); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; margin-bottom: 0.5rem;">Sentiment Index</p>
                  <div style="display: flex; align-items: baseline; gap: 0.25rem;">
                    <span style="font-size: 1.875rem; font-weight: 900;">7.4</span>
                    <span style="font-size: 0.875rem; font-weight: 700; color: var(--slate-300);">/10</span>
                  </div>
                </div>
                <div>
                  <p style="font-size: 10px; font-family: 'Outfit', sans-serif; color: var(--slate-400); text-transform: uppercase; letter-spacing: 0.1em; font-weight: 700; margin-bottom: 0.5rem;">Risk Exposure</p>
                  <p style="font-size: 1.875rem; font-weight: 900; color: var(--orange-600); text-transform: uppercase; letter-spacing: -0.05em;">Moderate</p>
                </div>
              </div>
              <div class="chart-container" style="width: 16rem;">
                 {bars_html}
              </div>
            </div>
          </div>
        </section>

        <aside class="lg-col-span-4" style="display: flex; flex-direction: column; gap: 2rem;">
          <div class="bg-primary-navy group" style="border-radius: 2rem; padding: 2.5rem; color: white; position: relative; overflow: hidden;">
            <div class="group-hover-scale transition-all" style="position: absolute; right: -1.5rem; bottom: -1.5rem; opacity: 0.05; width: 11.25rem; height: 11.25rem;">
              {filetext_svg}
            </div>
            <div style="position: relative; z-index: 10;">
              <h4 style="font-size: 1.5rem; font-weight: 700; margin-bottom: 0.75rem; letter-spacing: -0.025em;">Monthly Intelligence PDF</h4>
              <p style="color: var(--slate-400); font-size: 0.875rem; line-height: 1.625; margin-bottom: 2rem;">Generate a 48-page deep-dive including ledger audits, predictive trends, and tax optimization strategies.</p>
              <button class="ai-btn-primary">
                Generate Report {download_svg}
              </button>
              <div style="margin-top: 2rem; display: flex; align-items: center; justify-content: center; gap: 2rem;">
                <button style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; letter-spacing: 0.1em; color: var(--slate-500); background: none; border: none; cursor: pointer; font-weight: 700;">View Last Month</button>
                <div style="width: 4px; height: 4px; border-radius: 9999px; background-color: #334155;"></div>
                <button style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; letter-spacing: 0.1em; color: var(--slate-500); background: none; border: none; cursor: pointer; font-weight: 700;">Schedule Weekly</button>
              </div>
            </div>
          </div>

          <div class="bg-slate-50" style="border-radius: 2rem; padding: 2.5rem; position: relative; overflow: hidden;">
             <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 2rem;">
                <span class="font-label" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.2em; color: var(--rose-600); font-weight: 800;">Risk Alerts</span>
                <div style="color: var(--rose-600);">{alert_svg}</div>
             </div>
             <div class="space-y-8">
                <div style="display: flex; gap: 1rem;">
                   <div style="width: 0.5rem; height: 0.5rem; border-radius: 9999px; background-color: var(--rose-600); margin-top: 0.5rem; flex-shrink: 0;"></div>
                   <div>
                      <p style="font-size: 0.875rem; font-weight: 700; color: var(--slate-900); margin-bottom: 0.25rem;">Currency Fluctuation: EUR/USD</p>
                      <p style="font-size: 11px; color: var(--slate-500); line-height: 1.625;">Ledger exposure exceeds 12% in non-hedged foreign holdings. Mitigation recommended.</p>
                   </div>
                </div>
                <div style="display: flex; gap: 1rem; opacity: 0.5;">
                   <div style="width: 0.5rem; height: 0.5rem; border-radius: 9999px; background-color: var(--slate-400); margin-top: 0.5rem; flex-shrink: 0;"></div>
                   <div>
                      <p style="font-size: 0.875rem; font-weight: 700; color: var(--slate-400); margin-bottom: 0.25rem;">Compliance Deadline</p>
                      <p style="font-size: 11px; color: var(--slate-500); line-height: 1.625;">Tax filings for offshore accounts due in 14 days. Automation enabled.</p>
                   </div>
                </div>
             </div>
          </div>
        </aside>

        <section class="col-span-12" style="margin-top: 2rem;">
           <div style="display: flex; align-items: flex-end; justify-content: space-between; margin-bottom: 2.5rem;">
              <div>
                <span class="font-label" style="font-size: 10px; text-transform: uppercase; letter-spacing: 0.3em; color: var(--slate-500); font-weight: 700; margin-bottom: 0.5rem; display: block;">Alpha Signals</span>
                <h3 style="font-size: 2.25rem; font-weight: 800; letter-spacing: -0.025em;">Top Opportunities</h3>
              </div>
              <button style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; letter-spacing: 0.3em; font-weight: 800; color: var(--primary-navy); border-bottom: 2px solid var(--primary-navy); padding-bottom: 0.25rem; background: none; border-left: none; border-right: none; border-top: none; cursor: pointer; transition: opacity 0.2s;">View Full Matrix</button>
           </div>
           <div class="ai-grid" style="gap: 2rem; display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));">
              
                <div class="bg-white group" style="padding: 2rem; border-radius: 1.5rem; border: 1px solid var(--slate-100); box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); transition: all 0.3s;">
                   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem;">
                      <div class="bg-orange-50" style="width: 3.5rem; height: 3.5rem; border-radius: 1rem; display: flex; align-items: center; justify-content: center; color: var(--orange-600);">
                         {network_svg}
                      </div>
                      <span style="font-size: 10px; font-family: 'Outfit', sans-serif; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; padding: 0.25rem 0.75rem; border-radius: 9999px; background-color: var(--orange-50); color: var(--orange-600);">High Growth</span>
                   </div>
                   <h4 style="font-size: 1.125rem; font-weight: 700; margin-bottom: 0.75rem; letter-spacing: -0.025em;">Private Equity Pivot</h4>
                   <p style="font-size: 0.875rem; color: var(--slate-500); line-height: 1.625; margin-bottom: 2.5rem;">Strategic shift in secondary markets for Series C automation startups. Predicted 24% IRR over 36 months.</p>
                   <div style="padding-top: 1.5rem; border-top: 1px solid var(--slate-50); display: flex; align-items: center; justify-content: space-between;">
                      <span style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.1em;">Confidence Score</span>
                      <div style="display: flex; align-items: center; gap: 0.5rem;">
                         <div style="width: 4rem; height: 0.25rem; background-color: var(--slate-100); border-radius: 9999px; overflow: hidden;">
                            <div style="height: 100%; background-color: var(--orange-600); width: 92%;"></div>
                         </div>
                         <span style="font-size: 0.75rem; font-weight: 700; font-family: monospace;">92%</span>
                      </div>
                   </div>
                </div>

                <div class="bg-white group" style="padding: 2rem; border-radius: 1.5rem; border: 1px solid var(--slate-100); box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); transition: all 0.3s;">
                   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem;">
                      <div class="bg-emerald-50" style="width: 3.5rem; height: 3.5rem; border-radius: 1rem; display: flex; align-items: center; justify-content: center; color: var(--emerald-600);">
                         {leaf_svg}
                      </div>
                      <span style="font-size: 10px; font-family: 'Outfit', sans-serif; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; padding: 0.25rem 0.75rem; border-radius: 9999px; background-color: var(--emerald-50); color: var(--emerald-600);">Stable</span>
                   </div>
                   <h4 style="font-size: 1.125rem; font-weight: 700; margin-bottom: 0.75rem; letter-spacing: -0.025em;">Sustainable REITs</h4>
                   <p style="font-size: 0.875rem; color: var(--slate-500); line-height: 1.625; margin-bottom: 2.5rem;">Green-certified commercial real estate in emerging tech hubs. Projected dividend yield of 6.2% annually.</p>
                   <div style="padding-top: 1.5rem; border-top: 1px solid var(--slate-50); display: flex; align-items: center; justify-content: space-between;">
                      <span style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.1em;">Confidence Score</span>
                      <div style="display: flex; align-items: center; gap: 0.5rem;">
                         <div style="width: 4rem; height: 0.25rem; background-color: var(--slate-100); border-radius: 9999px; overflow: hidden;">
                            <div style="height: 100%; background-color: var(--emerald-600); width: 84%;"></div>
                         </div>
                         <span style="font-size: 0.75rem; font-weight: 700; font-family: monospace;">84%</span>
                      </div>
                   </div>
                </div>

                <div class="bg-white group" style="padding: 2rem; border-radius: 1.5rem; border: 1px solid var(--slate-100); box-shadow: 0 1px 2px 0 rgba(0, 0, 0, 0.05); transition: all 0.3s;">
                   <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 2rem;">
                      <div class="bg-blue-50" style="width: 3.5rem; height: 3.5rem; border-radius: 1rem; display: flex; align-items: center; justify-content: center; color: var(--blue-600);">
                         {rocket_svg}
                      </div>
                      <span style="font-size: 10px; font-family: 'Outfit', sans-serif; font-weight: 800; text-transform: uppercase; letter-spacing: 0.1em; padding: 0.25rem 0.75rem; border-radius: 9999px; background-color: var(--blue-50); color: var(--blue-600);">Speculative</span>
                   </div>
                   <h4 style="font-size: 1.125rem; font-weight: 700; margin-bottom: 0.75rem; letter-spacing: -0.025em;">Sub-Orbital Logistics</h4>
                   <p style="font-size: 0.875rem; color: var(--slate-500); line-height: 1.625; margin-bottom: 2.5rem;">Early-stage funding for high-speed intercontinental freight. High volatility, high alpha potential.</p>
                   <div style="padding-top: 1.5rem; border-top: 1px solid var(--slate-50); display: flex; align-items: center; justify-content: space-between;">
                      <span style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.1em;">Confidence Score</span>
                      <div style="display: flex; align-items: center; gap: 0.5rem;">
                         <div style="width: 4rem; height: 0.25rem; background-color: var(--slate-100); border-radius: 9999px; overflow: hidden;">
                            <div style="height: 100%; background-color: var(--blue-600); width: 67%;"></div>
                         </div>
                         <span style="font-size: 0.75rem; font-weight: 700; font-family: monospace;">67%</span>
                      </div>
                   </div>
                </div>

           </div>
        </section>
      </div>

      <footer style="margin-top: 5rem; padding-top: 2.5rem; border-top: 1px solid var(--slate-100); display: flex; flex-direction: column; align-items: center; gap: 2.5rem;">
         <div style="display: flex; align-items: center; gap: 1.5rem;">
            <div style="display: flex; gap: 0.375rem;">
               <div style="width: 0.375rem; height: 0.375rem; border-radius: 9999px; background-color: var(--slate-900);"></div>
               <div style="width: 0.375rem; height: 0.375rem; border-radius: 9999px; background-color: var(--slate-900);"></div>
               <div style="width: 0.375rem; height: 0.375rem; border-radius: 9999px; background-color: var(--slate-300);"></div>
            </div>
            <span style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.2em;">System State: Processing Deep Insights • 12:45 UTC</span>
         </div>
         <div style="display: flex; gap: 2.5rem;">
            <button style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.1em; background: none; border: none; cursor: pointer; transition: color 0.2s;">Audit Logs</button>
            <button style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.1em; background: none; border: none; cursor: pointer; transition: color 0.2s;">API Access</button>
            <button style="font-size: 10px; font-family: 'Outfit', sans-serif; text-transform: uppercase; font-weight: 700; color: var(--slate-400); letter-spacing: 0.1em; background: none; border: none; cursor: pointer; transition: color 0.2s;">Privacy Protocols</button>
         </div>
      </footer>
    </div>
    """
    import re
    cleaned_html = re.sub(r'^[ \t]+', '', html_content, flags=re.MULTILINE)
    st.markdown(cleaned_html, unsafe_allow_html=True)

if page_choice == "🧠 AI Insights":
    render_ai_insights()

