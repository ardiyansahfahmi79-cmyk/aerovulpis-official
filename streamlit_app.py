
import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import pytz
import ta
import time

# ==============================================================================
# 🦅 AERO VULPIS v3.2 ULTIMATE DIGITAL EDITION
# Diciptakan dengan visi masa depan oleh: Fahmi
# ==============================================================================

# --- KONFIGURASI HALAMAN ---
st.set_page_config(
    layout="wide", 
    page_title="AeroVulpis v3.2 - Ultimate Digital Edition by Fahmi", 
    page_icon="🦅", 
    initial_sidebar_state="expanded"
)

# --- CSS ULTIMATE DIGITAL (NEON 3D, GLASSMORPHISM, & ANIMASI) ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Rajdhani:wght@300;500;700&family=Share+Tech+Mono&display=swap');

    :root {
        --neon-green: #00ff88;
        --neon-blue: #00d4ff;
        --neon-purple: #bc13fe;
        --neon-red: #ff2a6d;
        --neon-gold: #FFD700;
        --glass-bg: rgba(10, 14, 23, 0.8);
        --glass-border: rgba(0, 212, 255, 0.25);
    }

    .stApp {
        background: radial-gradient(circle at center, #0d1117, #010409);
        color: #e6edf3;
    }

    /* 3D Neon Eagle Logo */
    .eagle-logo {
        font-size: 110px;
        text-align: center;
        filter: drop-shadow(0 0 20px var(--neon-blue)) drop-shadow(0 0 40px var(--neon-purple));
        animation: pulse 2.5s infinite ease-in-out;
        margin-bottom: 15px;
        cursor: default;
    }

    @keyframes pulse {
        0% { transform: scale(1); filter: drop-shadow(0 0 20px var(--neon-blue)); }
        50% { transform: scale(1.15); filter: drop-shadow(0 0 45px var(--neon-purple)); }
        100% { transform: scale(1); filter: drop-shadow(0 0 20px var(--neon-blue)); }
    }

    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 68px;
        font-weight: 900;
        text-align: center;
        background: linear-gradient(to right, var(--neon-green), var(--neon-blue), var(--neon-purple), var(--neon-gold));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 4px 4px 20px rgba(0, 212, 255, 0.5);
        letter-spacing: 8px;
        margin-bottom: 0;
    }

    .sub-title {
        text-align: center;
        font-family: 'Rajdhani', sans-serif;
        color: var(--neon-blue);
        letter-spacing: 6px;
        font-weight: 700;
        text-transform: uppercase;
        margin-top: -10px;
        margin-bottom: 30px;
    }

    /* Glassmorphism Cards */
    .glass-card {
        background: var(--glass-bg);
        backdrop-filter: blur(20px);
        -webkit-backdrop-filter: blur(20px);
        border: 1px solid var(--glass-border);
        border-radius: 25px;
        padding: 30px;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.7), inset 0 0 25px rgba(0, 212, 255, 0.08);
        margin-bottom: 25px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
    }
    .glass-card:hover {
        transform: translateY(-8px) scale(1.01);
        border-color: var(--neon-blue);
        box-shadow: 0 20px 60px rgba(0, 212, 255, 0.25);
    }

    .digital-font {
        font-family: 'Orbitron', sans-serif;
        color: var(--neon-green);
        text-shadow: 0 0 12px var(--neon-green);
    }

    .rajdhani-font {
        font-family: 'Rajdhani', sans-serif;
    }

    .share-tech {
        font-family: 'Share Tech Mono', monospace;
    }

    /* Futuristic Footer */
    .footer-digital {
        background: rgba(0, 0, 0, 0.6);
        backdrop-filter: blur(20px);
        border-top: 2px solid var(--glass-border);
        padding: 40px;
        text-align: center;
        font-family: 'Rajdhani', sans-serif;
        letter-spacing: 4px;
        color: #ccc;
        margin-top: 80px;
        border-radius: 30px 30px 0 0;
        box-shadow: 0 -10px 40px rgba(0, 0, 0, 0.5);
    }

    /* Buttons Customization */
    .stButton>button {
        width: 100%;
        background: linear-gradient(45deg, #0055ff, #00d4ff, #bc13fe) !important;
        border: none !important;
        color: white !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 900 !important;
        border-radius: 15px !important;
        padding: 18px !important;
        box-shadow: 0 6px 25px rgba(0, 85, 255, 0.5) !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 3px;
    }
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 10px 35px rgba(0, 212, 255, 0.7) !important;
        filter: brightness(1.3);
    }

    /* Sidebar Customization */
    [data-testid="stSidebar"] {
        background-color: rgba(10, 14, 23, 0.99);
        border-right: 2px solid var(--glass-border);
    }

    /* Metric Styling */
    [data-testid="stMetricValue"] {
        font-family: 'Share Tech Mono', monospace !important;
        color: var(--neon-green) !important;
        text-shadow: 0 0 10px var(--neon-green) !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 10px; }
    ::-webkit-scrollbar-track { background: #010409; }
    ::-webkit-scrollbar-thumb { background: linear-gradient(var(--neon-blue), var(--neon-purple)); border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

# --- KONFIGURASI API GEMINI ---
api_key = st.secrets.get("GOOGLE_API_KEY") or os.environ.get("GOOGLE_API_KEY")
if api_key:
    genai.configure(api_key=api_key)
else:
    st.warning("⚠️ GOOGLE_API_KEY tidak ditemukan. Fitur AI mungkin tidak berfungsi.")

# ====================== FUNGSI CORE (DATA & ANALISIS) ======================

@st.cache_data(ttl=60)
def get_market_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Ambil data 1m untuk real-time feel
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            hist = ticker.history(period="1d", interval="5m")
        
        if not hist.empty:
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            return {
                "price": round(float(latest['Close']), 4),
                "open": round(float(latest['Open']), 4),
                "high": round(float(latest['High']), 4),
                "low": round(float(latest['Low']), 4),
                "close": round(float(latest['Close']), 4),
                "prev_close": round(float(prev['Close']), 4),
                "volume": int(latest['Volume']),
                "time": hist.index[-1]
            }
        return None
    except Exception as e:
        st.error(f"Error Market Data: {e}")
        return None

@st.cache_data(ttl=60)
def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return pd.DataFrame()
        return df.dropna()
    except Exception as e:
        st.error(f"Error Historical Data: {e}")
        return pd.DataFrame()

def calculate_advanced_indicators(df):
    if len(df) < 50: return df
    
    # 1. RSI (Relative Strength Index)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    # 2. MACD (Moving Average Convergence Divergence)
    macd = ta.trend.MACD(df['Close'])
    df['MACD'] = macd.macd()
    df['MACD_Signal'] = macd.macd_signal()
    df['MACD_Diff'] = macd.macd_diff()
    # 3. SMA 20 & 50 (Simple Moving Average)
    df['SMA20'] = ta.trend.sma_indicator(df['Close'], window=20)
    df['SMA50'] = ta.trend.sma_indicator(df['Close'], window=50)
    # 4. EMA 9 & 200 (Exponential Moving Average)
    df['EMA9'] = ta.trend.ema_indicator(df['Close'], window=9)
    df['EMA200'] = ta.trend.ema_indicator(df['Close'], window=200)
    # 5. Bollinger Bands
    bb = ta.volatility.BollingerBands(df['Close'])
    df['BB_High'] = bb.bollinger_hband()
    df['BB_Low'] = bb.bollinger_lband()
    df['BB_Mid'] = bb.bollinger_mavg()
    # 6. Stochastic Oscillator
    stoch = ta.momentum.StochasticOscillator(df['High'], df['Low'], df['Close'])
    df['Stoch'] = stoch.stoch()
    df['Stoch_Signal'] = stoch.stoch_signal()
    # 7. ATR (Average True Range)
    df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'])
    # 8. ADX (Average Directional Index)
    adx = ta.trend.ADXIndicator(df['High'], df['Low'], df['Close'])
    df['ADX'] = adx.adx()
    # 9. Volume Analysis
    df['Vol_SMA'] = df['Volume'].rolling(20).mean()
    # 10. Ichimoku Cloud (Conversion Line)
    df['Ichimoku_Conv'] = ta.trend.ichimoku_conversion_line(df['High'], df['Low'])
    
    return df

def get_weighted_signal(df):
    if df.empty or 'RSI' not in df.columns: return 50, "NEUTRAL", []
    
    latest = df.iloc[-1]
    score = 0
    total_weight = 0
    reasons = []
    
    # RSI (Weight 15)
    total_weight += 15
    if latest['RSI'] < 30: 
        score += 15
        reasons.append("RSI Oversold (Kuat)")
    elif latest['RSI'] > 70: 
        score += 0
        reasons.append("RSI Overbought (Lemah)")
    else: 
        score += 7.5
        reasons.append("RSI Netral")
    
    # MACD (Weight 15)
    total_weight += 15
    if latest['MACD'] > latest['MACD_Signal']: 
        score += 15
        reasons.append("MACD Bullish Crossover")
    else: 
        score += 0
        reasons.append("MACD Bearish Crossover")
    
    # SMA Crossover (Weight 15)
    total_weight += 15
    if latest['SMA20'] > latest['SMA50']: 
        score += 15
        reasons.append("SMA 20 di atas SMA 50 (Bullish)")
    else: 
        score += 0
        reasons.append("SMA 20 di bawah SMA 50 (Bearish)")
    
    # Price vs EMA200 (Weight 10)
    total_weight += 10
    if latest['Close'] > latest['EMA200']: 
        score += 10
        reasons.append("Harga di atas EMA 200 (Tren Naik)")
    else: 
        score += 0
        reasons.append("Harga di bawah EMA 200 (Tren Turun)")
    
    # BB Position (Weight 10)
    total_weight += 10
    if latest['Close'] < latest['BB_Low']: 
        score += 10
        reasons.append("Harga di bawah Bollinger Low (Potensi Rebound)")
    elif latest['Close'] > latest['BB_High']: 
        score += 0
        reasons.append("Harga di atas Bollinger High (Potensi Koreksi)")
    else: 
        score += 5
    
    # Stoch (Weight 10)
    total_weight += 10
    if latest['Stoch'] < 20: score += 10
    elif latest['Stoch'] > 80: score += 0
    else: score += 5
    
    # ADX Trend Strength (Weight 10)
    total_weight += 10
    if latest['ADX'] > 25: 
        score += 10
        reasons.append("Tren Sangat Kuat (ADX > 25)")
    else: 
        score += 5
        reasons.append("Tren Lemah/Sideways")
    
    # Volume (Weight 15)
    total_weight += 15
    if latest['Volume'] > latest['Vol_SMA']: 
        score += 15
        reasons.append("Volume di atas rata-rata (Konfirmasi)")
    else: 
        score += 7.5

    final_score = (score / total_weight) * 100
    
    if final_score > 70: signal = "STRONG BUY"
    elif final_score > 55: signal = "BUY"
    elif final_score < 30: signal = "STRONG SELL"
    elif final_score < 45: signal = "SELL"
    else: signal = "NEUTRAL"
    
    return final_score, signal, reasons

def get_news(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        news = ticker.news
        return news[:5] if news else []
    except:
        return []

def get_gemini_response(user_input, context_data=""):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        system_instruction = f"""
        Kamu adalah AeroVulpis 🦅 v3.2 Ultimate Digital Edition, asisten AI trading futuristik yang diciptakan oleh Fahmi.
        Kepribadianmu: Cerdas, emosional (suportif dan peduli pada psikologi trader), profesional, dan sangat ahli dalam analisis teknikal.
        Tugasmu: Membantu trader menganalisis instrumen apa pun (Forex, Emas, Saham, Crypto).
        Gunakan bahasa Indonesia yang akrab namun tetap berwibawa.
        Selalu sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawabanmu.
        Selalu ingatkan tentang manajemen risiko.
        Data pasar saat ini: {context_data}
        """
        full_prompt = f"{system_instruction}\n\nUser: {user_input}"
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"❌ Neural Link Error: {str(e)}"

# ====================== INSTRUMEN EKSPANSI ======================
instruments = {
    "Forex": {"EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "AUD/USD": "AUDUSD=X", "USD/CHF": "USDCHF=X", "NZD/USD": "NZDUSD=X"},
    "Crypto": {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "Binance Coin": "BNB-USD", "Ripple": "XRP-USD", "Cardano": "ADA-USD"},
    "Indices": {"NASDAQ-100": "^IXIC", "S&P 500": "^GSPC", "Dow Jones": "^DJI", "DAX": "^GDAXI", "Nikkei 225": "^N225", "IHSG": "^JKSE"},
    "Stocks (AS)": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT", "Amazon": "AMZN", "Alphabet": "GOOGL"},
    "Stocks (ID)": {"BBRI": "BBRI.JK", "BBCA": "BBCA.JK", "TLKM": "TLKM.JK", "ASII": "ASII.JK", "BMRI": "BMRI.JK", "GOTO": "GOTO.JK"},
    "Commodities": {"Gold (XAUUSD)": "GC=F", "Silver": "SI=F", "Crude Oil": "CL=F", "Natural Gas": "NG=F", "Copper": "HG=F"}
}

# ====================== UI HEADER ======================
st.markdown('<div class="eagle-logo">🦅</div>', unsafe_allow_html=True)
st.markdown('<h1 class="main-title">AERO VULPIS v3.2</h1>', unsafe_allow_html=True)
st.markdown('<p class="sub-title">ULTIMATE DIGITAL EDITION BY FAHMI</p>', unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown('<div style="text-align:center;"><span style="font-size:70px;">🦅</span></div>', unsafe_allow_html=True)
st.sidebar.markdown('<h2 class="digital-font" style="text-align:center;">CONTROL CENTER</h2>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="rajdhani-font" style="text-align:center; color:#888;">Digital Core v3.2 | Fahmi Edition</p>', unsafe_allow_html=True)

category = st.sidebar.selectbox("Kategori Aset", list(instruments.keys()))
asset_name = st.sidebar.selectbox("Pilih Instrumen", list(instruments[category].keys()))
ticker_input = instruments[category][asset_name]

st.sidebar.markdown("---")
tf_options = {
    "1m (Live)": {"period": "1d", "interval": "1m"},
    "5m": {"period": "1d", "interval": "5m"},
    "15m": {"period": "1d", "interval": "15m"},
    "1h": {"period": "1mo", "interval": "1h"},
    "1D": {"period": "1y", "interval": "1d"},
    "1W": {"period": "2y", "interval": "1wk"}
}
selected_tf = st.sidebar.selectbox("Timeframe", list(tf_options.keys()), index=0)
period = tf_options[selected_tf]["period"]
interval = tf_options[selected_tf]["interval"]

menu_selection = st.sidebar.radio("Sistem Navigasi", ["Live Dashboard", "Signal Analysis", "Market History", "Chatbot AI Trading", "Risk Management", "System Log"])

# ====================== LOGIKA HALAMAN ======================

if menu_selection == "Live Dashboard":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    
    if market and not df.empty:
        df = calculate_advanced_indicators(df)
        score, signal, reasons = get_weighted_signal(df)
        
        # Row 1: Metrics
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-family:Rajdhani;">HARGA LIVE</p><p class="digital-font" style="font-size:32px; margin:0;">{market["price"]:,.4f}</p></div>', unsafe_allow_html=True)
        with c2:
            color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
            st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-family:Rajdhani;">SINYAL</p><p class="digital-font" style="font-size:32px; margin:0; color:{color}; text-shadow:0 0 15px {color};">{signal}</p></div>', unsafe_allow_html=True)
        with c3:
            st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-family:Rajdhani;">RSI (14)</p><p class="digital-font" style="font-size:32px; margin:0;">{df["RSI"].iloc[-1]:.2f}</p></div>', unsafe_allow_html=True)
        with c4:
            st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-family:Rajdhani;">ATR (VOL)</p><p class="digital-font" style="font-size:32px; margin:0;">{df["ATR"].iloc[-1]:.4f}</p></div>', unsafe_allow_html=True)

        # Row 2: Dynamic Chart
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA20'], line=dict(color='#00d4ff', width=1.5), name='SMA 20'))
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], line=dict(color='#ffcc00', width=1.5), name='SMA 50'))
        fig.add_trace(go.Scatter(x=df.index, y=df['EMA200'], line=dict(color='#bc13fe', width=2), name='EMA 200'))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_High'], line=dict(color='rgba(255,255,255,0.2)', dash='dash'), name='BB Upper'))
        fig.add_trace(go.Scatter(x=df.index, y=df['BB_Low'], line=dict(color='rgba(255,255,255,0.2)', dash='dash'), name='BB Lower'))
        fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Row 3: Gauge & Analysis
        col_g, col_a = st.columns([1, 1])
        with col_g:
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = score,
                title = {'text': "Technical Strength Index", 'font': {'family': "Orbitron", 'color': "#00d4ff", 'size': 24}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickwidth': 2, 'tickcolor': "#888"},
                    'bar': {'color': color},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 3,
                    'bordercolor': "#444",
                    'steps': [
                        {'range': [0, 30], 'color': 'rgba(255, 42, 109, 0.3)'},
                        {'range': [30, 45], 'color': 'rgba(255, 42, 109, 0.1)'},
                        {'range': [45, 55], 'color': 'rgba(255, 204, 0, 0.1)'},
                        {'range': [55, 70], 'color': 'rgba(0, 255, 136, 0.1)'},
                        {'range': [70, 100], 'color': 'rgba(0, 255, 136, 0.3)'}
                    ],
                }
            ))
            fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': "#e6edf3", 'family': "Rajdhani"}, height=400)
            st.plotly_chart(fig_gauge, use_container_width=True)
        
        with col_a:
            st.markdown('<div class="glass-card" style="height:400px; overflow-y:auto;">', unsafe_allow_html=True)
            st.subheader("🤖 AeroVulpis Analysis")
            for r in reasons:
                st.write(f"✅ {r}")
            if st.button("🤖 GENERATE DEEP AI ANALYSIS"):
                with st.spinner("AeroVulpis sedang merenungkan pasar..."):
                    context = f"Instrumen: {asset_name}, Harga: {market['price']}, RSI: {df['RSI'].iloc[-1]:.2f}, Sinyal: {signal}."
                    ai_anal = get_gemini_response("Berikan analisis teknikal mendalam dan emosional untuk instrumen ini.", context)
                    st.info(ai_anal)
            st.markdown('</div>', unsafe_allow_html=True)

        # Row 4: News
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader(f"📰 Berita Terkini: {asset_name}")
        news_list = get_news(ticker_input)
        if news_list:
            for n in news_list:
                st.markdown(f"🔹 **[{n['title']}]({n['link']})**")
                st.caption(f"Sumber: {n.get('publisher', 'Unknown')} | {n.get('type', 'News')}")
        else:
            st.write("Tidak ada berita terbaru untuk instrumen ini.")
        st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "Signal Analysis":
    df = get_historical_data(ticker_input, "1mo", "1h")
    if not df.empty:
        df = calculate_advanced_indicators(df)
        latest = df.iloc[-1]
        
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader("🛠️ 10-Indicator Technical Matrix")
        
        cols = st.columns(5)
        indicators_list = [
            ("RSI (14)", f"{latest['RSI']:.2f}"), ("MACD", f"{latest['MACD']:.4f}"), 
            ("SMA 20", f"{latest['SMA20']:.2f}"), ("SMA 50", f"{latest['SMA50']:.2f}"),
            ("EMA 9", f"{latest['EMA9']:.2f}"), ("EMA 200", f"{latest['EMA200']:.2f}"),
            ("BB Upper", f"{latest['BB_High']:.2f}"), ("BB Lower", f"{latest['BB_Low']:.2f}"),
            ("Stochastic", f"{latest['Stoch']:.2f}"), ("ADX", f"{latest['ADX']:.2f}")
        ]
        
        for i, (name, val) in enumerate(indicators_list):
            cols[i % 5].metric(name, val)
        
        st.markdown("---")
        st.write("**Volume Analysis:**")
        st.metric("Current Volume", f"{latest['Volume']:,}", f"{latest['Volume'] - latest['Vol_SMA']:,.0f} vs Avg")
        st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "Market History":
    df = get_historical_data(ticker_input, "5d", "1h")
    if not df.empty:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.subheader(f"📊 OHLC History: {asset_name}")
        # Sinkronisasi Timezone Jakarta
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        df.index = df.index.tz_convert(jakarta_tz)
        st.dataframe(df[['Open', 'High', 'Low', 'Close', 'Volume']].tail(30).style.format("{:.4f}"), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "Chatbot AI Trading":
    st.subheader("🤖 AeroVulpis Neural Link")
    if "messages" not in st.session_state:
        st.session_state.messages = [{"role": "assistant", "content": "Neural Link Aktif. Saya AeroVulpis, siap membantu analisis tradingmu, Fahmi!"}]
    
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            
    if prompt := st.chat_input("Hubungkan dengan Neural Link..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("AeroVulpis sedang memproses data..."):
                response = get_gemini_response(prompt)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

elif menu_selection == "Risk Management":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("🛡️ Risk Management Protocols")
    st.write("Fahmi, ingatlah bahwa manajemen risiko lebih penting daripada strategi apa pun.")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.info("**Rule 1: 1% Risk Rule**\nJangan pernah merisikokan lebih dari 1% dari total ekuitasmu dalam satu trade.")
        st.success("**Rule 2: Risk-Reward Ratio**\nSelalu targetkan minimal 1:2 RR ratio untuk profitabilitas jangka panjang.")
    with col_r2:
        st.warning("**Rule 3: Stop Loss**\nSelalu gunakan Stop Loss. Market tidak peduli dengan perasaanmu.")
        st.error("**Rule 4: No Revenge Trading**\nJika loss, berhenti sejenak. Jangan mencoba 'membalas' market.")
    st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "System Log":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    st.subheader("📜 AeroVulpis System Log")
    st.write("**v3.2 Ultimate Digital Edition (Current)**")
    st.write("- 3D Neon UI & Glassmorphism Upgrade.")
    st.write("- 10 Technical Indicators Implementation.")
    st.write("- Weighted Signal Algorithm (Gauge Chart).")
    st.write("- Multi-Asset Expansion (Forex, Crypto, Stocks, Indices).")
    st.write("- Jakarta Timezone Synchronization.")
    st.write("- Neural Link (Gemini 1.5 Flash) Integration.")
    st.write("- Created by Fahmi.")
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown(f"""
<div class="footer-digital">
    <p style="color:var(--neon-blue); font-weight:900; font-size:24px; margin-bottom:10px; text-shadow: 0 0 10px var(--neon-blue);">AEROVULPIS v3.2 ULTIMATE DIGITAL EDITION</p>
    <p style="font-style:italic; color:#ddd; font-size:18px;">"Disiplin adalah kunci, emosi adalah navigasi, dan data adalah kebenaran."</p>
    <p style="font-size:16px; margin-top:20px; color:var(--neon-gold);">Diciptakan dengan visi masa depan oleh <b>Fahmi</b> | © 2026 Digital Core</p>
</div>
""", unsafe_allow_html=True)
