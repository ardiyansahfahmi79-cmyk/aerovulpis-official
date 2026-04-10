/h1><p class="rajdhani-font">Score: {buy_count} Buy | {sell_count} Sell</p></div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="glass-card"><p class="digital-font">10-INDICATOR ANALYSIS</p>', unsafe_allow_html=True)
            for k, v in indicators.items():
                col_c = "#00ff88" if v in ["BUY", "BULLISH", "STRONG"] else "#ff2a6d" if v in ["SELL", "BEARISH"] else "#888888"
                st.markdown(f'<div style="display:flex; justify-content:space-between;"><span class="rajdhani-font">{k}</span><span class="digital-font" style="color:{col_c};">{v}</span></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("Data tidak cukup untuk analisis 10 indikator. Coba timeframe lebih besar.")

# ====================== RISK MANAGEMENT ======================
elif menu_selection == "Risk Management":
    st.markdown('<h2 class="digital-font">🛡️ Risk Management Protocol</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        balance = st.number_input("Account Balance ($)", value=1000.0)
        risk_pct = st.slider("Risk per Trade (%)", 0.1, 5.0, 1.0)
        entry_p = st.number_input("Entry Price", value=0.0)
        stop_l = st.number_input("Stop Loss Price", value=0.0)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        if entry_p > 0 and stop_l > 0:
            risk_amt = balance * (risk_pct / 100)
            diff = abs(entry_p - stop_l)
            pos_size = risk_amt / diff if diff > 0 else 0
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <p class="rajdhani-font">CALCULATED POSITION SIZE</p>
                <h2 class="digital-font" style="color:#00d4ff;">{pos_size:,.2f} Units</h2>
                <hr style="border-color:rgba(255,255,255,0.1);">
                <p class="rajdhani-font">Risk Amount: <span style="color:#ff2a6d;">${risk_amt:,.2f}</span></p>
                <p class="rajdhani-font">Reward (1:2): <span style="color:#00ff88;">${risk_amt*2:,.2f}</span></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Masukkan Entry Price dan Stop Loss untuk menghitung manajemen risiko.")

# ====================== MARKET HISTORY ======================
elif menu_selection == "Market History":
    st.markdown(f'<h2 class="digital-font">📊 Market History ({selected_tf_display})</h2>', unsafe_allow_html=True)
    market_data = get_market_data(ticker_input)
    if market_data:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("OPEN", f"{market_data['open']:,.4f}")
        c2.metric("HIGH", f"{market_data['high']:,.4f}")
        c3.metric("LOW", f"{market_data['low']:,.4f}")
        c4.metric("CLOSE", f"{market_data['close']:,.4f}")
        
    df_hist = get_historical_data(ticker_input, period=period, interval=interval)
    if not df_hist.empty:
        df_hist = df_hist.sort_index(ascending=False)
        df_hist.index = df_hist.index.strftime('%d %B %Y %H:%M')
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.dataframe(df_hist[['Open', 'High', 'Low', 'Close', 'Volume']].head(50), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ====================== CHATBOT AI TRADING (FINAL FIX VERSION) ======================
elif menu_selection == "Chatbot AI Trading":
    st.markdown('<h2 class="digital-font">🤖 Chatbot AI Trading</h2>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    
    # Inisialisasi history pesan
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Sistem AeroVulpis v3.2 Aktif. Siap beraksi, Fahmi!"}]
        
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(f'<span class="rajdhani-font">{msg["content"]}</span>', unsafe_allow_html=True)
    
    if prompt := st.chat_input("Kirim perintah ke AeroVulpis..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
            
        with st.chat_message("assistant"):
            with st.spinner("Menganalisis..."):
                market_data = get_market_data(ticker_input)
                price_val = market_data['price'] if market_data else 'N/A'
                context = f"Harga {ticker_display} saat ini adalah {price_val} pada timeframe {selected_tf_display}."
                response = get_gemini_response(prompt, context)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 20px; opacity: 0.8;">
    <p class="rajdhani-font" style="font-style: italic; font-size: 18px; color: #ccc;">
        "Disiplin adalah kunci, emosi adalah musuh. Tetap tenang dan percaya pada sistem."
    </p>
    <p class="digital-font" style="font-size: 16px; color: #00ff88;">
        — Fahmi (Pencipta AeroVulpis)
    </p>
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v3.2 ULTIMATE • 2026</p>
</div>
""", unsafe_allow_html=True)
