from supabase import create_client, Client
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
            "updated_at": datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
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
    """Menghapus data market_prices yang lebih lama dari 24 jam"""
    try:
        supabase: Client = create_client(url, key)
        cutoff = (datetime.now(pytz.timezone('Asia/Jakarta')) - timedelta(hours=24)).isoformat()
        supabase.table("market_prices").delete().lt("updated_at", cutoff).execute()
    except Exception:
        pass

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.4 Ultimate", page_icon="🦅", initial_sidebar_state="expanded")

# Eksekusi Awal Logging & Cleanup
cleanup_logs()
cleanup_old_data()
send_log("AeroVulpis Online")

# Inisialisasi Session State untuk Bahasa
if "lang" not in st.session_state:
    st.session_state.lang = "ID"

# Inisialisasi Session State untuk Caching AI Analysis
if "cached_analysis" not in st.session_state:
    st.session_state.cached_analysis = {}

# Inisialisasi Session State untuk User Tier (Default: free)
if "user_tier" not in st.session_state:
    st.session_state.user_tier = "free"
if "daily_analysis_count" not in st.session_state:
    st.session_state.daily_analysis_count = 0
if "daily_chatbot_count" not in st.session_state:
    st.session_state.daily_chatbot_count = 0
if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = datetime.now().date()

# Reset daily limits
if st.session_state.last_reset_date < datetime.now().date():
    st.session_state.daily_analysis_count = 0
    st.session_state.daily_chatbot_count = 0
    st.session_state.last_reset_date = datetime.now().date()

# Limit konfigurasi berdasarkan tier
LIMITS = {
    "free": {"analysis_per_day": 5, "chatbot_per_day": 20},
    "trial": {"analysis_per_day": 10, "chatbot_per_day": 50},
    "weekly": {"analysis_per_day": 20, "chatbot_per_day": 100},
    "monthly": {"analysis_per_day": 50, "chatbot_per_day": 200},
    "six_months": {"analysis_per_day": 100, "chatbot_per_day": 500},
    "yearly": {"analysis_per_day": 999999, "chatbot_per_day": 999999}
}

# Fungsi untuk cek cache AI Analysis di Supabase
def get_cached_ai_analysis(asset_name, timeframe):
    """Mengambil cache analisis AI dari Supabase"""
    try:
        supabase: Client = create_client(url, key)
        # Cache berlaku 5 menit
        cutoff = (datetime.now(pytz.UTC) - timedelta(minutes=5)).isoformat()
        res = supabase.table("ai_analysis_cache").select("*")\
            .eq("asset_name", asset_name)\
            .eq("timeframe", timeframe)\
            .gte("created_at", cutoff)\
            .execute()
        if res.data:
            return res.data[0]["analysis"]
    except Exception:
        pass
    return None

