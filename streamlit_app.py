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
from urllib.parse import urlencode, parse_qs

from dotenv import load_dotenv
load_dotenv()

# ====================== KONFIGURASI SUPABASE ======================
url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]
service_role_key = st.secrets.get("supabase_service_role_key", key)

def get_supabase_client():
    """Mendapatkan Supabase client dengan anon key"""
    return create_client(url, key)

def get_supabase_admin():
    """Mendapatkan Supabase client dengan service_role key (untuk operasi admin)"""
    return create_client(url, service_role_key)

# ====================== FUNGSI LOGGING & CLEANUP ======================
def send_log(pesan):
    """Mencatat log aktivitas ke Supabase"""
    try:
        supabase = get_supabase_client()
        supabase.table("logs_aktivitas").insert({"keterangan": pesan}).execute()
    except Exception:
        pass

def cleanup_logs():
    """Menghapus log yang lebih lama dari 24 jam"""
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        supabase.table("logs_aktivitas").delete().lt("created_at", cutoff).execute()
    except Exception:
        pass

def cache_market_price(symbol, price, change_pct=0.0):
    """Menyimpan harga pasar terbaru ke Supabase cache"""
    try:
        supabase = get_supabase_client()
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
    """Mengambil harga pasar dari cache Supabase"""
    try:
        supabase = get_supabase_client()
        res = supabase.table("market_prices").select("price").eq("instrument", symbol).execute()
        if res.data:
            return res.data[0]["price"]
    except Exception:
        pass
    return None

def cleanup_old_data():
    """Menghapus data market_prices yang lebih lama dari 24 jam"""
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now(pytz.timezone('Asia/Jakarta')) - timedelta(hours=24)).isoformat()
        supabase.table("market_prices").delete().lt("updated_at", cutoff).execute()
    except Exception:
        pass

# ====================== FUNGSI USER & TIER ======================
def get_user_tier(user_id):
    """
    Cek tier user dari tabel user_tiers
    Return: (tier, expired_at)
    Jika expired, return 'free'
    """
    if not user_id:
        return "free", None
    try:
        supabase = get_supabase_client()
        res = supabase.table("user_tiers").select("tier, expired_at").eq("user_id", user_id).execute()
        if res.data:
            tier = res.data[0]["tier"]
            expired_at = res.data[0].get("expired_at")
            if expired_at:
                try:
                    expired_date = datetime.fromisoformat(expired_at.replace('Z', '+00:00'))
                    if datetime.now(pytz.UTC) > expired_date:
                        # Tier expired, update ke free
                        get_supabase_admin().table("user_tiers").update({"tier": "free"}).eq("user_id", user_id).execute()
                        return "free", None
                except Exception:
                    pass
            return tier, expired_at
    except Exception:
        pass
    return "free", None

def activate_key(user_id, key_code):
    """
    Validasi dan aktivasi kunci premium
    1. Cek kunci di tabel activation_keys (is_used = false)
    2. Update user_tiers dengan tier baru
    3. Tandai kunci sebagai used
    """
    if not user_id or not key_code:
        return False, "User ID dan kunci harus diisi"
    
    try:
        supabase = get_supabase_client()
        
        # Cari kunci yang valid dan belum digunakan
        res = supabase.table("activation_keys").select("*").eq("key_code", key_code).eq("is_used", False).execute()
        
        if not res.data:
            return False, "Kunci tidak valid atau sudah digunakan"
        
        key_data = res.data[0]
        tier = key_data.get("tier", "monthly")
        duration_days = key_data.get("duration_days", 30)
        
        # Hitung expired date
        expired_at = (datetime.now(pytz.UTC) + timedelta(days=duration_days)).isoformat()
        
        # Gunakan service_role untuk update (bypass RLS)
        supabase_admin = get_supabase_admin()
        
        # Update/Create user tier
        supabase_admin.table("user_tiers").upsert({
            "user_id": user_id,
            "tier": tier,
            "expired_at": expired_at,
            "activated_at": datetime.now(pytz.UTC).isoformat()
        }).execute()
        
        # Tandai kunci sebagai sudah digunakan
        supabase.table("activation_keys").update({
            "is_used": True,
            "used_by": user_id,
            "used_at": datetime.now(pytz.UTC).isoformat()
        }).eq("key_code", key_code).execute()
        
        return True, f"Aktivasi berhasil! Tier: {tier.upper()}, Expired: {expired_at[:10]}"
    
    except Exception as e:
        return False, f"Error aktivasi: {str(e)}"

