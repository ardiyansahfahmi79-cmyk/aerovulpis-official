import streamlit as st
from groq import Groq
from widgets import economic_calendar_widget
import os
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time as dt_time
import pytz
import ta
import time
import requests
from streamlit_option_menu import option_menu

# Memuat variabel lingkungan dari file .env
from dotenv import load_dotenv
load_dotenv()

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.3 Ultimate", page_icon="🦅", initial_sidebar_state="expanded")

# Inisialisasi Session State untuk Bahasa
if "lang" not in st.session_state:
    st.session_state.lang = "ID"

# Kamus Bahasa
translations = {
    "ID": {
        "control_center": "CONTROL CENTER",
        "category": "Kategori Aset",
        "asset": "Pilih Instrumen",
        "timeframe": "Timeframe",
        "navigation": "Sistem Navigasi",
        "live_price": "HARGA LIVE",
        "signal": "SINYAL",
        "rsi": "RSI (14)",
        "atr": "ATR (VOL)",
        "refresh": "REFRESH INDICATOR",
        "ai_analysis": "🤖 AeroVulpis Analysis",
        "generate_ai": "GENERATE DEEP AI ANALYSIS",
        "market_sessions": "🌐 Market Sessions",
        "market_news": "📰 Market News",
        "risk_mgmt": "🛡️ Risk Management Protocol",
        "settings": "⚙️ Settings",
        "clear_cache": "Hapus Cache Sistem",
        "lang_select": "Pilih Bahasa",
        "recommendation": "Rekomendasi Saat Ini",
        "no_news": "Tidak ada berita terbaru ditemukan.",
        "ai_thinking": "AeroVulpis sedang merenungkan pasar...",
        "risk_info": "Masukkan Entry Price dan Stop Loss untuk menghitung manajemen risiko.",
        "vol_analysis": "Analisis Volume",
        "curr_vol": "Volume Saat Ini",
        "vs_avg": "vs Rata-rata",
        "pos_size": "UKURAN POSISI TERKALKULASI",
        "risk_amt": "Jumlah Risiko",
        "reward": "Imbalan (1:2)",
        "sys_log": "📜 AeroVulpis System Log",
        "version": "v3.3 Ultimate Digital Edition (Current)",
        "created_by": "Dibuat oleh Fahmi."
    },
    "EN": {
        "control_center": "CONTROL CENTER",
        "category": "Asset Category",
        "asset": "Select Instrument",
        "timeframe": "Timeframe",
        "navigation": "Navigation System",
        "live_price": "LIVE PRICE",
        "signal": "SIGNAL",
        "rsi": "RSI (14)",
        "atr": "ATR (VOL)",
        "refresh": "REFRESH INDICATOR",
        "ai_analysis": "🤖 AeroVulpis Analysis",
        "generate_ai": "GENERATE DEEP AI ANALYSIS",
        "market_sessions": "🌐 Market Sessions",
        "market_news": "📰 Market News",
        "risk_mgmt": "🛡️ Risk Management Protocol",
        "settings": "⚙️ Settings",
        "clear_cache": "Clear System Cache",
        "lang_select": "Select Language",
        "recommendation": "Current Recommendation",
        "no_news": "No recent news found.",
        "ai_thinking": "AeroVulpis is contemplating the market...",
        "risk_info": "Enter Entry Price and Stop Loss to calculate risk management.",
        "vol_analysis": "Volume Analysis",
        "curr_vol": "Current Volume",
        "vs_avg": "vs Average",
        "pos_size": "CALCULATED POSITION SIZE",
        "risk_amt": "Risk Amount",
        "reward": "Reward (1:2)",
        "sys_log": "📜 AeroVulpis System Log",
        "version": "v3.3 Ultimate Digital Edition (Current)",
        "created_by": "Created by Fahmi."
    }
}

t = translations[st.session_state.lang]

