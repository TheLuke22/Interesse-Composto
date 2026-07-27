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
@st.cache_data(ttl=3600)
@retry_on_failure(max_retries=3, initial_delay=1.0)
def get_marquee_data() -> str:
    """
    Recupera i dati correnti per l'intestazione a scorrimento (Marquee) tramite Yahoo Finance.

    Returns:
        str: Stringa HTML contenente i ticker formattati o un messaggio di errore.
    """
    tickers = {
        "S&P 500": "SPY", "NASDAQ": "QQQ", "DOW J": "DIA", "GOLD": "GLD",
        "BTC": "BTC-USD", "10Y YIELD": "^TNX", "NVIDIA": "NVDA", "APPLE": "AAPL",
        "TESLA": "TSLA", "DOLLAR": "DX-Y.NYB", "OIL": "CL=F", "EURO": "EURUSD=X"
    }
    marquee_items = []

    # Per essere robusti in caso d'errore di Rete
    try:
        data = yf.download(list(tickers.values()),
                           period="5d", progress=False)['Close']
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
        return " ".join(marquee_items) if marquee_items else "MARKET DATA LIMITED"
    except Exception as e:
        logger.warning(f"Chiamata get_marquee_data fallita: {e}")
        return "MARKET DATA UNAVAILABLE"


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
        # Calcola l'EPS CAGR storico reale dagli statements finanziari
        try:
            inc = stock.income_stmt
            if inc is not None and not inc.empty:
                for row_name in ['Diluted EPS', 'Basic EPS', 'Net Income']:
                    if row_name in inc.index:
                        eps_series = inc.loc[row_name].dropna()
                        if len(eps_series) >= 2:
                            latest_val = eps_series.iloc[0]
                            oldest_val = eps_series.iloc[-1]
                            num_years = len(eps_series) - 1
                            if latest_val > 0 and oldest_val > 0 and num_years > 0:
                                eps_cagr = ((latest_val / oldest_val)
                                            ** (1 / num_years) - 1) * 100
                                info['epsGrowth5Y'] = eps_cagr
                                break
        except Exception:
            pass
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
                    cells = [td.get_text(strip=True)
                             for td in row.find_all(['th', 'td'])]
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
/* Stile base delle schede di navigazione */
[data-testid="stSidebar"] [data-baseweb="radio"] {
    padding: 12px 16px !important;
    margin-bottom: 8px !important;
    border-radius: 10px !important;
    transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
    position: relative !important;
    cursor: pointer !important;
    background: rgba(255, 255, 255, 0.02) !important;
    border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

/* Nascondi i cerchi nativi di Streamlit */
[data-testid="stSidebar"] [data-baseweb="radio"] > div:first-child {
    display: none !important;
}

/* Hover pulito per i bottoni con micro-spostamento laterale e bagliore ciano */
[data-testid="stSidebar"] [data-baseweb="radio"]:hover {
    background-color: rgba(255, 255, 255, 0.06) !important;
    border-color: rgba(0, 242, 254, 0.3) !important;
    transform: translateX(4px) !important;
}

/* Elemento attivo: Gradiente Ciano/Blu Neon */
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {
    background: linear-gradient(135deg, rgba(79, 172, 254, 0.12) 0%, rgba(0, 242, 254, 0.12) 100%) !important;
    border: 1px solid rgba(0, 242, 254, 0.4) !important;
    border-left: 4px solid #00f2fe !important;
    box-shadow: 0 0 15px rgba(0, 242, 254, 0.1) !important;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {
    color: #00f2fe !important;
    font-weight: 700 !important;
}

/* Spazio extra per far respirare i titoli */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1) { margin-top: 30px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(3) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(8) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(9) { margin-top: 35px; }

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

/* Testi specifici dei titoli decorativi */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(1)::before { content: '🏠 Overview'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(2)::before { content: '🧮 Calculators'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(3)::before { content: '📉 Analytics'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4)::before { content: '💼 Portfolio'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5)::before { content: '📰 Financial News'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6)::before { content: '👑 Hedge Funds'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(7)::before { content: '🌍 Macro & Market'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(8)::before { content: '🔍 Discovery'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(9)::before { content: '🤖 Hedge Fund OS AI'; }
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
    "🔍 Stock Screener",
    "🤖 Hedge Fund OS AI"
], label_visibility="collapsed", key="navigation_page")


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
            new_watch_ticker = st.text_input("Ticker", key="wl_input", label_visibility="collapsed",
                                             placeholder="Add ticker to watchlist (e.g. NVDA)...").upper().strip()
        with wl_c2:
            if st.button("➕ Add", key="wl_add_btn", use_container_width=True) and new_watch_ticker:
                if new_watch_ticker not in st.session_state['watchlist']:
                    st.session_state['watchlist'].append(new_watch_ticker)
                    save_watchlist(st.session_state['watchlist'])
                    st.toast(
                        f"{new_watch_ticker} added to watchlist!", icon="⭐")
                    st.rerun()
                else:
                    st.toast(
                        f"{new_watch_ticker} is already in your watchlist", icon="⚠️")
        with wl_c3:
            if st.button("🗑️ Clear", key="wl_clear_btn", use_container_width=True) and st.session_state['watchlist']:
                st.session_state['watchlist'] = []
                save_watchlist([])
                st.rerun()

        if st.session_state['watchlist']:
            wl_prices = fetch_watchlist_prices(
                tuple(st.session_state['watchlist']))
            if wl_prices:
                wl_html = '<div style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px;">'
                for wl_tk in st.session_state['watchlist']:
                    if wl_tk in wl_prices:
                        wl_curr, wl_prev = wl_prices[wl_tk]
                        wl_chg = ((wl_curr - wl_prev) / wl_prev) * \
                            100 if wl_prev != 0 else 0
                        wl_color = "#22c55e" if wl_chg >= 0 else "#ef4444"
                        wl_sign = "+" if wl_chg >= 0 else ""
                        wl_arrow = "▲" if wl_chg >= 0 else "▼"
                        wl_html += f'<div class="transition-all" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-left: 3px solid {wl_color}; border-radius: 12px; padding: 14px 20px; min-width: 170px; flex: 1; max-width: 220px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);"><a class="screener-link" href="?ticker={wl_tk}" target="_self"><span class="ticker-badge" style="margin-bottom: 6px;">{wl_tk}</span></a><div class="num-value" style="font-size: 20px; font-weight: 700; margin-top: 6px; color: #ffffff;">${wl_curr:,.2f}</div><div class="num-value" style="color: {wl_color}; font-weight: 600; font-size: 14px; margin-top: 2px;">{wl_arrow} {wl_sign}{wl_chg:.2f}%</div></div>'
                    else:
                        wl_html += f'<div class="transition-all" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); border-radius: 12px; padding: 14px 20px; min-width: 170px; flex: 1; max-width: 220px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);"><a class="screener-link" href="?ticker={wl_tk}" target="_self"><span class="ticker-badge" style="margin-bottom: 6px;">{wl_tk}</span></a><div style="font-size: 14px; color: #64748b; margin-top: 6px;">Data unavailable</div></div>'
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
            raw = yf.download(ticker_list, period="5d",
                              progress=False, threads=True)
            if isinstance(raw.columns, pd.MultiIndex):
                batch_prices = raw['Close']
            else:
                batch_prices = raw[['Close']].rename(columns={'Close': ticker_list[0]}) if len(
                    ticker_list) == 1 else raw['Close']
        except Exception:
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
                        pct = ((curr - prev) / prev) * \
                            100 if prev != 0 else 0.0
                        price_data[tkr] = (curr, pct)
                        valid_tickers.append(tkr)
                except Exception:
                    pass

        if not valid_tickers:
            return pd.DataFrame()

        # STEP 2: Fetch market caps in parallelo con retry + throttle
        def get_mcap(tkr):
            for attempt in range(3):
                try:
                    mcap = float(yf.Ticker(tkr).fast_info.market_cap)
                    return tkr, mcap
                except Exception:
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
        html_table = requests.get(
            url, headers={'User-Agent': 'Mozilla/5.0'}).text
        raw_tickers = pd.read_html(io.StringIO(html_table))[
            0]['Symbol'].tolist()

        # Converti punti in trattini (es. BRK.B -> BRK-B, BF.B -> BF-B)
        cleaned = [t.replace('.', '-') for t in raw_tickers]

        # Rimuovi duplicati classe azioni (GOOG/GOOGL -> tieni solo GOOGL)
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
            html = requests.get(
                url, headers={'User-Agent': 'Mozilla/5.0'}).text
            df_wiki = pd.read_html(io.StringIO(html))[0]
            return dict(zip(df_wiki['Symbol'].str.replace('.', '-', regex=False), df_wiki['GICS Sector']))
        except Exception:
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
            except Exception:
                st.error("Wikipedia Data non disponibile.")

    with st.spinner(f"Sincronizzazione dati live... | '{random.choice(WALL_STREET_QUOTES)}'"):
        df_display = fetch_home_data(tuple(tks_to_fetch))

    # Applica filtro Gainers/Losers
    if not df_display.empty:
        if st.session_state.home_filter == "Gainers":
            df_display = df_display[df_display['Change'] > 0].sort_values(
                by='Change', ascending=False)
        elif st.session_state.home_filter == "Losers":
            df_display = df_display[df_display['Change'] < 0].sort_values(
                by='Change', ascending=True)

    # Market Summary bar
    if not df_display.empty:
        avg_change = df_display['Change'].mean()
        total_mcap = df_display['MarketCap'].sum()
        gainers_count = (df_display['Change'] > 0).sum()
        losers_count = (df_display['Change'] < 0).sum()

        sm1, sm2, sm3, sm4 = st.columns(4)
        sm1.metric("Stocks Loaded", f"{len(df_display)}")
        sm2.metric("Avg Change", f"{avg_change:+.2f}%")
        sm3.metric("Gainers", f"{gainers_count}",
                   delta=f"{gainers_count}", delta_color="normal")
        sm4.metric("Losers", f"{losers_count}",
                   delta=f"-{losers_count}", delta_color="normal")
        st.write("")

    if not df_display.empty:
        html_str = '<table class="market-table"><thead><tr><th style="width:5%">#</th><th style="width:30%">NAME</th><th style="width:15%">TICKER</th><th style="width:18%">LAST PRICE</th><th style="width:17%">PRICE CHANGE</th><th style="width:15%">MARKET CAP</th></tr></thead><tbody>'
        for idx, (_, row) in enumerate(df_display.iterrows(), 1):
            tkr = row['Ticker']
            name = row['Name']
            if len(name) > 28:
                name = name[:25] + "..."
            price = row['Price']
            change = row['Change']
            mcap = row['MarketCap']
            domain = row['Domain']

            if mcap >= 1e12:
                mcap_str = f"${mcap/1e12:.3f}T"
            elif mcap >= 1e9:
                mcap_str = f"${mcap/1e9:.3f}B"
            elif mcap >= 1e6:
                mcap_str = f"${mcap/1e6:.1f}M"
            else:
                mcap_str = "N/A"

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
                <td><a class="screener-link" href="?ticker={tkr}" target="_self"><span class="ticker-badge">{tkr}</span></a></td>
                <td class="num-value"><strong>${price:,.2f}</strong></td>
                <td class="num-value"><span class="pill {pill_class}">{sign}{change:.2f}%</span></td>
                <td class="num-value"><span class="mcap-val">{mcap_str}</span></td>
            </tr>'''
        html_str += "</tbody></table>"
        st.markdown(html_str, unsafe_allow_html=True)
    else:
        if st.session_state.home_filter != "S&P 500":
            st.info(
                f"Nessun titolo trovato nella categoria '{st.session_state.home_filter}' al momento.")
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
        except Exception:
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
        initial_cap = st.number_input(
            "Initial Investment ($)", min_value=0.0, value=1000.0)
        rate = st.number_input("Annual Rate (%)", min_value=0.0, value=5.0)
    with col2:
        years = int(st.number_input("Years", min_value=1, value=10))
        freq = st.selectbox("Compounding Frequency", [
                            "Annually", "Semi-annually", "Quarterly", "Monthly"])
        freq_map = {"Annually": 1, "Semi-annually": 2,
                    "Quarterly": 4, "Monthly": 12}

    if st.button("🚀 Calculate", type="primary", use_container_width=True):
        data = []
        r_dec = rate / 100
        for y in range(years + 1):
            m = initial_cap * \
                (1 + r_dec / freq_map[freq]) ** (freq_map[freq] * y)
            data.append({"Year": y, "Total Capital ($)": round(m, 2)})
        df = pd.DataFrame(data)
        st.success(
            f"**Final Total:** $ {df.iloc[-1]['Total Capital ($)']:,.2f}")
        st.plotly_chart(px.area(df, x="Year", y="Total Capital ($)",
                        markers=True), use_container_width=True)

# ==========================================
# PAGE 2: STOCK TRACKER
# ==========================================
elif page_choice == "📊 Stock Tracker":
    st.title("📊 Institutional Equity Analysis")
    st.divider()

    with st.form("stock_tracker_form", enter_to_submit=True):
        col1, col2, col3, col4 = st.columns(4)
        default_ticker = st.session_state.get('active_ticker', 'KO')
        with col1:
            ticker_input = st.text_input(
                "Stock Ticker", value=default_ticker).upper()
        with col2:
            invested_cap = st.number_input(
                "Initial Investment ($)", min_value=100.0, value=1000.0)
        with col3:
            backtest_years = st.slider(
                "Years of History", min_value=1, max_value=20, value=10)
        with col4:
            benchmark_ticker = st.text_input(
                "Benchmark (Compare)", value="SPY").upper()

        # Salviamo i parametri in sessione per non perderli al ricarico della pagina (es. al toggle DRIP)
        submitted = st.form_submit_button(
            "🚀 Run Deep Analysis", type="primary", use_container_width=True)
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
                rt_price = rt_hist['Close'].iloc[-1] if not rt_hist.empty else info.get(
                    'currentPrice', hist_data['Close'].iloc[-1])

                prev_close = info.get(
                    'previousClose', hist_data['Close'].iloc[-2] if len(hist_data) > 1 else rt_price)
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

                # Helper to safely extract numeric values (handles None, NaN, non-numeric)
                def _safe_num(val):
                    if val is None:
                        return None
                    try:
                        import pandas as pd
                        if pd.isna(val):
                            return None
                    except Exception:
                        pass
                    return val if isinstance(val, (int, float)) else None

                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Market Cap", format_large_numbers(rt_mcap))

                # Trailing PE
                val_tpe = _safe_num(info.get('trailingPE'))
                # Manual calculation fallback if PE is missing but EPS and Price are present
                if val_tpe is None:
                    e_ttm = _safe_num(info.get('trailingEps'))
                    if e_ttm and e_ttm > 0 and rt_price:
                        val_tpe = rt_price / e_ttm
                m2.metric("P/E (Trailing)", round(val_tpe, 2)
                          if val_tpe is not None else 'N/A')

                # EPS (TTM)
                eps_ttm = _safe_num(info.get('trailingEps'))
                m3.metric(
                    "EPS (TTM)", f"${eps_ttm:.2f}" if eps_ttm is not None else 'N/A')

                # Dividend Rate
                div_rate = _safe_num(info.get('dividendRate'))
                m4.metric(
                    "Div Rate", f"${div_rate:.2f}" if div_rate is not None else 'N/A')

                st.write("")

                m5, m6, m7, m8 = st.columns(4)
                m5.metric("Current Price",
                          f"${rt_price:,.2f}", f"{change:.2f}%")

                # Forward PE
                val_fpe = _safe_num(info.get('forwardPE'))
                if val_fpe is None:
                    e_fwd = _safe_num(info.get('forwardEps'))
                    if e_fwd and e_fwd > 0 and rt_price:
                        val_fpe = rt_price / e_fwd
                m6.metric("P/E (Forward)", round(val_fpe, 2)
                          if val_fpe is not None else 'N/A')

                # EPS (Forward)
                eps_fwd = _safe_num(info.get('forwardEps'))
                m7.metric("EPS (Forward)",
                          f"${eps_fwd:.2f}" if eps_fwd is not None else 'N/A')

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
                q3.metric("Volatility (Annual)",
                          f"{returns.std()*np.sqrt(252)*100:.2f}%")
                st.divider()

                # --- SIMULATORE PREZZO (DRIP VS NO DRIP) ---
                shares_with_drip = a_cap / hist_data['Close'].iloc[0]
                shares_no_drip = shares_with_drip
                cash_no_drip = 0
                val_with_drip_series, val_no_drip_series, val_price_only_series = [], [], []
                div_history = []

                # Variabili aggiuntive per le statistiche DRIP annuali (sempre simulate)
                sim_shares_drip = shares_no_drip
                reinvested_shares_by_year = {}  # {year: shares_bought}
                div_by_year = {}  # {year: div_received}
                shares_at_year_end = {}  # {year: shares_owned}

                for i in range(len(hist_data)):
                    price = hist_data['Close'].iloc[i]
                    div = hist_data['Dividends'].iloc[i]
                    date = hist_data.index[i]
                    year = date.year

                    if year not in reinvested_shares_by_year:
                        reinvested_shares_by_year[year] = 0.0
                        div_by_year[year] = 0.0

                    # 1. Simulatore DRIP costante per statistiche
                    div_incassato_drip_sim = div * sim_shares_drip
                    if div > 0:
                        shares_bought_sim = div_incassato_drip_sim / price
                        sim_shares_drip += shares_bought_sim
                        reinvested_shares_by_year[year] += shares_bought_sim
                        div_by_year[year] += div_incassato_drip_sim

                    shares_at_year_end[year] = sim_shares_drip

                    # 2. Simulatore completo per entrambi i casi (incondizionato per statistiche corrette)
                    if div > 0:
                        # Caso con DRIP: dividendi reinvestiti sulle quote accumulate finora
                        div_incassato_drip = div * shares_with_drip
                        shares_with_drip += div_incassato_drip / price

                        # Caso senza DRIP: dividendi incassati come cash sulle quote iniziali (che non variano)
                        div_incassato_no_drip = div * shares_no_drip
                        cash_no_drip += div_incassato_no_drip

                        # Salviamo lo storico dei dividendi incassati (con DRIP di default per l'effetto Snowball)
                        div_history.append(
                            {"Date": date, "Amount": div_incassato_drip})

                    val_with_drip_series.append(shares_with_drip * price)
                    val_no_drip_series.append(
                        (shares_no_drip * price) + cash_no_drip)
                    val_price_only_series.append(shares_no_drip * price)

                # --- SISTEMA DI TAB ---
                # Scarica report istituzionale
                st.divider()
                with st.expander("📄 Genera Report PDF (Tear Sheet)"):
                    pdf_bytes = generate_pdf_report(
                        a_ticker, rt_price, info, sharpe, max_dd)
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
                    with col_t1:
                        st.subheader("Historical Performance")
                    with col_t2:
                        chart_type = st.toggle(
                            "Mostra Analisi Tecnica (Candele)", value=False)

                    if chart_type:
                        fig_cand = make_subplots(
                            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])

                        # Candele
                        fig_cand.add_trace(go.Candlestick(
                            x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], name='Price'), row=1, col=1)
                        # Medie Mobili
                        sma50 = hist_data['Close'].rolling(window=50).mean()
                        sma200 = hist_data['Close'].rolling(window=200).mean()
                        fig_cand.add_trace(go.Scatter(x=hist_data.index, y=sma50, line=dict(
                            color='orange', width=1.5), name='SMA 50'), row=1, col=1)
                        fig_cand.add_trace(go.Scatter(x=hist_data.index, y=sma200, line=dict(
                            color='purple', width=1.5), name='SMA 200'), row=1, col=1)
                        # Volumi
                        colors = ['#27AE60' if c >= o else '#E74C3C' for c, o in zip(
                            hist_data['Close'], hist_data['Open'])]
                        fig_cand.add_trace(go.Bar(
                            x=hist_data.index, y=hist_data['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

                        fig_cand.update_layout(
                            xaxis_rangeslider_visible=False, height=600, margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_cand, use_container_width=True)

                    else:
                        bench_raw = yf.download(
                            a_bench, start=hist_data.index[0], end=hist_data.index[-1], progress=False)
                        if not bench_raw.empty:
                            if 'Close' in bench_raw.columns:
                                bench_close = bench_raw['Close'].squeeze()
                            else:
                                bench_close = bench_raw.squeeze()  # Se non usa multistrato

                            stock_close = hist_data['Close'].squeeze()

                            norm_stock = (
                                stock_close / stock_close.iloc[0]) * 100
                            norm_bench = (
                                bench_close / bench_close.iloc[0]) * 100

                            fig_comp = go.Figure()
                            fig_comp.add_trace(go.Scatter(
                                x=norm_stock.index, y=norm_stock, name=a_ticker, line=dict(color='#2E86C1', width=2)))
                            fig_comp.add_trace(go.Scatter(
                                x=norm_bench.index, y=norm_bench, name=a_bench, line=dict(color='#E74C3C', width=2)))
                            fig_comp.update_layout(yaxis_title="Value of 100$ Investment", hovermode="x unified", legend=dict(
                                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1), margin=dict(l=0, r=0, t=30, b=0))
                            st.plotly_chart(fig_comp, use_container_width=True)
                        else:
                            st.warning("Dati benchmark non disponibili.")

                # --- TAB 2: DIVIDENDS ---
                with tab_divs:
                    st.subheader("Total Return & Dividend Compounding")

                    tot_ret_drip = (val_with_drip_series[-1] / a_cap) - 1
                    tot_ret_no_drip = (val_no_drip_series[-1] / a_cap) - 1

                    # Calcolo robusto del tasso di dividendo con fallbacks
                    div_rate_val = info.get('dividendRate')
                    if div_rate_val is None or div_rate_val == 0:
                        div_rate_val = info.get('trailingAnnualDividendRate')
                    if div_rate_val is None or div_rate_val == 0:
                        # Fallback sui dividendi storici degli ultimi 12 mesi
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
                    pm1.metric("Total Return (with DRIP)",
                               format_perc(tot_ret_drip))
                    pm1.metric("Yield on Cost (with DRIP)",
                               format_perc(yoc_drip))
                    pm2.metric("Total Return (w/o DRIP)",
                               format_perc(tot_ret_no_drip))
                    pm2.metric("Yield on Cost (w/o DRIP)",
                               format_perc(yoc_no_drip))

                    fig_perf = go.Figure()
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=val_with_drip_series,
                                       name='Total Return (with DRIP)', fill='tozeroy', line=dict(color='#27AE60')))
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=val_no_drip_series,
                                       name='Total Return (w/o DRIP)', line=dict(color='#2E86C1')))
                    fig_perf.add_trace(go.Scatter(x=hist_data.index, y=val_price_only_series,
                                       name='Price Only', line=dict(color='#95A5A6', dash='dash')))
                    fig_perf.update_layout(
                        yaxis_title="Portfolio Value ($)", margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_perf, use_container_width=True)

                    st.divider()

                    st.subheader("❄️ The Dividend Snowball Effect")
                    if div_history:
                        df_div = pd.DataFrame(div_history)
                        df_div['Year'] = df_div['Date'].dt.year
                        yearly_div = df_div.groupby(
                            'Year')['Amount'].sum().reset_index()

                        fig_snow = px.bar(yearly_div, x='Year', y='Amount',
                                          text_auto='.2f', color_discrete_sequence=['#F1C40F'])
                        fig_snow.update_layout(
                            xaxis_title="Year", yaxis_title="Dividends Received ($)", margin=dict(l=0, r=0, t=30, b=0))
                        st.plotly_chart(fig_snow, use_container_width=True)
                    else:
                        st.info(
                            "Questo titolo non ha distribuito dividendi nel periodo selezionato.")

                    st.divider()
                    st.subheader("📈 Dividend Growth (CAGR)")

                    raw_divs = hist_data['Dividends'][hist_data['Dividends'] > 0]
                    if not raw_divs.empty:
                        annual_divs = raw_divs.groupby(
                            raw_divs.index.year).sum()
                        current_year = datetime.today().year
                        annual_divs = annual_divs[annual_divs.index <
                                                  current_year]

                        if len(annual_divs) >= 2:
                            latest_div = annual_divs.iloc[-1]
                            c1, c2, c3 = st.columns(3)

                            anni_totali = len(annual_divs) - 1
                            primo_div = annual_divs.iloc[0]
                            cagr_tot = calc_cagr(
                                primo_div, latest_div, anni_totali)
                            c1.metric(
                                f"CAGR ({anni_totali} Anni)", format_perc(cagr_tot))

                            if len(annual_divs) >= 6:
                                div_5y_ago = annual_divs.iloc[-6]
                                cagr_5y = calc_cagr(div_5y_ago, latest_div, 5)
                                c2.metric("CAGR (5 Anni)",
                                          format_perc(cagr_5y))
                            else:
                                c2.metric("CAGR (5 Anni)", "N/A")

                            if len(annual_divs) >= 4:
                                div_3y_ago = annual_divs.iloc[-4]
                                cagr_3y = calc_cagr(div_3y_ago, latest_div, 3)
                                c3.metric("CAGR (3 Anni)",
                                          format_perc(cagr_3y))
                            else:
                                c3.metric("CAGR (3 Anni)", "N/A")
                        else:
                            st.info(
                                "Storico di anni completi insufficiente per calcolare la crescita annuale composta (CAGR).")

                    # --- DETTAGLIO AZIONI POSSEDUTE E RIACQUISTO DIVIDENDI (DRIP) ---
                    st.divider()
                    st.subheader("❄️ Reinvestment & Share Ownership Details")

                    initial_shares = a_cap / hist_data['Close'].iloc[0]
                    current_shares_actual = shares_with_drip

                    st.write(
                        "Analizziamo in dettaglio come l'investimento iniziale ha generato e accumulato quote azionarie nel tempo.")

                    oc1, oc2 = st.columns(2)

                    # Colonna 1: Stato Attuale con DRIP
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

                    # Colonna 2: Vantaggio dell'effetto DRIP
                    with oc2:
                        extra_shares = sim_shares_drip - initial_shares
                        pct_increase = (extra_shares / initial_shares) * \
                            100 if initial_shares > 0 else 0
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
                    st.markdown(
                        "#### 📅 Piano di Accumulo Reinvestimenti (DRIP)")
                    st.write(
                        "Dettaglio anno per anno delle azioni riacquistate e della crescita del portafoglio grazie al reinvestimento automatico dei dividendi:")

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
                            total_sh = shares_at_year_end.get(
                                yr, initial_shares)

                            table_html += f"""
                            <tr>
                                <td><span class="ticker-badge" style="background: rgba(255, 255, 255, 0.08); box-shadow: none; color: #ffffff !important;">{yr}</span></td>
                                <td style="text-align: right; font-weight: 600; color: #00FF7F;">${div_rec:,.2f}</td>
                                <td style="text-align: right; font-weight: 600; color: #00f2fe;">+{shares_b:.3f}</td>
                                <td style="text-align: right; font-weight: 700; color: #ffffff;">{total_sh:.3f}</td>
                            </tr>
                            """

                        table_html += """
                            </tbody>
                        </table>
                        """
                        clean_table_html = "\n".join(
                            [line.strip() for line in table_html.split("\n")])
                        st.markdown(clean_table_html, unsafe_allow_html=True)
                    else:
                        st.info(
                            "Questo titolo non ha distribuito dividendi nel periodo selezionato, quindi non ci sono riacquisti da mostrare.")

                # --- TAB 3: PROJECTIONS ---
                with tab_mc:
                    st.subheader("🎲 Monte Carlo Simulation (5Y Projection)")
                    st.write(
                        "Simulazione basata sul Geometric Brownian Motion (GBM).")

                    log_returns = np.log(1 + returns)
                    mu, sigma = log_returns.mean(), log_returns.std()

                    sim_days, num_sim = 252 * 5, 100
                    last_price = hist_data['Close'].iloc[-1]
                    last_date = hist_data.index[-1]

                    daily_sim_returns = np.exp(np.random.normal(
                        mu - 0.5 * sigma**2, sigma, (sim_days, num_sim)))
                    sims = np.zeros_like(daily_sim_returns)
                    sims[0] = last_price
                    for t in range(1, sim_days):
                        sims[t] = sims[t-1] * daily_sim_returns[t]

                    future_dates = pd.date_range(
                        start=last_date, periods=sim_days, freq='B')

                    # --- 3D MONTE CARLO PROBABILITY SURFACE ---
                    # Appiattiamo le simulazioni per formare una matrice di densità 2D
                    time_idx = np.repeat(np.arange(sim_days), num_sim)
                    price_vals = sims.flatten()

                    try:
                        H, xedges, yedges = np.histogram2d(
                            time_idx, price_vals, bins=[50, 50])
                        H_z = H.T

                        # Sfoca la superficie per renderla più 'rocciosa' e naturale se c'è scipy
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
                                xaxis=dict(backgroundcolor="rgba(0,0,0,0)",
                                           gridcolor="rgba(255,255,255,0.1)"),
                                yaxis=dict(backgroundcolor="rgba(0,0,0,0)",
                                           gridcolor="rgba(255,255,255,0.1)"),
                                zaxis=dict(
                                    backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)", showticklabels=False)
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
                        except Exception:
                            holders = None
                        if holders is not None and not holders.empty:
                            holders_df = holders.copy()
                            if isinstance(holders_df, pd.Series):
                                holders_df = holders_df.to_frame()

                            holders_df = holders_df.reset_index()
                            if len(holders_df.columns) >= 2:
                                holders_df.columns = [
                                    "Descrizione", "Valore"] + list(holders_df.columns[2:])

                                label_map = {
                                    'insidersPercentHeld': '% Held by Insiders',
                                    'institutionsPercentHeld': '% Held by Institutions',
                                    'institutionsFloatPercentHeld': '% Float Held by Institutions',
                                    'institutionsCount': 'Number of Institutions'
                                }
                                holders_df['Descrizione'] = holders_df['Descrizione'].replace(
                                    label_map)

                                def format_holder_val(row):
                                    val = pd.to_numeric(
                                        row['Valore'], errors='coerce')
                                    if pd.isna(val):
                                        return row['Valore']
                                    if "Number" in str(row['Descrizione']) or val > 1.5:
                                        return f"{int(val):,}"
                                    else:
                                        return f"{val * 100:.2f}%"
                                holders_df['Valore'] = holders_df.apply(
                                    format_holder_val, axis=1)

                            st.dataframe(
                                holders_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Ownership data not available.")

                    with col_h2:
                        st.write("**Top Institutional Holders**")
                        try:
                            inst_holders = stock.institutional_holders
                        except Exception:
                            inst_holders = None
                        if inst_holders is not None and not inst_holders.empty:
                            inst_df = inst_holders.copy()

                            inst_df.rename(
                                columns={'pctHeld': '% Held', 'pctChange': '% Change'}, inplace=True)

                            for col in ['% Held', '% Out', '% Change']:
                                if col in inst_df.columns:
                                    inst_df[col] = (pd.to_numeric(
                                        inst_df[col], errors='coerce') * 100).map("{:.2f}%".format)
                            if 'Shares' in inst_df.columns:
                                inst_df['Shares'] = pd.to_numeric(inst_df['Shares'], errors='coerce').apply(
                                    lambda x: format_large_numbers(x, is_currency=False))
                            if 'Value' in inst_df.columns:
                                inst_df['Value'] = pd.to_numeric(
                                    inst_df['Value'], errors='coerce').apply(format_large_numbers)
                            st.dataframe(
                                inst_df, use_container_width=True, hide_index=True)
                        else:
                            st.info("Institutional data not available.")

                # --- TAB 5: FINANCIAL HEALTH (VISUAL CHARTS) ---
                with tab_fhealth:
                    st.subheader("📈 Financial Health — Trend Analysis")
                    st.markdown(
                        "<p style='color: #8A929A; margin-top:-10px; margin-bottom:20px;'>Andamento storico dei principali indicatori fondamentali anno per anno.</p>", unsafe_allow_html=True)

                    # --- Fetch 10+ Years Financial Data (Multi-Source) ---
                    _FMP_API_KEY = "ZIDZlYJLFBKtr9HgMsCF79zuPv540wkn"

                    # Source 1: Macrotrends (10-15 anni, scraping)
                    mt_inc, mt_bal, mt_cash = fetch_macrotrends_financials(
                        a_ticker, limit_years=10)
                    # Source 2: FMP API (5 anni)
                    fmp_inc, fmp_bal, fmp_cash = fetch_fmp_financials(
                        a_ticker, _FMP_API_KEY)
                    # Source 3: Yahoo Finance Extended (5-8 anni)
                    yf_inc, yf_bal, yf_cash = fetch_financials_extended(
                        a_ticker)

                    # Combine: macrotrends primary -> FMP fills gaps -> yfinance fills remaining
                    if not mt_inc.empty:
                        fh_inc = _merge_financial_dfs(
                            mt_inc, _merge_financial_dfs(fmp_inc, yf_inc))
                        fh_bal = _merge_financial_dfs(
                            mt_bal, _merge_financial_dfs(fmp_bal, yf_bal))
                        fh_cash = _merge_financial_dfs(
                            mt_cash, _merge_financial_dfs(fmp_cash, yf_cash))
                        n_years = len(fh_inc.columns)
                        st.caption(
                            f"📡 Sorgente: **Multi-Source ({n_years} anni)**")
                    elif not fmp_inc.empty:
                        fh_inc = _merge_financial_dfs(fmp_inc, yf_inc)
                        fh_bal = _merge_financial_dfs(fmp_bal, yf_bal)
                        fh_cash = _merge_financial_dfs(fmp_cash, yf_cash)
                        n_years = len(fh_inc.columns)
                        st.caption(
                            f"📡 Sorgente: **FMP + Yahoo Finance ({n_years} anni)**")
                    elif yf_inc is not None and not yf_inc.empty:
                        fh_inc, fh_bal, fh_cash = yf_inc, yf_bal, yf_cash
                        n_years = len(fh_inc.columns)
                        st.caption(
                            f"📡 Sorgente: **Yahoo Finance ({n_years} anni)**")
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
                        row.index = [c.year if hasattr(
                            c, 'year') else str(c) for c in row.index]
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
                        xaxis=dict(
                            gridcolor='rgba(255,255,255,0.06)', dtick=1),
                        yaxis=dict(gridcolor='rgba(255,255,255,0.06)'),
                        hovermode='x unified',
                        legend=dict(orientation='h', yanchor='bottom',
                                    y=1.02, xanchor='right', x=1)
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
                            colors_rev = [
                                '#3b82f6' if v >= 0 else '#ef4444' for v in revenue.values]
                            fig_rev.add_trace(go.Bar(
                                x=[str(y) for y in revenue.index], y=revenue.values,
                                marker_color=colors_rev, name='Revenue',
                                text=[format_large_numbers(
                                    v) for v in revenue.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_rev.update_layout(
                                title='💵 Total Revenue', **_chart_layout)
                            st.plotly_chart(fig_rev, use_container_width=True)
                        else:
                            st.info("Revenue data not available.")

                    with ch_col2:
                        if net_income is not None and len(net_income) >= 2:
                            has_any_chart = True
                            fig_ni = go.Figure()
                            colors_ni = [
                                '#22c55e' if v >= 0 else '#ef4444' for v in net_income.values]
                            fig_ni.add_trace(go.Bar(
                                x=[str(y) for y in net_income.index], y=net_income.values,
                                marker_color=colors_ni, name='Net Income',
                                text=[format_large_numbers(
                                    v) for v in net_income.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_ni.update_layout(
                                title='📊 Net Income', **_chart_layout)
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
                            colors_eps = [
                                '#a78bfa' if v >= 0 else '#ef4444' for v in eps_series.values]
                            fig_eps.add_trace(go.Bar(
                                x=[str(y) for y in eps_series.index], y=eps_series.values,
                                marker_color=colors_eps, name='EPS',
                                text=[f"${v:.2f}" for v in eps_series.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_eps.update_layout(
                                title='💰 Earnings Per Share (EPS)', **_chart_layout)
                            st.plotly_chart(fig_eps, use_container_width=True)
                        else:
                            st.info("EPS data not available.")

                    with ch_col4:
                        if fcf is not None and len(fcf) >= 2:
                            has_any_chart = True
                            fig_fcf = go.Figure()
                            colors_fcf = ['#06b6d4' if v >=
                                          0 else '#ef4444' for v in fcf.values]
                            fig_fcf.add_trace(go.Bar(
                                x=[str(y) for y in fcf.index], y=fcf.values,
                                marker_color=colors_fcf, name='FCF',
                                text=[format_large_numbers(
                                    v) for v in fcf.values],
                                textposition='outside', textfont=dict(size=11)
                            ))
                            fig_fcf.update_layout(
                                title='🏦 Free Cash Flow', **_chart_layout)
                            st.plotly_chart(fig_fcf, use_container_width=True)
                        else:
                            st.info("Free Cash Flow data not available.")

                    # ──── CHART 5 & 6: Debt vs Equity + Margins ────
                    total_debt = _extract_annual_series(fh_bal, 'Total Debt')
                    total_equity = _extract_annual_series(
                        fh_bal, 'Stockholders Equity')
                    if total_equity is None:
                        total_equity = _extract_annual_series(
                            fh_bal, 'Total Stockholders Equity')

                    # Margins from income statement
                    gross_profit = _extract_annual_series(
                        fh_inc, 'Gross Profit')
                    operating_income = _extract_annual_series(
                        fh_inc, 'Operating Income')

                    ch_col5, ch_col6 = st.columns(2)

                    with ch_col5:
                        if total_debt is not None and total_equity is not None:
                            has_any_chart = True
                            # Align on common years
                            common_years = sorted(
                                set(total_debt.index) & set(total_equity.index))
                            if len(common_years) >= 2:
                                fig_de = go.Figure()
                                fig_de.add_trace(go.Bar(
                                    x=[str(y) for y in common_years],
                                    y=[total_debt[y] for y in common_years],
                                    name='Total Debt',
                                    marker_color='#ef4444',
                                    text=[format_large_numbers(
                                        total_debt[y]) for y in common_years],
                                    textposition='outside', textfont=dict(size=10)
                                ))
                                fig_de.add_trace(go.Bar(
                                    x=[str(y) for y in common_years],
                                    y=[total_equity[y] for y in common_years],
                                    name='Equity',
                                    marker_color='#22c55e',
                                    text=[format_large_numbers(
                                        total_equity[y]) for y in common_years],
                                    textposition='outside', textfont=dict(size=10)
                                ))
                                fig_de.update_layout(
                                    title='⚖️ Debt vs Equity', barmode='group', **_chart_layout)
                                st.plotly_chart(
                                    fig_de, use_container_width=True)
                            else:
                                st.info(
                                    "Not enough common years for Debt vs Equity chart.")
                        else:
                            st.info("Debt / Equity data not available.")

                    with ch_col6:
                        # Compute margins %
                        if revenue is not None and len(revenue) >= 2:
                            fig_margins = go.Figure()
                            margin_plotted = False

                            if gross_profit is not None:
                                common = sorted(
                                    set(revenue.index) & set(gross_profit.index))
                                if len(common) >= 2:
                                    gm = [(gross_profit[y] / revenue[y]) *
                                          100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=gm,
                                        name='Gross Margin %', mode='lines+markers',
                                        line=dict(color='#3b82f6', width=2.5),
                                        marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if operating_income is not None:
                                common = sorted(set(revenue.index) & set(
                                    operating_income.index))
                                if len(common) >= 2:
                                    om = [(operating_income[y] / revenue[y]) *
                                          100 if revenue[y] != 0 else 0 for y in common]
                                    fig_margins.add_trace(go.Scatter(
                                        x=[str(y) for y in common], y=om,
                                        name='Operating Margin %', mode='lines+markers',
                                        line=dict(color='#f59e0b', width=2.5),
                                        marker=dict(size=8)
                                    ))
                                    margin_plotted = True

                            if net_income is not None:
                                common = sorted(
                                    set(revenue.index) & set(net_income.index))
                                if len(common) >= 2:
                                    nm = [
                                        (net_income[y] / revenue[y]) * 100 if revenue[y] != 0 else 0 for y in common]
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
                                st.plotly_chart(
                                    fig_margins, use_container_width=True)
                            else:
                                st.info("Margin data not available.")
                        else:
                            st.info(
                                "Revenue data insufficient for margin calculation.")

                    # ──── CHART 7 (Full Width): EBITDA Trend ────
                    ebitda = _extract_annual_series(fh_inc, 'EBITDA')
                    if ebitda is not None and len(ebitda) >= 2:
                        has_any_chart = True
                        fig_ebitda = go.Figure()
                        fig_ebitda.add_trace(go.Scatter(
                            x=[str(y) for y in ebitda.index], y=ebitda.values,
                            mode='lines+markers+text',
                            line=dict(color='#f97316', width=3),
                            marker=dict(size=10, color='#f97316',
                                        line=dict(width=2, color='#ffffff')),
                            text=[format_large_numbers(v)
                                  for v in ebitda.values],
                            textposition='top center', textfont=dict(size=11),
                            fill='tozeroy', fillcolor='rgba(249, 115, 22, 0.08)',
                            name='EBITDA'
                        ))
                        fig_ebitda.update_layout(title='🔥 EBITDA Trend', height=350, **{
                                                 k: v for k, v in _chart_layout.items() if k != 'height'})
                        st.plotly_chart(fig_ebitda, use_container_width=True)

                    if not has_any_chart:
                        st.warning(
                            "⚠️ Nessun dato fondamentale disponibile per questo ticker. Potrebbe trattarsi di un ETF o di un titolo con dati limitati.")

                # --- TAB 6: EARNINGS & FUNDS ---
                with tab_funds:
                    st.subheader("📅 Upcoming Earnings & Estimates")
                    try:
                        earn_data = stock.earnings_dates
                    except Exception:
                        try:
                            # Fallback to stock.calendar se earnings_dates fallisce (es. KeyError su Streamlit Cloud)
                            cal = stock.calendar
                            if cal and 'Earnings Date' in cal and cal['Earnings Date']:
                                earn_dates = cal['Earnings Date']
                                earn_data = pd.DataFrame({
                                    "Earnings Date": earn_dates,
                                    "EPS Est. Average": [cal.get("Earnings Average", "N/A")] * len(earn_dates),
                                    "Rev Est. Average": [cal.get("Revenue Average", "N/A")] * len(earn_dates)
                                })
                                # Gestisci le date come indice se ci sono, per coerenza con earnings_dates
                                earn_data.set_index(
                                    "Earnings Date", inplace=True)
                            else:
                                earn_data = None
                        except Exception:
                            earn_data = None
                    if earn_data is not None:
                        st.dataframe(earn_data, use_container_width=True)
                    else:
                        st.info("Upcoming earnings dates not available.")

                    st.subheader("Financial Highlights")
                    h1, h2, h3 = st.columns(3)
                    with h1:
                        render_custom_metric("Profit Margin", format_perc(
                            info.get('profitMargins')), icon="💰")
                        render_custom_metric("ROE (ttm)", format_perc(
                            info.get('returnOnEquity')), icon="📈")
                    with h2:
                        render_custom_metric("Total Cash", format_large_numbers(
                            info.get('totalCash')), icon="💵")
                        render_custom_metric(
                            "Debt/Equity", str(info.get('debtToEquity', 'N/A')), icon="⚖️")
                    with h3:
                        render_custom_metric("Free Cash Flow", format_large_numbers(
                            info.get('leveredFreeCashFlow')), icon="💸")

                    st.divider()
                    st.subheader("📑 Full Financial Statements (Annual)")

                    inc_stmt, bal_sheet, cash_flow = fetch_financials(a_ticker)

                    def format_fin_df(df):
                        if df is None or df.empty:
                            return df
                        df_fmt = df.copy()
                        df_fmt.columns = [c.strftime(
                            '%Y-%m-%d') if hasattr(c, 'strftime') else str(c) for c in df_fmt.columns]
                        for col in df_fmt.columns:
                            df_fmt[col] = df_fmt[col].apply(
                                format_large_numbers)
                        return df_fmt

                    inc_stmt_fmt = format_fin_df(inc_stmt)
                    bal_sheet_fmt = format_fin_df(bal_sheet)
                    cash_flow_fmt = format_fin_df(cash_flow)

                    sub_t1, sub_t2, sub_t3 = st.tabs(
                        ["Income Statement", "Balance Sheet", "Cash Flow"])
                    with sub_t1:
                        if not inc_stmt_fmt.empty:
                            st.dataframe(
                                inc_stmt_fmt, use_container_width=True)
                        else:
                            st.info("Dati non disponibili.")
                    with sub_t2:
                        if not bal_sheet_fmt.empty:
                            st.dataframe(
                                bal_sheet_fmt, use_container_width=True)
                        else:
                            st.info("Dati non disponibili.")
                    with sub_t3:
                        if not cash_flow_fmt.empty:
                            st.dataframe(
                                cash_flow_fmt, use_container_width=True)
                        else:
                            st.info("Dati non disponibili.")

                    st.divider()
                    st.subheader("🤖 AI Financial Analysis")
                    st.write(
                        f"Sfrutta l'intelligenza artificiale locale di Gemma per analizzare i bilanci di **{a_ticker}** e ottenerne una valutazione della solidità.")
                    if st.button("⚖️ Genera Report Fondamentale", type="secondary"):
                        with st.spinner(f"Gemma sta scansionando i rendiconti annuali di {a_ticker} per elaborare un'analisi..."):
                            ai_report = analyze_financial_statements_ai(
                                a_ticker, inc_stmt, bal_sheet, cash_flow)
                            st.info(ai_report)

                # --- TAB 6: DCF VALUATION ---
                with tab_dcf:
                    st.subheader("🧮 Valutazione Fair Value (DCF Model)")
                    st.write(
                        "Calcolo a flussi di cassa scontati (Discounted Cash Flow).")
                    try:
                        inc_stmt_dcf, bal_sheet_dcf, cash_flow_dcf = fetch_financials(
                            a_ticker)
                        if not cash_flow_dcf.empty and 'Free Cash Flow' in cash_flow_dcf.index:
                            recent_fcf = cash_flow_dcf.loc['Free Cash Flow'].dropna(
                            ).iloc[0]
                        else:
                            recent_fcf = info.get('freeCashflow')

                        shares_out_dcf = info.get('sharesOutstanding')

                        if recent_fcf and shares_out_dcf and shares_out_dcf > 0:
                            dcf_col1, dcf_col2 = st.columns(2)
                            with dcf_col1:
                                fcf_growth_rate = st.number_input(
                                    "Tasso Crescita FCF (Anni 1-5) %", value=8.0) / 100
                                discount_rate = st.number_input(
                                    "Tasso di Sconto (WACC) %", value=10.0) / 100
                            with dcf_col2:
                                terminal_growth = st.number_input(
                                    "Tasso Crescita Terminale %", value=2.5) / 100

                            if discount_rate <= terminal_growth:
                                st.error(
                                    "⚠️ Errore Matematico: Il Tasso di Sconto (WACC) deve essere strettamente maggiore del Tasso Terminale per calcolare il Terminal Value.")
                            else:
                                if recent_fcf < 0:
                                    st.warning(
                                        "⚠️ L'azienda presenta un Free Cash Flow recente negativo. Il Fair Value risultante potrebbe essere negativo o inaffidabile, poiché il modello sconta perdite anziché profitti.")

                                pv_fcf = sum(
                                    [recent_fcf * (1 + fcf_growth_rate)**t / (1 + discount_rate)**t for t in range(1, 6)])
                                fcf_year_5 = recent_fcf * \
                                    (1 + fcf_growth_rate)**5
                                tv = (fcf_year_5 * (1 + terminal_growth)
                                      ) / (discount_rate - terminal_growth)
                                pv_tv = tv / (1 + discount_rate)**5

                                enterprise_value = pv_fcf + pv_tv
                                total_debt = info.get('totalDebt') or 0
                                total_cash = info.get('totalCash') or 0
                                net_debt = total_debt - total_cash
                                equity_value = enterprise_value - net_debt

                                raw_fair_value = equity_value / shares_out_dcf
                                fair_value = max(0, raw_fair_value)

                                if raw_fair_value < 0:
                                    st.info(
                                        f"Nota: Il valore teorico del capitale netto sarebbe negativo (${raw_fair_value:,.2f}), limitato a zero nel calcolo.")

                                margin_of_safety = (
                                    (fair_value - rt_price) / fair_value) if fair_value > 0 else 0
                                fv_col1, fv_col2 = st.columns(2)
                                with fv_col1:
                                    render_custom_metric(
                                        "Fair Value per Azione Stimato", f"${fair_value:,.2f}", icon="🎯")
                                with fv_col2:
                                    render_custom_metric(
                                        "Margine di Sicurezza", f"{margin_of_safety*100:.2f}%", icon="🛡️", is_positive=(margin_of_safety > 0))

                                if fair_value == 0:
                                    st.error(
                                        "🔴 Il Fair Value teorico è zero (o inferiore) a causa di flussi di cassa negativi o debito eccessivo.")
                                elif margin_of_safety > 0:
                                    st.success(
                                        "🟢 Il titolo sembra istituzionalmente **SOTTOVALUTATO** rispetto al Fair Value.")
                                else:
                                    st.error(
                                        "🔴 Il titolo sembra istituzionalmente **SOPRAVVALUTATO** rispetto al Fair Value.")
                        else:
                            st.info(
                                "Dati di cassa non sufficienti per il modello DCF.")
                    except Exception as e:
                        st.error("Errore nel calcolo DCF: " + str(e))

# ==========================================
# PAGE 3: MY PORTFOLIO
# ==========================================
elif page_choice == "📁 My Portfolio":
    st.title("📁 Institutional Portfolio Manager")
    st.write(
        "Gestisci le tue posizioni e visualizza la diversificazione del tuo capitale.")
    st.divider()

    # --- INPUT PER AGGIUNGERE TITOLI ---
    with st.expander("➕ Aggiungi Nuova Posizione", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        new_ticker = c1.text_input("Ticker (es. AAPL)").upper()
        new_shares = c2.number_input(
            "Quantità (Azioni/Quote)", min_value=0.0, step=0.1)
        new_price = c3.number_input("Prezzo di Acquisto ($) [opzionale]", min_value=0.0,
                                    step=1.0, value=0.0, help="Se lasciato a 0.0, userà il prezzo attuale di mercato")
        if c4.button("Aggiungi al Book") and new_ticker:
            try:
                check_df = yf.Ticker(new_ticker).history(period="1d")
                if check_df.empty:
                    st.error("Ticker non valido. Riprova.")
                else:
                    curr_price = float(check_df['Close'].iloc[-1])
                    purchase_price = new_price if new_price > 0.0 else curr_price
                    st.session_state['portfolio'].append({
                        "ticker": new_ticker,
                        "shares": new_shares,
                        "purchase_price": purchase_price
                    })
                    save_portfolio(st.session_state['portfolio'])
                    st.toast(f"{new_ticker} aggiunto con successo!", icon="✅")
                    st.rerun()
            except Exception:
                st.error("Errore imprevisto durante la validazione. Riprova.")

    # --- BACKUP / RECOVERY ---
    with st.expander("💾 Salva / Carica Backup Portafoglio", expanded=False):
        b_col1, b_col2 = st.columns(2)

        with b_col1:
            st.markdown("#### Esporta")
            st.write(
                "Scarica un file di backup per salvare le tue posizioni sul tuo computer.")
            portfolio_str = json.dumps(st.session_state['portfolio'], indent=2)
            st.download_button(
                label="📤 Scarica Backup Portafoglio (JSON)",
                data=portfolio_str,
                file_name="portfolio_backup.json",
                mime="application/json",
                key="btn_download_backup"
            )

        with b_col2:
            st.markdown("#### Importa")
            st.write("Ripristina le tue posizioni caricando il tuo file di backup.")
            uploaded_file = st.file_uploader("Scegli il file di backup (.json, .csv)", type=[
                                             "json", "csv"], key="uploader_backup")
            if uploaded_file is not None:
                try:
                    file_extension = uploaded_file.name.split('.')[-1].lower()
                    imported_portfolio = []

                    if file_extension == 'json':
                        imported_portfolio = json.load(uploaded_file)
                        if not isinstance(imported_portfolio, list):
                            st.error(
                                "Formato file non valido. Deve essere una lista JSON.")
                            imported_portfolio = []
                    elif file_extension == 'csv':
                        df_csv = pd.read_csv(uploaded_file)

                        # Mappa le colonne (cerca corrispondenze sia in inglese che in italiano)
                        col_mapping = {
                            'ticker': ['Ticker', 'ticker', 'TICKER'],
                            'shares': ['Quantità', 'Quantita', 'shares', 'Shares', 'Quantity', 'qty', 'Qty'],
                            'purchase_price': ["Prezzo d'Acquisto ($)", "Prezzo d'acquisto ($)", "Prezzo d'Acquisto", "Prezzo d'acquisto", "Prezzo Medio", "purchase_price", "Purchase Price", "purchasePrice", "price", "Price"]
                        }

                        ticker_col = None
                        shares_col = None
                        price_col = None

                        for col in df_csv.columns:
                            col_str = str(col).strip()
                            if not ticker_col and col_str in col_mapping['ticker']:
                                ticker_col = col
                            if not shares_col and col_str in col_mapping['shares']:
                                shares_col = col
                            if not price_col and col_str in col_mapping['purchase_price']:
                                price_col = col

                        # Fallback agli indici se non trovate colonne mappate
                        if not ticker_col and len(df_csv.columns) >= 1:
                            ticker_col = df_csv.columns[0]
                        if not shares_col and len(df_csv.columns) >= 2:
                            shares_col = df_csv.columns[1]
                        if not price_col and len(df_csv.columns) >= 3:
                            price_col = df_csv.columns[2]

                        if ticker_col and shares_col:
                            for _, row in df_csv.iterrows():
                                tk = str(row[ticker_col]).strip().upper()
                                if tk and tk != "NAN" and tk != "":
                                    # Gestisci valori nulli o non validi
                                    try:
                                        sh = float(row[shares_col]) if pd.notna(
                                            row[shares_col]) else 0.0
                                    except Exception:
                                        sh = 0.0
                                    try:
                                        pr = float(row[price_col]) if price_col and pd.notna(
                                            row[price_col]) else 0.0
                                    except Exception:
                                        pr = 0.0
                                    imported_portfolio.append({
                                        "ticker": tk,
                                        "shares": sh,
                                        "purchase_price": pr
                                    })
                        else:
                            st.error(
                                "Colonne Ticker o Quantità non trovate nel file CSV.")

                    if isinstance(imported_portfolio, list) and len(imported_portfolio) > 0:
                        st.session_state['portfolio'] = imported_portfolio
                        save_portfolio(imported_portfolio)
                        st.toast(
                            "Portafoglio importato con successo!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Nessun dato valido trovato nel file.")
                except Exception as e:
                    st.error(f"Errore durante l'importazione: {e}")

    # --- GOOGLE SHEETS SYNC ---
    with st.expander("📊 Sincronizzazione Google Sheets", expanded=False):
        st.markdown("### 🔄 Sincronizza il tuo portafoglio in tempo reale")
        st.write("Collega un foglio Google Sheets per salvare e sincronizzare automaticamente il tuo portafoglio su tutti i tuoi dispositivi.")

        # Cerca URL nei secrets o nel session state o in un file locale
        saved_url = ""
        if 'GSHEETS_URL' in st.secrets:
            saved_url = st.secrets['GSHEETS_URL']
        elif os.path.exists("gsheets_url.txt"):
            try:
                with open("gsheets_url.txt", "r") as f:
                    saved_url = f.read().strip()
            except Exception:
                pass

        gsheets_url = st.text_input(
            "URL del tuo Google Apps Script Web App",
            value=saved_url,
            help="Incolla l'URL della Web App generata da Google Sheets. Vedi le istruzioni sotto per configurarlo."
        )

        if gsheets_url:
            # Salva l'URL in gsheets_url.txt per persistenza locale
            if gsheets_url != saved_url:
                try:
                    with open("gsheets_url.txt", "w") as f:
                        f.write(gsheets_url)
                except Exception:
                    pass

            c_s1, c_s2 = st.columns(2)
            with c_s1:
                if st.button("🔄 Leggi da Google Sheets", key="btn_read_gsheets"):
                    with st.spinner("Lettura dati in corso da Google Sheets..."):
                        try:
                            import requests
                            res = requests.get(gsheets_url, timeout=10)
                            if res.status_code == 200:
                                imported_portfolio = res.json()
                                if isinstance(imported_portfolio, list):
                                    st.session_state['portfolio'] = imported_portfolio
                                    save_portfolio(imported_portfolio)
                                    st.toast(
                                        "Dati letti da Google Sheets con successo!", icon="✅")
                                    st.rerun()
                                else:
                                    st.error(
                                        "Dati ricevuti non validi. Verifica l'Apps Script.")
                            else:
                                st.error(
                                    f"Errore di connessione: HTTP {res.status_code}")
                        except Exception as e:
                            st.error(f"Errore durante la lettura: {e}")
            with c_s2:
                if st.button("📤 Invia a Google Sheets", key="btn_write_gsheets"):
                    with st.spinner("Invio dati in corso a Google Sheets..."):
                        try:
                            push_portfolio_to_gsheets(
                                st.session_state['portfolio'])
                            st.toast(
                                "Dati inviati a Google Sheets con successo!", icon="✅")
                        except Exception as e:
                            st.error(f"Errore durante l'invio: {e}")

            # Auto sync toggle
            auto_sync = st.checkbox("Sincronizzazione automatica ad ogni modifica", value=True,
                                    help="Se attivo, ogni aggiunta, modifica o rimozione di titoli sul sito salverà automaticamente sul tuo Google Sheets.")
            st.session_state['gsheets_auto_sync'] = auto_sync
            st.session_state['gsheets_url'] = gsheets_url

        # Guida all'installazione
        with st.container():
            st.divider()
            st.markdown("#### 🛠️ Guida alla configurazione in 1 minuto")
            st.markdown("""
            1. Crea un nuovo **Foglio Google Sheets**.
            2. Fai clic su **Estensioni** in alto -> **Apps Script**.
            3. Cancella tutto il codice presente e incolla questo script:
            """)
            st.code("""
function doGet() {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  var data = sheet.getDataRange().getValues();
  var portfolio = [];
  for (var i = 1; i < data.length; i++) {
    var row = data[i];
    if (row[0]) {
      portfolio.push({
        ticker: row[0].toString().trim().toUpperCase(),
        shares: parseFloat(row[1]) || 0,
        purchase_price: parseFloat(row[2]) || 0
      });
    }
  }
  return ContentService.createTextOutput(JSON.stringify(portfolio))
    .setMimeType(ContentService.MimeType.JSON);
}

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
  sheet.clearContents();
  sheet.appendRow(["Ticker", "Quantità", "Prezzo d'Acquisto"]);
  var portfolio = JSON.parse(e.postData.contents);
  for (var i = 0; i < portfolio.length; i++) {
    var item = portfolio[i];
    sheet.appendRow([item.ticker, item.shares, item.purchase_price]);
  }
  return ContentService.createTextOutput(JSON.stringify({status: "success"}))
    .setMimeType(ContentService.MimeType.JSON);
}
            """, language="javascript")
            st.markdown("""
            4. Fai clic sul pulsante **Distribuisci** in alto a destra -> **Nuova distribuzione**.
            5. Configura così:
               - **Seleziona tipo**: Web App (clicca sulla rotella delle impostazioni se non la vedi).
               - **Esegui come**: Tu (tua mail).
               - **Chi ha accesso**: Chiunque (questo è fondamentale affinché l'app Streamlit possa dialogare con il foglio).
            6. Clicca su **Distribuisci**, autorizza l'accesso con la tua mail di Google e copia l'**URL della Web App** fornito alla fine.
            7. Incolla quell'URL nel campo di testo qui sopra!
            """)

    # --- GESTIONE / RIMOZIONE POSIZIONI ---
    if st.session_state['portfolio']:
        with st.expander("⚙️ Gestisci / Rimuovi Posizione", expanded=False):
            position_options = [
                f"{i+1}. {item['ticker']} ({item['shares']} quote)"
                for i, item in enumerate(st.session_state['portfolio'])
            ]
            selected_pos = st.selectbox(
                "Seleziona una posizione da gestire", options=position_options)

            if selected_pos:
                selected_idx = position_options.index(selected_pos)
                current_item = st.session_state['portfolio'][selected_idx]

                m1, m2 = st.columns(2)

                with m1:
                    new_qty = st.number_input(
                        f"Modifica Quantità per {current_item['ticker']}",
                        min_value=0.0,
                        value=float(current_item['shares']),
                        step=0.1,
                        key=f"edit_qty_{selected_idx}"
                    )
                    old_price = float(current_item.get('purchase_price', 0.0))
                    new_purchase_price = st.number_input(
                        f"Prezzo di Acquisto ($) per {current_item['ticker']}",
                        min_value=0.0,
                        value=old_price,
                        step=1.0,
                        key=f"edit_price_{selected_idx}",
                        help="Imposta il prezzo medio a cui hai acquistato l'azione"
                    )
                    if st.button("Aggiorna Posizione", key=f"btn_update_{selected_idx}"):
                        st.session_state['portfolio'][selected_idx]['shares'] = new_qty
                        st.session_state['portfolio'][selected_idx]['purchase_price'] = new_purchase_price
                        save_portfolio(st.session_state['portfolio'])
                        st.toast(
                            f"Posizione {current_item['ticker']} aggiornata con successo!", icon="✅")
                        st.rerun()

                with m2:
                    st.write(" ")
                    st.write(" ")
                    if st.button("Rimuovi Posizione", type="primary", key=f"btn_remove_{selected_idx}"):
                        removed_item = st.session_state['portfolio'].pop(
                            selected_idx)
                        save_portfolio(st.session_state['portfolio'])
                        st.toast(
                            f"{removed_item['ticker']} rimosso con successo!", icon="🗑️")
                        st.rerun()

    # --- VISUALIZZAZIONE PORTAFOGLIO ---
    if st.session_state['portfolio']:
        st.subheader("Le tue posizioni")

        tickers = [item['ticker'] for item in st.session_state['portfolio']]

        with st.spinner("Aggiornamento prezzi e dividendi batch..."):
            # FETCH PREZZI IN BATCH PIÙ EFFICIENTE
            prices_dict = get_batch_prices(list(set(tickers)))

            # Fetch stock info per dividendi (utilizza la cache con fallback robusto)
            stock_infos = {}
            for tk in list(set(tickers)):
                try:
                    stock_infos[tk] = fetch_stock_info(tk)
                except Exception:
                    stock_infos[tk] = None

            portfolio_data = []
            total_portfolio_value = 0.0
            total_portfolio_cost = 0.0
            total_trailing_dividends = 0.0
            total_forward_dividends = 0.0

            for item in st.session_state['portfolio']:
                ticker = item['ticker']
                
                # Safe conversions to float for shares
                try:
                    shares = float(item.get('shares', 0.0))
                except Exception:
                    shares = 0.0
                if shares is None or pd.isna(shares):
                    shares = 0.0

                # Safe conversions to float for purchase_price
                try:
                    purchase_price = float(item.get('purchase_price', 0.0))
                except Exception:
                    purchase_price = 0.0
                if purchase_price is None or pd.isna(purchase_price):
                    purchase_price = 0.0

                # Otteniamo il prezzo dalla cache batch
                current_price = prices_dict.get(ticker, 0.0)
                # Float check per sicurezza
                if isinstance(current_price, pd.Series):
                    current_price = current_price.iloc[0]

                # Sanitize current_price (it could be NaN or None)
                if current_price is None or pd.isna(current_price):
                    current_price = 0.0
                else:
                    try:
                        current_price = float(current_price)
                    except Exception:
                        current_price = 0.0

                # Fallback per il prezzo d'acquisto se è 0.0 (es. posizioni esistenti non modificate)
                if purchase_price == 0.0:
                    purchase_price = current_price

                current_value = shares * current_price
                total_portfolio_value += current_value
                total_portfolio_cost += shares * purchase_price

                # Recupera dati dividendi
                info = stock_infos.get(ticker) or {}

                trailing_div_rate = info.get('trailingAnnualDividendRate')
                if trailing_div_rate is None or trailing_div_rate == 0 or pd.isna(trailing_div_rate):
                    trailing_div_rate = info.get('dividendRate')
                if trailing_div_rate is None or pd.isna(trailing_div_rate):
                    trailing_div_rate = 0.0
                else:
                    try:
                        trailing_div_rate = float(trailing_div_rate)
                    except Exception:
                        trailing_div_rate = 0.0

                forward_div_rate = info.get('dividendRate')
                if forward_div_rate is None or forward_div_rate == 0 or pd.isna(forward_div_rate):
                    forward_div_rate = info.get('trailingAnnualDividendRate')
                if forward_div_rate is None or pd.isna(forward_div_rate):
                    forward_div_rate = 0.0
                else:
                    try:
                        forward_div_rate = float(forward_div_rate)
                    except Exception:
                        forward_div_rate = 0.0

                # Calcola YOC individuale
                yoc = 0.0
                yoc_fwd = 0.0
                if purchase_price > 0.0:
                    yoc = (trailing_div_rate / purchase_price) * 100
                    yoc_fwd = (forward_div_rate / purchase_price) * 100

                # Accumula dividendi totali per YOC di portafoglio
                total_trailing_dividends += shares * trailing_div_rate
                total_forward_dividends += shares * forward_div_rate

                portfolio_data.append({
                    "Ticker": ticker,
                    "Quantità": shares,
                    "Prezzo d'Acquisto ($)": purchase_price,
                    "Prezzo Attuale ($)": current_price,
                    "Costo Totale ($)": shares * purchase_price,
                    "Valore Totale ($)": current_value,
                    "YOC (%)": yoc if (trailing_div_rate > 0.0) else 0.0,
                    "Dividendi TTM ($)": shares * trailing_div_rate,
                    "YOC FWD (%)": yoc_fwd if (forward_div_rate > 0.0) else 0.0,
                    "Dividendi FWD ($)": shares * forward_div_rate
                })

        df_portfolio = pd.DataFrame(portfolio_data)

        # Tabella formattata in stile Bloomberg
        st.dataframe(df_portfolio.style.format({
            "Prezzo d'Acquisto ($)": '${:,.2f}',
            "Prezzo Attuale ($)": '${:,.2f}',
            "Costo Totale ($)": '${:,.2f}',
            "Valore Totale ($)": '${:,.2f}',
            "YOC (%)": "{:.2f}%",
            "Dividendi TTM ($)": '${:,.2f}',
            "YOC FWD (%)": "{:.2f}%",
            "Dividendi FWD ($)": '${:,.2f}'
        }), use_container_width=True, hide_index=True)

        # Calcolo YOC globali del portafoglio
        portfolio_yoc = 0.0
        portfolio_yoc_fwd = 0.0
        if total_portfolio_cost > 0.0:
            portfolio_yoc = (total_trailing_dividends /
                             total_portfolio_cost) * 100
            portfolio_yoc_fwd = (total_forward_dividends /
                                 total_portfolio_cost) * 100

        # KPI Metrics - Row 1 (Market Values & Yields)
        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        kpi_c1.metric("Total Assets Under Management (AUM)",
                      format_large_numbers(total_portfolio_value))
        kpi_c2.metric("Portfolio Yield on Cost (YOC)",
                      f"{portfolio_yoc:.2f}%" if total_portfolio_cost > 0.0 else "0.00%")
        kpi_c3.metric("Portfolio YOC (FWD)",
                      f"{portfolio_yoc_fwd:.2f}%" if total_portfolio_cost > 0.0 else "0.00%")

        # KPI Metrics - Row 2 (Investment & Absolute Dividend Income)
        st.write("")
        kpi_d1, kpi_d2, kpi_d3 = st.columns(3)
        kpi_d1.metric("Total Portfolio Cost",
                      format_large_numbers(total_portfolio_cost))
        kpi_d2.metric("Annual Dividend Income (TTM)",
                      f"${total_trailing_dividends:,.2f}")
        kpi_d3.metric("Annual Dividend Income (FWD)",
                      f"${total_forward_dividends:,.2f}")

        st.divider()
        st.subheader("⚖️ Risk Concentration")

        fig_pie = px.pie(
            df_portfolio,
            values='Valore Totale ($)',
            names='Ticker',
            hole=0.4,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        fig_pie.update_traces(textinfo='percent+label',
                              pull=[0.05] * len(df_portfolio))
        fig_pie.update_layout(margin=dict(t=30, b=0, l=0, r=0))
        st.plotly_chart(fig_pie, use_container_width=True)

        # --- CORRELATION MATRIX ---
        st.divider()
        st.subheader("🔗 Correlation Matrix")
        st.write("Correlazioni tra i rendimenti giornalieri dei tuoi titoli (ultimi 12 mesi). Valori vicini a **1.0** indicano asset che si muovono insieme — poca diversificazione reale.")

        unique_portfolio_tickers = list(set(tickers))
        if len(unique_portfolio_tickers) >= 2:
            try:
                corr_data = yf.download(
                    unique_portfolio_tickers, period="1y", progress=False)['Close']
                if isinstance(corr_data, pd.Series):
                    st.info(
                        "Aggiungi almeno 2 titoli diversi per la matrice di correlazione.")
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
                                high_corr_pairs.append(
                                    (corr_matrix.columns[i], corr_matrix.columns[j], val))

                    if high_corr_pairs:
                        st.warning(
                            "⚠️ **Coppie ad alta correlazione (|ρ| ≥ 0.75):**")
                        for t1, t2, rho in sorted(high_corr_pairs, key=lambda x: abs(x[2]), reverse=True):
                            emoji = "🔴" if rho > 0 else "🔵"
                            st.markdown(
                                f"{emoji} **{t1}** ↔ **{t2}**: ρ = {rho:.3f}")
                    else:
                        st.success(
                            "✅ Buona diversificazione! Nessuna coppia con correlazione superiore a ±0.75.")
            except Exception as e:
                st.error(f"Errore nel calcolo delle correlazioni: {e}")
        else:
            st.info(
                "Aggiungi almeno 2 titoli al portafoglio per visualizzare la matrice di correlazione.")

        st.divider()
        st.subheader("🎯 Frontiera Efficiente di Markowitz")
        st.write(
            "Calcolo dei pesi ottimali per massimizzare lo Sharpe Ratio (Maximum Risk-Adjusted Return).")
        if len(df_portfolio) > 1:
            if st.button("🚀 Ottimizza Portafoglio", type="primary"):
                with st.spinner("Ottimizzazione covarianza in corso..."):
                    try:
                        data_batch = yf.download(
                            tickers, period="3y", progress=False)['Close']
                        if not data_batch.empty:
                            if isinstance(data_batch, pd.Series):  # edge case
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
                                    p_vol = np.sqrt(
                                        np.dot(w.T, np.dot(cov_mat, w)))
                                    return - (p_ret - rf_rate) / p_vol

                                constraints = (
                                    {'type': 'eq', 'fun': lambda x: np.sum(x) - 1})
                                bounds = tuple((0, 1)
                                               for _ in range(num_assets))
                                init_guess = num_assets * [1. / num_assets]
                                res = minimize(
                                    neg_sharpe, init_guess, bounds=bounds, constraints=constraints)
                                opt_weights = res.x

                                opt_df = pd.DataFrame(
                                    {'Ticker': active_tickers, 'Peso Ottimale (%)': (opt_weights*100).round(2)})
                                p_ret = np.sum(mean_ret * opt_weights)
                                p_vol = np.sqrt(
                                    np.dot(opt_weights.T, np.dot(cov_mat, opt_weights)))
                                shorp = (p_ret - rf_rate) / p_vol

                                c1, c2 = st.columns(2)
                                c1.dataframe(opt_df, hide_index=True)
                                c2.metric("Sharpe Ratio Atteso",
                                          f"{shorp:.2f}")
                                c2.metric("Rendimento Annuo Atteso",
                                          f"{p_ret*100:.2f}%")

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
                                    size=np.maximum(
                                        df_3d['Optimal Weight %'], 1),
                                    hover_name="Ticker",
                                    color_continuous_scale=px.colors.sequential.Viridis,
                                    opacity=0.8
                                )
                                fig_3d.update_layout(
                                    margin=dict(l=0, r=0, b=0, t=0), height=500,
                                    scene=dict(
                                        xaxis=dict(
                                            backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                        yaxis=dict(
                                            backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                        zaxis=dict(
                                            backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
                                    )
                                )
                                st.plotly_chart(
                                    fig_3d, use_container_width=True)
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
                ai_advice = analyze_portfolio_diversification(
                    df_portfolio, total_portfolio_value)
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
    st.write(
        "Stay up-to-date with the latest market news and **AI-powered sentiment analysis**.")
    st.divider()

    # --- AI PORTFOLIO TREEMAP ---
    if st.session_state.get('portfolio'):
        with st.expander("🌌 Genera S&P AI Sentiment Treemap (Sperimentale)", expanded=False):
            st.write(
                "Crea una mappa di calore del tuo portafoglio analizzando il sentiment generale di mercato tramite l'AI di Gemma.")
            if st.button("🚀 Esegui Analisi Treemap"):
                with st.spinner(f"Estrazione news e calcolo inferenziale Sentiment in corso... | '{random.choice(WALL_STREET_QUOTES)}'"):
                    tickers = [item['ticker']
                               for item in st.session_state['portfolio']]
                    prices_dict = get_batch_prices(
                        list(set(tickers))) if tickers else {}

                    tree_data = []
                    for item in st.session_state['portfolio']:
                        tk = item['ticker']
                        # Safe conversions to float for shares
                        try:
                            shares = float(item.get('shares', 0.0))
                        except Exception:
                            shares = 0.0
                        if shares is None or pd.isna(shares):
                            shares = 0.0

                        current_price = prices_dict.get(tk, 1.0)
                        if isinstance(current_price, pd.Series):
                            current_price = current_price.iloc[0]
                        if current_price is None or pd.isna(current_price):
                            current_price = 0.0
                        else:
                            try:
                                current_price = float(current_price)
                            except Exception:
                                current_price = 0.0
                        valore_monetario = shares * current_price

                        tk_news = fetch_news(tk)
                        sentiment_score = 0
                        valid_news = 0

                        if tk_news:
                            for n in tk_news[:8]:  # Ampliato a 8 notizie come richiesto
                                # Gestizione formati news misti
                                title = ""
                                if 'content' in n:
                                    title = n['content'].get('title', '')
                                else:
                                    title = n.get('title', '')

                                if title:
                                    lbl = get_sentiment(title)
                                    if "Positive" in lbl:
                                        sentiment_score += 1
                                    elif "Negative" in lbl:
                                        sentiment_score -= 1
                                    valid_news += 1

                        avg_score = (sentiment_score /
                                     valid_news) if valid_news > 0 else 0

                        if avg_score > 0.3:
                            human_lbl = "🟢 Rialzista"
                        elif avg_score < -0.3:
                            human_lbl = "🔴 Ribassista"
                        else:
                            human_lbl = "⚪ Incerto/Neutro"

                        tree_data.append({"Ticker": tk, "Valore ($)": max(
                            valore_monetario, 0.01), "AI Score": avg_score, "Giudizio": human_lbl})

                    df_tree = pd.DataFrame(tree_data)
                    if not df_tree.empty:
                        # Crea il Nodo Root genitore per Plotly
                        df_tree["Portafoglio"] = "Mio Portafoglio"
                        fig_tree = px.treemap(
                            df_tree,
                            path=['Portafoglio', 'Ticker'],
                            values='Valore ($)',
                            color='AI Score',
                            hover_name='Ticker',
                            hover_data={"AI Score": False,
                                        "Giudizio": True, "Valore ($)": ':$,.2f'},
                            color_continuous_scale=[
                                # Da -1.0 a -0.3 (Rosso)
                                [0.0, '#E74C3C'], [0.35, '#E74C3C'],
                                # Da -0.3 a 0.3 (Grigio Scuro/Neutro)
                                [0.35, '#2E2E2E'], [0.65, '#2E2E2E'],
                                # Da 0.3 a 1.0 (Verde)
                                [0.65, '#27AE60'], [1.0, '#27AE60']
                            ],
                            range_color=[-1, 1],
                            title="AI Portfolio Sentiment Heatmap (Proporzionata per Capitale Investito)"
                        )
                        st.plotly_chart(fig_tree, use_container_width=True)
    st.divider()

    col_news, _ = st.columns([1, 2])
    with col_news:
        ticker_news = st.text_input(
            "Enter Ticker (e.g., AAPL, MSFT)", value="AAPL").upper()

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
                        publisher = provider_dict.get(
                            'displayName', 'Unknown Source')

                        url_dict = news_data.get(
                            'clickThroughUrl') or news_data.get('canonicalUrl') or {}
                        link = url_dict.get(
                            'url', f"https://finance.yahoo.com/quote/{ticker_news}/news")

                        pub_date_str = news_data.get('pubDate', '')
                        if pub_date_str:
                            try:
                                pub_date = pd.to_datetime(
                                    pub_date_str).strftime('%d %b %Y - %H:%M')
                            except Exception:
                                pub_date = pub_date_str[:10]
                        else:
                            pub_date = "Date not available"
                    else:
                        title = item.get('title', 'No Title')
                        publisher = item.get('publisher', 'Unknown Source')
                        link = item.get(
                            'link', f"https://finance.yahoo.com/quote/{ticker_news}/news")

                        timestamp = item.get('providerPublishTime', 0)
                        if timestamp > 0:
                            pub_date = datetime.fromtimestamp(
                                timestamp).strftime('%d %b %Y - %H:%M')
                        else:
                            pub_date = "Date not available"

                    if title != 'No Title':
                        # AI Sentiment logic
                        sentiment_label = get_sentiment(title)
                        st.session_state['news_contexts'].append(
                            f"Titolo: {title} | Data: {pub_date}")

                        with st.container():
                            st.markdown(f"#### {title}")
                            st.caption(
                                f"✍️ **Source:** {publisher} | 🕒 **Published:** {pub_date} | 🧠 **AI Sentiment:** {sentiment_label}")
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
        st.session_state['chat_history'].append(
            {"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Risposta IA
        with st.chat_message("assistant"):
            if st.session_state.get('news_contexts'):
                with st.spinner(f"Riflessione quantitativa profonda... | '{random.choice(WALL_STREET_QUOTES)}'"):
                    ctx_str = "\n".join(st.session_state['news_contexts'][:15])
                    ans = ask_financial_chatbot(prompt, ctx_str)
                    st.markdown(ans)
                    st.session_state['chat_history'].append(
                        {"role": "assistant", "content": ans})
            else:
                warning_msg = "Attenzione: Cerca prima le notizie del titolo usando la barra di ricerca in alto, altrimenti Gemma non avrà alcun contesto su cui basarsi."
                st.warning(warning_msg)
                st.session_state['chat_history'].append(
                    {"role": "assistant", "content": warning_msg})

# ==========================================
# ==========================================
# PAGE 5: MACRO & MARKET
# ==========================================
elif page_choice == "🌍 Macro & Market":
    st.title("🌍 Macro & Market Pulse")
    st.markdown("<p style='color: #8A929A; font-style: italic; font-size: 18px;'>« Governments don't rule the world, Goldman Sachs rules the world. »</p>", unsafe_allow_html=True)
    st.divider()

    with st.spinner(f"Acquisizione dati macroeconomici... | '{random.choice(WALL_STREET_QUOTES)}'"):
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

        macro_data = {}
        for name, tk in macro_tickers.items():
            hist = yf.Ticker(tk).history(period="6mo")
            if not hist.empty:
                macro_data[name] = hist['Close']

        items = list(macro_data.items())
        cols_per_row = 3

        for i in range(0, len(items), cols_per_row):
            chunk = items[i:i+cols_per_row]
            cols = st.columns(cols_per_row)
            for j, (name, series) in enumerate(chunk):
                with cols[j]:
                    val = series.iloc[-1]
                    prev = series.iloc[-2] if len(series) > 1 else val
                    pct = ((val - prev)/prev)*100 if prev != 0 else 0.0

                    # Rilevamento icona in base al nome dell'asset macro
                    m_icon = "🌍"
                    if "Oro" in name:
                        m_icon = "🪙"
                    elif "Argento" in name:
                        m_icon = "💿"
                    elif "Petrolio" in name:
                        m_icon = "⛽"
                    elif "EUR/USD" in name:
                        m_icon = "💱"

                    # Formattazione decimale ad alta precisione per EUR/USD
                    if "EUR/USD" in name:
                        render_custom_metric(
                            name, f"{val:.4f}", f"{pct:+.2f}%", icon=m_icon, is_positive=(pct >= 0))
                    else:
                        formatted_val = f"${val:,.2f}" if (
                            "Oro" in name or "Argento" in name or "Petrolio" in name) else f"{val:,.2f}"
                        render_custom_metric(
                            name, formatted_val, f"{pct:+.2f}%", icon=m_icon, is_positive=(pct >= 0))

                    # Sparkline premium, trasparente e con colore adattivo al trend
                    color = "#2ECC71" if pct >= 0 else "#E74C3C"
                    fig = px.line(series, x=series.index, y=series.values)
                    fig.update_traces(line_color=color, line_width=2.5)
                    fig.update_layout(
                        xaxis_visible=False,
                        yaxis_visible=False,
                        height=150,
                        margin=dict(l=0, r=0, t=45, b=0),
                        showlegend=False,
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)"
                    )
                    st.plotly_chart(fig, use_container_width=True, config={
                                    'displayModeBar': False})

            st.write("")  # Spazio extra verticale
            st.write("")

# ==========================================
# PAGE 6: STOCK SCREENER
# ==========================================
elif page_choice == "🔍 Stock Screener":
    st.title("🔍 S&P 500 Stock Screener")
    st.write(
        "Esplora l'intero **S&P 500** alla ricerca di opportunità Value e Dividend.")
    st.divider()

    @st.cache_data(ttl=3600*24)
    def get_sp500_tickers():
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        html = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}).text
        return pd.read_html(io.StringIO(html))[0]['Symbol'].tolist()

    try:
        sp500_tickers = get_sp500_tickers()
    except Exception:
        st.error("Impossibile caricare S&P 500.")
        sp500_tickers = []

    st.markdown("#### ⚙️ Parametri di Screening Quantitativo")

    col_row1 = st.columns(4)
    max_pe = col_row1[0].number_input(
        "P/E Ratio Massimo", value=25.0, help="Filtra aziende con P/E inferiore o uguale a questa soglia (Utile/Value).")
    min_div = col_row1[1].number_input(
        "Dividend Yield Minimo (%)", value=2.0, help="Soglia minima di rendimento da dividendo annuale.")
    min_cap = col_row1[2].number_input(
        "Market Cap Min. (Bld $)", value=50, help="Capitalizzazione di mercato minima in miliardi di dollari.")
    max_payout = col_row1[3].number_input(
        "Payout Ratio Massimo (%)", value=70.0, help="Soglia massima di utili destinati ai dividendi (sostenibilità).")

    col_row2 = st.columns(4)
    min_eps_growth = col_row2[0].number_input("EPS Growth 5A CAGR Min. (%)", value=5.0,
                                              help="Aumento annualizzato previsto degli utili per azione (EPS) nei prossimi 5 anni.")
    min_div_growth = col_row2[1].number_input(
        "Div Growth 5A CAGR Min. (%)", value=4.0, help="Crescita annualizzata minima stimata dei dividendi.")
    min_net_income = col_row2[2].number_input(
        "Net Income Min. (Mln $)", value=500.0, help="Utile netto minimo cumulato in milioni di dollari.")
    min_profit_margin = col_row2[3].number_input(
        "Net Profit Margin Min. (%)", value=10.0, help="Margine di profitto netto minimo (%) dell'azienda.")

    if st.button("🚀 Esegui Screen", type="primary"):
        if sp500_tickers:
            with st.spinner(f"Scansione parallela di {len(sp500_tickers)} titoli S&P 500 (15-20 sec)... | '{random.choice(WALL_STREET_QUOTES)}'"):

                def evaluate_ticker(tkr):
                    try:
                        tk_info = fetch_stock_info(tkr)
                        if not tk_info:
                            return None
                        # Helper to safely extract numeric values (handles None, NaN, non-numeric)

                        def _safe_num(val):
                            if val is None:
                                return None
                            try:
                                import pandas as pd
                                if pd.isna(val):
                                    return None
                            except Exception:
                                pass
                            return val if isinstance(val, (int, float)) else None

                        # 1. P/E
                        pe = _safe_num(tk_info.get('trailingPE'))

                        # 2. Dividend Yield
                        div_rate = _safe_num(tk_info.get('dividendRate'))
                        price = _safe_num(tk_info.get('currentPrice'))

                        if div_rate is not None and div_rate > 0 and price is not None and price > 0:
                            div_yield = (div_rate / price) * 100
                        else:
                            div_yield = _safe_num(tk_info.get('dividendYield'))
                            if div_yield is not None:
                                # se è in formato decimale (es. 0.025 per 2.5%)
                                if div_yield < 0.2:
                                    div_yield = div_yield * 100
                            else:
                                div_yield = 0.0

                        # 3. Market Cap (Billion $)
                        mcap = _safe_num(tk_info.get('marketCap'))
                        mcap_b = (mcap or 0) / 1e9

                        # 4. EPS Growth next 5Y CAGR
                        eps_cagr = _safe_num(tk_info.get('epsGrowth5Y'))
                        if eps_cagr is not None:
                            eps_growth_val = eps_cagr
                        else:
                            eps_growth = _safe_num(
                                tk_info.get('earningsGrowth'))
                            if eps_growth is not None:
                                eps_growth_val = eps_growth * \
                                    100 if abs(
                                        eps_growth) <= 1.0 else eps_growth
                            else:
                                eps_growth_q = _safe_num(
                                    tk_info.get('earningsQuarterlyGrowth'))
                                if eps_growth_q is not None:
                                    eps_growth_val = eps_growth_q * \
                                        100 if abs(
                                            eps_growth_q) <= 1.0 else eps_growth_q
                                else:
                                    eps_growth_val = 0.0

                        # 5. Payout Ratio (%)
                        payout = _safe_num(tk_info.get('payoutRatio'))
                        payout_val = (
                            payout * 100) if payout is not None else 0.0

                        # 6. Dividend Growth next 5Y CAGR
                        if div_yield == 0:
                            div_growth_val = 0.0
                        else:
                            # Legge fiveYearAvgDividendYield o fa fallback su eps_growth_val
                            five_yr_avg = _safe_num(
                                tk_info.get('fiveYearAvgDividendYield'))
                            if five_yr_avg is not None:
                                div_growth_val = five_yr_avg if five_yr_avg > 1.0 else five_yr_avg * 100
                            else:
                                div_growth_val = eps_growth_val * 0.8

                        # 7. Net Income (Million $)
                        net_income = _safe_num(
                            tk_info.get('netIncomeToCommon'))
                        if net_income is None:
                            net_income = _safe_num(tk_info.get('netIncome'))
                        net_income_m = (
                            net_income / 1e6) if net_income is not None else 0.0

                        # 8. Net Profit Margin (%)
                        profit_margin = _safe_num(tk_info.get('profitMargins'))
                        profit_margin_val = (
                            profit_margin * 100) if profit_margin is not None else 0.0

                        # Valutazione filtri
                        pe_match = (pe is not None and pe <= max_pe)
                        div_match = (div_yield >= min_div)
                        mcap_match = (mcap_b >= min_cap)
                        eps_growth_match = (eps_growth_val >= min_eps_growth)
                        payout_match = (payout_val <= max_payout)
                        div_growth_match = (div_growth_val >= min_div_growth)
                        net_income_match = (net_income_m >= min_net_income)
                        profit_margin_match = (
                            profit_margin_val >= min_profit_margin)

                        if pe_match and div_match and mcap_match and eps_growth_match and payout_match and div_growth_match and net_income_match and profit_margin_match:
                            return {
                                "Ticker": tkr,
                                "Azienda": tk_info.get('shortName', ''),
                                "P/E": round(pe, 2),
                                "Div Yield %": round(div_yield, 2),
                                "Market Cap (B)": round(mcap_b, 2),
                                "Payout Ratio %": round(payout_val, 2),
                                "EPS Growth %": round(eps_growth_val, 2),
                                "Net Income (M)": round(net_income_m, 2),
                                "Profit Margin %": round(profit_margin_val, 2),
                                "Prezzo": tk_info.get('currentPrice', 'N/A')
                            }
                    except Exception:
                        pass
                    return None

                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    results = list(executor.map(
                        evaluate_ticker, sp500_tickers))

                screener_res = [r for r in results if r is not None]

                if screener_res:
                    df_screen = pd.DataFrame(screener_res).sort_values(
                        by="Div Yield %", ascending=False)
                    st.success(
                        f"Trovate {len(screener_res)} aziende che rispettano i tuoi parametri istituzionali.")
                    render_premium_screener_table(df_screen)

                    info_note_html = """
                    <div style="background: rgba(0, 242, 254, 0.05); border: 1px dashed rgba(0, 242, 254, 0.2); padding: 12px 18px; border-radius: 8px; margin-top: 15px; margin-bottom: 25px; display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 18px;">💡</span>
                        <span style="color: #cbd5e1; font-size: 13.5px; font-weight: 500;">
                            <b>Analisi Diretta:</b> Clicca sul <span style="background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%); color: white; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 11px;">TICKER</span> di qualsiasi azienda per analizzarla istantaneamente nella sezione <b>Stock Tracker</b>!
                        </span>
                    </div>
                    """
                    clean_info_note = "\n".join(
                        [line.strip() for line in info_note_html.split("\n")])
                    st.markdown(clean_info_note, unsafe_allow_html=True)

                    if len(df_screen) >= 4:
                        st.subheader("🧲 K-Means AI Clustering (S&P 500)")
                        st.write(
                            "Aggreghiamo matematicamente queste aziende in cluster spaziali in base al loro DNA finanziario (P/E, Dividendo, Grandezza).")
                        with st.spinner("Addestramento modello ML K-Means in puro NumPy..."):
                            # Preparazione e normalizzazione dati
                            data = df_screen[[
                                'P/E', 'Div Yield %', 'Market Cap (B)']].values
                            # Prevenzione division by zero sui dev.std
                            std_devs = np.std(data, axis=0)
                            std_devs[std_devs == 0] = 1
                            data_norm = (
                                data - np.mean(data, axis=0)) / std_devs

                            k = min(4, len(df_screen))
                            np.random.seed(42)
                            centroids = data_norm[np.random.choice(
                                data_norm.shape[0], k, replace=False)]

                            for _ in range(100):  # Hard cap a 100 iterazioni
                                distances = np.sqrt(
                                    ((data_norm - centroids[:, np.newaxis])**2).sum(axis=2))
                                labels = np.argmin(distances, axis=0)
                                new_centroids = np.array([data_norm[labels == i].mean(axis=0) if len(
                                    data_norm[labels == i]) > 0 else centroids[i] for i in range(k)])
                                if np.allclose(centroids, new_centroids):
                                    break
                                centroids = new_centroids

                            df_screen['Cluster ID'] = [
                                f"Ammasso {L+1}" for L in labels]

                            fig_clust = px.scatter_3d(
                                df_screen, x='P/E', y='Div Yield %', z='Market Cap (B)',
                                color='Cluster ID', hover_name='Ticker', hover_data=['Azienda'],
                                title="Costellazione S&P 500 Segmentata",
                                color_discrete_sequence=px.colors.qualitative.Bold
                            )
                            fig_clust.update_layout(
                                margin=dict(l=0, r=0, b=0, t=30), height=600,
                                scene=dict(
                                    xaxis=dict(
                                        backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    yaxis=dict(
                                        backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    zaxis=dict(
                                        backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
                                )
                            )
                            st.plotly_chart(
                                fig_clust, use_container_width=True)
                else:
                    st.warning("Nessuna azienda rispetta queste query severe!")

# ==========================================
# PAGE 7: SUPER INVESTORS
# ==========================================
elif page_choice == "👑 Super Investors":
    portfolio_details = {
        "Warren Buffett": [
            {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology",
                "Allocazione %": 21.99, "Quote": "227.9M", "Valore": "$57.8B"},
            {"Ticker": "AXP", "Azienda": "American Express", "Settore": "Financial",
                "Allocazione %": 17.43, "Quote": "151.6M", "Valore": "$45.9B"},
            {"Ticker": "KO", "Azienda": "Coca-Cola", "Settore": "Consumer",
                "Allocazione %": 11.56, "Quote": "400.0M", "Valore": "$30.4B"},
            {"Ticker": "BAC", "Azienda": "Bank of America", "Settore": "Financial",
                "Allocazione %": 9.52, "Quote": "513.6M", "Valore": "$25.0B"},
            {"Ticker": "CVX", "Azienda": "Chevron", "Settore": "Energy",
                "Allocazione %": 6.64, "Quote": "84.4M", "Valore": "$17.5B"},
            {"Ticker": "OXY", "Azienda": "Occidental Petroleum", "Settore": "Energy",
                "Allocazione %": 6.50, "Quote": "248.5M", "Valore": "$17.1B"},
            {"Ticker": "GOOGL", "Azienda": "Alphabet Inc. (Class A)", "Settore": "Technology",
             "Allocazione %": 5.93, "Quote": "54.2M", "Valore": "$15.6B"},
            {"Ticker": "CB", "Azienda": "Chubb Limited", "Settore": "Financial",
                "Allocazione %": 4.20, "Quote": "26.0M", "Valore": "$11.0B"},
            {"Ticker": "MCO", "Azienda": "Moody's Corp.", "Settore": "Financial",
                "Allocazione %": 4.10, "Quote": "24.6M", "Valore": "$10.8B"},
            {"Ticker": "KHC", "Azienda": "Kraft Heinz Co.", "Settore": "Consumer",
                "Allocazione %": 2.80, "Quote": "325.6M", "Valore": "$7.4B"},
            {"Ticker": "DVA", "Azienda": "DaVita Inc.", "Settore": "Health",
                "Allocazione %": 1.30, "Quote": "36.1M", "Valore": "$3.4B"},
            {"Ticker": "KR", "Azienda": "Kroger Co.", "Settore": "Consumer",
                "Allocazione %": 1.20, "Quote": "50.0M", "Valore": "$3.1B"},
            {"Ticker": "DAL", "Azienda": "Delta Air Lines", "Settore": "Industrial",
                "Allocazione %": 0.70, "Quote": "39.8M", "Valore": "$1.8B"},
            {"Ticker": "SIRI", "Azienda": "Sirius XM Holdings", "Settore": "Technology",
                "Allocazione %": 0.60, "Quote": "125.6M", "Valore": "$1.5B"},
            {"Ticker": "VRSN", "Azienda": "VeriSign Inc.", "Settore": "Technology",
                "Allocazione %": 0.50, "Quote": "12.8M", "Valore": "$1.3B"},
            {"Ticker": "COF", "Azienda": "Capital One Financial", "Settore": "Financial",
                "Allocazione %": 0.50, "Quote": "7.15M", "Valore": "$1.3B"},
            {"Ticker": "LEN", "Azienda": "Lennar Corp. (Class A)", "Settore": "Consumer",
             "Allocazione %": 0.40, "Quote": "6.8M", "Valore": "$1.0B"},
            {"Ticker": "GOOG", "Azienda": "Alphabet Inc. (Class C)", "Settore": "Technology",
             "Allocazione %": 0.40, "Quote": "3.6M", "Valore": "$1.0B"},
            {"Ticker": "ALLY", "Azienda": "Ally Financial", "Settore": "Financial",
                "Allocazione %": 0.30, "Quote": "29.0M", "Valore": "$790M"},
            {"Ticker": "NYT", "Azienda": "New York Times Co.", "Settore": "Consumer",
                "Allocazione %": 0.30, "Quote": "15.0M", "Valore": "$790M"},
            {"Ticker": "NUE", "Azienda": "Nucor Corp.", "Settore": "Industrial",
                "Allocazione %": 0.25, "Quote": "4.5M", "Valore": "$660M"},
            {"Ticker": "LPX", "Azienda": "Louisiana-Pacific", "Settore": "Industrial",
                "Allocazione %": 0.20, "Quote": "7.0M", "Valore": "$530M"},
            {"Ticker": "JEF", "Azienda": "Jefferies Financial", "Settore": "Financial",
                "Allocazione %": 0.15, "Quote": "3.5M", "Valore": "$390M"},
            {"Ticker": "STZ", "Azienda": "Constellation Brands", "Settore": "Consumer",
                "Allocazione %": 0.10, "Quote": "1.2M", "Valore": "$260M"},
            {"Ticker": "NVR", "Azienda": "NVR Inc.", "Settore": "Consumer",
                "Allocazione %": 0.10, "Quote": "110K", "Valore": "$260M"},
            {"Ticker": "LLYVA", "Azienda": "Liberty Live (Class A)", "Settore": "Technology",
             "Allocazione %": 0.10, "Quote": "5.0M", "Valore": "$260M"},
            {"Ticker": "LEN.B", "Azienda": "Lennar Corp. (Class B)", "Settore": "Consumer",
             "Allocazione %": 0.05, "Quote": "1.0M", "Valore": "$130M"},
            {"Ticker": "M", "Azienda": "Macy's Inc.", "Settore": "Consumer",
                "Allocazione %": 0.02, "Quote": "3.0M", "Valore": "$52M"},
        ],
        "Michael Burry": [
            {"Ticker": "MOH", "Azienda": "Molina Healthcare Inc.", "Settore": "Health",
                "Allocazione %": 23.50, "Quote": "125K", "Valore": "$23.9M"},
            {"Ticker": "LULU", "Azienda": "Lululemon Athletica", "Settore": "Consumer",
                "Allocazione %": 21.20, "Quote": "100K", "Valore": "$17.7M"},
            {"Ticker": "SLM", "Azienda": "SLM Corp.", "Settore": "Financial",
                "Allocazione %": 19.30, "Quote": "480K", "Valore": "$13.2M"},
            {"Ticker": "PYPL", "Azienda": "PayPal Holdings", "Settore": "Technology",
                "Allocazione %": 15.50, "Quote": "250K", "Valore": "$16.5M"},
            {"Ticker": "ADBE", "Azienda": "Adobe Inc.", "Settore": "Technology",
                "Allocazione %": 11.00, "Quote": "25K", "Valore": "$12.1M"},
            {"Ticker": "MELI", "Azienda": "MercadoLibre", "Settore": "E-Commerce",
                "Allocazione %": 9.50, "Quote": "6K", "Valore": "$10.5M"},
        ],
        "Cathie Wood": [
            {"Ticker": "TSLA", "Azienda": "Tesla", "Settore": "Auto",
                "Allocazione %": 18.50, "Quote": "3.8M", "Valore": "$680M"},
            {"Ticker": "AMD", "Azienda": "Advanced Micro Devices", "Settore": "Technology",
                "Allocazione %": 9.15, "Quote": "4.2M", "Valore": "$340M"},
            {"Ticker": "CRCL", "Azienda": "Circle Internet Group", "Settore": "Crypto",
                "Allocazione %": 8.85, "Quote": "9.1M", "Valore": "$320M"},
            {"Ticker": "CRSP", "Azienda": "CRISPR Therapeutics", "Settore": "Health",
                "Allocazione %": 8.15, "Quote": "6.3M", "Valore": "$300M"},
            {"Ticker": "TEM", "Azienda": "Tempus AI, Inc.", "Settore": "Health",
                "Allocazione %": 7.85, "Quote": "6.5M", "Valore": "$290M"},
            {"Ticker": "ROKU", "Azienda": "Roku", "Settore": "Communication",
                "Allocazione %": 7.65, "Quote": "8.5M", "Valore": "$280M"},
            {"Ticker": "HOOD", "Azienda": "Robinhood Markets", "Settore": "Financial",
                "Allocazione %": 7.35, "Quote": "15.0M", "Valore": "$270M"},
            {"Ticker": "COIN", "Azienda": "Coinbase Global", "Settore": "Crypto",
                "Allocazione %": 7.35, "Quote": "1.2M", "Valore": "$270M"},
            {"Ticker": "SHOP", "Azienda": "Shopify Inc.", "Settore": "E-Commerce",
                "Allocazione %": 6.85, "Quote": "4.0M", "Valore": "$250M"},
            {"Ticker": "PLTR", "Azienda": "Palantir Technologies", "Settore": "Software",
                "Allocazione %": 5.15, "Quote": "6.3M", "Valore": "$190M"},
            {"Ticker": "RBLX", "Azienda": "Roblox Corp.", "Settore": "Software",
                "Allocazione %": 5.00, "Quote": "5.2M", "Valore": "$184M"},
            {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce",
                "Allocazione %": 4.15, "Quote": "800K", "Valore": "$153M"},
            {"Ticker": "GOOGL", "Azienda": "Alphabet Inc.", "Settore": "Technology",
                "Allocazione %": 4.00, "Quote": "900K", "Valore": "$147M"},
        ],
        "Bill Ackman": [
            {"Ticker": "BN", "Azienda": "Brookfield Corp.", "Settore": "Financial",
                "Allocazione %": 19.34, "Quote": "59.7M", "Valore": "$2.41B"},
            {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce",
                "Allocazione %": 19.12, "Quote": "11.5M", "Valore": "$2.38B"},
            {"Ticker": "UBER", "Azienda": "Uber Technologies", "Settore": "Tech",
                "Allocazione %": 17.25, "Quote": "30.0M", "Valore": "$2.15B"},
            {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software",
                "Allocazione %": 16.81, "Quote": "5.7M", "Valore": "$2.10B"},
            {"Ticker": "QSR", "Azienda": "Restaurant Brands", "Settore": "Consumer",
                "Allocazione %": 13.41, "Quote": "22.6M", "Valore": "$1.67B"},
            {"Ticker": "HHH", "Azienda": "Howard Hughes Holdings", "Settore": "Real Estate",
                "Allocazione %": 12.97, "Quote": "23.5M", "Valore": "$1.62B"},
            {"Ticker": "GOOGL", "Azienda": "Alphabet Inc. (Class A)", "Settore": "Technology",
             "Allocazione %": 0.77, "Quote": "580K", "Valore": "$96M"},
            {"Ticker": "GOOG", "Azienda": "Alphabet Inc. (Class C)", "Settore": "Technology",
             "Allocazione %": 0.33, "Quote": "250K", "Valore": "$41M"},
        ],
        "David Tepper": [
            {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce",
                "Allocazione %": 17.43, "Quote": "4.8M", "Valore": "$899M"},
            {"Ticker": "MU", "Azienda": "Micron Technology", "Settore": "Technology",
                "Allocazione %": 10.56, "Quote": "4.5M", "Valore": "$562M"},
            {"Ticker": "GOOG", "Azienda": "Alphabet Inc.", "Settore": "Communication",
                "Allocazione %": 9.53, "Quote": "2.8M", "Valore": "$497M"},
            {"Ticker": "UBER", "Azienda": "Uber Technologies", "Settore": "Tech",
                "Allocazione %": 8.92, "Quote": "6.2M", "Valore": "$455M"},
            {"Ticker": "TSM", "Azienda": "Taiwan Semi", "Settore": "Technology",
                "Allocazione %": 8.48, "Quote": "2.9M", "Valore": "$448M"},
            {"Ticker": "BABA", "Azienda": "Alibaba Group", "Settore": "E-Commerce",
                "Allocazione %": 8.33, "Quote": "5.1M", "Valore": "$440M"},
            {"Ticker": "VST", "Azienda": "Vistra Corp.", "Settore": "Energy",
                "Allocazione %": 5.95, "Quote": "4.5M", "Valore": "$314M"},
            {"Ticker": "EWY", "Azienda": "iShares South Korea ETF", "Settore": "ETF",
                "Allocazione %": 5.78, "Quote": "4.8M", "Valore": "$305M"},
            {"Ticker": "NRG", "Azienda": "NRG Energy Inc.", "Settore": "Utilities",
                "Allocazione %": 4.96, "Quote": "3.2M", "Valore": "$262M"},
            {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology",
                "Allocazione %": 4.93, "Quote": "3.4M", "Valore": "$260M"},
            {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication",
                "Allocazione %": 4.79, "Quote": "380K", "Valore": "$253M"},
            {"Ticker": "SNDK", "Azienda": "SanDisk Corp.", "Settore": "Technology",
                "Allocazione %": 3.50, "Quote": "2.2M", "Valore": "$185M"},
            {"Ticker": "GLW", "Azienda": "Corning Inc.", "Settore": "Technology",
                "Allocazione %": 3.01, "Quote": "4.5M", "Valore": "$159M"},
            {"Ticker": "WHR", "Azienda": "Whirlpool Corp.", "Settore": "Consumer",
                "Allocazione %": 2.06, "Quote": "1.1M", "Valore": "$109M"},
            {"Ticker": "PDD", "Azienda": "PDD Holdings Inc.", "Settore": "E-Commerce",
                "Allocazione %": 1.77, "Quote": "800K", "Valore": "$93M"},
        ],
        "Ray Dalio": [
            {"Ticker": "SPY", "Azienda": "SPDR S&P 500 ETF", "Settore": "ETF",
                "Allocazione %": 27.20, "Quote": "5.4M", "Valore": "$2.84B"},
            {"Ticker": "IVV", "Azienda": "iShares Core S&P 500", "Settore": "ETF",
                "Allocazione %": 16.80, "Quote": "3.2M", "Valore": "$1.75B"},
            {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce",
                "Allocazione %": 8.80, "Quote": "4.7M", "Valore": "$918M"},
            {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology",
                "Allocazione %": 7.75, "Quote": "8.5M", "Valore": "$806M"},
            {"Ticker": "GOOGL", "Azienda": "Alphabet Inc.", "Settore": "Communication",
                "Allocazione %": 5.60, "Quote": "3.4M", "Valore": "$582M"},
            {"Ticker": "AVGO", "Azienda": "Broadcom Inc.", "Settore": "Technology",
                "Allocazione %": 5.40, "Quote": "420K", "Valore": "$560M"},
            {"Ticker": "MU", "Azienda": "Micron Technology", "Settore": "Technology",
                "Allocazione %": 4.75, "Quote": "3.8M", "Valore": "$493M"},
            {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software",
                "Allocazione %": 3.90, "Quote": "1.1M", "Valore": "$403M"},
            {"Ticker": "GEV", "Azienda": "GE Vernova Inc.", "Settore": "Energy",
                "Allocazione %": 3.65, "Quote": "1.5M", "Valore": "$381M"},
            {"Ticker": "TSM", "Azienda": "Taiwan Semi", "Settore": "Technology",
                "Allocazione %": 3.45, "Quote": "2.2M", "Valore": "$358M"},
            {"Ticker": "MRVL", "Azienda": "Marvell Technology", "Settore": "Technology",
                "Allocazione %": 3.25, "Quote": "4.5M", "Valore": "$336M"},
            {"Ticker": "PG", "Azienda": "Procter & Gamble", "Settore": "Consumer",
                "Allocazione %": 3.00, "Quote": "2.0M", "Valore": "$314M"},
            {"Ticker": "JNJ", "Azienda": "Johnson & Johnson", "Settore": "Health",
                "Allocazione %": 2.60, "Quote": "1.7M", "Valore": "$269M"},
            {"Ticker": "PEP", "Azienda": "PepsiCo", "Settore": "Consumer",
                "Allocazione %": 2.35, "Quote": "1.5M", "Valore": "$246M"},
            {"Ticker": "COST", "Azienda": "Costco Wholesale", "Settore": "Consumer",
                "Allocazione %": 1.50, "Quote": "200K", "Valore": "$157M"},
        ],
        "Stanley Druckenmiller": [
            {"Ticker": "NTRA", "Azienda": "Natera, Inc.", "Settore": "Health",
                "Allocazione %": 27.20, "Quote": "8.1M", "Valore": "$828M"},
            {"Ticker": "INSM", "Azienda": "Insmed Incorporated", "Settore": "Health",
                "Allocazione %": 8.40, "Quote": "9.5M", "Valore": "$256M"},
            {"Ticker": "TSM", "Azienda": "Taiwan Semi", "Settore": "Technology",
                "Allocazione %": 7.50, "Quote": "2.2M", "Valore": "$229M"},
            {"Ticker": "EWZ", "Azienda": "iShares MSCI Brazil", "Settore": "ETF",
                "Allocazione %": 13.05, "Quote": "12.0M", "Valore": "$398M"},
            {"Ticker": "RSP", "Azienda": "Invesco S&P 500 Equal", "Settore": "ETF",
                "Allocazione %": 7.05, "Quote": "2.2M", "Valore": "$215M"},
            {"Ticker": "YPF", "Azienda": "YPF Sociedad Anonima", "Settore": "Energy",
                "Allocazione %": 6.60, "Quote": "8.2M", "Valore": "$201M"},
            {"Ticker": "TBBB", "Azienda": "BBB Foods Inc.", "Settore": "Consumer",
                "Allocazione %": 4.95, "Quote": "6.0M", "Valore": "$151M"},
            {"Ticker": "AA", "Azienda": "Alcoa Corporation", "Settore": "Materials",
                "Allocazione %": 4.35, "Quote": "3.5M", "Valore": "$133M"},
            {"Ticker": "NAMS", "Azienda": "NewAmsterdam Pharma", "Settore": "Health",
                "Allocazione %": 4.35, "Quote": "7.5M", "Valore": "$133M"},
            {"Ticker": "SE", "Azienda": "Sea Limited", "Settore": "E-Commerce",
                "Allocazione %": 4.05, "Quote": "1.8M", "Valore": "$123M"},
            {"Ticker": "STM", "Azienda": "STMicroelectronics", "Settore": "Technology",
                "Allocazione %": 3.75, "Quote": "4.5M", "Valore": "$114M"},
            {"Ticker": "WWD", "Azienda": "Woodward Inc.", "Settore": "Industrial",
                "Allocazione %": 3.00, "Quote": "500K", "Valore": "$91M"},
            {"Ticker": "TEVA", "Azienda": "Teva Pharmaceutical", "Settore": "Health",
                "Allocazione %": 2.70, "Quote": "11.1M", "Valore": "$82M"},
            {"Ticker": "AVGO", "Azienda": "Broadcom Inc.", "Settore": "Technology",
                "Allocazione %": 3.05, "Quote": "160K", "Valore": "$93M"},
        ],
        "Ken Griffin": [
            {"Ticker": "SPY", "Azienda": "SPDR S&P 500 ETF", "Settore": "ETF",
                "Allocazione %": 22.00, "Quote": "35.1M", "Valore": "$12.0B"},
            {"Ticker": "QQQ", "Azienda": "Invesco QQQ Trust", "Settore": "ETF",
                "Allocazione %": 18.00, "Quote": "25.2M", "Valore": "$9.8B"},
            {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology",
                "Allocazione %": 13.80, "Quote": "9.8M", "Valore": "$7.5B"},
            {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology",
                "Allocazione %": 9.00, "Quote": "22.3M", "Valore": "$4.9B"},
            {"Ticker": "TSLA", "Azienda": "Tesla", "Settore": "Auto",
                "Allocazione %": 7.30, "Quote": "15.1M", "Valore": "$4.0B"},
            {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software",
                "Allocazione %": 6.20, "Quote": "8.2M", "Valore": "$3.38B"},
            {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication",
                "Allocazione %": 8.80, "Quote": "8.5M", "Valore": "$4.8B"},
            {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce",
                "Allocazione %": 8.00, "Quote": "21.5M", "Valore": "$4.3B"},
            {"Ticker": "GLD", "Azienda": "SPDR Gold Shares", "Settore": "Commodity",
                "Allocazione %": 6.90, "Quote": "18.0M", "Valore": "$3.8B"},
        ],
        "Carl Icahn": [
            {"Ticker": "IEP", "Azienda": "Icahn Enterprises", "Settore": "Conglomerate",
                "Allocazione %": 48.49, "Quote": "298M", "Valore": "$4.15B"},
            {"Ticker": "CVI", "Azienda": "CVR Energy", "Settore": "Energy",
                "Allocazione %": 28.01, "Quote": "31.2M", "Valore": "$2.40B"},
            {"Ticker": "UAN", "Azienda": "CVR Partners LP", "Settore": "Materials",
                "Allocazione %": 6.17, "Quote": "3.5M", "Valore": "$528M"},
            {"Ticker": "CTRI", "Azienda": "Centuri Holdings Inc", "Settore": "Utilities",
                "Allocazione %": 4.90, "Quote": "7.5M", "Valore": "$419M"},
            {"Ticker": "IFF", "Azienda": "Intl Flavors", "Settore": "Materials",
                "Allocazione %": 3.63, "Quote": "3.2M", "Valore": "$310M"},
            {"Ticker": "JBLU", "Azienda": "JetBlue Airways", "Settore": "Industrial",
                "Allocazione %": 1.74, "Quote": "33.6M", "Valore": "$149M"},
            {"Ticker": "MNRO", "Azienda": "Monro Inc.", "Settore": "Consumer",
                "Allocazione %": 0.95, "Quote": "5.08M", "Valore": "$81M"},
            {"Ticker": "SD", "Azienda": "SandRidge Energy", "Settore": "Energy",
                "Allocazione %": 0.94, "Quote": "4.95M", "Valore": "$80M"},
            {"Ticker": "BLCO", "Azienda": "Bausch + Lomb Corp.", "Settore": "Health",
                "Allocazione %": 2.50, "Quote": "14.5M", "Valore": "$213M"},
            {"Ticker": "CZR", "Azienda": "Caesars Entertainment", "Settore": "Consumer",
                "Allocazione %": 1.20, "Quote": "2.5M", "Valore": "$103M"},
            {"Ticker": "AEP", "Azienda": "American Electric Power", "Settore": "Utilities",
                "Allocazione %": 1.00, "Quote": "1.0M", "Valore": "$85M"},
            {"Ticker": "SATS", "Azienda": "EchoStar Corporation", "Settore": "Technology",
                "Allocazione %": 0.47, "Quote": "2.2M", "Valore": "$40M"},
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
            "Warren Buffett": "$263.1 Miliardi",
            "Michael Burry": "$93.9 Milioni",
            "Cathie Wood": "$12.86 Miliardi",
            "Bill Ackman": "$13.71 Miliardi",
            "David Tepper": "$5.93 Miliardi",
            "Ray Dalio": "$22.40 Miliardi",
            "Stanley Druckenmiller": "$3.38 Miliardi",
            "Ken Griffin": "$96.4 Miliardi",
            "Carl Icahn": "$8.55 Miliardi"
        }

        if inv_name in bios:
            st.markdown(
                f"<p style='color: #A0A0A0; font-size: 16px; margin-bottom: 20px;'><i>{bios[inv_name]}</i></p>", unsafe_allow_html=True)

        if inv_name in aum_map:
            render_custom_metric(
                "Asset Under Management (13F)", aum_map[inv_name], icon="💼")

        st.divider()

        if inv_name in portfolio_details:
            df_port = pd.DataFrame(portfolio_details[inv_name])

            c1, c2 = st.columns([1.5, 1])
            with c1:
                render_premium_portfolio_table(portfolio_details[inv_name])

            with c2:
                st.subheader("🥧 Allocazione Asset")
                fig_pie = px.pie(
                    df_port,
                    names='Ticker',
                    values='Allocazione %',
                    hole=0.4,
                    color_discrete_sequence=px.colors.qualitative.Bold
                )
                fig_pie.update_traces(
                    textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(margin=dict(
                    t=0, b=0, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True,
                                config={'displayModeBar': False})
        else:
            st.error(
                "Dati portafoglio non ancora digitalizzati per questo investitore.")

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

        t1, t2, t3, t4 = st.tabs(
            ["Top Investors", "Congress Trades", "Insider Trades", "Stock Picks"])

        with t1:
            st.write("")
            category_choice = st.radio("Filtra per stile di investimento:",
                                       ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors",
                                           "🏛️ Value Investors", "📉 Contrarians / Short", "⏳ Long-Term"],
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
                        data_1y = yf.download(
                            unique_tkrs, period="1y", progress=False)['Close']

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

                            df_galaxy["Rendimento Annuo %"] = df_galaxy["Ticker"].map(
                                ann_ret).fillna(0)
                            df_galaxy["Volatilità %"] = df_galaxy["Ticker"].map(
                                ann_vol).fillna(0)

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
                                    xaxis=dict(
                                        backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    yaxis=dict(
                                        backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)"),
                                    zaxis=dict(
                                        backgroundcolor="rgba(0,0,0,0)", gridcolor="rgba(255,255,255,0.1)")
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
                    "perf": "26.17%", "size": "$263.1B",
                    "categories": ["🌟 Popular", "🏛️ Value Investors", "⏳ Long-Term"],
                    "holdings": [("AAPL", "Apple Inc.", "#000000"), ("AXP", "American Express", "#006fcf"), ("KO", "Coca-Cola", "#E30016")],
                    "more": 24
                },
                {
                    "name": "Michael Burry", "company": "Scion Asset Management",
                    "perf": "28.20%", "size": "$93.9M",
                    "categories": ["🌟 Popular", "📉 Contrarians / Short"],
                    "holdings": [("MOH", "Molina Healthcare", "#00A99D"), ("LULU", "Lululemon Athletica", "#E60028"), ("SLM", "SLM Corp.", "#004B87")],
                    "more": 3
                },
                {
                    "name": "Cathie Wood", "company": "ARK Invest",
                    "perf": "48.75%", "size": "$12.86B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("TSLA", "Tesla", "#E82127"), ("AMD", "Advanced Micro Devices", "#FF0000"), ("CRCL", "Circle Internet Group", "#0052FF")],
                    "more": 10
                },
                {
                    "name": "Bill Ackman", "company": "Pershing Square",
                    "perf": "31.42%", "size": "$13.71B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🏛️ Value Investors"],
                    "holdings": [("BN", "Brookfield Corp", "#002F6C"), ("AMZN", "Amazon", "#FF9900"), ("UBER", "Uber", "#000000")],
                    "more": 5
                },
                {
                    "name": "David Tepper", "company": "Appaloosa Management",
                    "perf": "35.10%", "size": "$5.93B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("AMZN", "Amazon", "#FF9900"), ("MU", "Micron Technology", "#0066CC"), ("GOOG", "Alphabet Inc.", "#DB4437")],
                    "more": 12
                },
                {
                    "name": "Ray Dalio", "company": "Bridgewater Associates",
                    "perf": "14.80%", "size": "$22.40B",
                    "categories": ["🌟 Popular", "⏳ Long-Term"],
                    "holdings": [("SPY", "SPDR S&P 500", "#0B2664"), ("IVV", "iShares Core S&P 500", "#000000"), ("AMZN", "Amazon", "#FF9900")],
                    "more": 12
                },
                {
                    "name": "Stanley Druckenmiller", "company": "Duquesne Family Office",
                    "perf": "41.60%", "size": "$3.38B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("NTRA", "Natera", "#00A9E0"), ("EWZ", "iShares MSCI Brazil", "#008000"), ("INSM", "Insmed", "#8A929A")],
                    "more": 11
                },
                {
                    "name": "Ken Griffin", "company": "Citadel Advisors",
                    "perf": "21.30%", "size": "$96.4B",
                    "categories": ["🌟 Popular", "📉 Contrarians / Short", "⏳ Long-Term"],
                    "holdings": [("SPY", "SPDR S&P 500", "#0B2664"), ("QQQ", "Invesco QQQ", "#000000"), ("NVDA", "NVIDIA", "#76B900")],
                    "more": 6
                },
                {
                    "name": "Carl Icahn", "company": "Icahn Enterprises",
                    "perf": "12.40%", "size": "$8.55B",
                    "categories": ["🌟 Popular", "🏛️ Value Investors", "📉 Contrarians / Short"],
                    "holdings": [("IEP", "Icahn Enterprises", "#000000"), ("CVI", "CVR Energy", "#006fcf"), ("UAN", "CVR Partners LP", "#008000")],
                    "more": 9
                }
            ]

            filtered_data = [
                inv for inv in super_data if category_choice in inv['categories']]

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

                            st.markdown(
                                f'<div class="inv-card"><div class="inv-name">{inv["name"]}</div><div class="inv-company">{inv["company"]}</div><div class="inv-perf">📈 Performance: {inv["perf"]} last year</div><div class="inv-port">{inv["size"]} portfolio</div>{holdings_html}</div>', unsafe_allow_html=True)

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
            st.info(
                "Insider Trades (CEO, CFO, Board Members) verranno implementati leggendo i form SEC 4.")
        with t4:
            st.info("Le Stock Picks istituzionali verranno generate filtrando l'universo del S&P 500 in base alle logiche dell'Hedge Fund selezionato.")

# ==========================================
# PAGE 8: HEDGE FUND OS AI
# ==========================================
elif page_choice == "🤖 Hedge Fund OS AI":
    st.title("🤖 Hedge Fund OS AI")
    st.write("Canale di Controllo Multi-Agente per l'analisi fondamentale e la conformità del rischio.")
    st.divider()

    from agents_core import equity_portfolio_manager_agent, chief_risk_agent

    # Configurazione Chiave API (opzionale con fallback)
    with st.expander("🔑 Configurazione API Key (Opzionale)"):
        api_key_input = st.text_input("Inserisci la tua Gemini API Key per analisi live (lascia vuoto per usare il motore di simulazione):", 
                                      value=st.session_state.get("gemini_api_key", ""), 
                                      type="password")
        if api_key_input != st.session_state.get("gemini_api_key", ""):
            st.session_state["gemini_api_key"] = api_key_input
            st.toast("Gemini API Key salvata per la sessione!", icon="🔑")

    # Inizializziamo il ticker di default usando quello attivo nel portafoglio/tracker se presente
    default_ticker = st.session_state.get('active_ticker', 'NVDA')

    col_input1, col_input2 = st.columns([1, 2])
    with col_input1:
        ticker_per_agenti = st.text_input("Conferma Ticker per l'analisi AI:", value=default_ticker)
    with col_input2:
        nota_analisi = st.text_area("Istruzioni operative per l'Investment Office:", 
                                    value="Analisi dei margini storici e del Margin of Safety reale.")

    if st.button("⚡ Esegui Audit AI", key="run_ai_audit", type="primary"):
        with st.spinner(f"Elaborazione report in corso da parte dell'Investment Office per {ticker_per_agenti}..."):
            try:
                # 1. Recuperiamo i dati reali sfruttando yfinance
                stock = yf.Ticker(ticker_per_agenti)
                info = stock.info
                
                prezzo_live = info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
                valuta = info.get("currency", "USD")
                market_cap = info.get("marketCap") or 0
                ebitda = info.get("ebitda") or 0
                
                # 2. Compiliamo il payload per i cervelli artificiali
                contesto_arricchito = f"""
                TARGET: {ticker_per_agenti}
                Prezzo Spot: {prezzo_live} {valuta}
                Market Cap: {market_cap:,} {valuta}
                EBITDA: {ebitda:,} {valuta}
                --- NOTE ---
                {nota_analisi}
                """
                
                # 3. Interrogazione in cascata degli agenti
                key_to_use = st.session_state.get("gemini_api_key") or None
                pm_output = equity_portfolio_manager_agent(ticker_per_agenti, contesto_arricchito, api_key=key_to_use)
                risk_output = chief_risk_agent(pm_output, api_key=key_to_use)
                
                # 4. Parsing del Rating e Visualizzazione Grafica dei Banner
                risk_rating = "YELLOW"
                if "GREEN" in risk_output.upper(): risk_rating = "GREEN"
                elif "RED" in risk_output.upper(): risk_rating = "RED"
                elif "BLACK" in risk_output.upper(): risk_rating = "BLACK"
                
                if risk_rating in ["GREEN", "YELLOW"]:
                    st.success(f"🟢 **RISK RATING: {risk_rating}** — Condizioni validate per lo staging.")
                else:
                    st.error(f"🔴 **VETO RILEVATO: {risk_rating}** — Operazione bloccata dal Risk Management.")
                
                # Visualizzazione dei report espandibili
                c_pm, c_risk = st.columns(2)
                with c_pm:
                    with st.expander("📈 Visualizza Report Finanziario (Equity PM)", expanded=True):
                        st.markdown(pm_output)
                with c_risk:
                    with st.expander("🛡️ Visualizza Risk Audit (Chief Risk)", expanded=True):
                        st.markdown(risk_output)
            except Exception as e:
                st.error(f"Si è verificato un errore durante l'audit: {e}")

# ==========================================
# PAGE: BUSINESS SEGMENTS & FINANCIAL FLOW
# ==========================================
elif page_choice == "🧩 Business Segments":
    # 0. Subscription Status Header & Demo Toggle
    is_pro = monetization_engine.is_user_pro()
    
    st.markdown(f"""
    <div style="background: linear-gradient(135deg, rgba(15,23,42,0.95) 0%, rgba(30,58,138,0.4) 100%); border: 1px solid rgba(0, 242, 254, 0.25); border-radius: 20px; padding: 24px; margin-bottom: 24px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
            <div>
                <span class="ticker-badge" style="font-size: 13px; padding: 5px 12px;">Business Segments Pro</span>
                <h2 style="color: #FFFFFF; font-family: 'Outfit', sans-serif; font-size: 28px; margin: 8px 0 4px 0; font-weight: 800;">🧩 Business Segment Breakdown & Financial Flow</h2>
                <p style="color: #94A3B8; font-size: 14px; margin: 0;">Analisi visiva multi-anno per segmento aziendale, area geografica e diagramma di flusso Sankey.</p>
            </div>
            <div style="text-align: right;">
                {'<span style="background: linear-gradient(135deg, #00FF7F 0%, #10B981 100%); color: #0F172A; font-weight: 800; font-size: 12px; padding: 6px 14px; border-radius: 12px;">👑 Statuto Account: PRO ATTIVO</span>' if is_pro else '<span style="background: rgba(255,255,255,0.1); color: #CBD5E1; font-weight: 700; font-size: 12px; padding: 6px 14px; border-radius: 12px; border: 1px solid rgba(255,255,255,0.2);">⚪ Statuto Account: PIANO FREE</span>'}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Demo Switcher Bar for Admin Testing
    with st.expander("⚙️ Pannello di Controllo Monetizzazione (Demo Switcher Free / Pro)"):
        col_demo1, col_demo2 = st.columns([3, 1])
        with col_demo1:
            st.caption("Usa questo selettore per testare l'esperienza visiva tra Utente Free (con Paywall Stripe) e Utente Pro Abbonato.")
        with col_demo2:
            new_pro_state = st.toggle("Attiva Account Pro", value=is_pro, key="toggle_pro_status_demo")
            if new_pro_state != is_pro:
                st.session_state["is_pro_user"] = new_pro_state
                st.rerun()
    
    # 1. Unified State-Based Ticker Selection System
    if "active_bus_ticker" not in st.session_state:
        st.session_state["active_bus_ticker"] = "AAPL"
        
    st.markdown("<p style='color: #8A929A; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px;'>⚡ Quick Select Mega-Cap Tickers (Inclusi nel Piano Free):</p>", unsafe_allow_html=True)
    p_cols = st.columns(10)
    presets = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "NFLX", "KO", "DIS"]
    for idx, p_sym in enumerate(presets):
        with p_cols[idx]:
            is_active = (st.session_state["active_bus_ticker"] == p_sym)
            if st.button(p_sym, key=f"preset_btn_{p_sym}", use_container_width=True, type="primary" if is_active else "secondary"):
                st.session_state["active_bus_ticker"] = p_sym
                st.session_state["custom_ticker_search_field"] = ""
                st.rerun()
                
    c_sel1, c_sel2 = st.columns([3, 1])
    
    with c_sel1:
        user_typed = st.text_input(
            "🔒 Ricerca qualsiasi Ticker Personalizzato (Riservato agli utenti Pro, es. WMT, COST, LLY, CAT...):",
            key="custom_ticker_search_field",
            placeholder="Digita ticker (es. COST) e premi Invio..."
        ).upper().strip()
        
        if user_typed and user_typed != st.session_state["active_bus_ticker"]:
            st.session_state["active_bus_ticker"] = user_typed
            st.rerun()
            
    with c_sel2:
        period_choice = st.radio(
            "Periodo Temporale:",
            options=["Annual (FY)", "Quarterly (Q)"],
            horizontal=True,
            key="qualtrim_period_select"
        )
        
    ticker_to_use = st.session_state["active_bus_ticker"]
    
    # 2. Freemium Gate Enforcement Check
    is_custom_ticker = (ticker_to_use not in presets)
    is_quarterly = (period_choice.startswith("Quarter"))
    
    if not is_pro and (is_custom_ticker or is_quarterly):
        # Trigger Stripe Paywall Modal
        reason = "Ricerca Ticker Personalizzati (SEC EDGAR)" if is_custom_ticker else "Dati Trimestrali Dettagliati (Q1-Q4)"
        monetization_engine.render_paywall_modal(feature_name=reason)
    else:
        # Fetch Segment & Financial Data
        with st.spinner(f"Caricamento dati di segmento ({period_choice}) per {ticker_to_use}..."):
            company_data = qualtrim_engine.get_company_segment_data(ticker_to_use, period=period_choice)
        
    if not company_data:
        st.error(f"Impossibile recuperare dati per {ticker_to_use}. Verifica il simbolo ticker.")
    else:
        if company_data.get("_is_fallback"):
            source_name = company_data.get("_source", "SEC EDGAR Official API / yfinance")
            st.info(f"🏛️ **Fonte Dati:** {source_name} — Dati finanziari storici dal {company_data['periods'][0]} al {company_data['periods'][-1]} per {ticker_to_use}.")
            
        periods = company_data["periods"]
        latest_p = periods[-1]
        bus_segs = company_data["business_segments"]
        
        # Calculate Top Segment and Fastest Growing Segment
        top_segment = max(bus_segs.keys(), key=lambda k: bus_segs[k][-1] if bus_segs[k] else 0)
        top_seg_val = bus_segs[top_segment][-1]
        
        # Growth Rate calculation
        fastest_growth_seg = top_segment
        max_growth_pct = -999.0
        for seg_k, vals in bus_segs.items():
            if len(vals) >= 2 and vals[-2] > 0:
                growth = ((vals[-1] - vals[-2]) / vals[-2]) * 100
                if growth > max_growth_pct:
                    max_growth_pct = growth
                    fastest_growth_seg = seg_k
                    
        geo_segs = company_data.get("geographic_segments", {})
        top_geo = max(geo_segs.keys(), key=lambda k: geo_segs[k][-1] if geo_segs[k] else 0) if geo_segs else "N/A"
        
        # Glassmorphic KPI Cards
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)
        
        with kpi_col1:
            st.markdown(f"""
            <div class="custom-kpi-card">
                <div style="color: #8A929A; font-size: 11px; font-weight: 700; text-transform: uppercase;">Azienda Target</div>
                <div style="color: #FFFFFF; font-size: 22px; font-weight: 800; margin: 4px 0;">{company_data['name']}</div>
                <div style="color: #00F2FE; font-size: 12px; font-weight: 600;">{ticker_to_use} ({company_data['currency']})</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col2:
            rev_val = company_data['sankey_latest'].get('Revenue', 0)
            st.markdown(f"""
            <div class="custom-kpi-card">
                <div style="color: #8A929A; font-size: 11px; font-weight: 700; text-transform: uppercase;">Ricavi ({latest_p})</div>
                <div style="color: #00FF7F; font-size: 24px; font-weight: 800; margin: 4px 0;">${rev_val:.1f} B</div>
                <div style="color: #94A3B8; font-size: 12px; font-weight: 600;">Totale Periodo ({company_data['unit']})</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col3:
            st.markdown(f"""
            <div class="custom-kpi-card">
                <div style="color: #8A929A; font-size: 11px; font-weight: 700; text-transform: uppercase;">Top Segmento</div>
                <div style="color: #F59E0B; font-size: 18px; font-weight: 800; margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{top_segment}</div>
                <div style="color: #00F2FE; font-size: 12px; font-weight: 600;">${top_seg_val:.1f} B ({periods[-1]})</div>
            </div>
            """, unsafe_allow_html=True)
            
        with kpi_col4:
            growth_text = f"+{max_growth_pct:.1f}%" if max_growth_pct > 0 else f"{max_growth_pct:.1f}%"
            st.markdown(f"""
            <div class="custom-kpi-card">
                <div style="color: #8A929A; font-size: 11px; font-weight: 700; text-transform: uppercase;">Segmento a Maggior Crescita</div>
                <div style="color: #EC4899; font-size: 18px; font-weight: 800; margin: 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">{fastest_growth_seg}</div>
                <div style="color: #00FF7F; font-size: 12px; font-weight: 600;">Crescita: {growth_text} vs periodo prec.</div>
            </div>
            """, unsafe_allow_html=True)
            
        st.divider()
        
        # Interactive Dashboard Tabs
        tab_bus, tab_geo, tab_sankey, tab_fin = st.tabs([
            "📊 Segmenti Aziendali", 
            "🌍 Ripartizione Geografica", 
            "💸 Diagramma Sankey", 
            "📈 Trend Finanziari Multi-Anno"
        ])
        
        with tab_bus:
            st.subheader(f"📊 Ricavi per Segmento Aziendale ({company_data['name']} - {period_choice})")
            
            v_col1, v_col2 = st.columns([3, 1])
            with v_col1:
                view_mode = st.radio(
                    "Modalità Grafico:", 
                    options=["Pila Assoluta ($)", "Quota Percentuale (%)", "Entrambi i Grafici"],
                    horizontal=True,
                    key="qualtrim_view_mode_bus"
                )
                
            if view_mode in ["Pila Assoluta ($)", "Entrambi i Grafici"]:
                fig_stacked = qualtrim_engine.create_segment_stacked_bar_chart(company_data, "business_segments")
                st.plotly_chart(fig_stacked, use_container_width=True)
                
            if view_mode in ["Quota Percentuale (%)", "Entrambi i Grafici"]:
                fig_pct = qualtrim_engine.create_segment_percentage_chart(company_data, "business_segments")
                st.plotly_chart(fig_pct, use_container_width=True)
                
            df_bus = pd.DataFrame(company_data["business_segments"], index=[str(p) for p in periods])
            df_bus["TOTALE"] = df_bus.sum(axis=1)
            st.markdown(qualtrim_engine.render_qualtrim_data_table(df_bus, f"Dati Storici Segmenti Aziendali ({company_data['name']})"), unsafe_allow_html=True)
            
        with tab_geo:
            st.subheader("🌍 Ricavi per Area Geografica")
            if company_data.get("geographic_segments"):
                col_g1, col_g2 = st.columns([3, 2])
                with col_g1:
                    fig_geo_stack = qualtrim_engine.create_segment_stacked_bar_chart(company_data, "geographic_segments")
                    st.plotly_chart(fig_geo_stack, use_container_width=True)
                with col_g2:
                    fig_geo_donut = qualtrim_engine.create_geographic_donut_chart(company_data)
                    st.plotly_chart(fig_geo_donut, use_container_width=True)
                    
                df_geo = pd.DataFrame(company_data["geographic_segments"], index=[str(p) for p in periods])
                df_geo["TOTALE"] = df_geo.sum(axis=1)
                st.markdown(qualtrim_engine.render_qualtrim_data_table(df_geo, f"Dati Storici Ripartizione Geografica ({company_data['name']})"), unsafe_allow_html=True)
            else:
                st.info("Dati geografici non disponibili per questo ticker.")
                
        with tab_sankey:
            st.subheader(f"💸 Flusso Economico Qualtrim Sankey ({latest_p}) — {company_data['name']}")
            fig_sankey = qualtrim_engine.create_sankey_diagram(company_data)
            if fig_sankey:
                st.plotly_chart(fig_sankey, use_container_width=True)
            else:
                st.info("Diagramma Sankey non disponibile per questo ticker.")
                
            with st.expander("🔍 Dettaglio Voci del Diagramma Sankey"):
                s_data = company_data.get("sankey_latest", {})
                for k, v in s_data.items():
                    st.write(f"• **{k}**: ${v:.2f} {company_data['unit']}")
                    
        with tab_fin:
            st.subheader(f"📈 Trend Storici Conto Economico & Cash Flow ({ticker_to_use} - {period_choice})")
            fig_fin_trends = qualtrim_engine.create_multiyear_financial_trends_chart(ticker_to_use, period=period_choice)
            if fig_fin_trends:
                st.plotly_chart(fig_fin_trends, use_container_width=True)
            else:
                st.info("Trend finanziari non disponibili.")
                
        # 3. High-CPA Broker Affiliate Links Partnership Card
        monetization_engine.render_broker_affiliate_card(ticker_to_use)
        
        st.divider()
        csv_data = pd.DataFrame(company_data["business_segments"]).to_csv(index=True)
        st.download_button(
            label=f"📥 Scarica CSV Dati Business Segments ({ticker_to_use})",
            data=csv_data,
            file_name=f"{ticker_to_use}_business_segments_{period_choice}.csv",
            mime="text/csv"
        )