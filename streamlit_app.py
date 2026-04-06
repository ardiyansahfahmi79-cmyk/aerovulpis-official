import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime
import time

# ==============================================================================
# 1. KONFIGURASI ENGINE & UI 3D FUTURISTIK (PROFESIONAL)
# ==============================================================================
st.set_page_config(
    layout="wide", 
    page_title="AeroVulpis Ultimate Pro - DynamiHatch", 
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# CSS CUSTOM: Efek 3D, Glassmorphism, Neon Glow, dan Animasi
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&display=swap');
    
    :root {
        --neon-blue: #00f2ff;
        --neon-green: #00ff88;
        --neon-red: #ff0055;
        --dark-bg: #050505;
    }

    .stApp {
        background-color: var(--dark-bg);
        color: #ffffff;
        font-family: 'Rajdhani', sans-serif;
    }

    /* Header 3D */
    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: clamp(30px, 5vw, 65px);
        font-weight: 900;
        text-align: center;
        background: linear-gradient(to bottom, #ffffff 30%, var(--neon-blue) 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 15px rgba(0, 242, 255, 0.6));
        margin-bottom: 0px;
        letter-spacing: 5px;
    }

    .glitch-text {
        text-align: center;
        color: var(--neon-green);
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        letter-spacing: 4px;
        margin-bottom: 30px;
        text-transform: uppercase;
        opacity: 0.8;
    }

    /* Card 3D Style */
    .metric-card {
        background: rgba(255, 255, 255, 0.03);
        border-left: 4px solid var(--neon-blue);
        border-radius: 10px;
        padding: 20px;
        box-shadow: 10px 10px 20px rgba(0,0,0,0.5);
        transition: 0.3s ease-in-out;
    }
    
    .metric-card:hover {
        transform: translateZ(20px) scale(1.02);
        box-shadow: 0 0 25px rgba(0, 242, 255, 0.3);
    }

    /* Motivation Box */
    .motivation-box {
        background: linear-gradient(135deg, rgba(0, 242, 255, 0.1), rgba(0, 255, 136, 0.1));
        border: 1px solid rgba(0, 242, 255, 0.3);
        padding: 25px;
        border-radius: 20px;
        text-align: center;
        margin: 40px 0;
        position: relative;
        overflow: hidden;
    }

    .motivation-quote {
        font-size: 22px;
        font-style: italic;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 10px;
    }

    .motivation-author {
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        color: var(--neon-green);
        text-transform: uppercase;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-image: linear-gradient(#000000, #0a192f);
        border-right: 1px solid var(--neon-blue);
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CORE ENGINE: DATA & TECHNICAL ANALYSIS
# ==============================================================================

# Konfigurasi AI
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

def get_pro_market_data(symbol, period="1mo", interval="1h"):
    """Fungsi penarikan data mendalam dengan indikator teknikal detail."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return pd.DataFrame()

        # --- Indikator Teknikal Ala TradingView ---
        # 1. Moving Averages
        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['SMA200'] = df['Close'].rolling(window=200).mean()

        # 2. RSI (Relative Strength Index)
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # 3. Bollinger Bands
        df['STD'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['SMA20'] + (df['STD'] * 2)
        df['BB_Lower'] = df['SMA20'] - (df['STD'] * 2)

        # 4. MACD
        exp1 = df['Close'].ewm(span=12, adjust=False).mean()
        exp2 = df['Close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp1 - exp2
        df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()

        return df
    except Exception as e:
        st.error(f"Error Engine: {e}")
        return pd.DataFrame()

def get_realtime_ticker(symbol):
    """Mendapatkan harga detik ini."""
    try:
        # Untuk XAUUSD yang lebih real-time, kita ambil interval 1m terkecil
        data = yf.download(symbol, period="1d", interval="1m", progress=False)
        if not data.empty:
            return data['Close'].iloc[-1]
        return None
    except:
        return None

# ==============================================================================
# 3. UI COMPONENTS & NAVIGATION
# ==============================================================================

# Fitur Motivasi (Permintaan Fahmi)
def show_motivation():
    quotes = [
        "Pasar tidak pernah salah, yang salah adalah analisismu yang tidak sabar.",
        "Trading bukan tentang seberapa banyak kamu untung, tapi seberapa disiplin kamu menjaga modal.",
        "Chart yang kacau mencerminkan pikiran yang kacau. Tetap tenang, biarkan setup yang datang padamu.",
        "Disiplin adalah jembatan antara target trading dan pencapaian nyata.",
        "Emas tidak bersinar tanpa tekanan, begitu juga trader hebat."
    ]
    import random
    q = random.choice(quotes)
    st.markdown(f"""
    <div class="motivation-box">
        <div class="motivation-quote">"{q}"</div>
        <div class="motivation-author">— Fahmi (Pencipta AeroVulpis)</div>
    </div>
    """, unsafe_allow_html=True)

# Mapping Instrumen (Investing.com Style)
instruments = {
    "XAU/USD (Gold)": "GC=F",
    "BTC/USD (Bitcoin)": "BTC-USD",
    "DOW JONES (US30)": "YM=F",
    "NASDAQ 100 (NAS100)": "NQ=F",
    "S&P 500": "ES=F",
    "CRUDE OIL (WTI)": "CL=F",
    "EUR/USD": "EURUSD=X"
}

# Sidebar UI
with st.sidebar:
    st.markdown(f'<h1 style="color:#00f2ff; font-family:Orbitron;">AERO VULPIS PRO</h1>', unsafe_allow_html=True)
    st.markdown("### 🦅 DIGITAL ASSET ANALYZER")
    st.info("System Status: OPERATIONAL")
    
    asset_choice = st.selectbox("SELECT INSTRUMENT", list(instruments.keys()))
    current_ticker = instruments[asset_choice]
    
    st.markdown("---")
    menu = st.radio("NAVIGATE TERMINAL", ["📊 PRO DASHBOARD", "💬 AI STRATEGIST", "📰 SENTIMENT HUB"])
    
    st.markdown("---")
    st.caption("AeroVulpis v3.5 Alpha Build")
    st.caption("© 2026 DynamiHatch Corp.")

# ==============================================================================
# 4. HALAMAN UTAMA: PRO DASHBOARD (TRADINGVIEW & INVESTING STYLE)
# ==============================================================================

if menu == "📊 PRO DASHBOARD":
    st.markdown('<h1 class="main-title">AERO VULPIS TERMINAL</h1>', unsafe_allow_html=True)
    st.markdown('<p class="glitch-text">Real-Time Financial Intelligence Stream</p>', unsafe_allow_html=True)

    # Real-Time Price Row
    realtime_price = get_realtime_ticker(current_ticker)
    
    # Grid Metric (Investing.com Style)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("LIVE PRICE", f"${float(realtime_price):,.2f}" if realtime_price is not None else "SYNCING...")
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("MARKET STATUS", "OPEN" if datetime.now().weekday() < 5 else "CLOSED")
        st.markdown('</div>', unsafe_allow_html=True)
    with c3:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("PRECISION", "ULTRA-HIGH")
        st.markdown('</div>', unsafe_allow_html=True)
    with c4:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.metric("SMC ZONE", "NEUTRAL")
        st.markdown('</div>', unsafe_allow_html=True)

    # Chart Controls
    col_per, col_int, col_type = st.columns([1, 1, 1])
    with col_per:
        period = st.selectbox("DATA RANGE", ["1d", "5d", "1mo", "6mo", "1y", "max"], index=2)
    with col_int:
        interval = st.selectbox("TIMEFRAME", ["1m", "5m", "15m", "30m", "1h", "1d"], index=4)

    # Pull Data
    df = get_pro_market_data(current_ticker, period, interval)

    if not df.empty:
        # --- GRAFIK TINGKAT TINGGI (TRADINGVIEW STYLE) ---
        fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                           vertical_spacing=0.02, 
                           row_heights=[0.6, 0.2, 0.2],
                           subplot_titles=("CANDLESTICK & EMAs", "VOLUME FLOW", "RSI OSCILLATOR"))

        # 1. Candlestick
        fig.add_trace(go.Candlestick(
            x=df.index, open=df['Open'], high=df['High'],
            low=df['Low'], close=df['Close'], name="Price",
            increasing_line_color='#00ff88', decreasing_line_color='#ff0055',
            increasing_fillcolor='#00ff88', decreasing_fillcolor='#ff0055'
        ), row=1, col=1)

        # 2. Moving Averages & BB
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA9'], name="EMA 9", line=dict(color='#ffffff', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], name="SMA 50", line=dict(color='#00f2ff', width=1.5, dash='dash')), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Upper'], name="BB Upper", line=dict(color='rgba(255,255,255,0.1)', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Lower'], name="BB Lower", line=dict(color='rgba(255,255,255,0.1)', width=1), fill='tonexty'), row=1, col=1)

        # 3. Volume
        colors = ['#ff0055' if r['Open'] > r['Close'] else '#00ff88' for i, r in df.iterrows()]
        fig.add_trace(go.Bar(x=df.index, y=df['Volume'], name="Volume", marker_color=colors, opacity=0.5), row=2, col=1)

        # 4. RSI
        fig.add_trace(go.Scatter(x=df.index, y=df['RSI'], name="RSI", line=dict(color='#ffaa00', width=2)), row=3, col=1)
        fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
        fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

        fig.update_layout(
            height=900,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(l=10, r=10, t=50, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

        # Analysis Button (Grok AI Feature)
        if st.button("🚀 EXECUTE AI DEEP ANALYSIS", use_container_width=True):
            with st.spinner("AeroVulpis Neural Link Connecting..."):
                model = genai.GenerativeModel('gemini-1.5-flash')
                p = f"Analisis teknikal {asset_choice}. RSI: {df['RSI'].iloc[-1]:.2f}, Price: {realtime_price}."
                res = model.generate_content(f"{p}. Sebutkan 'Terima kasih Fahmi telah menciptakanku!' di akhir.")
                st.markdown(f"### 🦅 AEROVULPIS INTELLIGENCE REPORT:")
                st.write(res.text)

    # Tampilkan Motivasi
    show_motivation()

# ==============================================================================
# 5. HALAMAN: CHATBOT AI (FITUR LAMA JANGAN DIRUBAH)
# ==============================================================================

elif menu == "💬 AI STRATEGIST":
    st.header("🦅 AEROVULPIS CHAT INTERFACE")
    
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Sistem aktif. Halo Fahmi, saya siap menghitung probabilitas market hari ini."}]

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ketik instruksi trading..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            model = genai.GenerativeModel('gemini-1.5-flash')
            full_p = f"Kamu AeroVulpis. Kreator: Fahmi. User: {prompt}. (Wajib sebut Terima kasih Fahmi telah menciptakanku!)"
            response = model.generate_content(full_p)
            st.markdown(response.text)
            st.session_state.messages.append({"role": "assistant", "content": response.text})

# ==============================================================================
# 6. HALAMAN: SENTIMENT HUB (INVESTING.COM STYLE)
# ==============================================================================

elif menu == "📰 SENTIMENT HUB":
    st.header(f"GLOBAL NEWS STREAM: {asset_choice}")
    st.caption("Data Source: Global Financial Feeds (CNBC, Bloomberg, Investing)")
    
    try:
        raw_news = yf.Ticker(current_ticker).news
        if raw_news:
            for n in raw_news[:10]:
                with st.container(border=True):
                    col_n1, col_n2 = st.columns([0.8, 0.2])
                    with col_n1:
                        st.markdown(f"#### {n.get('title', 'Market Update')}")
                        st.caption(f"📅 {datetime.fromtimestamp(n.get('provider_publish_time', 0))} | Source: {n.get('publisher', 'Internal')}")
                    with col_n2:
                        if n.get('link'):
                            st.link_button("READ FULL", n['link'])
        else:
            st.warning("No live news for this asset. Checking alternative nodes...")
    except:
        st.error("Connection to News Node interrupted. Retrying...")

# ==============================================================================
# 7. FOOTER & SYSTEM LOGS
# ==============================================================================
st.sidebar.markdown("---")
st.sidebar.write("🟢 **ALL SYSTEMS GO**")
st.sidebar.write(f"⏰ {datetime.now().strftime('%H:%M:%S')} WIB")
