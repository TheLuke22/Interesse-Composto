"""
Stock Screener UI Component:
Features quantitative multi-metric screening (P/E, Div Yield, Market Cap, Payout, EPS Growth, Margin),
concurrent multi-threaded scanning, premium styled table with direct ticker navigation,
and 3D K-Means AI clustering on financial DNA.
"""
import random
import concurrent.futures
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from components.ui_utils import render_premium_screener_table, WALL_STREET_QUOTES


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_screener_universe_raw(sp500_tickers_tuple, _fetch_stock_info_fn):
    """
    Extracts raw quantitative screening metrics for all S&P 500 tickers concurrently.
    Cached for 1 hour for sub-millisecond real-time query filtering.
    """
    def _safe_num(val):
        if val is None:
            return None
        try:
            if pd.isna(val):
                return None
        except Exception:
            pass
        return val if isinstance(val, (int, float)) else None

    def extract_single_ticker(tkr):
        try:
            tk_info = _fetch_stock_info_fn(tkr)
            if not tk_info:
                return None

            pe = _safe_num(tk_info.get('trailingPE'))
            div_rate = _safe_num(tk_info.get('dividendRate'))
            price = _safe_num(tk_info.get('currentPrice'))

            if div_rate is not None and div_rate > 0 and price is not None and price > 0:
                div_yield = (div_rate / price) * 100
            else:
                div_yield = _safe_num(tk_info.get('dividendYield'))
                if div_yield is not None:
                    if div_yield < 0.2:
                        div_yield = div_yield * 100
                else:
                    div_yield = 0.0

            mcap = _safe_num(tk_info.get('marketCap'))
            mcap_b = (mcap or 0) / 1e9

            eps_cagr = _safe_num(tk_info.get('epsGrowth5Y'))
            if eps_cagr is not None:
                eps_growth_val = eps_cagr
            else:
                eps_growth = _safe_num(tk_info.get('earningsGrowth'))
                if eps_growth is not None:
                    eps_growth_val = eps_growth * 100 if abs(eps_growth) <= 1.0 else eps_growth
                else:
                    eps_growth_q = _safe_num(tk_info.get('earningsQuarterlyGrowth'))
                    if eps_growth_q is not None:
                        eps_growth_val = eps_growth_q * 100 if abs(eps_growth_q) <= 1.0 else eps_growth_q
                    else:
                        eps_growth_val = 0.0

            payout = _safe_num(tk_info.get('payoutRatio'))
            payout_val = (payout * 100) if payout is not None else 0.0

            if div_yield == 0:
                div_growth_val = 0.0
            else:
                five_yr_avg = _safe_num(tk_info.get('fiveYearAvgDividendYield'))
                if five_yr_avg is not None:
                    div_growth_val = five_yr_avg if five_yr_avg > 1.0 else five_yr_avg * 100
                else:
                    div_growth_val = eps_growth_val * 0.8

            net_income = _safe_num(tk_info.get('netIncomeToCommon')) or _safe_num(tk_info.get('netIncome'))
            net_income_m = (net_income / 1e6) if net_income is not None else 0.0

            profit_margin = _safe_num(tk_info.get('profitMargins'))
            profit_margin_val = (profit_margin * 100) if profit_margin is not None else 0.0

            return {
                "Ticker": tkr,
                "Azienda": tk_info.get('shortName', tkr),
                "P/E": round(pe, 2) if pe is not None else None,
                "Div Yield %": round(div_yield, 2),
                "Market Cap (B)": round(mcap_b, 2),
                "Payout Ratio %": round(payout_val, 2),
                "EPS Growth %": round(eps_growth_val, 2),
                "Div Growth %": round(div_growth_val, 2),
                "Net Income (M)": round(net_income_m, 2),
                "Profit Margin %": round(profit_margin_val, 2),
                "Prezzo": tk_info.get('currentPrice', 'N/A')
            }
        except Exception:
            return None

    with concurrent.futures.ThreadPoolExecutor(max_workers=35) as executor:
        items = list(executor.map(extract_single_ticker, list(sp500_tickers_tuple)))

    valid_items = [itm for itm in items if itm is not None]
    return pd.DataFrame(valid_items)


