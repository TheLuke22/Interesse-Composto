"""
Macro & Market Pulse UI Component:
Features real-time tracking of macro commodities, yields, currencies,
adaptive neon sparklines, and percentage change indicators.
"""
import streamlit as st
import plotly.express as px
from components.ui_utils import render_custom_metric


def render_macro_market_ui(fetch_macro_market_data_fn):
    """
    Renders the Macro & Market Pulse dashboard.
    """
    st.title("🌍 Macro & Market Pulse")
    st.markdown(
        "<p style='color: #8A929A; font-style: italic; font-size: 18px;'>"
        "« Governments don't rule the world, Goldman Sachs rules the world. »"
        "</p>",
        unsafe_allow_html=True
    )
    st.divider()

    with st.spinner("Acquisizione dati macroeconomici in batch..."):
        macro_data = fetch_macro_market_data_fn()

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

                    m_icon = "🌍"
                    if "Oro" in name:
                        m_icon = "🪙"
                    elif "Argento" in name:
                        m_icon = "💿"
                    elif "Petrolio" in name:
                        m_icon = "⛽"
                    elif "EUR/USD" in name:
                        m_icon = "💱"

                    if "EUR/USD" in name:
                        render_custom_metric(name, f"{val:.4f}", f"{pct:+.2f}%", icon=m_icon, is_positive=(pct >= 0))
                    else:
                        formatted_val = f"${val:,.2f}" if ("Oro" in name or "Argento" in name or "Petrolio" in name) else f"{val:,.2f}"
                        render_custom_metric(name, formatted_val, f"{pct:+.2f}%", icon=m_icon, is_positive=(pct >= 0))

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
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

            st.write("")
            st.write("")
