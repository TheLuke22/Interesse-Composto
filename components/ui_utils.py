"""
Shared UI Utilities, KPI Cards, HTML Table Formatters, Plotly Theme Enhancers,
and Text/Numeric Formatting Helpers.
"""
from typing import Any
import streamlit as st
import pandas as pd
import numpy as np
from textblob import TextBlob

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


def render_custom_metric(label: str, value: str, delta: str = None, icon: str = None, is_positive: bool = None):
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

        formatted_price = f"${prezzo:,.2f}" if isinstance(prezzo, (int, float)) else str(prezzo)
        if isinstance(prezzo, str) and not prezzo.startswith('$') and prezzo != 'N/A':
            try:
                formatted_price = f"${float(prezzo):,.2f}"
            except Exception:
                pass

        if pe is None or str(pe) == 'nan':
            pe_html = '<span style="color: #8A929A;">N/A</span>'
        else:
            if pe < 15:
                pe_html = f'<span style="color: #00FF7F; font-weight: 700; background: rgba(0, 255, 127, 0.1); border: 1px solid rgba(0, 255, 127, 0.2); padding: 3px 8px; border-radius: 6px;">{pe:.2f}</span>'
            elif pe <= 25:
                pe_html = f'<span style="color: #FFAB00; font-weight: 700; background: rgba(255, 171, 0, 0.1); border: 1px solid rgba(255, 171, 0, 0.2); padding: 3px 8px; border-radius: 6px;">{pe:.2f}</span>'
            else:
                pe_html = f'<span style="color: #FF3B30; font-weight: 700; background: rgba(255, 59, 48, 0.1); border: 1px solid rgba(255, 59, 48, 0.2); padding: 3px 8px; border-radius: 6px;">{pe:.2f}</span>'

        div_html = f'<span style="color: #00f2fe; font-weight: 700;">{div:.2f}%</span>' if div > 0 else '<span style="color: #8A929A;">0.00%</span>'
        payout_html = f'<span style="color: #E2E8F0;">{payout:.1f}%</span>' if payout > 0 else '<span style="color: #8A929A;">0.0%</span>'
        eps_g_html = f'<span style="color: #00FF7F; font-weight: 600;">+{eps_g:.1f}%</span>' if eps_g > 0 else f'<span style="color: #FF3B30; font-weight: 600;">{eps_g:.1f}%</span>'
        net_inc_formatted = f"${net_inc/1000:.2f}B" if net_inc >= 1000 else f"${net_inc:.1f}M"
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
    clean_html = "\n".join([line.strip() for line in html.split("\n")])
    st.markdown(clean_html, unsafe_allow_html=True)


def format_large_numbers(value: Any, is_currency: bool = True) -> str:
    """Formatta numeri grandi in notazione M (Milioni), B (Miliardi), T (Trilioni)."""
    if value is None or str(value) == "nan" or value == "N/A":
        return "N/A"
    try:
        val = float(value)
    except (ValueError, TypeError):
        return str(value)

    prefix = "$" if is_currency else ""
    sign = "-" if val < 0 else ""
    abs_val = abs(val)

    if abs_val >= 1e12:
        return f"{sign}{prefix}{abs_val / 1e12:.2f}T"
    elif abs_val >= 1e9:
        return f"{sign}{prefix}{abs_val / 1e9:.2f}B"
    elif abs_val >= 1e6:
        return f"{sign}{prefix}{abs_val / 1e6:.2f}M"
    elif abs_val >= 1e3:
        return f"{sign}{prefix}{abs_val / 1e3:.2f}K"
    else:
        return f"{sign}{prefix}{abs_val:.2f}"


def format_perc(value: Any) -> str:
    """Formatta percentuali con gestione sicura dei valori nulli."""
    if value is None or str(value) == "nan" or value == "N/A":
        return "N/A"
    try:
        val = float(value)
        if abs(val) <= 1.0 and val != 0.0:
            val = val * 100.0
        return f"{val:+.2f}%"
    except (ValueError, TypeError):
        return str(value)


def calc_cagr(start_val: float, end_val: float, years: float) -> float:
    """Calcola il tasso di crescita annuo composto (CAGR)."""
    if start_val <= 0 or end_val <= 0 or years <= 0:
        return 0.0
    return ((end_val / start_val) ** (1.0 / years) - 1.0) * 100.0


def calc_risk_metrics(returns: pd.Series, rf_rate: float = 0.02) -> tuple[float, float]:
    """Calcola Sharpe Ratio e Max Drawdown annualizzati."""
    if len(returns) < 2:
        return 0.0, 0.0

    daily_rf = (1 + rf_rate) ** (1 / 252) - 1
    excess_ret = returns - daily_rf
    mean_ex = excess_ret.mean() * 252
    std_ret = returns.std() * np.sqrt(252)

    sharpe = mean_ex / std_ret if std_ret > 0 else 0.0

    cum_ret = (1 + returns).cumprod()
    peak = cum_ret.cummax()
    drawdown = (cum_ret - peak) / peak
    max_dd = drawdown.min() * 100.0 if not drawdown.empty else 0.0

    return sharpe, max_dd


def get_sentiment(text: str) -> str:
    """Classifica il sentiment di un testo finanziario usando TextBlob."""
    if not text:
        return "Neutro ⚪"
    try:
        analysis = TextBlob(str(text))
        polarity = analysis.sentiment.polarity
        if polarity > 0.15:
            return "Bullish 🟢"
        elif polarity < -0.15:
            return "Bearish 🔴"
        else:
            return "Neutro ⚪"
    except Exception:
        return "Neutro ⚪"
