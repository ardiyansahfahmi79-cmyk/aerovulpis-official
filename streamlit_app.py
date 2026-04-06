import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis - AI Trading Assistant", page_icon="🦅", initial_sidebar_state="expanded")

# CSS untuk tombol Refresh biru 3D
st.markdown("""
<style>
    .stButton > button {
        background: linear-gradient(145deg, #007BFF, #0056b3);
        color: white;
        border: none;
        border-radius: 12px;
        padding: 14px 28px;
        font-size: 18px;
        font-weight: bold;
        box-shadow: 0 8px 15px rgba(0, 123, 255, 0.4);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        box-shadow: 0 12px 20px rgba(0, 123, 255, 0.5);
        transform: translateY(-3px);
    }
</style>
""", unsafe_allow_html=True)

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ====================== FUNGSI GEMINI ======================
def get_gemini_response(question, context=""):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        full_prompt = f"""
Kamu adalah AeroVulpis 🦅, AI asisten yang emosional, antusias, dan jujur.
Nama penciptamu adalah Fahmi — sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jika relevan.

Personality: Pakai emoji, santai tapi membantu, seperti teman dekat.

Context: {context}
Pertanyaan: {question}

Jawab dalam bahasa Indonesia yang hidup dan jelas.
"""
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Gemini error: {str(e)}\nCoba refresh halaman."

# ====================== FUNGSI DATA ======================
def get_current_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.fast_info
        price = info.get('lastPrice') or info.get('regularMarketPrice')
        return round(float(price), 4) if price else None
    except:
        return None

