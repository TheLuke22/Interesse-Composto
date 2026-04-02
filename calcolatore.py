import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import yfinance as yf
from datetime import datetime, timedelta

# --- Configurazione Iniziale ---
st.set_page_config(page_title="Dashboard Finanziaria Pro", layout="wide")

# --- Funzioni di Utilità ---
def formatta_grandi_numeri(valore):
    if valore is None or str(valore) == 'nan' or valore == 'N/A' or isinstance(valore, str): return "N/A"
    prefix = ""
    if valore < 0: valore = abs(valore); prefix = "-"
    if valore >= 1_000_000_000_000: return f"{prefix}${valore/1_000_000_000_000:.2f}T"
    if valore >= 1_000_000_000: return f"{prefix}${valore/1_000_000_000:.2f}B"
    if valore >= 1_000_000: return f"{prefix}${valore/1_000_000:.2f}M"
    return f"{prefix}${valore:,.2f}"

def formatta_perc(valore):
    if valore is None or str(valore) == 'nan' or valore == 'N/A': return "N/A"
    return f"{valore * 100:.2f}%"

# --- MENU LATERALE ---
st.sidebar.title("🧭 Navigazione")
pagina_scelta = st.sidebar.radio("Strumento:", ["📈 Interesse Composto", "📊 Tracker Azionario"])
st.sidebar.divider()

# NUOVO: Opzione Reinvestimento Dividendi (visibile solo nella pagina Tracker)
drip_attivo = False
if pagina_scelta == "📊 Tracker Azionario":
    st.sidebar.subheader("Opzioni Strategia")
    drip_attivo = st.sidebar.toggle("Reinvesti Dividendi (DRIP)", value=False, help="Se attivato, i dividendi vengono usati per acquistare nuove azioni al prezzo di chiusura del giorno di stacco.")

# ==========================================
# PAGINA 1: INTERESSE COMPOSTO
# ==========================================
if pagina_scelta == "📈 Interesse Composto":
    st.title("💸 Calcolatore di Interesse Composto")
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        cap_iniz = st.number_input("Capitale iniziale (€)", min_value=0.0, value=1000.0)
        tasso = st.number_input("Tasso annuo (%)", min_value=0.0, value=5.0)
    with col2:
        anni = int(st.number_input("Anni", min_value=1, value=10))
        freq = st.selectbox("Capitalizzazione", ["Annuale", "Semestrale", "Trimestrale", "Mensile"])
        freq_map = {"Annuale": 1, "Semestrale": 2, "Trimestrale": 4, "Mensile": 12}

    if st.button("🚀 Calcola", type="primary", use_container_width=True):
        dati = []
        t_dec = tasso / 100
        for a in range(anni + 1):
            m = cap_iniz * (1 + t_dec / freq_map[freq]) ** (freq_map[freq] * a)
            dati.append({"Anno": a, "Capitale Totale (€)": round(m, 2)})
        df = pd.DataFrame(dati)
        st.success(f"**Totale finale:** € {df.iloc[-1]['Capitale Totale (€)']:,.2f}")
        st.plotly_chart(px.area(df, x="Anno", y="Capitale Totale (€)", markers=True), use_container_width=True)

