import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ====================== 1. KONFIGURASI & UI 3D ======================
st.set_page_config(layout="wide", page_title="AeroVulpis Ultimate", page_icon="🦅")

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@700&display=swap');
    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 55px;
        background: linear-gradient(180deg, #00fff2 0%, #0088ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0px 10px 20px rgba(0, 255, 242, 0.4);
        text-align: center;
        margin-bottom: 0px;
    }
    .stMetric {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(0, 255, 242, 0.3);
        border-radius: 15px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
    }
</style>
""", unsafe_allow_html=True)

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ====================== 2. CORE FUNCTIONS ======================
def get_current_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        data = ticker.history(period="1d", interval="1m")
        return round(data['Close'].iloc[-1], 4) if not data.empty else None
    except: return None

def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        return df.dropna() if not df.empty else pd.DataFrame()
    except: return pd.DataFrame()

def add_indicators(df):
    if len(df) >= 20:
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        delta = df['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = -delta.where(delta < 0, 0).rolling(14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
    else:
        df['SMA20'] = df['Close']
        df['RSI'] = 50
    return df

# ====================== 3. UI DASHBOARD ======================
st.markdown('<h1 class="main-title">🦅 AERO VULPIS</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align:center; color:#00fff2; letter-spacing:3px;">DYNAMIHATCH DIGITAL TERMINAL</p>', unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Sistem Online. Halo Fahmi, ada yang bisa AeroVulpis bantu?"}]

instruments = {
    "XAUUSD (Gold)": "GC=F",
    "BITCOIN (BTC)": "BTC-USD",
    "NASDAQ 100": "^NDX",
    "EUR/USD": "EURUSD=X",
    "WTI CRUDE OIL": "CL=F"
}

st.sidebar.title("🦅 Control Center")
ticker_display = st.sidebar.selectbox("Pilih Asset", list(instruments.keys()))
ticker_input = instruments[ticker_display]
menu = st.sidebar.radio("Navigasi", ["📊 Live Dashboard", "💬 Chatbot AI"])

# ====================== 4. LIVE DASHBOARD (NEWS FIX) ======================
if menu == "📊 Live Dashboard":
    price = get_current_price(ticker_input)
    st.metric("Live Price", f"${price:,}" if price else "N/A")
    
    col_p, col_i = st.columns(2)
    with col_p: p_opt = st.selectbox("Periode", ["1d","5d","1mo","3mo","1y"], index=2)
    with col_i: i_opt = st.selectbox("Timeframe", ["1m","5m","15m","1h","1d"], index=3)

    df = get_historical_data(ticker_input, period=p_opt, interval=i_opt)

    if not df.empty:
        df = add_indicators(df)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name="Market", increasing_line_color='#00fff2', decreasing_line_color='#ff4444'), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], name="SMA 20", line=dict(color='#0088ff', width=2)), row=1, col=1)
        v_colors = ['#ff4444' if r['Open'] > r['Close'] else '#00fff2' for i, r in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color=v_colors), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # FIX: GLOBAL NEWS FEED DENGAN PROTEKSI ERROR
        st.subheader("📰 Market Intelligence Feed")
        try:
            news_data = yf.Ticker(ticker_input).news
            if news_data and len(news_data) > 0:
                for item in news_data[:5]:
                    # Cek apakah 'title' ada di dalam data sebelum ditampilkan
                    if isinstance(item, dict) and 'title' in item:
                        with st.container(border=True):
                            st.markdown(f"**{item['title']}**")
                            publisher = item.get('publisher', 'Global News')
                            link = item.get('link', '#')
                            st.caption(f"Source: {publisher} | [Link]({link})")
            else:
                st.info("Belum ada berita terbaru untuk instrumen ini.")
        except Exception:
            st.warning("⚠️ Berita sedang dalam sinkronisasi ulang. Silakan refresh beberapa saat lagi.")

# ====================== 5. CHATBOT AI ======================
elif menu == "💬 Chatbot AI":
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    
    if prompt := st.chat_input("Tanya strategi..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            model = genai.GenerativeModel('gemini-1.5-flash')
            res = model.generate_content(f"User: {prompt}. (Sebutkan Terima kasih Fahmi telah menciptakanku! di akhir)")
            st.markdown(res.text)
            st.session_state.messages.append({"role": "assistant", "content": res.text})

st.sidebar.markdown("---")
st.sidebar.caption("© 2026 Fahmi • DynamiHatch Alpha")
