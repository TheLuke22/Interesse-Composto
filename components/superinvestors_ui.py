"""
Super Investors & 13F Institutional Intelligence UI Component:
Features August 2026 13F portfolios across 9 hedge funds / titans,
3D Galaxy Risk/Return Constellation, Category Filtering, and Warren Buffett 10-K Scorecard.
"""
import random
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from components.ui_utils import render_custom_metric, render_premium_portfolio_table, WALL_STREET_QUOTES
import qualtrim_engine


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


PORTFOLIO_DETAILS_13F = {
    "Warren Buffett": [
        {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology", "Allocazione %": 26.50, "Quote": "280.0M", "Valore": "$83.5B"},
        {"Ticker": "AXP", "Azienda": "American Express", "Settore": "Financial", "Allocazione %": 14.80, "Quote": "151.6M", "Valore": "$46.7B"},
        {"Ticker": "KO", "Azienda": "Coca-Cola", "Settore": "Consumer", "Allocazione %": 10.20, "Quote": "400.0M", "Valore": "$32.2B"},
        {"Ticker": "BAC", "Azienda": "Bank of America", "Settore": "Financial", "Allocazione %": 8.90, "Quote": "450.0M", "Valore": "$28.1B"},
        {"Ticker": "CVX", "Azienda": "Chevron", "Settore": "Energy", "Allocazione %": 6.80, "Quote": "110.0M", "Valore": "$21.4B"},
        {"Ticker": "OXY", "Azienda": "Occidental Petroleum", "Settore": "Energy", "Allocazione %": 6.10, "Quote": "255.3M", "Valore": "$19.2B"},
        {"Ticker": "MCO", "Azienda": "Moody's Corp.", "Settore": "Financial", "Allocazione %": 4.30, "Quote": "24.7M", "Valore": "$13.6B"},
        {"Ticker": "CB", "Azienda": "Chubb Limited", "Settore": "Financial", "Allocazione %": 3.80, "Quote": "29.5M", "Valore": "$12.0B"},
        {"Ticker": "KHC", "Azienda": "Kraft Heinz Co.", "Settore": "Consumer", "Allocazione %": 3.10, "Quote": "325.6M", "Valore": "$9.8B"},
        {"Ticker": "DVA", "Azienda": "DaVita Inc.", "Settore": "Health", "Allocazione %": 1.60, "Quote": "36.1M", "Valore": "$5.0B"},
        {"Ticker": "SIRI", "Azienda": "Sirius XM Holdings", "Settore": "Technology", "Allocazione %": 1.40, "Quote": "115.0M", "Valore": "$4.4B"},
        {"Ticker": "KR", "Azienda": "Kroger Co.", "Settore": "Consumer", "Allocazione %": 1.10, "Quote": "50.0M", "Valore": "$3.5B"},
        {"Ticker": "C", "Azienda": "Citigroup Inc.", "Settore": "Financial", "Allocazione %": 1.00, "Quote": "45.0M", "Valore": "$3.2B"},
        {"Ticker": "VRSN", "Azienda": "VeriSign Inc.", "Settore": "Technology", "Allocazione %": 0.80, "Quote": "12.8M", "Valore": "$2.5B"},
        {"Ticker": "ULTA", "Azienda": "Ulta Beauty Inc.", "Settore": "Consumer", "Allocazione %": 0.50, "Quote": "1.2M", "Valore": "$1.6B"},
        {"Ticker": "HEI-A", "Azienda": "HEICO Corp. (Class A)", "Settore": "Industrial", "Allocazione %": 0.40, "Quote": "2.1M", "Valore": "$1.3B"},
    ],
    "Michael Burry": [
        {"Ticker": "BABA", "Azienda": "Alibaba Group", "Settore": "E-Commerce", "Allocazione %": 24.50, "Quote": "280K", "Valore": "$29.0M"},
        {"Ticker": "BIDU", "Azienda": "Baidu Inc.", "Settore": "Technology", "Allocazione %": 18.20, "Quote": "190K", "Valore": "$21.6M"},
        {"Ticker": "JD", "Azienda": "JD.com Inc.", "Settore": "E-Commerce", "Allocazione %": 15.40, "Quote": "450K", "Valore": "$18.2M"},
        {"Ticker": "SQ", "Azienda": "Block Inc.", "Settore": "Financial", "Allocazione %": 12.80, "Quote": "160K", "Valore": "$15.2M"},
        {"Ticker": "VST", "Azienda": "Vistra Corp.", "Settore": "Energy", "Allocazione %": 9.50, "Quote": "85K", "Valore": "$11.3M"},
        {"Ticker": "FOUR", "Azienda": "Shift4 Payments", "Settore": "Financial", "Allocazione %": 7.20, "Quote": "90K", "Valore": "$8.5M"},
        {"Ticker": "SHW", "Azienda": "Sherwin-Williams", "Settore": "Materials", "Allocazione %": 6.80, "Quote": "20K", "Valore": "$8.1M"},
        {"Ticker": "REGN", "Azienda": "Regeneron Pharmaceuticals", "Settore": "Health", "Allocazione %": 5.60, "Quote": "6.5K", "Valore": "$6.6M"},
    ],
    "Cathie Wood": [
        {"Ticker": "TSLA", "Azienda": "Tesla Inc.", "Settore": "Auto", "Allocazione %": 12.80, "Quote": "7.2M", "Valore": "$2.00B"},
        {"Ticker": "COIN", "Azienda": "Coinbase Global", "Settore": "Crypto", "Allocazione %": 9.50, "Quote": "5.4M", "Valore": "$1.48B"},
        {"Ticker": "ROKU", "Azienda": "Roku Inc.", "Settore": "Communication", "Allocazione %": 8.40, "Quote": "16.5M", "Valore": "$1.31B"},
        {"Ticker": "PLTR", "Azienda": "Palantir Technologies", "Settore": "Software", "Allocazione %": 7.60, "Quote": "28.5M", "Valore": "$1.19B"},
        {"Ticker": "SQ", "Azienda": "Block Inc.", "Settore": "Financial", "Allocazione %": 6.90, "Quote": "12.8M", "Valore": "$1.08B"},
        {"Ticker": "HOOD", "Azienda": "Robinhood Markets", "Settore": "Financial", "Allocazione %": 6.20, "Quote": "32.0M", "Valore": "$967M"},
        {"Ticker": "RBLX", "Azienda": "Roblox Corp.", "Settore": "Software", "Allocazione %": 5.80, "Quote": "18.5M", "Valore": "$905M"},
        {"Ticker": "CRSP", "Azienda": "CRISPR Therapeutics", "Settore": "Health", "Allocazione %": 5.10, "Quote": "11.2M", "Valore": "$796M"},
        {"Ticker": "SHOP", "Azienda": "Shopify Inc.", "Settore": "E-Commerce", "Allocazione %": 4.80, "Quote": "8.5M", "Valore": "$749M"},
        {"Ticker": "TEM", "Azienda": "Tempus AI Inc.", "Settore": "Health", "Allocazione %": 4.20, "Quote": "12.5M", "Valore": "$655M"},
        {"Ticker": "AMD", "Azienda": "Advanced Micro Devices", "Settore": "Technology", "Allocazione %": 3.90, "Quote": "3.4M", "Valore": "$608M"},
        {"Ticker": "PATH", "Azienda": "UiPath Inc.", "Settore": "Software", "Allocazione %": 3.20, "Quote": "35.0M", "Valore": "$499M"},
    ],
    "Bill Ackman": [
        {"Ticker": "HLT", "Azienda": "Hilton Worldwide", "Settore": "Consumer", "Allocazione %": 21.50, "Quote": "11.2M", "Valore": "$3.19B"},
        {"Ticker": "QSR", "Azienda": "Restaurant Brands", "Settore": "Consumer", "Allocazione %": 18.20, "Quote": "24.5M", "Valore": "$2.70B"},
        {"Ticker": "CMG", "Azienda": "Chipotle Mexican Grill", "Settore": "Consumer", "Allocazione %": 17.10, "Quote": "31.0M", "Valore": "$2.54B"},
        {"Ticker": "GOOGL", "Azienda": "Alphabet Inc. (Class A)", "Settore": "Technology", "Allocazione %": 14.60, "Quote": "9.5M", "Valore": "$2.17B"},
        {"Ticker": "BN", "Azienda": "Brookfield Corp.", "Settore": "Financial", "Allocazione %": 12.40, "Quote": "35.0M", "Valore": "$1.84B"},
        {"Ticker": "NKE", "Azienda": "Nike Inc.", "Settore": "Consumer", "Allocazione %": 8.50, "Quote": "14.2M", "Valore": "$1.26B"},
        {"Ticker": "HHH", "Azienda": "Howard Hughes Holdings", "Settore": "Real Estate", "Allocazione %": 5.80, "Quote": "12.5M", "Valore": "$861M"},
        {"Ticker": "GOOG", "Azienda": "Alphabet Inc. (Class C)", "Settore": "Technology", "Allocazione %": 1.90, "Quote": "1.2M", "Valore": "$282M"},
    ],
    "David Tepper": [
        {"Ticker": "BABA", "Azienda": "Alibaba Group", "Settore": "E-Commerce", "Allocazione %": 16.50, "Quote": "12.8M", "Valore": "$1.23B"},
        {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce", "Allocazione %": 11.80, "Quote": "4.1M", "Valore": "$879M"},
        {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software", "Allocazione %": 9.60, "Quote": "1.5M", "Valore": "$715M"},
        {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication", "Allocazione %": 8.80, "Quote": "1.1M", "Valore": "$656M"},
        {"Ticker": "GOOGL", "Azienda": "Alphabet Inc.", "Settore": "Communication", "Allocazione %": 7.90, "Quote": "3.2M", "Valore": "$589M"},
        {"Ticker": "TSM", "Azienda": "Taiwan Semi", "Settore": "Technology", "Allocazione %": 7.20, "Quote": "2.9M", "Valore": "$536M"},
        {"Ticker": "VST", "Azienda": "Vistra Corp.", "Settore": "Energy", "Allocazione %": 6.80, "Quote": "5.2M", "Valore": "$507M"},
        {"Ticker": "PDD", "Azienda": "PDD Holdings Inc.", "Settore": "E-Commerce", "Allocazione %": 6.20, "Quote": "3.4M", "Valore": "$462M"},
        {"Ticker": "BIDU", "Azienda": "Baidu Inc.", "Settore": "Technology", "Allocazione %": 5.50, "Quote": "3.8M", "Valore": "$410M"},
        {"Ticker": "FXI", "Azienda": "iShares China Large-Cap ETF", "Settore": "ETF", "Allocazione %": 5.10, "Quote": "11.5M", "Valore": "$380M"},
        {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology", "Allocazione %": 4.60, "Quote": "2.8M", "Valore": "$343M"},
    ],
    "Ray Dalio": [
        {"Ticker": "IVV", "Azienda": "iShares Core S&P 500", "Settore": "ETF", "Allocazione %": 6.80, "Quote": "3.1M", "Valore": "$1.69B"},
        {"Ticker": "IEMG", "Azienda": "iShares Core MSCI Emerging", "Settore": "ETF", "Allocazione %": 5.50, "Quote": "24.5M", "Valore": "$1.36B"},
        {"Ticker": "GOOGL", "Azienda": "Alphabet Inc.", "Settore": "Communication", "Allocazione %": 4.80, "Quote": "6.2M", "Valore": "$1.19B"},
        {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology", "Allocazione %": 4.50, "Quote": "8.8M", "Valore": "$1.12B"},
        {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication", "Allocazione %": 4.10, "Quote": "1.8M", "Valore": "$1.02B"},
        {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software", "Allocazione %": 3.90, "Quote": "1.9M", "Valore": "$967M"},
        {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce", "Allocazione %": 3.80, "Quote": "4.5M", "Valore": "$942M"},
        {"Ticker": "SPY", "Azienda": "SPDR S&P 500 ETF", "Settore": "ETF", "Allocazione %": 3.40, "Quote": "1.5M", "Valore": "$843M"},
        {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology", "Allocazione %": 3.10, "Quote": "3.5M", "Valore": "$769M"},
        {"Ticker": "PG", "Azienda": "Procter & Gamble", "Settore": "Consumer", "Allocazione %": 2.80, "Quote": "3.8M", "Valore": "$694M"},
        {"Ticker": "COST", "Azienda": "Costco Wholesale", "Settore": "Consumer", "Allocazione %": 2.40, "Quote": "650K", "Valore": "$595M"},
        {"Ticker": "WMT", "Azienda": "Walmart Inc.", "Settore": "Consumer", "Allocazione %": 2.20, "Quote": "7.2M", "Valore": "$546M"},
        {"Ticker": "JNJ", "Azienda": "Johnson & Johnson", "Settore": "Health", "Allocazione %": 2.00, "Quote": "3.1M", "Valore": "$496M"},
    ],
    "Stanley Druckenmiller": [
        {"Ticker": "NTRA", "Azienda": "Natera Inc.", "Settore": "Health", "Allocazione %": 18.50, "Quote": "5.8M", "Valore": "$731M"},
        {"Ticker": "COHR", "Azienda": "Coherent Corp.", "Settore": "Technology", "Allocazione %": 14.20, "Quote": "6.2M", "Valore": "$561M"},
        {"Ticker": "TSM", "Azienda": "Taiwan Semi", "Settore": "Technology", "Allocazione %": 10.50, "Quote": "2.2M", "Valore": "$415M"},
        {"Ticker": "WWD", "Azienda": "Woodward Inc.", "Settore": "Industrial", "Allocazione %": 9.20, "Quote": "1.8M", "Valore": "$363M"},
        {"Ticker": "SE", "Azienda": "Sea Limited", "Settore": "E-Commerce", "Allocazione %": 8.10, "Quote": "3.8M", "Valore": "$320M"},
        {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software", "Allocazione %": 6.80, "Quote": "520K", "Valore": "$269M"},
        {"Ticker": "VST", "Azienda": "Vistra Corp.", "Settore": "Energy", "Allocazione %": 6.20, "Quote": "2.4M", "Valore": "$245M"},
        {"Ticker": "TEVA", "Azienda": "Teva Pharmaceutical", "Settore": "Health", "Allocazione %": 5.50, "Quote": "12.5M", "Valore": "$217M"},
        {"Ticker": "AR", "Azienda": "Antero Resources", "Settore": "Energy", "Allocazione %": 4.80, "Quote": "5.1M", "Valore": "$190M"},
        {"Ticker": "NAMS", "Azienda": "NewAmsterdam Pharma", "Settore": "Health", "Allocazione %": 4.10, "Quote": "7.2M", "Valore": "$162M"},
    ],
    "Ken Griffin": [
        {"Ticker": "SPY", "Azienda": "SPDR S&P 500 ETF", "Settore": "ETF", "Allocazione %": 8.20, "Quote": "16.5M", "Valore": "$8.90B"},
        {"Ticker": "NVDA", "Azienda": "NVIDIA Corp.", "Settore": "Technology", "Allocazione %": 6.40, "Quote": "55.0M", "Valore": "$6.94B"},
        {"Ticker": "MSFT", "Azienda": "Microsoft Corp.", "Settore": "Software", "Allocazione %": 5.50, "Quote": "13.2M", "Valore": "$5.97B"},
        {"Ticker": "AMZN", "Azienda": "Amazon.com Inc.", "Settore": "E-Commerce", "Allocazione %": 5.10, "Quote": "26.5M", "Valore": "$5.53B"},
        {"Ticker": "META", "Azienda": "Meta Platforms", "Settore": "Communication", "Allocazione %": 4.60, "Quote": "9.8M", "Valore": "$4.99B"},
        {"Ticker": "AAPL", "Azienda": "Apple Inc.", "Settore": "Technology", "Allocazione %": 4.10, "Quote": "19.5M", "Valore": "$4.45B"},
        {"Ticker": "GOOGL", "Azienda": "Alphabet Inc.", "Settore": "Communication", "Allocazione %": 3.80, "Quote": "20.2M", "Valore": "$4.12B"},
        {"Ticker": "QQQ", "Azienda": "Invesco QQQ Trust", "Settore": "ETF", "Allocazione %": 3.50, "Quote": "7.8M", "Valore": "$3.80B"},
        {"Ticker": "AVGO", "Azienda": "Broadcom Inc.", "Settore": "Technology", "Allocazione %": 3.10, "Quote": "2.1M", "Valore": "$3.36B"},
        {"Ticker": "LLY", "Azienda": "Eli Lilly & Co.", "Settore": "Health", "Allocazione %": 2.70, "Quote": "2.8M", "Valore": "$2.93B"},
    ],
    "Carl Icahn": [
        {"Ticker": "IEP", "Azienda": "Icahn Enterprises", "Settore": "Conglomerate", "Allocazione %": 65.00, "Quote": "420.0M", "Valore": "$7.41B"},
        {"Ticker": "CVI", "Azienda": "CVR Energy Inc.", "Settore": "Energy", "Allocazione %": 18.50, "Quote": "78.5M", "Valore": "$2.11B"},
        {"Ticker": "UAN", "Azienda": "CVR Partners LP", "Settore": "Materials", "Allocazione %": 4.80, "Quote": "6.2M", "Valore": "$547M"},
        {"Ticker": "JBLU", "Azienda": "JetBlue Airways", "Settore": "Industrial", "Allocazione %": 3.50, "Quote": "38.0M", "Valore": "$399M"},
        {"Ticker": "CTRI", "Azienda": "Centuri Holdings Inc.", "Settore": "Utilities", "Allocazione %": 2.80, "Quote": "12.0M", "Valore": "$319M"},
        {"Ticker": "SD", "Azienda": "SandRidge Energy", "Settore": "Energy", "Allocazione %": 1.90, "Quote": "15.5M", "Valore": "$217M"},
        {"Ticker": "BLCO", "Azienda": "Bausch + Lomb Corp.", "Settore": "Health", "Allocazione %": 1.50, "Quote": "10.2M", "Valore": "$171M"},
        {"Ticker": "CZR", "Azienda": "Caesars Entertainment", "Settore": "Consumer", "Allocazione %": 1.20, "Quote": "3.2M", "Valore": "$137M"},
    ]
}


def render_superinvestors_ui(fetch_galaxy_history_fn):
    """
    Renders the Super Investors 13F Institutional Intelligence page.
    """
    portfolio_details = PORTFOLIO_DETAILS_13F

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
            "Warren Buffett": "$315.4 Miliardi",
            "Michael Burry": "$118.5 Milioni",
            "Cathie Wood": "$15.60 Miliardi",
            "Bill Ackman": "$14.85 Miliardi",
            "David Tepper": "$7.45 Miliardi",
            "Ray Dalio": "$24.80 Miliardi",
            "Stanley Druckenmiller": "$3.95 Miliardi",
            "Ken Griffin": "$108.5 Miliardi",
            "Carl Icahn": "$11.40 Miliardi"
        }

        if inv_name in bios:
            st.markdown(f"<p style='color: #A0A0A0; font-size: 16px; margin-bottom: 20px;'><i>{bios[inv_name]}</i></p>", unsafe_allow_html=True)

        if inv_name in aum_map:
            render_custom_metric("Asset Under Management (13F)", aum_map[inv_name], icon="💼")

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
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=350, showlegend=False)
                st.plotly_chart(fig_pie, use_container_width=True, config={'displayModeBar': False})
        else:
            st.error("Dati portafoglio non ancora digitalizzati per questo investitore.")

        if inv_name == "Warren Buffett":
            st.divider()
            st.subheader("📘 Guida Completa: Cosa Guarda Warren Buffett nel Bilancio (10-K)")
            st.markdown("""
            La filosofia di analisi fondamentale di Warren Buffett si concentra su **tre documenti contabili chiave** del report annuale 10-K per identificare aziende con un **fossato competitivo inattaccabile (Economic Moat)**.
            """)

            guide_tab1, guide_tab2, guide_tab3, guide_tab4 = st.tabs([
                "📊 Conto Economico",
                "🏛️ Stato Patrimoniale",
                "💸 Rendiconto Finanziario",
                "🔍 Test Ticker dal Vivo"
            ])

            with guide_tab1:
                st.markdown("""
                ### 📊 1. Conto Economico (Income Statement)
                * **Margine di Profitto Lordo (Gross Margin) ≥ 40%**: Se l'azienda mantiene un margine lordo elevato e costante negli anni, significa che possiede un **pricing power** elevato e non deve ribassare i prezzi per competere.
                * **Spese SG&A / Profitto Lordo < 30%**: Spese generali, amministrative e di vendita basse indicano un'azienda estremamente efficiente che non deve spendere fortune in pubblicità o burocrazia per vendere i propri prodotti.
                * **Spese in R&D (Ricerca & Sviluppo) assenti o minime**: Aziende che richiedono continui investimenti colossali in R&D per non diventare obsolete (es. alcuni settori tech o biotech) corrono un rischio tecnologico elevato. Buffett preferisce prodotti stabili e senza tempo (es. Coca-Cola, See's Candies).
                * **Ammortamenti / Profitto Lordo < 10%**: Bassi ammortamenti indicano che i macchinari/impianti non si usurano rapidamente, evitando continui reinvestimenti per mantenere l'attività.
                * **Spese per Interessi / EBIT < 15%**: L'azienda non deve essere soffocata dagli interessi sul debito. Nei periodi di crisi o tassi alti, la maggior parte del reddito operativo resta intatta.
                * **Margine di Utile Netto ≥ 20%**: Una percentuale elevata di ricavi si trasforma direttamente in utile netto disponibile per gli azionisti.
                """)

            with guide_tab2:
                st.markdown("""
                ### 🏛️ 2. Stato Patrimoniale (Balance Sheet)
                * **Cassa e Titoli a Breve Termine Elevati**: Una consistente riserva di liquidità permette all'azienda di superare le recessioni e cogliere opportunità di acquisizione a prezzo di saldo.
                * **Debito a Lungo Termine / Utile Netto < 4 anni**: Buffett preferisce aziende che potrebbero estinguere **l'intero debito a lungo termine in meno di 3-4 anni** di utili netti correnti.
                * **Utili Trattenuti (Retained Earnings) in Crescita**: Gli utili non distribuiti come dividendi devono incrementare il valore contabile dell'azienda anno dopo anno, generando un effetto *compounding*.
                * **Return on Equity (ROE) ≥ 15-20%**: Un elevato rendimento sul capitale proprio dimostra la capacità del management di allocare efficientemente il capitale degli azionisti (senza abusare della leva finanziaria).
                * **Azioni Proprie (Treasury Stock / Buybacks)**: Se l'azienda riacquista le proprie azioni a prezzi attraenti, aumenta la percentuale di possesso degli azionisti esistenti senza richiedere loro un singolo dollaro aggiuntivo.
                """)

            with guide_tab3:
                st.markdown("""
                ### 💸 3. Rendiconto Finanziario (Cash Flow Statement)
                * **CapEx / Utile Netto < 25% (max 50%)**: Le aziende eccezionali richiedono pochissimo capitale per mantenere gli impianti (*Capital Light*), lasciando enormi risorse finanziarie libere.
                * **Owner Earnings (Utili del Proprietario)**: Formula di Buffett per il vero cash flow libero generato al netto del mantenimento dell'attività:
                  $$\\text{Owner Earnings} = \\text{Cash Flow Operativo} - \\text{CapEx}$$
                  Se gli *Owner Earnings* superano costantemente l'Utile Netto contabile, la qualità dei profitti è eccellente.
                * **Free Cash Flow Consistente**: Flussi di cassa operativi stabili e prevedibili nel tempo, non soggetti a brusche contrazioni cicliche.
                """)

            with guide_tab4:
                st.markdown("### 🧪 Esegui lo Scorecard di Buffett su un Ticker a scelta")
                b_ticker_input = st.text_input("Inserisci Ticker (es. KO, AAPL, MSFT, BAC, AXP):", value="KO", key="wb_guide_ticker_input").upper().strip()
                if b_ticker_input:
                    render_buffett_scorecard_ui(b_ticker_input)

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
            category_choice = st.radio(
                "Filtra per stile di investimento:",
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
                        data_1y = fetch_galaxy_history_fn(tuple(sorted(unique_tkrs)))

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
                    "perf": "29.80%", "size": "$315.4B",
                    "categories": ["🌟 Popular", "🏛️ Value Investors", "⏳ Long-Term"],
                    "holdings": [("AAPL", "Apple Inc.", "#000000"), ("AXP", "American Express", "#006fcf"), ("KO", "Coca-Cola", "#E30016")],
                    "more": 13
                },
                {
                    "name": "Michael Burry", "company": "Scion Asset Management",
                    "perf": "38.50%", "size": "$118.5M",
                    "categories": ["🌟 Popular", "📉 Contrarians / Short"],
                    "holdings": [("BABA", "Alibaba Group", "#FF6A00"), ("BIDU", "Baidu Inc.", "#2932E1"), ("JD", "JD.com", "#E1251B")],
                    "more": 5
                },
                {
                    "name": "Cathie Wood", "company": "ARK Invest",
                    "perf": "42.10%", "size": "$15.6B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("TSLA", "Tesla", "#E82127"), ("COIN", "Coinbase", "#0052FF"), ("ROKU", "Roku", "#662D91")],
                    "more": 9
                },
                {
                    "name": "Bill Ackman", "company": "Pershing Square",
                    "perf": "33.60%", "size": "$14.8B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🏛️ Value Investors"],
                    "holdings": [("HLT", "Hilton Worldwide", "#002F6C"), ("QSR", "Restaurant Brands", "#D52B1E"), ("CMG", "Chipotle", "#8B1E0F")],
                    "more": 5
                },
                {
                    "name": "David Tepper", "company": "Appaloosa Management",
                    "perf": "41.80%", "size": "$7.45B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("BABA", "Alibaba", "#FF6A00"), ("AMZN", "Amazon", "#FF9900"), ("MSFT", "Microsoft", "#00A4EF")],
                    "more": 8
                },
                {
                    "name": "Ray Dalio", "company": "Bridgewater Associates",
                    "perf": "18.20%", "size": "$24.80B",
                    "categories": ["🌟 Popular", "⏳ Long-Term"],
                    "holdings": [("IVV", "iShares Core S&P 500", "#000000"), ("IEMG", "iShares Emerging", "#008000"), ("GOOGL", "Alphabet", "#4285F4")],
                    "more": 10
                },
                {
                    "name": "Stanley Druckenmiller", "company": "Duquesne Family Office",
                    "perf": "47.50%", "size": "$3.95B",
                    "categories": ["🌟 Popular", "📈 Best Performance", "🚀 Growth Investors"],
                    "holdings": [("NTRA", "Natera", "#00A9E0"), ("COHR", "Coherent Corp.", "#F37021"), ("TSM", "Taiwan Semi", "#0066CC")],
                    "more": 7
                },
                {
                    "name": "Ken Griffin", "company": "Citadel Advisors",
                    "perf": "25.40%", "size": "$108.5B",
                    "categories": ["🌟 Popular", "📉 Contrarians / Short", "⏳ Long-Term"],
                    "holdings": [("SPY", "SPDR S&P 500", "#0B2664"), ("NVDA", "NVIDIA", "#76B900"), ("MSFT", "Microsoft", "#00A4EF")],
                    "more": 7
                },
                {
                    "name": "Carl Icahn", "company": "Icahn Enterprises",
                    "perf": "14.60%", "size": "$11.40B",
                    "categories": ["🌟 Popular", "🏛️ Value Investors", "📉 Contrarians / Short"],
                    "holdings": [("IEP", "Icahn Enterprises", "#000000"), ("CVI", "CVR Energy", "#006fcf"), ("UAN", "CVR Partners", "#008000")],
                    "more": 5
                }
            ]

            filtered_data = [inv for inv in super_data if category_choice in inv['categories']]

            if not filtered_data:
                st.warning("Nessun investitore trovato per questa categoria.")
            else:
                for i in range(0, len(filtered_data), 3):
                    cols = st.columns(3)
                    for j, inv in enumerate(filtered_data[i:i+3]):
                        with cols[j]:
                            holdings_html = ""
                            for h in inv['holdings']:
                                holdings_html += f'<div class="holding-row"><div class="holding-icon" style="background-color: {h[2]}; ">{h[0][0]}</div><div class="holding-name">{h[1]}</div></div>'

                            st.markdown(
                                f'<div class="inv-card"><div class="inv-name">{inv["name"]}</div><div class="inv-company">{inv["company"]}</div><div class="inv-perf">📈 Performance: {inv["perf"]} last year</div><div class="inv-port">{inv["size"]} portfolio</div>{holdings_html}</div>',
                                unsafe_allow_html=True
                            )

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