def sync_user_to_supabase(user_id, email, name, avatar=""):
    """
    Sinkronisasi data user dari Google OAuth ke tabel users
    Insert jika belum ada, update jika sudah ada
    """
    try:
        supabase = get_supabase_client()
        existing = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if existing.data:
            # Update last_login
            supabase.table("users").update({
                "email": email,
                "name": name,
                "avatar": avatar,
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).eq("id", user_id).execute()
        else:
            # Insert user baru
            supabase.table("users").insert({
                "id": user_id,
                "email": email,
                "name": name,
                "avatar": avatar,
                "created_at": datetime.now(pytz.UTC).isoformat(),
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).execute()
            
            # Kasih tier free untuk user baru
            supabase.table("user_tiers").insert({
                "user_id": user_id,
                "tier": "free",
                "activated_at": datetime.now(pytz.UTC).isoformat()
            }).execute()
    except Exception:
        pass

# ====================== CACHE AI ANALYSIS ======================
def get_cached_ai_analysis(asset_name, timeframe):
    """
    Mengambil cache analisis AI dari Supabase
    Cache berlaku 5 menit untuk menghemat API calls
    """
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now(pytz.UTC) - timedelta(minutes=5)).isoformat()
        res = supabase.table("ai_analysis_cache").select("*")\
            .eq("asset_name", asset_name)\
            .eq("timeframe", timeframe)\
            .gte("created_at", cutoff)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            return res.data[0]["analysis"]
    except Exception:
        pass
    return None

def cache_ai_analysis(asset_name, timeframe, analysis):
    """
    Menyimpan cache analisis AI ke Supabase
    Untuk berbagi hasil analisis antar user (hemat API)
    """
    try:
        supabase = get_supabase_client()
        data = {
            "asset_name": asset_name,
            "timeframe": timeframe,
            "analysis": analysis,
            "created_at": datetime.now(pytz.UTC).isoformat()
        }
        supabase.table("ai_analysis_cache").insert(data).execute()
    except Exception:
        pass

# ====================== GOOGLE OAUTH HANDLER ======================
def handle_google_oauth():
    """
    Menangani redirect dari Google OAuth via Supabase Auth
    1. Cek query params untuk 'code' (dari Google redirect)
    2. Exchange code untuk session
    3. Sync user ke Supabase
    4. Cek tier user
    """
    query_params = st.query_params
    
    # Handle OAuth callback (ada 'code' di URL)
    if "code" in query_params:
        code = query_params["code"]
        try:
            supabase = get_supabase_client()
            # Exchange authorization code for session
            auth_response = supabase.auth.exchange_code_for_session({"auth_code": code})
            
            if auth_response and auth_response.user:
                user = auth_response.user
                user_id = user.id
                user_email = user.email or ""
                user_name = user.user_metadata.get("full_name", "") or user.user_metadata.get("name", "") or (user_email.split("@")[0] if user_email else "User")
                user_avatar = user.user_metadata.get("avatar_url", "") or user.user_metadata.get("picture", "")
                
                # Sync ke tabel users
                sync_user_to_supabase(user_id, user_email, user_name, user_avatar)
                
                # Simpan ke session state
                st.session_state.auth_session = auth_response.session.access_token if auth_response.session else "active"
                st.session_state.user_id = user_id
                st.session_state.user_name = user_name
                st.session_state.user_email = user_email
                st.session_state.user_avatar = user_avatar
                
                # Ambil tier user
                st.session_state.user_tier, _ = get_user_tier(user_id)
                
                # Bersihkan query params & rerun
                st.query_params.clear()
                send_log(f"User login: {user_name} ({user_email})")
                st.rerun()
                
        except Exception as e:
            st.sidebar.error(f"OAuth Error: {str(e)}")
            send_log(f"OAuth Error: {str(e)}")
    
    # Cek existing session (user sudah login sebelumnya)
    if not st.session_state.get("auth_session"):
        try:
            supabase = get_supabase_client()
            session = supabase.auth.get_session()
            if session and session.user:
                user = session.user
                st.session_state.auth_session = session.access_token
                st.session_state.user_id = user.id
                st.session_state.user_name = user.user_metadata.get("full_name", user.email.split("@")[0] if user.email else "User")
                st.session_state.user_email = user.email or ""
                st.session_state.user_avatar = user.user_metadata.get("avatar_url", "")
                st.session_state.user_tier, _ = get_user_tier(user.id)
        except Exception:
            pass

# ====================== KONFIGURASI APLIKASI ======================
st.set_page_config(
    layout="wide",
    page_title="AeroVulpis v3.4 Ultimate",
    page_icon="🦅",
    initial_sidebar_state="expanded"
)

# Eksekusi Awal
cleanup_logs()
cleanup_old_data()
send_log("AeroVulpis Online")

# ====================== SESSION STATE ======================
# Bahasa
if "lang" not in st.session_state:
    st.session_state.lang = "ID"

# Cache AI
if "cached_analysis" not in st.session_state:
    st.session_state.cached_analysis = {}

# User & Auth
if "user_tier" not in st.session_state:
    st.session_state.user_tier = "free"
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None
if "user_avatar" not in st.session_state:
    st.session_state.user_avatar = None
if "auth_session" not in st.session_state:
    st.session_state.auth_session = None

# Daily Limits
if "daily_analysis_count" not in st.session_state:
    st.session_state.daily_analysis_count = 0
if "daily_chatbot_count" not in st.session_state:
    st.session_state.daily_chatbot_count = 0
if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = datetime.now().date()

# Aktivasi
if "show_activation" not in st.session_state:
    st.session_state.show_activation = False
if "activation_result" not in st.session_state:
    st.session_state.activation_result = None

# Analisis & Chat
if "sentinel_analysis" not in st.session_state:
    st.session_state.sentinel_analysis = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_alerts" not in st.session_state:
    st.session_state.active_alerts = []

# Reset daily limits jika sudah ganti hari
if st.session_state.last_reset_date < datetime.now().date():
    st.session_state.daily_analysis_count = 0
    st.session_state.daily_chatbot_count = 0
    st.session_state.last_reset_date = datetime.now().date()

# Handle Google OAuth Redirect
handle_google_oauth()

# ====================== LIMIT KONFIGURASI PER TIER ======================
LIMITS = {
    "free": {"analysis_per_day": 5, "chatbot_per_day": 20},
    "trial": {"analysis_per_day": 10, "chatbot_per_day": 50},
    "weekly": {"analysis_per_day": 20, "chatbot_per_day": 100},
    "monthly": {"analysis_per_day": 50, "chatbot_per_day": 200},
    "six_months": {"analysis_per_day": 100, "chatbot_per_day": 500},
    "yearly": {"analysis_per_day": 999999, "chatbot_per_day": 999999}
}

# ====================== KAMUS BAHASA (LENGKAP ID & EN) ======================
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
        "login_google": "MASUK DENGAN GOOGLE",
        "logout": "KELUAR",
        "activate_key": "AKTIVASI KUNCI PREMIUM",
        "enter_key": "Masukkan Kunci Aktivasi",
        "activate_btn": "AKTIVASI",
        "welcome": "Selamat Datang",
        "tier_free": "GRATIS",
        "processing": "Memproses aktivasi...",
        "activation_success": "Aktivasi Berhasil!",
        "activation_failed": "Aktivasi Gagal!",
        "sign_in_prompt": "MASUK UNTUK MEMBUKA FITUR PREMIUM",
        "sign_in_desc": "Login dengan Google untuk menyimpan data dan mengakses fitur eksklusif.",
        "already_logged_in": "Anda sudah masuk sebagai",
        "tier_badge": "Tier",
        "activate_title": "AKTIVASI KUNCI PREMIUM",
        "activate_desc": "Masukkan kunci aktivasi yang Anda dapatkan untuk upgrade tier.",
        "activate_placeholder": "XXXX-XXXX-XXXX-XXXX",
        "activate_success_msg": "Selamat! Tier Anda sekarang: ",
        "activate_failed_msg": "Aktivasi gagal. Periksa kunci Anda.",
        "market_overview": "MARKET OVERVIEW"
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
        "activate_key": "ACTIVATE PREMIUM KEY",
        "enter_key": "Enter Activation Key",
        "activate_btn": "ACTIVATE",
        "welcome": "Welcome",
        "tier_free": "FREE",
        "processing": "Processing activation...",
        "activation_success": "Activation Successful!",
        "activation_failed": "Activation Failed!",
        "sign_in_prompt": "SIGN IN TO UNLOCK PREMIUM FEATURES",
        "sign_in_desc": "Login with Google to save data and access exclusive features.",
        "already_logged_in": "You are logged in as",
        "tier_badge": "Tier",
        "activate_title": "ACTIVATE PREMIUM KEY",
        "activate_desc": "Enter the activation key you received to upgrade your tier.",
        "activate_placeholder": "XXXX-XXXX-XXXX-XXXX",
        "activate_success_msg": "Congratulations! Your tier is now: ",
        "activate_failed_msg": "Activation failed. Check your key.",
        "market_overview": "MARKET OVERVIEW"
    }
}

