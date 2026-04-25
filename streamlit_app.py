import streamlit as st
from groq import Groq
from news_cache_manager import initialize_news_cache, should_update_news, get_cached_news, update_news_cache
from widgets import economic_calendar_widget, smart_alert_widget
import os
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time as dt_time, timedelta
import pytz
import ta
import time
import requests
import json
from streamlit_option_menu import option_menu
from supabase import create_client, Client

# Memuat variabel lingkungan dari file .env
from dotenv import load_dotenv
load_dotenv()

# Konfigurasi Supabase
url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]

def send_log(pesan):
    try:
        supabase: Client = create_client(url, key)
        supabase.table("logs_aktivitas").insert({"keterangan": pesan}).execute()
    except Exception:
        pass

def cleanup_logs():
    try:
        supabase: Client = create_client(url, key)
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        supabase.table("logs_aktivitas").delete().lt("created_at", cutoff).execute()
    except Exception:
        pass

def cache_market_price(symbol, price, change_pct=0.0):
    try:
        supabase: Client = create_client(url, key)
        data = {
            "instrument": symbol, 
            "price": price, 
            "change_pct": change_pct,
            "updated_at": datetime.now(pytz.UTC).isoformat()
        }
        supabase.table("market_prices").upsert(data, on_conflict="instrument").execute()
    except Exception:
        pass

def get_cached_market_price(symbol):
    try:
        supabase: Client = create_client(url, key)
        res = supabase.table("market_prices").select("price").eq("instrument", symbol).execute()
        if res.data:
            return res.data[0]["price"]
    except Exception:
        pass
    return None

def cleanup_old_data():
    try:
        supabase: Client = create_client(url, key)
        cutoff = (datetime.now(pytz.UTC) - timedelta(hours=24)).isoformat()
        supabase.table("market_prices").delete().lt("updated_at", cutoff).execute()
    except Exception:
        pass

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.4 Ultimate", page_icon="🦅", initial_sidebar_state="expanded")

cleanup_logs()
cleanup_old_data()
send_log("AeroVulpis Online")

if "lang" not in st.session_state:
    st.session_state.lang = "ID"

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
        padding: 10px 0;
        margin-bottom: -15px;
        background: transparent !important;
        perspective: 1200px;
        overflow: visible !important;
    }

    .custom-logo {
        width: 100px;
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
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.6) !important;
    }

    /* Sidebar Digital Fintech Style */
    [data-testid="stSidebar"] {
        background-color: #05080d !important;
        border-right: 1px solid rgba(0, 212, 255, 0.2);
    }
    
    [data-testid="stSidebar"] .stSelectbox label, 
    [data-testid="stSidebar"] .stMultiSelect label {
        color: var(--electric-blue) !important;
        font-family: 'Orbitron', sans-serif !important;
        font-size: 11px !important;
        letter-spacing: 1px;
    }

    .sidebar-header {
        padding: 20px 0;
        text-align: center;
        border-bottom: 1px solid rgba(0, 212, 255, 0.1);
        margin-bottom: 20px;
    }

    /* 3D Tech Logo Animation */
    .tech-logo-3d {
        width: 80px;
        height: 80px;
        margin: 20px auto;
        position: relative;
        transform-style: preserve-3d;
        animation: rotate3D 3s linear infinite;
    }
    
    @keyframes rotate3D {
        from { transform: rotateY(0deg) rotateX(0deg); }
        to { transform: rotateY(360deg) rotateX(360deg); }
    }

    .pillar-container {
        display: flex;
        justify-content: space-between;
        gap: 10px;
        margin-bottom: 20px;
    }
    .pillar-item {
        flex: 1;
        background: rgba(0, 212, 255, 0.05);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 10px;
        padding: 10px;
        text-align: center;
        transition: all 0.3s ease;
    }
    .pillar-item:hover {
        background: rgba(0, 212, 255, 0.1);
        border-color: var(--electric-blue);
        transform: translateY(-5px);
    }
    .pillar-icon {
        width: 30px;
        height: 30px;
        margin-bottom: 8px;
        filter: drop-shadow(0 0 5px var(--electric-blue));
    }
    .pillar-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 10px;
        color: var(--electric-blue);
        margin: 0;
    }
    .pillar-desc {
        font-family: 'Rajdhani', sans-serif;
        font-size: 9px;
        color: #aaa;
        margin: 0;
    }