# ==========================================
# PAGINA 2: TRACKER AZIONARIO (CON LOGICA DRIP)
# ==========================================
elif pagina_scelta == "📊 Tracker Azionario":
    st.title("📈 Analisi Fondamentale & Performance")
    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1: ticker_input = st.text_input("Simbolo Azione", value="KO").upper()
    with col2: cap_investito = st.number_input("Capitale iniziale", min_value=100.0, value=1000.0)
    with col3: anni_backtest = st.slider("Anni di storico", min_value=1, max_value=20, value=10)

    if st.button("🚀 Analizza Titolo", type="primary", use_container_width=True):
        azione = yf.Ticker(ticker_input)
        info = azione.info
        
        if not info or ('regularMarketPrice' not in info and 'previousClose' not in info):
            st.error("Simbolo non trovato.")
        else:
            # --- METRICHE PRINCIPALI ---
            st.markdown(f"### 🏢 {info.get('shortName', ticker_input)}")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Market Cap", formatta_grandi_numeri(info.get('marketCap')))
            m2.metric("P/E (Trailing)", info.get('trailingPE', 'N/A'))
            m3.metric("EPS (Trailing)", f"${info.get('trailingEps', 'N/A')}")
            dy = info.get('dividendYield', 'N/A')
            dy_corr = (dy if dy > 0.5 else dy * 100) if dy != 'N/A' else 0
            m4.metric("Div Yield (FWD)", f"{dy_corr:.2f}%" if dy != 'N/A' else "N/A")
            
            m1.metric("Prev. Close", f"${info.get('previousClose', 'N/A')}")
            m2.metric("P/E (Forward)", info.get('forwardPE', 'N/A'))
            m3.metric("EPS (Forward)", f"${info.get('forwardEps', 'N/A')}")
            m4.metric("Div Rate (FWD)", f"${info.get('dividendRate', 'N/A')}")

            st.divider()

            # --- FINANCIAL HIGHLIGHTS ---
            st.markdown("### 💎 Financial Highlights")
            h1, h2, h3 = st.columns(3)
            with h1:
                st.write("**Redditività**")
                st.metric("Profit Margin", formatta_perc(info.get('profitMargins')))
                st.metric("Return on Assets (ttm)", formatta_perc(info.get('returnOnAssets')))
                st.metric("Return on Equity (ttm)", formatta_perc(info.get('returnOnEquity')))
            with h2:
                st.write("**Bilancio**")
                st.metric("Total Cash (mrq)", formatta_grandi_numeri(info.get('totalCash')))
                st.metric("Total Debt/Equity (mrq)", f"{info.get('debtToEquity', 'N/A')}")
            with h3:
                st.write("**Cash Flow**")
                st.metric("Levered Free Cash Flow (ttm)", formatta_grandi_numeri(info.get('leveredFreeCashFlow')))

            st.divider()

            # --- SIMULAZIONE STORICA CON E SENZA DRIP ---
            data_fine = datetime.today()
            data_inizio = data_fine - timedelta(days=anni_backtest * 365)
            dati = azione.history(start=data_inizio, end=data_fine)
            
            if not dati.empty:
                # Logica di simulazione parallela
                azioni_con_drip = cap_investito / dati['Close'].iloc[0]
                azioni_senza_drip = azioni_con_drip
                cash_senza_drip = 0
                
                valore_con_drip_serie = []
                valore_senza_drip_serie = []
                valore_solo_prezzo_serie = []
                
                for i in range(len(dati)):
                    prezzo = dati['Close'].iloc[i]
                    div = dati['Dividends'].iloc[i]
                    
                    if div > 0:
                        # Scenario 1: DRIP Attivo
                        azioni_con_drip += (div * azioni_con_drip) / prezzo
                        # Scenario 2: DRIP Disattivo
                        cash_senza_drip += (div * azioni_senza_drip)
                    
                    valore_con_drip_serie.append(azioni_con_drip * prezzo)
                    valore_senza_drip_serie.append((azioni_senza_drip * prezzo) + cash_senza_drip)
                    valore_solo_prezzo_serie.append(azioni_senza_drip * prezzo)

                dati['Valore DRIP'] = valore_con_drip_serie
                dati['Valore NO DRIP'] = valore_senza_drip_serie
                dati['Valore Solo Prezzo'] = valore_solo_prezzo_serie
                
                # Estrazione dei valori finali
                finale_drip = dati['Valore DRIP'].iloc[-1]
                finale_no_drip = dati['Valore NO DRIP'].iloc[-1]
                
                # Calcolo delle percentuali di rendimento (ROI)
                perc_drip = ((finale_drip - cap_investito) / cap_investito) * 100
                perc_no_drip = ((finale_no_drip - cap_investito) / cap_investito) * 100
                
                # --- NUOVO: Calcolo Yield on Cost (YOC) ---
                # 1. Troviamo i dividendi pagati negli ultimi 365 giorni per singola azione
                data_un_anno_fa = dati.index[-1] - pd.Timedelta(days=365)
                div_ttm_per_share = dati.loc[dati.index >= data_un_anno_fa, 'Dividends'].sum()
                
                # 2. Calcoliamo il rendimento in base alle azioni possedute nei due scenari
                yoc_drip = (div_ttm_per_share * azioni_con_drip) / cap_investito * 100
                yoc_no_drip = (div_ttm_per_share * azioni_senza_drip) / cap_investito * 100
                
                # Scegliamo quale serie mostrare sul grafico in base all'interruttore
                serie_scelta = dati['Valore DRIP'] if drip_attivo else dati['Valore NO DRIP']
                
                # --- Stampa a schermo ---
                st.markdown(f"### 📊 Performance Storica ({'Con Reinvestimento' if drip_attivo else 'Senza Reinvestimento'})")
                
                # I due box di confronto affiancati con Percentuali e YOC
                c1, c2 = st.columns(2)
                c1.info(f"**Total Return with DRIP:** ${finale_drip:,.2f}  ( **+{perc_drip:,.2f}%** )\n\n**Yield on Cost with DRIP:** {yoc_drip:,.2f}%")
                c2.warning(f"**Total Return without DRIP:** ${finale_no_drip:,.2f}  ( **+{perc_no_drip:,.2f}%** )\n\n**Yield on Cost without DRIP:** {yoc_no_drip:,.2f}%")
                
                # Creazione del grafico
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=dati.index, y=serie_scelta, name='Total Return', fill='tozeroy', line=dict(color='#27AE60')))
                fig.add_trace(go.Scatter(x=dati.index, y=dati['Valore Solo Prezzo'], name='Price Return (Solo Prezzo)', line=dict(color='#2E86C1', dash='dash')))
                fig.update_layout(hovermode="x unified", yaxis_title="Valore Investimento ($)")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.warning("Dati storici non disponibili.")