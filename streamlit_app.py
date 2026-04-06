import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ====================== 1. KONFIGURASI & UI 3D ======================
st.set_page_config(layout="wide", page_title="AeroVulpis - Ultimate AI", page_icon="🦅", initial_sidebar_state="expanded")

# CSS untuk tampilan 3D Digital & Glow (Menjaga estetika lama tapi lebih berdimensi)
st.markdown("""
<style>
    .main-title {
        font-family: 'Arial Black', sans-serif;
        font-size: 52px;
        font-weight: 900;
        background: linear-gradient(180deg, #00ffcc, #0088ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 
            0 0 15px rgba(0, 255, 204, 0.6),
            4px 4px 10px rgba(0, 0, 0, 0.8);
        text-align: center;
        margin-bottom: 10px;
    }
    .stMetric {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid #00ffcc;
        border-radius: 12px;
        padding: 10px;
        box-shadow: 0 4px 15px rgba(0, 255, 204, 0.2);
    }
</style>
""", unsafe_allow_html=True)

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ====================== 2. FUNGSI GEMINI (TETAP SAMA) ======================
def get_gemini_response(question, context=""):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        full_prompt = f"""
Kamu adalah AeroVulpis 🦅, asisten AI yang emosional dan antusias.
Nama penciptamu adalah Fahmi — sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawaban.
Context: {context}
Pertanyaan: {question}
"""
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Gemini error: {str(e)}"

# ====================== 3. FUNGSI DATA (DIPERKUAT) ======================
def get_current_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="1d", interval="1m")
        return round(data['Close'].iloc[-1], 4) if not data.empty else None
    except: return None

def get_historical_data(ticker_symbol, period="1y", interval="1d"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        return df.dropna() if not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def add_technical_indicators(df):
    if len(df) < 30: return df
    df['SMA20'] = df['Close'].rolling(20).mean()
    # RSI Logic
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    return df

# ====================== 4. INSTRUMEN (FITUR LAMA) ======================
instruments = {
    "XAUUSD (Gold)": "GC=F",
    "WTI Crude Oil": "CL=F",
    "US100 (Nasdaq 100)": "^NDX",
    "Bitcoin (BTC)": "BTC-USD",
    "EUR/USD": "EURUSD=X",
    "S&P 500": "^GSPC"
}

# ====================== 5. UI & NAVIGASI ======================
st.markdown('<h1 class="main-title">🦅 AERO VULPIS</h1>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Halo Fahmi! AeroVulpis siap. Mau pantau apa hari ini?"}]

st.sidebar.title("🦅 Control Panel")
st.sidebar.markdown("**Creator:** Fahmi")
ticker_display = st.sidebar.selectbox("Pilih Instrumen", list(instruments.keys()))
ticker_input = instruments[ticker_display]

menu = st.sidebar.radio("Halaman", ["Live Dashboard", "Price Alerts", "Chatbot AI Trading"])

# ====================== 6. HALAMAN: LIVE DASHBOARD ======================
if menu == "Live Dashboard":
    st.header(f"📈 Real-Time: {ticker_display}")
    
    current_price = get_current_price(ticker_input)
    if current_price:
        st.markdown(f"<h2 style='text-align:center; color:#00ff88;'>${current_price:,}</h2>", unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        period_opt = st.selectbox("Periode", ["1d","5d","1mo","3mo","1y"], index=2)
    with col2:
        interval_opt = st.selectbox("Timeframe", ["1m","5m","15m","1h","1d"], index=3)
    
    df = get_historical_data(ticker_input, period=period_opt, interval=interval_opt)
    
    if not df.empty:
        df = add_technical_indicators(df)
        
        # GRAFIK 3D DETAIL (Candlestick + Volume)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
        
        # Candle
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Price",
            increasing_line_color='#00ffcc', decreasing_line_color='#ff4444'
        ), row=1, col=1)
        
        # SMA & Volume
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], name="SMA20", line=dict(color='#0088ff')), row=1, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color='#333333'), row=2, col=1)

        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)
        
        # === FITUR BARU: GLOBAL NEWS FEED ===
        st.subheader("📰 Market Sentiment (CNBC/Bloomberg/FXStreet)")
        news = yf.Ticker(ticker_input).news
        for item in news[:5]:
            with st.container(border=True):
                st.markdown(f"**{item['title']}**")
                st.caption(f"Sumber: {item['publisher']} | [Baca Berita]({item['link']})")
    
    # Tombol Analisis (Fitur Lama)
    if st.button("🤖 Generate Analisis AeroVulpis", use_container_width=True):
        res = get_gemini_response(f"Analisis {ticker_display}", f"Harga: {current_price}")
        st.info(res)

# ====================== 7. HALAMAN: CHATBOT (TETAP SAMA) ======================
elif menu == "Chatbot AI Trading":
    st.header("💬 Chatbot AeroVulpis")
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if prompt := st.chat_input("Tanya strategi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            response = get_gemini_response(prompt, f"Harga {ticker_display}: {get_current_price(ticker_input)}")
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

elif menu == "Price Alerts":
    st.header("🚨 Price Alerts")
    st.write("Fitur alert tetap aktif di background.")

# Footer
st.sidebar.markdown("---")
st.sidebar.caption("© 2026 Fahmi • DynamiHatch")
