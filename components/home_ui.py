"""
Market Dashboard / Home Page UI Component:
Features live Watchlist with glowing KPI cards, S&P 500 Heavyweights ranking table,
real-time price updates, and market heatmap treemap.
"""
import random
import streamlit as st
import pandas as pd
import plotly.express as px
from components.ui_utils import WALL_STREET_QUOTES

TOP_25_SP500_TICKERS = [
    "NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "META", "BRK-B", "TSLA", "AVGO", "WMT",
    "LLY", "JPM", "V", "UNH", "XOM", "MA", "PG", "JNJ", "COST", "HD", "ABBV", "MRK",
    "BAC", "CRM", "NFLX"
]

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


def render_home_ui(fetch_home_data_fn, fetch_watchlist_prices_fn, save_watchlist_fn, get_full_sp500_list_fn=None, get_sp500_sectors_fn=None):
    """
    Renders the institutional Market Dashboard / Home view.
    """
    st.title("🏠 Market Dashboard")
    st.markdown("<p style='color: #8A929A; font-size: 16px; margin-bottom:20px;'>Live Snapshot of the S&P 500 Heavyweights</p>", unsafe_allow_html=True)

    # --- WATCHLIST SECTION ---
    with st.expander("⭐ My Watchlist", expanded=bool(st.session_state.get('watchlist'))):
        wl_c1, wl_c2, wl_c3 = st.columns([3, 1, 1])
        with wl_c1:
            new_watch_ticker = st.text_input(
                "Ticker", key="wl_input", label_visibility="collapsed",
                placeholder="Add ticker to watchlist (e.g. NVDA)..."
            ).upper().strip()
        with wl_c2:
            if st.button("➕ Add", key="wl_add_btn", use_container_width=True) and new_watch_ticker:
                if new_watch_ticker not in st.session_state['watchlist']:
                    st.session_state['watchlist'].append(new_watch_ticker)
                    save_watchlist_fn(st.session_state['watchlist'])
                    st.toast(f"{new_watch_ticker} added to watchlist!", icon="⭐")
                    st.rerun()
                else:
                    st.toast(f"{new_watch_ticker} is already in your watchlist", icon="⚠️")
        with wl_c3:
            if st.button("🗑️ Clear", key="wl_clear_btn", use_container_width=True) and st.session_state['watchlist']:
                st.session_state['watchlist'] = []
                save_watchlist_fn([])
                st.rerun()

        if st.session_state.get('watchlist'):
            wl_prices = fetch_watchlist_prices_fn(tuple(st.session_state['watchlist']))
            if wl_prices:
                wl_html = '<div style="display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px;">'
                for wl_tk in st.session_state['watchlist']:
                    if wl_tk in wl_prices:
                        wl_curr, wl_prev = wl_prices[wl_tk]
                        wl_chg = ((wl_curr - wl_prev) / wl_prev) * 100 if wl_prev != 0 else 0
                        wl_color = "#22c55e" if wl_chg >= 0 else "#ef4444"
                        wl_sign = "+" if wl_chg >= 0 else ""
                        wl_arrow = "▲" if wl_chg >= 0 else "▼"
                        wl_html += (
                            f'<div class="transition-all" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); '
                            f'border-left: 3px solid {wl_color}; border-radius: 12px; padding: 14px 20px; min-width: 170px; flex: 1; max-width: 220px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">'
                            f'<a class="screener-link" href="?ticker={wl_tk}" target="_self"><span class="ticker-badge" style="margin-bottom: 6px;">{wl_tk}</span></a>'
                            f'<div class="num-value" style="font-size: 20px; font-weight: 700; margin-top: 6px; color: #ffffff;">${wl_curr:,.2f}</div>'
                            f'<div class="num-value" style="color: {wl_color}; font-weight: 600; font-size: 14px; margin-top: 2px;">{wl_arrow} {wl_sign}{wl_chg:.2f}%</div></div>'
                        )
                    else:
                        wl_html += (
                            f'<div class="transition-all" style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.06); '
                            f'border-radius: 12px; padding: 14px 20px; min-width: 170px; flex: 1; max-width: 220px; box-shadow: 0 4px 15px rgba(0,0,0,0.1);">'
                            f'<a class="screener-link" href="?ticker={wl_tk}" target="_self"><span class="ticker-badge" style="margin-bottom: 6px;">{wl_tk}</span></a>'
                            f'<div style="font-size: 14px; color: #64748b; margin-top: 6px;">Data unavailable</div></div>'
                        )
                wl_html += '</div>'
                st.markdown(wl_html, unsafe_allow_html=True)

            # Remove buttons for each ticker
            st.write("")
            max_wl_cols = min(len(st.session_state['watchlist']), 8)
            if max_wl_cols > 0:
                wl_rem_cols = st.columns(max_wl_cols)
                for wi, wl_tk in enumerate(st.session_state['watchlist'][:8]):
                    with wl_rem_cols[wi]:
                        if st.button(f"✕ {wl_tk}", key=f"wl_rem_{wl_tk}", use_container_width=True):
                            st.session_state['watchlist'].remove(wl_tk)
                            save_watchlist_fn(st.session_state['watchlist'])
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

    if 'show_all_sp500' not in st.session_state:
        st.session_state.show_all_sp500 = False
    if 'home_filter' not in st.session_state:
        st.session_state.home_filter = "S&P 500"

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

    if st.session_state.show_all_sp500 and get_full_sp500_list_fn:
        with st.spinner(f"Scaricamento composizione intero S&P 500... | '{random.choice(WALL_STREET_QUOTES)}'"):
            try:
                tks_to_fetch = get_full_sp500_list_fn()
            except Exception:
                st.error("Wikipedia Data non disponibile.")

    with st.spinner(f"Sincronizzazione dati live... | '{random.choice(WALL_STREET_QUOTES)}'"):
        df_display = fetch_home_data_fn(tuple(tks_to_fetch))

    # Applica filtro Gainers/Losers
    if not df_display.empty:
        if st.session_state.home_filter == "Gainers":
            df_display = df_display[df_display['Change'] > 0].sort_values(by='Change', ascending=False)
        elif st.session_state.home_filter == "Losers":
            df_display = df_display[df_display['Change'] < 0].sort_values(by='Change', ascending=True)

    # Market Summary bar
    if not df_display.empty:
        avg_change = df_display['Change'].mean()
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

        try:
            wiki_sectors = get_sp500_sectors_fn() if get_sp500_sectors_fn else {}
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
