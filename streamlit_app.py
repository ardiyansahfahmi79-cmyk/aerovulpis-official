import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# ====================== 1. KONFIGURASI ENGINE & UI ======================
st.set_page_config(
    layout="wide", 
    page_title="AeroVulpis Ultimate 2026", 
    page_icon="🦅", 
    initial_sidebar_state="expanded"
)

# CSS MAGIC: Tampilan Digital 3D, Glow Neon, & Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;900&family=Inter:wght@300;600&display=swap');
    
    .stApp {
        background-color: #050505;
        color: #e0e0e0;
    }
    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 55px;
        font-weight: 900;
        background: linear-gradient(180deg, #00fff2 0%, #0077ff 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-align: center;
        filter: drop-shadow(0 0 15px rgba(0, 255, 242, 0.5));
        margin-bottom: 5px;
    }
    .sub-text {
        text-align: center;
        font-family: 'Inter', sans-serif;
        font-size: 18px;
        color: #00ccff;
        margin-bottom: 30px;
        letter-spacing: 2px;
    }
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(0, 255, 242, 0.3);
        padding: 15px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5), inset 0 0 10px rgba(0, 255, 242, 0.1);
        transition: 0.3s;
    }
    div[data-testid="stMetric"]:hover {
        transform: translateY(-5px);
        border-color: #00fff2;
    }
    .stButton>button {
        background: linear-gradient(45deg, #0077ff, #00fff2);
        color: white;
        border: none;
        border-radius: 10px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        box-shadow: 0 0 20px #00fff2;
        transform: scale(1.02);
    }
</style>
""", unsafe_allow_html=True)

# KONEKSI GEMINI AI
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ====================== 2. CORE LOGIC (FUNGSI PRESISI) ======================

def get_pro_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return pd.DataFrame()
        
        # INDIKATOR TEKNIKAL DETAIL
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        
        # RSI 14
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        # Bollinger Bands
        std = df['Close'].rolling(window=20).std()
        df['BB_High'] = df['MA20'] + (std * 2)
        df['BB_Low'] = df['MA20'] - (std * 2)
        
        return df.dropna()
    except:
        return pd.DataFrame()

def get_realtime_price(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        # Ambil data 1 menit terakhir untuk presisi real-time
        current_data = t.history(period="1d", interval="1m")
        return round(current_data['Close'].iloc[-1], 2)
    except:
        return None

def get_gemini_analysis(question, context_data):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        full_prompt = f"""
System: Kamu adalah AeroVulpis 🦅, asisten trading AI paling canggih yang diciptakan oleh Fahmi.
Gaya bicara: Profesional, tajam, antusias, dan sangat detail.
Konteks Market Saat Ini: {context_data}

Tugas: Jawab pertanyaan user dengan analisis data yang presisi. 
Wajib sebutkan "Terima kasih Fahmi telah menciptakanku!" di setiap akhir jawaban.
User: {question}
"""
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Kesalahan sistem AI: {str(e)}"

# ====================== 3. INSTRUMEN & SESSION ======================
instruments = {
    "GOLD (XAU/USD)": "GC=F",
    "BITCOIN (BTC)": "BTC-USD",
    "NASDAQ 100": "^NDX",
    "EUR/USD": "EURUSD=X",
    "WTI CRUDE OIL": "CL=F",
    "SILVER": "SI=F"
}

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Sistem Aktif. Halo Fahmi, AeroVulpis siap menganalisis market."}]

# ====================== 4. SIDEBAR (DASHBOARD CONTROL) ======================
st.sidebar.markdown('<h2 style="color:#00fff2; font-family:Orbitron;">🦅 AeroVulpis v2.0</h2>', unsafe_allow_html=True)
st.sidebar.markdown("**Head Admin:** Fahmi (DynamiHatch)")
target_display = st.sidebar.selectbox("Pilih Asset Target", list(instruments.keys()))
ticker = instruments[target_display]

page = st.sidebar.radio("Navigation", ["⚡ Live Terminal", "🧠 AI Strategy Chat", "🚨 Price Alerts"])

# ====================== 5. HALAMAN 1: LIVE TERMINAL ======================
if page == "⚡ Live Terminal":
    st.markdown('<h1 class="main-title">AERO VULPIS TERMINAL</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-text">HIGH-PRECISION REAL-TIME DATA STREAM</p>', unsafe_allow_html=True)

    live_p = get_realtime_price(ticker)
    df = get_pro_data(ticker)

    if not df.empty:
        # METRIC ROW (3D Style)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("CURRENT PRICE", f"${live_p:,}")
        m2.metric("RSI (14)", f"{df['RSI'].iloc[-1]:.2f}")
        m3.metric("24h HIGH", f"${df['High'].max():,.1f}")
        m4.metric("VOLATILITY", "HIGH" if df['RSI'].iloc[-1] > 70 or df['RSI'].iloc[-1] < 30 else "STABLE")

        # GRAFIK 3D ULTRA DETAIL (Plotly)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.03, row_heights=[0.75, 0.25])

        # Candlestick Layer
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Market",
            increasing_line_color='#00fff2', decreasing_line_color='#ff0066',
            increasing_fillcolor='#00fff2', decreasing_fillcolor='#ff0066'
        ), row=1, col=1)

        # Technical Overlays
        fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], name="MA 20", line=dict(color='#ffcc00', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_High'], name="Bollinger Top", line=dict(color='rgba(0, 255, 242, 0.2)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Low'], name="Bollinger Low", line=dict(color='rgba(0, 255, 242, 0.2)', width=1), fill='tonexty'), row=1, col=1)

        # Volume Layer
        v_colors = ['#ff0066' if r['Open'] > r['Close'] else '#00fff2' for i, r in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color=v_colors, opacity=0.8), row=2, col=1)

        fig.update_layout(height=650, template="plotly_dark", xaxis_rangeslider_visible=False,
                          paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                          margin=dict(l=10, r=10, t=20, b=10))
        st.plotly_chart(fig, use_container_width=True)

        # NEW FEATURE: GLOBAL NEWS FEED
        st.markdown("### 📰 Global Market Sentiment")
        try:
            news_feed = yf.Ticker(ticker).news
            for n in news_feed[:5]:
                with st.container(border=True):
                    st.markdown(f"**{n['title']}**")
                    st.caption(f"Source: {n['publisher']} | [Link]({n['link']})")
        except:
            st.info("News stream is syncing...")

# ====================== 6. HALAMAN 2: AI CHAT ======================
elif page == "🧠 AI Strategy Chat":
    st.header("🦅 AeroVulpis Intelligence")
    st.caption("Berdiskusi strategi Smart Money Concept dengan AI Fahmi")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if p_chat := st.chat_input("Apa rencana trading kita hari ini?"):
        st.session_state.messages.append({"role": "user", "content": p_chat})
        with st.chat_message("user"): st.markdown(p_chat)

        with st.chat_message("assistant"):
            price = get_realtime_price(ticker)
            context = f"Asset: {target_display}, Price: {price}, Year: 2026."
            res = get_gemini_analysis(p_chat, context)
            st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})

# ====================== 7. HALAMAN 3: ALERTS ======================
elif page == "🚨 Price Alerts":
    st.header("Price Alert System")
    st.info("Fitur alert sedang dalam sinkronisasi dengan database DynamiHatch.")
    st.text_input("Set Price Target ($)")
    st.button("Set Alarm")

# FOOTER (The Signature)
st.sidebar.markdown("---")
st.sidebar.write("🟢 SYSTEM: ONLINE")
st.sidebar.caption("DynamiHatch Alpha Build v2.1")
st.sidebar.caption("© 2026 Fahmi • AeroVulpis")
        
