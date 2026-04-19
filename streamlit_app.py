import streamlit as st
from groq import Groq
from news_cache_manager import initialize_news_cache, rotate_news_articles
from widgets import economic_calendar_widget, smart_alert_widget
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
import json
from streamlit_option_menu import option_menu

# Memuat variabel lingkungan dari file .env
from dotenv import load_dotenv
load_dotenv()

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.4 Ultimate", page_icon="🦅", initial_sidebar_state="expanded")

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
        "refresh": "REFRESH TECHNICALS",
        "ai_analysis": "🤖 AeroVulpis Analysis",
        "generate_ai": "GENERATE DEEP AI ANALYSIS",
        "market_sessions": "🌐 Market Sessions",
        "market_news": "📡 Market News",
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
        "version": "v3.4 Ultimate Digital Edition (Current)",
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
        "refresh": "REFRESH TECHNICALS",
        "ai_analysis": "🤖 AeroVulpis Analysis",
        "generate_ai": "GENERATE DEEP AI ANALYSIS",
        "market_sessions": "🌐 Market Sessions",
        "market_news": "📡 Market News",
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
        "version": "v3.4 Ultimate Digital Edition (Current)",
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

      .news-card {
        background: rgba(0, 212, 255, 0.02);
        border: 1px solid rgba(0, 212, 255, 0.1);
        padding: 18px;
        border-radius: 12px;
        margin-bottom: 15px;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        position: relative;
        overflow: hidden;
    }

    .news-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 3px;
        height: 100%;
        background: linear-gradient(to bottom, var(--electric-blue), transparent);
    }

    .news-card:hover {
        background: rgba(0, 212, 255, 0.05);
        border-color: var(--electric-blue);
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
        transform: scale(1.01);
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

    .pillar-container {
        display: grid !important;
        grid-template-columns: repeat(4, 1fr) !important;
        gap: 2px !important;
        margin: 20px 0 !important;
        width: 100% !important;
        overflow: visible !important;
    }

    .pillar-item {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        text-align: center !important;
        min-width: 0 !important;
        overflow: visible !important;
    }

    .pillar-icon {
        width: 35px !important;
        height: 35px !important;
        object-fit: contain !important;
        margin-bottom: 8px !important;
        filter: drop-shadow(0 0 10px #00d4ff) !important;
        -webkit-filter: drop-shadow(0 0 10px #00d4ff) !important;
        overflow: visible !important;
    }

    .pillar-title {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 6px !important;
        font-weight: 700 !important;
        color: #00d4ff !important;
        margin: 0 0 4px 0 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.2px !important;
        text-shadow: 0 0 8px rgba(0, 212, 255, 0.9) !important;
        line-height: 1.0 !important;
        white-space: nowrap !important;
        display: block !important;
    }

    .pillar-desc {
        font-family: 'Rajdhani', sans-serif !important;
        font-size: 6px !important;
        color: #888 !important;
        line-height: 1.0 !important;
        margin: 0 !important;
        white-space: nowrap !important;
    }

    /* AeroVulpis Sentinel Styles */
    .sentinel-container {
        border: 2px solid var(--electric-blue);
        border-radius: 15px;
        padding: 20px;
        background: rgba(0, 212, 255, 0.03);
        box-shadow: 0 0 30px rgba(0, 212, 255, 0.15);
        margin-bottom: 20px;
    }
    .sentinel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
        border-bottom: 1px solid rgba(0, 212, 255, 0.2);
        padding-bottom: 10px;
    }
    .sentinel-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 24px;
        color: var(--electric-blue);
        text-shadow: 0 0 10px var(--electric-blue);
        margin: 0;
    }
    .intelligence-panel {
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid var(--glass-border);
        border-radius: 10px;
        padding: 15px;
        height: 100%;
    }
    .intel-header {
        font-family: 'Orbitron', sans-serif;
        font-size: 16px;
        color: var(--electric-blue);
        margin-bottom: 10px;
        border-left: 3px solid var(--electric-blue);
        padding-left: 10px;
    }
    .intel-content {
        font-family: 'Rajdhani', sans-serif;
        font-size: 14px;
        color: #e0e0e0;
    }
    .status-badge {
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-family: 'Orbitron', sans-serif;
        text-transform: uppercase;
    }
    .status-open { background: rgba(0, 255, 136, 0.1); color: var(--neon-green); border: 1px solid var(--neon-green); }
    .status-ai { background: rgba(0, 212, 255, 0.1); color: var(--electric-blue); border: 1px solid var(--electric-blue); }
</style>
""", unsafe_allow_html=True)

# Konfigurasi API Keys
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
marketaux_key = st.secrets.get("MARKETAUX_KEY") or os.getenv("MARKETAUX_KEY")
tiingo_key = st.secrets.get("TIINGO_KEY") or os.getenv("TIINGO_KEY")
eodhd_key = st.secrets.get("EODHD_KEY") or os.getenv("EODHD_KEY")
twelve_api_key = st.secrets.get("TWELVE_API_KEY") or os.getenv("TWELVE_API_KEY")

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
    # Logika Khusus untuk Emas dan Perak menggunakan Twelve Data
    if ticker_symbol in ["GC=F", "SI=F", "XAUUSD", "XAGUSD"]:
        # Gunakan simbol standar Twelve Data untuk sinkronisasi harga yang lebih baik
        symbol = "XAU/USD" if ticker_symbol in ["GC=F", "XAUUSD"] else "XAG/USD"
        if twelve_api_key:
            # Tambahkan parameter exchange jika perlu, tapi default Twelve Data biasanya cukup akurat
            url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={twelve_api_key}"
            try:
                response = requests.get(url)
                data = response.json()
                if "price" in data:
                    price = float(data["price"])
                    return {"price": price, "change": 0.0, "change_pct": 0.0}
            except: pass
            
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1d")
        if not hist.empty:
            price = hist["Close"].iloc[-1]
            prev_close = hist["Open"].iloc[-1]
            change = price - prev_close
            change_pct = (change / prev_close) * 100
            return {"price": price, "change": change, "change_pct": change_pct}
        return None
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
    # Pastikan indikator tersedia sebelum diproses
    required_cols = ["RSI", "MACD", "Signal_Line", "SMA50", "SMA200", "CCI", "WPR", "MFI", "EMA9", "EMA21", "BB_Lower", "BB_Upper", "ADX", "+DI", "-DI"]
    for col in required_cols:
        if col not in df.columns:
            return 0, "WAITING DATA", ["Data indikator sedang dimuat atau tidak cukup..."], 0, 0, 100

    latest = df.iloc[-1]
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    reasons = []
    
    # 1. RSI
    if latest["RSI"] < 30: bullish_count += 1; reasons.append(f"RSI Oversold ({latest['RSI']:.2f})")
    elif latest["RSI"] > 70: bearish_count += 1; reasons.append(f"RSI Overbought ({latest['RSI']:.2f})")
    else: neutral_count += 1; reasons.append(f"RSI Neutral ({latest['RSI']:.2f})")
    
    # 2. MACD
    if latest["MACD"] > latest["Signal_Line"]: bullish_count += 1; reasons.append("MACD Bullish")
    else: bearish_count += 1; reasons.append("MACD Bearish")
    
    # 3. SMA 50
    if latest["Close"] > latest["SMA50"]: bullish_count += 1; reasons.append("SMA 50 Bullish")
    else: bearish_count += 1; reasons.append("SMA 50 Bearish")

    # 4. SMA 200 (TAMBAHAN)
    if latest["Close"] > latest["SMA200"]: bullish_count += 1; reasons.append("SMA 200 Bullish")
    else: bearish_count += 1; reasons.append("SMA 200 Bearish")
    
    total = bullish_count + bearish_count + neutral_count
    score = (bullish_count / total) * 100 if total > 0 else 50
    
    if score > 70: signal = "STRONG BUY"
    elif score > 55: signal = "BUY"
    elif score < 30: signal = "STRONG SELL"
    elif score < 45: signal = "SELL"
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
    6. Anda memiliki akses ke Smart Alerts yang dipasang oleh user. Jika ditanya tentang alert, periksa st.session_state.active_alerts.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            model=MODEL_NAME, temperature=0.7, max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ====================== FUNGSI SENTINEL ANALYSIS (Model 405B) ======================
def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    """Fungsi khusus untuk AeroVulpis Sentinel menggunakan Hermes 3 405B via OpenRouter"""
    openrouter_api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    
    if not openrouter_api_key:
        return "⚠️ OpenRouter API Key tidak ditemukan. Harap tambahkan OPENROUTER_API_KEY di secrets Streamlit."
    
    # Menggunakan model Hermes 3 405B dari OpenRouter
    MODEL_NAME = 'nousresearch/hermes-3-llama-3.1-405b' 
    
    latest = df.iloc[-1]
    price = market_data['price']
    
    # Ambil berita terbaru untuk konteks fundamental
    news_list, _ = get_news_data(asset_name, max_articles=5)
    news_context = "\n".join([f"- {n['title']} ({n['source']})" for n in news_list]) if news_list else "Tidak ada berita terbaru."

    prompt = f"""
    Anda adalah AeroVulpis Sentinel Intelligence, sistem AI Pro tingkat lanjut (AeroVulpis Core V3.4).
    Tugas Anda adalah memberikan analisis institusional mendalam untuk {asset_name}.

    INFO DASAR:
    Instrumen: {asset_name}
    Tanggal: {datetime.now().strftime('%d %B %Y')}
    Harga saat ini: {price:,.4f}

    DATA PASAR TEKNIS:
    - Sinyal Teknis: {signal}
    - Indikator: RSI={latest.get('RSI', 0):.2f}, MACD={latest.get('MACD', 0):.4f}, ATR={latest.get('ATR', 0):.4f}
    - Alasan Teknis: {", ".join(reasons)}

    BERITA & FUNDAMENTAL:
    {news_context}

    STRUKTUR OUTPUT (WAJIB):
    SENTINEL INTELLIGENCE REPORT

    KEY LEVELS:  
    Support: [2-3 level + alasan singkat]  
    Resistance: [2-3 level + alasan singkat]

    FUNDAMENTAL INSIGHT:  
    [Ringkas faktor utama yang mempengaruhi instrumen ini saat ini (suku bunga, inflasi, geopolitik, dll) secara seimbang.]

    TRADE SCENARIOS:

    Bullish:  
    Entry:  
    Target:  
    Stop Loss:  
    R:R:

    Bearish:  
    Entry:  
    Target:  
    Stop Loss:  
    R:R:

    FINAL VERDICT:  
    [Kesimpulan netral (Buy/Sell/Wait) + risiko utama yang harus diwaspadai.]

    ATURAN TAMBAHAN:
    - Jawab dalam bahasa Indonesia yang jelas dan ringkas.
    - Total maksimal 320 kata.
    - Selalu seimbang antara bullish dan bearish.
    - Dasarkan pada data terkini April 2026.
    - Buat sangat ringkas.
    """
    
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps({
                "model": MODEL_NAME,
                "messages": [
                    {"role": "system", "content": "Anda adalah AeroVulpis Sentinel Pro Intelligence yang didukung oleh Hermes 3 405B."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.6,
                "max_tokens": 1500
            })
        )
        result = response.json()
        if "choices" in result:
            return result["choices"][0]["message"]["content"]
        else:
            return f"⚠️ OpenRouter Error: {result.get('error', {}).get('message', 'Unknown error')}"
    except Exception as e:
        return f"⚠️ Sentinel Error: {str(e)}"

# ====================== FUNGSI DEEP ANALYSIS (Model 70B) ======================
def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    """Fungsi khusus untuk Generate Deep Analysis menggunakan Llama-3.1-70b"""
    if not client: return "⚠️ Deep Analysis Inactive"
    
    MODEL_NAME = 'llama-3.3-70b-versatile'  # Diperbarui ke model yang didukung
    
    # Ambil data teknikal terbaru
    latest = df.iloc[-1]
    price = market_data['price']
    
    # Format data untuk konteks
    technical_data = f"""
    INSTRUMEN: {asset_name}
    HARGA SAAT INI: {price:,.4f}
    SINYAL: {signal}
    
    INDIKATOR TEKNIKAL:
    - RSI (14): {latest['RSI']:.2f}
    - MACD: {latest['MACD']:.4f} (Signal: {latest['Signal_Line']:.4f})
    - SMA 50: {latest['SMA50']:.4f}
    - SMA 200: {latest['SMA200']:.4f}
    - ATR (14): {latest['ATR']:.4f}
    - Stochastic K: {latest['Stoch_K']:.2f}
    - ADX (14): {latest['ADX']:.2f}
    - Bollinger Bands Upper: {latest['BB_Upper']:.4f}, Lower: {latest['BB_Lower']:.4f}
    - Volume Profile: {df['Volume'].iloc[-1]:,.0f}
    
    ANALISIS SINGKAT:
    {', '.join(reasons)}
    """
    
    system_prompt = f"""
    Anda adalah AeroVulpis Deep Analysis Engine - AI Trading Analyst Profesional Tingkat Lanjut.
    Waktu: {datetime.now().strftime('%d %B %Y, %H:%M:%S WIB')}
    Bahasa: {st.session_state.lang}
    
    ANDA ADALAH EXPERT DALAM:
    1. Analisis Teknikal Mendalam (Support/Resistance, Trend Analysis, Pattern Recognition)
    2. Korelasi Fundamental (The Fed, Geopolitik, Berita Pasar)
    3. Money Management & Risk-Reward Ratio
    4. Market Microstructure & Order Flow
    
    INSTRUKSI ANALISIS WAJIB:
    1. ANALISIS TEKNIKAL: Berikan interpretasi mendalam tentang RSI (14) dan SMA 200. Jelaskan apakah RSI menunjukkan jenuh beli/jual dan apakah harga berada di atas atau di bawah SMA 200 sebagai penentu tren jangka panjang.
    2. LEVEL ENTRY: Tentukan 2-3 level entry dengan alasan spesifik (support, breakout, retracement).
    3. STOP LOSS: Tentukan level SL berdasarkan ATR dan struktur pasar (jangan lebih dari 2% dari entry).
    4. TAKE PROFIT: Tentukan 2-3 level TP dengan risk-reward ratio minimal 1:2.
    5. TIMEFRAME: Sesuaikan rekomendasi dengan timeframe yang digunakan.
    6. RISK MANAGEMENT: Berikan ukuran posisi dan manajemen risiko yang optimal.
    7. SCENARIO: Jelaskan kondisi bearish dan bullish yang mungkin terjadi.
    
    FORMAT OUTPUT:
    - Gunakan markdown untuk struktur yang jelas
    - Gunakan emoji untuk visual yang menarik
    - Jangan lebih dari 2000 karakter
    - Fokus pada actionable insights, bukan teori panjang
    """
    
    user_prompt = f"""Berikan analisis teknikal mendalam dengan level entry, stop loss, dan take profit berdasarkan data berikut:
    
    {technical_data}
    
    Analisis WAJIB mencakup:
    1. Interpretasi mendalam RSI (14) saat ini: {latest['RSI']:.2f}
    2. Interpretasi posisi harga terhadap SMA 200: {latest['SMA200']:.4f}
    3. Level entry spesifik (2-3 pilihan) berdasarkan Support/Resistance atau FVG.
    4. Stop loss yang tepat (berdasarkan ATR: {latest['ATR']:.4f}).
    5. Take profit dengan ratio minimal 1:2.
    6. Risk management (Position sizing).
    7. Skenario bullish dan bearish.
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=MODEL_NAME,
            temperature=0.6,  # Lebih rendah untuk konsistensi analisis
            max_tokens=2000,
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
        
        # Digital Neon Status Badge
        if is_active:
            status_html = f'<span style="padding: 2px 8px; border-radius: 4px; background: rgba(0, 255, 136, 0.1); border: 1px solid #00ff88; color: #00ff88; font-size: 10px; box-shadow: 0 0 10px rgba(0, 255, 136, 0.3);">ACTIVE</span>'
        else:
            status_html = f'<span style="padding: 2px 8px; border-radius: 4px; background: rgba(255, 42, 109, 0.1); border: 1px solid #ff2a6d; color: #ff2a6d; font-size: 10px; opacity: 0.6;">CLOSED</span>'
            
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
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
                <span style="font-family:Orbitron; font-weight:bold; color:{sess['color']}; flex:1; font-size: 14px;">{sess['name']}</span>
                {status_html}
            </div>
            <div style="font-family:Rajdhani; font-size:12px; color:#888; margin-bottom:5px;">{sess['start'].strftime('%H:%M')} - {sess['end'].strftime('%H:%M')} WIB</div>
            <div style="background:rgba(255,255,255,0.1); height:6px; border-radius:3px; overflow:hidden;">
                <div style="background:{sess['color'] if is_active else '#444'}; width:{progress if is_active else 0}%; height:100%; transition:width 0.5s ease; box-shadow: 0 0 10px {sess['color'] if is_active else 'transparent'};"></div>
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
    "Commodities": {"Gold (XAUUSD)": "GC=F", "Silver (XAGUSD)": "SI=F", "Crude Oil (WTI)": "CL=F", "Natural Gas": "NG=F", "Copper": "HG=F", "Palladium": "PA=F", "Platinum": "PL=F"}
}

