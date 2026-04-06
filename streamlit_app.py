import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ====================== KONFIGURASI TAMPILAN ======================
st.set_page_config(layout="wide", page_title="AeroVulpis - Pro Trader AI", page_icon="🦅")

# CSS Custom untuk Tema Dark & Glow Profesional
st.markdown("""
<style>
    .main-title {
        font-family: 'Inter', sans-serif;
        font-size: 60px;
        font-weight: 800;
        background: linear-gradient(135deg, #00F2FF 0%, #007BFF 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        filter: drop-shadow(0px 4px 10px rgba(0, 242, 255, 0.3));
    }
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        padding: 15px;
        border-radius: 10px;
        border: 1px solid rgba(0, 242, 255, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# API Key Gemini - Pastikan sudah diset di Secrets Streamlit/Replit
api_key = os.environ.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("⚠️ API Key belum terdeteksi. Chatbot mungkin tidak merespons.")

# ====================== FUNGSI DATA & ANALISIS ======================
def get_current_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return round(data['Close'].iloc[-1], 2)
        return None
    except:
        return None

def get_pro_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return pd.DataFrame()
        
        # Indikator Teknikal Detail
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        
        # Bollinger Bands
        std = df['Close'].rolling(window=20).std()
        df['BB_High'] = df['MA20'] + (std * 2)
        df['BB_Low'] = df['MA20'] - (std * 2)
        
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        return df
    except:
        return pd.DataFrame()

# ====================== SIDEBAR & NAVIGASI ======================
st.sidebar.markdown('<h1 style="color:#00F2FF;">🦅 AeroVulpis Pro</h1>', unsafe_allow_html=True)
st.sidebar.markdown("---")

instruments = {
    "GOLD (XAU/USD)": "GC=F",
    "BITCOIN (BTC/USD)": "BTC-USD",
    "NASDAQ 100": "^NDX",
    "EUR/USD": "EURUSD=X",
    "CRUDE OIL": "CL=F"
}

target_name = st.sidebar.selectbox("Pilih Asset", list(instruments.keys()))
ticker = instruments[target_name]

menu = st.sidebar.radio("Navigasi", ["📊 Market Dashboard", "💬 AeroVulpis AI Chat", "📰 Global News Feed"])

# ====================== HALAMAN 1: DASHBOARD ======================
if menu == "📊 Market Dashboard":
    st.markdown(f'<h1 class="main-title">AERO VULPIS MARKET</h1>', unsafe_allow_html=True)
    
    price = get_current_price(ticker)
    df = get_pro_data(ticker)
    
    if not df.empty:
        # Header Info
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Live Price", f"${price:,}")
        c2.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.2f}")
        c3.metric("High (24h)", f"${df['High'].max():,.2f}")
        c4.metric("Low (24h)", f"${df['Low'].min():,.2f}")

        # GRAFIK DETAIL (Subplots: Candle + Volume)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.03, row_heights=[0.7, 0.3])

        # Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Price",
            increasing_line_color='#00FFCC', decreasing_line_color='#FF3E3E'
        ), row=1, col=1)

        # MA Lines
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="MA 20", line=dict(color='#FFD700', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_High'], name="BB Upper", line=dict(color='rgba(173, 216, 230, 0.2)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Low'], name="BB Lower", line=dict(color='rgba(173, 216, 230, 0.2)', width=1), fill='tonexty'), row=1, col=1)

        # Volume
        colors = ['#FF3E3E' if row['Open'] - row['Close'] >= 0 else '#00FFCC' for index, row in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color=colors), row=2, col=1)

        fig.update_layout(height=700, template="plotly_dark", xaxis_rangeslider_visible=False,
                          margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

# ====================== HALAMAN 2: CHATBOT ======================
elif menu == "💬 AeroVulpis AI Chat":
    st.header("🦅 Chat dengan AeroVulpis AI")
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Tanya tentang market..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            try:
                model = genai.GenerativeModel('gemini-1.5-flash')
                context = f"User sedang memantau {target_name}. Harga saat ini {get_current_price(ticker)}."
                full_prompt = f"System: Kamu AeroVulpis. Kreator: Fahmi. Context: {context}. User: {prompt}"
                response = model.generate_content(full_prompt)
                st.markdown(response.text)
                st.session_state.messages.append({"role": "assistant", "content": response.text})
            except Exception as e:
                st.error("Gagal konek ke otak AI. Cek API Key.")

# ====================== HALAMAN 3: NEWS FEED ======================
elif menu == "📰 Global News Feed":
    st.header(f"Berita Terkini {target_name}")
    st.caption("Sumber: CNBC, Bloomberg, FXStreet (via Yahoo Finance Feed)")
    
    news_ticker = yf.Ticker(ticker)
    news_items = news_ticker.news
    
    if news_items:
        for item in news_items[:10]:
            with st.expander(f"📌 {item['title']}"):
                st.write(f"**Publisher:** {item['publisher']}")
                st.write(f"**Waktu:** {datetime.fromtimestamp(item['provider_publish_time'])}")
                st.write(f"[Klik untuk baca selengkapnya]({item['link']})")
    else:
        st.info("Tidak ada berita spesifik saat ini. Cek kembali nanti.")

# FOOTER
st.sidebar.markdown("---")
st.sidebar.write("🟢 **System Status: Active**")
st.sidebar.caption("Dibuat oleh Fahmi untuk DynamiHatch")
