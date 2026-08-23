import datetime
import json
import os
import sqlite3
import streamlit as st
import pandas as pd
import numpy as np
from typing import Any
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
import logging
import time
from functools import wraps
import qualtrim_engine
import monetization_engine
from components import (
    render_compound_interest_ui,
    render_dcf_valuation_ui,
    render_consensus_pe_section,
    render_portfolio_dividend_suite,
    render_portfolio_stress_test_suite,
    render_my_portfolio_ui,
    render_home_ui,
    render_macro_market_ui,
    render_financial_news_ui,
    render_stock_screener_ui,
    render_superinvestors_ui,
    render_buffett_scorecard_ui,
    render_business_segments_ui,
    render_stock_tracker_ui,
)

# --- SYSTEM LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("PROQuantDashboard")

# --- EXPONENTIAL BACKOFF RETRY DECORATOR ---


def retry_on_failure(max_retries=3, initial_delay=1.0, backoff_factor=2.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        logger.error(
                            f"Errore definitivo in {func.__name__} dopo {max_retries} tentativi: {e}")
                        raise
                    logger.warning(
                        f"Tentativo {attempt + 1} fallito per {func.__name__}. Riprovo tra {delay:.2f}s. Errore: {e}")
                    time.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator

# --- YAHOO FINANCE ---
# (Il yf_session personalizzato è stato rimosso in quanto yfinance lo gestisce nativamente con curl_cffi per evitare i blocchi)


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
st.set_page_config(page_title="PRO Quant Dashboard",
                   layout="wide", initial_sidebar_state="expanded")

# --- QUERY PARAMETERS INTERCEPTOR (DIRECT NAV FROM SCREENER & SUPER INVESTORS) ---
if "ticker" in st.query_params:
    qp_ticker = st.query_params["ticker"]
    if qp_ticker:
        # Prepopulate Stock Tracker
        st.session_state['active_ticker'] = qp_ticker.upper()
        if 'active_cap' not in st.session_state:
            st.session_state['active_cap'] = 1000.0
        if 'active_years' not in st.session_state:
            st.session_state['active_years'] = 10
        if 'active_bench' not in st.session_state:
            st.session_state['active_bench'] = "SPY"
        # Switch navigation page to Stock Tracker
        st.session_state['navigation_page'] = "📊 Stock Tracker"
        # Clear query parameters to update browser URL and avoid routing loops
        st.query_params.clear()
        st.rerun()
# --- INIZIALIZZAZIONE SESSION STATE PER STOCK TRACKER ---
if 'active_ticker' not in st.session_state:
    st.session_state['active_ticker'] = 'KO'
if 'active_cap' not in st.session_state:
    st.session_state['active_cap'] = 1000.0
if 'active_years' not in st.session_state:
    st.session_state['active_years'] = 10
if 'active_bench' not in st.session_state:
    st.session_state['active_bench'] = "SPY"


# --- MOTORE PER MARQUEE DATA ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_marquee_data() -> str:
    """
    Recupera i dati correnti per l'intestazione a scorrimento (Marquee) tramite Yahoo Finance.
    Ottimizzato con download multithreaded batch e fallback non-bloccante.
    """
    tickers = {
        "S&P 500": "SPY", "NASDAQ": "QQQ", "DOW J": "DIA", "GOLD": "GLD",
        "BTC": "BTC-USD", "10Y YIELD": "^TNX", "NVIDIA": "NVDA", "APPLE": "AAPL",
        "TESLA": "TSLA", "DOLLAR": "DX-Y.NYB", "OIL": "CL=F", "EURO": "EURUSD=X"
    }
    marquee_items = []

    try:
        data = yf.download(list(tickers.values()),
                           period="5d", progress=False, threads=True, timeout=2.0)['Close']
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
                        marquee_items.append(
                            f"<span style='margin-right: 40px;'><b>{name}</b> ${last_prc:,.2f} <span style='color: {color};'>{sign}{pct:.2f}%</span></span>")
        if marquee_items:
            return " ".join(marquee_items)
    except Exception as e:
        logger.warning(f"get_marquee_data fallback: {e}")

    return (
        "<span style='margin-right: 40px;'><b>S&P 500</b> $5,800.00 <span style='color: #00FF00;'>+0.45%</span></span>"
        "<span style='margin-right: 40px;'><b>NASDAQ</b> $20,200.00 <span style='color: #00FF00;'>+0.62%</span></span>"
        "<span style='margin-right: 40px;'><b>NVIDIA</b> $128.50 <span style='color: #00FF00;'>+1.85%</span></span>"
        "<span style='margin-right: 40px;'><b>BTC</b> $68,400.00 <span style='color: #00FF00;'>+2.10%</span></span>"
        "<span style='margin-right: 40px;'><b>GOLD</b> $2,650.00 <span style='color: #00FF00;'>+0.30%</span></span>"
    )


marquee_html = get_marquee_data()

# --- INIETTA STYLE.CSS (Design AI Insights) ---


def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


local_css("style.css")

# --- HELPER FUNCTIONS FOR PREMIUM UI/UX & CHARTS ---


def render_custom_metric(label, value, delta=None, icon=None, is_positive=None):
    """
    Genera una KPI Card personalizzata con Glassmorphism Plus, Neon Glow ed icone.
    """
    if is_positive is None:
        if delta:
            clean_delta = str(delta).strip()
            if clean_delta.startswith('-'):
                is_positive = False
            elif clean_delta.startswith('+') or any(char.isdigit() for char in clean_delta):
                is_positive = True
            else:
                is_positive = True
        else:
            is_positive = True

    arrow = "▲" if is_positive else "▼"
    delta_color = "#00FF7F" if is_positive else "#FF3B30"
    glow_color = "rgba(0, 255, 127, 0.15)" if is_positive else "rgba(255, 59, 48, 0.15)"
    rgb_values = "0,255,127" if is_positive else "255,59,48"

    icon_html = f'<span style="font-size: 22px;">{icon}</span>' if icon else ''

    delta_html = ""
    if delta:
        delta_html = f"""
        <div style="color: {delta_color}; font-weight: 600; font-size: 14px; margin-top: 6px; display: inline-flex; align-items: center; gap: 4px; padding: 3px 10px; background: {glow_color}; border: 1px solid rgba({rgb_values}, 0.2); border-radius: 6px; box-shadow: 0 0 10px {glow_color};">
            <span style="font-size: 10px;">{arrow}</span> {delta}
        </div>
        """

    html = f"""
    <div class="custom-kpi-card">
        <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div style="font-size: 13px; font-weight: 500; color: #8A929A; text-transform: uppercase; letter-spacing: 0.5px;">{label}</div>
            {icon_html}
        </div>
        <div class="num-value" style="font-size: 28px; font-weight: 700; color: #ffffff; margin-top: 10px; letter-spacing: -0.5px; text-shadow: 0 0 12px rgba(255,255,255,0.08);">{value}</div>
        {delta_html}
    </div>
    """
    # Rimuove gli spazi iniziali da ogni riga per evitare che il markdown interpreti l'HTML come blocco di codice preformattato
    clean_html = "\n".join([line.strip() for line in html.split("\n")])
    st.markdown(clean_html, unsafe_allow_html=True)


def render_premium_portfolio_table(holdings):
    """
    Genera una tabella di portafoglio HTML/CSS premium con progress bar per l'allocazione,
    badge colorati per i ticker e pillole colorate per i settori merceologici.
    """
    html = """
    <table class="premium-portfolio-table">
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Azienda</th>
                <th>Settore</th>
                <th style="text-align: right;">Quote</th>
                <th style="text-align: right;">Valore 13F</th>
                <th style="text-align: right; width: 180px;">Peso Portafoglio</th>
            </tr>
        </thead>
        <tbody>
    """
    for h in holdings:
        ticker = h.get('Ticker', 'N/A')
        azienda = h.get('Azienda', 'N/A')
        settore = h.get('Settore', 'N/A')
        alloc = h.get('Allocazione %', 0.0)
        quote = h.get('Quote', 'N/A')
        valore = h.get('Valore', 'N/A')

        # Determina classe CSS in base al settore
        sec_clean = settore.lower().strip()
        if 'tech' in sec_clean or 'software' in sec_clean or 'crypto' in sec_clean:
            sec_class = "sector-technology"
        elif 'financial' in sec_clean:
            sec_class = "sector-financial"
        elif 'consumer' in sec_clean or 'retail' in sec_clean or 'auto' in sec_clean or 'e-commerce' in sec_clean:
            sec_class = "sector-consumer"
        elif 'energy' in sec_clean or 'utilities' in sec_clean:
            sec_class = "sector-energy"
        elif 'health' in sec_clean:
            sec_class = "sector-health"
        elif 'industrial' in sec_clean or 'materials' in sec_clean:
            sec_class = "sector-industrial"
        else:
            sec_class = "sector-default"

        html += f"""
        <tr>
            <td><a class="screener-link" href="?ticker={ticker}" target="_self"><span class="ticker-badge">{ticker}</span></a></td>
            <td class="company-name">{azienda}</td>
            <td><span class="sector-pill {sec_class}">{settore}</span></td>
            <td class="num-value" style="text-align: right; font-weight: 500; color: #CBD5E1;">{quote}</td>
            <td class="num-value" style="text-align: right; font-weight: 700; color: #ffffff;">{valore}</td>
            <td>
                <div class="allocation-bar-container">
                    <div class="allocation-bar-bg">
                        <div class="allocation-bar-fill" style="width: {alloc}%;"></div>
                    </div>
                    <span class="allocation-text">{alloc:.2f}%</span>
                </div>
            </td>
        </tr>
        """
    html += """
    </tbody>
</table>
"""
    # Rimuove gli spazi iniziali da ogni riga per evitare che il markdown interpreti l'HTML come blocco di codice preformattato
    clean_html = "\n".join([line.strip() for line in html.split("\n")])
    st.markdown(clean_html, unsafe_allow_html=True)


def render_premium_screener_table(df):
    """
    Genera una tabella per lo Stock Screener in HTML/CSS premium,
    con badge colorati per i ticker, progress bar per i dividendi e status colorati per il P/E.
    """
    html = """
    <table class="premium-portfolio-table">
        <thead>
            <tr>
                <th>Ticker</th>
                <th>Azienda</th>
                <th style="text-align: right;">Prezzo</th>
                <th style="text-align: right;">P/E Ratio</th>
                <th style="text-align: right;">Div Yield %</th>
                <th style="text-align: right;">Payout %</th>
                <th style="text-align: right;">EPS Growth %</th>
                <th style="text-align: right;">Net Income</th>
                <th style="text-align: right;">Profit Margin</th>
            </tr>
        </thead>
        <tbody>
    """
    for _, row in df.iterrows():
        ticker = row.get('Ticker', 'N/A')
        azienda = row.get('Azienda', 'N/A')
        pe = row.get('P/E', None)
        div = row.get('Div Yield %', 0.0)
        payout = row.get('Payout Ratio %', 0.0)
        eps_g = row.get('EPS Growth %', 0.0)
        net_inc = row.get('Net Income (M)', 0.0)
        margin = row.get('Profit Margin %', 0.0)
        prezzo = row.get('Prezzo', 'N/A')

        # Formattazione prezzo
        formatted_price = f"${prezzo:,.2f}" if isinstance(
            prezzo, (int, float)) else str(prezzo)
        if isinstance(prezzo, str) and not prezzo.startswith('$') and prezzo != 'N/A':
            try:
                formatted_price = f"${float(prezzo):,.2f}"
            except Exception:
                pass

        # Status P/E
        if pe is None or str(pe) == 'nan':
            pe_html = '<span style="color: #8A929A;">N/A</span>'
        else:
            if pe < 15:
                pe_html = f'<span style="color: #00FF7F; font-weight: 700; background: rgba(0, 255, 127, 0.1); border: 1px solid rgba(0, 255, 127, 0.2); padding: 3px 8px; border-radius: 6px;">{pe:.2f}</span>'
            elif pe <= 25:
                pe_html = f'<span style="color: #FFAB00; font-weight: 700; background: rgba(255, 171, 0, 0.1); border: 1px solid rgba(255, 171, 0, 0.2); padding: 3px 8px; border-radius: 6px;">{pe:.2f}</span>'
            else:
                pe_html = f'<span style="color: #FF3B30; font-weight: 700; background: rgba(255, 59, 48, 0.1); border: 1px solid rgba(255, 59, 48, 0.2); padding: 3px 8px; border-radius: 6px;">{pe:.2f}</span>'

        # Div Yield
        div_html = f'<span style="color: #00f2fe; font-weight: 700;">{div:.2f}%</span>' if div > 0 else '<span style="color: #8A929A;">0.00%</span>'

        # Payout
        payout_html = f'<span style="color: #E2E8F0;">{payout:.1f}%</span>' if payout > 0 else '<span style="color: #8A929A;">0.0%</span>'

        # EPS Growth
        eps_g_html = f'<span style="color: #00FF7F; font-weight: 600;">+{eps_g:.1f}%</span>' if eps_g > 0 else f'<span style="color: #FF3B30; font-weight: 600;">{eps_g:.1f}%</span>'

        # Net Income
        net_inc_formatted = f"${net_inc/1000:.2f}B" if net_inc >= 1000 else f"${net_inc:.1f}M"

        # Margin
        margin_html = f'<span style="color: #00FF7F; font-weight: 600;">{margin:.1f}%</span>' if margin >= 15 else f'<span style="color: #E2E8F0;">{margin:.1f}%</span>'

        html += f"""
        <tr>
            <td><a class="screener-link" href="?ticker={ticker}" target="_self"><span class="ticker-badge">{ticker}</span></a></td>
            <td class="company-name">{azienda}</td>
            <td class="num-value" style="text-align: right; font-weight: 600; color: #ffffff;">{formatted_price}</td>
            <td class="num-value" style="text-align: right;">{pe_html}</td>
            <td class="num-value" style="text-align: right;">{div_html}</td>
            <td class="num-value" style="text-align: right;">{payout_html}</td>
            <td class="num-value" style="text-align: right;">{eps_g_html}</td>
            <td class="num-value" style="text-align: right; font-weight: 600; color: #ffffff;">{net_inc_formatted}</td>
            <td class="num-value" style="text-align: right;">{margin_html}</td>
        </tr>
        """
    html += """
        </tbody>
    </table>
    """
    # Rimuove gli spazi iniziali da ogni riga per evitare che il markdown interpreti l'HTML come blocco di codice preformattato
    clean_html = "\n".join([line.strip() for line in html.split("\n")])
    st.markdown(clean_html, unsafe_allow_html=True)


def render_buffett_scorecard_ui(ticker: str):
    """Renders the Warren Buffett 10-K Financial Statement Scorecard UI in Streamlit."""
    res = qualtrim_engine.calculate_buffett_scorecard(ticker)
    if "error" in res:
        st.error(res["error"])
        return
    
    score = res["score"]
    pass_cnt = res["pass_count"]
    tot_cnt = res["total_criteria"]
    comp_name = res["company_name"]
    
    score_color = "#00FF7F" if score >= 75 else ("#FFD700" if score >= 50 else "#FF4500")
    score_badge = "🏆 Azienda in pieno stile Warren Buffett (Fossato Competitivo Eccellente)" if score >= 75 else ("⚠️ Azienda parzialmente conforme ai criteri di Buffett" if score >= 50 else "❌ L'azienda non soddisfa i rigidi criteri di bilancio di Buffett")
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(30, 41, 59, 0.9) 100%); padding: 24px; border-radius: 16px; border: 1px solid rgba(0, 242, 254, 0.25); margin-bottom: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.4);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 16px;">
            <div>
                <h2 style="margin: 0; color: #FFFFFF; font-family: 'Outfit', sans-serif; font-size: 24px;">🧙‍♂️ Buffett 10-K Scorecard: <span style="color: #00F2FE;">{ticker}</span> ({comp_name})</h2>
                <p style="color: #8A929A; margin-top: 6px; font-size: 14px;">Analisi automatica del bilancio sui 9 pilastri contabili di Warren Buffett & David Clark</p>
            </div>
            <div style="text-align: right; background: rgba(0,0,0,0.4); padding: 12px 24px; border-radius: 14px; border: 1px solid {score_color};">
                <div style="font-size: 34px; font-weight: 800; color: {score_color}; font-family: 'Outfit', sans-serif;">{score} <span style="font-size: 16px; color: #8A929A;">/ 100</span></div>
                <div style="font-size: 12px; font-weight: 700; color: #E2E8F0;">{pass_cnt} su {tot_cnt} Criteri Superati</div>
            </div>
        </div>
        <div style="margin-top: 16px; padding: 10px 16px; background: rgba(255,255,255,0.04); border-radius: 8px; font-size: 13px; font-weight: 600; color: {score_color};">
            {score_badge}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    categories = ["Conto Economico", "Stato Patrimoniale", "Rendiconto Finanziario"]
    cat_icons = {"Conto Economico": "📊", "Stato Patrimoniale": "🏛️", "Rendiconto Finanziario": "💸"}
    
    cat_tabs = st.tabs([f"{cat_icons[cat]} {cat}" for cat in categories])
    
    for idx, cat in enumerate(categories):
        with cat_tabs[idx]:
            cat_criteria = [c for c in res["criteria"] if c["category"] == cat]
            for c in cat_criteria:
                status = c["status"]
                bg_card = "rgba(0, 255, 127, 0.04)" if status == "PASS" else ("rgba(255, 215, 0, 0.04)" if status == "WARNING" else "rgba(255, 69, 0, 0.04)")
                border_card = "#00FF7F" if status == "PASS" else ("#FFD700" if status == "WARNING" else "#FF4500")
                badge_html = f"<span style='background: {border_card}; color: #000; font-weight: 800; padding: 3px 8px; border-radius: 6px; font-size: 11px;'>✅ PASS</span>" if status == "PASS" else (f"<span style='background: {border_card}; color: #000; font-weight: 800; padding: 3px 8px; border-radius: 6px; font-size: 11px;'>⚠️ WARNING</span>" if status == "WARNING" else f"<span style='background: {border_card}; color: #FFF; font-weight: 800; padding: 3px 8px; border-radius: 6px; font-size: 11px;'>❌ FAIL</span>")
                
                st.markdown(f"""
                <div style="background: {bg_card}; border-left: 4px solid {border_card}; border-radius: 12px; padding: 16px; margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                        <span style="font-weight: 700; font-size: 16px; color: #FFFFFF;">{c['name']}</span>
                        {badge_html}
                    </div>
                    <div style="display: flex; gap: 24px; margin-top: 10px; flex-wrap: wrap;">
                        <div><span style="color: #8A929A; font-size: 12px;">Valore Misurato:</span> <b style="color: #FFFFFF; font-size: 15px;">{c['value_str']}</b></div>
                        <div><span style="color: #8A929A; font-size: 12px;">Target di Buffett:</span> <b style="color: #00F2FE; font-size: 15px;">{c['target']}</b></div>
                    </div>
                    <p style="margin-top: 10px; margin-bottom: 4px; color: #CBD5E1; font-size: 13px;"><i>{c['desc']}</i></p>
                    <div style="font-size: 11px; color: #64748B; background: rgba(0,0,0,0.25); padding: 4px 10px; border-radius: 4px; display: inline-block; margin-top: 4px;">
                        📌 <b>Dove trovarlo nel Bilancio 10-K:</b> {c['where']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

    raw = res.get("raw", {})
    oe = raw.get("owner_earnings", 0) / 1e9
    ni = raw.get("net_income", 0) / 1e9
    capex_b = raw.get("capex", 0) / 1e9
    ocf_b = (raw.get("owner_earnings", 0) + raw.get("capex", 0)) / 1e9
    
    st.divider()
    if oe >= ni:
        oe_comment = "🟢 <b>Eccellente:</b> Il Cash Flow Reale supera l'Utile Netto, a dimostrazione di una straordinaria conversione in cassa senza spese fantasma."
    else:
        oe_comment = "⚠️ <b>Attenzione:</b> L'Utile Netto supera il Cash Flow Reale a causa di ingenti spese in capitale fisso (CapEx) o capitale circolante."

    st.markdown(f"""
    Warren Buffett ritiene che l'Utile Netto sia un dato contabile facilmente alterabile da regole di ammortamento e svalutazione. 
    Per valutare il vero cash flow generato dall'azienda per gli azionisti, calcola gli **Owner Earnings**:
    
    <div style="background: rgba(0,242,254,0.08); border: 1px solid rgba(0,242,254,0.3); border-radius: 12px; padding: 18px; margin: 12px 0;">
        <div style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: #00F2FE; font-size: 15px;">
            Owner Earnings = OCF (${ocf_b:.2f}B) - CapEx (${capex_b:.2f}B) = <span style="color: #00FF7F; font-size: 18px;">${oe:.2f} Miliardi</span>
        </div>
        <div style="margin-top: 10px; font-size: 13px; color: #E2E8F0;">
            Confronto con Utile Netto Contabile: <b>${ni:.2f} Miliardi</b><br>
            {oe_comment}
        </div>
    </div>
    """, unsafe_allow_html=True)


def apply_premium_chart_theme(fig, is_sparkline=False):
    """
    Applica un tema Plotly scuro istituzionale, trasparente ed estremamente pulito.
    """
    is_spark = is_sparkline
    if hasattr(fig, 'layout') and fig.layout:
        if hasattr(fig.layout, 'xaxis') and fig.layout.xaxis and fig.layout.xaxis.visible is False:
            is_spark = True

    # Palette istituzionale scura
    color_palette = ["#4facfe", "#10b981",
                     "#f59e0b", "#ef4444", "#a5b4fc", "#64748b"]

    # Impostazioni di stile base trasparenti, font e colorway globale
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, sans-serif", color="#CBD5E1"),
        colorway=color_palette,
        hoverlabel=dict(
            bgcolor="rgba(15, 23, 42, 0.98)",
            bordercolor="rgba(255, 255, 255, 0.08)",
            font=dict(family="Inter, sans-serif", size=12, color="#FFFFFF")
        )
    )

    # Applica lo stile tipografico pulito al titolo
    if hasattr(fig, 'layout') and fig.layout and fig.layout.title and getattr(fig.layout.title, 'text', None):
        fig.update_layout(
            title_font=dict(family="Outfit, sans-serif",
                            size=16, color="#FFFFFF"),
            title_pad=dict(b=12)
        )

    if is_spark:
        fig.update_layout(margin=dict(l=0, r=0, t=5, b=5))
    else:
        fig.update_layout(
            margin=dict(l=15, r=15, t=45, b=15),
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0.0,
                font=dict(size=11, color="#94A3B8"),
                bgcolor="rgba(0,0,0,0)"
            )
        )
        try:
            fig.update_xaxes(
                gridcolor="rgba(255, 255, 255, 0.03)",
                linecolor="rgba(255, 255, 255, 0.06)",
                tickfont=dict(family="Inter, sans-serif",
                              size=10, color="#94A3B8"),
                zeroline=False
            )
            fig.update_yaxes(
                gridcolor="rgba(255, 255, 255, 0.03)",
                linecolor="rgba(255, 255, 255, 0.06)",
                tickfont=dict(family="Inter, sans-serif",
                              size=10, color="#94A3B8"),
                zeroline=False
            )
        except Exception:
            pass

    # Aggiorna dinamicamente i singoli tracciati (Traces) per uno stile impeccabile
    if hasattr(fig, 'data') and fig.data:
        for idx, trace in enumerate(fig.data):
            default_color = color_palette[idx % len(color_palette)]
            try:
                # 1. Curve e Aree (Scatter)
                if trace.type == "scatter":
                    if hasattr(trace, 'line') and trace.line:
                        if not getattr(trace.line, 'color', None):
                            trace.line.color = default_color
                        trace.line.shape = "spline"
                        trace.line.width = 2.5

                    # Gradienti traslucidi ad area
                    if hasattr(trace, 'fill') and trace.fill and trace.fill != 'none':
                        ref_color = getattr(trace.line, 'color', default_color)
                        if isinstance(ref_color, str) and ref_color.startswith('#'):
                            h = ref_color.lstrip('#')
                            rgb = tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
                            trace.fillcolor = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, 0.06)"

                # 2. Istogrammi (Bar)
                elif trace.type == "bar":
                    if hasattr(trace, 'marker') and trace.marker:
                        if not getattr(trace.marker, 'color', None):
                            trace.marker.color = default_color
                        if hasattr(trace.marker, 'line'):
                            trace.marker.line.width = 0
            except Exception:
                pass

    return fig


# Override st.plotly_chart per applicare automaticamente il tema a ogni grafico
_original_plotly_chart = st.plotly_chart


def custom_plotly_chart(fig, *args, **kwargs):
    fig = apply_premium_chart_theme(fig)
    return _original_plotly_chart(fig, *args, **kwargs)


st.plotly_chart = custom_plotly_chart

# Custom CSS per look "Institutional Premium Glassmorphic" e Leggibilità Avanzata
st.markdown(f"""
    <style>
    /* Global Background & Smooth Animation */
    @keyframes gradientShift {{
        0%   {{ background-position: 0% 50%; }}
        50%  {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}

    [data-testid="stAppViewContainer"] {{
        background: linear-gradient(-45deg, #0a0a12, #121420, #0c0a1a, #05050e) !important;
        background-size: 400% 400% !important;
        animation: gradientShift 30s ease infinite !important;
        color: #e0e0e0 !important;
    }}

    /* Overlay per profondità e texture */
    [data-testid="stAppViewContainer"]::before {{
        content: "";
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background: radial-gradient(circle at center, transparent 0%, rgba(0,0,0,0.3) 100%);
        pointer-events: none;
        z-index: 0;
    }}

    /* 4. IDENTITÀ TIPOGRAFICA BESPOKE */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Outfit:wght@400;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap');

    h1, h2, h3, [data-testid="stHeader"] {{
        font-family: 'Outfit', sans-serif !important;
        color: #ffffff !important;
        text-shadow: 0 0 15px rgba(255,255,255,0.1);
        letter-spacing: -0.5px;
    }}

    .stMarkdown, p, label, .stMetric label, .stSelectbox label, .stSlider label, [data-testid="stWidgetLabel"] p {{
        font-family: 'Inter', sans-serif !important;
        color: #cbd5e1 !important;
    }}

    /* Numeri e valori quantitativi con JetBrains Mono */
    div[data-testid="stMetric-value"], 
    .num-value, 
    .ticker-badge, 
    .allocation-text, 
    .allocation-bar-container span {{
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 500 !important;
        letter-spacing: -0.2px !important;
    }}

    /* 6. STRUTTURA DI PROFONDITÀ (GLASSMORPHISM STRATIFICATO) */
    [data-testid="stMetric"], .stDataFrame, .stExpander, div[data-testid="stVerticalBlock"] > div[style*="background-color"] {{ 
        background: rgba(255, 255, 255, 0.02) !important; 
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        padding: 22px !important; 
        border-radius: 18px !important; 
        border: 1px solid rgba(255, 255, 255, 0.06) !important; 
        box-shadow: 0 12px 40px 0 rgba(0, 0, 0, 0.45) !important;
        transition: all 0.35s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }}
    
    [data-testid="stMetric"]:hover, .stExpander:hover {{
        transform: translateY(-3px) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
        box-shadow: 0 18px 45px 0 rgba(0, 0, 0, 0.55), 0 0 25px rgba(79, 172, 254, 0.05) !important;
        background: rgba(255, 255, 255, 0.03) !important;
    }}

    /* 1. CONTROLLI DI INPUT PREMIUM (FORM, SLIDERS & BUTTONS) */
    /* Input di Testo, Area e Numerici - Sfondo scuro sempre leggibile con padding adeguato */
    input, 
    textarea,
    div[data-testid="stNumberInput"] input, 
    div[data-testid="stTextInput"] input,
    div[data-baseweb="input"] input {{
        background-color: #0c0d14 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        color: #ffffff !important;
        font-family: 'Inter', sans-serif !important;
        padding: 8px 12px !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.15) !important;
    }}

    /* Selectbox di Streamlit - Solo fondale scuro e bordi finissimi, senza alterare il padding nativo per evitare troncamenti (...) */
    div[data-baseweb="select"] > div {{
        background-color: #0c0d14 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        font-family: 'Inter', sans-serif !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }}
    
    input:focus, 
    textarea:focus,
    div[data-testid="stNumberInput"] input:focus, 
    div[data-testid="stTextInput"] input:focus {{
        border-color: rgba(79, 172, 254, 0.4) !important;
        box-shadow: 0 0 15px rgba(79, 172, 254, 0.12), inset 0 2px 4px rgba(0, 0, 0, 0.15) !important;
        background-color: #0c0d14 !important;
    }}

    div[data-baseweb="select"] > div:focus-within {{
        border-color: rgba(79, 172, 254, 0.4) !important;
        box-shadow: 0 0 15px rgba(79, 172, 254, 0.12) !important;
    }}

    /* Dropdown select options styling (per evitare menu bianchi con testo bianco) */
    div[role="listbox"], ul[role="listbox"], [data-baseweb="menu"], [data-baseweb="popover"] {{
        background-color: #0c0d14 !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
    }}
    div[role="option"], li[role="option"], [data-baseweb="menu"] li {{
        background-color: transparent !important;
        color: #cbd5e1 !important;
        transition: all 0.2s ease !important;
    }}
    div[role="option"]:hover, li[role="option"]:hover, [data-baseweb="menu"] li:hover {{
        background-color: rgba(79, 172, 254, 0.15) !important;
        color: #ffffff !important;
    }}

    /* Forza il testo selezionato all'interno dei selectbox di Streamlit ad essere bianco e leggibile */
    div[data-baseweb="select"] div,
    div[data-baseweb="select"] span,
    [data-testid="stSelectboxVirtualFocus"],
    [data-testid="stSelectbox"] div {{
        color: #ffffff !important;
    }}

    /* Sliders Streamlit */
    div[data-testid="stSlider"] [data-baseweb="slider"] {{
        background-color: transparent !important;
    }}
    div[data-testid="stSlider"] [data-baseweb="slider"] > div {{
        background-color: rgba(255, 255, 255, 0.06) !important;
        height: 6px !important;
        border-radius: 3px !important;
    }}
    div[data-testid="stSlider"] [role="slider"] {{
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%) !important;
        border: 2px solid #ffffff !important;
        width: 16px !important;
        height: 16px !important;
        box-shadow: 0 0 10px rgba(79, 172, 254, 0.3) !important;
        transition: transform 0.2s ease, box-shadow 0.2s ease !important;
    }}
    div[data-testid="stSlider"] [role="slider"]:hover {{
        transform: scale(1.2) !important;
        box-shadow: 0 0 14px rgba(79, 172, 254, 0.5) !important;
    }}

    /* Pulsanti Nativi di Streamlit */
    div.stButton > button {{
        background: linear-gradient(135deg, rgba(255, 255, 255, 0.05) 0%, rgba(255, 255, 255, 0.01) 100%) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 12px !important;
        padding: 8px 20px !important;
        font-family: 'Outfit', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    }}
    div.stButton > button:hover {{
        border-color: rgba(79, 172, 254, 0.35) !important;
        background: linear-gradient(135deg, rgba(79, 172, 254, 0.08) 0%, rgba(0, 242, 254, 0.03) 100%) !important;
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(79, 172, 254, 0.12) !important;
    }}
    div.stButton > button:active {{
        transform: translateY(1px) !important;
    }}

    /* 5. MOTION DESIGN & MICRO-INTERAZIONI (FADE-IN STAGGERED) */
    @keyframes fadeInUp {{
        from {{
            opacity: 0;
            transform: translateY(12px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    [data-testid="stVerticalBlock"] > div {{
        animation: fadeInUp 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}
    [data-testid="stVerticalBlock"] > div:nth-child(1) {{ animation-delay: 0.04s; }}
    [data-testid="stVerticalBlock"] > div:nth-child(2) {{ animation-delay: 0.08s; }}
    [data-testid="stVerticalBlock"] > div:nth-child(3) {{ animation-delay: 0.12s; }}
    [data-testid="stVerticalBlock"] > div:nth-child(4) {{ animation-delay: 0.16s; }}
    [data-testid="stVerticalBlock"] > div:nth-child(5) {{ animation-delay: 0.20s; }}

    /* Sidebar Styling */
    [data-testid="stSidebar"] {{
        background-color: #04040a !important;
        border-right: 1px solid rgba(255,255,255,0.04);
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
        background: rgba(4, 4, 10, 0.7);
        backdrop-filter: blur(8px);
        padding: 10px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
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
        width: 6px;
    }}
    ::-webkit-scrollbar-track {{
        background: rgba(0,0,0,0.1);
    }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(255,255,255,0.06);
        border-radius: 10px;
    }}
    ::-webkit-scrollbar-thumb:hover {{
        background: rgba(255,255,255,0.12);
    }}
    </style>
    <div class="ticker-wrap">
        <div class="ticker-move">
            {marquee_html}{marquee_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


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

    # Auto-sync su Google Sheets se configurato in session_state
    try:
        if 'gsheets_url' in st.session_state and st.session_state.get('gsheets_auto_sync', False):
            push_portfolio_to_gsheets(p_list)
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


def format_large_numbers(value: Any, is_currency: bool = True) -> str:
    """
    Formatta numeri di grandi dimensioni (T, B, M) aggiungendo opzionalmente il simbolo di valuta.

    Args:
        value (Any): Il valore numerico da formattare (supporta float, int, liste o Series).
        is_currency (bool, optional): Se aggiungere il prefisso '$'. Defaults to True.

    Returns:
        str: Il numero formattato in formato abbreviato o 'N/A' se non valido.
    """
    # Se il valore è una Series o lista, prendi il primo elemento (evita errori di ambiguità pandas)
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        if len(value) > 0:
            import pandas as pd
            value = value.iloc[0] if isinstance(
                value, (pd.Series, pd.DataFrame)) else value[0]
        else:
            return "N/A"

    if value is None or str(value) == 'nan' or value == 'N/A' or isinstance(value, str):
        return "N/A"
    prefix = ""
    if value < 0:
        value = abs(value)
        prefix = "-"
    c = "$" if is_currency else ""
    if value >= 1_000_000_000_000:
        return f"{prefix}{c}{value/1_000_000_000_000:.2f}T"
    if value >= 1_000_000_000:
        return f"{prefix}{c}{value/1_000_000_000:.2f}B"
    if value >= 1_000_000:
        return f"{prefix}{c}{value/1_000_000:.2f}M"
    return f"{prefix}{c}{value:,.2f}"


def format_perc(value: Any) -> str:
    """
    Formatta un valore frazionario in stringa percentuale raccordata.

    Args:
        value (Any): Il valore frazionario da formattare (supporta float, int, liste o Series).

    Returns:
        str: La percentuale formattata (es. '12.34%') o 'N/A' se non valido.
    """
    if hasattr(value, "__len__") and not isinstance(value, (str, bytes)):
        if len(value) > 0:
            import pandas as pd
            value = value.iloc[0] if isinstance(
                value, (pd.Series, pd.DataFrame)) else value[0]
        else:
            return "N/A"
    if value is None or str(value) == 'nan' or value == 'N/A':
        return "N/A"
    return f"{value * 100:.2f}%"


def calc_cagr(start_val: float, end_val: float, years: float) -> float:
    """
    Calcola il tasso composto annuo di crescita (Compound Annual Growth Rate).

    Args:
        start_val (float): Valore patrimoniale iniziale.
        end_val (float): Valore patrimoniale finale.
        years (float): Numero di anni dell'intervallo temporale.

    Returns:
        float: Il tasso CAGR espresso in forma decimale.
    """
    if start_val <= 0 or years <= 0:
        return 0.0
    return (end_val / start_val) ** (1 / years) - 1


def calc_risk_metrics(returns: pd.Series, rf_rate: float = 0.02) -> tuple[float, float]:
    """
    Calcola l'indice di Sharpe ed il massimo drawdown storico su una serie temporale di rendimenti.

    Args:
        returns (pd.Series): Serie storica dei rendimenti giornalieri.
        rf_rate (float, optional): Tasso d'interesse privo di rischio. Defaults to 0.02 (2%).

    Returns:
        tuple[float, float]: Una tupla contenente (Sharpe Ratio annualizzato, Max Drawdown).
    """
    if returns.empty:
        return 0.0, 0.0

    try:
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

        return float(sharpe), float(max_dd)
    except Exception as e:
        logger.error(f"Errore nel calcolo delle metriche di rischio: {e}")
        return 0.0, 0.0


# --- FUNZIONI AI OLLAMA (LOCALE) ---
@retry_on_failure(max_retries=3, initial_delay=1.0)
def get_sentiment(text: str) -> str:
    """
    Analizza il sentiment finanziario del testo (positivo, negativo o neutrale) tramite il modello locale Gemma.
    Se fallisce, esegue un fallback locale sul sentiment di TextBlob.

    Args:
        text (str): Testo o titolo della notizia da analizzare.

    Returns:
        str: Il sentiment rilevato formattato con emoji.
    """
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
            logger.warning(
                f"Ollama API ha risposto con codice non 200: {response.status_code}")
            raise Exception("API status error")
    except Exception as e:
        logger.warning(f"Ollama fallito, avvio TextBlob fallback: {e}")
        score = TextBlob(text).sentiment.polarity
        if score > 0.1:
            return "🟢 Positive (TextBlob Fallback)"
        elif score < -0.1:
            return "🔴 Negative (TextBlob Fallback)"
        else:
            return "⚪ Neutral (TextBlob Fallback)"


def analyze_portfolio_diversification(portfolio_df, total_value):
    """Fa analizzare a Gemma la diversificazione del portafoglio."""
    assets_text = ""
    for index, row in portfolio_df.iterrows():
        ticker = row['Ticker']
        peso_perc = (row['Valore Totale ($)'] / total_value * 100) if total_value > 0.0 else 0.0
        assets_text += f"- {ticker}: {peso_perc:.2f}%\n"

    prompt = f"""Agisci come un consulente finanziario esperto in gestione del rischio. 
    Analizza la seguente allocazione di portafoglio di un investitore:
    
    {assets_text}
    
    Scrivi un commento professionale (massimo 4-5 frasi) valutando la diversificazione. 
    Rispondi a queste domande: È un portafoglio equilibrato? C'è un rischio di sovraesposizione su un singolo titolo o settore? Qual è il tuo consiglio per bilanciare il rischio?
    Rispondi in italiano in modo chiaro e diretto.
    """
    try:
        response = requests.post("http://localhost:11434/api/generate", json={
                                 "model": "gemma:2b", "prompt": prompt, "stream": False, "options": {"temperature": 0.2}}, timeout=30)
        if response.status_code == 200:
            return response.json()['response'].strip()
        else:
            return "Errore nella generazione."
    except Exception:
        return "Errore di connessione con Ollama."


def analyze_financial_statements_ai(ticker, inc_stmt, bal_sheet, cash_flow):
    """Analisi accurata dei bilanci annuali tramite Gemma."""
    def simplify_df(df, name):
        if df is None or df.empty:
            return f"{name}: Dati non disponibili"
        # Prime 15 metriche, ultimi 2 anni per stare nel context window del modello locale
        df_compact = df.iloc[:15, :2].copy()
        for col in df_compact.columns:
            df_compact[col] = pd.to_numeric(df_compact[col], errors='coerce').apply(
                lambda x: f"${x/1e9:.2f}B" if pd.notna(
                    x) and abs(x) >= 1e8 else str(x)
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
        response = requests.post("http://localhost:11434/api/generate", json={
                                 "model": "gemma:2b", "prompt": prompt, "stream": False, "options": {"temperature": 0.2}}, timeout=30)
        if response.status_code == 200:
            return response.json()['response'].strip()
        else:
            return "Errore nella generazione."
    except Exception:
        return "Errore di connessione con Ollama."


def generate_pdf_report(ticker, rt_price, info, sharpe, max_dd):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"Institutional Tear Sheet: {ticker}", ln=True, align="C")
    pdf.set_font("Arial", '', 12)
    name = info.get('shortName', ticker)
    pdf.cell(
        0, 10, f"Company: {name.encode('latin-1', 'replace').decode('latin-1')}", ln=True)
    pdf.cell(0, 10, f"Current Price: ${rt_price:,.2f}", ln=True)
    pdf.cell(
        0, 10, f"P/E Rating (Trailing): {info.get('trailingPE', 'N/A')}", ln=True)
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
    if not tickers:
        return {}
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
    if not ticker_tuple:
        return {}
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
                    result[tk] = (float(series.iloc[-1]),
                                  float(series.iloc[-2]))
        return result
    except Exception:
        return {}


@st.cache_data(ttl=900)
def fetch_portfolio_vs_voo_history(tickers_tuple):
    """Fetch 5-year historical close prices for portfolio tickers + VOO."""
    if not tickers_tuple:
        return pd.DataFrame()
    unique_tickers = [str(tk).strip().upper() for tk in tickers_tuple if tk]
    if not unique_tickers:
        return pd.DataFrame()
    all_tickers = list(set(unique_tickers + ['VOO']))
    try:
        raw = yf.download(all_tickers, period="5y", progress=False, threads=True)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            close_df = raw['Close']
        else:
            close_df = raw[['Close']].rename(columns={'Close': all_tickers[0]}) if len(all_tickers) == 1 else raw['Close']
        if isinstance(close_df, pd.Series):
            close_df = close_df.to_frame(name=all_tickers[0])
        close_df = close_df.ffill().bfill()
        return close_df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=60, show_spinner=False)
def fetch_realtime_price(ticker):
    """Recupera il prezzo attuale vivo con cache breve (60s) e accesso fast_info ultra-rapido."""
    try:
        fast = yf.Ticker(ticker).fast_info
        prc = getattr(fast, 'last_price', None)
        if prc is not None and not pd.isna(prc) and prc > 0:
            return float(prc)
    except Exception:
        pass
    try:
        hist = yf.Ticker(ticker).history(period="1d")
        if not hist.empty and 'Close' in hist:
            return float(hist['Close'].iloc[-1])
    except Exception:
        pass
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_benchmark_history(bench_ticker, start_date_str, end_date_str):
    """Recupera i dati storici del benchmark con cache oraria."""
    try:
        return yf.download(bench_ticker, start=start_date_str, end=end_date_str, progress=False)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_ownership_data(ticker):
    """Recupera dati major holders e institutional holders con cache giornaliera."""
    t = yf.Ticker(ticker)
    mh = None
    ih = None
    try:
        mh = t.major_holders
    except Exception:
        pass
    try:
        ih = t.institutional_holders
    except Exception:
        pass
    return mh, ih


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_earnings_dates_cached(ticker):
    """Recupera il calendario utili con fallback su stock.calendar."""
    stock = yf.Ticker(ticker)
    try:
        return stock.earnings_dates
    except Exception:
        try:
            cal = stock.calendar
            if cal and 'Earnings Date' in cal and cal['Earnings Date']:
                earn_dates = cal['Earnings Date']
                earn_data = pd.DataFrame({
                    "Earnings Date": earn_dates,
                    "EPS Est. Average": [cal.get("Earnings Average", "N/A")] * len(earn_dates),
                    "Rev Est. Average": [cal.get("Revenue Average", "N/A")] * len(earn_dates)
                })
                earn_data.set_index("Earnings Date", inplace=True)
                return earn_data
        except Exception:
            pass
    return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_portfolio_close_history(tickers_tuple, period="1y"):
    """Recupera i prezzi di chiusura per i ticker del portafoglio (matrice correlazione e ottimizzazione)."""
    if not tickers_tuple:
        return pd.DataFrame()
    try:
        raw = yf.download(list(tickers_tuple), period=period, progress=False, threads=True)
        if raw.empty:
            return pd.DataFrame()
        if isinstance(raw.columns, pd.MultiIndex):
            return raw['Close']
        elif 'Close' in raw:
            return raw[['Close']].rename(columns={'Close': tickers_tuple[0]}) if len(tickers_tuple) == 1 else raw['Close']
        return raw
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_macro_market_data():
    """Acquisisce i dati macroeconomici principali in batch multithreaded."""
    macro_tickers = {
        "S&P 500 (Trend US)": "^GSPC",
        "Nasdaq 100": "^NDX",
        "US 10Y Treasury (Risk-Free)": "^TNX",
        "VIX (Fear Index)": "^VIX",
        "Oro (Bene Rifugio)": "GC=F",
        "Argento (Metallo Prezioso)": "SI=F",
        "Petrolio Brent (Energia)": "BZ=F",
        "Petrolio WTI (Energia)": "CL=F",
        "EUR/USD (Valuta)": "EURUSD=X"
    }
    try:
        raw = yf.download(list(macro_tickers.values()), period="6mo", progress=False, threads=True)
        closes = raw['Close'] if isinstance(raw.columns, pd.MultiIndex) else raw
        data_out = {}
        for name, sym in macro_tickers.items():
            if sym in closes.columns:
                s = closes[sym].dropna()
                if not s.empty:
                    data_out[name] = s
        return data_out
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500_tickers():
    """Scarica e memorizza nella cache i ticker dell'indice S&P 500."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    try:
        html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).text
        return pd.read_html(io.StringIO(html))[0]['Symbol'].tolist()
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_galaxy_history(tk_tuple):
    """Scarica dati a 1 anno per la galassia dei super investitori."""
    try:
        raw = yf.download(list(tk_tuple), period="1y", progress=False, threads=True)
        return raw['Close'] if isinstance(raw.columns, pd.MultiIndex) else raw
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_consensus_data(ticker, current_price):
    """Estrae e memorizza nella cache le stime di consenso degli analisti e la struttura del capitale."""
    from analytics.consensus_pe import extract_consensus_pe_data
    try:
        s_obj = yf.Ticker(ticker)
        s_info = fetch_stock_info(ticker)
        return extract_consensus_pe_data(
            ticker=ticker,
            info=s_info,
            stock_obj=s_obj,
            current_price=current_price
        )
    except Exception:
        return {}


@st.cache_data(ttl=300, show_spinner=False)
def fetch_home_data(ticker_tuple):
    """Hybrid: batch yf.download per i prezzi + fast_info parallelo per market cap."""
    import concurrent.futures
    import time as _time
    ticker_list = list(ticker_tuple)

    try:
        raw = yf.download(ticker_list, period="5d", progress=False, threads=True)
        if isinstance(raw.columns, pd.MultiIndex):
            batch_prices = raw['Close']
        else:
            batch_prices = raw[['Close']].rename(columns={'Close': ticker_list[0]}) if len(
                ticker_list) == 1 else raw['Close']
    except Exception:
        batch_prices = pd.DataFrame()

    if batch_prices.empty:
        return pd.DataFrame()

    if isinstance(batch_prices, pd.Series):
        batch_prices = batch_prices.to_frame(name=ticker_list[0])

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

    if failed_tickers:
        _time.sleep(0.3)
        for tkr in failed_tickers:
            try:
                hist = yf.Ticker(tkr).history(period="5d")
                if not hist.empty and len(hist) >= 2:
                    curr = float(hist['Close'].iloc[-1])
                    prev = float(hist['Close'].iloc[-2])
                    pct = ((curr - prev) / prev) * 100 if prev != 0 else 0.0
                    price_data[tkr] = (curr, pct)
                    valid_tickers.append(tkr)
            except Exception:
                pass

    if not valid_tickers:
        return pd.DataFrame()

    def get_mcap(tkr):
        for attempt in range(2):
            try:
                mcap = float(yf.Ticker(tkr).fast_info.market_cap)
                return tkr, mcap
            except Exception:
                _time.sleep(0.2 * (attempt + 1))
        return tkr, 0.0

    workers = min(25, len(valid_tickers))
    mcap_map = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        for tkr, mcap in executor.map(get_mcap, valid_tickers):
            mcap_map[tkr] = mcap

    COMPANY_INFO_MAP = {
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

    results = []
    for tkr in valid_tickers:
        curr, pct = price_data[tkr]
        mcap = mcap_map.get(tkr, 0.0)
        name, domain = COMPANY_INFO_MAP.get(tkr, (tkr, ""))

        results.append({
            "Ticker": tkr, "Name": name, "Price": curr,
            "Change": pct, "MarketCap": mcap, "Domain": domain
        })

    df = pd.DataFrame(results)
    if not df.empty:
        df.sort_values(by="MarketCap", ascending=False, inplace=True)
        df.reset_index(drop=True, inplace=True)
    return df


@st.cache_data(ttl=86400, show_spinner=False)
def get_full_sp500_list():
    """Scarica la lista completa S&P 500 da Wikipedia, con cleanup ticker."""
    url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
    try:
        html_table = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).text
        raw_tickers = pd.read_html(io.StringIO(html_table))[0]['Symbol'].tolist()
        cleaned = [t.replace('.', '-') for t in raw_tickers]
        deduped = []
        for t in cleaned:
            base = t.split('-')[0] if t not in ('BRK-B', 'BF-B') else t
            if base == 'GOOG' and 'GOOGL' in cleaned and t != 'GOOGL':
                continue
            if t not in deduped:
                deduped.append(t)
        return deduped
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500_sectors():
    """Fetch GICS sector mapping from Wikipedia for all S&P 500 tickers."""
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5).text
        df_wiki = pd.read_html(io.StringIO(html))[0]
        return dict(zip(df_wiki['Symbol'].str.replace('.', '-', regex=False), df_wiki['GICS Sector']))
    except Exception:
        return {}


def fetch_fmp_quote(ticker, api_key):
    """Fetch real-time quote data from Financial Modeling Prep (stable API)."""
    result = {}
    try:
        # 1. Fetch Price & basic quote data
        url_q = f"https://financialmodelingprep.com/stable/quote?symbol={ticker}&apikey={api_key}"
        r_q = requests.get(url_q, timeout=5)
        if r_q.status_code == 200:
            data_q = r_q.json()
            if data_q and isinstance(data_q, list):
                q = data_q[0]
                result['price'] = q.get('price')
                result['marketCap'] = q.get('marketCap')
                result['previousClose'] = q.get('previousClose')
                result['name'] = q.get('name')
                result['exchange'] = q.get('exchange')
                if result.get('marketCap') and result.get('price'):
                    result['sharesOutstanding'] = result['marketCap'] / \
                        result['price']

        # 2. Fetch Valuation Ratios (PE, EPS, Dividend)
        url_r = f"https://financialmodelingprep.com/stable/ratios-ttm?symbol={ticker}&apikey={api_key}"
        r_r = requests.get(url_r, timeout=5)
        if r_r.status_code == 200:
            data_r = r_r.json()
            if data_r and isinstance(data_r, list):
                rat = data_r[0]
                result['pe'] = rat.get('priceToEarningsRatioTTM')
                result['eps'] = rat.get('netIncomePerShareTTM')
                result['dividendRate'] = rat.get('dividendPerShareTTM')
                result['dividendYield'] = rat.get('dividendYieldTTM')
    except Exception:
        pass
    return result if result else None


@st.cache_data(ttl=3600)
def fetch_stock_info(ticker, _v=1):
    stock = yf.Ticker(ticker)
    info = None
    try:
        info = stock.info
        if not info or ('regularMarketPrice' not in info and 'currentPrice' not in info):
            raise ValueError("Empty info (rate limited)")
    except Exception:
        info = None

    # Check if info is missing key valuation metrics
    metrics_to_check = ['trailingPE', 'forwardPE', 'trailingEps', 'forwardEps']
    is_thin = info is None or not any(m in info for m in metrics_to_check)

    if is_thin:
        try:
            FMP_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"
            fmp_data = fetch_fmp_quote(ticker, FMP_KEY)
            if fmp_data:
                if info is None:
                    info = {'symbol': ticker, 'shortName': ticker}

                # Map FMP fields to yfinance fields for consistency
                mapping = {
                    'price': 'currentPrice',
                    'pe': 'trailingPE',
                    'eps': 'trailingEps',
                    'marketCap': 'marketCap',
                    'sharesOutstanding': 'sharesOutstanding',
                    'previousClose': 'previousClose',
                    'name': 'shortName',
                    'dividendRate': 'dividendRate',
                    'dividendYield': 'dividendYield'
                }
                for fmp_key, yf_key in mapping.items():
                    if fmp_key in fmp_data and (yf_key not in info or info[yf_key] is None):
                        info[yf_key] = fmp_data[fmp_key]
                info['_fmp_augmented'] = True
        except Exception:
            pass

    if info and ('currentPrice' in info or 'regularMarketPrice' in info):
        # Utilizza la stima di crescita utile direttamente da info (evita chiamate HTTP pesanti a income_stmt)
        if 'epsGrowth5Y' not in info or info['epsGrowth5Y'] is None:
            g_val = info.get('earningsGrowth') or info.get('earningsQuarterlyGrowth') or 0.0
            info['epsGrowth5Y'] = float(g_val) * 100 if isinstance(g_val, (int, float)) and g_val < 10 else float(g_val or 0.0)
        return info

    # Se ancora non abbiamo i dati base, procediamo col fallback quantitativo
    try:
        fast = stock.fast_info
        curr_price = getattr(fast, 'last_price', 0)
        shares = getattr(fast, 'shares', 0)

        fallback_info = {
            'symbol': ticker,
            'shortName': ticker,
            'currentPrice': curr_price,
            'marketCap': getattr(fast, 'market_cap', 0),
            'previousClose': getattr(fast, 'previous_close', 0),
            'sharesOutstanding': shares,
            'sector': 'Unknown (Rate Limited)',
            'industry': 'Unknown',
            '_rate_limited': True
        }

        try:
            # Tenta di estrarre metriche fondamentali (ROE, Margini, Debito, ecc) in modo passivo
            inc = stock.income_stmt
            bal = stock.balance_sheet
            cf = stock.cashflow

            if inc is not None and not inc.empty and 'Net Income' in inc.index and 'Total Revenue' in inc.index:
                net_inc = inc.loc['Net Income'].dropna().iloc[0]
                rev = inc.loc['Total Revenue'].dropna().iloc[0]
                if rev > 0:
                    fallback_info['profitMargins'] = net_inc / rev

                if curr_price and shares:
                    eps = net_inc / shares
                    if eps > 0:
                        fallback_info['trailingPE'] = curr_price / eps

            if bal is not None and not bal.empty:
                eq_key = 'Stockholders Equity' if 'Stockholders Equity' in bal.index else 'Total Stockholders Equity'
                if eq_key in bal.index and 'profitMargins' in fallback_info:
                    eq = bal.loc[eq_key].dropna().iloc[0]
                    net_inc = inc.loc['Net Income'].dropna().iloc[0]
                    if eq > 0:
                        fallback_info['returnOnEquity'] = net_inc / eq

                if 'Total Debt' in bal.index:
                    tot_debt = bal.loc['Total Debt'].dropna().iloc[0]
                    if 'Total Stockholders Equity' in bal.index:
                        eq = bal.loc['Total Stockholders Equity'].dropna(
                        ).iloc[0]
                        if eq > 0:
                            fallback_info['debtToEquity'] = (
                                tot_debt / eq) * 100

                cash_key = 'Cash And Cash Equivalents'
                if cash_key in bal.index:
                    fallback_info['totalCash'] = bal.loc[cash_key].dropna(
                    ).iloc[0]

            if cf is not None and not cf.empty and 'Free Cash Flow' in cf.index:
                fallback_info['leveredFreeCashFlow'] = cf.loc['Free Cash Flow'].dropna(
                ).iloc[0]
        except Exception:
            pass

        return fallback_info
    except Exception:
        return {'symbol': ticker, 'shortName': ticker, '_rate_limited': True}


def push_portfolio_to_gsheets(p_list):
    try:
        url = st.session_state.get('gsheets_url')
        if not url:
            # Carica da file se non è in session state
            if os.path.exists("gsheets_url.txt"):
                with open("gsheets_url.txt", "r") as f:
                    url = f.read().strip()
        if not url:
            return

        import requests
        import pandas as pd

        # Ottieni prezzi e dividendi correnti per arricchire il pacchetto
        tickers = [item['ticker'] for item in p_list]
        if not tickers:
            return
        prices_dict = get_batch_prices(list(set(tickers)))

        # Fetch stock info per dividendi (utilizza la cache con fallback robusto)
        stock_infos = {}
        for tk in list(set(tickers)):
            try:
                stock_infos[tk] = fetch_stock_info(tk)
            except Exception:
                stock_infos[tk] = None

        enriched_data = []
        for item in p_list:
            tk = item['ticker']
            sh = item['shares']
            pr = float(item.get('purchase_price', 0.0))

            curr_p = prices_dict.get(tk, 0.0)
            if isinstance(curr_p, pd.Series):
                curr_p = curr_p.iloc[0]
            if pr == 0.0:
                pr = curr_p

            info = stock_infos.get(tk) or {}

            trailing_div_rate = info.get('trailingAnnualDividendRate')
            if trailing_div_rate is None or trailing_div_rate == 0:
                trailing_div_rate = info.get('dividendRate')
            if trailing_div_rate is None:
                trailing_div_rate = 0.0

            forward_div_rate = info.get('dividendRate')
            if forward_div_rate is None or forward_div_rate == 0:
                forward_div_rate = info.get('trailingAnnualDividendRate')
            if forward_div_rate is None:
                forward_div_rate = 0.0

            yoc = (trailing_div_rate / pr * 100) if pr > 0 else 0.0
            yoc_fwd = (forward_div_rate / pr * 100) if pr > 0 else 0.0

            enriched_data.append({
                "Ticker": tk,
                "Quantità": sh,
                "Prezzo d'Acquisto ($)": pr,
                "Prezzo Attuale ($)": curr_p,
                "Costo Totale ($)": sh * pr,
                "Valore Totale ($)": sh * curr_p,
                "YOC (%)": f"{yoc:.2f}%",
                "Dividendi TTM ($)": sh * trailing_div_rate,
                "YOC FWD (%)": f"{yoc_fwd:.2f}%",
                "Dividendi FWD ($)": sh * forward_div_rate
            })

        requests.post(url, json=enriched_data, timeout=10)
    except Exception:
        pass


@st.cache_data(ttl=3600)
def fetch_history(ticker, years, _v=1):
    stock = yf.Ticker(ticker)
    end_date = datetime.today()
    start_date = end_date - timedelta(days=years * 365)
    return stock.history(start=start_date, end=end_date)


@st.cache_data(ttl=3600)
def fetch_financials(ticker, _v=1):
    stock = yf.Ticker(ticker)
    try:
        f1, f2, f3 = stock.financials, stock.balance_sheet, stock.cashflow
        if f1 is None or f1.empty:
            raise ValueError()
        return f1, f2, f3
    except Exception:
        try:
            API_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"
            return fetch_fmp_financials(ticker, API_KEY)
        except Exception:
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
            res.columns = [pd.Timestamp(
                year=int(y), month=12, day=31) for y in res.columns]
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
            extra = [c for c in q_agg_df.columns if hasattr(
                c, 'year') and c.year not in a_years]
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
        extra_cols = [c for c in df_secondary.columns if hasattr(
            c, 'year') and c.year not in p_years]
        if extra_cols:
            # Only keep rows that exist in primary (avoid mismatched row names)
            common_rows = df_primary.index.intersection(df_secondary.index)
            if not common_rows.empty:
                merged = pd.concat(
                    [df_primary, df_secondary.loc[common_rows, extra_cols]], axis=1)
            else:
                merged = pd.concat(
                    [df_primary, df_secondary[extra_cols]], axis=1)
            return merged.reindex(sorted(merged.columns), axis=1)
        return df_primary
    except Exception:
        return df_primary


@st.cache_data(ttl=3600)
def fetch_macrotrends_financials(ticker, limit_years=10):
    """Scrape 10-15 years of key annual financials from macrotrends.net."""
    from bs4 import BeautifulSoup
    import re as _re

    headers_req = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

    # Step 1: Resolve company slug (macrotrends URLs require company-name in path)
    def _resolve_slug(tk):
        try:
            test_url = f'https://www.macrotrends.net/stocks/charts/{tk}/x/revenue'
            r = requests.get(test_url, headers=headers_req,
                             timeout=10, allow_redirects=True)
            if r.status_code == 200:
                m = _re.search(
                    rf'/stocks/charts/{tk}/([^/]+)/', r.url, _re.IGNORECASE)
                if m:
                    return m.group(1)
                m2 = _re.search(
                    rf'/stocks/charts/{tk}/([^/"]+)/revenue', r.text, _re.IGNORECASE)
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

    def _scrape_metric_item(item):
        row_name, metric_slug = item
        url = f'https://www.macrotrends.net/stocks/charts/{ticker}/{slug}/{metric_slug}'
        try:
            r = requests.get(url, headers=headers_req, timeout=3.5)
            if r.status_code != 200:
                return row_name, {}
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
                    cells = [td.get_text(strip=True)
                             for td in row.find_all(['th', 'td'])]
                    if len(cells) >= 2 and len(cells[0]) == 4 and cells[0].isdigit():
                        year = int(cells[0])
                        val = _parse_value(cells[1])
                        if val is not None:
                            result[year] = val
                if result:
                    return row_name, result
        except Exception:
            pass
        return row_name, {}

    # Step 3: Scrape all metrics concurrently in parallel
    all_data = {}
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        for row_name, res in executor.map(_scrape_metric_item, metric_slugs.items()):
            if res:
                all_data[row_name] = res

    if not all_data:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Step 4: Build DataFrames
    million_scale = {'Total Revenue', 'Net Income',
                     'EBITDA', 'Free Cash Flow', 'Total Debt'}

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
            (all_data['Total Debt'].get(y, None) or 0) *
            1_000_000 if all_data['Total Debt'].get(y) is not None else None
            for y in all_years
        ]

    cf_data = {}
    if 'Free Cash Flow' in all_data:
        cf_data['Free Cash Flow'] = [
            (all_data['Free Cash Flow'].get(y, None) or 0) *
            1_000_000 if all_data['Free Cash Flow'].get(
                y) is not None else None
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
/* 1. NASCONDI I PALLINI/CERCHI DEL RADIO BUTTON (100% CSS STANDARD COMPATIBILE) */
[data-testid="stSidebar"] [data-baseweb="radio"] input,
[data-testid="stSidebar"] [data-testid="stRadioButton"] input,
[data-testid="stSidebar"] div[role="radiogroup"] input,
[data-testid="stSidebar"] [data-baseweb="radio"] label > div > div:first-child,
[data-testid="stSidebar"] [data-baseweb="radio"] label > div > div:first-of-type,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label > div > div:first-child,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label > div > div:first-of-type,
[data-testid="stSidebar"] [data-baseweb="radio"] div[aria-hidden="true"],
[data-testid="stSidebar"] [data-testid="stRadioButton"] div[aria-hidden="true"],
[data-testid="stSidebar"] [data-baseweb="radio"] svg,
[data-testid="stSidebar"] [data-testid="stRadioButton"] svg {
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    opacity: 0 !important;
    visibility: hidden !important;
    margin: 0 !important;
    padding: 0 !important;
    border: none !important;
    background: transparent !important;
}

/* AZZERA MARGINI E PADDING SUL CONTENITORE DEL TESTO */
[data-testid="stSidebar"] [data-baseweb="radio"] label > div > div:last-child,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label > div > div:last-child,
[data-testid="stSidebar"] div[role="radiogroup"] label > div > div:last-child {
    margin-left: 0 !important;
    padding-left: 0 !important;
    width: 100% !important;
}

/* 2. STILE BASE SCHEDE CARD DI NAVIGAZIONE */
[data-testid="stSidebar"] [data-testid="stRadioButton"] label,
[data-testid="stSidebar"] [data-baseweb="radio"],
[data-testid="stSidebar"] div[role="radiogroup"] label {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    padding: 12px 16px !important;
    margin-bottom: 8px !important;
    border-radius: 10px !important;
    transition: all 0.25s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    position: relative !important; /* CRUCIALE PER ANCORARE I TITOLI DECORATIVI */
    cursor: pointer !important;
    background: rgba(255, 255, 255, 0.03) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
    box-sizing: border-box !important;
}

/* 3. TESTO NELLE SCHEDE */
[data-testid="stSidebar"] [data-testid="stRadioButton"] label p,
[data-testid="stSidebar"] [data-baseweb="radio"] p,
[data-testid="stSidebar"] div[role="radiogroup"] label p {
    color: #e2e8f0 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    margin: 0 !important;
    padding: 0 !important;
    line-height: 1.4 !important;
}

/* 4. HOVER STATE CON BAGLIORE CIANO E MICRO-SPOSTAMENTO */
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:hover,
[data-testid="stSidebar"] [data-baseweb="radio"]:hover,
[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
    background-color: rgba(255, 255, 255, 0.07) !important;
    border-color: rgba(0, 242, 254, 0.4) !important;
    transform: translateX(4px) !important;
}

/* 5. VOCE ATTIVA (EVIDENZIATORE NEON CIANO) */
[data-testid="stSidebar"] [data-baseweb="radio"][aria-checked="true"],
[data-testid="stSidebar"] [data-testid="stRadioButton"] label[aria-checked="true"],
[data-testid="stSidebar"] [aria-checked="true"],
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:has(input:checked),
[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked),
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
    background: linear-gradient(135deg, rgba(79, 172, 254, 0.16) 0%, rgba(0, 242, 254, 0.16) 100%) !important;
    border: 1px solid rgba(0, 242, 254, 0.5) !important;
    border-left: 4px solid #00f2fe !important;
    box-shadow: 0 0 15px rgba(0, 242, 254, 0.12) !important;
}

[data-testid="stSidebar"] [data-baseweb="radio"][aria-checked="true"] p,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label[aria-checked="true"] p,
[data-testid="stSidebar"] [aria-checked="true"] p,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:has(input:checked) p,
[data-testid="stSidebar"] [data-baseweb="radio"]:has(input:checked) p,
[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
    color: #00f2fe !important;
    font-weight: 700 !important;
}

/* 6. SPAZIATURA GRUPPI E TITOLI DI CATEGORIA ANCORATI */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(1),
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(1) { margin-top: 22px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(2),
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(2) { margin-top: 28px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(5),
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(5) { margin-top: 28px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(6),
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(6) { margin-top: 28px !important; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(9),
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(9) { margin-top: 28px !important; }

/* TITOLI DECORATIVI ANCORATI SOPRA I GRUPPI */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(1)::before,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(1)::before {
    content: 'OVERVIEW';
    position: absolute;
    top: -20px;
    left: 2px;
    font-size: 10px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 1px;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(2)::before,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(2)::before {
    content: 'CALCULATORS & ANALYTICS';
    position: absolute;
    top: -20px;
    left: 2px;
    font-size: 10px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 1px;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(5)::before,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(5)::before {
    content: 'PORTFOLIO';
    position: absolute;
    top: -20px;
    left: 2px;
    font-size: 10px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 1px;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(6)::before,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(6)::before {
    content: 'MARKET INTELLIGENCE';
    position: absolute;
    top: -20px;
    left: 2px;
    font-size: 10px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 1px;
}

[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-of-type(9)::before,
[data-testid="stSidebar"] [data-testid="stRadioButton"] label:nth-of-type(9)::before {
    content: 'DISCOVERY';
    position: absolute;
    top: -20px;
    left: 2px;
    font-size: 10px;
    font-weight: 800;
    color: #64748b;
    letter-spacing: 1px;
}
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
    "🧩 Business Segments",
    "📁 My Portfolio",
    "📰 Financial News",
    "👑 Super Investors",
    "🌍 Macro & Market",
    "🔍 Stock Screener"
], label_visibility="collapsed", key="navigation_page")



# ==========================================
# PAGE ROUTING & COMPONENT DELEGATION
# ==========================================
if page_choice == "🏠 Home":
    render_home_ui(
        fetch_home_data_fn=fetch_home_data,
        fetch_watchlist_prices_fn=fetch_watchlist_prices,
        save_watchlist_fn=save_watchlist,
        get_full_sp500_list_fn=get_full_sp500_list,
        get_sp500_sectors_fn=get_sp500_sectors,
    )

elif page_choice == "📈 Compound Interest":
    render_compound_interest_ui()

elif page_choice == "📊 Stock Tracker":
    render_stock_tracker_ui(
        fetch_stock_info_fn=fetch_stock_info,
        fetch_history_fn=fetch_history,
        fetch_realtime_price_fn=fetch_realtime_price,
        fetch_benchmark_history_fn=fetch_benchmark_history,
        fetch_consensus_data_fn=fetch_consensus_data,
        fetch_ownership_data_fn=fetch_ownership_data,
        fetch_earnings_dates_cached_fn=fetch_earnings_dates_cached,
        fetch_macrotrends_financials_fn=fetch_macrotrends_financials,
        fetch_fmp_financials_fn=fetch_fmp_financials,
        fetch_financials_extended_fn=fetch_financials_extended,
        merge_financial_dfs_fn=_merge_financial_dfs,
        fetch_financials_fn=fetch_financials,
        generate_pdf_report_fn=generate_pdf_report,
        analyze_financial_statements_ai_fn=analyze_financial_statements_ai,
    )

elif page_choice == "🧩 Business Segments":
    render_business_segments_ui()

elif page_choice == "📁 My Portfolio":
    render_my_portfolio_ui(
        save_portfolio_fn=save_portfolio,
        get_batch_prices_fn=get_batch_prices,
        fetch_stock_info_fn=fetch_stock_info,
        fetch_portfolio_vs_voo_history_fn=fetch_portfolio_vs_voo_history,
        fetch_portfolio_close_history_fn=fetch_portfolio_close_history,
        push_portfolio_to_gsheets_fn=push_portfolio_to_gsheets,
        analyze_portfolio_diversification_fn=analyze_portfolio_diversification,
    )

elif page_choice == "📰 Financial News":
    render_financial_news_ui(
        fetch_news_fn=fetch_news,
        get_batch_prices_fn=get_batch_prices,
        ask_financial_chatbot_fn=ask_financial_chatbot,
    )

elif page_choice == "👑 Super Investors":
    render_superinvestors_ui(
        fetch_galaxy_history_fn=fetch_galaxy_history,
    )

elif page_choice == "🌍 Macro & Market":
    render_macro_market_ui(
        fetch_macro_market_data_fn=fetch_macro_market_data,
    )

elif page_choice == "🔍 Stock Screener":
    render_stock_screener_ui(
        get_sp500_tickers_fn=get_sp500_tickers,
        fetch_stock_info_fn=fetch_stock_info,
    )