t = translations[st.session_state.lang]

# ====================== CSS LENGKAP (~600 BARIS) ======================
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

    /* ============================================================
       ANIMASI LOADING 3D SMOOTH - SENTINEL PRO (HERMES 405B + QWEN)
       ============================================================ */
    .loading-3d-pro-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 50px;
        position: relative;
        background: radial-gradient(circle at center, rgba(0, 212, 255, 0.08) 0%, transparent 70%);
        border-radius: 20px;
        border: 1px solid rgba(0, 212, 255, 0.15);
    }
    
    .loading-3d-pro-scene {
        width: 130px;
        height: 130px;
        perspective: 500px;
        position: relative;
    }
    
    .loading-3d-pro-core {
        width: 100%;
        height: 100%;
        position: relative;
        transform-style: preserve-3d;
        animation: rotate3DPro 3s infinite cubic-bezier(0.68, -0.55, 0.27, 1.55);
    }
    
    .loading-3d-pro-ring {
        position: absolute;
        border-radius: 50%;
        border: 2px solid transparent;
        top: 50%;
        left: 50%;
        transform-style: preserve-3d;
    }
    
    .loading-3d-pro-ring:nth-child(1) {
        width: 100%; height: 100%; margin-top: -50%; margin-left: -50%;
        border-top-color: #00d4ff; border-left-color: rgba(0, 212, 255, 0.3);
        animation: ringGlowPro1 2s infinite ease-in-out;
        transform: rotateX(70deg) rotateY(0deg);
    }
    
    .loading-3d-pro-ring:nth-child(2) {
        width: 80%; height: 80%; margin-top: -40%; margin-left: -40%;
        border-right-color: #00ff88; border-bottom-color: rgba(0, 255, 136, 0.3);
        animation: ringGlowPro2 2s infinite ease-in-out 0.3s;
        transform: rotateX(0deg) rotateY(70deg);
    }
    
    .loading-3d-pro-ring:nth-child(3) {
        width: 60%; height: 60%; margin-top: -30%; margin-left: -30%;
        border-bottom-color: #ff2a6d; border-right-color: rgba(255, 42, 109, 0.3);
        animation: ringGlowPro3 2s infinite ease-in-out 0.6s;
        transform: rotateX(50deg) rotateY(50deg) rotateZ(30deg);
    }
    
    .loading-3d-pro-ring:nth-child(4) {
        width: 40%; height: 40%; margin-top: -20%; margin-left: -20%;
        border-left-color: #bc13fe; border-top-color: rgba(188, 19, 254, 0.3);
        animation: ringGlowPro4 2s infinite ease-in-out 0.9s;
        transform: rotateX(30deg) rotateY(30deg) rotateZ(60deg);
    }
    
    .loading-3d-pro-center {
        position: absolute;
        width: 18px; height: 18px;
        background: radial-gradient(circle, #00d4ff, #0055ff);
        border-radius: 50%;
        top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        box-shadow: 0 0 40px rgba(0, 212, 255, 0.9), 0 0 80px rgba(0, 85, 255, 0.5), 0 0 120px rgba(0, 212, 255, 0.3);
        animation: centerPulsePro 1.5s infinite alternate;
    }
    
    .loading-3d-pro-particles {
        position: absolute;
        width: 100%; height: 100%;
        top: 0; left: 0;
    }
    
    .loading-3d-pro-particle {
        position: absolute;
        width: 3px; height: 3px;
        background: #00d4ff;
        border-radius: 50%;
        box-shadow: 0 0 6px #00d4ff;
        animation: particleFloat 2s infinite ease-in-out;
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
        0%, 100% { border-top-color: rgba(0, 212, 255, 0.3); box-shadow: 0 0 5px rgba(0, 212, 255, 0.1); }
        50% { border-top-color: #00d4ff; box-shadow: 0 0 25px rgba(0, 212, 255, 0.6); }
    }
    
    @keyframes ringGlowPro2 {
        0%, 100% { border-right-color: rgba(0, 255, 136, 0.3); box-shadow: 0 0 5px rgba(0, 255, 136, 0.1); }
        50% { border-right-color: #00ff88; box-shadow: 0 0 25px rgba(0, 255, 136, 0.6); }
    }
    
    @keyframes ringGlowPro3 {
        0%, 100% { border-bottom-color: rgba(255, 42, 109, 0.3); box-shadow: 0 0 5px rgba(255, 42, 109, 0.1); }
        50% { border-bottom-color: #ff2a6d; box-shadow: 0 0 25px rgba(255, 42, 109, 0.6); }
    }
    
    @keyframes ringGlowPro4 {
        0%, 100% { border-left-color: rgba(188, 19, 254, 0.3); box-shadow: 0 0 5px rgba(188, 19, 254, 0.1); }
        50% { border-left-color: #bc13fe; box-shadow: 0 0 25px rgba(188, 19, 254, 0.6); }
    }
    
    @keyframes centerPulsePro {
        0% { transform: translate(-50%, -50%) scale(0.8); box-shadow: 0 0 30px rgba(0, 212, 255, 0.6), 0 0 60px rgba(0, 85, 255, 0.3); }
        100% { transform: translate(-50%, -50%) scale(1.3); box-shadow: 0 0 60px rgba(0, 212, 255, 1), 0 0 120px rgba(0, 85, 255, 0.7), 0 0 180px rgba(0, 212, 255, 0.4); }
    }
    
    @keyframes particleFloat {
        0%, 100% { transform: translateY(0) scale(1); opacity: 0.3; }
        50% { transform: translateY(-15px) scale(1.8); opacity: 1; }
    }
    
    .loading-3d-pro-text {
        font-family: 'Orbitron', sans-serif;
        color: #00d4ff;
        text-shadow: 0 0 15px rgba(0, 212, 255, 0.7), 0 0 30px rgba(0, 85, 255, 0.4);
        margin-top: 25px;
        font-size: 15px;
        letter-spacing: 3px;
        animation: textGlowPro 2s infinite alternate;
    }
    
    .loading-3d-pro-sub {
        font-family: 'Rajdhani', sans-serif;
        color: #888;
        font-size: 12px;
        margin-top: 8px;
        letter-spacing: 1px;
        animation: textGlowPro 2s infinite alternate 0.5s;
    }
    
    @keyframes textGlowPro {
        0% { opacity: 0.5; }
        100% { opacity: 1; }
    }

    /* ============================================================
       RADAR CYBER-TECH
       ============================================================ */
    .radar-cyber-container {
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 15px;
        margin: 10px 0;
    }
    
    .radar-cyber-disc {
        width: 50px; height: 50px;
        position: relative;
        flex-shrink: 0;
    }
    
    .radar-cyber-disc::before {
        content: '';
        position: absolute;
        width: 100%; height: 100%;
        border: 2px solid rgba(0, 212, 255, 0.4);
        border-radius: 50%;
        top: 0; left: 0;
        animation: radarDiscPulse 2s infinite;
    }
    
    .radar-cyber-disc::after {
        content: '';
        position: absolute;
        width: 60%; height: 60%;
        border: 1px solid rgba(0, 255, 136, 0.3);
        border-radius: 50%;
        top: 20%; left: 20%;
        animation: radarDiscPulse 2s infinite 0.5s;
    }
    
    .radar-cyber-sweep {
        position: absolute;
        width: 50%; height: 2px;
        background: linear-gradient(to right, transparent, #00d4ff);
        top: 50%; left: 50%;
        transform-origin: left center;
        animation: radarSweep 2s linear infinite;
        box-shadow: 0 0 8px rgba(0, 212, 255, 0.6);
    }
    
    .radar-cyber-dot {
        position: absolute;
        width: 4px; height: 4px;
        background: #00ff88;
        border-radius: 50%;
        box-shadow: 0 0 8px #00ff88;
        animation: radarDotBlink 1.5s infinite;
    }
    
    .radar-cyber-dot:nth-child(1) { top: 15%; left: 30%; animation-delay: 0s; }
    .radar-cyber-dot:nth-child(2) { top: 60%; left: 70%; animation-delay: 0.7s; }
    .radar-cyber-dot:nth-child(3) { top: 75%; left: 20%; animation-delay: 1.4s; }
    
    @keyframes radarDiscPulse {
        0%, 100% { transform: scale(1); opacity: 0.5; }
        50% { transform: scale(1.1); opacity: 1; }
    }
    
    @keyframes radarSweep {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    
    @keyframes radarDotBlink {
        0%, 100% { opacity: 0.3; transform: scale(0.8); }
        50% { opacity: 1; transform: scale(1.5); }
    }

    /* ============================================================
       SMART ALERT CYBER GLOW
       ============================================================ */
    .alert-cyber-text {
        font-family: 'Orbitron', sans-serif;
        color: #00d4ff;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.8), 0 0 25px rgba(0, 212, 255, 0.4), 0 0 50px rgba(0, 85, 255, 0.3);
        letter-spacing: 2px;
        animation: cyberTextGlow 2s infinite alternate;
    }
    
    .alert-cyber-border {
        border: 2px solid rgba(0, 212, 255, 0.5) !important;
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.3), inset 0 0 20px rgba(0, 212, 255, 0.05) !important;
    }
    
    @keyframes cyberTextGlow {
        0% { text-shadow: 0 0 8px rgba(0, 212, 255, 0.5), 0 0 20px rgba(0, 212, 255, 0.2); }
        100% { text-shadow: 0 0 20px rgba(0, 212, 255, 1), 0 0 40px rgba(0, 212, 255, 0.6), 0 0 80px rgba(0, 85, 255, 0.4); }
    }

    /* ============================================================
       FINTECH RESULT CARDS
       ============================================================ */
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
        top: 0; left: 0;
        width: 100%; height: 2px;
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

    /* ============================================================
       GOOGLE LOGIN BUTTON STYLING
       ============================================================ */
    .google-login-wrapper {
        text-align: center;
        padding: 10px 0;
    }
    
    .google-login-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 12px;
        background: #ffffff;
        border: 2px solid #e0e0e0;
        color: #333333;
        padding: 14px 28px;
        border-radius: 12px;
        font-family: 'Orbitron', sans-serif;
        font-weight: 700;
        font-size: 13px;
        cursor: pointer;
        letter-spacing: 1px;
        width: 100%;
        transition: all 0.3s ease;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
        text-decoration: none !important;
    }
    
    .google-login-btn:hover {
        border-color: #4285F4;
        box-shadow: 0 6px 25px rgba(66, 133, 244, 0.4);
        transform: translateY(-2px);
        color: #000000;
        text-decoration: none !important;
    }
    
    .google-login-btn svg {
        width: 22px;
        height: 22px;
        flex-shrink: 0;
    }

    /* ============================================================
       MAIN STYLES
       ============================================================ */
    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 32px;
        font-weight: 700;
        background: linear-gradient(90deg, var(--electric-blue), var(--deep-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        margin: 0; padding: 0;
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

    .rajdhani-font { font-family: 'Rajdhani', sans-serif; }

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
        width: 35px !important; height: 35px !important;
        object-fit: contain !important;
        margin-bottom: 8px !important;
        filter: drop-shadow(0 0 10px #00d4ff) !important;
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

# ====================== API KEYS & KONFIGURASI ======================
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
marketaux_key = st.secrets.get("MARKETAUX_KEY") or os.getenv("MARKETAUX_KEY")

client = None
if groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception as e:
        st.sidebar.error(f"⚠️ Groq Error: {str(e)}")
else:
    st.sidebar.error("⚠️ GROQ_API_KEY NOT FOUND")

# ====================== FUNGSI DATA PASAR ======================
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
        
        # Cek Cache Supabase
        supabase_for_cache = create_client(url, key)
        res = supabase_for_cache.table("market_prices").select("*").eq("instrument", inst_name).execute()
        
        if res.data:
            cached = res.data[0]
            updated_at_str = cached.get('updated_at', '')
            
            if isinstance(updated_at_str, str) and updated_at_str:
                updated_at_str = updated_at_str.replace('Z', '+00:00')
                try:
                    updated_at = datetime.fromisoformat(updated_at_str)
                except:
                    updated_at = datetime.now(pytz.UTC) - timedelta(seconds=10)
            else:
                updated_at = datetime.now(pytz.UTC) - timedelta(seconds=10)
            
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=pytz.UTC)
            else:
                updated_at = updated_at.astimezone(pytz.UTC)
            
            now = datetime.now(pytz.UTC)
            
            # Jika data masih segar (< 3 detik), gunakan cache
            if (now - updated_at).total_seconds() < 3:
                return {
                    "price": cached.get('price', 0),
                    "change": cached.get('price', 0) * (cached.get('change_pct', 0)/100),
                    "change_pct": cached.get('change_pct', 0),
                    "source": "Cache"
                }

        # Jika Cache Basi/Kosong, Ambil Live dari yfinance
        fetch_ticker = ticker_symbol
        
        ticker = yf.Ticker(fetch_ticker)
        hist = ticker.history(period="2d")
        
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            
            # Khusus Gold/Silver, bulatkan 2 desimal
            if ticker_symbol in ["GC=F", "SI=F"]:
                price = round(price, 2)
                
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else float(hist["Open"].iloc[-1])
            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            
            # Update Cache Global di Supabase
            cache_market_price(inst_name, price, change_pct)
            
            return {
                "price": price,
                "change": price - prev_close,
                "change_pct": change_pct,
                "source": "Live"
            }
        return None
    except Exception:
        return None

def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    """Mengambil data historis dari yfinance"""
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        return df.sort_index().dropna()
    except Exception:
        return pd.DataFrame()

def add_technical_indicators(df):
    """
    Menambahkan 20+ indikator teknikal ke dataframe
    SMA, EMA, RSI, MACD, Bollinger Bands, Stochastic, ATR, ADX,
    CCI, Williams %R, MFI, TRIX, ROC, Awesome Oscillator,
    KAMA, Ichimoku, Parabolic SAR, Volume SMA, Base Line
    """
    if len(df) < 50:
        return df
    
    # Moving Averages
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=min(len(df), 200)).mean()
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    
    # RSI (14)
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
    
    # Bollinger Bands (20, 2)
    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    df["BB_Std"] = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Mid"] + (df["BB_Std"] * 2)
    df["BB_Lower"] = df["BB_Mid"] - (df["BB_Std"] * 2)
    
    # Stochastic Oscillator (14, 3)
    low_14 = df["Low"].rolling(window=14).min()
    high_14 = df["High"].rolling(window=14).max()
    df["Stoch_K"] = 100 * ((df["Close"] - low_14) / (high_14 - low_14).replace(0, 0.001))
    df["Stoch_D"] = df["Stoch_K"].rolling(window=3).mean()
    
    # ATR (14)
    high_low = df["High"] - df["Low"]
    high_cp = np.abs(df["High"] - df["Close"].shift())
    low_cp = np.abs(df["Low"] - df["Close"].shift())
    df["TR"] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()
    
    # ADX (14)
    df["UpMove"] = df["High"] - df["High"].shift()
    df["DownMove"] = df["Low"].shift() - df["Low"]
    df["+DM"] = np.where((df["UpMove"] > df["DownMove"]) & (df["UpMove"] > 0), df["UpMove"], 0)
    df["-DM"] = np.where((df["DownMove"] > df["UpMove"]) & (df["DownMove"] > 0), df["DownMove"], 0)
    df["+DI"] = 100 * (df["+DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["-DI"] = 100 * (df["-DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["DX"] = 100 * np.abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"]).replace(0, 0.001)
    df["ADX"] = df["DX"].rolling(14).mean()
    
    # CCI (20)
    df["CCI"] = ta.trend.cci(df["High"], df["Low"], df["Close"], window=20)
    
    # Williams %R (14)
    df["WPR"] = ta.momentum.williams_r(df["High"], df["Low"], df["Close"], lbp=14)
    
    # MFI (14)
    df["MFI"] = ta.volume.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], window=14)
    
    # TRIX (15)
    df["TRIX"] = ta.trend.trix(df["Close"], window=15)
    
    # ROC (12)
    df["ROC"] = ta.momentum.roc(df["Close"], window=12)
    
    # Awesome Oscillator (5, 34)
    df["AO"] = ta.momentum.awesome_oscillator(df["High"], df["Low"], window1=5, window2=34)
    
    # KAMA (10)
    df["KAMA"] = ta.momentum.kama(df["Close"], window=10, pow1=2, pow2=30)
    
    # Ichimoku Cloud
    df["Ichimoku_A"] = ta.trend.ichimoku_a(df["High"], df["Low"], window1=9, window2=26)
    df["Ichimoku_B"] = ta.trend.ichimoku_b(df["High"], df["Low"], window2=26, window3=52)
    
    # Parabolic SAR
    psar_up = ta.trend.psar_up(df["High"], df["Low"], df["Close"])
    psar_down = ta.trend.psar_down(df["High"], df["Low"], df["Close"])
    df["Parabolic_SAR"] = psar_up.fillna(psar_down)
    
    # Volume SMA (20)
    df["Vol_SMA"] = df["Volume"].rolling(window=20).mean()
    
    # Base Line (Ichimoku baseline)
    df["Base_Line"] = (df["High"].rolling(window=26).max() + df["Low"].rolling(window=26).min()) / 2
    
    return df

def get_weighted_signal(df):
    """
    Menghitung sinyal teknikal berdasarkan weighted scoring
    Return: (score, signal, reasons, bullish_count, bearish_count, neutral_count)
    """
    required_cols = ["RSI", "MACD", "Signal_Line", "SMA50", "SMA200"]
    for col in required_cols:
        if col not in df.columns:
            return 0, "WAITING DATA", ["Data indikator sedang dimuat..."], 0, 0, 100

    latest = df.iloc[-1]
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    reasons = []
    
    # 1. RSI (14)
    rsi_val = latest["RSI"]
    if rsi_val < 30:
        bullish_count += 1
        reasons.append(f"RSI Oversold ({rsi_val:.2f})")
    elif rsi_val > 70:
        bearish_count += 1
        reasons.append(f"RSI Overbought ({rsi_val:.2f})")
    else:
        neutral_count += 1
        reasons.append(f"RSI Neutral ({rsi_val:.2f})")
    
    # 2. MACD
    if latest["MACD"] > latest["Signal_Line"]:
        bullish_count += 1
        reasons.append("MACD Bullish Cross")
    else:
        bearish_count += 1
        reasons.append("MACD Bearish Cross")
    
    # 3. SMA 50
    if latest["Close"] > latest["SMA50"]:
        bullish_count += 1
        reasons.append("Price > SMA 50 (Bullish)")
    else:
        bearish_count += 1
        reasons.append("Price < SMA 50 (Bearish)")

    # 4. SMA 200
    if latest["Close"] > latest["SMA200"]:
        bullish_count += 1
        reasons.append("Price > SMA 200 (Long-term Bullish)")
    else:
        bearish_count += 1
        reasons.append("Price < SMA 200 (Long-term Bearish)")
    
    # Hitung score
    total = bullish_count + bearish_count + neutral_count
    score = (bullish_count / total) * 100 if total > 0 else 50
    
    # Tentukan sinyal
    if score > 70:
        signal = "STRONG BUY"
    elif score > 55:
        signal = "BUY"
    elif score < 30:
        signal = "STRONG SELL"
    elif score < 45:
        signal = "SELL"
    else:
        signal = "NEUTRAL"
    
    return score, signal, reasons, bullish_count, bearish_count, neutral_count

# ====================== FUNGSI AI ======================
def get_groq_response(question, context=""):
    """Chatbot AI menggunakan Llama 3.3 70B via Groq"""
    if not client:
        return "⚠️ Chatbot Inactive - Groq API Key not configured"
    
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
    1. Membantu user menganalisis data trading dan berita.
    2. Berikan level ENTRY, STOP LOSS, dan TAKE PROFIT yang spesifik.
    3. Jawab dengan singkat, padat, dan teknis.
    4. JANGAN menyarankan perubahan kode website.
    5. Konteks: {context}
    """
    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            model=MODEL_NAME,
            temperature=0.7,
            max_tokens=1024,
        )
        st.session_state.daily_chatbot_count += 1
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Error: {str(e)}"

def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    """
    AeroVulpis Sentinel PRO - Hermes 3 405B + Qwen 2 72B via OpenRouter
    Dengan backup model jika primary limit
    """
    openrouter_api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    
    if not openrouter_api_key:
        return "⚠️ OpenRouter API Key tidak ditemukan. Tambahkan OPENROUTER_API_KEY di secrets."
    
    # Cek cache dulu (hemat API)
    cached = get_cached_ai_analysis(asset_name, "sentinel")
    if cached:
        return cached + "\n\n*[Data dari cache, diperbarui < 5 menit yang lalu]*"
    
    # Cek limit harian
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"⚠️ {t['limit_reached']} ({st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']})"
    
    # Model Utama & Pendamping
    PRIMARY_MODEL = 'nousresearch/hermes-3-llama-3.1-405b'
    COMPANION_MODEL = 'qwen/qwen-2-72b-instruct'
    
    # Model Cadangan
    BACKUP_MODELS = [
        'deepseek/deepseek-chat',
        'minimax/minimax-01',
        'google/gemini-flash-1.5'
    ]
    
    latest = df.iloc[-1]
    price = market_data['price']
    
    # Ambil berita untuk konteks fundamental
    news_list, _ = get_news_data(asset_name, max_articles=5)
    if news_list:
        news_context = "\n".join([f"- {n['title']} ({n['source']})" for n in news_list])
    else:
        news_context = "Tidak ada berita terbaru."
    
    # Prompt untuk analisis
    prompt = f"""
    Anda adalah AeroVulpis Sentinel Intelligence, sistem AI Pro tingkat lanjut (AeroVulpis Core V3.4).
    Tugas Anda adalah memberikan analisis institusional mendalam untuk {asset_name}.
    
    INFO DASAR:
    Instrumen: {asset_name}
    Tanggal: {datetime.now().strftime('%d %B %Y')}
    Harga saat ini: {price:,.4f}
    
    DATA PASAR TEKNIS:
    - Sinyal Teknis: {signal}
    - RSI (14): {latest.get('RSI', 0):.2f}
    - MACD: {latest.get('MACD', 0):.4f}
    - ATR (14): {latest.get('ATR', 0):.4f}
    - ADX (14): {latest.get('ADX', 0):.2f}
    - Stochastic K: {latest.get('Stoch_K', 0):.2f}
    - Bollinger Upper: {latest.get('BB_Upper', 0):.4f}
    - Bollinger Lower: {latest.get('BB_Lower', 0):.4f}
    - Alasan Teknis: {", ".join(reasons)}
    
    BERITA & FUNDAMENTAL:
    {news_context}
    
    STRUKTUR OUTPUT (WAJIB):
    
    🔮 SENTINEL INTELLIGENCE REPORT
    
    📊 KEY LEVELS:
    Support: [2-3 level + alasan singkat]
    Resistance: [2-3 level + alasan singkat]
    
    🌍 FUNDAMENTAL INSIGHT:
    [Ringkas faktor utama yang mempengaruhi instrumen ini saat ini (suku bunga, inflasi, geopolitik)]
    
    📈 TRADE SCENARIOS:
    
    🟢 Bullish:
    - Entry: [level]
    - Target: [level]
    - Stop Loss: [level]
    - R:R: [ratio]
    
    🔴 Bearish:
    - Entry: [level]
    - Target: [level]
    - Stop Loss: [level]
    - R:R: [ratio]
    
    ⚡ FINAL VERDICT:
    [Kesimpulan netral (Buy/Sell/Wait) + risiko utama]
    
    ATURAN:
    - Bahasa Indonesia jelas dan ringkas
    - Total maksimal 320 kata
    - Seimbang antara bullish dan bearish
    """
    
    def call_openrouter(model_name, system_msg):
        """Panggil OpenRouter API"""
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
        except Exception:
            return None
    
    # 1. Coba Model Utama (Hermes 405B)
    analysis = call_openrouter(PRIMARY_MODEL, "Anda adalah AeroVulpis Sentinel Pro Intelligence (Hermes 405B).")
    
    # 2. Jika Sukses, Tambahkan Detail dari Model Pendamping (Qwen)
    if analysis:
        companion_detail = call_openrouter(COMPANION_MODEL, "Berikan detail teknis tambahan untuk analisis trading ini.")
        if companion_detail:
            analysis += "\n\n---\n**🔬 SENTINEL COMPANION (Qwen 2 72B) ADDITIONAL INSIGHTS:**\n" + companion_detail
    
    # 3. Jika Utama Gagal, Coba Model Cadangan
    if not analysis:
        for model in BACKUP_MODELS:
            analysis = call_openrouter(model, "Anda adalah AeroVulpis Sentinel Backup Intelligence.")
            if analysis:
                analysis = f"⚠️ **[SYSTEM] PRIMARY MODELS LIMIT REACHED. SWITCHING TO BACKUP ({model})**\n\n" + analysis
                break
    
    if not analysis:
        return "⚠️ Sentinel Error: Semua model AI (Utama, Pendamping, & Cadangan) sedang sibuk atau limit habis. Coba lagi nanti."
    
    # Update counter & cache
    st.session_state.daily_analysis_count += 1
    cache_ai_analysis(asset_name, "sentinel", analysis)
    
    return analysis

def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    """
    Generate Deep Analysis menggunakan Llama 3.3 70B via Groq
    Untuk analisis teknikal mendalam dengan entry, SL, TP
    """
    if not client:
        return "⚠️ Deep Analysis Inactive - Groq API Key not configured"
    
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
    - RSI (14): {latest.get('RSI', 0):.2f}
    - MACD: {latest.get('MACD', 0):.4f} (Signal: {latest.get('Signal_Line', 0):.4f})
    - SMA 50: {latest.get('SMA50', 0):.4f}
    - SMA 200: {latest.get('SMA200', 0):.4f}
    - ATR (14): {latest.get('ATR', 0):.4f}
    - Stochastic K: {latest.get('Stoch_K', 0):.2f}
    - ADX (14): {latest.get('ADX', 0):.2f}
    - Bollinger Bands: Upper {latest.get('BB_Upper', 0):.4f} / Lower {latest.get('BB_Lower', 0):.4f}
    - CCI (20): {latest.get('CCI', 0):.2f}
    - Volume: {df['Volume'].iloc[-1]:,.0f}
    
    ALASAN TEKNIS:
    {', '.join(reasons)}
    """
    
    system_prompt = f"""
    Anda adalah AeroVulpis Deep Analysis Engine - AI Trading Analyst Profesional.
    Waktu: {datetime.now().strftime('%d %B %Y, %H:%M:%S WIB')}
    Bahasa: {st.session_state.lang}
    
    ANDA ADALAH EXPERT DALAM:
    1. Analisis Teknikal Mendalam (Support/Resistance, Trend Analysis, Pattern Recognition)
    2. Korelasi Fundamental (The Fed, Geopolitik, Berita Pasar)
    3. Money Management & Risk-Reward Ratio
    4. Market Microstructure & Order Flow
    
    INSTRUKSI ANALISIS WAJIB:
    1. ANALISIS TEKNIKAL: Interpretasi mendalam RSI (14) dan SMA 200. Jelaskan apakah RSI menunjukkan jenuh beli/jual dan apakah harga di atas/bawah SMA 200.
    2. LEVEL ENTRY: Tentukan 2-3 level entry dengan alasan spesifik (support, breakout, retracement).
    3. STOP LOSS: Tentukan level SL berdasarkan ATR dan struktur pasar (jangan lebih dari 2% dari entry).
    4. TAKE PROFIT: Tentukan 2-3 level TP dengan risk-reward ratio minimal 1:2.
    5. RISK MANAGEMENT: Berikan ukuran posisi dan manajemen risiko optimal.
    6. SCENARIO: Jelaskan kondisi bearish dan bullish yang mungkin terjadi.
    
    FORMAT OUTPUT:
    - Gunakan markdown dan emoji
    - Maksimal 2000 karakter
    - Fokus pada actionable insights
    """
    
    user_prompt = f"""Berikan analisis teknikal mendalam dengan level entry, stop loss, dan take profit:
    
    {technical_data}
    
    WAJIB mencakup:
    1. Interpretasi RSI (14): {latest.get('RSI', 0):.2f}
    2. Posisi harga vs SMA 200: {latest.get('SMA200', 0):.4f}
    3. Level entry spesifik (2-3 pilihan)
    4. Stop loss (berdasarkan ATR: {latest.get('ATR', 0):.4f})
    5. Take profit (ratio minimal 1:2)
    6. Risk management & position sizing
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
        
        # Update counter & cache
        st.session_state.daily_analysis_count += 1
        cache_ai_analysis(asset_name, "deep", analysis)
        
        return analysis
    except Exception as e:
        return f"⚠️ Error: {str(e)}"