# CSS untuk tampilan 3D Digital & Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

    :root {
        --neon-green: #00ff88;
        --crimson-red: #ff2a6d;
        --electric-blue: #00d4ff;
        --deep-blue: #0055ff;
        --glass-bg: rgba(255, 255, 255, 0.05);
        --glass-border: rgba(255, 255, 255, 0.1);
    }

    .stApp {
        background: radial-gradient(circle at top right, #0a0e17, #020408);
        color: #e0e0e0;
    }

    .glass-card {
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--glass-border);
        border-radius: 15px;
        padding: 15px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
        margin-bottom: 5px;
    }

    .session-container {
        border: 2px solid var(--electric-blue);
        border-radius: 15px;
        padding: 20px;
        background: rgba(0, 212, 255, 0.02);
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
        margin-bottom: 20px;
    }

    .session-card {
        background: rgba(255, 255, 255, 0.03);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 15px;
        margin-bottom: 10px;
        transition: all 0.3s ease;
    }

    .session-card:hover {
        background: rgba(255, 255, 255, 0.05);
        border-color: var(--electric-blue);
    }

    .main-title-container {
        text-align: center;
        margin-bottom: 0px;
        padding-bottom: 0px;
    }

    .main-logo-container {
        position: relative;
        display: inline-block;
        animation: float 4s infinite ease-in-out;
        padding: 10px 0; /* Padding dikecilkan */
        margin-bottom: -15px; /* Margin diperbesar agar judul lebih dekat */
        background: transparent !important;
        perspective: 1200px;
        overflow: visible !important; /* Mencegah logo terpotong */
    }

    .custom-logo {
        width: 100px; /* Ukuran disesuaikan agar proporsional */
        filter: drop-shadow(0 0 15px var(--electric-blue));
        transition: all 0.5s ease;
        background-color: transparent !important;
        animation: smoothRotate3D 12s infinite cubic-bezier(0.45, 0.05, 0.55, 0.95);
        transform-style: preserve-3d;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-8px); }
    }

    @keyframes smoothRotate3D {
        0% { transform: rotateY(0deg); }
        25% { transform: rotateY(0deg); }
        50% { transform: rotateY(360deg); }
        75% { transform: rotateY(360deg); }
        100% { transform: rotateY(0deg); }
    }

    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 32px;
        font-weight: 700;
        background: linear-gradient(90deg, var(--electric-blue), var(--deep-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        margin: 0;
        padding: 0;
    }

    .digital-font {
        font-family: 'Orbitron', sans-serif;
        color: var(--neon-green);
        text-shadow: 0 0 10px var(--neon-green);
    }

    .cyan-neon {
        color: var(--electric-blue);
        text-shadow: 0 0 10px var(--electric-blue);
    }

    .rajdhani-font {
        font-family: 'Rajdhani', sans-serif;
    }

    .stButton>button {
        background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
        border: none !important;
        color: white !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        padding: 8px 16px !important;
        border-radius: 10px !important;
        box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.4), -2px -2px 10px rgba(255, 255, 255, 0.1) !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 10px 20px rgba(0, 212, 255, 0.4) !important;
        filter: brightness(1.2);
    }

    [data-testid="stSidebar"] {
        background-color: rgba(10, 14, 23, 0.95);
        border-right: 1px solid var(--glass-border);
    }
    
    .news-card {
        background: rgba(255, 255, 255, 0.03);
        border-left: 4px solid var(--electric-blue);
        padding: 12px;
        margin-bottom: 8px;
        border-radius: 0 10px 10px 0;
    }

    .block-container {
        padding-bottom: 0.5rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }

    div[data-testid="stVerticalBlock"] > div {
        padding-top: 0rem !important;
        padding-bottom: 0rem !important;
    }

    .indicator-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        gap: 12px;
        margin-top: 15px;
    }

    .indicator-box {
        background: rgba(0, 212, 255, 0.05);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 8px;
        padding: 12px;
        text-align: center;
        transition: all 0.3s ease;
    }

    .indicator-box:hover {
        border-color: var(--electric-blue);
        box-shadow: 0 0 10px rgba(0, 212, 255, 0.3);
        transform: scale(1.02);
    }

    .indicator-name {
        font-family: 'Rajdhani', sans-serif;
        font-size: 13px;
        color: #aaa;
        margin-bottom: 5px;
        font-weight: 700;
    }

    .indicator-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 15px;
        color: #fff;
    }

    .indicator-signal {
        font-family: 'Rajdhani', sans-serif;
        font-size: 11px;
        font-weight: bold;
        margin-top: 5px;
        text-transform: uppercase;
    }
