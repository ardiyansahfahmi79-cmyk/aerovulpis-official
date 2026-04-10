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
        filter: drop-shadow(0 0 15px var(--neon-blue)) drop-shadow(0 0 30px var(--neon-purple));
        animation: pulse 2s infinite ease-in-out;
        margin-bottom: 0px;
        cursor: default;
    }

    @keyframes pulse {
        0% { transform: scale(1); filter: drop-shadow(0 0 15px var(--neon-blue)); }
        50% { transform: scale(1.05); filter: drop-shadow(0 0 25px var(--neon-purple)); }
        100% { transform: scale(1); filter: drop-shadow(0 0 15px var(--neon-blue)); }
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
        margin-top: -10px;
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
        hist = ticker.history(period="1d", interval="1m")
        if hist.empty:
            hist = ticker.history(period="1d", interval="5m")
        
        if not hist.empty:
            latest = hist.iloc[-1]
            prev = hist.iloc[-2] if len(hist) > 1 else latest
            return {
                "price": round(float(latest["Close"]), 4),
                "open": round(float(latest["Open"]), 4),
                "high": round(float(latest["High"]), 4),
                "low": round(float(latest["Low"]), 4),
                "close": round(float(latest["Close"]), 4),
                "prev_close": round(float(prev["Close"]), 4),
                "volume": int(latest["Volume"]),
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
    if len(df) < 200: return df
    
    df["SMA20"] = ta.trend.sma_indicator(df["Close"], window=20)
    df["SMA50"] = ta.trend.sma_indicator(df["Close"], window=50)
    df["SMA200"] = ta.trend.sma_indicator(df["Close"], window=200)
    df["EMA9"] = ta.trend.ema_indicator(df["Close"], window=9)
    df["RSI"] = ta.momentum.rsi(df["Close"], window=14)
    
    macd = ta.trend.MACD(df["Close"])
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Diff"] = macd.macd_diff()
    
    bb = ta.volatility.BollingerBands(df["Close"])
    df["BB_High"] = bb.bollinger_hband()
    df["BB_Low"] = bb.bollinger_lband()
    df["BB_Mid"] = bb.bollinger_mavg()
    
    stoch = ta.momentum.StochasticOscillator(df["High"], df["Low"], df["Close"])
    df["Stoch_K"] = stoch.stoch()
    df["Stoch_D"] = stoch.stoch_signal()
    
    df["ATR"] = ta.volatility.average_true_range(df["High"], df["Low"], df["Close"])
    
    adx = ta.trend.ADXIndicator(df["High"], df["Low"], df["Close"])
    df["ADX"] = adx.adx()
    df["ADX_pos"] = adx.adx_pos()
    df["ADX_neg"] = adx.adx_neg()
    
    df["Vol_SMA"] = df["Volume"].rolling(window=20).mean()
    df["Ichimoku_Conv"] = ta.trend.ichimoku_conversion_line(df["High"], df["Low"])
    
    return df

def get_weighted_signal(df):
    if df.empty or len(df) < 200 or "RSI" not in df.columns: return 50, "NETRAL", []
    
    latest = df.iloc[-1]
    score = 0
    total_weight = 0
    reasons = []
    
    # 1. RSI (Weight 15)
    total_weight += 15
    if latest["RSI"] < 30: 
        score += 15
        reasons.append("RSI Oversold (Potensi Rebound Kuat)")
    elif latest["RSI"] > 70: 
        score += 0
        reasons.append("RSI Overbought (Potensi Koreksi Kuat)")
    elif latest["RSI"] < 45: 
        score += 5
        reasons.append("RSI Menuju Oversold (Potensi Beli)")
    elif latest["RSI"] > 55: 
        score += 10
        reasons.append("RSI Menuju Overbought (Potensi Jual)")
    else: 
        score += 7.5
        reasons.append("RSI Netral")
    
    # 2. MACD (Weight 15)
    total_weight += 15
    if latest["MACD"] > latest["MACD_Signal"] and latest["MACD_Diff"] > 0: 
        score += 15
        reasons.append("MACD Bullish Crossover (Momentum Naik)")
    elif latest["MACD"] < latest["MACD_Signal"] and latest["MACD_Diff"] < 0: 
        score += 0
        reasons.append("MACD Bearish Crossover (Momentum Turun)")
    else: 
        score += 7.5
        reasons.append("MACD Netral")
    
    # 3. SMA Crossover (Weight 15)
    total_weight += 15
    if latest["SMA20"] > latest["SMA50"] and df["SMA20"].iloc[-2] <= df["SMA50"].iloc[-2]: 
        score += 15
        reasons.append("Golden Cross (SMA20 > SMA50) - Sinyal Beli Kuat")
    elif latest["SMA20"] < latest["SMA50"] and df["SMA20"].iloc[-2] >= df["SMA50"].iloc[-2]: 
        score += 0
        reasons.append("Death Cross (SMA20 < SMA50) - Sinyal Jual Kuat")
    elif latest["SMA20"] > latest["SMA50"]: 
        score += 10
        reasons.append("SMA20 di atas SMA50 (Tren Naik)")
    elif latest["SMA20"] < latest["SMA50"]: 
        score += 5
        reasons.append("SMA20 di bawah SMA50 (Tren Turun)")
    else: 
        score += 7.5
        reasons.append("SMA Crossover Netral")
    
    # 4. Price vs SMA200 (Weight 10)
    total_weight += 10
    if latest["Close"] > latest["SMA200"]: 
        score += 10
        reasons.append("Harga di atas SMA200 (Tren Jangka Panjang Naik)")
    else: 
        score += 0
        reasons.append("Harga di bawah SMA200 (Tren Jangka Panjang Turun)")
    
    # 5. Bollinger Bands (Weight 10)
    total_weight += 10
    if latest["Close"] < latest["BB_Low"]: 
        score += 10
        reasons.append("Harga di bawah Bollinger Lower Band (Oversold)")
    elif latest["Close"] > latest["BB_High"]: 
        score += 0
        reasons.append("Harga di atas Bollinger Upper Band (Overbought)")
    else: 
        score += 5
        reasons.append("Harga di dalam Bollinger Bands")
    
    # 6. Stochastic Oscillator (Weight 10)
    total_weight += 10
    if latest["Stoch_K"] < 20 and latest["Stoch_D"] < 20 and latest["Stoch_K"] > latest["Stoch_D"]: 
        score += 10
        reasons.append("Stochastic Oversold & Bullish Crossover")
    elif latest["Stoch_K"] > 80 and latest["Stoch_D"] > 80 and latest["Stoch_K"] < latest["Stoch_D"]: 
        score += 0
        reasons.append("Stochastic Overbought & Bearish Crossover")
    else: 
        score += 5
        reasons.append("Stochastic Netral")
    
    # 7. ADX (Weight 10)
    total_weight += 10
    if latest["ADX"] > 25 and latest["ADX_pos"] > latest["ADX_neg"]: 
        score += 10
        reasons.append("ADX Kuat & Tren Naik Dominan")
    elif latest["ADX"] > 25 and latest["ADX_neg"] > latest["ADX_pos"]: 
        score += 0
        reasons.append("ADX Kuat & Tren Turun Dominan")
    else: 
        score += 5
        reasons.append("ADX Tren Lemah/Sideways")
    
    # 8. ATR (Weight 5)
    total_weight += 5
    reasons.append(f"Volatilitas (ATR): {latest['ATR']:.4f}")
    score += 2.5
    
    # 9. Volume Analysis (Weight 5)
    total_weight += 5
    if latest["Volume"] > latest["Vol_SMA"] * 1.5: 
        score += 5
        reasons.append("Volume Tinggi (Konfirmasi Tren)")
    elif latest["Volume"] < latest["Vol_SMA"] * 0.5: 
        score += 0
        reasons.append("Volume Rendah (Kurang Konfirmasi Tren)")
    else: 
        score += 2.5
        reasons.append("Volume Normal")
    
    # 10. EMA9 vs Close (Weight 5)
    total_weight += 5
    if latest["Close"] > latest["EMA9"]: 
        score += 5
        reasons.append("Harga di atas EMA9 (Momentum Jangka Pendek Naik)")
    else: 
        score += 0
        reasons.append("Harga di bawah EMA9 (Momentum Jangka Pendek Turun)")
    
    final_score = (score / total_weight) * 100
    
    if final_score >= 75: signal = "STRONG BUY"
    elif final_score >= 60: signal = "BUY"
    elif final_score <= 25: signal = "STRONG SELL"
    elif final_score <= 40: signal = "SELL"
    else: signal = "NEUTRAL"
    
    return final_score, signal, reasons

def get_gemini_response(user_input, context_data=""):
    if not api_key:
        return "⚠️ Chatbot tidak aktif: API Key belum dikonfigurasi."
    
    MODEL_NAME = "gemini-1.5-flash"
    full_prompt = f"""
    Kamu adalah AeroVulpis 🦅 v3.2, asisten AI trading futuristik yang emosional, cerdas, dan sangat disiplin.
    Nama penciptamu adalah Fahmi — sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawaban.
    
    Personality: Digital, tajam, suportif, peduli pada psikologi trader, pakai emoji futuristik.
    Tugasmu: Membantu trader menganalisis instrumen apa pun (Forex, Emas, Saham, Crypto).
    Gunakan bahasa Indonesia yang akrab namun tetap berwibawa.
    Selalu ingatkan tentang manajemen risiko.
    Data pasar saat ini: {context_data}
    
    User: {user_input}
    """
    try:
        model = genai.GenerativeModel(model_name=MODEL_NAME)
        response = model.generate_content(full_prompt)
        return response.text if response and response.text else "⚠️ Gemini tidak memberikan respons teks."
    except Exception as e:
        return f"⚠️ Chatbot error: {str(e)}"

# ====================== INSTRUMEN EKSPANSI ======================
instruments = {
    "Forex": {
        "EUR/USD": "EURUSD=X", 
        "GBP/USD": "GBPUSD=X", 
        "USD/JPY": "USDJPY=X", 
        "AUD/USD": "AUDUSD=X", 
        "USD/CHF": "USDCHF=X"
    },
    "Commodities": {
        "Gold (XAUUSD)": "GC=F", 
        "Silver": "SI=F", 
        "Crude Oil": "CL=F", 
        "Natural Gas": "NG=F", 
        "Copper": "HG=F"
    },
    "Stocks (AS)": {
        "NVIDIA": "NVDA", 
        "Apple": "AAPL", 
        "Microsoft": "MSFT", 
        "Alphabet (Google)": "GOOGL", 
        "Amazon": "AMZN"
    },
    "Stocks (ID)": {
        "BBCA": "BBCA.JK", 
        "BBRI": "BBRI.JK", 
        "TLKM": "TLKM.JK", 
        "BMRI": "BMRI.JK", 
        "ASII": "ASII.JK"
    },
    "Crypto": {
        "Bitcoin": "BTC-USD", 
        "Ethereum": "ETH-USD", 
        "Solana": "SOL-USD"
    }
}

# ====================== UI HEADER ======================
st.markdown("<div class='eagle-logo'>🦅</div>", unsafe_allow_html=True)
st.markdown("<h1 class='main-title'>AERO VULPIS v3.2</h1>", unsafe_allow_html=True)
st.markdown("<p class='sub-title'>ULTIMATE DIGITAL EDITION BY FAHMI</p>", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown("<div style='text-align:center;'><span style='font-size:70px;'>🦅</span></div>", unsafe_allow_html=True)
st.sidebar.markdown("<h2 class='digital-font' style='text-align:center;'>CONTROL CENTER</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p class='rajdhani-font' style='text-align:center; color:#888;'>Digital Core v3.2 | Fahmi Edition</p>", unsafe_allow_html=True)

category = st.sidebar.selectbox("Kategori Aset", list(instruments.keys()))
asset_name = st.sidebar.selectbox("Pilih Instrumen", list(instruments[category].keys()))
ticker_input = instruments[category][asset_name]

st.sidebar.markdown("---")
tf_options = {
    "1m (Live)": {"period": "1d", "interval": "1m"},
    "5m": {"period": "1d", "interval": "5m"},
    "15m": {"period": "1d", "interval": "15m"},
    "1h": {"period": "1mo", "interval": "1h"},
    "1D": {"period": "1y", "interval": "1d"}
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
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        fig = go.Figure()
        # Menggunakan Line Chart sesuai permintaan Fahmi
        is_up = market["price"] >= market["prev_close"]
        line_color = "#00ff88" if is_up else "#ff2a6d"
        fig.add_trace(go.Scatter(
            x=df.index, y=df["Close"], 
            mode='lines', 
            line=dict(color=line_color, width=3),
            fill='tozeroy',
            fillcolor=f'rgba({0 if is_up else 255}, {255 if is_up else 42}, {136 if is_up else 109}, 0.1)',
            name='Price'
        ))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color='#00d4ff', width=1.5, dash='dot'), name='SMA 50'))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], line=dict(color='#bc13fe', width=2), name='SMA 200'))
        
        fig.update_layout(template="plotly_dark", height=650, xaxis_rangeslider_visible=False, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
                        {'range': [0, 20], 'color': 'rgba(139, 0, 0, 0.3)', 'name': 'Strong Bearish'},
                        {'range': [20, 40], 'color': 'rgba(255, 42, 109, 0.1)', 'name': 'Low Bearish'},
                        {'range': [40, 60], 'color': 'rgba(255, 204, 0, 0.1)', 'name': 'Neutral'},
                        {'range': [60, 80], 'color': 'rgba(0, 255, 136, 0.1)', 'name': 'Low Bullish'},
                        {'range': [80, 100], 'color': 'rgba(0, 255, 136, 0.3)', 'name': 'Strong Bullish'}
                    ],
                }
            ))
            fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': "#e6edf3", 'family': "Rajdhani"}, height=400)
            st.plotly_chart(fig_gauge, use_container_width=True)
        
        with col_a:
            st.markdown("<div class='glass-card' style='height:400px; overflow-y:auto;'>", unsafe_allow_html=True)
            st.subheader("🤖 AeroVulpis Analysis")
            for r in reasons:
                st.write(f"✅ {r}")
            if st.button("🤖 GENERATE DEEP AI ANALYSIS"):
                with st.spinner("AeroVulpis sedang merenungkan pasar..."):
                    context = f"Instrumen: {asset_name}, Harga: {market['price']}, RSI: {df['RSI'].iloc[-1]:.2f}, Sinyal: {signal}."
                    ai_anal = get_gemini_response("Berikan analisis teknikal mendalam dan emosional untuk instrumen ini.", context)
                    st.info(ai_anal)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        if st.button("🔄 REFRESH DIGITAL CORE"):
            st.cache_data.clear()
            st.rerun()
        st.info("Sistem AeroVulpis melakukan sinkronisasi data setiap 60 detik secara otomatis.")
        st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "Signal Analysis":
    df = get_historical_data(ticker_input, period, interval)
    if not df.empty:
        df = calculate_advanced_indicators(df)
        latest = df.iloc[-1]
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.subheader("🛠️ 10-Indicator Technical Matrix")
        
        cols = st.columns(5)
        indicators_list = [
            ("RSI (14)", f"{latest['RSI']:.2f}"), ("MACD", f"{latest['MACD']:.4f}"), 
            ("SMA 20", f"{latest['SMA20']:.2f}"), ("SMA 50", f"{latest['SMA50']:.2f}"),
            ("EMA 9", f"{latest['EMA9']:.2f}"), ("EMA 200", f"{latest['SMA200']:.2f}"),
            ("BB Upper", f"{latest['BB_High']:.2f}"), ("BB Lower", f"{latest['BB_Low']:.2f}"),
            ("Stochastic K", f"{latest['Stoch_K']:.2f}"), ("ADX", f"{latest['ADX']:.2f}")
        ]
        
        for i, (name, val) in enumerate(indicators_list):
            cols[i % 5].metric(name, val)
        
        st.markdown("---")
        st.write("**Volume Analysis:**")
        st.metric("Current Volume", f"{latest['Volume']:,}", f"{latest['Volume'] - latest['Vol_SMA']:,.0f} vs Avg")
        st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "Market History":
    df = get_historical_data(ticker_input, "5d", "1h")
    if not df.empty:
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        st.subheader(f"📊 OHLC History: {asset_name}")
        jakarta_tz = pytz.timezone('Asia/Jakarta')
        df.index = df.index.tz_convert(jakarta_tz)
        st.dataframe(df[["Open", "High", "Low", "Close", "Volume"]].tail(30).style.format("{:.4f}"), use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
                market = get_market_data(ticker_input)
                context = f"Harga {asset_name} saat ini: {market['price'] if market else 'N/A'}"
                response = get_gemini_response(prompt, context)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

elif menu_selection == "Risk Management":
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("🛡️ Risk Management Protocols")
    st.write("Fahmi, ingatlah bahwa manajemen risiko lebih penting daripada strategi apa pun.")
    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.info("**Rule 1: 1% Risk Rule**\nJangan pernah merisikokan lebih dari 1% dari total ekuitasmu dalam satu trade.")
        st.success("**Rule 2: Risk-Reward Ratio**\nSelalu targetkan minimal 1:2 RR ratio untuk profitabilitas jangka panjang.")
    with col_r2:
        st.warning("**Rule 3: Stop Loss**\nSelalu gunakan Stop Loss. Market tidak peduli dengan perasaanmu.")
        st.error("**Rule 4: No Revenge Trading**\nJika loss, berhenti sejenak. Jangan mencoba 'membalas' market.")
    st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "System Log":
    st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
    st.subheader("📜 AeroVulpis System Log")
    st.write("**v3.2 Ultimate Digital Edition (Fixed)**")
    st.write("- Fixed SyntaxErrors in f-strings and quoting.")
    st.write("- Removed Market Update widget to prevent recurring errors.")
    st.write("- Expanded Multi-Asset List (Forex, Commodities, US & ID Stocks).")
    st.write("- Implemented Line Chart with area gradient.")
    st.write("- Optimized Gauge Chart with 5-zone technical analysis.")
    st.write("- Neural Link (Gemini 1.5 Flash) Integration Fixed.")
    st.write("- Created by Fahmi.")
    st.markdown("</div>", unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown(f"""
<div class="footer-digital">
    <p style="color:var(--neon-blue); font-weight:900; font-size:24px; margin-bottom:10px; text-shadow: 0 0 10px var(--neon-blue);">AEROVULPIS v3.2 ULTIMATE DIGITAL EDITION</p>
    <p style="font-style:italic; color:#ddd; font-size:18px;">"Disiplin adalah kunci, emosi adalah navigasi, dan data adalah kebenaran."</p>
    <p style="font-size:16px; margin-top:20px; color:var(--neon-gold);">Diciptakan dengan visi masa depan oleh <b>Fahmi</b> | © 2026 Digital Core</p>
</div>
""", unsafe_allow_html=True)