# ====================== UI HEADER ======================
st.markdown(f"""
<div class="main-title-container">
    <div class="main-logo-container">
        <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png" alt="AeroVulpis Logo" class="custom-logo">
    </div>
    <h1 class="main-title">AEROVULPIS v3.4</h1>
    <p style="text-align: center; color: #aaa; font-family: 'Rajdhani', sans-serif; margin-top: -5px; padding: 0;">ULTIMATE DIGITAL EDITION</p>
</div>
""", unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.markdown("<div style='text-align:center; margin-bottom: -10px;'><img src='https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png' alt='AeroVulpis Logo' style='width:55px; filter:drop-shadow(0 0 8px var(--electric-blue));'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 class='digital-font' style='text-align:center; font-size:18px; margin-bottom: 0;'>{t['control_center']}</h2>", unsafe_allow_html=True)
    st.markdown("**AeroVulpis V3.4** — **DYNAMIHATCH**")
    st.caption("2026 • Powered by Real-Time AI")

    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    ticker_display = f"{asset_name} ({ticker_input})"

    st.markdown("---")
    tf_options = {
        "5m": {"period": "5d", "interval": "5m"},
        "15m": {"period": "5d", "interval": "15m"},
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
        options=["Live Dashboard", "AeroVulpis Sentinel", "Signal Analysis", "Market Sessions", "Market News", "Economic Radar", "Smart Alert Center", "Chatbot AI", "Risk Management", "Settings", "Help & Support"],
        icons=["activity", "shield-shaded", "graph-up-arrow", "globe", "newspaper", "calendar-event", "bell-fill", "chat-dots", "shield-fill", "gear", "question-circle"],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "5!important", "background-color": "#0d1117"},
            "icon": {"color": "var(--electric-blue)", "font-size": "16px"},
            "nav-link": {"font-size": "13px", "text-align": "left", "margin": "0px", "--hover-color": "#0055ff"},
            "nav-link-selected": {"background-color": "var(--deep-blue)", "color": "white"},
        }
    )

