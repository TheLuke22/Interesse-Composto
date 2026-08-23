"""
Portfolio Intelligence UI Component:
Features complete position management, Google Sheets real-time sync, backup import/export,
11-horizon performance benchmark comparison vs VOO / S&P 500 with Alpha calculation,
Markowitz Efficient Frontier & 3D Risk/Return Constellation, Correlation Matrix,
Projected Dividend Calendar, Yield on Cost (YoC), and Historical Stress Testing Simulations.
"""
import os
import json
import concurrent.futures
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np
import yfinance as yf
from scipy.optimize import minimize
from analytics.portfolio_analytics import calculate_dividend_projections, simulate_portfolio_stress_test
from components.ui_utils import format_large_numbers


def render_portfolio_dividend_suite(holdings: list, current_prices: dict, dividend_yields: dict):
    """
    Renders the Dividend Calendar and Yield on Cost breakdown.
    """
    st.subheader("❄️ Dividend Income Calendar & Yield on Cost (YoC)")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px; margin-bottom: 20px;'>"
        "Track forward dividend cash flow and compare current yields against your purchase cost basis."
        "</p>",
        unsafe_allow_html=True
    )

    div_res = calculate_dividend_projections(holdings, current_prices, dividend_yields)

    if div_res["total_market_val"] <= 0 or div_res["df_holdings"].empty:
        st.info("No active holdings found in your portfolio.")
        return

    # KPI Metrics
    dk1, dk2, dk3, dk4 = st.columns(4)
    with dk1:
        st.metric("💵 Projected Annual Dividends", f"${div_res['total_annual_dividend']:,.2f}")
    with dk2:
        st.metric("🗓️ Monthly Average Cash Flow", f"${div_res['total_annual_dividend']/12.0:,.2f}")
    with dk3:
        st.metric("📈 Portfolio Forward Yield", f"{div_res['weighted_forward_yield']:.2f}%")
    with dk4:
        st.metric("🎯 Portfolio Yield on Cost", f"{div_res['weighted_yoc']:.2f}%", 
                  delta=f"{div_res['weighted_yoc'] - div_res['weighted_forward_yield']:+.2f}% vs Market",
                  delta_color="normal")

    st.write("")
    div_c1, div_c2 = st.columns([1, 2])
    with div_c1:
        st.markdown("##### 📅 Estimated Monthly Cashflow Distribution")
        df_m = div_res["df_monthly"]
        fig_bar = go.Figure(data=[go.Bar(
            x=df_m["Month"],
            y=df_m["Projected Payout ($)"],
            marker_color="#00f2fe",
            text=[f"${v:,.0f}" if v > 0 else "" for v in df_m["Projected Payout ($)"]],
            textposition="outside"
        )])
        fig_bar.update_layout(
            height=280,
            margin=dict(l=10, r=10, t=20, b=10),
            yaxis_title="Payout ($)",
            template="plotly_dark"
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    with div_c2:
        st.markdown("##### 📋 Holdings Dividend Breakdown & YoC")
        st.dataframe(div_res["df_holdings"], use_container_width=True, hide_index=True)


def render_portfolio_stress_test_suite(holdings_df: pd.DataFrame, total_portfolio_value: float):
    """
    Renders the Historical Crisis Simulation & Macro Stress Test.
    """
    st.subheader("⚡ Historical Crisis & Macro Stress Testing")
    st.markdown(
        "<p style='color: #8A929A; font-size: 14px; margin-bottom: 20px;'>"
        "Simulate how your current portfolio allocation would have performed during major historical market crashes."
        "</p>",
        unsafe_allow_html=True
    )

    stress_res = simulate_portfolio_stress_test(holdings_df, total_portfolio_value)
    scenarios = stress_res.get("scenarios", [])

    if not scenarios:
        st.info("Add holdings to your portfolio to run stress test simulations.")
        return

    cols = st.columns(2)
    for idx, sc in enumerate(scenarios):
        col = cols[idx % 2]
        with col:
            loss_pct = sc["Simulated Portfolio Loss (%)"]
            loss_dollars = sc["Estimated Loss ($)"]
            post_val = sc["Post-Crash Portfolio Value ($)"]
            resilience = sc["Relative Resilience"]
            bench_loss = sc["S&P 500 Benchmark Loss"]

            st.markdown(f"""
            <div style="background: rgba(255,255,255,0.03); border: 1px solid rgba(255,255,255,0.08); border-radius: 14px; padding: 18px; margin-bottom: 15px;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <h4 style="margin: 0; color: #FFFFFF; font-size: 16px;">{sc['Scenario']}</h4>
                    <span style="font-size: 12px; font-weight: 700; color: #94a3b8;">Benchmark: {bench_loss}</span>
                </div>
                <p style="color: #94a3b8; font-size: 12px; margin-bottom: 12px;">{sc['Description']}</p>
                <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px; text-align: center;">
                    <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.2); border-radius: 8px; padding: 8px;">
                        <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase;">Simulated Loss</div>
                        <div style="color: #ef4444; font-size: 16px; font-weight: 800;">{loss_pct:+.1f}%</div>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 8px;">
                        <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase;">Est. Dollar Loss</div>
                        <div style="color: #f87171; font-size: 16px; font-weight: 800;">-${loss_dollars:,.0f}</div>
                    </div>
                    <div style="background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 8px; padding: 8px;">
                        <div style="color: #94a3b8; font-size: 10px; text-transform: uppercase;">Post-Crash Value</div>
                        <div style="color: #00f2fe; font-size: 16px; font-weight: 800;">${post_val:,.0f}</div>
                    </div>
                </div>
                <div style="margin-top: 10px; font-size: 12px; font-weight: 600; color: #10b981;">{resilience}</div>
            </div>
            """, unsafe_allow_html=True)


def render_my_portfolio_ui(
    save_portfolio_fn,
    get_batch_prices_fn,
    fetch_stock_info_fn,
    fetch_portfolio_vs_voo_history_fn,
    fetch_portfolio_close_history_fn,
    push_portfolio_to_gsheets_fn,
    analyze_portfolio_diversification_fn
):
    """
    Renders the complete My Portfolio suite.
    """
    st.title("📁 Institutional Portfolio Manager")
    st.write("Gestisci le tue posizioni e visualizza la diversificazione del tuo capitale.")
    st.divider()

    # --- INPUT PER AGGIUNGERE TITOLI ---
    with st.expander("➕ Aggiungi Nuova Posizione", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        new_ticker = c1.text_input("Ticker (es. AAPL)").upper()
        new_shares = c2.number_input("Quantità (Azioni/Quote)", min_value=0.0, step=0.1)
        new_price = c3.number_input(
            "Prezzo di Acquisto ($) [opzionale]", min_value=0.0, step=1.0, value=0.0,
            help="Se lasciato a 0.0, userà il prezzo attuale di mercato"
        )
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
                    save_portfolio_fn(st.session_state['portfolio'])
                    st.toast(f"{new_ticker} aggiunto con successo!", icon="✅")
                    st.rerun()
            except Exception:
                st.error("Errore imprevisto durante la validazione. Riprova.")

    # --- BACKUP / RECOVERY ---
    with st.expander("💾 Salva / Carica Backup Portafoglio", expanded=False):
        b_col1, b_col2 = st.columns(2)

        with b_col1:
            st.markdown("#### Esporta")
            st.write("Scarica un file di backup per salvare le tue posizioni sul tuo computer.")
            portfolio_str = json.dumps(st.session_state.get('portfolio', []), indent=2)
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
            uploaded_file = st.file_uploader("Scegli il file di backup (.json, .csv)", type=["json", "csv"], key="uploader_backup")
            if uploaded_file is not None:
                try:
                    file_extension = uploaded_file.name.split('.')[-1].lower()
                    imported_portfolio = []

                    if file_extension == 'json':
                        imported_portfolio = json.load(uploaded_file)
                        if not isinstance(imported_portfolio, list):
                            st.error("Formato file non valido. Deve essere una lista JSON.")
                            imported_portfolio = []
                    elif file_extension == 'csv':
                        df_csv = pd.read_csv(uploaded_file)
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
                                    try:
                                        sh = float(row[shares_col]) if pd.notna(row[shares_col]) else 0.0
                                    except Exception:
                                        sh = 0.0
                                    try:
                                        pr = float(row[price_col]) if price_col and pd.notna(row[price_col]) else 0.0
                                    except Exception:
                                        pr = 0.0
                                    imported_portfolio.append({
                                        "ticker": tk,
                                        "shares": sh,
                                        "purchase_price": pr
                                    })
                        else:
                            st.error("Colonne Ticker o Quantità non trovate nel file CSV.")

                    if isinstance(imported_portfolio, list) and len(imported_portfolio) > 0:
                        st.session_state['portfolio'] = imported_portfolio
                        save_portfolio_fn(imported_portfolio)
                        st.toast("Portafoglio importato con successo!", icon="✅")
                        st.rerun()
                    else:
                        st.error("Nessun dato valido trovato nel file.")
                except Exception as e:
                    st.error(f"Errore durante l'importazione: {e}")

    # --- GOOGLE SHEETS SYNC ---
    with st.expander("📊 Sincronizzazione Google Sheets", expanded=False):
        st.markdown("### 🔄 Sincronizza il tuo portafoglio in tempo reale")
        st.write("Collega un foglio Google Sheets per salvare e sincronizzare automaticamente il tuo portafoglio su tutti i tuoi dispositivi.")

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
                                    save_portfolio_fn(imported_portfolio)
                                    st.toast("Dati letti da Google Sheets con successo!", icon="✅")
                                    st.rerun()
                                else:
                                    st.error("Dati ricevuti non validi. Verifica l'Apps Script.")
                            else:
                                st.error(f"Errore di connessione: HTTP {res.status_code}")
                        except Exception as e:
                            st.error(f"Errore durante la lettura: {e}")
            with c_s2:
                if st.button("📤 Invia a Google Sheets", key="btn_write_gsheets"):
                    with st.spinner("Invio dati in corso a Google Sheets..."):
                        try:
                            push_portfolio_to_gsheets_fn(st.session_state['portfolio'])
                            st.toast("Dati inviati a Google Sheets con successo!", icon="✅")
                        except Exception as e:
                            st.error(f"Errore durante l'invio: {e}")

            auto_sync = st.checkbox("Sincronizzazione automatica ad ogni modifica", value=True,
                                    help="Se attivo, ogni aggiunta, modifica o rimozione di titoli sul sito salverà automaticamente sul tuo Google Sheets.")
            st.session_state['gsheets_auto_sync'] = auto_sync
            st.session_state['gsheets_url'] = gsheets_url

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
            5. Configura così: **Web App**, **Esegui come: Tu**, **Chi ha accesso: Chiunque**.
            6. Clicca su **Distribuisci**, autorizza l'accesso e copia l'**URL della Web App**.
            7. Incolla quell'URL nel campo di testo qui sopra!
            """)

    # --- GESTIONE / RIMOZIONE POSIZIONI ---
    if st.session_state.get('portfolio'):
        with st.expander("⚙️ Gestisci / Rimuovi Posizione", expanded=False):
            position_options = [
                f"{i+1}. {item['ticker']} ({item['shares']} quote)"
                for i, item in enumerate(st.session_state['portfolio'])
            ]
            selected_pos = st.selectbox("Seleziona una posizione da gestire", options=position_options)

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
                        save_portfolio_fn(st.session_state['portfolio'])
                        st.toast(f"Posizione {current_item['ticker']} aggiornata con successo!", icon="✅")
                        st.rerun()

                with m2:
                    st.write(" ")
                    st.write(" ")
                    if st.button("Rimuovi Posizione", type="primary", key=f"btn_remove_{selected_idx}"):
                        removed_item = st.session_state['portfolio'].pop(selected_idx)
                        save_portfolio_fn(st.session_state['portfolio'])
                        st.toast(f"{removed_item['ticker']} rimosso con successo!", icon="🗑️")
                        st.rerun()

    # --- VISUALIZZAZIONE PORTAFOGLIO ---
    if st.session_state.get('portfolio'):
        st.subheader("Le tue posizioni")

        tickers = [item['ticker'] for item in st.session_state['portfolio']]

        with st.spinner("Aggiornamento prezzi e dividendi batch..."):
            prices_dict = get_batch_prices_fn(list(set(tickers)))

            stock_infos = {}
            unique_tks = list(set(tickers))
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(12, max(len(unique_tks), 1))) as executor:
                future_to_tk = {executor.submit(fetch_stock_info_fn, tk): tk for tk in unique_tks}
                for future in concurrent.futures.as_completed(future_to_tk):
                    tk = future_to_tk[future]
                    try:
                        stock_infos[tk] = future.result()
                    except Exception:
                        stock_infos[tk] = None

            portfolio_data = []
            total_portfolio_value = 0.0
            total_portfolio_cost = 0.0
            total_trailing_dividends = 0.0
            total_forward_dividends = 0.0

            for item in st.session_state['portfolio']:
                ticker = item['ticker']
                try:
                    shares = float(item.get('shares', 0.0))
                except Exception:
                    shares = 0.0
                if shares is None or pd.isna(shares):
                    shares = 0.0

                try:
                    purchase_price = float(item.get('purchase_price', 0.0))
                except Exception:
                    purchase_price = 0.0
                if purchase_price is None or pd.isna(purchase_price):
                    purchase_price = 0.0

                current_price = prices_dict.get(ticker, 0.0)
                if isinstance(current_price, pd.Series):
                    current_price = current_price.iloc[0]

                if current_price is None or pd.isna(current_price):
                    current_price = 0.0
                else:
                    try:
                        current_price = float(current_price)
                    except Exception:
                        current_price = 0.0

                if purchase_price == 0.0:
                    purchase_price = current_price

                current_value = shares * current_price
                total_portfolio_value += current_value
                total_portfolio_cost += shares * purchase_price

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

                yoc = 0.0
                yoc_fwd = 0.0
                if purchase_price > 0.0:
                    yoc = (trailing_div_rate / purchase_price) * 100
                    yoc_fwd = (forward_div_rate / purchase_price) * 100

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

        portfolio_yoc = 0.0
        portfolio_yoc_fwd = 0.0
        if total_portfolio_cost > 0.0:
            portfolio_yoc = (total_trailing_dividends / total_portfolio_cost) * 100
            portfolio_yoc_fwd = (total_forward_dividends / total_portfolio_cost) * 100

        kpi_c1, kpi_c2, kpi_c3 = st.columns(3)
        kpi_c1.metric("Total Assets Under Management (AUM)", format_large_numbers(total_portfolio_value))
        kpi_c2.metric("Portfolio Yield on Cost (YOC)", f"{portfolio_yoc:.2f}%" if total_portfolio_cost > 0.0 else "0.00%")
        kpi_c3.metric("Portfolio YOC (FWD)", f"{portfolio_yoc_fwd:.2f}%" if total_portfolio_cost > 0.0 else "0.00%")

        st.write("")
        kpi_d1, kpi_d2, kpi_d3 = st.columns(3)
        kpi_d1.metric("Total Portfolio Cost", format_large_numbers(total_portfolio_cost))
        kpi_d2.metric("Annual Dividend Income (TTM)", f"${total_trailing_dividends:,.2f}")
        kpi_d3.metric("Annual Dividend Income (FWD)", f"${total_forward_dividends:,.2f}")

        # --- BENCHMARK COMPARISON VS VOO (S&P 500) ---
        st.divider()
        st.subheader("⚔️ Benchmark Performance: Portafoglio vs VOO (S&P 500)")
        st.write("Confronta il rendimento storico del tuo portafoglio rispetto all'ETF **Vanguard S&P 500 (VOO)** nei vari orizzonti temporali.")

        portfolio_tickers_tuple = tuple(item['ticker'] for item in st.session_state['portfolio'])
        history_df = fetch_portfolio_vs_voo_history_fn(portfolio_tickers_tuple)

        if not history_df.empty and 'VOO' in history_df.columns:
            portfolio_val_series = pd.Series(0.0, index=history_df.index)
            for item in st.session_state['portfolio']:
                tk = str(item.get('ticker', '')).strip().upper()
                try:
                    sh = float(item.get('shares', 0.0))
                except Exception:
                    sh = 0.0
                if tk in history_df.columns:
                    portfolio_val_series += history_df[tk] * sh

            bench_df = pd.DataFrame({
                'Portafoglio': portfolio_val_series,
                'VOO': history_df['VOO']
            }, index=history_df.index)

            last_date = bench_df.index[-1]

            timeframes_cfg = [
                ("1 Giorno", "1d", lambda d: d - pd.Timedelta(days=1)),
                ("5 Giorni", "5d", lambda d: d - pd.Timedelta(days=5)),
                ("1 Settimana", "1w", lambda d: d - pd.Timedelta(days=7)),
                ("1 Mese", "1m", lambda d: d - pd.DateOffset(months=1)),
                ("3 Mesi", "3m", lambda d: d - pd.DateOffset(months=3)),
                ("6 Mesi", "6m", lambda d: d - pd.DateOffset(months=6)),
                ("1 Anno", "1y", lambda d: d - pd.DateOffset(years=1)),
                ("2 Anni", "2y", lambda d: d - pd.DateOffset(years=2)),
                ("3 Anni", "3y", lambda d: d - pd.DateOffset(years=3)),
                ("4 Anni", "4y", lambda d: d - pd.DateOffset(years=4)),
                ("5 Anni", "5y", lambda d: d - pd.DateOffset(years=5)),
            ]

            results = []
            for label, code, date_fn in timeframes_cfg:
                if label == "1 Giorno" and len(bench_df) >= 2:
                    start_date = bench_df.index[-2]
                elif label == "5 Giorni" and len(bench_df) >= 6:
                    start_date = bench_df.index[-6]
                else:
                    target_date = date_fn(last_date)
                    sub = bench_df.loc[bench_df.index <= target_date]
                    if not sub.empty:
                        start_date = sub.index[-1]
                    else:
                        start_date = bench_df.index[0]

                p_start = float(bench_df.loc[start_date, 'Portafoglio'])
                p_end = float(bench_df.loc[last_date, 'Portafoglio'])
                p_ret = ((p_end / p_start) - 1.0) * 100.0 if p_start > 0 else 0.0

                v_start = float(bench_df.loc[start_date, 'VOO'])
                v_end = float(bench_df.loc[last_date, 'VOO'])
                v_ret = ((v_end / v_start) - 1.0) * 100.0 if v_start > 0 else 0.0

                alpha = p_ret - v_ret

                if abs(alpha) < 0.01:
                    winner = "➖ Parità"
                elif alpha > 0:
                    winner = "🟢 Portafoglio"
                else:
                    winner = "🔵 VOO"

                results.append({
                    "Orizzonte": label,
                    "Rendimento Portafoglio (%)": p_ret,
                    "Rendimento VOO (%)": v_ret,
                    "Alpha / Diff (%)": alpha,
                    "Esito": winner,
                    "_start_date": start_date
                })

            df_results = pd.DataFrame(results)

            wins_portfolio = sum(1 for r in results if r["Alpha / Diff (%)"] > 0.01)
            alpha_1y = next((r["Alpha / Diff (%)"] for r in results if r["Orizzonte"] == "1 Anno"), 0.0)
            alpha_5y = next((r["Alpha / Diff (%)"] for r in results if r["Orizzonte"] == "5 Anni"), 0.0)

            col_b1, col_b2, col_b3 = st.columns(3)
            col_b1.metric("Orizzonti Vinti vs VOO", f"{wins_portfolio} / 11", help="Numero di timeframe in cui il tuo portafoglio supera VOO")
            col_b2.metric("Alpha 1 Anno", f"{alpha_1y:+.2f}%", delta=f"{alpha_1y:+.2f}%")
            col_b3.metric("Alpha 5 Anni", f"{alpha_5y:+.2f}%", delta=f"{alpha_5y:+.2f}%")

            st.write("")
            st.markdown("#### 📋 Tabella Comparativa Performance (11 Orizzonti)")

            df_display = df_results[["Orizzonte", "Rendimento Portafoglio (%)", "Rendimento VOO (%)", "Alpha / Diff (%)", "Esito"]].copy()

            st.dataframe(
                df_display,
                column_config={
                    "Orizzonte": st.column_config.TextColumn("Orizzonte Temporale"),
                    "Rendimento Portafoglio (%)": st.column_config.NumberColumn("Portafoglio (%)", format="%+.2f%%"),
                    "Rendimento VOO (%)": st.column_config.NumberColumn("VOO (%)", format="%+.2f%%"),
                    "Alpha / Diff (%)": st.column_config.NumberColumn("Alpha / Diff (%)", format="%+.2f%%"),
                    "Esito": st.column_config.TextColumn("Esito Benchmark")
                },
                use_container_width=True,
                hide_index=True
            )

            st.write("")
            st.markdown("#### 📈 Grafico Comparativo Interattivo")

            selected_tf = st.selectbox(
                "Seleziona l'orizzonte temporale da visualizzare nel grafico:",
                options=[r["Orizzonte"] for r in results] + ["Tutto (5 Anni)"],
                index=6,
                key="portfolio_voo_tf_select"
            )

            if selected_tf == "Tutto (5 Anni)":
                tf_start_date = bench_df.index[0]
            else:
                tf_start_date = next((r["_start_date"] for r in results if r["Orizzonte"] == selected_tf), bench_df.index[0])

            sliced_bench = bench_df.loc[bench_df.index >= tf_start_date].copy()
            if not sliced_bench.empty and len(sliced_bench) >= 1:
                norm_port = (sliced_bench['Portafoglio'] / sliced_bench['Portafoglio'].iloc[0]) * 100.0
                norm_voo = (sliced_bench['VOO'] / sliced_bench['VOO'].iloc[0]) * 100.0

                fig_comp = go.Figure()
                fig_comp.add_trace(go.Scatter(
                    x=sliced_bench.index,
                    y=norm_port,
                    name="Il tuo Portafoglio",
                    line=dict(color="#27AE60", width=2.5)
                ))
                fig_comp.add_trace(go.Scatter(
                    x=sliced_bench.index,
                    y=norm_voo,
                    name="VOO (S&P 500)",
                    line=dict(color="#2E86C1", width=2.5, dash="dash")
                ))

                fig_comp.update_layout(
                    title=f"Crescita Comparativa di $100 Investiti - Orizzonte: {selected_tf}",
                    yaxis_title="Valore Normalizzato ($)",
                    hovermode="x unified",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                st.plotly_chart(fig_comp, use_container_width=True)

            st.write("")
            st.markdown("#### 📊 Sovraperformance / Alpha nei 11 Orizzonti (% vs VOO)")
            colors_alpha = ['#27AE60' if a >= 0 else '#E74C3C' for a in df_results['Alpha / Diff (%)']]

            fig_alpha = go.Figure(go.Bar(
                x=df_results['Orizzonte'],
                y=df_results['Alpha / Diff (%)'],
                marker_color=colors_alpha,
                text=[f"{a:+.2f}%" for a in df_results['Alpha / Diff (%)']],
                textposition='auto'
            ))
            fig_alpha.update_layout(
                yaxis_title="Alpha (%) vs VOO",
                xaxis_title="Orizzonte Temporale",
                margin=dict(l=0, r=0, t=30, b=0),
                height=380
            )
            st.plotly_chart(fig_alpha, use_container_width=True)

        else:
            st.warning("Dati storici per VOO o portafoglio momentaneamente non disponibili.")

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
                corr_data = fetch_portfolio_close_history_fn(tuple(sorted(unique_portfolio_tickers)), period="1y")
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
                        data_batch = fetch_portfolio_close_history_fn(tuple(sorted(tickers)), period="3y")
                        if not data_batch.empty:
                            if isinstance(data_batch, pd.Series):
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

        # --- DIVIDEND SUITE & HISTORICAL CRISIS STRESS TESTING ---
        st.divider()
        port_tab_div, port_tab_stress = st.tabs([
            "❄️ Dividend Income & Yield on Cost",
            "⚡ Macro Stress Testing & Historical Crashes"
        ])

        with port_tab_div:
            try:
                curr_prices_map = {}
                div_yields_map = {}
                for itm in st.session_state['portfolio']:
                    tk_sym = str(itm.get('ticker', '')).strip().upper()
                    if tk_sym in prices_dict:
                        curr_prices_map[tk_sym] = float(prices_dict[tk_sym])
                    tk_info = stock_infos.get(tk_sym) or {}
                    dy = tk_info.get('dividendYield') or 0.0
                    if dy > 0 and dy < 1.0:
                        dy *= 100.0
                    div_yields_map[tk_sym] = float(dy)

                render_portfolio_dividend_suite(
                    holdings=st.session_state['portfolio'],
                    current_prices=curr_prices_map,
                    dividend_yields=div_yields_map
                )
            except Exception as e:
                st.warning(f"Unable to compute dividend projections: {e}")

        with port_tab_stress:
            try:
                stress_df_input = pd.DataFrame({
                    "Ticker": df_portfolio["Ticker"],
                    "Value ($)": df_portfolio["Valore Totale ($)"],
                    "Sector": [(stock_infos.get(t) or {}).get("sector", "Technology") for t in df_portfolio["Ticker"]]
                })
                render_portfolio_stress_test_suite(stress_df_input, total_portfolio_value)
            except Exception as e:
                st.warning(f"Unable to run stress test simulation: {e}")

        # --- AI PORTFOLIO ANALYSIS ---
        st.divider()
        st.subheader("🤖 AI Risk & Diversification Analysis")
        st.write("Chiedi a Gemma di valutare il rischio delle tue posizioni.")

        if st.button("⚖️ Analizza Diversificazione", type="secondary"):
            with st.spinner("Gemma sta analizzando i pesi del tuo portafoglio..."):
                ai_advice = analyze_portfolio_diversification_fn(df_portfolio, total_portfolio_value)
                st.success(ai_advice)

        if st.button("🗑️ Svuota Portafoglio"):
            st.session_state['portfolio'] = []
            save_portfolio_fn([])
            st.rerun()

    else:
        st.info("Nessuna posizione in portafoglio.")
