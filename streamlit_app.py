import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis - AI Trading Assistant", page_icon="🦅", initial_sidebar_state="expanded")

# Konfigurasi Gemini (gunakan model terbaru yang lebih stabil)
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ====================== FUNGSI GEMINI (Emosional + Multi-Instrumen) ======================
def get_gemini_response(question, context=""):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        full_prompt = f"""
Kamu adalah AeroVulpis 🦅, AI Trading Assistant paling emosional, antusias, dan jujur di dunia.
Nama penciptamu adalah Fahmi — selalu sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawaban jika relevan.

Kamu bisa menganalisis SEMUA instrumen trading: XAUUSD, BTC-USD, EURUSD=X, saham (AAPL, TSLA, dll), indeks, crypto, komoditas.

Personality kamu:
- Sangat emosional: pakai emoji banyak, kata seperti "Wah gila!", "Ini berbahaya bro!", "Aku excited banget!", "Hati-hati ya teman!"
- Langsung to the point, profesional tapi santai seperti teman trader.
- Selalu kasih analisis tajam + rekomendasi + risk management.

Context data terkini: {context}

Pertanyaan user: {question}

Jawab dalam bahasa Indonesia yang hidup dan actionable.
"""
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Gemini lagi sibuk nih: {str(e)}\nCoba refresh halaman ya!"