def render_stock_screener_ui(get_sp500_tickers_fn, fetch_stock_info_fn):
    """
    Renders the S&P 500 Quantitative Stock Screener.
    """
    st.title("🔍 S&P 500 Stock Screener")
    st.write("Esplora l'intero **S&P 500** alla ricerca di opportunità Value e Dividend.")
    st.divider()

    try:
        sp500_tickers = get_sp500_tickers_fn()
    except Exception:
        st.error("Impossibile caricare S&P 500.")
        sp500_tickers = []

    st.markdown("#### ⚙️ Parametri di Screening Quantitativo")

    col_row1 = st.columns(4)
    max_pe = col_row1[0].number_input(
        "P/E Ratio Massimo", value=25.0, help="Filtra aziende con P/E inferiore o uguale a questa soglia (Utile/Value)."
    )
    min_div = col_row1[1].number_input(
        "Dividend Yield Minimo (%)", value=2.0, help="Soglia minima di rendimento da dividendo annuale."
    )
    min_cap = col_row1[2].number_input(
        "Market Cap Min. (Bld $)", value=50, help="Capitalizzazione di mercato minima in miliardi di dollari."
    )
    max_payout = col_row1[3].number_input(
        "Payout Ratio Massimo (%)", value=70.0, help="Soglia massima di utili destinati ai dividendi (sostenibilità)."
    )

    col_row2 = st.columns(4)
    min_eps_growth = col_row2[0].number_input(
        "EPS Growth 5A CAGR Min. (%)", value=5.0,
        help="Aumento annualizzato previsto degli utili per azione (EPS) nei prossimi 5 anni."
    )
    min_div_growth = col_row2[1].number_input(
        "Div Growth 5A CAGR Min. (%)", value=4.0, help="Crescita annualizzata minima stimata dei dividendi."
    )
    min_net_income = col_row2[2].number_input(
        "Net Income Min. (Mln $)", value=500.0, help="Utile netto minimo cumulato in milioni di dollari."
    )
    min_profit_margin = col_row2[3].number_input(
        "Net Profit Margin Min. (%)", value=10.0, help="Margine di profitto netto minimo (%) dell'azienda."
    )

    if st.button("🚀 Esegui Screen", type="primary"):
        if sp500_tickers:
            with st.spinner(f"Scansione e filtraggio istantaneo S&P 500... | '{random.choice(WALL_STREET_QUOTES)}'"):
                df_universe = fetch_screener_universe_raw(tuple(sp500_tickers), fetch_stock_info_fn)

                if not df_universe.empty:
                    # Vectorized sub-millisecond filtering
                    pe_condition = df_universe['P/E'].notna() & (df_universe['P/E'] <= max_pe)
                    div_condition = df_universe['Div Yield %'] >= min_div
                    mcap_condition = df_universe['Market Cap (B)'] >= min_cap
                    payout_condition = df_universe['Payout Ratio %'] <= max_payout
                    eps_condition = df_universe['EPS Growth %'] >= min_eps_growth
                    div_g_condition = df_universe['Div Growth %'] >= min_div_growth
                    net_inc_condition = df_universe['Net Income (M)'] >= min_net_income
                    margin_condition = df_universe['Profit Margin %'] >= min_profit_margin

                    mask = (
                        pe_condition & div_condition & mcap_condition & payout_condition &
                        eps_condition & div_g_condition & net_inc_condition & margin_condition
                    )

                    df_screen = df_universe[mask].copy().sort_values(by="Div Yield %", ascending=False)
                    screener_res = df_screen.to_dict('records')
                else:
                    df_screen = pd.DataFrame()
                    screener_res = []

                if screener_res:
                    st.success(f"Trovate {len(screener_res)} aziende che rispettano i tuoi parametri istituzionali.")
                    render_premium_screener_table(df_screen)

                    info_note_html = """
                    <div style="background: rgba(0, 242, 254, 0.05); border: 1px dashed rgba(0, 242, 254, 0.2); padding: 12px 18px; border-radius: 8px; margin-top: 15px; margin-bottom: 25px; display: flex; align-items: center; gap: 10px;">
                        <span style="font-size: 18px;">💡</span>
                        <span style="color: #cbd5e1; font-size: 13.5px; font-weight: 500;">
                            <b>Analisi Diretta:</b> Clicca sul <span style="background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%); color: white; font-weight: 700; padding: 2px 6px; border-radius: 4px; font-size: 11px;">TICKER</span> di qualsiasi azienda per analizzarla istantaneamente nella sezione <b>Stock Tracker</b>!
                        </span>
                    </div>
                    """
                    clean_info_note = "\n".join([line.strip() for line in info_note_html.split("\n")])
                    st.markdown(clean_info_note, unsafe_allow_html=True)

                    if len(df_screen) >= 4:
                        st.subheader("🧲 K-Means AI Clustering (S&P 500)")
                        st.write("Aggreghiamo matematicamente queste aziende in cluster spaziali in base al loro DNA finanziario (P/E, Dividendo, Grandezza).")
                        with st.spinner("Addestramento modello ML K-Means in puro NumPy..."):
                            data = df_screen[['P/E', 'Div Yield %', 'Market Cap (B)']].values
                            std_devs = np.std(data, axis=0)
                            std_devs[std_devs == 0] = 1
                            data_norm = (data - np.mean(data, axis=0)) / std_devs

                            k = min(4, len(df_screen))
                            np.random.seed(42)
                            centroids = data_norm[np.random.choice(data_norm.shape[0], k, replace=False)]

                            for _ in range(100):
                                distances = np.sqrt(((data_norm - centroids[:, np.newaxis])**2).sum(axis=2))
                                labels = np.argmin(distances, axis=0)
                                new_centroids = np.array([data_norm[labels == i].mean(axis=0) if len(data_norm[labels == i]) > 0 else centroids[i] for i in range(k)])
                                if np.allclose(centroids, new_centroids):
                                    break
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
