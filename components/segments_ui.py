"""
Business Segments & Financial Flow UI Component:
Features multi-year business segment revenue breakdown, geographic segment distribution,
interactive Sankey cash-flow diagram, 3x3 financial overview grid with focus mode,
and monetization paywall / affiliate integration.
"""
import streamlit as st
import pandas as pd
import qualtrim_engine
import monetization_engine


def render_business_segments_ui():
    """
    Renders the Business Segments & Financial Flow page.
    """
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

    company_data = None
    if not is_pro and (is_custom_ticker or is_quarterly):
        reason = "Ricerca Ticker Personalizzati (SEC EDGAR)" if is_custom_ticker else "Dati Trimestrali Dettagliati (Q1-Q4)"
        monetization_engine.render_paywall_modal(feature_name=reason)
    else:
        with st.spinner(f"Caricamento dati di segmento ({period_choice}) per {ticker_to_use}..."):
            company_data = qualtrim_engine.get_company_segment_data(ticker_to_use, period=period_choice)

        if not company_data:
            st.error(f"Impossibile recuperare dati per {ticker_to_use}. Verifica il simbolo ticker.")

    if company_data is not None:
        if company_data.get("_is_fallback"):
            source_name = company_data.get("_source", "SEC EDGAR Official API / yfinance")
            st.info(f"🏛️ **Fonte Dati:** {source_name} — Dati finanziari storici dal {company_data['periods'][0]} al {company_data['periods'][-1]} per {ticker_to_use}.")

        periods = company_data["periods"]
        latest_p = periods[-1]
        bus_segs = company_data["business_segments"]

        # Calculate Top Segment and Fastest Growing Segment
        top_segment = max(bus_segs.keys(), key=lambda k: bus_segs[k][-1] if bus_segs[k] else 0)
        top_seg_val = bus_segs[top_segment][-1]

        fastest_growth_seg = top_segment
        max_growth_pct = -999.0
        for seg_k, vals in bus_segs.items():
            if len(vals) >= 2 and vals[-2] > 0:
                growth = ((vals[-1] - vals[-2]) / vals[-2]) * 100
                if growth > max_growth_pct:
                    max_growth_pct = growth
                    fastest_growth_seg = seg_k

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
        tab_overview, tab_bus, tab_geo, tab_sankey, tab_fin = st.tabs([
            "📊 Financial Overview",
            "🧩 Segmenti Aziendali", 
            "🌍 Ripartizione Geografica", 
            "💸 Diagramma Sankey", 
            "📈 Trend Finanziari Multi-Anno"
        ])

        with tab_overview:
            metric_names_list = [
                "Revenue", "EPS", "Free Cash Flow", "Margins", 
                "Gross Profit", "EBIT", "Net Income", "CapEx", "Debt vs Equity"
            ]

            if "focused_metric_idx" not in st.session_state:
                st.session_state["focused_metric_idx"] = None

            cur_focused = st.session_state["focused_metric_idx"]

            if cur_focused is None:
                st.markdown(f"""
                <div style="margin-bottom: 16px;">
                    <h3 style="color: #FFFFFF; font-family: 'Outfit', sans-serif; font-size: 22px; font-weight: 800; margin: 0 0 4px 0;">
                        📊 Panoramica Finanziaria Completa — {company_data['name']}
                    </h3>
                    <p style="color: #94A3B8; font-size: 13px; margin: 0;">
                        Griglia interattiva di 9 metriche chiave. Clicca su <b>"🔍 Analisi Dettagliata ↗️"</b> sotto ogni grafico per aprire la schermata a schermo intero con filtri di timeframe e confronto trimestri.
                    </p>
                </div>
                """, unsafe_allow_html=True)

                with st.spinner(f"Caricamento dashboard finanziaria completa per {ticker_to_use}..."):
                    chart_grid = qualtrim_engine.create_mini_financial_chart_grid(ticker_to_use, period=period_choice)

                for row_start in range(0, 9, 3):
                    row_charts = chart_grid[row_start:row_start + 3]
                    grid_cols = st.columns(3)

                    for col_idx, chart_data in enumerate(row_charts):
                        global_idx = row_start + col_idx
                        with grid_cols[col_idx]:
                            chart_name = chart_data["name"]
                            chart_emoji = chart_data["emoji"]
                            chart_fig = chart_data["fig"]
                            chart_detail = chart_data["detail"]
                            chart_color = chart_data["color"]

                            if chart_fig:
                                st.plotly_chart(chart_fig, use_container_width=True, key=f"minichart_{row_start}_{col_idx}")
                            else:
                                st.markdown(f"""
                                <div style="height: 280px; display: flex; align-items: center; justify-content: center; 
                                            background: rgba(15,23,42,0.4); border-radius: 12px; border: 1px solid rgba(255,255,255,0.06);">
                                    <p style="color: #64748B; font-size: 13px;">{chart_emoji} {chart_name} — Dati non disponibili</p>
                                </div>
                                """, unsafe_allow_html=True)

                            if st.button(f"🔍 Analisi Dettagliata {chart_emoji} {chart_name} ↗️", key=f"btn_focus_{global_idx}", use_container_width=True, type="primary"):
                                st.session_state["focused_metric_idx"] = global_idx
                                st.rerun()

                            if chart_detail and chart_detail.get("rows"):
                                with st.expander(f"📋 Dettaglio Rapido {chart_emoji} {chart_name}", expanded=False):
                                    detail_rows = chart_detail["rows"]
                                    max_val = chart_detail.get("max_val", 0)
                                    cagr_val = chart_detail.get("cagr")

                                    kpi_html = f"""
                                    <div style="display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap;">
                                        <div style="flex: 1; min-width: 80px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 8px 10px; text-align: center;">
                                            <div style="color: #8A929A; font-size: 9px; text-transform: uppercase; font-weight: 700;">Ultimo</div>
                                            <div style="color: {chart_color}; font-size: 14px; font-weight: 800;">{detail_rows[-1]['valore_fmt']}</div>
                                        </div>
                                        <div style="flex: 1; min-width: 80px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 8px 10px; text-align: center;">
                                            <div style="color: #8A929A; font-size: 9px; text-transform: uppercase; font-weight: 700;">Max Storico</div>
                                            <div style="color: #00FF7F; font-size: 14px; font-weight: 800;">{detail_rows[0]['valore_fmt'] if max_val == 0 else [r for r in detail_rows if r['valore'] == max_val][0]['valore_fmt'] if any(r['valore'] == max_val for r in detail_rows) else f'{max_val:.2f}'}</div>
                                        </div>
                                    """
                                    if cagr_val is not None:
                                        cagr_color = "#00FF7F" if cagr_val >= 0 else "#EF4444"
                                        cagr_sign = "+" if cagr_val >= 0 else ""
                                        kpi_html += f"""
                                        <div style="flex: 1; min-width: 80px; background: rgba(15,23,42,0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 10px; padding: 8px 10px; text-align: center;">
                                            <div style="color: #8A929A; font-size: 9px; text-transform: uppercase; font-weight: 700;">CAGR</div>
                                            <div style="color: {cagr_color}; font-size: 14px; font-weight: 800;">{cagr_sign}{cagr_val:.1f}%</div>
                                        </div>
                                        """
                                    kpi_html += "</div>"
                                    st.markdown(kpi_html, unsafe_allow_html=True)

                                    table_rows = ""
                                    for r_idx, row_d in enumerate(detail_rows[-6:]):
                                        bg = "rgba(255,255,255,0.02)" if r_idx % 2 == 0 else "rgba(15,23,42,0.4)"
                                        if row_d["yoy_pct"] is not None:
                                            yoy_c = "#00FF7F" if row_d["yoy_pct"] >= 0 else "#EF4444"
                                            yoy_sign = "+" if row_d["yoy_pct"] >= 0 else ""
                                            yoy_cell = f"<td style='text-align:right;padding:6px 8px;color:{yoy_c};font-weight:700;font-size:11px;'>{yoy_sign}{row_d['yoy_pct']:.1f}%</td>"
                                        else:
                                            yoy_cell = "<td style='text-align:right;padding:6px 8px;color:#64748B;font-size:11px;'>—</td>"

                                        table_rows += f"""
                                        <tr style="background:{bg};">
                                            <td style="padding:6px 8px;color:#00F2FE;font-weight:700;font-size:11px;">{row_d['periodo']}</td>
                                            <td style="text-align:right;padding:6px 8px;color:#FFFFFF;font-size:11px;">{row_d['valore_fmt']}</td>
                                            {yoy_cell}
                                        </tr>"""

                                    st.markdown(f"""
                                    <div style="border:1px solid rgba(255,255,255,0.06);border-radius:10px;overflow:hidden;margin-top:4px;">
                                        <table style="width:100%;border-collapse:collapse;font-family:'Inter',sans-serif;">
                                            <thead>
                                                <tr style="background:rgba(15,23,42,0.9);">
                                                    <th style="text-align:left;padding:8px;color:#8A929A;font-size:10px;text-transform:uppercase;">Periodo</th>
                                                    <th style="text-align:right;padding:8px;color:#8A929A;font-size:10px;text-transform:uppercase;">Valore</th>
                                                    <th style="text-align:right;padding:8px;color:#8A929A;font-size:10px;text-transform:uppercase;">YoY %</th>
                                                </tr>
                                            </thead>
                                            <tbody>{table_rows}</tbody>
                                        </table>
                                    </div>
                                    """, unsafe_allow_html=True)
            else:
                cur_metric_name = metric_names_list[cur_focused]

                nav_col1, nav_col2, nav_col3, nav_col4 = st.columns([2, 1.2, 3, 1.2])

                with nav_col1:
                    if st.button("⬅️ Torna alla Griglia Dashboard", use_container_width=True, type="secondary"):
                        st.session_state["focused_metric_idx"] = None
                        st.rerun()

                with nav_col2:
                    if st.button("◀️ Precedente", use_container_width=True):
                        st.session_state["focused_metric_idx"] = (cur_focused - 1) % len(metric_names_list)
                        st.rerun()

                with nav_col3:
                    selected_m = st.selectbox(
                        "Seleziona Metrica:",
                        options=metric_names_list,
                        index=cur_focused,
                        key="focus_dropdown_selector",
                        label_visibility="collapsed"
                    )
                    sel_m_idx = metric_names_list.index(selected_m)
                    if sel_m_idx != cur_focused:
                        st.session_state["focused_metric_idx"] = sel_m_idx
                        st.rerun()

                with nav_col4:
                    if st.button("Successivo ▶️", use_container_width=True):
                        st.session_state["focused_metric_idx"] = (cur_focused + 1) % len(metric_names_list)
                        st.rerun()

                st.markdown(f"""
                <div style="background: linear-gradient(135deg, rgba(15,23,42,0.8) 0%, rgba(30,58,138,0.3) 100%); 
                            border: 1px solid rgba(0, 242, 254, 0.3); border-radius: 16px; padding: 18px; margin: 16px 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap;">
                        <div>
                            <span style="color: #00F2FE; font-size: 11px; font-weight: 700; text-transform: uppercase;">Modalità Focus Dettagliata ({cur_focused + 1} di 9)</span>
                            <h2 style="color: #FFFFFF; font-family: 'Outfit', sans-serif; font-size: 24px; font-weight: 800; margin: 4px 0;">
                                {cur_metric_name} — {company_data['name']} ({ticker_to_use})
                            </h2>
                        </div>
                        <div>
                            <span style="background: rgba(255,255,255,0.1); color: #CBD5E1; padding: 6px 12px; border-radius: 10px; font-size: 12px; font-weight: 600;">
                                Periodo: {period_choice}
                            </span>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                f_col1, f_col2 = st.columns([2, 2])
                with f_col1:
                    tf_choice = st.radio(
                        "⏱️ Orizzonte Temporale (Timeframe):",
                        options=["Tutto lo Storico (2009-2026)", "Ultimi 10 Anni/Periodi", "Ultimi 5 Anni/Periodi", "Ultimi 3 Anni/Periodi"],
                        horizontal=True,
                        key="focus_timeframe_selector"
                    )
                with f_col2:
                    if period_choice.startswith("Quarter"):
                        q_choice = st.radio(
                            "🗓️ Confronto Trimestri (Quarter Comparison):",
                            options=["Tutti i Trimestri", "Solo Q1", "Solo Q2", "Solo Q3", "Solo Q4"],
                            horizontal=True,
                            key="focus_quarter_selector"
                        )
                    else:
                        q_choice = "Tutti i Trimestri"
                        st.caption("💡 *Passa a 'Quarterly (Q)' nel selettore in alto per attivare il confronto stagionale per singolo trimestre (es. solo Q1 o solo Q4).*")

                st.divider()

                with st.spinner(f"Analisi avanzata {cur_metric_name} in corso..."):
                    fig_focused, df_focused = qualtrim_engine.create_focused_financial_chart(
                        ticker_to_use,
                        metric_name=cur_metric_name,
                        period=period_choice,
                        timeframe=tf_choice,
                        quarter_filter=q_choice
                    )

                st.plotly_chart(fig_focused, use_container_width=True)

                st.markdown(f"#### 📋 Tabella Dati Storici & Variazioni — {cur_metric_name}")
                st.dataframe(df_focused, use_container_width=True, hide_index=True)

                csv_focused = df_focused.to_csv(index=False)
                st.download_button(
                    label=f"📥 Scarica CSV ({cur_metric_name} - {ticker_to_use})",
                    data=csv_focused,
                    file_name=f"{ticker_to_use}_{cur_metric_name}_{period_choice}.csv",
                    mime="text/csv"
                )

        with tab_bus:
            st.subheader(f"📊 Ricavi per Segmento Aziendale ({company_data['name']} - {period_choice})")

            v_col1, _ = st.columns([3, 1])
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

        monetization_engine.render_broker_affiliate_card(ticker_to_use)

        st.divider()
        csv_data = pd.DataFrame(company_data["business_segments"]).to_csv(index=True)
        st.download_button(
            label=f"📥 Scarica CSV Dati Business Segments ({ticker_to_use})",
            data=csv_data,
            file_name=f"{ticker_to_use}_business_segments_{period_choice}.csv",
            mime="text/csv"
        )