</style>
""", unsafe_allow_html=True)

# Konfigurasi API Keys
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
marketaux_key = st.secrets.get("MARKETAUX_KEY") or os.getenv("MARKETAUX_KEY")
tiingo_key = st.secrets.get("TIINGO_KEY") or os.getenv("TIINGO_KEY")
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
    """
    Sistem Centralized Caching:
    Mengambil data dari Supabase (Cache) jika masih segar (< 3 detik).
    Jika sudah basi, ambil dari yfinance (atau cTrader) dan update cache.
    """
    try:
        # 1. Cek Cache Supabase (Global untuk semua user)
        import pytz
        
        # Mapping nama instrumen dari ticker
        inst_name = ticker_symbol
        for cat in instruments.values():
            for name, tick in cat.items():
                if tick == ticker_symbol:
                    inst_name = name
                    break
        
        # Ambil data terakhir dari Supabase
        supabase_url = st.secrets.get("SUPABASE_URL")
        supabase_key = st.secrets.get("SUPABASE_KEY")
        if supabase_url and supabase_key:
            supabase = create_client(supabase_url, supabase_key)
            res = supabase.table("market_prices").select("*").eq("instrument", inst_name).execute()
            
            if res.data:
                cached = res.data[0]
                updated_at = datetime.fromisoformat(cached['updated_at'].replace('Z', '+00:00'))
                now = datetime.now(pytz.UTC)
                
                # Jika data masih segar (< 3 detik), gunakan cache
                if (now - updated_at).total_seconds() < 3:
                    return {
                        "price": cached['price'],
                        "change": cached['price'] * (cached['change_pct']/100),
                        "change_pct": cached['change_pct'],
                        "source": "Cache"
                    }

        # 2. Jika Cache Basi/Kosong, Ambil Live (yfinance)
        fetch_ticker = ticker_symbol
        ticker = yf.Ticker(fetch_ticker)
        hist = ticker.history(period="2d")
        if not hist.empty:
            price = hist["Close"].iloc[-1]
            
            # Khusus XAUUSD, pastikan tidak ada pembulatan kasar
            if ticker_symbol == "GC=F":
                price = round(float(price), 2)
                
            prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else hist["Open"].iloc[-1]
            change_pct = ((price - prev_close) / prev_close) * 100
            
            # Update Cache Global di Supabase
            cache_market_price(inst_name, price, change_pct)
            
            return {"price": price, "change": price - prev_close, "change_pct": change_pct, "source": "Live"}
        return None
    except Exception:
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
    required_cols = ["RSI", "MACD", "Signal_Line", "SMA50", "SMA200", "CCI", "WPR", "MFI", "EMA9", "EMA21", "BB_Lower", "BB_Upper", "ADX", "+DI", "-DI"]
    for col in required_cols:
        if col not in df.columns:
            return 0, "WAITING DATA", ["Data indikator sedang dimuat atau tidak cukup..."], 0, 0, 100

    latest = df.iloc[-1]
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    reasons = []
    
    if latest["RSI"] < 30: bullish_count += 1; reasons.append(f"RSI Oversold ({latest['RSI']:.2f})")
    elif latest["RSI"] > 70: bearish_count += 1; reasons.append(f"RSI Overbought ({latest['RSI']:.2f})")
    else: neutral_count += 1; reasons.append(f"RSI Neutral ({latest['RSI']:.2f})")
    
    if latest["MACD"] > latest["Signal_Line"]: bullish_count += 1; reasons.append("MACD Bullish Cross")
    else: bearish_count += 1; reasons.append("MACD Bearish Cross")
    
    if latest["Close"] > latest["SMA200"]: bullish_count += 1; reasons.append("Above SMA 200 (Bullish Trend)")
    else: bearish_count += 1; reasons.append("Below SMA 200 (Bearish Trend)")
    
    if latest["Close"] > latest["SMA50"]: bullish_count += 1; reasons.append("Above SMA 50")
    else: bearish_count += 1; reasons.append("Below SMA 50")
    
    if latest["EMA9"] > latest["EMA21"]: bullish_count += 1; reasons.append("EMA 9/21 Bullish Cross")
    else: bearish_count += 1; reasons.append("EMA 9/21 Bearish Cross")
    
    if latest["Close"] < latest["BB_Lower"]: bullish_count += 1; reasons.append("Price below BB Lower")
    elif latest["Close"] > latest["BB_Upper"]: bearish_count += 1; reasons.append("Price above BB Upper")
    
    if latest["CCI"] < -100: bullish_count += 1; reasons.append("CCI Oversold")
    elif latest["CCI"] > 100: bearish_count += 1; reasons.append("CCI Overbought")
    
    if latest["WPR"] < -80: bullish_count += 1; reasons.append("Williams %R Oversold")
    elif latest["WPR"] > -20: bearish_count += 1; reasons.append("Williams %R Overbought")
    
    if latest["MFI"] < 20: bullish_count += 1; reasons.append("MFI Oversold")
    elif latest["MFI"] > 80: bearish_count += 1; reasons.append("MFI Overbought")
    
    if latest["ADX"] > 25:
        if latest["+DI"] > latest["-DI"]: bullish_count += 1; reasons.append("Strong Bullish Trend (ADX)")
        else: bearish_count += 1; reasons.append("Strong Bearish Trend (ADX)")
    else: neutral_count += 1; reasons.append("Weak Trend (ADX)")

    total = bullish_count + bearish_count + neutral_count
    bull_pct = (bullish_count / total) * 100
    bear_pct = (bearish_count / total) * 100
    neut_pct = (neutral_count / total) * 100
    
    score = bull_pct - bear_pct
    if score > 20: signal = "STRONG BUY"
    elif score > 5: signal = "BUY"
    elif score < -20: signal = "STRONG SELL"
    elif score < -5: signal = "SELL"
    else: signal = "NEUTRAL / WAIT"
    
    return score, signal, reasons, bull_pct, bear_pct, neut_pct

# ====================== FUNGSI SENTINEL ANALYSIS (Model Pro) ======================
def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    if not client: return "⚠️ Sentinel Intelligence Inactive"
    
    PRIMARY_MODEL = 'hermes-3-llama-3.1-405b'
    COMPANION_MODEL = 'qwen-2.5-72b-instruct'
    BACKUP_MODELS = ['llama-3.1-70b-versatile', 'mixtral-8x7b-32768']
    
    latest = df.iloc[-1]
    price = market_data['price']
    
    technical_data = f"""
    INSTRUMEN: {asset_name}
    HARGA SAAT INI: {price:,.4f}
    SINYAL: {signal}
    INDIKATOR: RSI={latest['RSI']:.2f}, MACD={latest['MACD']:.4f}, SMA200={latest['SMA200']:.4f}
    ALASAN: {', '.join(reasons)}
    """
    
    def call_openrouter(model, system_msg):
        try:
            prompt = f"Berikan analisis institusional mendalam untuk {asset_name} berdasarkan data: {technical_data}"
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY')}"},
                data=json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ]
                }),
                timeout=45
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            return None
        except:
            return None

    analysis = call_openrouter(PRIMARY_MODEL, "Anda adalah AeroVulpis Sentinel Pro Intelligence (Hermes 405B).")
    if analysis:
        companion_detail = call_openrouter(COMPANION_MODEL, "Berikan detail teknis tambahan untuk analisis ini.")
        if companion_detail:
            analysis += "\n\n---\n**SENTINEL COMPANION (Qwen) ADDITIONAL INSIGHTS:**\n" + companion_detail
    
    if not analysis:
        for model in BACKUP_MODELS:
            analysis = call_openrouter(model, "Anda adalah AeroVulpis Sentinel Backup Intelligence.")
            if analysis:
                analysis = f"⚠️ [SYSTEM]: PRIMARY MODELS LIMIT REACHED. SWITCHING TO BACKUP ({model})\n\n" + analysis
                break
                
    if not analysis:
        return "⚠️ Sentinel Error: Semua model AI sedang sibuk."
            
    return analysis

# ====================== FUNGSI DEEP ANALYSIS (Model 70B) ======================
def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    if not client: return "⚠️ Deep Analysis Inactive"
    MODEL_NAME = 'llama-3.3-70b-versatile'
    latest = df.iloc[-1]
    price = market_data['price']
    technical_data = f"INSTRUMEN: {asset_name}, HARGA: {price:,.4f}, SINYAL: {signal}, RSI: {latest['RSI']:.2f}"
    
    system_prompt = f"Anda adalah AeroVulpis Deep Analysis Engine. Bahasa: {st.session_state.lang}"
    user_prompt = f"Berikan analisis teknikal mendalam untuk {asset_name} berdasarkan data: {technical_data}"
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model=MODEL_NAME,
            temperature=0.6,
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
        status_html = f'<span style="padding: 2px 8px; border-radius: 4px; background: rgba(0, 255, 136, 0.1); border: 1px solid #00ff88; color: #00ff88; font-size: 10px;">ACTIVE</span>' if is_active else f'<span style="padding: 2px 8px; border-radius: 4px; background: rgba(255, 42, 109, 0.1); border: 1px solid #ff2a6d; color: #ff2a6d; font-size: 10px; opacity: 0.6;">CLOSED</span>'
        if is_active: active_sessions.append(sess["name"])
        st.markdown(f'<div class="session-card"><div style="display:flex; justify-content:space-between; align-items:center;"><b>{sess["name"]}</b>{status_html}</div></div>', unsafe_allow_html=True)
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

# ====================== FUNGSI PENGECEKAN SMART ALERT ======================
def check_smart_alerts():
    if "active_alerts" not in st.session_state or not st.session_state.active_alerts:
        return
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or st.secrets.get("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        return
    unique_instruments = list(set([a["instrument"] for a in st.session_state.active_alerts if not a.get("triggered")]))
    if not unique_instruments:
        return
    instrument_to_ticker = {"XAUUSD": "GC=F", "BTCUSD": "BTC-USD", "XAGUSD": "SI=F", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X"}
    for cat in instruments.values():
        for name, ticker in cat.items():
            instrument_to_ticker[name] = ticker
    current_prices = {}
    for inst in unique_instruments:
        price = get_cached_market_price(inst)
        if price is None:
            ticker = instrument_to_ticker.get(inst)
            if ticker:
                m_data = get_market_data(ticker)
                if m_data: price = m_data["price"]
        if price is not None: current_prices[inst] = price
    for alert in st.session_state.active_alerts:
        if not alert.get("triggered", False):
            inst_name = alert.get("instrument")
            current_price = current_prices.get(inst_name)
            if current_price is None: continue
            target = alert["target"]
            condition = alert["condition"]
            triggered = (condition == "bullish" and current_price >= target) or (condition == "bearish" and current_price <= target)
            if triggered:
                alert["triggered"] = True
                st.toast(f"🚀 ALERT TERPICU: {inst_name} menyentuh {target}!", icon="🚨")

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
    st.markdown("<div class='sidebar-header'><img src='https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png' style='width:55px; filter:drop-shadow(0 0 8px var(--electric-blue));'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 class='digital-font' style='text-align:center; font-size:18px; margin-bottom: 0;'>{t['control_center']}</h2>", unsafe_allow_html=True)
    st.markdown("**AeroVulpis V3.4** — **DYNAMIHATCH**")
    st.caption("2026 • Powered by Real-Time AI")
    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    st.markdown("---")
    tf_options = {"15m": {"period": "5d", "interval": "15m"}, "30m": {"period": "5d", "interval": "30m"}, "1h": {"period": "1mo", "interval": "1h"}, "1D": {"period": "1y", "interval": "1d"}}
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
            "container": {"padding": "5!important", "background-color": "#05080d"},
            "icon": {"color": "var(--electric-blue)", "font-size": "16px"},
            "nav-link": {"font-size": "12px", "text-align": "left", "margin": "0px", "--hover-color": "#0055ff", "font-family": "Rajdhani"},
            "nav-link-selected": {"background-color": "rgba(0, 212, 255, 0.1)", "color": "white", "border-left": "3px solid var(--electric-blue)"},
        }
    )

# ====================== LOGIKA HALAMAN ======================
check_smart_alerts()

if menu_selection == "AeroVulpis Sentinel":
    st.markdown('<div class="sentinel-container"><h2 class="sentinel-title">AEROVULPIS SENTINEL</h2>', unsafe_allow_html=True)
    col_chart, col_intel = st.columns([2, 1])
    with col_chart:
        st.info("TradingView Chart Placeholder")
        if st.button("GENERATE DEEP ANALYSIS PRO", key="sentinel_pro_btn", use_container_width=True):
            st.markdown('<div class="tech-logo-3d"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png" style="width:100%;"></div>', unsafe_allow_html=True)
            with st.spinner("Sentinel Intelligence sedang memproses data pasar..."):
                time.sleep(3) # Simulasi pencarian data detail
                market = get_market_data(ticker_input)
                df = get_historical_data(ticker_input, period, interval)
                if market and not df.empty:
                    df = add_technical_indicators(df)
                    score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
                    analysis = get_sentinel_analysis(asset_name, market, df, signal, reasons)
                    st.session_state.sentinel_analysis = analysis
    with col_intel:
        if "sentinel_analysis" in st.session_state: st.markdown(st.session_state.sentinel_analysis)
        else: st.info("Klik tombol untuk memulai analisis AI Pro.")

elif menu_selection == "Live Dashboard":
    market = get_market_data(ticker_input)
    if market:
        st.metric("Price", f"{market['price']:,.2f}", f"{market['change_pct']:+.2f}%")
    else: st.error("Gagal memuat data.")

elif menu_selection == "Smart Alert Center":
    smart_alert_widget()

elif menu_selection == "Risk Management":
    st.markdown('<h2 class="digital-font" style="text-align:center; font-size:26px;">Ultimate Risk Framework & Return Simulator</h2>', unsafe_allow_html=True)
    st.markdown("""
    <div class="pillar-container">
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/lxtUFfqAGtqmckoG.png" class="pillar-icon"><p class="pillar-title">TRADING RULES</p><p class="pillar-desc">Stop Loss & Rules.</p></div>
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/IrMPKUKVGNWfJYiT.png" class="pillar-icon"><p class="pillar-title">POSITION SIZING</p><p class="pillar-desc">Scale & Size.</p></div>
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/KvlBOIcTGsUXIlxi.png" class="pillar-icon"><p class="pillar-title">CONFIDENCE SCORES</p><p class="pillar-desc">Real-time Chart.</p></div>
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/XagmGYTISfZpBVMv.png" class="pillar-icon"><p class="pillar-title">RISK MGMT</p><p class="pillar-desc">Risk Strategy.</p></div>
    </div>
    """, unsafe_allow_html=True)
    
    balance = st.number_input("ACCOUNT BALANCE ($)", value=1000.0, step=100.0, key="sim_balance")
    max_loss_day = st.number_input("MAX LOSS PER DAY ($)", value=balance*0.02, key="max_loss")
    max_profit_day = st.number_input("MAX PROFIT TARGET ($)", value=balance*0.05, key="max_profit")
    
    w_col, l_col = st.columns(2)
    wins = w_col.number_input("Weekly Wins:", min_value=0, value=3)
    losses = l_col.number_input("Weekly Losses:", min_value=0, value=2)
    
    if st.button("SIMULATE & CALCULATE RETURNS", use_container_width=True, type="primary"):
        risk_amt = balance * 0.01
        reward_amt = risk_amt * 2
        weekly_net = (wins * reward_amt) - (losses * risk_amt)
        final_balance = balance + weekly_net
        st.success(f"Projected Weekly Balance: ${final_balance:,.2f}")
        st.info(f"Monthly Projection: ${balance + (weekly_net * 4):,.2f}")
        st.info(f"Yearly Projection: ${balance + (weekly_net * 52):,.2f}")

elif menu_selection == "Settings":
    st.markdown('<h2 class="digital-font">Settings</h2>', unsafe_allow_html=True)
    st.markdown("### Pricing Structure (AeroVulpis Pro)")
    st.markdown("""
    | Plan | Price (IDR) | Limit |
    |------|-------------|-------|
    | 1 Hari (Trial) | Rp 999 | 5 Deep Analysis |
    | 1 Minggu | Rp 19.000 | 30 Deep Analysis |
    | 1 Bulan | Rp 35.000 | Unlimited* |
    | 6 Bulan | Rp 99.000 | Unlimited* |
    | 1 Tahun | Rp 175.000 | Unlimited* |
    """)
    st.caption("*Unlimited subject to fair usage policy (FUP) to save API costs.")