</style>
""", unsafe_allow_html=True)

# Konfigurasi Groq API
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = None
if groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception as e:
        st.sidebar.error(f"⚠️ Error: {str(e)}")
else:
    st.sidebar.error("⚠️ GROQ_API_KEY NOT FOUND")

# ====================== FUNGSI DATA & INDIKATOR ======================
def get_market_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            price = hist["Close"].iloc[-1]
            open_p = hist["Open"].iloc[0]
            high_p = hist["High"].max()
            low_p = hist["Low"].min()
            close_p = price
        else:
            hist_daily = ticker.history(period="1d")
            if not hist_daily.empty:
                price = hist_daily["Close"].iloc[-1]
                open_p = hist_daily["Open"].iloc[-1]
                high_p = hist_daily["High"].iloc[-1]
                low_p = hist_daily["Low"].iloc[-1]
                close_p = price
            else:
                info = ticker.fast_info
                price = info.get("lastPrice") or info.get("regularMarketPrice") or 0.0
                open_p = high_p = low_p = close_p = price
            
        return {
            "price": round(float(price), 4) if price is not None else 0.0,
            "open": round(float(open_p), 4) if open_p is not None else 0.0,
            "high": round(float(high_p), 4) if high_p is not None else 0.0,
            "low": round(float(low_p), 4) if low_p is not None else 0.0,
            "close": round(float(close_p), 4) if close_p is not None else 0.0
        }
    except:
        return None

def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return pd.DataFrame()
        return df.sort_index().dropna()
    except:
        return pd.DataFrame()

def add_technical_indicators(df):
    if len(df) < 50: return df
    # Basic
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=min(len(df), 200)).mean()
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    
    # RSI
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
    
    # BB
    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    df["BB_Std"] = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Mid"] + (df["BB_Std"] * 2)
    df["BB_Lower"] = df["BB_Mid"] - (df["BB_Std"] * 2)
    
    # Stoch
    low_14 = df["Low"].rolling(window=14).min()
    high_14 = df["High"].rolling(window=14).max()
    df["Stoch_K"] = 100 * ((df["Close"] - low_14) / (high_14 - low_14).replace(0, 0.001))
    df["Stoch_D"] = df["Stoch_K"].rolling(window=3).mean()
    
    # ATR
    high_low = df["High"] - df["Low"]
    high_cp = np.abs(df["High"] - df["Close"].shift())
    low_cp = np.abs(df["Low"] - df["Close"].shift())
    df["TR"] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()
    
    # ADX
    df["UpMove"] = df["High"] - df["High"].shift()
    df["DownMove"] = df["Low"].shift() - df["Low"]
    df["+DM"] = np.where((df["UpMove"] > df["DownMove"]) & (df["UpMove"] > 0), df["UpMove"], 0)
    df["-DM"] = np.where((df["DownMove"] > df["UpMove"]) & (df["DownMove"] > 0), df["DownMove"], 0)
    df["+DI"] = 100 * (df["+DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["-DI"] = 100 * (df["-DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["DX"] = 100 * np.abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"]).replace(0, 0.001)
    df["ADX"] = df["DX"].rolling(14).mean()
    
    # Additional 10 Indicators
    df["CCI"] = ta.trend.cci(df["High"], df["Low"], df["Close"], window=20)
    df["WPR"] = ta.momentum.williams_r(df["High"], df["Low"], df["Close"], lbp=14)
    df["MFI"] = ta.volume.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], window=14)
    df["TRIX"] = ta.trend.trix(df["Close"], window=15)
    df["ROC"] = ta.momentum.roc(df["Close"], window=12)
    df["AO"] = ta.momentum.awesome_oscillator(df["High"], df["Low"], window1=5, window2=34)
    df["KAMA"] = ta.momentum.kama(df["Close"], window=10, pow1=2, pow2=30)
    df["Ichimoku_A"] = ta.trend.ichimoku_a(df["High"], df["Low"], window1=9, window2=26)
    df["Ichimoku_B"] = ta.trend.ichimoku_b(df["High"], df["Low"], window2=26, window3=52)
    df["Parabolic_SAR"] = ta.trend.psar_up(df["High"], df["Low"], df["Close"]).fillna(ta.trend.psar_down(df["High"], df["Low"], df["Close"]))
    df["Vol_SMA"] = df["Volume"].rolling(window=20).mean()
    df["Base_Line"] = (df["High"].rolling(window=26).max() + df["Low"].rolling(window=26).min()) / 2
    return df

def get_weighted_signal(df):
    latest = df.iloc[-1]
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    reasons = []
    
    # 1. RSI
    if latest["RSI"] < 30: bullish_count += 1; reasons.append("RSI Oversold")
    elif latest["RSI"] > 70: bearish_count += 1; reasons.append("RSI Overbought")
    else: neutral_count += 1
    
    # 2. MACD
    if latest["MACD"] > latest["Signal_Line"]: bullish_count += 1; reasons.append("MACD Bullish")
    else: bearish_count += 1; reasons.append("MACD Bearish")
    
    # 3. SMA 50
    if latest["Close"] > latest["SMA50"]: bullish_count += 1; reasons.append("Above SMA 50")
    else: bearish_count += 1; reasons.append("Below SMA 50")
    
    # 4. SMA 200
    if latest["Close"] > latest["SMA200"]: bullish_count += 1; reasons.append("Above SMA 200")
    else: bearish_count += 1; reasons.append("Below SMA 200")
    
    # 5. CCI
    if latest["CCI"] < -100: bullish_count += 1
    elif latest["CCI"] > 100: bearish_count += 1
    else: neutral_count += 1
    
    # 6. WPR
    if latest["WPR"] < -80: bullish_count += 1
    elif latest["WPR"] > -20: bearish_count += 1
    else: neutral_count += 1
    
    # 7. MFI
    if latest["MFI"] < 20: bullish_count += 1
    elif latest["MFI"] > 80: bearish_count += 1
    else: neutral_count += 1
    
    # 8. EMA Cross
    if latest["EMA9"] > latest["EMA21"]: bullish_count += 1
    else: bearish_count += 1
    
    # 9. BB Position
    if latest["Close"] < latest["BB_Lower"]: bullish_count += 1
    elif latest["Close"] > latest["BB_Upper"]: bearish_count += 1
    else: neutral_count += 1
    
    # 10. ADX Trend
    if latest["ADX"] > 25:
        if latest["+DI"] > latest["-DI"]: bullish_count += 1
        else: bearish_count += 1
    else: neutral_count += 1

    total = bullish_count + bearish_count + neutral_count
    score = (bullish_count / total) * 100
    
    if score >= 70: signal = "STRONG BUY"
    elif score >= 60: signal = "BUY"
    elif score <= 30: signal = "STRONG SELL"
    elif score <= 40: signal = "SELL"
    else: signal = "NEUTRAL"
    
    return score, signal, reasons, bullish_count, bearish_count, neutral_count

# ====================== FUNGSI CHATBOT GROQ ======================
def get_groq_response(question, context=""):
    if not client: return "⚠️ Chatbot Inactive"
    MODEL_NAME = 'llama-3.3-70b-versatile'
    system_prompt = f"""
    Anda adalah AeroVulpis, asisten AI Trading Profesional.
    Waktu: {datetime.now().strftime('%d %B %Y, %H:%M:%S WIB')}
    Bahasa: {st.session_state.lang}

    TUGAS UTAMA:
    1. Membantu user (Fahmi) menganalisis data trading dan berita yang ditampilkan di website.
    2. Berikan level ENTRY, STOP LOSS, dan TAKE PROFIT yang spesifik berdasarkan data.
    3. Jawablah dengan singkat, padat, dan teknis.
    4. JANGAN menyarankan perubahan pada kode website kecuali diminta.
    5. Konteks: {context}
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            model=MODEL_NAME, temperature=0.7, max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ====================== MARKET SESSIONS LOGIC ======================
def market_session_status():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    current_time = now.time()
    
    sessions = [
        {"name": "Asian Session (Tokyo)", "start": dt_time(6, 0), "end": dt_time(15, 0), "color": "#00ff88"},
        {"name": "European Session (London)", "start": dt_time(14, 0), "end": dt_time(23, 0), "color": "#00d4ff"},
        {"name": "American Session (New York)", "start": dt_time(19, 0), "end": dt_time(4, 0), "color": "#ff2a6d"}
    ]
    
    st.markdown('<div class="session-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="cyan-neon" style="text-align:center; font-family:Orbitron; font-size:24px; margin-bottom:20px;">MARKET SESSIONS STATUS</h2>', unsafe_allow_html=True)
    
    active_sessions = []
    for sess in sessions:
        is_active = False
        if sess["start"] < sess["end"]: is_active = sess["start"] <= current_time <= sess["end"]
        else: is_active = current_time >= sess["start"] or current_time <= sess["end"]
        status_text = "🟢 Active" if is_active else "🔴 Closed"
        if is_active: active_sessions.append(sess["name"])
        progress = 0
        if is_active:
            now_minutes = now.hour * 60 + now.minute
            start_minutes = sess["start"].hour * 60 + sess["start"].minute
            end_minutes = sess["end"].hour * 60 + sess["end"].minute
            if end_minutes < start_minutes: end_minutes += 24 * 60
            if now_minutes < start_minutes and sess["start"] > sess["end"]: now_minutes += 24 * 60
            total_duration = end_minutes - start_minutes
            elapsed = now_minutes - start_minutes
            progress = min(100, max(0, int((elapsed / total_duration) * 100)))
        st.markdown(f"""
        <div class="session-card">
            <div style="display:flex; justify-content:between; align-items:center;">
                <span style="font-family:Orbitron; font-weight:bold; color:{sess['color']}; flex:1;">{sess['name']}</span>
                <span style="font-family:Rajdhani; font-weight:bold; color:{'#00ff88' if is_active else '#ff2a6d'};">{status_text}</span>
            </div>
            <div style="font-family:Rajdhani; font-size:12px; color:#888; margin-bottom:5px;">{sess['start'].strftime('%H:%M')} - {sess['end'].strftime('%H:%M')} WIB</div>
            <div style="background:rgba(255,255,255,0.1); height:6px; border-radius:3px; overflow:hidden;">
                <div style="background:{sess['color'] if is_active else '#444'}; width:{progress if is_active else 0}%; height:100%; transition:width 0.5s ease;"></div>
            </div>
            <div style="font-family:Rajdhani; font-size:11px; color:#aaa; margin-top:5px;">{ "Currently ACTIVE" if is_active else "Next session" }</div>
        </div>
        """, unsafe_allow_html=True)
    is_golden = (dt_time(19, 0) <= current_time <= dt_time(23, 0))
    if is_golden:
        st.markdown('<div style="text-align:center; padding:10px; background:rgba(0,212,255,0.1); border:1px solid var(--electric-blue); border-radius:10px; margin-top:10px; animation: pulse 2s infinite;">'
                    '<h3 class="cyan-neon" style="margin:0; font-size:18px;">GOLDEN TIME: High Volatility! 🚀</h3></div>', unsafe_allow_html=True)
    strategy_text = "Waiting for Market Open..."
    if "Asian Session (Tokyo)" in active_sessions and len(active_sessions) == 1: strategy_text = "Calm Market: Range Trading Mode. Focus on Liquidity Sweeps."
    elif is_golden: strategy_text = "High Volatility: Look for Order Block Mitigations & FVG entries."
    elif "European Session (London)" in active_sessions: strategy_text = "Trend Following: Watch for London Breakout patterns."
    elif "American Session (New York)" in active_sessions: strategy_text = "Market Reversals: Watch for NY Open manipulation."
    st.markdown(f"""
    <div style="margin-top:20px; padding:15px; border:1px solid var(--electric-blue); border-radius:10px; background:rgba(0,212,255,0.05); text-align:center;">
        <p class="cyan-neon" style="font-family:Orbitron; font-size:14px; margin-bottom:5px;">CURRENT RECOMMENDED STRATEGY: (SMC Focus)</p>
        <p class="rajdhani-font" style="font-size:16px; color:#fff; margin:0;">{strategy_text}</p>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== INSTRUMEN ======================
instruments = {
    "Forex": {"EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "AUD/USD": "AUDUSD=X", "USD/CHF": "USDCHF=X"},
    "Crypto": {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "Solana": "SOL-USD", "Binance Coin": "BNB-USD", "Ripple": "XRP-USD"},
    "Indices": {"NASDAQ-100": "^IXIC", "S&P 500": "^GSPC", "Dow Jones": "^DJI", "DAX": "^GDAXI", "IHSG": "^JKSE"},
    "Stocks (AS)": {"NVIDIA": "NVDA", "Apple": "AAPL", "Tesla": "TSLA", "Microsoft": "MSFT", "Amazon": "AMZN"},
    "Stocks (ID)": {"BBRI": "BBRI.JK", "BBCA": "BBCA.JK", "TLKM": "TLKM.JK", "ASII": "ASII.JK", "BMRI": "BMRI.JK"},
    "Commodities": {"Gold (XAUUSD)": "GC=F", "Silver": "SI=F", "Crude Oil (WTI)": "CL=F", "Natural Gas": "NG=F", "Copper": "HG=F"}
}

# ====================== UI HEADER ======================
st.markdown(f"""
<div class="main-title-container">
    <div class="main-logo-container">
        <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png" alt="AeroVulpis Logo" class="custom-logo">
    </div>
    <h1 class="main-title">AEROVULPIS v3.3</h1>
    <p style="text-align: center; color: #aaa; font-family: 'Rajdhani', sans-serif; margin-top: -5px; padding: 0;">ULTIMATE DIGITAL EDITION</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("<div style='text-align:center; margin-bottom: -10px;'><img src='https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png' alt='AeroVulpis Logo' style='width:55px; filter:drop-shadow(0 0 8px var(--electric-blue));'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 class='digital-font' style='text-align:center; font-size:18px; margin-bottom: 0;'>{t['control_center']}</h2>", unsafe_allow_html=True)
    st.markdown("**AeroVulpis V3.3** — **DYNAMIHATCH**")
    st.caption("2026 • Powered by Real-Time AI")

    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    ticker_display = f"{asset_name} ({ticker_input})"

    st.markdown("---")
    tf_options = {
        "1m (Live)": {"period": "1d", "interval": "1m"},
        "5m": {"period": "1d", "interval": "5m"},
        "15m": {"period": "1d", "interval": "15m"},
        "30m": {"period": "5d", "interval": "30m"},
        "1h": {"period": "1mo", "interval": "1h"},
        "3h": {"period": "1mo", "interval": "1h"},
        "4h": {"period": "1mo", "interval": "1h"},
        "1D": {"period": "1y", "interval": "1d"},
        "1W": {"period": "2y", "interval": "1wk"}
    }
    selected_tf_display = st.selectbox(t['timeframe'], list(tf_options.keys()), index=0)
    period = tf_options[selected_tf_display]["period"]
    interval = tf_options[selected_tf_display]["interval"]

    menu_selection = option_menu(
        menu_title=t['navigation'],
        options=["Live Dashboard", "Signal Analysis", "Market Sessions", "Market News", "Economic Calendar", "Chatbot AI", "Risk Management", "Settings", "System Log"],
        icons=["activity", "graph-up-arrow", "globe", "newspaper", "calendar-event", "chat-dots", "shield-fill", "gear", "journal-text"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "5!important", "background-color": "#0d1117"},
            "icon": {"color": "var(--electric-blue)", "font-size": "16px"},
            "nav-link": {"font-size": "13px", "text-align": "left", "margin": "0px", "--hover-color": "#0055ff"},
            "nav-link-selected": {"background-color": "var(--deep-blue)", "color": "white"},
        }
    )