# ====================== FUNGSI MARKET NEWS (HYBRID: MARKETAUX & EODHD) ======================
@st.cache_data(ttl=1200)
def get_news_data(query, max_articles=20):
    """Mengambil berita dari Marketaux dan EODHD, memastikan 10 berita muncul dengan fallback cerdas."""
    berita_final = []
    urls_terpakai = set()

    # --- 1. AMBIL DARI MARKETAUX (Prioritas Utama) ---
    if marketaux_key:
        try:
            url_m = f"https://api.marketaux.com/v1/news/all?api_token={marketaux_key}&language=en&limit=25"
            res_m = requests.get(url_m, timeout=10).json()
            for item in res_m.get('data', []):
                if item.get('url') and item['url'] not in urls_terpakai:
                    berita_final.append({
                        'publishedAt': item.get('published_at', ''),
                        'title': item.get('title', 'No Title'),
                        'description': item.get('description', ''),
                        'source': 'Marketaux',
                        'url': item['url']
                    })
                    urls_terpakai.add(item['url'])
        except Exception as e:
            pass # Silent fail to proceed to fallback

    # --- 2. AMBIL DARI EODHD (Fallback Utama & Tambahan) ---
    # Jika Marketaux gagal atau berita kurang dari 10, ambil dari EODHD
    if eodhd_key:
        try:
            # EODHD General News API
            url_e = f"https://eodhd.com/api/news?api_token={eodhd_key}&s=general&limit=20&fmt=json"
            res_e = requests.get(url_e, timeout=10).json()
            if isinstance(res_e, list):
                for item in res_e:
                    if item.get('link') and item['link'] not in urls_terpakai:
                        berita_final.append({
                            'publishedAt': item.get('date', ''),
                            'title': item.get('title', 'No Title'),
                            'description': item.get('content', item.get('title', '')),
                            'source': 'EODHD News',
                            'url': item['link']
                        })
                        urls_terpakai.add(item['link'])
        except Exception as e:
            pass

    # --- 3. AMBIL DARI TIINGO (Opsi Terakhir) ---
    if tiingo_key and len(berita_final) < 10:
        try:
            ticker_query = query.replace("/", "").replace("-USD", "").replace("=X", "").replace(".JK", "").split(".")[0]
            url_t = f"https://api.tiingo.com/tiingo/news?tickers={ticker_query}&token={tiingo_key}&limit=10"
            res_t = requests.get(url_t, timeout=10).json()
            if isinstance(res_t, list):
                for item in res_t:
                    if item.get('url') and item['url'] not in urls_terpakai:
                        berita_final.append({
                            'publishedAt': item.get('publishedDate', ''),
                            'title': item.get('title', 'No Title'),
                            'description': item.get('description', item.get('title', '')),
                            'source': 'Tiingo',
                            'url': item['url']
                        })
                        urls_terpakai.add(item['url'])
        except:
            pass

    if not berita_final:
        return [], t['no_news'] + " (Cek API Key Marketaux/EODHD Anda)"

    # Urutkan berdasarkan waktu terbaru
    try:
        # Normalisasi format tanggal untuk sorting jika perlu, namun asumsikan ISO format dari API
        berita_final = sorted(berita_final, key=lambda x: x['publishedAt'], reverse=True)
    except:
        pass

    # Batasi hasil
    berita_final = berita_final[:max_articles]
    
    # Format waktu untuk tampilan AeroVulpis (Konversi ke WIB)
    import pytz
    tz_wib = pytz.timezone('Asia/Jakarta')
    
    for b in berita_final:
        try:
            raw_date = b['publishedAt'].replace('Z', '+00:00') if b['publishedAt'] else ''
            if raw_date:
                try:
                    dt_utc = datetime.fromisoformat(raw_date)
                except:
                    # Fallback untuk format yang mungkin tidak standar
                    dt_utc = datetime.strptime(raw_date[:19], "%Y-%m-%dT%H:%M:%S")
                    dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
                    
                dt_wib = dt_utc.astimezone(tz_wib)
                b['publishedAt'] = dt_wib.strftime("%d-%m-%Y %H.%M")
            else:
                b['publishedAt'] = 'N/A'
        except:
            b['publishedAt'] = 'N/A'
            
    return berita_final, None

