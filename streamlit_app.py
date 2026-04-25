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

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# ====================== SUPABASE KONFIGURASI ======================
url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]
service_key = st.secrets.get("supabase_service_key", key)

supabase_public = create_client(url, key)
supabase_admin = create_client(url, service_key) if service_key != key else supabase_public

def send_log(pesan):
    try:
        supabase_admin.table("logs_aktivitas").insert({"keterangan": pesan}).execute()
    except Exception:
        pass

def cleanup_logs():
    try:
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        supabase_admin.table("logs_aktivitas").delete().lt("created_at", cutoff).execute()
    except Exception:
        pass

def cache_market_price(symbol, price, change_pct=0.0):
    try:
        data = {
            "instrument": symbol,
            "price": price,
            "change_pct": change_pct,
            "updated_at": datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
        }
        supabase_admin.table("market_prices").upsert(data, on_conflict="instrument").execute()
    except Exception:
        pass

def get_cached_market_price(symbol):
    try:
        res = supabase_public.table("market_prices").select("price").eq("instrument", symbol).execute()
        if res.data:
            return res.data[0]["price"]
    except Exception:
        pass
    return None

def cleanup_old_data():
    try:
        cutoff = (datetime.now(pytz.timezone('Asia/Jakarta')) - timedelta(hours=24)).isoformat()
        supabase_admin.table("market_prices").delete().lt("updated_at", cutoff).execute()
    except Exception:
        pass

# ====================== FUNGSI USER & TIER ======================
def get_user_tier(user_id):
    try:
        res = supabase_public.table("user_tiers")\
            .select("tier, expires_at")\
            .eq("user_id", user_id)\
            .single()\
            .execute()
        if res.data:
            tier = res.data.get("tier", "free")
            expires = res.data.get("expires_at")
            if expires:
                expires_date = datetime.fromisoformat(expires.replace('Z', '+00:00'))
                if expires_date < datetime.now(pytz.UTC):
                    return "free"
            return tier
    except Exception:
        pass
    return "free"

def activate_key(user_id, key_code):
    try:
        key_data = supabase_admin.table("activation_keys")\
            .select("*")\
            .eq("key_code", key_code)\
            .eq("is_used", False)\
            .single()\
            .execute()
        if not key_data.data:
            return False, "Kunci tidak valid atau sudah dipakai!"
        key = key_data.data
        tier = key["tier"]
        duration_days = key["duration_days"]
        now = datetime.now(pytz.UTC)
        expires = now + timedelta(days=duration_days)
        supabase_admin.table("user_tiers").upsert({
            "user_id": user_id,
            "tier": tier,
            "activated_at": now.isoformat(),
            "expires_at": expires.isoformat(),
            "key_code": key_code
        }).execute()
        supabase_admin.table("activation_keys")\
            .update({
                "is_used": True,
                "used_by": user_id,
                "used_at": now.isoformat()
            })\
            .eq("key_code", key_code)\
            .execute()
        st.session_state.user_tier = tier
        return True, tier
    except Exception as e:
        return False, str(e)

# ====================== KONFIGURASI HALAMAN ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.4 Ultimate", page_icon="🦅", initial_sidebar_state="expanded")

cleanup_logs()
cleanup_old_data()
send_log("AeroVulpis Online")

# Session State
if "lang" not in st.session_state:
    st.session_state.lang = "ID"
if "cached_analysis" not in st.session_state:
    st.session_state.cached_analysis = {}
if "user_tier" not in st.session_state:
    st.session_state.user_tier = "free"
if "daily_analysis_count" not in st.session_state:
    st.session_state.daily_analysis_count = 0
if "daily_chatbot_count" not in st.session_state:
    st.session_state.daily_chatbot_count = 0
if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = datetime.now().date()
if "show_activation" not in st.session_state:
    st.session_state.show_activation = False
if "activation_result" not in st.session_state:
    st.session_state.activation_result = None
if "sentinel_analysis" not in st.session_state:
    st.session_state.sentinel_analysis = None

if st.session_state.last_reset_date < datetime.now().date():
    st.session_state.daily_analysis_count = 0
    st.session_state.daily_chatbot_count = 0
    st.session_state.last_reset_date = datetime.now().date()

LIMITS = {
    "free": {"analysis_per_day": 5, "chatbot_per_day": 20},
    "trial": {"analysis_per_day": 10, "chatbot_per_day": 50},
    "weekly": {"analysis_per_day": 20, "chatbot_per_day": 100},
    "monthly": {"analysis_per_day": 50, "chatbot_per_day": 200},
    "six_months": {"analysis_per_day": 100, "chatbot_per_day": 500},
    "yearly": {"analysis_per_day": 999999, "chatbot_per_day": 999999}
}

def get_cached_ai_analysis(asset_name, timeframe):
    try:
        cutoff = (datetime.now(pytz.UTC) - timedelta(minutes=5)).isoformat()
        res = supabase_public.table("ai_analysis_cache").select("*")\
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
    try:
        data = {
            "asset_name": asset_name,
            "timeframe": timeframe,
            "analysis": analysis,
            "created_at": datetime.now(pytz.UTC).isoformat()
        }
        supabase_admin.table("ai_analysis_cache").insert(data).execute()
    except Exception:
        pass

# ====================== KAMUS BAHASA ======================
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
        "upgrade_premium": "UPGRADE PREMIUM",
        "login_google": "SIGN IN WITH GOOGLE",
        "logout": "LOGOUT",
        "activate_key": "AKTIVASI KUNCI",
        "enter_key": "Masukkan kunci aktivasi",
        "activate_btn": "AKTIVASI SEKARANG",
        "welcome": "WELCOME",
        "tier_free": "FREE",
        "processing": "Memproses...",
        "activation_success": "AKTIVASI BERHASIL!",
        "activation_failed": "AKTIVASI GAGAL!"
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
        "upgrade_premium": "UPGRADE PREMIUM",
        "login_google": "SIGN IN WITH GOOGLE",
        "logout": "LOGOUT",
        "activate_key": "ACTIVATE KEY",
        "enter_key": "Enter activation key",
        "activate_btn": "ACTIVATE NOW",
        "welcome": "WELCOME",
        "tier_free": "FREE",
        "processing": "Processing...",
        "activation_success": "ACTIVATION SUCCESS!",
        "activation_failed": "ACTIVATION FAILED!"
    }
}

t = translations[st.session_state.lang]