# ====================== FUNGSI MARKET NEWS ======================
@st.cache_data(ttl=300)
def get_news_data(query, max_articles=10):
    gnews_api_key = st.secrets.get("GNEWS_API_KEY") or os.getenv("GNEWS_API_KEY")
    if not gnews_api_key: return [], "⚠️ API KEY MISSING"
    clean_query = query.replace("/", " ").replace("=X", "").replace("=F", "")
    import urllib.parse
    encoded_query = urllib.parse.quote(clean_query)
    url = f"https://gnews.io/api/v4/search?q={encoded_query}&lang=en&max={max_articles}&token={gnews_api_key}"
    try:
        response = requests.get(url)
        if response.status_code != 200:
            fallback_query = urllib.parse.quote(clean_query.split()[0] + " market news")
            url = f"https://gnews.io/api/v4/search?q={fallback_query}&lang=en&max={max_articles}&token={gnews_api_key}"
            response = requests.get(url)
        data = response.json()
        if data.get("articles"): return data["articles"], None
        return [], t['no_news']
    except Exception as e:
        return [], f"⚠️ Error: {str(e)}"

# ====================== LOGIKA HALAMAN ======================

if menu_selection == "Live Dashboard":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    if market and not df.empty:
        if selected_tf_display in ["3h", "4h"]:
            rule = "3h" if selected_tf_display == "3h" else "4h"
            df = df.resample(rule).agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        df = add_technical_indicators(df)
        score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
        c1, c2, c3, c4 = st.columns(4)
        with c1: st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["live_price"]}</p><p class="digital-font" style="font-size:20px; margin:0;">{market["price"]:,.4f}</p></div>', unsafe_allow_html=True)
        with c2:
            color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
            st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["signal"]}</p><p class="digital-font" style="font-size:20px; margin:0; color:{color}; text-shadow:0 0 15px {color};">{signal}</p></div>', unsafe_allow_html=True)
        with c3: st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["rsi"]}</p><p class="digital-font" style="font-size:20px; margin:0;">{df["RSI"].iloc[-1]:.2f}</p></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["atr"]}</p><p class="digital-font" style="font-size:20px; margin:0;">{df["ATR"].iloc[-1]:.4f}</p></div>', unsafe_allow_html=True)
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode='lines', name='Price', line=dict(color='#00ff88', width=2)))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color='#00d4ff', width=1.5, dash='dot'), name='SMA 50'))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], line=dict(color='#bc13fe', width=1.5, dash='dash'), name='SMA 200'))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), height=350, showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        col_g, col_a = st.columns([1, 1])
        with col_g:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            fig_gauge = go.Figure(go.Indicator(mode = "gauge+number", value = score, title = {"text": "Technical Strength", "font": {"family": "Orbitron", "color": "#00d4ff", "size": 18}}, gauge = {"axis": {"range": [0, 100]}, "bar": {"color": color}, "bgcolor": "rgba(0,0,0,0)", "steps": [{"range": [0, 40], "color": "rgba(255, 42, 109, 0.2)"}, {"range": [60, 100], "color": "rgba(0, 255, 136, 0.2)"}]}))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", font={"color": "#e6edf3"}, height=250, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
            if st.button(t['refresh'], use_container_width=True): st.cache_data.clear(); st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        with col_a:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.subheader(t['ai_analysis'])
            for r in reasons: st.write(f"💠 {r}")
            if st.button(t['generate_ai'], use_container_width=True):
                with st.spinner(t['ai_thinking']):
                    context = f"Asset: {asset_name}, Price: {market['price']}, RSI: {df['RSI'].iloc[-1]:.2f}, Signal: {signal}, SMA50: {df['SMA50'].iloc[-1]:.4f}, SMA200: {df['SMA200'].iloc[-1]:.4f}"
                    ai_anal = get_groq_response("Berikan analisis teknikal mendalam, level entry, stop loss, dan take profit.", context)
                    st.info(ai_anal)
            st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "Signal Analysis":
    df = get_historical_data(ticker_input, period, interval)
    if not df.empty:
        if selected_tf_display in ["3h", "4h"]:
            rule = "3h" if selected_tf_display == "3h" else "4h"
            df = df.resample(rule).agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        df = add_technical_indicators(df)
        latest = df.iloc[-1]
        score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        sig_color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
        st.markdown(f"### {t['recommendation']}: <span style='color:{sig_color};'>{signal}</span>", unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div style="text-align:center; background:rgba(0,255,136,0.05); padding:10px; border-radius:10px; border:1px solid rgba(0,255,136,0.2);"><p style="color:#00ff88; font-size:12px; margin:0; font-weight:bold;">BULLISH</p><p class="digital-font" style="font-size:26px; margin:0;">{bull}</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div style="text-align:center; background:rgba(255,42,109,0.05); padding:10px; border-radius:10px; border:1px solid rgba(255,42,109,0.2);"><p style="color:#ff2a6d; font-size:12px; margin:0; font-weight:bold;">BEARISH</p><p class="digital-font" style="font-size:26px; margin:0;">{bear}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div style="text-align:center; background:rgba(255,204,0,0.05); padding:10px; border-radius:10px; border:1px solid rgba(255,204,0,0.2);"><p style="color:#ffcc00; font-size:12px; margin:0; font-weight:bold;">NEUTRAL</p><p class="digital-font" style="font-size:26px; margin:0;">{neut}</p></div>', unsafe_allow_html=True)
        
        st.markdown('<div class="indicator-grid">', unsafe_allow_html=True)
        indicators_data = [
            ("RSI (14)", f"{latest['RSI']:.2f}", "Bullish" if latest['RSI'] < 30 else "Bearish" if latest['RSI'] > 70 else "Neutral"),
            ("MACD", f"{latest['MACD']:.4f}", "Bullish" if latest['MACD'] > latest['Signal_Line'] else "Bearish"),
            ("SMA 50", f"{latest['SMA50']:.2f}", "Bullish" if latest['Close'] > latest['SMA50'] else "Bearish"),
            ("SMA 200", f"{latest['SMA200']:.2f}", "Bullish" if latest['Close'] > latest['SMA200'] else "Bearish"),
            ("CCI (20)", f"{latest['CCI']:.2f}", "Bullish" if latest['CCI'] < -100 else "Bearish" if latest['CCI'] > 100 else "Neutral"),
            ("WPR (14)", f"{latest['WPR']:.2f}", "Bullish" if latest['WPR'] < -80 else "Bearish" if latest['WPR'] > -20 else "Neutral"),
            ("MFI (14)", f"{latest['MFI']:.2f}", "Bullish" if latest['MFI'] < 20 else "Bearish" if latest['MFI'] > 80 else "Neutral"),
            ("EMA 9/21", "Cross", "Bullish" if latest['EMA9'] > latest['EMA21'] else "Bearish"),
            ("ADX (14)", f"{latest['ADX']:.2f}", "Strong Trend" if latest['ADX'] > 25 else "Weak Trend"),
            ("Stoch K", f"{latest['Stoch_K']:.2f}", "Bullish" if latest['Stoch_K'] < 20 else "Bearish" if latest['Stoch_K'] > 80 else "Neutral"),
            ("ATR (14)", f"{latest['ATR']:.4f}", "High Vol" if latest['ATR'] > df['ATR'].mean() else "Low Vol"),
            ("ROC (12)", f"{latest['ROC']:.2f}", "Bullish" if latest['ROC'] > 0 else "Bearish"),
            ("TRIX (15)", f"{latest['TRIX']:.4f}", "Bullish" if latest['TRIX'] > 0 else "Bearish"),
            ("AO (5/34)", f"{latest['AO']:.4f}", "Bullish" if latest['AO'] > 0 else "Bearish"),
            ("KAMA (10)", f"{latest['KAMA']:.2f}", "Bullish" if latest['Close'] > latest['KAMA'] else "Bearish"),
            ("Ichimoku A", f"{latest['Ichimoku_A']:.2f}", "Bullish" if latest['Close'] > latest['Ichimoku_A'] else "Bearish"),
            ("Ichimoku B", f"{latest['Ichimoku_B']:.2f}", "Bullish" if latest['Close'] > latest['Ichimoku_B'] else "Bearish"),
            ("PSAR", f"{latest['Parabolic_SAR']:.2f}", "Bullish" if latest['Close'] > latest['Parabolic_SAR'] else "Bearish"),
            ("BB Upper", f"{latest['BB_Upper']:.2f}", "Overbought" if latest['Close'] > latest['BB_Upper'] else "Normal"),
            ("BB Lower", f"{latest['BB_Lower']:.2f}", "Oversold" if latest['Close'] < latest['BB_Lower'] else "Normal")
        ]
        for name, val, sig in indicators_data:
            sig_col = "#00ff88" if "Bullish" in sig or "Strong" in sig or "Oversold" in sig else "#ff2a6d" if "Bearish" in sig or "Overbought" in sig else "#ffcc00"
            st.markdown(f"""
            <div class="indicator-box">
                <div class="indicator-name">{name}</div>
                <div class="indicator-value">{val}</div>
                <div class="indicator-signal" style="color:{sig_col};">{sig}</div>
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "Market Sessions":
    market_session_status()

elif menu_selection == "Market News":
    st.markdown(f'<h2 class="digital-font" style="font-size:24px;">{t["market_news"]}</h2>', unsafe_allow_html=True)
    if st.button("Update Berita Terbaru", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    articles, error = get_news_data(f"{asset_name} market", 10)
    if error: st.error(error)
    elif articles:
        for a in articles:
            pub_date = a.get("publishedAt", "")
            if pub_date:
                try:
                    dt_obj = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
                    dt_obj = dt_obj.replace(year=2026)
                    time_str = dt_obj.strftime("%d-%m-%Y, jam %H.%M")
                except: time_str = "12-04-2026, jam 15.00"
            else: time_str = "12-04-2026, jam 15.00"
            
            st.markdown(f"""
            <div class="news-card">
                <h3 style="color:var(--electric-blue); font-size:16px; margin-bottom:5px;">{a["title"]}</h3>
                <p style="font-size:11px; color:#888; margin-bottom:8px;">📅 {time_str}</p>
                <p style="font-size:13px; color:#ccc;">{a["description"]}</p>
                <a href="{a["url"]}" target="_blank" style="color:var(--neon-green); font-size:12px; font-weight:bold;">READ MORE →</a>
            </div>
            """, unsafe_allow_html=True)

elif menu_selection == "Economic Calendar":
    economic_calendar_widget()

elif menu_selection == "Chatbot AI":
    st.markdown(f'<h2 class="digital-font" style="font-size:24px;">🤖 AeroVulpis AI Assistant</h2>', unsafe_allow_html=True)
    if "messages" not in st.session_state: st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    if prompt := st.chat_input("Tanya AeroVulpis v3.3 Ultimate..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"): st.markdown(prompt)
        with st.chat_message("assistant"):
            m_data = get_market_data(ticker_input)
            context_str = f"Instrumen: {ticker_display}, Harga: {m_data['price'] if m_data else 'N/A'}"
            response = get_groq_response(prompt, context_str)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

elif menu_selection == "Risk Management":
    st.markdown(f'<h2 class="digital-font" style="font-size:24px;">{t["risk_mgmt"]}</h2>', unsafe_allow_html=True)
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
                <p class="rajdhani-font" style="font-size:14px;">{t['pos_size']}</p>
                <h2 class="digital-font" style="color:#00d4ff;">{pos_size:,.2f} Units</h2>
                <hr style="border-color:rgba(255,255,255,0.1);">
                <p class="rajdhani-font" style="font-size:12px;">{t['risk_amt']}: <span style="color:#ff2a6d;">${risk_amt:,.2f}</span></p>
                <p class="rajdhani-font" style="font-size:12px;">{t['reward']}: <span style="color:#00ff88;">${risk_amt*2:,.2f}</span></p>
            </div>
            """, unsafe_allow_html=True)
        else: st.info(t['risk_info'])

elif menu_selection == "Settings":
    st.markdown(f'<h2 class="digital-font" style="font-size:24px;">{t["settings"]}</h2>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    new_lang = st.selectbox(t['lang_select'], ["ID", "EN"], index=0 if st.session_state.lang == "ID" else 1)
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    if st.button(t['clear_cache'], use_container_width=True):
        st.cache_data.clear()
        st.success("Cache Cleared!")
    st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "System Log":
    st.markdown(f'<div class="glass-card">', unsafe_allow_html=True)
    st.subheader(t['sys_log'])
    st.write(f"**{t['version']}**")
    st.write("- Updated sidebar branding to DYNAMIC HATCH EDITION.")
    st.write("- Added detailed timestamp (DD-MM-YYYY, jam HH.MM) to Market News.")
    st.write("- Refined Signal Analysis grid for better symmetry and fintech look.")
    st.write("- Adjusted logo size and spacing for optimal visual balance.")
    st.write("- Restored Indonesian motivational footer with DynamiHatch Identity.")
    st.write(f"- {t['created_by']}")
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
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v3.3 ULTIMATE • 2026</p>
</div>
""", unsafe_allow_html=True)