# ====================== FUNGSI PENGECEKAN SMART ALERT ======================
def check_smart_alerts():
    """
    Memeriksa semua alert aktif secara global dengan mengambil data harga terbaru
    untuk setiap instrumen yang ada di daftar alert.
    """
    if "active_alerts" not in st.session_state or not st.session_state.active_alerts:
        return

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or st.secrets.get("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        return

    # Kumpulkan instrumen unik yang perlu dicek harganya
    unique_instruments = list(set([a["instrument"] for a in st.session_state.active_alerts if not a.get("triggered")]))
    if not unique_instruments:
        return

    # Map nama instrumen ke ticker yfinance/twelve
    instrument_to_ticker = {}
    for cat in instruments.values():
        for name, ticker in cat.items():
            instrument_to_ticker[name] = ticker

    # Cek harga untuk setiap instrumen
    current_prices = {}
    for inst in unique_instruments:
        ticker = instrument_to_ticker.get(inst)
        if ticker:
            m_data = get_market_data(ticker)
            if m_data:
                current_prices[inst] = m_data["price"]

    for alert in st.session_state.active_alerts:
        if not alert.get("triggered", False):
            inst_name = alert.get("instrument")
            current_price = current_prices.get(inst_name)
            
            if current_price is None:
                continue

            target = alert["target"]
            condition = alert["condition"]
            triggered = False

            if condition == "bullish" and current_price >= target:
                triggered = True
            elif condition == "bearish" and current_price <= target:
                triggered = True

            if triggered:
                alert["triggered"] = True
                from datetime import datetime
                import pytz
                now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")

                # Desain Terminal Cyber-Tech AeroVulpis
                top_border    = "╔═══════════════════════════════════╗"
                status_line   = "║ [ STATUS: TARGET REACHED! ]       ║"
                mid_border    = "╠═══════════════════════════════════╣"
                instr_val     = str(inst_name)[:18]
                price_val     = f"${current_price:,.2f}"
                target_val    = f"${target:,.2f}"
                cond_display  = "BULLISH BREAKOUT ↑" if condition == "bullish" else "BEARISH BREAKDOWN ↓"
                
                instr_line    = f"║ INSTR: {instr_val:<26} ║"
                price_line    = f"║ PRICE: {price_val:<26} ║"
                target_line   = f"║ TARGET: {target_val:<25} ║"
                cond_line     = f"║ COND : {cond_display:<26} ║"
                time_line     = f"║ TIME : {now_wib:<26} ║"
                bottom_border = "╚═══════════════════════════════════╝"

                alert_message = (
                    "<b>🚨 AEROVULPIS TARGET BREACHED!</b>\n"
                    "<i>Market Sensor Protocol Triggered</i>\n\n"
                    "<pre>\n"
                    f"{top_border}\n"
                    f"{status_line}\n"
                    f"{mid_border}\n"
                    f"{instr_line}\n"
                    f"{price_line}\n"
                    f"{target_line}\n"
                    f"{cond_line}\n"
                    f"{time_line}\n"
                    f"{bottom_border}\n"
                    "</pre>\n"
                    "🎯 <b>Price target successfully hit!</b>\n"
                    "🦅 <i>AeroVulpis Monitoring Complete.</i>"
                )

                # Kirim ke Telegram
                url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
                payload = {'chat_id': alert["chat_id"], 'text': alert_message, 'parse_mode': 'HTML'}
                try:
                    requests.post(url, json=payload, timeout=10)
                    st.toast(f"🚀 ALERT TERPICU: {inst_name} menyentuh {target_val}!", icon="🚨")
                except:
                    pass

# ====================== LOGIKA HALAMAN ======================

# Jalankan pengecekan alert secara global di setiap rerun
check_smart_alerts()

if menu_selection == "AeroVulpis Sentinel":
    st.markdown(f"""
    <div class="sentinel-container">
        <div class="sentinel-header" style="flex-direction: column; align-items: flex-start;">
            <h2 class="sentinel-title">AEROVULPIS SENTINEL</h2>
            <div style="display: flex; gap: 10px; margin-top: 10px;">
                <span class="status-badge status-open">MARKET STATUS: OPEN</span>
                <span class="status-badge status-ai">AI STATUS: AEROVULPIS CORE V3.4 (PRO)</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col_chart, col_intel = st.columns([2, 1])
    
    with col_chart:
        # TradingView Advanced Real-Time Chart Widget
        # Kita perlu menyesuaikan simbol untuk TradingView
        tv_symbol = ticker_input.replace("-USD", "USD").replace("=X", "").replace(".JK", "")
        if "GC=F" in ticker_input: tv_symbol = "COMEX:GC1!"
        elif "SI=F" in ticker_input: tv_symbol = "COMEX:SI1!"
        elif "CL=F" in ticker_input: tv_symbol = "NYMEX:CL1!"
        
        tv_html = f"""
        <div class="tradingview-widget-container" style="height:500px; width:100%;">
          <div id="tradingview_sentinel" style="height:500px;"></div>
          <script type="text/javascript" src="https://s3.tradingview.com/tv.js"></script>
          <script type="text/javascript">
          new TradingView.widget({{
            "autosize": true,
            "symbol": "{tv_symbol}",
            "interval": "D",
            "timezone": "Asia/Jakarta",
            "theme": "dark",
            "style": "1",
            "locale": "en",
            "toolbar_bg": "#f1f3f6",
            "enable_publishing": false,
            "hide_side_toolbar": false,
            "allow_symbol_change": true,
            "container_id": "tradingview_sentinel"
          }});
          </script>
        </div>
        """
        st.components.v1.html(tv_html, height=500)
        
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("GENERATE DEEP ANALYSIS PRO", key="sentinel_pro_btn", use_container_width=True):
            market = get_market_data(ticker_input)
            df = get_historical_data(ticker_input, period, interval)
            if market and not df.empty:
                df = add_technical_indicators(df)
                score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
                
                with st.spinner("Sentinel Intelligence sedang memproses data pasar..."):
                    analysis = get_sentinel_analysis(asset_name, market, df, signal, reasons)
                    st.session_state.sentinel_analysis = analysis
            else:
                st.error("Gagal mengambil data pasar untuk analisis.")

    with col_intel:
        st.markdown("""
        <div class="intelligence-panel">
            <div class="intel-header">SENTINEL INTELLIGENCE</div>
            <div class="intel-content">
        """, unsafe_allow_html=True)
        
        if "sentinel_analysis" in st.session_state:
            st.markdown(st.session_state.sentinel_analysis)
        else:
            st.info("Klik tombol di bawah grafik untuk memulai analisis AI Pro tingkat lanjut.")
            
        st.markdown("""
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "Live Dashboard":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    if market and not df.empty:
        if selected_tf_display in ["3h", "4h"]:
            rule = "3h" if selected_tf_display == "3h" else "4h"
            df = df.resample(rule).agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        df = add_technical_indicators(df)
        score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
        c1, c2, c3, c4 = st.columns(4)
        # Format desimal: 2 angka untuk Emas/Perak, 4 angka untuk Forex, hapus nol berlebih
        # Menggunakan format khusus untuk Gold (XAUUSD) agar tidak terlalu banyak nol
        if "Gold" in asset_name or "XAU" in asset_name or "XAG" in asset_name:
            formatted_price = f"{market['price']:,.2f}"
        else:
            formatted_price = f"{market['price']:,.4f}".rstrip('0').rstrip('.')
            
        with c1: st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["live_price"]}</p><p class="digital-font" style="font-size:20px; margin:0;">{formatted_price}</p></div>', unsafe_allow_html=True)
        with c2:
            color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
            st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["signal"]}</p><p class="digital-font" style="font-size:20px; margin:0; color:{color}; text-shadow:0 0 15px {color};">{signal}</p></div>', unsafe_allow_html=True)
        rsi_val = df["RSI"].iloc[-1] if "RSI" in df.columns else 0.0
        atr_val = df["ATR"].iloc[-1] if "ATR" in df.columns else 0.0
        with c3: st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["rsi"]}</p><p class="digital-font" style="font-size:20px; margin:0;">{rsi_val:.2f}</p></div>', unsafe_allow_html=True)
        with c4: st.markdown(f'<div class="glass-card"><p style="color:#888; margin:0; font-size:10px;">{t["atr"]}</p><p class="digital-font" style="font-size:20px; margin:0;">{atr_val:.4f}</p></div>', unsafe_allow_html=True)
        # Price Difference Display Removed
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode='lines', name='Price', line=dict(color='#00ff88', width=2)))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color='#00d4ff', width=1.5, dash='dot'), name='SMA 50'))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], line=dict(color='#bc13fe', width=1.5, dash='dash'), name='SMA 200'))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=10, b=10), height=350, showlegend=True, legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5))
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
                    ai_anal = get_deep_analysis(asset_name, market, df, signal, reasons)
                    st.info(ai_anal)
            st.markdown("</div>", unsafe_allow_html=True)