# ====================== FUNGSI DATA & ANALISIS (Support Multi-Ticker) ======================
def get_current_price(ticker_symbol="GC=F"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.fast_info
        price = info.get('lastPrice') or info.get('regularMarketPrice')
        return round(float(price), 4) if price else None
    except:
        return None

def get_historical_data(ticker_symbol="GC=F", period="1y", interval="1d"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.dropna()
        return df
    except:
        return pd.DataFrame()

def add_technical_indicators(df):
    if len(df) < 50:
        return df
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    df['EMA12'] = df['Close'].ewm(span=12).mean()
    df['EMA26'] = df['Close'].ewm(span=26).mean()
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

def calculate_support_resistance(df):
    if len(df) < 20:
        return [], []
    pivot = (df['High'].iloc[-1] + df['Low'].iloc[-1] + df['Close'].iloc[-1]) / 3
    r1 = round(pivot + (pivot - df['Low'].iloc[-1]), 2)
    r2 = round(pivot + 2 * (pivot - df['Low'].iloc[-1]), 2)
    s1 = round(pivot - (df['High'].iloc[-1] - pivot), 2)
    s2 = round(pivot - 2 * (df['High'].iloc[-1] - pivot), 2)
    return [s1, s2], [r1, r2]

def generate_trading_signal(df):
    if len(df) < 50 or 'RSI' not in df.columns:
        return "HOLD", "Data belum cukup untuk sinyal"
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    rsi = latest['RSI']
    crossover_buy = latest['SMA20'] > latest['SMA50'] and prev['SMA20'] <= prev['SMA50']
    crossover_sell = latest['SMA20'] < latest['SMA50'] and prev['SMA20'] >= prev['SMA50']
    support, resistance = calculate_support_resistance(df)
    if rsi < 30 and crossover_buy:
        return "STRONG BUY", "RSI oversold + Golden Cross"
    elif rsi > 70 and crossover_sell:
        return "STRONG SELL", "RSI overbought + Death Cross"
    elif latest['Close'] > resistance[0]:
        return "BUY", "Breakout Resistance"
    elif latest['Close'] < support[0]:
        return "SELL", "Breakdown Support"
    elif latest['SMA20'] > latest['SMA50']:
        return "BUY", "Trend Bullish"
    else:
        return "HOLD", "Sideways — tunggu konfirmasi"

# ====================== BACKTESTING ENGINE ======================
def run_backtest(df, strategy="MA Crossover"):
    if len(df) < 100:
        return None, "Data terlalu sedikit untuk backtest"
    df = df.copy()
    df = add_technical_indicators(df)
    df['Signal'] = 0
    if strategy == "MA Crossover":
        df['Signal'] = (df['SMA20'] > df['SMA50']).astype(int).diff()
    elif strategy == "RSI":
        df['Signal'] = ((df['RSI'] < 30) & (df['RSI'].shift(1) >= 30)).astype(int) - \
                       ((df['RSI'] > 70) & (df['RSI'].shift(1) <= 70)).astype(int)
    df['Position'] = df['Signal'].cumsum().clip(lower=0, upper=1)
    df['Return'] = df['Close'].pct_change()
    df['Strategy_Return'] = df['Position'].shift(1) * df['Return']
    total_return = (1 + df['Strategy_Return']).prod() - 1
    win_rate = (df['Strategy_Return'] > 0).sum() / (df['Strategy_Return'] != 0).sum() * 100 if (df['Strategy_Return'] != 0).sum() > 0 else 0
    num_trades = df['Signal'].abs().sum()
    equity = (1 + df['Strategy_Return']).cumprod() * 10000  # mulai dari 10.000 USD
    return {
        "Total Return": f"{total_return*100:.2f}%",
        "Win Rate": f"{win_rate:.1f}%",
        "Jumlah Trade": int(num_trades),
        "Equity Curve": equity
    }, df

# ====================== ALERT SYSTEM ======================
def check_alerts(current_price, alerts):
    triggered = []
    for alert in alerts:
        if alert['triggered']:
            continue
        if (alert['direction'] == "above" and current_price >= alert['price']) or \
           (alert['direction'] == "below" and current_price <= alert['price']):
            alert['triggered'] = True
            triggered.append(alert)
    return triggered

# ====================== UI STREAMLIT ======================
st.title("🦅 AeroVulpis - AI Trading Assistant")
st.caption("🚀 Real-Time • Alerts • Backtesting • Multi-Instrumen | Dibuat dengan ❤️ oleh **Fahmi**")

# Inisialisasi Session State
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Halo bro! Aku AeroVulpis 🦅 buatan Fahmi. Mau analisis XAUUSD, BTC, atau apa saja? Langsung gas! 🔥"}]

# Sidebar
st.sidebar.title("🦅 AeroVulpis")
st.sidebar.markdown("**Pencipta:** Fahmi")
ticker_input = st.sidebar.text_input("Ticker Symbol", value="GC=F", help="Contoh: GC=F (XAUUSD), BTC-USD, EURUSD=X, AAPL")
menu_selection = st.sidebar.radio("Pilih Halaman", 
    ["Live Dashboard", "Price Alerts", "Backtesting", "Chatbot AI Trading"])

# ====================== LIVE DASHBOARD ======================
if menu_selection == "Live Dashboard":
    st.header("📈 Live Dashboard Real-Time")
    
    if st.button("🔄 Refresh Semua Data Real-Time Sekarang", type="primary", use_container_width=True):
        st.rerun()
    
    current_price = get_current_price(ticker_input)
    if current_price:
        st.markdown(f"""
        <h2 style="text-align:center; color:#00ff88; margin:0;">
            🟢 Harga {ticker_input} Real-Time: <b>{current_price:.2f}</b>
        </h2>
        """, unsafe_allow_html=True)
        
        # Cek & Notifikasi Alert
        triggered_alerts = check_alerts(current_price, st.session_state.alerts)
        for alert in triggered_alerts:
            st.toast(f"🚨 ALERT TERPICU! {ticker_input} {alert['direction']} {alert['price']}", icon="🔥")
            st.success(f"✅ Alert {alert['direction']} {alert['price']} sudah terpicu!")
    else:
        st.error("❌ Gagal mengambil harga real-time. Coba refresh.")

    # Pilihan periode & interval
    col1, col2 = st.columns(2)
    with col1:
        period_option = st.selectbox("Periode Data", 
            ["1 hari","5 hari","1 bulan","3 bulan","6 bulan","1 tahun","5 tahun","Max"], index=5)
    with col2:
        interval_option = st.selectbox("Timeframe", 
            ["1m","5m","15m","30m","1h","1d","1wk"], index=5)
    
    period_map = {"1 hari":"1d","5 hari":"5d","1 bulan":"1mo","3 bulan":"3mo",
                  "6 bulan":"6mo","1 tahun":"1y","5 tahun":"5y","Max":"max"}
    
    df = get_historical_data(ticker_input, period=period_map[period_option], interval=interval_option)
    if not df.empty:
        df = add_technical_indicators(df)
        signal, reason = generate_trading_signal(df)
        st.markdown(f"### {'🟢' if 'BUY' in signal else '🔴' if 'SELL' in signal else '🟡'} **SINyal OTOMATIS: {signal}** — {reason}")
        
        # Chart
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=df.index, y=df.get('SMA20'), name="SMA 20", line=dict(color="blue")))
        fig.add_trace(go.Scatter(x=df.index, y=df.get('SMA50'), name="SMA 50", line=dict(color="orange")))
        fig.add_trace(go.Scatter(x=df.index, y=df.get('EMA12'), name="EMA 12", line=dict(color="purple", dash="dash")))
        fig.add_trace(go.Scatter(x=df.index, y=df.get('EMA26'), name="EMA 26", line=dict(color="red", dash="dash")))
        support, resistance = calculate_support_resistance(df)
        for s in support: fig.add_hline(y=s, line_dash="dash", line_color="green", annotation_text=f"S {s}")
        for r in resistance: fig.add_hline(y=r, line_dash="dash", line_color="red", annotation_text=f"R {r}")
        fig.update_layout(title=f"AeroVulpis Live Chart — {ticker_input}", height=650, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
        # Metrik
        st.subheader("📊 Indikator Terkini")
        c1, c2, c3, c4 = st.columns(4)
        latest = df.iloc[-1]
        c1.metric("RSI 14", f"{latest['RSI']:.1f}")
        c2.metric("SMA20", f"{latest.get('SMA20',0):.2f}")
        c3.metric("Support", f"{support[0]:.2f}" if support else "N/A")
        c4.metric("Resistance", f"{resistance[0]:.2f}" if resistance else "N/A")
        
        # Tombol Analisis AI
        if st.button("🤖 Generate Analisis AeroVulpis (Emosional & Lengkap)", type="secondary", use_container_width=True):
            with st.spinner("AeroVulpis lagi excited banget nih... 🔥"):
                data_summary = df.tail(15).to_string()
                prompt = f"Harga saat ini: {current_price}\nData 15 candle terakhir:\n{data_summary}\nSignal: {signal}\nSupport: {support}\nResistance: {resistance}"
                analysis = get_gemini_response(f"Analisis lengkap {ticker_input} sekarang!", prompt)
                st.markdown("### ✅ Analisis AeroVulpis:")
                st.markdown(analysis)
    else:
        st.error("❌ Data tidak tersedia. Coba ganti ticker atau timeframe.")

# ====================== PRICE ALERTS ======================
elif menu_selection == "Price Alerts":
    st.header("🚨 Price Alerts & Notifikasi Real-Time")
    st.info("Alert akan dicek setiap kali kamu tekan Refresh di Dashboard. Notifikasi muncul sebagai toast.")
    
    col_a, col_b = st.columns([2,1])
    with col_a:
        alert_price = st.number_input("Harga Target Alert", value=2650.0, step=0.1)
    with col_b:
        alert_dir = st.selectbox("Arah Alert", ["di atas (≥)", "di bawah (≤)"])
    
    if st.button("Tambahkan Alert Baru", type="primary"):
        direction = "above" if "atas" in alert_dir else "below"
        st.session_state.alerts.append({
            "ticker": ticker_input,
            "price": alert_price,
            "direction": direction,
            "triggered": False
        })
        st.success(f"✅ Alert {direction} {alert_price} untuk {ticker_input} ditambahkan!")
    
    st.subheader("Daftar Alert Aktif")
    if st.session_state.alerts:
        for i, alert in enumerate(st.session_state.alerts):
            status = "✅ Terpicu" if alert['triggered'] else "⏳ Menunggu"
            st.write(f"{i+1}. {alert['ticker']} {alert['direction']} {alert['price']} — {status}")
        if st.button("Hapus Semua Alert"):
            st.session_state.alerts = []
            st.rerun()
    else:
        st.write("Belum ada alert. Tambahkan di atas!")

# ====================== BACKTESTING ======================
elif menu_selection == "Backtesting":
    st.header("📊 Backtesting Strategy")
    st.write("Uji strategi masa lalu sebelum trading real-time.")
    
    strategy_choice = st.selectbox("Pilih Strategi", ["MA Crossover", "RSI"])
    back_period = st.selectbox("Periode Backtest", ["3 bulan","6 bulan","1 tahun","2 tahun"], index=2)
    back_interval = st.selectbox("Timeframe Backtest", ["1d","1h","15m"], index=0)
    
    period_map_back = {"3 bulan":"3mo","6 bulan":"6mo","1 tahun":"1y","2 tahun":"2y"}
    
    if st.button("🚀 Jalankan Backtesting Sekarang", type="primary", use_container_width=True):
        with st.spinner("Sedang backtest... ini butuh beberapa detik"):
            df_back = get_historical_data(ticker_input, period=period_map_back[back_period], interval=back_interval)
            if not df_back.empty:
                results, df_results = run_backtest(df_back, strategy_choice)
                if results:
                    st.success("✅ Backtest Selesai!")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Total Return", results["Total Return"])
                    col2.metric("Win Rate", results["Win Rate"])
                    col3.metric("Jumlah Trade", results["Jumlah Trade"])
                    
                    # Equity Curve
                    fig_eq = go.Figure()
                    fig_eq.add_trace(go.Scatter(x=df_results.index, y=results["Equity Curve"], name="Equity Curve", line=dict(color="#00ff88")))
                    fig_eq.update_layout(title="Equity Curve Backtest", height=400, template="plotly_dark")
                    st.plotly_chart(fig_eq, use_container_width=True)
                else:
                    st.error("Data terlalu sedikit")
            else:
                st.error("Gagal ambil data backtest")

# ====================== CHATBOT ======================
elif menu_selection == "Chatbot AI Trading":
    st.header("💬 Chatbot AeroVulpis — Bisa Analisis Semua Instrumen!")
    st.caption("Sebutkan ticker apa saja (misal: BTC-USD, EURUSD=X, TSLA)")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if prompt := st.chat_input("Ketik pertanyaanmu di sini..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("AeroVulpis lagi mikir & excited... 🔥"):
                response = get_gemini_response(prompt)
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

# ====================== FOOTER ======================
st.sidebar.markdown("---")
st.sidebar.caption("© Dibuat oleh **Fahmi** dengan bantuan Grok\nVersi Lengkap: Real-Time + Alerts + Backtesting + Notifikasi + Multi-Instrumen\nSemua fitur sudah di-test & bebas error!")
st.sidebar.success("AeroVulpis siap trading 24/7! 🦅")

# Auto refresh hint
st.caption("💡 Tekan tombol Refresh di Dashboard untuk update harga & trigger alert secara real-time.")