# ====================== CSS LENGKAP ======================
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
        top: 0; left: 0;
        width: 3px; height: 100%;
        background: linear-gradient(to bottom, var(--electric-blue), transparent);
    }

    .news-card:hover {
        background: rgba(0, 212, 255, 0.05);
        border-color: var(--electric-blue);
        box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
        transform: scale(1.01);
    }

    .main-title-container { text-align: center; margin-bottom: 0; padding-bottom: 0; }
    .main-logo-container {
        position: relative; display: inline-block; animation: float 4s infinite ease-in-out;
        padding: 10px 0; margin-bottom: -15px; background: transparent !important;
        perspective: 1200px; overflow: visible !important;
    }
    .custom-logo {
        width: 100px; filter: drop-shadow(0 0 15px var(--electric-blue));
        transition: all 0.5s ease; background-color: transparent !important;
        animation: smoothRotate3D 12s infinite cubic-bezier(0.45, 0.05, 0.55, 0.95);
        transform-style: preserve-3d;
    }
    @keyframes float {
        0%,100% { transform: translateY(0px); }
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
        font-family: 'Orbitron', sans-serif; font-size: 32px; font-weight: 700;
        background: linear-gradient(90deg, var(--electric-blue), var(--deep-blue));
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.5); margin: 0; padding: 0;
    }

    .digital-font {
        font-family: 'Orbitron', sans-serif; color: var(--neon-green);
        text-shadow: 0 0 10px var(--neon-green);
    }
    .cyan-neon { color: var(--electric-blue); text-shadow: 0 0 10px var(--electric-blue); }
    .rajdhani-font { font-family: 'Rajdhani', sans-serif; }

    /* ============ ANIMASI 3D SENTINEL PRO ============ */
    .loading-3d-pro-container {
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        padding: 50px; position: relative;
        background: radial-gradient(circle at center, rgba(0, 212, 255, 0.08) 0%, transparent 70%);
        border-radius: 20px; border: 1px solid rgba(0, 212, 255, 0.15);
    }
    .loading-3d-pro-scene { width: 130px; height: 130px; perspective: 500px; position: relative; }
    .loading-3d-pro-core {
        width: 100%; height: 100%; position: relative; transform-style: preserve-3d;
        animation: rotate3DPro 3s infinite cubic-bezier(0.68, -0.55, 0.27, 1.55);
    }
    .loading-3d-pro-ring {
        position: absolute; border-radius: 50%; border: 2px solid transparent;
        top: 50%; left: 50%; transform-style: preserve-3d;
    }
    .loading-3d-pro-ring:nth-child(1) {
        width: 100%; height: 100%; margin-top: -50%; margin-left: -50%;
        border-top-color: #00d4ff; border-left-color: rgba(0, 212, 255, 0.3);
        animation: ringGlowPro1 2s infinite ease-in-out; transform: rotateX(70deg) rotateY(0deg);
    }
    .loading-3d-pro-ring:nth-child(2) {
        width: 80%; height: 80%; margin-top: -40%; margin-left: -40%;
        border-right-color: #00ff88; border-bottom-color: rgba(0, 255, 136, 0.3);
        animation: ringGlowPro2 2s infinite ease-in-out 0.3s; transform: rotateX(0deg) rotateY(70deg);
    }
    .loading-3d-pro-ring:nth-child(3) {
        width: 60%; height: 60%; margin-top: -30%; margin-left: -30%;
        border-bottom-color: #ff2a6d; border-right-color: rgba(255, 42, 109, 0.3);
        animation: ringGlowPro3 2s infinite ease-in-out 0.6s; transform: rotateX(50deg) rotateY(50deg) rotateZ(30deg);
    }
    .loading-3d-pro-ring:nth-child(4) {
        width: 40%; height: 40%; margin-top: -20%; margin-left: -20%;
        border-left-color: #bc13fe; border-top-color: rgba(188, 19, 254, 0.3);
        animation: ringGlowPro4 2s infinite ease-in-out 0.9s; transform: rotateX(30deg) rotateY(30deg) rotateZ(60deg);
    }
    .loading-3d-pro-center {
        position: absolute; width: 18px; height: 18px;
        background: radial-gradient(circle, #00d4ff, #0055ff); border-radius: 50%;
        top: 50%; left: 50%; transform: translate(-50%, -50%);
        box-shadow: 0 0 40px rgba(0, 212, 255, 0.9), 0 0 80px rgba(0, 85, 255, 0.5), 0 0 120px rgba(0, 212, 255, 0.3);
        animation: centerPulsePro 1.5s infinite alternate;
    }
    .loading-3d-pro-particles { position: absolute; width: 100%; height: 100%; top: 0; left: 0; }
    .loading-3d-pro-particle {
        position: absolute; width: 3px; height: 3px; background: #00d4ff;
        border-radius: 50%; box-shadow: 0 0 6px #00d4ff; animation: particleFloat 2s infinite ease-in-out;
    }
    .loading-3d-pro-particle:nth-child(1) { top: 10%; left: 20%; animation-delay: 0s; }
    .loading-3d-pro-particle:nth-child(2) { top: 20%; left: 80%; animation-delay: 0.4s; }
    .loading-3d-pro-particle:nth-child(3) { top: 70%; left: 15%; animation-delay: 0.8s; }
    .loading-3d-pro-particle:nth-child(4) { top: 80%; left: 75%; animation-delay: 1.2s; }
    .loading-3d-pro-particle:nth-child(5) { top: 45%; left: 90%; animation-delay: 1.6s; }
    .loading-3d-pro-particle:nth-child(6) { top: 55%; left: 5%; animation-delay: 0.2s; }
    @keyframes rotate3DPro {
        0% { transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg); }
        25% { transform: rotateX(180deg) rotateY(90deg) rotateZ(45deg); }
        50% { transform: rotateX(360deg) rotateY(180deg) rotateZ(90deg); }
        75% { transform: rotateX(540deg) rotateY(270deg) rotateZ(135deg); }
        100% { transform: rotateX(720deg) rotateY(360deg) rotateZ(180deg); }
    }
    @keyframes ringGlowPro1 {
        0%,100% { border-top-color: rgba(0,212,255,0.3); box-shadow: 0 0 5px rgba(0,212,255,0.1); }
        50% { border-top-color: #00d4ff; box-shadow: 0 0 25px rgba(0,212,255,0.6); }
    }
    @keyframes ringGlowPro2 {
        0%,100% { border-right-color: rgba(0,255,136,0.3); box-shadow: 0 0 5px rgba(0,255,136,0.1); }
        50% { border-right-color: #00ff88; box-shadow: 0 0 25px rgba(0,255,136,0.6); }
    }
    @keyframes ringGlowPro3 {
        0%,100% { border-bottom-color: rgba(255,42,109,0.3); box-shadow: 0 0 5px rgba(255,42,109,0.1); }
        50% { border-bottom-color: #ff2a6d; box-shadow: 0 0 25px rgba(255,42,109,0.6); }
    }
    @keyframes ringGlowPro4 {
        0%,100% { border-left-color: rgba(188,19,254,0.3); box-shadow: 0 0 5px rgba(188,19,254,0.1); }
        50% { border-left-color: #bc13fe; box-shadow: 0 0 25px rgba(188,19,254,0.6); }
    }
    @keyframes centerPulsePro {
        0% { transform: translate(-50%, -50%) scale(0.8); box-shadow: 0 0 30px rgba(0,212,255,0.6); }
        100% { transform: translate(-50%, -50%) scale(1.3); box-shadow: 0 0 60px rgba(0,212,255,1), 0 0 120px rgba(0,85,255,0.7); }
    }
    @keyframes particleFloat {
        0%,100% { transform: translateY(0) scale(1); opacity: 0.3; }
        50% { transform: translateY(-15px) scale(1.8); opacity: 1; }
    }
    .loading-3d-pro-text {
        font-family: 'Orbitron', sans-serif; color: #00d4ff;
        text-shadow: 0 0 15px rgba(0,212,255,0.7), 0 0 30px rgba(0,85,255,0.4);
        margin-top: 25px; font-size: 15px; letter-spacing: 3px;
        animation: textGlowPro 2s infinite alternate;
    }
    .loading-3d-pro-sub {
        font-family: 'Rajdhani', sans-serif; color: #888; font-size: 12px;
        margin-top: 8px; letter-spacing: 1px; animation: textGlowPro 2s infinite alternate 0.5s;
    }
    @keyframes textGlowPro {
        0% { opacity: 0.5; } 100% { opacity: 1; }
    }

    /* ============ ECONOMIC RADAR CYBER TECH ============ */
    .radar-cyber-container {
        position: relative; display: flex; align-items: center; justify-content: center;
        gap: 15px; margin: 10px 0;
    }
    .radar-cyber-disc { width: 50px; height: 50px; position: relative; flex-shrink: 0; }
    .radar-cyber-disc::before {
        content: ''; position: absolute; width: 100%; height: 100%;
        border: 2px solid rgba(0,212,255,0.4); border-radius: 50%; top: 0; left: 0;
        animation: radarDiscPulse 2s infinite;
    }
    .radar-cyber-disc::after {
        content: ''; position: absolute; width: 60%; height: 60%;
        border: 1px solid rgba(0,255,136,0.3); border-radius: 50%; top: 20%; left: 20%;
        animation: radarDiscPulse 2s infinite 0.5s;
    }
    .radar-cyber-sweep {
        position: absolute; width: 50%; height: 2px;
        background: linear-gradient(to right, transparent, #00d4ff);
        top: 50%; left: 50%; transform-origin: left center;
        animation: radarSweep 2s linear infinite; box-shadow: 0 0 8px rgba(0,212,255,0.6);
    }
    .radar-cyber-dot {
        position: absolute; width: 4px; height: 4px; background: #00ff88;
        border-radius: 50%; box-shadow: 0 0 8px #00ff88; animation: radarDotBlink 1.5s infinite;
    }
    .radar-cyber-dot:nth-child(1) { top: 15%; left: 30%; animation-delay: 0s; }
    .radar-cyber-dot:nth-child(2) { top: 60%; left: 70%; animation-delay: 0.7s; }
    .radar-cyber-dot:nth-child(3) { top: 75%; left: 20%; animation-delay: 1.4s; }
    @keyframes radarDiscPulse {
        0%,100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
    }
    @keyframes radarSweep {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    @keyframes radarDotBlink {
        0%,100% { opacity: 0.3; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1.5); }
    }

    /* ============ SMART ALERT CYBER GLOW ============ */
    .alert-cyber-text {
        font-family: 'Orbitron', sans-serif; color: #00d4ff;
        text-shadow: 0 0 10px rgba(0,212,255,0.8), 0 0 25px rgba(0,212,255,0.4), 0 0 50px rgba(0,85,255,0.3);
        letter-spacing: 2px; animation: cyberTextGlow 2s infinite alternate;
    }
    .alert-cyber-border {
        border: 2px solid rgba(0,212,255,0.5) !important;
        box-shadow: 0 0 20px rgba(0,212,255,0.3), inset 0 0 20px rgba(0,212,255,0.05) !important;
    }
    @keyframes cyberTextGlow {
        0% { text-shadow: 0 0 8px rgba(0,212,255,0.5), 0 0 20px rgba(0,212,255,0.2); }
        100% { text-shadow: 0 0 20px rgba(0,212,255,1), 0 0 40px rgba(0,212,255,0.6), 0 0 80px rgba(0,85,255,0.4); }
    }

    /* ============ CYBER ACTIVATION FORM ============ */
    .cyber-activation-container {
        position: relative; padding: 25px;
        background: linear-gradient(145deg, rgba(0,10,20,0.9), rgba(5,15,30,0.9));
        border: 2px solid rgba(0,212,255,0.4); border-radius: 15px;
        box-shadow: 0 0 30px rgba(0,212,255,0.2), inset 0 0 30px rgba(0,212,255,0.05);
        overflow: hidden; margin: 15px 0;
    }
    .cyber-activation-container::before {
        content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
        background: conic-gradient(from 0deg, transparent, rgba(0,212,255,0.05), transparent, rgba(0,255,136,0.05), transparent);
        animation: cyberRotate 8s linear infinite; z-index: 0; pointer-events: none;
    }
    .cyber-activation-container::after {
        content: ''; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
        background: linear-gradient(180deg, transparent 0%, rgba(0,212,255,0.03) 50%, transparent 100%);
        animation: scanVertical 3s ease-in-out infinite; z-index: 0; pointer-events: none;
    }
    .cyber-activation-content { position: relative; z-index: 1; }
    .cyber-input-wrapper { position: relative; margin: 20px 0; }
    .cyber-input-wrapper::before {
        content: ''; position: absolute; bottom: -2px; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, transparent, #00d4ff, #00ff88, #00d4ff, transparent);
        animation: inputLineGlow 2s linear infinite; background-size: 200% 100%;
    }
    .cyber-input {
        background: rgba(0,0,0,0.5) !important; border: 1px solid rgba(0,212,255,0.3) !important;
        color: #00ff88 !important; font-family: 'Orbitron', sans-serif !important;
        font-size: 13px !important; letter-spacing: 2px !important;
        text-shadow: 0 0 8px rgba(0,255,136,0.6) !important; padding: 12px 15px !important;
        border-radius: 8px !important; transition: all 0.3s ease !important;
    }
    .cyber-input:focus {
        border-color: #00d4ff !important;
        box-shadow: 0 0 20px rgba(0,212,255,0.4), 0 0 40px rgba(0,212,255,0.1) !important;
        text-shadow: 0 0 15px rgba(0,255,136,0.9) !important;
    }
    .cyber-input::placeholder { color: rgba(0,212,255,0.4) !important; letter-spacing: 1px; }
    .cyber-btn {
        background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
        border: 2px solid #00d4ff !important; color: white !important;
        font-family: 'Orbitron', sans-serif !important; font-weight: 700 !important;
        padding: 12px 30px !important; border-radius: 10px !important;
        letter-spacing: 2px !important;
        box-shadow: 0 0 25px rgba(0,212,255,0.5), 0 0 50px rgba(0,85,255,0.3) !important;
        transition: all 0.4s ease !important; text-transform: uppercase;
        position: relative; overflow: hidden;
    }
    .cyber-btn::before {
        content: ''; position: absolute; top: -50%; left: -50%; width: 200%; height: 200%;
        background: linear-gradient(45deg, transparent, rgba(255,255,255,0.1), transparent);
        transform: rotate(45deg); animation: btnShine 2s infinite;
    }
    .cyber-btn:hover {
        transform: translateY(-3px);
        box-shadow: 0 0 40px rgba(0,212,255,0.8), 0 0 80px rgba(0,85,255,0.5) !important;
        border-color: #00ff88 !important;
    }
    @keyframes cyberRotate {
        from { transform: rotate(0deg); } to { transform: rotate(360deg); }
    }
    @keyframes scanVertical {
        0%,100% { transform: translateY(-100%); } 50% { transform: translateY(100%); }
    }
    @keyframes inputLineGlow {
        0% { background-position: 0% 50%; } 100% { background-position: 200% 50%; }
    }
    @keyframes btnShine {
        0% { transform: translateX(-100%) rotate(45deg); } 100% { transform: translateX(100%) rotate(45deg); }
    }
    .activation-success-anim {
        animation: successPulse 0.6s ease-in-out;
    }
    @keyframes successPulse {
        0% { transform: scale(1); } 50% { transform: scale(1.05); box-shadow: 0 0 60px rgba(0,255,136,0.8); }
        100% { transform: scale(1); }
    }

    /* ============ FINANCIAL CARDS ============ */
    .fintech-result-card {
        background: linear-gradient(145deg, rgba(0,212,255,0.08), rgba(0,85,255,0.05));
        border: 1px solid rgba(0,212,255,0.3); border-radius: 12px;
        padding: 20px; margin: 10px 0; position: relative; overflow: hidden;
    }
    .fintech-result-card::before {
        content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px;
        background: linear-gradient(90deg, transparent, #00d4ff, transparent);
        animation: scanLine 2s infinite;
    }
    @keyframes scanLine {
        0% { transform: translateX(-100%); } 100% { transform: translateX(100%); }
    }
    .risk-metric {
        font-family: 'Orbitron', sans-serif; font-size: 14px; color: #00d4ff; text-align: center;
    }

    .stButton>button {
        background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
        border: none !important; color: white !important;
        font-family: 'Orbitron', sans-serif !important; font-weight: 700 !important;
        padding: 8px 16px !important; border-radius: 10px !important;
        box-shadow: 5px 5px 15px rgba(0,0,0,0.4), -2px -2px 10px rgba(255,255,255,0.1) !important;
        transition: all 0.3s ease !important; text-transform: uppercase; letter-spacing: 1px;
    }
    .stButton>button:hover {
        transform: translateY(-2px); box-shadow: 0 10px 20px rgba(0,212,255,0.4) !important;
        filter: brightness(1.2);
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(10,14,23,0.98) 0%, rgba(5,8,15,0.99) 100%) !important;
        border-right: 2px solid rgba(0,212,255,0.3) !important;
        box-shadow: 5px 0 25px rgba(0,212,255,0.1) !important;
    }
    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(0,212,255,0.05) !important; border: 1px solid rgba(0,212,255,0.3) !important;
        border-radius: 8px !important; color: #e0e0e0 !important;
    }
    [data-testid="stSidebar"] .stSelectbox label {
        color: #00d4ff !important; font-family: 'Orbitron', sans-serif !important;
        font-size: 11px !important; letter-spacing: 1px !important;
    }
    [data-testid="stSidebar"] hr { border-color: rgba(0,212,255,0.2) !important; }
    [data-testid="stSidebar"] .nav-link {
        background: rgba(0,212,255,0.03) !important; border: 1px solid rgba(0,212,255,0.15) !important;
        border-radius: 8px !important; margin: 3px 0 !important; transition: all 0.3s ease !important;
        font-family: 'Rajdhani', sans-serif !important; font-weight: 600 !important; letter-spacing: 0.5px !important;
    }
    [data-testid="stSidebar"] .nav-link:hover {
        background: rgba(0,212,255,0.1) !important; border-color: rgba(0,212,255,0.5) !important;
        box-shadow: 0 0 15px rgba(0,212,255,0.2) !important;
    }
    [data-testid="stSidebar"] .nav-link.selected {
        background: linear-gradient(145deg, rgba(0,212,255,0.2), rgba(0,85,255,0.2)) !important;
        border-color: #00d4ff !important;
        box-shadow: 0 0 20px rgba(0,212,255,0.3), inset 0 0 10px rgba(0,212,255,0.1) !important;
        color: #00d4ff !important;
    }
</style>
""", unsafe_allow_html=True)

# ====================== API KEYS ======================
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
marketaux_key = st.secrets.get("MARKETAUX_KEY") or os.getenv("MARKETAUX_KEY")
client = None
if groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception:
        pass

# ====================== FUNGSI DATA ======================
def get_market_data(ticker_symbol):
    try:
        inst_name = ticker_symbol
        for cat in instruments.values():
            for name, tick in cat.items():
                if tick == ticker_symbol:
                    inst_name = name
                    break
        res = supabase_public.table("market_prices").select("*").eq("instrument", inst_name).execute()
        if res.data:
            cached = res.data[0]
            updated_at_str = cached['updated_at']
            if isinstance(updated_at_str, str):
                updated_at_str = updated_at_str.replace('Z', '+00:00')
                updated_at = datetime.fromisoformat(updated_at_str)
            else:
                updated_at = updated_at_str
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=pytz.UTC)
            else:
                updated_at = updated_at.astimezone(pytz.UTC)
            now = datetime.now(pytz.UTC)
            if (now - updated_at).total_seconds() < 3:
                return {
                    "price": cached['price'],
                    "change": cached['price'] * (cached.get('change_pct', 0)/100),
                    "change_pct": cached.get('change_pct', 0),
                    "source": "Cache"
                }
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="2d")
        if not hist.empty:
            price = hist["Close"].iloc[-1]
            if ticker_symbol == "GC=F": price = round(float(price), 2)
            prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else hist["Open"].iloc[-1]
            change_pct = ((price - prev_close) / prev_close) * 100
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
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=min(len(df), 200)).mean()
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    df["RSI"] = 100 - (100 / (1 + rs))
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    df["BB_Std"] = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Mid"] + (df["BB_Std"] * 2)
    df["BB_Lower"] = df["BB_Mid"] - (df["BB_Std"] * 2)
    low_14 = df["Low"].rolling(window=14).min()
    high_14 = df["High"].rolling(window=14).max()
    df["Stoch_K"] = 100 * ((df["Close"] - low_14) / (high_14 - low_14).replace(0, 0.001))
    df["Stoch_D"] = df["Stoch_K"].rolling(window=3).mean()
    high_low = df["High"] - df["Low"]
    high_cp = np.abs(df["High"] - df["Close"].shift())
    low_cp = np.abs(df["Low"] - df["Close"].shift())
    df["TR"] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()
    df["UpMove"] = df["High"] - df["High"].shift()
    df["DownMove"] = df["Low"].shift() - df["Low"]
    df["+DM"] = np.where((df["UpMove"] > df["DownMove"]) & (df["UpMove"] > 0), df["UpMove"], 0)
    df["-DM"] = np.where((df["DownMove"] > df["UpMove"]) & (df["DownMove"] > 0), df["DownMove"], 0)
    df["+DI"] = 100 * (df["+DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["-DI"] = 100 * (df["-DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["DX"] = 100 * np.abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"]).replace(0, 0.001)
    df["ADX"] = df["DX"].rolling(14).mean()
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
    required_cols = ["RSI", "MACD", "Signal_Line", "SMA50", "SMA200"]
    for col in required_cols:
        if col not in df.columns:
            return 0, "WAITING DATA", ["Data sedang dimuat..."], 0, 0, 100
    latest = df.iloc[-1]
    bull, bear, neut = 0, 0, 0
    reasons = []
    if latest["RSI"] < 30: bull += 1; reasons.append(f"RSI Oversold ({latest['RSI']:.2f})")
    elif latest["RSI"] > 70: bear += 1; reasons.append(f"RSI Overbought ({latest['RSI']:.2f})")
    else: neut += 1
    if latest["MACD"] > latest["Signal_Line"]: bull += 1; reasons.append("MACD Bullish")
    else: bear += 1; reasons.append("MACD Bearish")
    if latest["Close"] > latest["SMA50"]: bull += 1; reasons.append("SMA 50 Bullish")
    else: bear += 1
    if latest["Close"] > latest["SMA200"]: bull += 1; reasons.append("SMA 200 Bullish")
    else: bear += 1
    total = bull + bear + neut
    score = (bull / total) * 100 if total > 0 else 50
    if score > 70: signal = "STRONG BUY"
    elif score > 55: signal = "BUY"
    elif score < 30: signal = "STRONG SELL"
    elif score < 45: signal = "SELL"
    else: signal = "NEUTRAL"
    return score, signal, reasons, bull, bear, neut

# ====================== FUNGSI AI ======================
def get_groq_response(question, context=""):
    if not client: return "⚠️ Chatbot Inactive"
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_chatbot_count >= user_limits["chatbot_per_day"]:
        return f"⚠️ {t['limit_reached']} ({st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']})"
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": f"Anda AeroVulpis AI. Bahasa: {st.session_state.lang}. Konteks: {context}"},
                      {"role": "user", "content": question}],
            model='llama-3.3-70b-versatile', temperature=0.7, max_tokens=1024,
        )
        st.session_state.daily_chatbot_count += 1
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    openrouter_api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key: return "⚠️ API Key tidak ditemukan."
    cached = get_cached_ai_analysis(asset_name, "sentinel")
    if cached: return cached + "\n\n*[Cache < 5 menit]*"
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"⚠️ {t['limit_reached']}"
    latest = df.iloc[-1]; price = market_data['price']
    news_list, _ = get_news_data(asset_name, max_articles=5)
    news_context = "\n".join([f"- {n['title']}" for n in news_list]) if news_list else "Tidak ada"
    prompt = f"""Anda AeroVulpis Sentinel Pro. Analisis {asset_name}.\nHarga: {price:,.4f}\nSinyal: {signal}\nRSI: {latest.get('RSI',0):.2f}\nBerita: {news_context}\n\nBerikan: KEY LEVELS, FUNDAMENTAL INSIGHT, TRADE SCENARIOS (Bullish/Bearish), FINAL VERDICT. Maks 320 kata. Bahasa Indonesia."""
    def call_openrouter(model_name, system_msg):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_api_key}", "Content-Type": "application/json"},
                data=json.dumps({"model": model_name, "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}]}),
                timeout=45
            )
            if response.status_code == 200: return response.json()['choices'][0]['message']['content']
            return None
        except: return None
    analysis = call_openrouter('nousresearch/hermes-3-llama-3.1-405b', "Anda AeroVulpis Sentinel (Hermes 405B).")
    if analysis:
        companion = call_openrouter('qwen/qwen-2-72b-instruct', "Detail tambahan.")
        if companion: analysis += "\n\n---\n**Qwen 72B Insights:**\n" + companion
    else:
        for model in ['deepseek/deepseek-chat', 'minimax/minimax-01', 'google/gemini-flash-1.5']:
            analysis = call_openrouter(model, "Backup AI.")
            if analysis: break
    if analysis:
        st.session_state.daily_analysis_count += 1
        cache_ai_analysis(asset_name, "sentinel", analysis)
    return analysis or "⚠️ Semua model AI sibuk."

def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    if not client: return "⚠️ Deep Analysis Inactive"
    cached = get_cached_ai_analysis(asset_name, "deep")
    if cached: return cached + "\n\n*[Cache < 5 menit]*"
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"⚠️ {t['limit_reached']}"
    latest = df.iloc[-1]; price = market_data['price']
    technical_data = f"""INSTRUMEN: {asset_name}\nHARGA: {price:,.4f}\nRSI: {latest['RSI']:.2f}\nMACD: {latest['MACD']:.4f}\nSMA50: {latest['SMA50']:.4f}\nSMA200: {latest['SMA200']:.4f}\nATR: {latest['ATR']:.4f}"""
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": f"Anda AeroVulpis Deep Analysis (Llama 3.3 70B). Analisis teknikal mendalam. Maks 2000 karakter. Bahasa Indonesia."},
                      {"role": "user", "content": f"Analisis: {technical_data}\nEntry, SL, TP. Risk management."}],
            model='llama-3.3-70b-versatile', temperature=0.6, max_tokens=2000,
        )
        analysis = chat_completion.choices[0].message.content
        st.session_state.daily_analysis_count += 1
        cache_ai_analysis(asset_name, "deep", analysis)
        return analysis
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

# ====================== FUNGSI LAIN ======================
def market_session_status():
    tz = pytz.timezone('Asia/Jakarta'); now = datetime.now(tz); current_time = now.time()
    sessions = [
        {"name": "Asian (Tokyo)", "start": dt_time(6,0), "end": dt_time(15,0), "color": "#00ff88"},
        {"name": "European (London)", "start": dt_time(14,0), "end": dt_time(23,0), "color": "#00d4ff"},
        {"name": "American (New York)", "start": dt_time(19,0), "end": dt_time(4,0), "color": "#ff2a6d"}
    ]
    for sess in sessions:
        is_active = sess["start"] <= current_time <= sess["end"] if sess["start"] < sess["end"] else current_time >= sess["start"] or current_time <= sess["end"]
        st.markdown(f'<div class="glass-card"><span style="color:{sess["color"]}">{sess["name"]}</span>: {"🟢 ACTIVE" if is_active else "🔴 CLOSED"}</div>', unsafe_allow_html=True)
    if dt_time(19,0) <= current_time <= dt_time(23,0):
        st.markdown('<div class="cyan-neon">GOLDEN TIME! High Volatility 🚀</div>', unsafe_allow_html=True)

def get_news_data(category="General", max_articles=10):
    from news_cache_manager import should_update_news, get_cached_news, update_news_cache
    if not should_update_news(category): return get_cached_news(category), None
    berita_final = []; urls_terpakai = set()
    category_map = {"Stock": "stocks", "Konflik": "geopolitics", "Gold & Silver": "gold,silver", "Forex": "forex", "General": "finance"}
    api_query = category_map.get(category, "finance")
    if marketaux_key:
        try:
            url_m = f"https://api.marketaux.com/v1/news/all?api_token={marketaux_key}&language=en&search={api_query}&limit=15"
            res_m = requests.get(url_m, timeout=10).json()
            for item in res_m.get('data', []):
                if item.get('url') and item['url'] not in urls_terpakai:
                    berita_final.append({'publishedAt': item.get('published_at',''), 'title': item.get('title',''), 'description': item.get('description',''), 'source': 'Marketaux', 'url': item['url']})
                    urls_terpakai.add(item['url'])
        except: pass
    if berita_final:
        berita_final = sorted(berita_final, key=lambda x: x['publishedAt'], reverse=True)[:max_articles]
        update_news_cache(category, berita_final)
    return berita_final if berita_final else get_cached_news(category), None if berita_final else "Gagal ambil berita"

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

# ====================== SIDEBAR ======================
with st.sidebar:
    st.markdown("<div style='text-align:center; margin-bottom: -10px;'><img src='https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png' style='width:55px; filter:drop-shadow(0 0 8px var(--electric-blue));'></div>", unsafe_allow_html=True)
    st.markdown(f"<h2 class='digital-font' style='text-align:center; font-size:18px; margin-bottom:0;'>{t['control_center']}</h2>", unsafe_allow_html=True)

    # ===== LOGIN / USER SECTION =====
    try:
        auth_session = supabase_public.auth.get_session()
        user = auth_session.user if auth_session else None
    except:
        user = None

    if user:
        user_name = user.user_metadata.get("full_name", user.email.split("@")[0])
        st.session_state.user_tier = get_user_tier(user.id)
        tier_colors = {"free":"#888","trial":"#00d4ff","weekly":"#00ff88","monthly":"#ffcc00","six_months":"#ff8800","yearly":"#ff2a6d"}
        tier_names = {"free":"FREE","trial":"TRIAL","weekly":"WEEKLY","monthly":"MONTHLY","six_months":"6M PRO","yearly":"ULTIMATE"}
        tier_color = tier_colors.get(st.session_state.user_tier, "#888")
        tier_name = tier_names.get(st.session_state.user_tier, "FREE")
        st.markdown(f"""
        <div style="background:rgba(0,0,0,0.3); border:1px solid {tier_color}; border-radius:10px; padding:10px; margin:8px 0; text-align:center; box-shadow:0 0 10px rgba(0,212,255,0.2);">
            <p style="color:#00d4ff; font-family:'Rajdhani',sans-serif; font-size:13px; margin:0;">{t['welcome']}, {user_name}</p>
            <span style="font-family:'Orbitron',sans-serif; font-size:9px; color:{tier_color}; letter-spacing:2px;">[{tier_name}]</span>
        </div>
        """, unsafe_allow_html=True)
        if st.button(t['logout'], use_container_width=True):
            supabase_public.auth.sign_out()
            st.session_state.user_tier = "free"
            st.rerun()

        if st.button(t['activate_key'], use_container_width=True):
            st.session_state.show_activation = not st.session_state.show_activation

        if st.session_state.show_activation:
            st.markdown("---")
            st.markdown('<div class="cyber-activation-container"><div class="cyber-activation-content"><p class="alert-cyber-text" style="font-size:14px; text-align:center; margin-bottom:15px;">KEY ACTIVATION TERMINAL</p><div class="cyber-input-wrapper">', unsafe_allow_html=True)
            key_input = st.text_input(t['enter_key'], placeholder="AV-XXX-2026-XXXX-XXXX", key="activation_key_input", label_visibility="collapsed")
            st.markdown('</div>', unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1,2,1])
            with col2:
                if st.button(t['activate_btn'], use_container_width=True, type="primary"):
                    if key_input:
                        with st.spinner(t['processing']):
                            time.sleep(0.5)
                            success, result = activate_key(user.id, key_input)
                            if success:
                                st.success(f"✅ {t['activation_success']} Tier: {result.upper()}")
                                st.balloons()
                                st.session_state.show_activation = False
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"❌ {result}")
                    else:
                        st.warning("Masukkan kunci aktivasi!")
            st.markdown('</div></div>', unsafe_allow_html=True)
    else:
        st.markdown("<p style='font-family:Rajdhani; font-size:12px; color:#888; text-align:center;'>Sign in to unlock features</p>", unsafe_allow_html=True)
        if st.button(t['login_google'], use_container_width=True, type="primary"):
            try:
                auth_url = supabase_public.auth.sign_in_with_oauth({
                    "provider": "google",
                    "options": {"redirect_to": "https://aerovulpis.streamlit.app"}
                })
                st.markdown(f'<meta http-equiv="refresh" content="0;url={auth_url.url}">', unsafe_allow_html=True)
            except Exception as e:
                st.error(f"Login error: {str(e)}")

    st.markdown("**AeroVulpis V3.4** — **DYNAMIHATCH**")
    st.caption("2026 • Powered by Real-Time AI")

    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    ticker_display = f"{asset_name} ({ticker_input})"

    st.markdown("---")
    tf_options = {"15m":{"period":"5d","interval":"15m"},"30m":{"period":"5d","interval":"30m"},"1h":{"period":"1mo","interval":"1h"},"3h":{"period":"1mo","interval":"1h"},"4h":{"period":"1mo","interval":"1h"},"1D":{"period":"1y","interval":"1d"},"1W":{"period":"2y","interval":"1wk"}}
    selected_tf_display = st.selectbox(t['timeframe'], list(tf_options.keys()), index=0)
    period = tf_options[selected_tf_display]["period"]
    interval = tf_options[selected_tf_display]["interval"]

    menu_selection = option_menu(
        menu_title=t['navigation'],
        options=["Live Dashboard", "AeroVulpis Sentinel", "Signal Analysis", "Market Sessions", "Market News", "Economic Radar", "Smart Alert Center", "Chatbot AI", "Risk Management", "Settings", "Help & Support"],
        icons=["activity","shield-shaded","graph-up-arrow","globe","newspaper","calendar-event","bell-fill","chat-dots","shield-fill","gear","question-circle"],
        menu_icon="cast", default_index=0,
        styles={"container":{"padding":"5!important","background-color":"transparent"},"icon":{"color":"#00d4ff","font-size":"14px"},"nav-link":{"font-size":"12px","text-align":"left","margin":"2px 0","padding":"10px 12px","border-radius":"8px","font-family":"'Rajdhani',sans-serif","font-weight":"600","letter-spacing":"0.5px","background":"rgba(0,212,255,0.03)","border":"1px solid rgba(0,212,255,0.1)","transition":"all 0.3s ease"},"nav-link-selected":{"background":"linear-gradient(145deg, rgba(0,212,255,0.2), rgba(0,85,255,0.15))","border":"1px solid #00d4ff","color":"#00d4ff","box-shadow":"0 0 15px rgba(0,212,255,0.2)","font-weight":"700"}}
    )

    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(0,0,0,0.3); border:1px solid rgba(0,212,255,0.2); border-radius:8px; padding:10px; margin-top:10px;">
        <p style="font-family:'Orbitron',sans-serif; font-size:9px; color:#888; margin:0 0 5px 0; letter-spacing:1px;">{t['daily_limit']}</p>
        <p style="font-family:'Rajdhani',sans-serif; font-size:11px; color:#00d4ff; margin:2px 0;">🤖 AI: {st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']}</p>
        <p style="font-family:'Rajdhani',sans-serif; font-size:11px; color:#00d4ff; margin:2px 0;">💬 Chat: {st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']}</p>
    </div>
    """, unsafe_allow_html=True)

# ====================== MAIN CONTENT ======================
if menu_selection == "AeroVulpis Sentinel":
    st.markdown('<div class="sentinel-container"><div class="sentinel-header"><h2 class="sentinel-title">AEROVULPIS SENTINEL</h2><div style="display:flex;gap:10px;"><span class="status-badge status-open">MARKET: OPEN</span><span class="status-badge status-ai">HERMES 405B + QWEN 72B</span></div></div>', unsafe_allow_html=True)
    col_chart, col_intel = st.columns([2,1])
    with col_chart:
        tv_symbol = ticker_input.replace("-USD","USD").replace("=X","").replace(".JK","")
        if "GC=F" in ticker_input: tv_symbol = "COMEX:GC1!"
        elif "SI=F" in ticker_input: tv_symbol = "COMEX:SI1!"
        elif "CL=F" in ticker_input: tv_symbol = "NYMEX:CL1!"
        st.components.v1.html(f'<div id="tv_sentinel" style="height:500px;"></div><script src="https://s3.tradingview.com/tv.js"></script><script>new TradingView.widget({{"autosize":true,"symbol":"{tv_symbol}","interval":"D","theme":"dark","container_id":"tv_sentinel"}});</script>', height=500)
        loading_placeholder = st.empty()
        if st.button("GENERATE DEEP ANALYSIS PRO", key="sentinel_pro_btn", use_container_width=True):
            market = get_market_data(ticker_input)
            df = get_historical_data(ticker_input, period, interval)
            if market and not df.empty:
                df = add_technical_indicators(df)
                score, signal, reasons, _, _, _ = get_weighted_signal(df)
                loading_placeholder.markdown('<div class="loading-3d-pro-container"><div class="loading-3d-pro-scene"><div class="loading-3d-pro-core"><div class="loading-3d-pro-ring"></div><div class="loading-3d-pro-ring"></div><div class="loading-3d-pro-ring"></div><div class="loading-3d-pro-ring"></div></div><div class="loading-3d-pro-center"></div><div class="loading-3d-pro-particles"><div class="loading-3d-pro-particle"></div><div class="loading-3d-pro-particle"></div><div class="loading-3d-pro-particle"></div><div class="loading-3d-pro-particle"></div><div class="loading-3d-pro-particle"></div><div class="loading-3d-pro-particle"></div></div></div><p class="loading-3d-pro-text">SENTINEL PRO ANALYZING</p><p class="loading-3d-pro-sub">Hermes 405B + Qwen 72B • Market Microstructure Scan</p></div>', unsafe_allow_html=True)
                progress_bar = st.progress(0)
                for i in range(100): time.sleep(0.03); progress_bar.progress(i+1)
                st.session_state.sentinel_analysis = get_sentinel_analysis(asset_name, market, df, signal, reasons)
                loading_placeholder.empty(); progress_bar.empty()
            else:
                st.error("Gagal mengambil data pasar.")
    with col_intel:
        st.markdown('<div class="intelligence-panel"><div class="intel-header">SENTINEL INTELLIGENCE</div><div class="intel-content">', unsafe_allow_html=True)
        if st.session_state.sentinel_analysis: st.markdown(st.session_state.sentinel_analysis)
        else: st.info("Klik tombol Generate untuk analisis Pro.")
        st.markdown('</div></div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "Live Dashboard":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    if market and not df.empty:
        if selected_tf_display in ["3h","4h"]:
            df = df.resample("3h" if selected_tf_display=="3h" else "4h").agg({'Open':'first','High':'max','Low':'min','Close':'last','Volume':'sum'}).dropna()
        df = add_technical_indicators(df)
        score, signal, reasons, _, _, _ = get_weighted_signal(df)
        c1,c2,c3,c4 = st.columns(4)
        fmt_price = f"{market['price']:,.2f}" if "Gold" in asset_name or "XAU" in asset_name else f"{market['price']:,.4f}".rstrip('0').rstrip('.')
        c1.markdown(f'<div class="glass-card"><p style="color:#888;font-size:10px;">{t["live_price"]}</p><p class="digital-font" style="font-size:20px;">{fmt_price}</p></div>', unsafe_allow_html=True)
        color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
        c2.markdown(f'<div class="glass-card"><p style="color:#888;font-size:10px;">{t["signal"]}</p><p class="digital-font" style="font-size:20px;color:{color};">{signal}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div class="glass-card"><p style="color:#888;font-size:10px;">{t["rsi"]}</p><p class="digital-font" style="font-size:20px;">{df["RSI"].iloc[-1]:.2f}</p></div>', unsafe_allow_html=True)
        c4.markdown(f'<div class="glass-card"><p style="color:#888;font-size:10px;">{t["atr"]}</p><p class="digital-font" style="font-size:20px;">{df["ATR"].iloc[-1]:.4f}</p></div>', unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode='lines', line=dict(color='#00ff88',width=2), name='Price'))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", height=350)
        st.plotly_chart(fig, use_container_width=True)
        col_g, col_a = st.columns([1,1])
        with col_g:
            fig_gauge = go.Figure(go.Indicator(mode="gauge+number",value=score,title={"text":"Strength"},gauge={"axis":{"range":[0,100]},"bar":{"color":color}}))
            fig_gauge.update_layout(height=250)
            st.plotly_chart(fig_gauge, use_container_width=True)
        with col_a:
            for r in reasons: st.write(f"💠 {r}")
            if st.button(t['generate_ai'], use_container_width=True):
                with st.spinner("Llama 3.3 70B analyzing..."):
                    st.info(get_deep_analysis(asset_name, market, df, signal, reasons))

elif menu_selection == "Signal Analysis":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    if not df.empty:
        df = add_technical_indicators(df)
        score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
        st.markdown(f"### {t['recommendation']}: {signal}")
        c1,c2,c3 = st.columns(3)
        c1.markdown(f'🟢 BULLISH: {bull}'); c2.markdown(f'🔴 BEARISH: {bear}'); c3.markdown(f'🟡 NEUTRAL: {neut}')

elif menu_selection == "Market Sessions":
    market_session_status()

elif menu_selection == "Market News":
    st.markdown(f'<h2 class="digital-font">{t["market_news"]}</h2>', unsafe_allow_html=True)
    articles, error = get_news_data("General", 10)
    if articles:
        for a in articles:
            st.markdown(f'<div class="glass-card"><b style="color:#00d4ff;">{a["title"]}</b><br><small>{a.get("publishedAt","")}</small><br>{a["description"]}</div>', unsafe_allow_html=True)
    else:
        st.info(t['no_news'])

elif menu_selection == "Economic Radar":
    economic_calendar_widget()
    st.markdown("""
    <div class="radar-cyber-container">
        <div class="radar-cyber-disc">
            <div class="radar-cyber-sweep"></div>
            <div class="radar-cyber-dot"></div>
            <div class="radar-cyber-dot"></div>
            <div class="radar-cyber-dot"></div>
        </div>
        <p class="alert-cyber-text" style="font-size:14px; margin:0;">GLOBAL ECONOMIC SCANNER</p>
    </div>
    """, unsafe_allow_html=True)

elif menu_selection == "Smart Alert Center":
    st.markdown('<div class="alert-cyber-border" style="border-radius:15px; padding:25px; margin-bottom:20px;"><h2 class="alert-cyber-text" style="text-align:center; font-size:26px;">SMART ALERT CENTER V3.4</h2>', unsafe_allow_html=True)
    smart_alert_widget()
    st.markdown('</div>', unsafe_allow_html=True)

elif menu_selection == "Chatbot AI":
    st.markdown('<h2 class="digital-font">🤖 AeroVulpis AI Assistant</h2>', unsafe_allow_html=True)
    if "messages" not in st.session_state: st.session_state.messages = []
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]): st.markdown(msg["content"])
    if prompt := st.chat_input("Tanya AeroVulpis..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.chat_message("assistant"):
            response = get_groq_response(prompt, f"Instrumen: {ticker_display}")
            st.markdown(response)
        st.session_state.messages.append({"role":"assistant","content":response})

elif menu_selection == "Risk Management":
    st.markdown('<h2 class="digital-font" style="text-align:center;">Risk Management Protocol</h2>', unsafe_allow_html=True)
    balance = st.number_input("Account Balance ($)", value=1000.0, step=100.0)
    rr_ratios = {"1:2":2.0,"1:3":3.0,"1:4":4.0}
    selected_rr = st.radio("R:R Ratio", list(rr_ratios.keys()), horizontal=True)
    wins = st.number_input("Wins/Week", value=3, step=1)
    losses = st.number_input("Losses/Week", value=2, step=1)
    max_daily_loss_pct = st.number_input("Max Daily Loss %", value=5.0)
    max_daily_profit_pct = st.number_input("Max Daily Profit Target %", value=10.0)
    if st.button("CALCULATE", use_container_width=True, type="primary"):
        risk_amt = balance * 0.01
        reward_amt = risk_amt * rr_ratios[selected_rr]
        weekly_net = (wins*reward_amt) - (losses*risk_amt)
        max_daily_loss = balance * (max_daily_loss_pct/100)
        max_daily_profit = balance * (max_daily_profit_pct/100)
        st.markdown(f"""
        <div class="fintech-result-card">
            <p class="risk-metric">Weekly Net: {weekly_net:+,.2f} USD</p>
            <p class="risk-metric">Monthly Net: {weekly_net*4:+,.2f} USD</p>
            <p class="risk-metric">Yearly Net: {weekly_net*52:+,.2f} USD</p>
            <p class="risk-metric" style="color:#ff2a6d;">Max Daily Loss: -{max_daily_loss:,.2f} USD</p>
            <p class="risk-metric" style="color:#00ff88;">Max Daily Profit: +{max_daily_profit:,.2f} USD</p>
            <p class="risk-metric">Final Balance (1Y): {balance+(weekly_net*52):,.2f} USD</p>
        </div>
        """, unsafe_allow_html=True)

elif menu_selection == "Settings":
    st.markdown(f'<h2 class="digital-font">{t["settings"]}</h2>', unsafe_allow_html=True)
    new_lang = st.selectbox(t['lang_select'], ["ID","EN"], index=0 if st.session_state.lang=="ID" else 1)
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    if st.button(t['clear_cache'], use_container_width=True):
        st.cache_data.clear()
        st.session_state.cached_analysis = {}
        st.success("Cache Cleared!")

elif menu_selection == "Help & Support":
    st.markdown('<h2 class="digital-font" style="text-align:center;">Help & Support</h2>', unsafe_allow_html=True)
    packages = [
        {"name":"1 DAY TRIAL","price":"Rp999","color":"#00d4ff","analysis":"10/day","chatbot":"50/day"},
        {"name":"1 WEEK","price":"Rp15.000","color":"#00ff88","analysis":"20/day","chatbot":"100/day"},
        {"name":"1 MONTH","price":"Rp29.000","color":"#ffcc00","analysis":"50/day","chatbot":"200/day"},
        {"name":"6 MONTHS","price":"Rp99.000","color":"#ff8800","analysis":"100/day","chatbot":"500/day"},
        {"name":"1 YEAR","price":"Rp149.000","color":"#ff2a6d","analysis":"Unlimited","chatbot":"Unlimited"}
    ]
    cols = st.columns(5)
    for i, pkg in enumerate(packages):
        with cols[i]:
            st.markdown(f'<div style="border:1px solid {pkg["color"]}; border-radius:10px; padding:15px; text-align:center;"><p style="color:{pkg["color"]}; font-family:Orbitron;">{pkg["name"]}</p><p style="font-size:18px;">{pkg["price"]}</p><p>🤖 {pkg["analysis"]}</p><p>💬 {pkg["chatbot"]}</p></div>', unsafe_allow_html=True)
    st.markdown("<p style='text-align:center; color:#888;'>*Registration, payment & key system</p>", unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 20px; opacity: 0.8;">
    <p class="rajdhani-font" style="font-style: italic; font-size: 18px; color: #ccc;">
        "Disiplin adalah kunci, emosi adalah musuh. Tetap tenang dan percaya pada sistem."
    </p>
    <p class="digital-font" style="font-size: 15px; color: #00ff88;">
        — Fahmi (Pencipta AeroVulpis)
    </p>
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v3.4 ULTIMATE • 2026</p>
</div>
""", unsafe_allow_html=True)