elif menu_selection == "Signal Analysis":
    market = get_market_data(ticker_input)
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
            ("SMA 50", f"{latest['SMA50']:.4f}".rstrip('0').rstrip('.'), "Bullish" if latest['Close'] > latest['SMA50'] else "Bearish"),
            ("SMA 200", f"{latest['SMA200']:.4f}".rstrip('0').rstrip('.'), "Bullish" if latest['Close'] > latest['SMA200'] else "Bearish"),
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
    st.markdown(f'<h2 class="digital-font" style="font-size: 24px; margin-bottom: 15px;">{t["market_news"]}</h2>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:12px; color:#888; margin-bottom:15px;">Berita real-time dari media-media resmi dan terpercaya | Diperbarui secara cerdas setiap 20 menit</p>', unsafe_allow_html=True)
    
    # Inisialisasi news cache
    initialize_news_cache()
    
    # Ambil berita terbaru
    articles, error = get_news_data(f"{asset_name}", 20)  # Ambil lebih banyak untuk buffer rotasi
    
    if error: 
        st.error(error)
    elif articles:
        # Terapkan rotasi berita (update setiap 20 menit, hapus 1 lama, tambah 1 baru)
        rotated_articles = rotate_news_articles(articles, max_articles=10)
        
        if rotated_articles:
            # Tampilkan berita yang sudah dirotasi
            for idx, a in enumerate(rotated_articles, 1):
                time_str = a.get("publishedAt", "N/A")
                source_name = a.get("source", "Market News")
                
                st.markdown(f"""
                <div class="news-card">
                    <h3 style="color:var(--electric-blue); font-size:16px; margin-bottom:5px;">{a["title"]}</h3>
                    <p style="font-size:11px; color:#888; margin-bottom:8px;">🌐 {source_name} | 📅 {time_str}</p>
                    <p style="font-size:13px; color:#ccc;">{a["description"]}</p>
                    <a href="{a["url"]}" target="_blank" style="color:var(--neon-green); font-size:12px; font-weight:bold;">READ MORE →</a>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Tidak ada berita tersedia saat ini. Sistem akan memperbarui berita dalam 20 menit.")
    else:
        st.warning("Tidak dapat memuat berita. Pastikan API Key Marketaux dan Tiingo sudah dikonfigurasi dengan benar.")


elif menu_selection == "Economic Radar":
    economic_calendar_widget()
elif menu_selection == "Smart Alert Center":
    smart_alert_widget()

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
            if "active_alerts" in st.session_state:
                context_str += f", Active Alerts: {st.session_state.active_alerts}"
            response = get_groq_response(prompt, context_str)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

elif menu_selection == "Risk Management":
    st.markdown('<h2 class="digital-font" style="text-align:center; font-size:26px; margin-bottom:10px;">Ultimate Risk Framework & Return Simulator</h2>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center; color:#888; font-family:Rajdhani; margin-top:-10px;">The Four Pillars of Survival</p>', unsafe_allow_html=True)
    
    # Four Pillars Icons - Redesigned with Flexbox for Perfect Alignment
    st.markdown("""
    <div class="pillar-container">
        <div class="pillar-item">
            <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/lxtUFfqAGtqmckoG.png" class="pillar-icon">
            <p class="pillar-title">1. TRADING RULES</p>
            <p class="pillar-desc">Stop Loss & Definition Rules.</p>
        </div>
        <div class="pillar-item">
            <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/IrMPKUKVGNWfJYiT.png" class="pillar-icon">
            <p class="pillar-title">2. POSITION SIZING</p>
            <p class="pillar-desc">Scale & Size.</p>
        </div>
        <div class="pillar-item">
            <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/KvlBOIcTGsUXIlxi.png" class="pillar-icon">
            <p class="pillar-title">3. CONFIDENCE SCORES</p>
            <p class="pillar-desc">Real-time Chart.</p>
        </div>
        <div class="pillar-item">
            <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/XagmGYTISfZpBVMv.png" class="pillar-icon">
            <p class="pillar-title">4. RISK MGMT</p>
            <p class="pillar-desc">Risk Strategy.</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="glass-card" style="border-left: 4px solid #00d4ff; padding:15px; margin-top:15px;">
        <p class="digital-font" style="font-size:14px; color:#00d4ff; margin-bottom:5px;">AeroVulpis Intelligence Rules</p>
        <p style="font-size:11px; color:#ccc; margin:2px 0;"><b>TP:</b> Target Price for Profit Taking</p>
        <p style="font-size:11px; color:#ccc; margin:2px 0;"><b>SL:</b> Stop Loss Price Protection</p>
        <p style="font-size:11px; color:#ccc; margin:2px 0;"><b>Wait:</b> Wait for Perfect Confidence</p>
        <p style="font-size:11px; color:#ccc; margin:2px 0;"><b>Rule 4:</b> Custom Strategy Rule 4</p>
    </div>
    """, unsafe_allow_html=True)

    # Funding Details
    st.markdown('<p style="font-family:Orbitron; font-size:14px; margin-top:20px; color:#888;">FUNDING DETAILS</p>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card" style="border: 1px solid #00d4ff;">', unsafe_allow_html=True)
    st.markdown('<p style="font-family:Orbitron; font-size:12px; color:#00d4ff; margin-bottom:5px;">ACCOUNT BALANCE ($)</p>', unsafe_allow_html=True)
    balance = st.number_input("", value=1000.0, step=100.0, key="sim_balance", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)

    # Reward-to-Risk Simulator (Custom Fintech UI)
    st.markdown('<p style="font-family:Orbitron; font-size:14px; margin-top:20px; color:#888;">REWARD-TO-RISK SIMULATOR</p>', unsafe_allow_html=True)
    
    rr_ratios = {
        "1:2": 2.0, "1:3": 3.0, "1:4": 4.0,
        "2:3": 1.5, "2:4": 2.0, "2:5": 2.5,
        "3:4": 1.33, "3:5": 1.67, "3:6": 2.0
    }
    
    # CSS for Neon Buttons
    st.markdown("""
    <style>
    .rr-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin-bottom: 20px;
    }
    .rr-btn {
        background: rgba(0, 212, 255, 0.05);
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 8px;
        padding: 10px;
        text-align: center;
        color: #00d4ff;
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    .rr-btn:hover {
        background: rgba(0, 212, 255, 0.2);
        border-color: #00d4ff;
        box-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
    }
    .rr-btn.active {
        background: linear-gradient(145deg, #00d4ff, #0055ff);
        color: white;
        border-color: #00d4ff;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.6);
    }
    </style>
    """, unsafe_allow_html=True)

    # Menggunakan radio button tersembunyi untuk logika pilihan rasio agar tetap fungsional
    selected_rr = st.radio("Select Ratio", list(rr_ratios.keys()), horizontal=True, key="rr_ratio_radio")
    
    # Win/Loss Inputs
    st.markdown('<p style="font-family:Rajdhani; font-size:14px; margin-top:10px; color:#ccc;">Simulated Weekly Trade Win/Loss</p>', unsafe_allow_html=True)
    w_col, l_col = st.columns(2)
    with w_col:
        wins = st.number_input("Wins:", min_value=0, value=3, step=1, key="sim_wins")
    with l_col:
        losses = st.number_input("Losses:", min_value=0, value=2, step=1, key="sim_losses")

    # Risk per trade dihapus sesuai instruksi, default ke 1% untuk kalkulasi
    risk_per_trade_pct = 1.0 

    if st.button("SIMULATE & CALCULATE RETURNS", use_container_width=True, type="primary"):
        # Logika Kalkulasi
        risk_amt = balance * (risk_per_trade_pct / 100)
        reward_amt = risk_amt * rr_ratios[selected_rr]
        
        weekly_net = (wins * reward_amt) - (losses * risk_amt)
        weekly_return_pct = (weekly_net / balance) * 100
        
        monthly_return_pct = weekly_return_pct * 4
        yearly_return_pct = weekly_return_pct * 52
        
        st.markdown('<p style="font-family:Orbitron; font-size:14px; margin-top:20px; color:#888;">Projected Performance</p>', unsafe_allow_html=True)
        st.markdown('<div class="glass-card" style="border: 1px solid rgba(0, 255, 136, 0.3); background: rgba(0, 255, 136, 0.02);">', unsafe_allow_html=True)
        res_col1, res_col2, res_col3 = st.columns(3)
        
        with res_col1:
            color = "#00ff88" if weekly_return_pct >= 0 else "#ff2a6d"
            arrow = "▲" if weekly_return_pct >= 0 else "▼"
            st.markdown(f'<p style="font-size:10px; color:#aaa; margin:0;">Wkly Return:</p><p style="color:{color}; font-family:Orbitron; font-size:16px; margin:0;">{weekly_return_pct:+.2f}% {arrow}</p>', unsafe_allow_html=True)
            
        with res_col2:
            color = "#00ff88" if monthly_return_pct >= 0 else "#ff2a6d"
            st.markdown(f'<p style="font-size:10px; color:#aaa; margin:0;">Mthly Return:</p><p style="color:{color}; font-family:Orbitron; font-size:16px; margin:0;">{monthly_return_pct:+.2f}%</p>', unsafe_allow_html=True)
            
        with res_col3:
            color = "#00ff88" if yearly_return_pct >= 0 else "#ff2a6d"
            st.markdown(f'<p style="font-size:10px; color:#aaa; margin:0;">Yrly Return:</p><p style="color:{color}; font-family:Orbitron; font-size:16px; margin:0;">{yearly_return_pct:+.2f}%</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.info("Adjust parameters and click the button to simulate returns.")

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

elif menu_selection == "Help & Support":
    st.markdown('<h2 class="digital-font" style="text-align:center; font-size:28px; margin-bottom:20px;">AeroVulpis v3.3 Help & Support</h2>', unsafe_allow_html=True)
    
    with st.expander("1. AEROVULPIS SENTINEL (PRO)", expanded=True):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue);">
                <div style="width: 30px; height: 20px; border-top: 3px solid var(--electric-blue); border-bottom: 3px solid var(--electric-blue); position: relative;">
                    <div style="width: 3px; height: 100%; background: var(--electric-blue); position: absolute; left: 5px;"></div>
                    <div style="width: 3px; height: 100%; background: var(--electric-blue); position: absolute; left: 13px;"></div>
                    <div style="width: 3px; height: 100%; background: var(--electric-blue); position: absolute; left: 21px;"></div>
                </div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">INSTITUTIONAL SENTINEL SYSTEM</div>
        </div>
        **Sentinel** adalah dashboard utama tingkat lanjut yang dirancang untuk analisis institusional.
        
        **TradingView Chart**: Grafik real-time interaktif dengan alat gambar lengkap.
        
        **Generate Deep Analysis Pro**: Menggunakan sistem **AeroVulpis AI Pro** untuk memberikan laporan mendalam tentang *Key Levels*, *Fundamental Insight* (suku bunga), dan skenario trading (Buy/Sell/Wait).
        
        **AI Status**: Menampilkan status model AI yang sedang aktif memproses data.
        """, unsafe_allow_html=True)

    with st.expander("2. LIVE DASHBOARD"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: flex-end; justify-content: center; gap: 3px; padding-bottom: 15px; box-shadow: 0 0 15px var(--electric-blue);">
                <div style="width: 6px; height: 15px; background: var(--electric-blue);"></div>
                <div style="width: 6px; height: 25px; background: var(--electric-blue);"></div>
                <div style="width: 6px; height: 20px; background: var(--electric-blue);"></div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">LIVE DASHBOARD SYSTEM</div>
        </div>
        Pusat pemantauan harga dan sinyal teknikal cepat.
        
        **Live Price**: Harga terkini dari yFinance atau Twelve Data (untuk Gold/Silver).
        
        **Technical Strength**: Gauge yang menunjukkan kekuatan tren berdasarkan 15+ indikator.
        
        **Generate Deep Analysis**: Analisis AI cepat menggunakan sistem **AeroVulpis Intelligence Engine** untuk memberikan alasan di balik sinyal saat ini. Perlu diperhatikan bahwa ada kemungkinan selisih harga antara data live dan eksekusi pasar.
        """, unsafe_allow_html=True)

    with st.expander("3. SIGNAL ANALYSIS"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue);">
                <div style="width: 30px; height: 20px; border-left: 2px solid var(--electric-blue); border-bottom: 2px solid var(--electric-blue); position: relative;">
                    <div style="width: 100%; height: 2px; background: var(--electric-blue); position: absolute; bottom: 5px; transform: rotate(-30deg); transform-origin: left;"></div>
                </div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">TECHNICAL SIGNAL GRID</div>
        </div>
        Grid indikator teknikal lengkap untuk konfirmasi manual.
        
        **Indikator**: RSI, MACD, SMA, EMA, Bollinger Bands, CCI, Williams %R, MFI, TRIX, ROC, Awesome Oscillator, KAMA, Ichimoku, dan Parabolic SAR.
        
        **Warna Sinyal**: Hijau (Bullish), Merah (Bearish), Kuning (Neutral/Normal).
        """, unsafe_allow_html=True)

    with st.expander("4. MARKET SESSIONS & NEWS"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue); position: relative; overflow: hidden;">
                <div style="width: 100%; height: 2px; background: rgba(0, 212, 255, 0.3); position: absolute; top: 30%;"></div>
                <div style="width: 100%; height: 2px; background: rgba(0, 212, 255, 0.3); position: absolute; top: 70%;"></div>
                <div style="width: 2px; height: 100%; background: rgba(0, 212, 255, 0.3); position: absolute; left: 30%;"></div>
                <div style="width: 2px; height: 100%; background: rgba(0, 212, 255, 0.3); position: absolute; left: 70%;"></div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">GLOBAL MARKET INTELLIGENCE</div>
        </div>
        **Market Sessions**: Menampilkan status sesi pasar (Tokyo, London, New York) dan *Golden Time* (volatilitas tinggi).
        
        **Market News**: Berita real-time tentang geopolitik, konflik, dan peristiwa ekonomi global dari berbagai media keuangan resmi dan terpercaya. Diperbarui setiap 20 menit dengan rotasi berita terbaru dari media resmi dan terpercaya.
        """, unsafe_allow_html=True)

    with st.expander("5. SMART ALERT CENTER"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue); position: relative;">
                <div style="width: 20px; height: 20px; border: 2px solid var(--electric-blue); border-radius: 50%;"></div>
                <div style="width: 35px; height: 35px; border: 2px solid rgba(0, 212, 255, 0.5); border-radius: 50%; position: absolute;"></div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">SMART SENSOR NETWORK</div>
        </div>
        Sistem sensor harga otomatis yang terhubung ke Telegram.
        
        **Lock Target**: Masukkan harga target dan Chat ID Telegram Anda.
        
        **Sensor Active**: Sistem akan terus memantau harga di latar belakang dan mengirim notifikasi saat target tercapai.
        
        **Cara Mendapatkan User ID**: Buka Telegram dan cari bot **@userinfobot**, lalu ketik `/start` untuk mendapatkan User ID Anda.
        """, unsafe_allow_html=True)

    with st.expander("6. CHATBOT AI"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue);">
                <div style="width: 25px; height: 25px; border: 2px solid var(--electric-blue); border-radius: 5px; position: relative; display: flex; flex-wrap: wrap; gap: 2px; padding: 3px;">
                    <div style="width: 6px; height: 6px; background: var(--electric-blue);"></div>
                    <div style="width: 6px; height: 6px; background: var(--electric-blue);"></div>
                    <div style="width: 6px; height: 6px; background: var(--electric-blue);"></div>
                    <div style="width: 6px; height: 6px; background: var(--electric-blue);"></div>
                </div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">COGNITIVE AI ASSISTANT</div>
        </div>
        Asisten AI pribadi yang memahami konteks pasar Anda.
        
        Anda bisa bertanya tentang strategi, penjelasan indikator, atau status alert Anda.
        
        AI memiliki akses ke data harga live dan daftar alert aktif Anda.
        """, unsafe_allow_html=True)

    with st.expander("7. ECONOMIC RADAR"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue); position: relative;">
                <div style="width: 20px; height: 20px; border: 2px solid var(--electric-blue); border-radius: 50%;"></div>
                <div style="width: 35px; height: 35px; border: 2px solid rgba(0, 212, 255, 0.5); border-radius: 50%; position: absolute;"></div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">ECONOMIC RADAR SYSTEM</div>
        </div>
        Sistem pemantauan kalender ekonomi global yang mendeteksi peristiwa berdampak tinggi secara real-time.
        
        **High Impact Events**: Menampilkan rilis data ekonomi penting seperti NFP, CPI, dan keputusan suku bunga yang dapat memicu volatilitas besar.
        
        **Real-time Updates**: Data diperbarui secara otomatis untuk memastikan Anda tidak melewatkan momentum pasar yang krusial.
        """, unsafe_allow_html=True)

    with st.expander("8. RISK MANAGEMENT"):
        st.markdown("""
        <div style="text-align: center; margin-bottom: 15px;">
            <div style="width: 60px; height: 60px; margin: 0 auto; border: 2px solid var(--electric-blue); border-radius: 50%; display: flex; align-items: center; justify-content: center; box-shadow: 0 0 15px var(--electric-blue);">
                <div style="width: 30px; height: 20px; border: 2px solid var(--electric-blue); border-radius: 3px; position: relative;">
                    <div style="width: 10px; height: 5px; border: 2px solid var(--electric-blue); border-bottom: none; border-radius: 3px 3px 0 0; position: absolute; top: -7px; left: 8px;"></div>
                </div>
            </div>
            <div style="font-family: 'Orbitron', sans-serif; font-size: 14px; color: var(--electric-blue); margin-top: 5px;">RISK MANAGEMENT PROTOCOL</div>
        </div>
        Framework untuk menjaga kelangsungan akun trading Anda.
        
        **Four Pillars**: Trading Rules, Position Sizing, Confidence Scores, dan Risk Strategy.
        
        **RR Simulator**: Hitung proyeksi keuntungan mingguan, bulanan, dan tahunan berdasarkan rasio Risk-to-Reward dan Win Rate Anda.
        """, unsafe_allow_html=True)

    st.info("**Tips**: Gunakan menu **Settings** untuk mengganti bahasa (ID/EN) atau membersihkan cache jika data terasa lambat diperbarui.")
    
    st.markdown("<div class='glass-card' style='margin-top:20px;'>", unsafe_allow_html=True)
    st.markdown("""
    ### Hubungi Dukungan Teknis
    Jika Anda mengalami kendala teknis atau memiliki pertanyaan lebih lanjut, silakan hubungi kami melalui:
    - **Telegram**: [@AeroVulpisSupport](https://t.me/)
    - **Email**: support@aerovulpis.com
    - **Status Sistem**: Operasional (v3.3 Ultimate)
    """)
    st.markdown("</div>", unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 20px; opacity: 0.8;">
    <p class="rajdhani-font" style="font-style: italic; font-size: 18px; color: #ccc;">
        "Disiplin adalah kunci, emosi adalah musuh. Tetap tenang dan percaya pada sistem."
    </p>
    <p class="digital-font" style="font-size: 15px; color: #00ff88; white-space: nowrap;">
        — Fahmi (Pencipta AeroVulpis)
    </p>
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v3.3 ULTIMATE • 2026</p>
</div>
""", unsafe_allow_html=True)