def cache_ai_analysis(asset_name, timeframe, analysis):
    """Menyimpan cache analisis AI ke Supabase"""
    try:
        supabase: Client = create_client(url, key)
        data = {
            "asset_name": asset_name,
            "timeframe": timeframe,
            "analysis": analysis,
            "created_at": datetime.now(pytz.UTC).isoformat()
        }
        supabase.table("ai_analysis_cache").insert(data).execute()
    except Exception:
        pass

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
        "created_by": "Dibuat oleh Fahmi.",
        "limit_reached": "⚠️ Limit harian tercapai! Upgrade ke Premium untuk akses unlimited.",
        "daily_limit": "Limit Harian",
        "upgrade_premium": "UPGRADE PREMIUM"
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
        "created_by": "Created by Fahmi.",
        "limit_reached": "⚠️ Daily limit reached! Upgrade to Premium for unlimited access.",
        "daily_limit": "Daily Limit",
        "upgrade_premium": "UPGRADE PREMIUM"
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

    /* Animasi Loading 3D untuk Deep Analysis */
    .loading-3d-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 40px;
        position: relative;
    }
    
    .loading-3d-logo {
        width: 80px;
        height: 80px;
        position: relative;
        animation: rotate3D 2s infinite linear;
        transform-style: preserve-3d;
    }
    
    .loading-3d-ring {
        position: absolute;
        width: 100%;
        height: 100%;
        border: 3px solid transparent;
        border-radius: 50%;
        animation: ringPulse 1.5s infinite ease-in-out;
    }
    
    .loading-3d-ring:nth-child(1) {
        border-top-color: #00d4ff;
        animation-delay: 0s;
        transform: rotateX(60deg);
    }
    
    .loading-3d-ring:nth-child(2) {
        border-right-color: #00ff88;
        animation-delay: 0.3s;
        transform: rotateY(60deg);
    }
    
    .loading-3d-ring:nth-child(3) {
        border-bottom-color: #ff2a6d;
        animation-delay: 0.6s;
        transform: rotateZ(60deg);
    }
    
    .loading-3d-core {
        position: absolute;
        width: 20px;
        height: 20px;
        background: radial-gradient(circle, #00d4ff, #0055ff);
        border-radius: 50%;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        box-shadow: 0 0 30px rgba(0, 212, 255, 0.8);
        animation: coreGlow 1s infinite alternate;
    }
    
    @keyframes rotate3D {
        0% { transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg); }
        100% { transform: rotateX(360deg) rotateY(360deg) rotateZ(360deg); }
    }
    
    @keyframes ringPulse {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 1; }
    }
    
    @keyframes coreGlow {
        0% { box-shadow: 0 0 20px rgba(0, 212, 255, 0.5); }
        100% { box-shadow: 0 0 50px rgba(0, 212, 255, 1), 0 0 100px rgba(0, 85, 255, 0.5); }
    }
    
    .loading-text {
        font-family: 'Orbitron', sans-serif;
        color: #00d4ff;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.5);
        margin-top: 20px;
        font-size: 14px;
        animation: textGlow 1.5s infinite alternate;
    }
    
    @keyframes textGlow {
        0% { text-shadow: 0 0 5px rgba(0, 212, 255, 0.3); }
        100% { text-shadow: 0 0 20px rgba(0, 212, 255, 0.8), 0 0 40px rgba(0, 85, 255, 0.5); }
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
        background: linear-gradient(180deg, rgba(10, 14, 23, 0.98) 0%, rgba(5, 8, 15, 0.99) 100%) !important;
        border-right: 2px solid rgba(0, 212, 255, 0.3) !important;
        box-shadow: 5px 0 25px rgba(0, 212, 255, 0.1) !important;
    }
    
    /* Sidebar Digital Fintech Styling */
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(0, 212, 255, 0.05) !important;
        border: 1px solid rgba(0, 212, 255, 0.3) !important;
        border-radius: 8px !important;
        color: #e0e0e0 !important;
    }
    
    [data-testid="stSidebar"] .stSelectbox label {
        color: #00d4ff !important;
        font-family: 'Orbitron', sans-serif !important;
        font-size: 11px !important;
        letter-spacing: 1px !important;
    }
    
    [data-testid="stSidebar"] hr {
        border-color: rgba(0, 212, 255, 0.2) !important;
    }
    
    /* Sidebar Navigation Menu - Digital Fintech Style */
    [data-testid="stSidebar"] .nav-link {
        background: rgba(0, 212, 255, 0.03) !important;
        border: 1px solid rgba(0, 212, 255, 0.15) !important;
        border-radius: 8px !important;
        margin: 3px 0 !important;
        transition: all 0.3s ease !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 600 !important;
        letter-spacing: 0.5px !important;
    }
    
    [data-testid="stSidebar"] .nav-link:hover {
        background: rgba(0, 212, 255, 0.1) !important;
        border-color: rgba(0, 212, 255, 0.5) !important;
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.2) !important;
    }
    
    [data-testid="stSidebar"] .nav-link.selected {
        background: linear-gradient(145deg, rgba(0, 212, 255, 0.2), rgba(0, 85, 255, 0.2)) !important;
        border-color: #00d4ff !important;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.3), inset 0 0 10px rgba(0, 212, 255, 0.1) !important;
        color: #00d4ff !important;
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
    
    /* Risk Management Fintech Styling */
    .fintech-result-card {
        background: linear-gradient(145deg, rgba(0, 212, 255, 0.08), rgba(0, 85, 255, 0.05));
        border: 1px solid rgba(0, 212, 255, 0.3);
        border-radius: 12px;
        padding: 20px;
        margin: 10px 0;
        position: relative;
        overflow: hidden;
    }
    
    .fintech-result-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 2px;
        background: linear-gradient(90deg, transparent, #00d4ff, transparent);
        animation: scanLine 2s infinite;
    }
    
    @keyframes scanLine {
        0% { transform: translateX(-100%); }
        100% { transform: translateX(100%); }
    }
    
    .balance-display {
        font-family: 'Orbitron', sans-serif;
        font-size: 28px;
        color: #00ff88;
        text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
        text-align: center;
        padding: 10px;
    }
    
    .risk-metric {
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        color: #00d4ff;
        text-align: center;
    }
    
    .limit-indicator {
        background: rgba(255, 42, 109, 0.1);
        border: 1px solid rgba(255, 42, 109, 0.3);
        border-radius: 8px;
        padding: 8px 15px;
        display: inline-block;
        margin: 5px;
    }
</style>
""", unsafe_allow_html=True)

# Konfigurasi API Keys
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
marketaux_key = st.secrets.get("MARKETAUX_KEY") or os.getenv("MARKETAUX_KEY")
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
    """
    Sistem Centralized Caching:
    Mengambil data dari Supabase (Cache) jika masih segar (< 3 detik).
    Jika sudah basi, ambil dari yfinance dan update cache.
    """
    try:
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
            from supabase import create_client
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

        # Jika Cache Basi/Kosong, Ambil Live (yfinance)
        fetch_ticker = ticker_symbol
        if ticker_symbol == "GC=F": fetch_ticker = "GC=F"
        
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
    
    if latest["MACD"] > latest["Signal_Line"]: bullish_count += 1; reasons.append("MACD Bullish")
    else: bearish_count += 1; reasons.append("MACD Bearish")
    
    if latest["Close"] > latest["SMA50"]: bullish_count += 1; reasons.append("SMA 50 Bullish")
    else: bearish_count += 1; reasons.append("SMA 50 Bearish")

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
    
    # Cek limit harian
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_chatbot_count >= user_limits["chatbot_per_day"]:
        return f"⚠️ {t['limit_reached']} ({st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']})"
    
    MODEL_NAME = 'llama-3.3-70b-versatile'
    system_prompt = f"""
    Anda adalah AeroVulpis, asisten AI Trading Profesional.
    Waktu: {datetime.now().strftime('%d %B %Y, %H:%M:%S WIB')}
    Bahasa: {st.session_state.lang}

    TUGAS UTAMA:
    1. Membantu user menganalisis data trading dan berita yang ditampilkan di website.
    2. Berikan level ENTRY, STOP LOSS, dan TAKE PROFIT yang spesifik berdasarkan data.
    3. Jawablah dengan singkat, padat, dan teknis.
    4. JANGAN menyarankan perubahan pada kode website kecuali diminta.
    5. Konteks: {context}
    6. Anda memiliki akses ke Smart Alerts yang dipasang oleh user.
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            model=MODEL_NAME, temperature=0.7, max_tokens=1024,
        )
        st.session_state.daily_chatbot_count += 1
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ====================== FUNGSI SENTINEL ANALYSIS ======================
def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    """Fungsi khusus untuk AeroVulpis Sentinel menggunakan Hermes 3 405B dengan Backup Qwen 2.5"""
    openrouter_api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    
    if not openrouter_api_key:
        return "⚠️ OpenRouter API Key tidak ditemukan."
    
    # Cek cache dulu
    cached = get_cached_ai_analysis(asset_name, "sentinel")
    if cached:
        return cached + "\n\n*[Data dari cache, diperbarui < 5 menit yang lalu]*"
    
    # Cek limit harian
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"⚠️ {t['limit_reached']} ({st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']})"
    
    PRIMARY_MODEL = 'nousresearch/hermes-3-llama-3.1-405b'
    COMPANION_MODEL = 'qwen/qwen-2-72b-instruct'
    
    BACKUP_MODELS = [
        'deepseek/deepseek-chat',
        'minimax/minimax-01',
        'google/gemini-flash-1.5'
    ]
    
    latest = df.iloc[-1]
    price = market_data['price']
    
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
    [Ringkas faktor utama yang mempengaruhi instrumen ini saat ini]

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
    [Kesimpulan netral + risiko utama]

    ATURAN TAMBAHAN:
    - Jawab dalam bahasa Indonesia yang jelas dan ringkas.
    - Total maksimal 320 kata.
    - Selalu seimbang antara bullish dan bearish.
    """
    
    def call_openrouter(model_name, system_msg):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {openrouter_api_key}",
                    "Content-Type": "application/json",
                },
                data=json.dumps({
                    "model": model_name,
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
        return "⚠️ Sentinel Error: Semua model AI sedang sibuk atau limit habis."
    
    # Update counter dan cache
    st.session_state.daily_analysis_count += 1
    cache_ai_analysis(asset_name, "sentinel", analysis)
            
    return analysis

# ====================== FUNGSI DEEP ANALYSIS ======================
def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    """Fungsi khusus untuk Generate Deep Analysis menggunakan Llama-3.1-70b"""
    if not client: return "⚠️ Deep Analysis Inactive"
    
    # Cek cache dulu
    cached = get_cached_ai_analysis(asset_name, "deep")
    if cached:
        return cached + "\n\n*[Data dari cache, diperbarui < 5 menit yang lalu]*"
    
    # Cek limit harian
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"⚠️ {t['limit_reached']} ({st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']})"
    
    MODEL_NAME = 'llama-3.3-70b-versatile'
    
    latest = df.iloc[-1]
    price = market_data['price']
    
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
    Anda adalah AeroVulpis Deep Analysis Engine - AI Trading Analyst Profesional.
    Waktu: {datetime.now().strftime('%d %B %Y, %H:%M:%S WIB')}
    Bahasa: {st.session_state.lang}
    
    INSTRUKSI ANALISIS WAJIB:
    1. ANALISIS TEKNIKAL: Interpretasi mendalam RSI (14) dan SMA 200.
    2. LEVEL ENTRY: 2-3 level entry dengan alasan spesifik.
    3. STOP LOSS: Berdasarkan ATR dan struktur pasar.
    4. TAKE PROFIT: 2-3 level TP dengan risk-reward minimal 1:2.
    5. RISK MANAGEMENT: Position sizing optimal.
    6. SCENARIO: Bearish dan bullish.
    
    FORMAT OUTPUT:
    - Gunakan markdown untuk struktur yang jelas
    - Gunakan emoji untuk visual
    - Jangan lebih dari 2000 karakter
    - Fokus pada actionable insights
    """
    
    user_prompt = f"""Berikan analisis teknikal mendalam dengan level entry, stop loss, dan take profit:
    
    {technical_data}
    
    Analisis WAJIB mencakup:
    1. Interpretasi RSI (14): {latest['RSI']:.2f}
    2. Posisi harga vs SMA 200: {latest['SMA200']:.4f}
    3. Level entry spesifik (2-3 pilihan)
    4. Stop loss berdasarkan ATR: {latest['ATR']:.4f}
    5. Take profit dengan ratio minimal 1:2
    6. Risk management
    7. Skenario bullish dan bearish
    """
    
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=MODEL_NAME,
            temperature=0.6,
            max_tokens=2000,
        )
        analysis = chat_completion.choices[0].message.content
        
        # Update counter dan cache
        st.session_state.daily_analysis_count += 1
        cache_ai_analysis(asset_name, "deep", analysis)
        
        return analysis
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
    
    # User Tier Badge dengan gaya digital fintech
    tier_colors = {
        "free": "#888",
        "trial": "#00d4ff",
        "weekly": "#00ff88",
        "monthly": "#ffcc00",
        "six_months": "#ff8800",
        "yearly": "#ff2a6d"
    }
    tier_names = {
        "free": "FREE",
        "trial": "TRIAL",
        "weekly": "WEEKLY",
        "monthly": "MONTHLY",
        "six_months": "6 MONTHS PRO",
        "yearly": "YEARLY ULTIMATE"
    }
    tier_color = tier_colors.get(st.session_state.user_tier, "#888")
    tier_name = tier_names.get(st.session_state.user_tier, "FREE")
    
    st.markdown(f"""
    <div style="
        background: rgba(0, 0, 0, 0.4);
        border: 1px solid {tier_color};
        border-radius: 8px;
        padding: 8px 12px;
        margin: 10px 0;
        text-align: center;
        box-shadow: 0 0 10px rgba({','.join(str(int(tier_color[i:i+2], 16)) for i in (1,3,5))}, 0.2);
    ">
        <span style="font-family: 'Orbitron', sans-serif; font-size: 10px; color: {tier_color}; letter-spacing: 1px;">
            {tier_name}
        </span>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("**AeroVulpis V3.4** — **DYNAMIHATCH**")
    st.caption("2026 • Powered by Real-Time AI")

    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    ticker_display = f"{asset_name} ({ticker_input})"

    st.markdown("---")
    tf_options = {
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
            "container": {"padding": "5!important", "background-color": "transparent"},
            "icon": {"color": "#00d4ff", "font-size": "14px"},
            "nav-link": {
                "font-size": "12px", 
                "text-align": "left", 
                "margin": "2px 0",
                "padding": "10px 12px",
                "border-radius": "8px",
                "font-family": "'Rajdhani', sans-serif",
                "font-weight": "600",
                "letter-spacing": "0.5px",
                "background": "rgba(0, 212, 255, 0.03)",
                "border": "1px solid rgba(0, 212, 255, 0.1)",
                "transition": "all 0.3s ease"
            },
            "nav-link-selected": {
                "background": "linear-gradient(145deg, rgba(0, 212, 255, 0.2), rgba(0, 85, 255, 0.15))",
                "border": "1px solid #00d4ff",
                "color": "#00d4ff",
                "box-shadow": "0 0 15px rgba(0, 212, 255, 0.2), inset 0 0 10px rgba(0, 212, 255, 0.05)",
                "font-weight": "700"
            },
        }
    )
    
    # Limit indicator di sidebar
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    st.markdown("---")
    st.markdown(f"""
    <div style="
        background: rgba(0, 0, 0, 0.3);
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 8px;
        padding: 10px;
        margin-top: 10px;
    ">
        <p style="font-family: 'Orbitron', sans-serif; font-size: 9px; color: #888; margin: 0 0 5px 0; letter-spacing: 1px;">{t['daily_limit']}</p>
        <p style="font-family: 'Rajdhani', sans-serif; font-size: 11px; color: #00d4ff; margin: 2px 0;">
            🤖 AI Analysis: {st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']}
        </p>
        <p style="font-family: 'Rajdhani', sans-serif; font-size: 11px; color: #00d4ff; margin: 2px 0;">
            💬 Chatbot: {st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']}
        </p>
    </div>
    """, unsafe_allow_html=True)

# ====================== FUNGSI MARKET NEWS ======================
def get_news_data(category="General", max_articles=10):
    """Mengambil berita dengan filter kategori dan update setiap 1 jam."""
    from news_cache_manager import should_update_news, get_cached_news, update_news_cache
    
    if not should_update_news(category):
        return get_cached_news(category), None

    berita_final = []
    urls_terpakai = set()
    
    category_map = {
        "Stock": "stocks,equities,earnings",
        "Konflik": "geopolitics,war,conflict,sanctions",
        "Gold & Silver": "gold,silver,precious metals,commodities",
        "Forex": "forex,currency,central banks,interest rates",
        "General": "finance,economy,market"
    }
    api_query = category_map.get(category, "finance")

    if marketaux_key:
        try:
            url_m = f"https://api.marketaux.com/v1/news/all?api_token={marketaux_key}&language=en&search={api_query}&limit=15"
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
        except: pass

    tiingo_key = st.secrets.get("TIINGO_KEY") or os.getenv("TIINGO_KEY")
    if tiingo_key:
        try:
            url_t = f"https://api.tiingo.com/tiingo/news?token={tiingo_key}&limit=15"
            if category == "Stock": url_t += "&tags=stocks"
            elif category == "Forex": url_t += "&tags=forex"
            
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
        except: pass

    if not berita_final:
        return get_cached_news(category), "Gagal mengambil berita baru, menampilkan cache."

    try:
        berita_final = sorted(berita_final, key=lambda x: x['publishedAt'], reverse=True)
    except: pass
    
    berita_final = berita_final[:max_articles]
    
    tz_wib = pytz.timezone('Asia/Jakarta')
    for b in berita_final:
        try:
            raw_date = b['publishedAt'].replace('Z', '+00:00') if b['publishedAt'] else ''
            if raw_date:
                try: dt_utc = datetime.fromisoformat(raw_date)
                except:
                    dt_utc = datetime.strptime(raw_date[:19], "%Y-%m-%dT%H:%M:%S")
                    dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
                dt_wib = dt_utc.astimezone(tz_wib)
                b['publishedAt'] = dt_wib.strftime("%d-%m-%Y %H.%M")
            else: b['publishedAt'] = 'N/A'
        except: b['publishedAt'] = 'N/A'
            
    update_news_cache(category, berita_final)
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

    unique_instruments = list(set([a["instrument"] for a in st.session_state.active_alerts if not a.get("triggered")]))
    if not unique_instruments:
        return

    instrument_to_ticker = {
        "XAUUSD": "GC=F",
        "BTCUSD": "BTC-USD",
        "XAGUSD": "SI=F",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X"
    }
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
                if m_data:
                    price = m_data["price"]
        
        if price is not None:
            current_prices[inst] = price

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
                now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")

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
        
        # Loading animation placeholder
        loading_placeholder = st.empty()
        
        if st.button("GENERATE DEEP ANALYSIS PRO", key="sentinel_pro_btn", use_container_width=True):
            market = get_market_data(ticker_input)
            df = get_historical_data(ticker_input, period, interval)
            if market and not df.empty:
                df = add_technical_indicators(df)
                score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
                
                # Tampilkan animasi loading 3D
                loading_placeholder.markdown("""
                <div class="loading-3d-container">
                    <div class="loading-3d-logo">
                        <div class="loading-3d-ring"></div>
                        <div class="loading-3d-ring"></div>
                        <div class="loading-3d-ring"></div>
                        <div class="loading-3d-core"></div>
                    </div>
                    <p class="loading-text">AEROVULPIS SENTINEL PROCESSING...</p>
                    <p style="font-family: 'Rajdhani', sans-serif; color: #888; font-size: 11px; margin-top: 10px;">
                        Analyzing market microstructure & order flow...
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                # Simulasi proses AI dengan progress
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.03)
                    progress_bar.progress(i + 1)
                
                analysis = get_sentinel_analysis(asset_name, market, df, signal, reasons)
                st.session_state.sentinel_analysis = analysis
                
                # Hapus animasi loading
                loading_placeholder.empty()
                progress_bar.empty()
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
            
            # Loading animation untuk Deep Analysis
            deep_loading = st.empty()
            
            if st.button(t['generate_ai'], use_container_width=True):
                # Tampilkan animasi loading 3D
                deep_loading.markdown("""
                <div class="loading-3d-container">
                    <div class="loading-3d-logo">
                        <div class="loading-3d-ring"></div>
                        <div class="loading-3d-ring"></div>
                        <div class="loading-3d-ring"></div>
                        <div class="loading-3d-core"></div>
                    </div>
                    <p class="loading-text">AEROVULPIS DEEP ANALYSIS IN PROGRESS...</p>
                    <p style="font-family: 'Rajdhani', sans-serif; color: #888; font-size: 11px; margin-top: 10px;">
                        Scanning indicators & generating insights...
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.02)
                    progress_bar.progress(i + 1)
                
                ai_anal = get_deep_analysis(asset_name, market, df, signal, reasons)
                
                deep_loading.empty()
                progress_bar.empty()
                
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
    st.markdown('<p style="font-size:12px; color:#888; margin-bottom:15px;">Berita real-time dari media-media resmi dan terpercaya | Diperbarui secara cerdas setiap 1 jam</p>', unsafe_allow_html=True)
    
    news_categories = ["General", "Stock", "Konflik", "Gold & Silver", "Forex"]
    selected_news_cat = st.segmented_control("FILTER BERITA", news_categories, default="General")
    
    articles, error = get_news_data(selected_news_cat, 10)
    
    if error and not articles: 
        st.error(error)
    elif articles:
        for a in articles:
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
        st.info(f"Tidak ada berita tersedia untuk kategori {selected_news_cat} saat ini.")


elif menu_selection == "Economic Radar":
    economic_calendar_widget()
elif menu_selection == "Smart Alert Center":
    smart_alert_widget()

elif menu_selection == "Chatbot AI":
    st.markdown(f'<h2 class="digital-font" style="font-size:24px;">🤖 AeroVulpis AI Assistant</h2>', unsafe_allow_html=True)
    if "messages" not in st.session_state: st.session_state.messages = []
    for message in st.session_state.messages:
        with st.chat_message(message["role"]): st.markdown(message["content"])
    if prompt := st.chat_input("Tanya AeroVulpis v3.4 Ultimate..."):
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
    
    # Four Pillars Icons
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

    # Reward-to-Risk Simulator
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
    </style>
    """, unsafe_allow_html=True)

    selected_rr = st.radio("Select Ratio", list(rr_ratios.keys()), horizontal=True, key="rr_ratio_radio")
    
    # Win/Loss Inputs
    st.markdown('<p style="font-family:Rajdhani; font-size:14px; margin-top:10px; color:#ccc;">Simulated Weekly Trade Win/Loss</p>', unsafe_allow_html=True)
    w_col, l_col = st.columns(2)
    with w_col:
        wins = st.number_input("Wins:", min_value=0, value=3, step=1, key="sim_wins")
    with l_col:
        losses = st.number_input("Losses:", min_value=0, value=2, step=1, key="sim_losses")

    # Risk per trade
    risk_per_trade_pct = 1.0
    
    # Max daily loss & profit inputs
    st.markdown('<p style="font-family:Orbitron; font-size:14px; margin-top:15px; color:#888;">DAILY RISK PARAMETERS</p>', unsafe_allow_html=True)
    d_col1, d_col2 = st.columns(2)
    with d_col1:
        max_daily_loss_pct = st.number_input("Max Daily Loss %", min_value=1.0, max_value=100.0, value=5.0, step=1.0, key="max_daily_loss")
    with d_col2:
        max_daily_profit_pct = st.number_input("Max Daily Profit Target %", min_value=1.0, max_value=200.0, value=10.0, step=1.0, key="max_daily_profit")

    if st.button("SIMULATE & CALCULATE RETURNS", use_container_width=True, type="primary"):
        # Kalkulasi
        risk_amt = balance * (risk_per_trade_pct / 100)
        reward_amt = risk_amt * rr_ratios[selected_rr]
        
        weekly_net = (wins * reward_amt) - (losses * risk_amt)
        weekly_return_pct = (weekly_net / balance) * 100
        
        monthly_return_pct = weekly_return_pct * 4
        yearly_return_pct = weekly_return_pct * 52
        
        # Total saldo akhir
        final_balance_weekly = balance + weekly_net
        final_balance_monthly = balance + (weekly_net * 4)
        final_balance_yearly = balance + (weekly_net * 52)
        
        # Max daily loss & profit amount
        max_daily_loss_amt = balance * (max_daily_loss_pct / 100)
        max_daily_profit_amt = balance * (max_daily_profit_pct / 100)
        
        # Projected Performance dengan gaya Fintech Digital
        st.markdown('<p style="font-family:Orbitron; font-size:16px; margin-top:25px; color:#00d4ff; text-align:center; letter-spacing:2px;">📊 PROJECTED PERFORMANCE</p>', unsafe_allow_html=True)
        
        # Weekly Results
        st.markdown(f"""
        <div class="fintech-result-card">
            <p style="font-family:Orbitron; font-size:12px; color:#00d4ff; margin:0 0 10px 0;">📅 WEEKLY PROJECTION</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">NET P/L</p>
                    <p class="risk-metric" style="color:{'#00ff88' if weekly_net >= 0 else '#ff2a6d'}; font-size:16px;">
                        {weekly_net:+,.2f} USD
                    </p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">RETURN</p>
                    <p class="risk-metric" style="color:{'#00ff88' if weekly_return_pct >= 0 else '#ff2a6d'}; font-size:16px;">
                        {weekly_return_pct:+.2f}%
                    </p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">FINAL BALANCE</p>
                    <p class="risk-metric" style="color:#00d4ff; font-size:16px;">
                        {final_balance_weekly:,.2f} USD
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Monthly Results
        st.markdown(f"""
        <div class="fintech-result-card">
            <p style="font-family:Orbitron; font-size:12px; color:#00d4ff; margin:0 0 10px 0;">📅 MONTHLY PROJECTION</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">NET P/L</p>
                    <p class="risk-metric" style="color:{'#00ff88' if (weekly_net*4) >= 0 else '#ff2a6d'}; font-size:16px;">
                        {(weekly_net*4):+,.2f} USD
                    </p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">RETURN</p>
                    <p class="risk-metric" style="color:{'#00ff88' if monthly_return_pct >= 0 else '#ff2a6d'}; font-size:16px;">
                        {monthly_return_pct:+.2f}%
                    </p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">FINAL BALANCE</p>
                    <p class="risk-metric" style="color:#00d4ff; font-size:16px;">
                        {final_balance_monthly:,.2f} USD
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Yearly Results
        st.markdown(f"""
        <div class="fintech-result-card">
            <p style="font-family:Orbitron; font-size:12px; color:#00d4ff; margin:0 0 10px 0;">📅 YEARLY PROJECTION</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px;">
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">NET P/L</p>
                    <p class="risk-metric" style="color:{'#00ff88' if (weekly_net*52) >= 0 else '#ff2a6d'}; font-size:16px;">
                        {(weekly_net*52):+,.2f} USD
                    </p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">RETURN</p>
                    <p class="risk-metric" style="color:{'#00ff88' if yearly_return_pct >= 0 else '#ff2a6d'}; font-size:16px;">
                        {yearly_return_pct:+.2f}%
                    </p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">FINAL BALANCE</p>
                    <p class="risk-metric" style="color:#00d4ff; font-size:16px;">
                        {final_balance_yearly:,.2f} USD
                    </p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Risk Parameters Results
        st.markdown('<p style="font-family:Orbitron; font-size:16px; margin-top:25px; color:#ff2a6d; text-align:center; letter-spacing:2px;">⚠️ RISK PARAMETERS</p>', unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="fintech-result-card" style="border-color: rgba(255, 42, 109, 0.3);">
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px;">
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">RISK/TRADE</p>
                    <p class="risk-metric" style="color:#ff2a6d; font-size:14px;">{risk_amt:,.2f} USD</p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">REWARD/TRADE</p>
                    <p class="risk-metric" style="color:#00ff88; font-size:14px;">{reward_amt:,.2f} USD</p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">MAX DAILY LOSS</p>
                    <p class="risk-metric" style="color:#ff2a6d; font-size:14px;">-{max_daily_loss_amt:,.2f} USD</p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:10px; color:#888; margin:0;">MAX DAILY PROFIT</p>
                    <p class="risk-metric" style="color:#00ff88; font-size:14px;">+{max_daily_profit_amt:,.2f} USD</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Total Balance Summary
        st.markdown(f"""
        <div class="fintech-result-card" style="border: 2px solid #00d4ff; background: linear-gradient(145deg, rgba(0, 212, 255, 0.12), rgba(0, 85, 255, 0.08));">
            <p style="font-family:Orbitron; font-size:12px; color:#00d4ff; margin:0 0 8px 0; text-align:center;">💰 TOTAL BALANCE SUMMARY</p>
            <div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px;">
                <div style="text-align:center;">
                    <p style="font-size:9px; color:#888; margin:0;">INITIAL</p>
                    <p class="risk-metric" style="font-size:13px;">{balance:,.2f} USD</p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:9px; color:#888; margin:0;">AFTER 1W</p>
                    <p class="risk-metric" style="font-size:13px; color:{'#00ff88' if final_balance_weekly >= balance else '#ff2a6d'};">{final_balance_weekly:,.2f} USD</p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:9px; color:#888; margin:0;">AFTER 1M</p>
                    <p class="risk-metric" style="font-size:13px; color:{'#00ff88' if final_balance_monthly >= balance else '#ff2a6d'};">{final_balance_monthly:,.2f} USD</p>
                </div>
                <div style="text-align:center;">
                    <p style="font-size:9px; color:#888; margin:0;">AFTER 1Y</p>
                    <p class="risk-metric" style="font-size:13px; color:{'#00ff88' if final_balance_yearly >= balance else '#ff2a6d'};">{final_balance_yearly:,.2f} USD</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
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
        st.session_state.cached_analysis = {}
        st.success("Cache Cleared!")
    st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "Help & Support":
    st.markdown('<h2 class="digital-font" style="text-align:center; font-size:28px; margin-bottom:20px;">AeroVulpis v3.4 Help & Support</h2>', unsafe_allow_html=True)
    
    # Pricing Section
    st.markdown("""
    <div class="glass-card" style="border: 2px solid #00d4ff; margin-bottom: 25px;">
        <h3 style="text-align:center; font-family:Orbitron; color:#00d4ff; font-size:20px;">💎 PREMIUM PACKAGES</h3>
        <p style="text-align:center; color:#888; font-family:Rajdhani; font-size:13px;">Unlock Full AI Power & Unlimited Analysis</p>
    """, unsafe_allow_html=True)
    
    packages = [
        {"name": "1 DAY TRIAL", "price": "Rp999", "color": "#00d4ff", "desc": "Trust building • Full access trial", "analysis": "10/day", "chatbot": "50/day"},
        {"name": "1 WEEK", "price": "Rp15.000", "color": "#00ff88", "desc": "Weekly access • Great for testing", "analysis": "20/day", "chatbot": "100/day"},
        {"name": "1 MONTH", "price": "Rp29.000", "color": "#ffcc00", "desc": "Best value for active traders", "analysis": "50/day", "chatbot": "200/day"},
        {"name": "6 MONTHS", "price": "Rp99.000", "color": "#ff8800", "desc": "Pro trader package • Save 43%", "analysis": "100/day", "chatbot": "500/day"},
        {"name": "1 YEAR", "price": "Rp149.000", "color": "#ff2a6d", "desc": "Ultimate lifetime feel • Save 57%", "analysis": "Unlimited", "chatbot": "Unlimited"}
    ]
    
    cols = st.columns(5)
    for i, pkg in enumerate(packages):
        with cols[i]:
            st.markdown(f"""
            <div style="
                background: rgba(0, 0, 0, 0.4);
                border: 1px solid {pkg['color']};
                border-radius: 10px;
                padding: 15px 10px;
                text-align: center;
                height: 100%;
                box-shadow: 0 0 10px rgba({','.join(str(int(pkg['color'][j:j+2], 16)) for j in (1,3,5))}, 0.2);
            ">
                <p style="font-family:Orbitron; font-size:10px; color:{pkg['color']}; margin:0 0 5px 0; letter-spacing:1px;">{pkg['name']}</p>
                <p style="font-family:Orbitron; font-size:18px; color:white; margin:5px 0;">{pkg['price']}</p>
                <p style="font-family:Rajdhani; font-size:9px; color:#888; margin:5px 0;">{pkg['desc']}</p>
                <hr style="border-color:rgba(255,255,255,0.1); margin:8px 0;">
                <p style="font-family:Rajdhani; font-size:8px; color:#aaa;">🤖 AI: {pkg['analysis']}</p>
                <p style="font-family:Rajdhani; font-size:8px; color:#aaa;">💬 Chat: {pkg['chatbot']}</p>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("<p style='text-align:center; color:#888; font-size:10px; margin-top:10px;'>*Registration, payment & key system coming soon</p>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    
    # Existing Help sections
    with st.expander("1. AEROVULPIS SENTINEL (PRO)", expanded=True):
        st.markdown("""
        **Sentinel** adalah dashboard utama tingkat lanjut yang dirancang untuk analisis institusional.
        **TradingView Chart**: Grafik real-time interaktif dengan alat gambar lengkap.
        **Generate Deep Analysis Pro**: Menggunakan sistem AeroVulpis AI Pro untuk laporan mendalam.
        """, unsafe_allow_html=True)

    with st.expander("2. LIVE DASHBOARD"):
        st.markdown("""
        Pusat pemantauan harga dan sinyal teknikal cepat.
        **Live Price**: Harga terkini dari yFinance atau Twelve Data.
        **Generate Deep Analysis**: Analisis AI cepat menggunakan AeroVulpis Intelligence Engine.
        """, unsafe_allow_html=True)

    with st.expander("3. SIGNAL ANALYSIS"):
        st.markdown("""
        Grid indikator teknikal lengkap untuk konfirmasi manual.
        20+ Indikator termasuk RSI, MACD, Bollinger Bands, Ichimoku, dan Parabolic SAR.
        """, unsafe_allow_html=True)

    with st.expander("4. SMART ALERT CENTER"):
        st.markdown("""
        Sistem sensor harga otomatis yang terhubung ke Telegram.
        **Lock Target**: Masukkan harga target dan Chat ID Telegram.
        **Cara Mendapatkan User ID**: Buka Telegram dan cari bot **@userinfobot**.
        """, unsafe_allow_html=True)

    with st.expander("5. RISK MANAGEMENT"):
        st.markdown("""
        Framework untuk menjaga kelangsungan akun trading Anda.
        **Four Pillars**: Trading Rules, Position Sizing, Confidence Scores, dan Risk Strategy.
        **RR Simulator**: Hitung proyeksi keuntungan dengan Max Daily Loss & Profit parameters.
        """, unsafe_allow_html=True)

    st.info("**Tips**: Gunakan menu **Settings** untuk mengganti bahasa atau membersihkan cache.")

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
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v3.4 ULTIMATE • 2026</p>
</div>
""", unsafe_allow_html=True)
