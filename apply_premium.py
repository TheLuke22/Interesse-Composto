import re

with open("calcolatore.py", "r") as f:
    code = f.read()

# 1. Add new imports
old_imports = """import requests
import json
import os"""
new_imports = """import requests
import json
import os
from scipy.optimize import minimize
from fpdf import FPDF
import io"""
code = code.replace(old_imports, new_imports)

# 2. Add AI RAG and PDF generation before `@st.cache_data` (Data Engine)
injection_point = "# --- DATA ENGINE (WITH CACHING) ---"
new_functions = """def ask_financial_chatbot(question, news_context):
    prompt = f\"\"\"Sei un assistente finanziario intelligente integrato nella PRO Quant Dashboard. 
Usa ESCLUSIVAMENTE le seguenti notizie recenti per rispondere alla domanda dell'investitore. Non inventare dati.
Se la risposta non è nelle notizie, di' che non hai informazioni sufficienti. Rispondi in italiano in modo formale.

CONTESTO DELLE NEWS RECENTI:
{news_context}

DOMANDA DELL'INVESTITORE:
{question}
\"\"\"
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

# --- DATA ENGINE (WITH CACHING) ---"""
code = code.replace(injection_point, new_functions)

# 3. Modify Sidebar Sidebar CSS and choice
old_css_sidebar_1 = """[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4) { margin-top: 55px; } /* Stacco lungo per linea divisoria */"""
new_css_sidebar_1 = """[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4) { margin-top: 35px; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5) { margin-top: 55px; } /* Stacco lungo per linea divisoria Macro */
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6) { margin-top: 35px; }"""
code = code.replace(old_css_sidebar_1, new_css_sidebar_1)

old_css_sidebar_2 = """[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4)::before { 
    content: '';
    height: 1px;
    background-color: rgba(255, 255, 255, 0.2);
    top: -28px;
    left: -15px;
    right: -65px;
}"""
new_css_sidebar_2 = """[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(4)::before { content: '📰 Insights'; }
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(5)::before { 
    content: '';
    height: 1px;
    background-color: rgba(255, 255, 255, 0.2);
    top: -28px;
    left: -15px;
    right: -65px;
}
[data-testid="stSidebar"] div[role="radiogroup"] > label:nth-child(6)::before { content: '🔍 Discovery'; }"""
code = code.replace(old_css_sidebar_2, new_css_sidebar_2)

old_page_choice = """page_choice = st.sidebar.radio("Tool:", ["📈 Compound Interest", "📊 Stock Tracker", "📁 My Portfolio", "📰 Financial News"], label_visibility="collapsed")"""
new_page_choice = """page_choice = st.sidebar.radio("Tool:", ["📈 Compound Interest", "📊 Stock Tracker", "📁 My Portfolio", "📰 Financial News", "🌍 Macro & Market", "🔍 Stock Screener"], label_visibility="collapsed")"""
code = code.replace(old_page_choice, new_page_choice)

# 4. Modify Stock Tracker: Tabs (DCF) and PDF Export
old_tabs = """                tab_price, tab_divs, tab_mc, tab_holders, tab_funds = st.tabs([
                    "📊 Price & Tech Analysis", 
                    "💰 Dividends & Returns", 
                    "🎲 Projections", 
                    "🏦 Ownership", 
                    "📅 Fundamentals"
                ])"""
new_tabs = """                # Scarica report istituzionale
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
                ])"""
code = code.replace(old_tabs, new_tabs)

# Add DCF code inside Stock Tracker (just before ELIF for Portfolio)
dcf_code = """
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

"""
code = code.replace("# ==========================================\n# PAGE 3: MY PORTFOLIO", dcf_code + "# ==========================================\n# PAGE 3: MY PORTFOLIO")

# 5. Modify Portfolio for Markowitz Optimization
markowitz_code = """
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
                                num_assets = len(tickers)
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
                                
                                opt_df = pd.DataFrame({'Ticker': data_batch.columns, 'Peso Ottimale (%)': (opt_weights*100).round(2)})
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

        # --- AI PORTFOLIO ANALYSIS ---"""
code = code.replace("# --- AI PORTFOLIO ANALYSIS ---", markowitz_code)

# 6. Financial News Chatbot RAG Modification
old_news_start = "if st.button(\"Search News\", type=\"primary\"):\n        with st.spinner(\"Fetching latest news and analyzing sentiment...\"):\n            news_items = fetch_news(ticker_news)"
new_news_start = "if 'news_contexts' not in st.session_state:\n        st.session_state['news_contexts'] = []\n\n    if st.button(\"Search News\", type=\"primary\"):\n        with st.spinner(\"Fetching latest news and analyzing sentiment...\"):\n            news_items = fetch_news(ticker_news)\n            st.session_state['news_contexts'] = []"
code = code.replace(old_news_start, new_news_start)

