"""
Financial News Feed & AI Sentiment UI Component:
Features real-time news aggregation, AI portfolio sentiment treemap overlay,
TextBlob sentiment tagging, and conversational news RAG chatbot.
"""
import random
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
from components.ui_utils import get_sentiment, WALL_STREET_QUOTES


def render_financial_news_ui(fetch_news_fn, get_batch_prices_fn, ask_financial_chatbot_fn):
    """
    Renders the Financial News Feed and AI Sentiment analysis module.
    """
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
                    prices_dict = get_batch_prices_fn(list(set(tickers))) if tickers else {}

                    import concurrent.futures

                    def process_holding_sentiment(item):
                        tk = item['ticker']
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

                        tk_news = fetch_news_fn(tk)
                        sentiment_score = 0
                        valid_news = 0

                        if tk_news:
                            titles = []
                            for n in tk_news[:8]:
                                title = n['content'].get('title', '') if 'content' in n else n.get('title', '')
                                if title:
                                    titles.append(title)

                            for title in titles:
                                lbl = get_sentiment(title)
                                if "Bullish" in lbl or "Positive" in lbl:
                                    sentiment_score += 1
                                elif "Bearish" in lbl or "Negative" in lbl:
                                    sentiment_score -= 1
                                valid_news += 1

                        avg_score = (sentiment_score / valid_news) if valid_news > 0 else 0

                        if avg_score > 0.3:
                            human_lbl = "🟢 Rialzista"
                        elif avg_score < -0.3:
                            human_lbl = "🔴 Ribassista"
                        else:
                            human_lbl = "⚪ Incerto/Neutro"

                        return {
                            "Ticker": tk,
                            "Valore ($)": max(valore_monetario, 0.01),
                            "AI Score": avg_score,
                            "Giudizio": human_lbl
                        }

                    workers = min(12, max(len(st.session_state['portfolio']), 1))
                    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
                        tree_data = list(executor.map(process_holding_sentiment, st.session_state['portfolio']))

                    df_tree = pd.DataFrame(tree_data)
                    if not df_tree.empty:
                        df_tree["Portafoglio"] = "Mio Portafoglio"
                        fig_tree = px.treemap(
                            df_tree,
                            path=['Portafoglio', 'Ticker'],
                            values='Valore ($)',
                            color='AI Score',
                            hover_name='Ticker',
                            hover_data={"AI Score": False, "Giudizio": True, "Valore ($)": ':$,.2f'},
                            color_continuous_scale=[
                                [0.0, '#E74C3C'], [0.35, '#E74C3C'],
                                [0.35, '#2E2E2E'], [0.65, '#2E2E2E'],
                                [0.65, '#27AE60'], [1.0, '#27AE60']
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
            news_items = fetch_news_fn(ticker_news)
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
                            except Exception:
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

    for msg in st.session_state['chat_history']:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Es. 'Perché il titolo è crollato?' oppure 'Fai un riassunto sulle acquisizioni recenti...'"):
        st.session_state['chat_history'].append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            if st.session_state.get('news_contexts'):
                with st.spinner(f"Riflessione quantitativa profonda... | '{random.choice(WALL_STREET_QUOTES)}'"):
                    ctx_str = "\n".join(st.session_state['news_contexts'][:15])
                    ans = ask_financial_chatbot_fn(prompt, ctx_str)
                    st.markdown(ans)
                    st.session_state['chat_history'].append({"role": "assistant", "content": ans})
            else:
                warning_msg = "Attenzione: Cerca prima le notizie del titolo usando la barra di ricerca in alto, altrimenti Gemma non avrà alcun contesto su cui basarsi."
                st.warning(warning_msg)
                st.session_state['chat_history'].append({"role": "assistant", "content": warning_msg})