def get_historical_data(ticker_symbol, period="1y", interval="1d"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        return df.dropna() if not df.empty else pd.DataFrame()
    except:
        return pd.DataFrame()

def add_technical_indicators(df):
    if len(df) < 30:
        return df
    df['SMA20'] = df['Close'].rolling(20).mean()
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
    s1 = round(pivot - (df['High'].iloc[-1] - pivot), 2)
    return [s1], [r1]

# ====================== INSTRUMEN ======================
instruments = {
    "XAUUSD (Gold)": "GC=F",
    "WTI Crude Oil": "CL=F",
    "US100 (Nasdaq 100)": "^NDX",
    "Bitcoin (BTC)": "BTC-USD",
    "EUR/USD": "EURUSD=X",
    "S&P 500": "^GSPC",
    "Silver": "SI=F"
}

# ====================== UI ======================
st.title("🦅 AeroVulpis - AI Trading Assistant")
st.caption("Real-Time • Berita • Alerts • Multi-Instrumen | Dibuat dengan ❤️ oleh **Fahmi**")

if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Halo! Aku AeroVulpis 🦅 buatan Fahmi. Mau pantau harga emas, minyak, atau instrumen lain?"}]

st.sidebar.title("🦅 AeroVulpis")
st.sidebar.markdown("**Pencipta:** Fahmi")
ticker_display = st.sidebar.selectbox("Pilih Instrumen", list(instruments.keys()))
ticker_input = instruments[ticker_display]

menu_selection = st.sidebar.radio("Pilih Halaman", 
    ["Live Dashboard", "Price Alerts", "Chatbot AI Trading"])

# ====================== LIVE DASHBOARD ======================
if menu_selection == "Live Dashboard":
    st.header(f"📈 Live Dashboard - {ticker_display}")
    
    if st.button("Refresh Semua Data Real-Time Sekarang", type="primary", use_container_width=True):
        st.rerun()
    
    current_price = get_current_price(ticker_input)
    if current_price:
        st.markdown(f"""
        <h2 style="text-align:center; color:#00ff88; margin:0;">
            🟢 Harga {ticker_display} Real-Time: <b>{current_price:.2f}</b>
        </h2>
        """, unsafe_allow_html=True)
    else:
        st.error("❌ Gagal mengambil harga real-time.")

    # Periode & Timeframe
    col1, col2 = st.columns(2)
    with col1:
        period_option = st.selectbox("Periode Data", ["1 hari","5 hari","1 bulan","3 bulan","6 bulan","1 tahun","Max"], index=5)
    with col2:
        interval_option = st.selectbox("Timeframe", ["1m","5m","15m","30m","1h","1d"], index=5)
    
    period_map = {"1 hari":"1d","5 hari":"5d","1 bulan":"1mo","3 bulan":"3mo","6 bulan":"6mo","1 tahun":"1y","Max":"max"}
    
    df = get_historical_data(ticker_input, period=period_map[period_option], interval=interval_option)
    
    if not df.empty:
        df = add_technical_indicators(df)
        
        # Chart sederhana
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Price"))
        fig.add_trace(go.Scatter(x=df.index, y=df.get('SMA20'), name="SMA 20", line=dict(color="blue")))
        support, resistance = calculate_support_resistance(df)
        for s in support:
            fig.add_hline(y=s, line_dash="dash", line_color="green", annotation_text=f"Support {s}")
        for r in resistance:
            fig.add_hline(y=r, line_dash="dash", line_color="red", annotation_text=f"Resistance {r}")
        
        fig.update_layout(title=f"AeroVulpis Chart — {ticker_display}", height=600, template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)
        
        # Indikator sederhana
        st.subheader("📊 Indikator Terkini")
        latest = df.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("RSI 14", f"{latest.get('RSI', 50):.1f}")
        c2.metric("SMA 20", f"{latest.get('SMA20', 0):.2f}")
        c3.metric("Support Terdekat", f"{support[0]:.2f}" if support else "N/A")
        
        # === FITUR BERITA ===
        st.subheader("📰 Berita Terkini")
        ticker_obj = yf.Ticker(ticker_input)
        news_list = ticker_obj.news[:6] if hasattr(ticker_obj, 'news') else []
        if news_list:
            for item in news_list:
                st.markdown(f"**{item.get('title', 'Berita') }**")
                st.caption(f"{item.get('publisher', 'Sumber')} • {item.get('published', '')}")
                if item.get('link'):
                    st.markdown(f"[Baca selengkapnya]({item['link']})")
                st.divider()
        else:
            st.info("Belum ada berita baru untuk instrumen ini saat ini.")
        
        # Tombol Analisis AI
        if st.button("🤖 Generate Analisis AeroVulpis", type="secondary", use_container_width=True):
            with st.spinner("AeroVulpis sedang menganalisis..."):
                data_summary = df.tail(10).to_string()
                prompt = f"Harga saat ini: {current_price}\nData terbaru:\n{data_summary}"
                analysis = get_gemini_response(f"Analisis {ticker_display} sekarang", prompt)
                st.markdown("### ✅ Analisis AeroVulpis:")
                st.markdown(analysis)
    else:
        st.error("❌ Data tidak tersedia. Coba ganti instrumen atau timeframe.")

# ====================== PRICE ALERTS ======================
elif menu_selection == "Price Alerts":
    st.header("🚨 Price Alerts")
    st.info("Alert akan dicek saat refresh di Dashboard.")
    
    col_a, col_b = st.columns([2,1])
    with col_a:
        alert_price = st.number_input("Harga Target", value=2650.0, step=0.1)
    with col_b:
        alert_dir = st.selectbox("Arah", ["di atas (≥)", "di bawah (≤)"])
    
    if st.button("Tambahkan Alert", type="primary"):
        direction = "above" if "atas" in alert_dir else "below"
        st.session_state.alerts.append({
            "ticker": ticker_display,
            "price": alert_price,
            "direction": direction,
            "triggered": False
        })
        st.success(f"Alert {direction} {alert_price} untuk {ticker_display} ditambahkan!")
    
    st.subheader("Daftar Alert")
    if st.session_state.alerts:
        for i, alert in enumerate(st.session_state.alerts):
            status = "✅ Terpicu" if alert['triggered'] else "⏳ Menunggu"
            st.write(f"{i+1}. {alert['ticker']} {alert['direction']} {alert['price']} — {status}")
        if st.button("Hapus Semua Alert"):
            st.session_state.alerts = []
            st.rerun()
    else:
        st.write("Belum ada alert.")

# ====================== CHATBOT ======================
elif menu_selection == "Chatbot AI Trading":
    st.header("💬 Chatbot AeroVulpis")
    st.caption("Tanya apa saja tentang harga emas, minyak, atau instrumen lain.")
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    
    if prompt := st.chat_input("Ketik pertanyaanmu..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("AeroVulpis lagi mikir..."):
                response = get_gemini_response(prompt)
                st.markdown(response)
        
        st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("© Dibuat oleh Fahmi • Versi diperbaiki dengan fitur berita")
st.caption("💡 Tekan tombol biru untuk update data real-time.")