# capture contexts
code = code.replace("sentiment_label = get_sentiment(title)", "sentiment_label = get_sentiment(title)\n                        st.session_state['news_contexts'].append(f\"Titolo: {title} | Data: {pub_date}\")")

# add chatbot section at the end of news
chatbot_sec = """

    st.divider()
    st.subheader("💡 Chiedi all'Assistente AI Sulle Notizie")
    st.write("Fai una domanda usando solo i contenuti freschi estratti qui sopra (RAG Locale).")
    user_q = st.text_input("La tua domanda (Es. 'Perché il titolo è sceso oggi?')")
    if user_q and st.button("Consulta AI", key="btn_rag"):
        if st.session_state.get('news_contexts'):
            with st.spinner("Riflessione in corso..."):
                ctx_str = "\\n".join(st.session_state['news_contexts'][:15])
                ans = ask_financial_chatbot(user_q, ctx_str)
                st.success(ans)
        else:
            st.warning("Cerca prima le notizie per caricare il contesto dell'AI.")

# =========================================="""
code = code.replace("st.warning(f\"No recent news found for ticker {ticker_news}.\")", "st.warning(f\"No recent news found for ticker {ticker_news}.\")" + chatbot_sec)


# 7. Add Macro Page and Screener Page at the very end
new_pages = """
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
                
        cols = st.columns(len(macro_data))
        for col, (name, series) in zip(cols, macro_data.items()):
            with col:
                val = series.iloc[-1]
                prev = series.iloc[-2]
                pct = ((val - prev)/prev)*100
                st.metric(name, f"{val:.2f}", f"{pct:.2f}%")
                fig = px.line(series, x=series.index, y=series.values)
                fig.update_layout(xaxis_visible=False, yaxis_visible=False, height=100, margin=dict(l=0, r=0, t=10, b=0), showlegend=False)
                st.plotly_chart(fig, use_container_width=True)

# ==========================================
# PAGE 6: STOCK SCREENER
# ==========================================
elif page_choice == "🔍 Stock Screener":
    st.title("🔍 Blue-Chip Stock Screener")
    st.write("Esplora il **Dow Jones 30** alla ricerca di opportunità Value e Dividend.")
    st.divider()
    
    dow_30 = ["AAPL", "MSFT", "V", "JPM", "WMT", "JNJ", "PG", "UNH", "HD", "CVX", "MRK", "KO", "MCD", "CSCO", "CRM", "TRV", "GS", "BA", "DIS", "VZ", "HON", "AMGN", "IBM", "CAT", "NKE", "AXP", "MMM", "DOW", "INTC", "WBA"]
    
    sc1, sc2, sc3 = st.columns(3)
    max_pe = sc1.number_input("P/E Ratio Massimo", value=25.0)
    min_div = sc2.number_input("Dividend Yield Minimo (%)", value=2.0)
    min_cap = sc3.number_input("Market Cap Min. (Billion $)", value=100)
    
    if st.button("🚀 Esegui Screen", type="primary"):
        with st.spinner("Scansione rapida del Dow 30..."):
            screener_res = []
            for tkr in dow_30:
                tk_info = fetch_stock_info(tkr)
                if not tk_info: continue
                pe = tk_info.get('trailingPE')
                d_yield = tk_info.get('dividendYield', 0)
                d_yield = d_yield * 100 if d_yield else 0
                mcap_b = tk_info.get('marketCap', 0) / 1e9
                
                if pe and pe <= max_pe and d_yield >= min_div and mcap_b >= min_cap:
                    screener_res.append({
                        "Ticker": tkr,
                        "Azienda": tk_info.get('shortName', ''),
                        "P/E": round(pe, 2),
                        "Div Yield %": round(d_yield, 2),
                        "Market Cap (B)": round(mcap_b, 2),
                        "Prezzo": tk_info.get('currentPrice', 'N/A')
                    })
                        
            if screener_res:
                df_screen = pd.DataFrame(screener_res).sort_values(by="Div Yield %", ascending=False)
                st.success(f"Trovate {len(screener_res)} aziende che rispettano i tuoi parametri.")
                st.dataframe(df_screen, use_container_width=True, hide_index=True)
            else:
                st.warning("Nessuna azienda nel basket rispetta questi criteri!")

"""
code += new_pages

with open("calcolatore.py", "w") as f:
    f.write(code)

