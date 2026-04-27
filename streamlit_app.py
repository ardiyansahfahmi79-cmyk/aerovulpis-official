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

from dotenv import load_dotenv
load_dotenv()

# ##############################################################################
# SUPABASE CONFIGURATION
# ##############################################################################
url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]
service_role_key = st.secrets.get("supabase_service_role_key", key)

def get_supabase_client():
    """
    Mendapatkan Supabase client dengan anon key.
    Digunakan untuk semua operasi database yang mematuhi Row Level Security.
    """
    return create_client(url, key)

def get_supabase_admin():
    """
    Mendapatkan Supabase client dengan service_role key.
    Digunakan untuk operasi admin yang mem-bypass RLS,
    seperti update tier user dan aktivasi kunci lisensi.
    """
    return create_client(url, service_role_key)

# ##############################################################################
# SYSTEM LOGGING & MAINTENANCE
# ##############################################################################

def send_log(pesan):
    """
    Mencatat log aktivitas sistem ke tabel logs_aktivitas di database.
    Berguna untuk tracking penggunaan dan debugging.
    """
    try:
        supabase = get_supabase_client()
        supabase.table("logs_aktivitas").insert({"keterangan": pesan}).execute()
    except Exception:
        pass

def cleanup_logs():
    """
    Membersihkan log yang lebih lama dari 24 jam.
    Menjaga ukuran database tetap optimal.
    """
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        supabase.table("logs_aktivitas").delete().lt("created_at", cutoff).execute()
    except Exception:
        pass

def cache_market_price(symbol, price, change_pct=0.0):
    """
    Menyimpan harga pasar terbaru ke tabel market_prices.
    Menggunakan upsert: insert jika belum ada, update jika sudah ada.
    """
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
    """
    Mengambil harga terbaru dari cache di tabel market_prices.
    Return: (float) price, atau None jika tidak ditemukan.
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("market_prices").select("price").eq("instrument", symbol).execute()
        if res.data:
            return res.data[0]["price"]
    except Exception:
        pass
    return None

def get_cached_market_price_full(symbol):
    """
    Mengambil data harga lengkap dari cache.
    Digunakan oleh Smart Alert System untuk pengecekan harga.
    Return: dict dengan keys price, change_pct, updated_at.
    """
    try:
        supabase = get_supabase_client()
        res = supabase.table("market_prices").select("*").eq("instrument", symbol).execute()
        if res.data:
            return {
                "price": res.data[0].get("price", 0),
                "change_pct": res.data[0].get("change_pct", 0),
                "updated_at": res.data[0].get("updated_at", "")
            }
    except Exception:
        pass
    return None

def cleanup_old_data():
    """
    Membersihkan data market_prices yang lebih lama dari 24 jam.
    Dilakukan setiap aplikasi dijalankan untuk menjaga performa database.
    """
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now(pytz.timezone('Asia/Jakarta')) - timedelta(hours=24)).isoformat()
        supabase.table("market_prices").delete().lt("updated_at", cutoff).execute()
    except Exception:
        pass

# ##############################################################################
# USER & LICENSE MANAGEMENT
# ##############################################################################

def get_user_tier(user_id):
    """
    Memeriksa tier langganan user dari tabel user_tiers.
    Jika tier sudah expired, otomatis mengembalikan ke 'free'.
    
    Parameter:
    - user_id (str): ID unik user dari Google OAuth
    
    Return:
    - (tier, expired_at): tuple berisi tier aktif dan tanggal expired
    - ('free', None): jika user tidak ditemukan atau tier expired
    """
    if not user_id:
        return "free", None
    
    try:
        supabase = get_supabase_client()
        res = supabase.table("user_tiers").select("tier, expired_at").eq("user_id", user_id).execute()
        
        if res.data:
            tier = res.data[0]["tier"]
            expired_at = res.data[0].get("expired_at")
            
            # Cek apakah tier sudah expired
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
    Validasi dan aktivasi kunci lisensi premium.
    
    Flow:
    1. Cari kunci di tabel activation_keys (is_used = false)
    2. Ambil data tier dan durasi dari kunci
    3. Update/Create user_tiers dengan tier baru dan expired date
    4. Tandai kunci sebagai sudah digunakan
    
    Parameter:
    - user_id (str): ID user yang mengaktivasi
    - key_code (str): Kode aktivasi (format: XXXX-XXXX-XXXX-XXXX)
    
    Return:
    - (success, message): tuple boolean dan pesan status
    """
    if not user_id or not key_code:
        return False, "IDENTITY VERIFICATION REQUIRED"
    
    try:
        supabase = get_supabase_client()
        
        # Cari kunci yang valid dan belum digunakan
        res = supabase.table("activation_keys").select("*")\
            .eq("key_code", key_code.upper().strip())\
            .eq("is_used", False)\
            .execute()
        
        if not res.data:
            return False, "INVALID OR EXPIRED LICENSE KEY"
        
        key_data = res.data[0]
        tier = key_data.get("tier", "monthly")
        duration_days = key_data.get("duration_days", 30)
        
        # Hitung tanggal expired dalam UTC
        expired_at = (datetime.now(pytz.UTC) + timedelta(days=duration_days)).isoformat()
        
        # Gunakan service_role untuk bypass RLS
        supabase_admin = get_supabase_admin()
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
        }).eq("key_code", key_code.upper().strip()).execute()
        
        return True, f"ACCESS GRANTED | TIER: {tier.upper()} | VALID UNTIL: {expired_at[:10]}"
    
    except Exception as e:
        return False, f"SYSTEM ERROR: {str(e)}"

def sync_user_to_supabase(user_id, email, name, avatar=""):
    """
    Sinkronisasi data user dari Google OAuth ke tabel users.
    
    - Jika user sudah terdaftar: update email, nama, avatar, dan last_login
    - Jika user baru: insert data user + beri tier free
    
    Parameter:
    - user_id (str): ID unik dari Google
    - email (str): Email Google user
    - name (str): Nama lengkap user
    - avatar (str): URL foto profil (opsional)
    """
    try:
        supabase = get_supabase_client()
        
        # Cek apakah user sudah terdaftar
        existing = supabase.table("users").select("id").eq("id", user_id).execute()
        
        if existing.data:
            # User sudah ada - update data
            supabase.table("users").update({
                "email": email,
                "name": name,
                "avatar": avatar,
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).eq("id", user_id).execute()
        else:
            # User baru - insert data
            supabase.table("users").insert({
                "id": user_id,
                "email": email,
                "name": name,
                "avatar": avatar,
                "created_at": datetime.now(pytz.UTC).isoformat(),
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).execute()
            
            # Berikan tier free untuk user baru
            supabase.table("user_tiers").insert({
                "user_id": user_id,
                "tier": "free",
                "activated_at": datetime.now(pytz.UTC).isoformat()
            }).execute()
    except Exception:
        pass

# ##############################################################################
# AI ANALYSIS CACHE SYSTEM
# ##############################################################################

def get_cached_ai_analysis(asset_name, timeframe):
    """
    Mengambil cache analisis AI dari database.
    Cache berlaku 5 menit untuk menghemat pemakaian API key.
    
    Parameter:
    - asset_name (str): Nama instrumen (contoh: XAUUSD, EURUSD)
    - timeframe (str): Tipe analisis ('sentinel' atau 'deep')
    
    Return:
    - (str) Hasil analisis, atau None jika cache expired/tidak ada
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
    Menyimpan hasil analisis AI ke cache.
    Memungkinkan user lain mendapatkan hasil yang sama tanpa memanggil API lagi.
    
    Parameter:
    - asset_name (str): Nama instrumen
    - timeframe (str): Tipe analisis
    - analysis (str): Hasil analisis dari AI
    """
    try:
        supabase = get_supabase_client()
        supabase.table("ai_analysis_cache").insert({
            "asset_name": asset_name,
            "timeframe": timeframe,
            "analysis": analysis,
            "created_at": datetime.now(pytz.UTC).isoformat()
        }).execute()
    except Exception:
        pass

# ##############################################################################
# GOOGLE OAUTH AUTHENTICATION
# ##############################################################################

def handle_google_oauth():
    """
    Menangani autentikasi Google OAuth via Supabase Auth.
    
    Alur:
    1. Cek apakah URL memiliki parameter 'code' (callback dari Google)
    2. Exchange authorization code untuk mendapatkan session
    3. Sinkronisasi data user ke database
    4. Simpan informasi user ke session state
    5. Cek existing session untuk user yang sudah login
    
    KONFIGURASI YANG DIPERLUKAN:
    - Google Cloud Console:
      Authorized JavaScript origins: https://bqdugkmmnbxlftuxqtdg.supabase.co
      Authorized redirect URIs: https://bqdugkmmnbxlftuxqtdg.supabase.co/auth/v1/callback
    - Supabase Dashboard → Authentication → Providers → Google:
      Enable = ON, isi Client ID & Secret, Skip nonce checks = OFF
    - Supabase Dashboard → Authentication → URL Configuration:
      Site URL = https://[app].streamlit.app
    """
    # Handle OAuth callback (user kembali dari Google)
    query_params = st.query_params
    
    if "code" in query_params:
        code = query_params["code"]
        try:
            supabase = get_supabase_client()
            
            # Exchange authorization code untuk session
            auth_response = supabase.auth.exchange_code_for_session({
                "auth_code": code
            })
            
            if auth_response and auth_response.user:
                user = auth_response.user
                user_id = user.id
                user_email = user.email or ""
                user_name = user.user_metadata.get("full_name") or \
                           user.user_metadata.get("name") or \
                           (user_email.split("@")[0] if user_email else "USER")
                user_avatar = user.user_metadata.get("avatar_url") or \
                             user.user_metadata.get("picture") or ""
                
                # Sinkronisasi ke database
                sync_user_to_supabase(user_id, user_email, user_name, user_avatar)
                
                # Simpan ke session state
                st.session_state.auth_session = auth_response.session.access_token if auth_response.session else "active"
                st.session_state.user_id = user_id
                st.session_state.user_name = user_name
                st.session_state.user_email = user_email
                st.session_state.user_avatar = user_avatar
                
                # Ambil tier user
                st.session_state.user_tier, _ = get_user_tier(user_id)
                
                # Bersihkan URL dan refresh
                st.query_params.clear()
                send_log(f"AUTH: {user_name} ({user_email})")
                st.rerun()
                
        except Exception as e:
            st.sidebar.error(f"AUTHENTICATION ERROR: {str(e)}")
            send_log(f"AUTH ERROR: {str(e)}")
    
    # Cek existing session (user sudah login sebelumnya)
    if not st.session_state.get("auth_session"):
        try:
            supabase = get_supabase_client()
            session = supabase.auth.get_session()
            if session and session.user:
                user = session.user
                st.session_state.auth_session = session.access_token
                st.session_state.user_id = user.id
                st.session_state.user_name = user.user_metadata.get("full_name",
                    user.email.split("@")[0] if user.email else "USER")
                st.session_state.user_email = user.email or ""
                st.session_state.user_avatar = user.user_metadata.get("avatar_url", "")
                st.session_state.user_tier, _ = get_user_tier(user.id)
        except Exception:
            pass

# ##############################################################################
# IC MARKET PRICE FETCH (HARGA AKURAT DARI BROKER)
# ##############################################################################

def get_icmarket_price(symbol):
    """
    Mengambil harga real-time dari IC Market melalui cTrader API.
    
    Harga diambil langsung dari broker dengan spread yang akurat.
    
    Format harga per instrumen:
    - XAUUSD (Gold):     2 desimal (contoh: 4756.00)
    - XAGUSD (Silver):   2 desimal (contoh: 34.50)
    - EURUSD (Forex):    4 desimal (contoh: 1.0850)
    - BTCUSD (Bitcoin):  2 desimal (contoh: 67250.00)
    
    Parameter:
    - symbol (str): Kode instrumen (XAUUSD, EURUSD, dll)
    
    Return:
    - dict: {price, bid, ask, spread, source} atau None jika gagal
    """
    # Mapping kode instrumen ke ID cTrader
    ctrader_map = {
        "XAUUSD": "1",
        "XAGUSD": "2",
        "EURUSD": "3",
        "GBPUSD": "4",
        "USDJPY": "5",
        "AUDUSD": "6",
        "USDCHF": "7",
        "BTCUSD": "100",
        "ETHUSD": "101",
        "SOLUSD": "102",
        "XRPUSD": "103",
        "BNBUSD": "104",
    }
    
    symbol_id = ctrader_map.get(symbol)
    if not symbol_id:
        return None
    
    # Ambil kredensial dari secrets atau environment variables
    ctrader_client_id = st.secrets.get("CTRADER_CLIENT_ID") or os.getenv("CTRADER_CLIENT_ID")
    ctrader_client_secret = st.secrets.get("CTRADER_CLIENT_SECRET") or os.getenv("CTRADER_CLIENT_SECRET")
    
    if not ctrader_client_id or not ctrader_client_secret:
        return None
    
    try:
        # Panggil cTrader API
        response = requests.get(
            f"https://api.ctrader.com/v1/symbols/{symbol_id}/price",
            headers={
                "Authorization": f"Bearer {ctrader_client_id}:{ctrader_client_secret}",
                "Content-Type": "application/json"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            bid = float(data.get("bid", 0))
            ask = float(data.get("ask", 0))
            mid_price = (bid + ask) / 2
            
            # Format harga berdasarkan jenis instrumen
            if symbol in ["XAUUSD"]:
                formatted_price = round(mid_price, 2)
            elif symbol in ["XAGUSD"]:
                formatted_price = round(mid_price, 2)
            elif symbol in ["BTCUSD", "ETHUSD"]:
                formatted_price = round(mid_price, 2)
            elif symbol in ["SOLUSD", "XRPUSD", "BNBUSD"]:
                formatted_price = round(mid_price, 4)
            else:
                formatted_price = round(mid_price, 4)
            
            # Hitung spread
            spread = round(ask - bid, 5)
            
            return {
                "price": formatted_price,
                "bid": bid,
                "ask": ask,
                "spread": spread,
                "source": "ICMARKET"
            }
    except Exception:
        pass
    
    return None

def format_price_display(price, instrument_name):
    """
    Format tampilan harga sesuai jenis instrumen.
    
    Aturan format:
    - XAUUSD (Gold):      4,756.00  (3 digit di depan koma, 2 digit desimal)
    - XAGUSD (Silver):       34.50
    - EURUSD (Forex):      1.0850   (4 digit desimal)
    - BTCUSD (Bitcoin): 67,250.00
    - S&P 500 (Indeks): 5,280.50
    - Saham:               175.25
    
    Parameter:
    - price (float): Harga numerik
    - instrument_name (str): Nama instrumen
    
    Return:
    - (str) Harga yang sudah diformat
    """
    name_upper = str(instrument_name).upper() if instrument_name else ""
    
    # Gold & Silver
    if "XAU" in name_upper or "GOLD" in name_upper:
        return f"{price:,.2f}"
    elif "XAG" in name_upper or "SILVER" in name_upper:
        return f"{price:,.2f}"
    
    # Major Cryptocurrency
    elif "BTC" in name_upper or "BITCOIN" in name_upper:
        return f"{price:,.2f}"
    elif "ETH" in name_upper or "ETHEREUM" in name_upper:
        return f"{price:,.2f}"
    
    # Alternative Cryptocurrency
    elif any(c in name_upper for c in ["SOL", "BNB", "XRP"]):
        return f"{price:,.2f}"
    
    # Forex Pairs
    elif any(fx in name_upper for fx in ["EUR", "GBP", "CHF", "JPY", "AUD", "NZD", "CAD"]):
        return f"{price:,.4f}".rstrip('0').rstrip('.')
    
    # Stock Indices
    elif any(idx in name_upper for idx in ["NASDAQ", "S&P", "DOW", "DAX", "IHSG", "SP500"]):
        return f"{price:,.2f}"
    
    # Commodities
    elif any(cmd in name_upper for cmd in ["OIL", "WTI", "CRUDE", "GAS", "COPPER", "PALLADIUM", "PLATINUM"]):
        return f"{price:,.2f}"
    
    # Default formatting
    else:
        if price >= 1000:
            return f"{price:,.2f}"
        elif price >= 1:
            return f"{price:,.2f}"
        else:
            return f"{price:,.4f}".rstrip('0').rstrip('.')

# ##############################################################################
# APPLICATION CONFIGURATION
# ##############################################################################

st.set_page_config(
    layout="wide",
    page_title="AEROVULPIS V3.5",
    page_icon="◈",
    initial_sidebar_state="expanded"
)

# Jalankan maintenance rutin
cleanup_logs()
cleanup_old_data()
send_log("AEROVULPIS V3.5 SYSTEM ONLINE")

# ##############################################################################
# SESSION STATE INITIALIZATION
# ##############################################################################

# --- Bahasa ---
if "lang" not in st.session_state:
    st.session_state.lang = "ID"

# --- Cache Analisis AI ---
if "cached_analysis" not in st.session_state:
    st.session_state.cached_analysis = {}

# --- User & Authentication State ---
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

# --- Usage Limits Tracking ---
if "daily_analysis_count" not in st.session_state:
    st.session_state.daily_analysis_count = 0
if "daily_chatbot_count" not in st.session_state:
    st.session_state.daily_chatbot_count = 0
if "last_reset_date" not in st.session_state:
    st.session_state.last_reset_date = datetime.now().date()

# --- Feature States ---
if "show_activation" not in st.session_state:
    st.session_state.show_activation = False
if "activation_result" not in st.session_state:
    st.session_state.activation_result = None
if "sentinel_analysis" not in st.session_state:
    st.session_state.sentinel_analysis = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_alerts" not in st.session_state:
    st.session_state.active_alerts = []
if "last_news_fetch" not in st.session_state:
    st.session_state.last_news_fetch = {}

# Reset daily limits jika sudah berganti hari
if st.session_state.last_reset_date < datetime.now().date():
    st.session_state.daily_analysis_count = 0
    st.session_state.daily_chatbot_count = 0
    st.session_state.last_reset_date = datetime.now().date()

# Handle Google OAuth Redirect
handle_google_oauth()

# ##############################################################################
# TIER LIMITS CONFIGURATION (HEMAT API UNTUK 3000 USER / 500 DAU)
# ##############################################################################
LIMITS = {
    "free": {
        "analysis_per_day": 5,
        "chatbot_per_day": 20
    },
    "trial": {
        "analysis_per_day": 10,
        "chatbot_per_day": 50
    },
    "weekly": {
        "analysis_per_day": 20,
        "chatbot_per_day": 100
    },
    "monthly": {
        "analysis_per_day": 50,
        "chatbot_per_day": 200
    },
    "six_months": {
        "analysis_per_day": 100,
        "chatbot_per_day": 500
    },
    "yearly": {
        "analysis_per_day": 999999,
        "chatbot_per_day": 999999
    }
}

# ##############################################################################
# LANGUAGE DICTIONARY (BAHASA INDONESIA & ENGLISH)
# ##############################################################################
translations = {
    "ID": {
        "control_center": "CONTROL CENTER",
        "category": "KATEGORI ASET",
        "asset": "PILIH INSTRUMEN",
        "timeframe": "TIMEFRAME",
        "navigation": "NAVIGATION SYSTEM",
        "live_price": "LIVE PRICE",
        "signal": "SIGNAL",
        "rsi": "RSI",
        "atr": "ATR",
        "refresh": "REFRESH DATA",
        "ai_analysis": "AI ANALYSIS",
        "generate_ai": "GENERATE DEEP ANALYSIS",
        "market_sessions": "MARKET SESSIONS",
        "market_news": "MARKET NEWS",
        "risk_mgmt": "RISK MANAGEMENT",
        "settings": "SETTINGS",
        "clear_cache": "CLEAR SYSTEM CACHE",
        "lang_select": "LANGUAGE",
        "recommendation": "CURRENT RECOMMENDATION",
        "no_news": "NO NEWS AVAILABLE",
        "limit_reached": "DAILY LIMIT REACHED",
        "daily_limit": "DAILY USAGE",
        "upgrade_premium": "UPGRADE TIER",
        "login_google": "AUTHENTICATE WITH GOOGLE",
        "logout": "TERMINATE SESSION",
        "activate_key": "ACTIVATE LICENSE KEY",
        "enter_key": "ENTER ACTIVATION KEY",
        "activate_btn": "VALIDATE & ACTIVATE",
        "welcome": "WELCOME",
        "tier_free": "FREE TIER",
        "processing": "PROCESSING AUTHENTICATION",
        "activation_success": "ACTIVATION SUCCESSFUL",
        "activation_failed": "ACTIVATION FAILED",
        "sign_in_prompt": "IDENTITY VERIFICATION REQUIRED",
        "sign_in_desc": "Authenticate to access the AeroVulpis System",
        "sentinel_btn": "INITIATE DEEP ANALYSIS PRO",
        "risk_simulate": "EXECUTE SIMULATION",
        "risk_weekly": "WEEKLY",
        "risk_monthly": "MONTHLY",
        "risk_yearly": "YEARLY",
        "risk_net": "NET P/L",
        "risk_return": "RETURN %",
        "risk_balance": "FINAL BALANCE",
        "risk_initial": "INITIAL",
        "risk_after": "AFTER",
        "risk_params": "RISK PARAMETERS",
        "risk_per_trade": "RISK PER TRADE",
        "risk_reward_trade": "REWARD PER TRADE",
        "risk_max_loss": "MAX DAILY LOSS",
        "risk_max_profit": "MAX DAILY PROFIT",
        "risk_summary": "BALANCE PROJECTION",
        "funding_details": "ACCOUNT CONFIGURATION",
        "account_balance": "ACCOUNT BALANCE",
        "rr_simulator": "RISK-REWARD MATRIX",
        "wins": "WINNING TRADES",
        "losses": "LOSING TRADES",
        "daily_risk": "DAILY RISK LIMITS",
        "help_support": "SYSTEM DOCUMENTATION",
        "sentinel_title": "SENTINEL PRO INTELLIGENCE",
        "sentinel_ai_status": "AEROVULPIS SENTINEL CORE ACTIVE",
        "market_status": "MARKET STATUS: ACTIVE",
        "sentinel_intel": "INTELLIGENCE REPORT",
        "sentinel_placeholder": "Initialize Deep Analysis Pro to generate intelligence report",
        "news_filter": "CATEGORY FILTER",
        "news_updated": "Live feed from global financial networks | Updated hourly",
        "economic_title": "GLOBAL ECONOMIC SCANNER",
        "economic_subtitle": "Real-Time High Impact Event Detection Active",
        "alert_title": "SMART ALERT CENTER",
        "alert_subtitle": "AEROVULPIS TERMINAL V3.5",
        "alert_online": "SYSTEM ONLINE",
        "alert_sync": "MONITORING ACTIVE",
        "dashboard_title": "LIVE DASHBOARD",
        "signal_title": "TECHNICAL SIGNAL MATRIX",
        "chatbot_title": "NEURAL ASSISTANT",
        "risk_title": "RISK FRAMEWORK",
        "settings_title": "SYSTEM SETTINGS",
        "help_title": "SYSTEM DOCUMENTATION",
        "projection_title": "PROJECTED PERFORMANCE",
        "tier_label": "LICENSE TIER",
        "daily_usage_label": "DAILY USAGE MONITOR",
        "user_id_label": "USER ID",
        "user_email_label": "EMAIL",
        "license_activation": "LICENSE ACTIVATION",
        "enter_license_key": "ENTER LICENSE KEY",
        "license_placeholder": "XXXX-XXXX-XXXX-XXXX",
        "key_activate_button": "VALIDATE & ACTIVATE LICENSE",
        "force_refresh": "FORCE REFRESH"
    },
    "EN": {
        "control_center": "CONTROL CENTER",
        "category": "ASSET CATEGORY",
        "asset": "SELECT INSTRUMENT",
        "timeframe": "TIMEFRAME",
        "navigation": "NAVIGATION SYSTEM",
        "live_price": "LIVE PRICE",
        "signal": "SIGNAL",
        "rsi": "RSI",
        "atr": "ATR",
        "refresh": "REFRESH DATA",
        "ai_analysis": "AI ANALYSIS",
        "generate_ai": "GENERATE DEEP ANALYSIS",
        "market_sessions": "MARKET SESSIONS",
        "market_news": "MARKET NEWS",
        "risk_mgmt": "RISK MANAGEMENT",
        "settings": "SETTINGS",
        "clear_cache": "CLEAR SYSTEM CACHE",
        "lang_select": "LANGUAGE",
        "recommendation": "CURRENT RECOMMENDATION",
        "no_news": "NO NEWS AVAILABLE",
        "limit_reached": "DAILY LIMIT REACHED",
        "daily_limit": "DAILY USAGE",
        "upgrade_premium": "UPGRADE TIER",
        "login_google": "AUTHENTICATE WITH GOOGLE",
        "logout": "TERMINATE SESSION",
        "activate_key": "ACTIVATE LICENSE KEY",
        "enter_key": "ENTER ACTIVATION KEY",
        "activate_btn": "VALIDATE & ACTIVATE",
        "welcome": "WELCOME",
        "tier_free": "FREE TIER",
        "processing": "PROCESSING AUTHENTICATION",
        "activation_success": "ACTIVATION SUCCESSFUL",
        "activation_failed": "ACTIVATION FAILED",
        "sign_in_prompt": "IDENTITY VERIFICATION REQUIRED",
        "sign_in_desc": "Authenticate to access the AeroVulpis System",
        "sentinel_btn": "INITIATE DEEP ANALYSIS PRO",
        "risk_simulate": "EXECUTE SIMULATION",
        "risk_weekly": "WEEKLY",
        "risk_monthly": "MONTHLY",
        "risk_yearly": "YEARLY",
        "risk_net": "NET P/L",
        "risk_return": "RETURN %",
        "risk_balance": "FINAL BALANCE",
        "risk_initial": "INITIAL",
        "risk_after": "AFTER",
        "risk_params": "RISK PARAMETERS",
        "risk_per_trade": "RISK PER TRADE",
        "risk_reward_trade": "REWARD PER TRADE",
        "risk_max_loss": "MAX DAILY LOSS",
        "risk_max_profit": "MAX DAILY PROFIT",
        "risk_summary": "BALANCE PROJECTION",
        "funding_details": "ACCOUNT CONFIGURATION",
        "account_balance": "ACCOUNT BALANCE",
        "rr_simulator": "RISK-REWARD MATRIX",
        "wins": "WINNING TRADES",
        "losses": "LOSING TRADES",
        "daily_risk": "DAILY RISK LIMITS",
        "help_support": "SYSTEM DOCUMENTATION",
        "sentinel_title": "SENTINEL PRO INTELLIGENCE",
        "sentinel_ai_status": "AEROVULPIS SENTINEL CORE ACTIVE",
        "market_status": "MARKET STATUS: ACTIVE",
        "sentinel_intel": "INTELLIGENCE REPORT",
        "sentinel_placeholder": "Initialize Deep Analysis Pro to generate intelligence report",
        "news_filter": "CATEGORY FILTER",
        "news_updated": "Live feed from global financial networks | Updated hourly",
        "economic_title": "GLOBAL ECONOMIC SCANNER",
        "economic_subtitle": "Real-Time High Impact Event Detection Active",
        "alert_title": "SMART ALERT CENTER",
        "alert_subtitle": "AEROVULPIS TERMINAL V3.5",
        "alert_online": "SYSTEM ONLINE",
        "alert_sync": "MONITORING ACTIVE",
        "dashboard_title": "LIVE DASHBOARD",
        "signal_title": "TECHNICAL SIGNAL MATRIX",
        "chatbot_title": "NEURAL ASSISTANT",
        "risk_title": "RISK FRAMEWORK",
        "settings_title": "SYSTEM SETTINGS",
        "help_title": "SYSTEM DOCUMENTATION",
        "projection_title": "PROJECTED PERFORMANCE",
        "tier_label": "LICENSE TIER",
        "daily_usage_label": "DAILY USAGE MONITOR",
        "user_id_label": "USER ID",
        "user_email_label": "EMAIL",
        "license_activation": "LICENSE ACTIVATION",
        "enter_license_key": "ENTER LICENSE KEY",
        "license_placeholder": "XXXX-XXXX-XXXX-XXXX",
        "key_activate_button": "VALIDATE & ACTIVATE LICENSE",
        "force_refresh": "FORCE REFRESH"
    }
}

# Mengambil terjemahan sesuai bahasa yang dipilih
t = translations[st.session_state.lang]

# ##############################################################################
# CYBER-TECH DIGITAL FINTECH CSS
# ##############################################################################

st.markdown("""
<style>
    /* ==================== FONT IMPORTS ==================== */
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Rajdhani:wght@300;400;500;600;700&family=Share+Tech+Mono&display=swap');

    /* ==================== ROOT VARIABLES ==================== */
    :root {
        --neon-cyan: #00d4ff;
        --neon-green: #00ff88;
        --neon-red: #ff2a6d;
        --deep-blue: #0055ff;
        --dark-bg: #020408;
        --card-bg: rgba(10, 14, 23, 0.85);
        --glass-border: rgba(0, 212, 255, 0.12);
        --text-primary: #dce4f0;
        --text-secondary: #8899bb;
        --text-muted: #556680;
    }

    /* ==================== GLOBAL RESET ==================== */
    * {
        font-family: 'Rajdhani', sans-serif;
    }

    /* ==================== APP BACKGROUND ==================== */
    .stApp {
        background: radial-gradient(ellipse at 15% 45%, #0a1a30 0%, #030810 35%, #010408 100%);
        color: var(--text-primary);
    }

    /* ==================== GLASS CARDS ==================== */
    .glass-card {
        background: var(--card-bg);
        backdrop-filter: blur(24px);
        -webkit-backdrop-filter: blur(24px);
        border: 1px solid var(--glass-border);
        border-radius: 6px;
        padding: 20px;
        box-shadow: 0 4px 32px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255,255,255,0.02);
        margin-bottom: 6px;
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }

    .glass-card:hover {
        border-color: rgba(0, 212, 255, 0.25);
        box-shadow: 0 6px 36px rgba(0, 0, 0, 0.7), 0 0 16px rgba(0, 212, 255, 0.04);
    }

    /* ==================== SESSION CONTAINER ==================== */
    .session-container {
        border: 1px solid rgba(0, 212, 255, 0.2);
        border-radius: 6px;
        padding: 28px;
        background: rgba(0, 18, 36, 0.55);
        box-shadow: 0 0 48px rgba(0, 212, 255, 0.05);
        margin-bottom: 24px;
    }

    /* ==================== NEWS CARDS ==================== */
    .news-card {
        background: rgba(0, 212, 255, 0.015);
        border: 1px solid rgba(0, 212, 255, 0.06);
        padding: 20px;
        border-radius: 4px;
        margin-bottom: 10px;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
    }

    .news-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 2px;
        height: 100%;
        background: linear-gradient(180deg, var(--neon-cyan) 0%, transparent 100%);
        opacity: 0.4;
    }

    .news-card:hover {
        background: rgba(0, 212, 255, 0.03);
        border-color: rgba(0, 212, 255, 0.2);
        box-shadow: 0 0 20px rgba(0, 212, 255, 0.04);
        transform: translateX(2px);
    }

    /* ==================== HEADER & LOGO ==================== */
    .main-title-container {
        text-align: center;
        margin-bottom: 0;
        padding-bottom: 0;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }

    .main-logo-container {
        position: relative;
        display: inline-block;
        animation: floatLogo 5s infinite ease-in-out;
        padding: 6px 0;
        margin-bottom: -16px;
        background: transparent !important;
        perspective: 1200px;
        overflow: visible !important;
    }

    .custom-logo {
        width: 88px;
        filter: drop-shadow(0 0 22px rgba(0, 212, 255, 0.45));
        background-color: transparent !important;
        animation: rotateLogo3D 15s infinite linear;
        transform-style: preserve-3d;
        position: relative;
        z-index: 2;
    }

    @keyframes floatLogo {
        0%, 100% {
            transform: translateY(0px);
        }
        50% {
            transform: translateY(-7px);
        }
    }

    @keyframes rotateLogo3D {
        0% {
            transform: rotateY(0deg) rotateX(0deg);
        }
        25% {
            transform: rotateY(90deg) rotateX(4deg);
        }
        50% {
            transform: rotateY(180deg) rotateX(0deg);
        }
        75% {
            transform: rotateY(270deg) rotateX(-4deg);
        }
        100% {
            transform: rotateY(360deg) rotateX(0deg);
        }
    }

    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 38px;
        font-weight: 800;
        background: linear-gradient(135deg, #00d4ff 0%, #00ff88 30%, #00d4ff 60%, #0055ff 100%);
        background-size: 300% 300%;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: titleShimmer 6s ease infinite;
        margin: 0;
        padding: 0;
        letter-spacing: 10px;
        text-align: center;
    }

    @keyframes titleShimmer {
        0%, 100% {
            background-position: 0% 50%;
        }
        50% {
            background-position: 100% 50%;
        }
    }

    .subtitle-text {
        text-align: center;
        color: #556680;
        font-family: 'Share Tech Mono', monospace;
        margin-top: -6px;
        padding: 0;
        font-size: 11px;
        letter-spacing: 5px;
    }

    /* ==================== 3D LOADING ANIMATION ==================== */
    .loading-3d-pro-container {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 60px;
        position: relative;
        background: radial-gradient(circle at center, rgba(0, 212, 255, 0.06) 0%, transparent 70%);
        border-radius: 8px;
        border: 1px solid rgba(0, 212, 255, 0.08);
    }

    .loading-3d-pro-scene {
        width: 140px;
        height: 140px;
        perspective: 600px;
        position: relative;
    }

    .loading-3d-pro-core {
        width: 100%;
        height: 100%;
        position: relative;
        transform-style: preserve-3d;
        animation: rotateCore3D 3.5s infinite cubic-bezier(0.68, -0.55, 0.27, 1.55);
    }

    .loading-3d-pro-ring {
        position: absolute;
        border-radius: 50%;
        border: 1.5px solid transparent;
        top: 50%;
        left: 50%;
        transform-style: preserve-3d;
    }

    .loading-3d-pro-ring:nth-child(1) {
        width: 100%;
        height: 100%;
        margin-top: -50%;
        margin-left: -50%;
        border-top-color: #00d4ff;
        animation: ringPulse1 2s infinite ease-in-out;
        transform: rotateX(75deg);
    }

    .loading-3d-pro-ring:nth-child(2) {
        width: 78%;
        height: 78%;
        margin-top: -39%;
        margin-left: -39%;
        border-right-color: #00ff88;
        animation: ringPulse2 2s infinite ease-in-out 0.4s;
        transform: rotateY(75deg);
    }

    .loading-3d-pro-ring:nth-child(3) {
        width: 56%;
        height: 56%;
        margin-top: -28%;
        margin-left: -28%;
        border-bottom-color: #ff2a6d;
        animation: ringPulse3 2s infinite ease-in-out 0.8s;
        transform: rotateZ(60deg);
    }

    .loading-3d-pro-ring:nth-child(4) {
        width: 34%;
        height: 34%;
        margin-top: -17%;
        margin-left: -17%;
        border-left-color: #bc13fe;
        animation: ringPulse4 2s infinite ease-in-out 1.2s;
        transform: rotateX(45deg) rotateY(45deg);
    }

    .loading-3d-pro-center {
        position: absolute;
        width: 16px;
        height: 16px;
        background: radial-gradient(circle, #ffffff, #00d4ff);
        border-radius: 50%;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        box-shadow: 0 0 50px rgba(0, 212, 255, 0.8), 0 0 100px rgba(0, 85, 255, 0.4);
        animation: coreGlow 1.5s infinite alternate;
    }

    .loading-3d-pro-particles {
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
    }

    .loading-3d-pro-particle {
        position: absolute;
        width: 2px;
        height: 2px;
        background: #00d4ff;
        border-radius: 50%;
        box-shadow: 0 0 8px #00d4ff;
        animation: particleDrift 2.5s infinite ease-in-out;
    }

    .loading-3d-pro-particle:nth-child(1) {
        top: 8%;
        left: 25%;
        animation-delay: 0s;
    }

    .loading-3d-pro-particle:nth-child(2) {
        top: 22%;
        left: 78%;
        animation-delay: 0.5s;
    }

    .loading-3d-pro-particle:nth-child(3) {
        top: 68%;
        left: 18%;
        animation-delay: 1s;
    }

    .loading-3d-pro-particle:nth-child(4) {
        top: 82%;
        left: 72%;
        animation-delay: 1.5s;
    }

    .loading-3d-pro-particle:nth-child(5) {
        top: 40%;
        left: 88%;
        animation-delay: 2s;
    }

    .loading-3d-pro-particle:nth-child(6) {
        top: 55%;
        left: 8%;
        animation-delay: 0.3s;
    }

    @keyframes rotateCore3D {
        0% {
            transform: rotateX(0deg) rotateY(0deg) rotateZ(0deg);
        }
        100% {
            transform: rotateX(720deg) rotateY(360deg) rotateZ(180deg);
        }
    }

    @keyframes ringPulse1 {
        0%, 100% {
            border-top-color: rgba(0, 212, 255, 0.2);
        }
        50% {
            border-top-color: #00d4ff;
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
        }
    }

    @keyframes ringPulse2 {
        0%, 100% {
            border-right-color: rgba(0, 255, 136, 0.2);
        }
        50% {
            border-right-color: #00ff88;
            box-shadow: 0 0 30px rgba(0, 255, 136, 0.5);
        }
    }

    @keyframes ringPulse3 {
        0%, 100% {
            border-bottom-color: rgba(255, 42, 109, 0.2);
        }
        50% {
            border-bottom-color: #ff2a6d;
            box-shadow: 0 0 30px rgba(255, 42, 109, 0.5);
        }
    }

    @keyframes ringPulse4 {
        0%, 100% {
            border-left-color: rgba(188, 19, 254, 0.2);
        }
        50% {
            border-left-color: #bc13fe;
            box-shadow: 0 0 30px rgba(188, 19, 254, 0.5);
        }
    }

    @keyframes coreGlow {
        0% {
            transform: translate(-50%, -50%) scale(0.8);
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.5);
        }
        100% {
            transform: translate(-50%, -50%) scale(1.4);
            box-shadow: 0 0 70px rgba(0, 212, 255, 0.9), 0 0 140px rgba(0, 85, 255, 0.5);
        }
    }

    @keyframes particleDrift {
        0%, 100% {
            transform: translateY(0) scale(0.8);
            opacity: 0.2;
        }
        50% {
            transform: translateY(-18px) scale(2);
            opacity: 1;
        }
    }

    .loading-3d-pro-text {
        font-family: 'Orbitron', sans-serif;
        color: #00d4ff;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.6);
        margin-top: 30px;
        font-size: 15px;
        letter-spacing: 5px;
        font-weight: 700;
        animation: textFlicker 2s infinite alternate;
    }

    .loading-3d-pro-sub {
        font-family: 'Share Tech Mono', monospace;
        color: #6688aa;
        font-size: 10px;
        margin-top: 6px;
        letter-spacing: 2px;
        animation: textFlicker 2s infinite alternate 0.5s;
    }

    @keyframes textFlicker {
        0%, 100% {
            opacity: 0.7;
        }
        50% {
            opacity: 1;
        }
    }

    /* ==================== FIN-TECH RESULT CARDS ==================== */
    .fintech-result-card {
        background: linear-gradient(160deg, rgba(0, 18, 38, 0.9), rgba(0, 8, 24, 0.95));
        border: 1px solid rgba(0, 212, 255, 0.18);
        border-radius: 4px;
        padding: 22px;
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
        height: 1px;
        background: linear-gradient(90deg, transparent, #00d4ff, #00ff88, #00d4ff, transparent);
        animation: scanHorizontal 3s infinite;
    }

    @keyframes scanHorizontal {
        0% {
            transform: translateX(-100%);
        }
        100% {
            transform: translateX(100%);
        }
    }

    .risk-metric {
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        color: #00d4ff;
        text-align: center;
        letter-spacing: 1px;
    }

    /* ==================== BUTTONS ==================== */
    .stButton > button {
        background: linear-gradient(160deg, #001a33, #002850) !important;
        border: 1px solid rgba(0, 212, 255, 0.35) !important;
        color: #00d4ff !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 600 !important;
        font-size: 11px !important;
        padding: 10px 20px !important;
        border-radius: 3px !important;
        letter-spacing: 2px !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
    }

    .stButton > button:hover {
        background: linear-gradient(160deg, #002850, #003870) !important;
        border-color: #00d4ff !important;
        box-shadow: 0 0 28px rgba(0, 212, 255, 0.25), 0 0 56px rgba(0, 212, 255, 0.08) !important;
        color: #ffffff !important;
        transform: translateY(-1px);
    }

    .stButton > button:active {
        transform: translateY(0) !important;
    }

    /* ==================== SIDEBAR ==================== */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(6, 10, 18, 0.99) 0%, rgba(2, 5, 10, 0.99) 100%) !important;
        border-right: 1px solid rgba(0, 212, 255, 0.1) !important;
    }

    [data-testid="stSidebar"] .stSelectbox > div > div {
        background: rgba(0, 28, 56, 0.5) !important;
        border: 1px solid rgba(0, 212, 255, 0.2) !important;
        border-radius: 3px !important;
        color: #c0d0e0 !important;
        font-family: 'Rajdhani', sans-serif !important;
    }

    [data-testid="stSidebar"] .stSelectbox label {
        color: #00d4ff !important;
        font-family: 'Orbitron', sans-serif !important;
        font-size: 8px !important;
        letter-spacing: 2px !important;
    }

    [data-testid="stSidebar"] .nav-link {
        background: rgba(0, 212, 255, 0.015) !important;
        border: 1px solid rgba(0, 212, 255, 0.06) !important;
        border-radius: 3px !important;
        margin: 2px 0 !important;
        transition: all 0.25s ease !important;
        font-family: 'Rajdhani', sans-serif !important;
        font-weight: 500 !important;
        letter-spacing: 1px !important;
        font-size: 11px !important;
    }

    [data-testid="stSidebar"] .nav-link:hover {
        background: rgba(0, 212, 255, 0.05) !important;
        border-color: rgba(0, 212, 255, 0.3) !important;
    }

    [data-testid="stSidebar"] .nav-link.selected {
        background: linear-gradient(160deg, rgba(0, 48, 96, 0.4), rgba(0, 28, 64, 0.6)) !important;
        border-color: #00d4ff !important;
        box-shadow: 0 0 18px rgba(0, 212, 255, 0.12) !important;
        color: #00d4ff !important;
    }

    /* ==================== GOOGLE LOGIN BUTTON ==================== */
    .google-login-btn {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        gap: 10px;
        background: #ffffff;
        border: 1px solid #ddd;
        color: #1a1a1a;
        padding: 14px 24px;
        border-radius: 3px;
        font-family: 'Orbitron', sans-serif;
        font-weight: 600;
        font-size: 10px;
        letter-spacing: 1.5px;
        width: 100%;
        transition: all 0.3s ease;
        text-decoration: none !important;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
    }

    .google-login-btn:hover {
        border-color: #4285F4;
        box-shadow: 0 4px 20px rgba(66, 133, 244, 0.3);
        transform: translateY(-1px);
    }

    /* ==================== INDICATOR GRID ==================== */
    .indicator-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
        gap: 7px;
        margin-top: 14px;
    }

    .indicator-box {
        background: rgba(0, 28, 56, 0.35);
        border: 1px solid rgba(0, 212, 255, 0.08);
        border-radius: 3px;
        padding: 14px;
        text-align: center;
        transition: all 0.3s ease;
    }

    .indicator-box:hover {
        border-color: rgba(0, 212, 255, 0.35);
        background: rgba(0, 36, 72, 0.5);
    }

    .indicator-name {
        font-family: 'Share Tech Mono', monospace;
        font-size: 9px;
        color: #6688aa;
        margin-bottom: 6px;
        letter-spacing: 1px;
    }

    .indicator-value {
        font-family: 'Orbitron', sans-serif;
        font-size: 15px;
        color: #e0e6f0;
        font-weight: 600;
    }

    .indicator-signal {
        font-family: 'Rajdhani', sans-serif;
        font-size: 10px;
        font-weight: 700;
        margin-top: 4px;
        letter-spacing: 1.5px;
    }

    /* ==================== PILLARS ==================== */
    .pillar-container {
        display: grid !important;
        grid-template-columns: repeat(4, 1fr) !important;
        gap: 3px !important;
        margin: 18px 0 !important;
        width: 100% !important;
    }

    .pillar-item {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        text-align: center !important;
        padding: 12px 4px !important;
        background: rgba(0, 26, 52, 0.3) !important;
        border: 1px solid rgba(0, 212, 255, 0.08) !important;
        border-radius: 3px !important;
    }

    .pillar-icon {
        width: 30px !important;
        height: 30px !important;
        object-fit: contain !important;
        margin-bottom: 7px !important;
        filter: drop-shadow(0 0 8px rgba(0, 212, 255, 0.45)) !important;
    }

    .pillar-title {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 6px !important;
        font-weight: 700 !important;
        color: #00d4ff !important;
        margin: 0 0 3px 0 !important;
        letter-spacing: 1px !important;
    }

    .pillar-desc {
        font-family: 'Share Tech Mono', monospace !important;
        font-size: 6px !important;
        color: #557799 !important;
        margin: 0 !important;
    }

    /* ==================== SENTINEL ==================== */
    .sentinel-container {
        border: 1px solid rgba(0, 212, 255, 0.25);
        border-radius: 6px;
        padding: 24px;
        background: rgba(0, 12, 28, 0.6);
        box-shadow: 0 0 48px rgba(0, 212, 255, 0.06);
        margin-bottom: 20px;
    }

    .sentinel-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 18px;
        border-bottom: 1px solid rgba(0, 212, 255, 0.12);
        padding-bottom: 12px;
    }

    .sentinel-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 26px;
        font-weight: 700;
        color: #00d4ff;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.35);
        letter-spacing: 4px;
        margin: 0;
    }

    .intelligence-panel {
        background: rgba(0, 8, 22, 0.7);
        border: 1px solid rgba(0, 212, 255, 0.1);
        border-radius: 4px;
        padding: 18px;
        height: 100%;
    }

    .intel-header {
        font-family: 'Orbitron', sans-serif;
        font-size: 13px;
        font-weight: 600;
        color: #00d4ff;
        margin-bottom: 12px;
        border-left: 2px solid #00d4ff;
        padding-left: 12px;
        letter-spacing: 3px;
    }

    .intel-content {
        font-family: 'Rajdhani', sans-serif;
        font-size: 13px;
        color: #c0d0e0;
        line-height: 1.6;
    }

    .status-badge {
        padding: 4px 14px;
        border-radius: 2px;
        font-size: 9px;
        font-family: 'Orbitron', sans-serif;
        text-transform: uppercase;
        letter-spacing: 2px;
    }

    .status-open {
        background: rgba(0, 255, 136, 0.07);
        color: #00ff88;
        border: 1px solid rgba(0, 255, 136, 0.25);
    }

    .status-ai {
        background: rgba(0, 212, 255, 0.07);
        color: #00d4ff;
        border: 1px solid rgba(0, 212, 255, 0.25);
    }

    /* ==================== CYBER GAUGE ==================== */
    .cyber-gauge-container {
        position: relative;
        overflow: hidden;
    }

    .cyber-gauge-glow {
        animation: gaugeGlowPulse 2s infinite alternate;
    }

    @keyframes gaugeGlowPulse {
        0% {
            filter: drop-shadow(0 0 4px rgba(0, 255, 136, 0.3));
        }
        100% {
            filter: drop-shadow(0 0 12px rgba(0, 255, 136, 0.6));
        }
    }

    /* ==================== SCROLLBAR ==================== */
    ::-webkit-scrollbar {
        width: 3px;
    }

    ::-webkit-scrollbar-track {
        background: #010408;
    }

    ::-webkit-scrollbar-thumb {
        background: #1a3350;
        border-radius: 2px;
    }

    ::-webkit-scrollbar-thumb:hover {
        background: #00d4ff;
    }

    /* ==================== TEXT GLOW CLASSES ==================== */
    .cyber-glow-text {
        font-family: 'Orbitron', sans-serif;
        color: #00d4ff;
        text-shadow: 0 0 10px rgba(0, 212, 255, 0.55), 0 0 30px rgba(0, 212, 255, 0.18);
        letter-spacing: 2px;
    }

    .digital-display {
        font-family: 'Share Tech Mono', monospace;
        color: #00ff88;
        text-shadow: 0 0 8px rgba(0, 255, 136, 0.45);
    }

    .section-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 12px;
        font-weight: 600;
        color: #7788aa;
        letter-spacing: 3px;
        text-transform: uppercase;
        margin: 22px 0 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ##############################################################################
# API KEY CONFIGURATION
# ##############################################################################

groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
marketaux_key = st.secrets.get("MARKETAUX_KEY") or os.getenv("MARKETAUX_KEY")
currents_api_key = st.secrets.get("CURRENTS_API_KEY") or os.getenv("CURRENTS_API_KEY")

client = None
if groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception as e:
        st.sidebar.error(f"SYSTEM ERROR: {str(e)}")
else:
    st.sidebar.error("API CONFIGURATION REQUIRED")

# ##############################################################################
# MARKET DATA FUNCTIONS
# ##############################################################################

def get_market_data(ticker_symbol):
    """
    Multi-source market data dengan prioritas:
    1. IC Market cTrader API (XAUUSD, XAGUSD, Forex, Crypto terpilih)
    2. Database Cache (3 detik freshness)
    3. yfinance (global market data fallback)
    
    Return: dict dengan keys price, change, change_pct, source, spread (opsional)
    """
    try:
        # Identifikasi nama instrumen dari ticker symbol
        inst_name = ticker_symbol
        for cat in instruments.values():
            for name, tick in cat.items():
                if tick == ticker_symbol:
                    inst_name = name
                    break
        
        # 1. Coba IC Market cTrader untuk instrumen yang didukung
        ctrader_instruments = [
            "XAUUSD", "XAGUSD",
            "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
            "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "BNBUSD"
        ]
        if inst_name in ctrader_instruments:
            ctrader_data = get_icmarket_price(inst_name)
            if ctrader_data:
                # Update database cache dengan harga dari broker
                cache_market_price(inst_name, ctrader_data["price"], 0)
                return {
                    "price": ctrader_data["price"],
                    "change": 0,
                    "change_pct": 0,
                    "source": "ICMARKET",
                    "spread": ctrader_data.get("spread", 0)
                }
        
        # 2. Cek Database Cache
        supabase_for_cache = create_client(url, key)
        res = supabase_for_cache.table("market_prices").select("*").eq("instrument", inst_name).execute()
        
        if res.data:
            cached = res.data[0]
            updated_at_str = cached.get('updated_at', '')
            
            # Parse timestamp cache
            if isinstance(updated_at_str, str) and updated_at_str:
                updated_at_str = updated_at_str.replace('Z', '+00:00')
                try:
                    updated_at = datetime.fromisoformat(updated_at_str)
                except:
                    updated_at = datetime.now(pytz.UTC) - timedelta(seconds=10)
            else:
                updated_at = datetime.now(pytz.UTC) - timedelta(seconds=10)
            
            # Konversi timezone
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=pytz.UTC)
            
            now = datetime.now(pytz.UTC)
            
            # Jika data masih segar (< 3 detik), gunakan cache
            if (now - updated_at).total_seconds() < 3:
                return {
                    "price": cached.get('price', 0),
                    "change": cached.get('price', 0) * (cached.get('change_pct', 0) / 100),
                    "change_pct": cached.get('change_pct', 0),
                    "source": "CACHE"
                }
        
        # 3. Fallback ke yfinance
        fetch_ticker = ticker_symbol
        ticker = yf.Ticker(fetch_ticker)
        hist = ticker.history(period="2d")
        
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            
            # Bulatkan Gold/Silver ke 2 desimal
            if ticker_symbol in ["GC=F", "SI=F"]:
                price = round(price, 2)
            
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else float(hist["Open"].iloc[-1])
            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            
            # Update database cache
            cache_market_price(inst_name, price, change_pct)
            
            return {
                "price": price,
                "change": price - prev_close,
                "change_pct": change_pct,
                "source": "LIVE"
            }
        return None
    except Exception:
        return None

def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    """
    Mengambil data historis dari yfinance untuk analisis teknikal.
    
    Parameter:
    - ticker_symbol (str): Kode ticker
    - period (str): 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y
    - interval (str): 1m, 5m, 15m, 30m, 1h, 1d, 1wk
    
    Return: DataFrame dengan index datetime
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        return df.sort_index().dropna()
    except:
        return pd.DataFrame()

def add_technical_indicators(df):
    """
    Menambahkan 20+ indikator teknikal ke dataframe.
    
    Indikator yang dihitung:
    - Trend: SMA20, SMA50, SMA200, EMA9, EMA21, KAMA, Ichimoku A/B, Parabolic SAR
    - Momentum: RSI(14), MACD, Stochastic K/D, CCI(20), Williams %R(14),
                 MFI(14), TRIX(15), ROC(12), Awesome Oscillator(5/34)
    - Volatility: Bollinger Bands(20,2), ATR(14)
    - Trend Strength: ADX(14), +DI, -DI
    - Volume: Volume SMA(20), Base Line(26)
    """
    if len(df) < 50:
        return df
    
    # --- Simple Moving Averages ---
    df["SMA20"] = df["Close"].rolling(window=20).mean()
    df["SMA50"] = df["Close"].rolling(window=50).mean()
    df["SMA200"] = df["Close"].rolling(window=min(len(df), 200)).mean()
    
    # --- Exponential Moving Averages ---
    df["EMA9"] = df["Close"].ewm(span=9, adjust=False).mean()
    df["EMA21"] = df["Close"].ewm(span=21, adjust=False).mean()
    
    # --- RSI (Relative Strength Index) - 14 period ---
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    df["RSI"] = 100 - (100 / (1 + rs))
    
    # --- MACD (Moving Average Convergence Divergence) ---
    exp1 = df["Close"].ewm(span=12, adjust=False).mean()
    exp2 = df["Close"].ewm(span=26, adjust=False).mean()
    df["MACD"] = exp1 - exp2
    df["Signal_Line"] = df["MACD"].ewm(span=9, adjust=False).mean()
    
    # --- Bollinger Bands (20, 2) ---
    df["BB_Mid"] = df["Close"].rolling(window=20).mean()
    df["BB_Std"] = df["Close"].rolling(window=20).std()
    df["BB_Upper"] = df["BB_Mid"] + (df["BB_Std"] * 2)
    df["BB_Lower"] = df["BB_Mid"] - (df["BB_Std"] * 2)
    
    # --- Stochastic Oscillator (14, 3) ---
    low_14 = df["Low"].rolling(window=14).min()
    high_14 = df["High"].rolling(window=14).max()
    df["Stoch_K"] = 100 * ((df["Close"] - low_14) / (high_14 - low_14).replace(0, 0.001))
    df["Stoch_D"] = df["Stoch_K"].rolling(window=3).mean()
    
    # --- ATR (Average True Range) - 14 period ---
    high_low = df["High"] - df["Low"]
    high_cp = np.abs(df["High"] - df["Close"].shift())
    low_cp = np.abs(df["Low"] - df["Close"].shift())
    df["TR"] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df["ATR"] = df["TR"].rolling(window=14).mean()
    
    # --- ADX (Average Directional Index) - 14 period ---
    df["UpMove"] = df["High"] - df["High"].shift()
    df["DownMove"] = df["Low"].shift() - df["Low"]
    df["+DM"] = np.where((df["UpMove"] > df["DownMove"]) & (df["UpMove"] > 0), df["UpMove"], 0)
    df["-DM"] = np.where((df["DownMove"] > df["UpMove"]) & (df["DownMove"] > 0), df["DownMove"], 0)
    df["+DI"] = 100 * (df["+DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["-DI"] = 100 * (df["-DM"].rolling(14).mean() / df["ATR"].replace(0, 0.001))
    df["DX"] = 100 * np.abs(df["+DI"] - df["-DI"]) / (df["+DI"] + df["-DI"]).replace(0, 0.001)
    df["ADX"] = df["DX"].rolling(14).mean()
    
    # --- Additional Indicators ---
    df["CCI"] = ta.trend.cci(df["High"], df["Low"], df["Close"], window=20)
    df["WPR"] = ta.momentum.williams_r(df["High"], df["Low"], df["Close"], lbp=14)
    df["MFI"] = ta.volume.money_flow_index(df["High"], df["Low"], df["Close"], df["Volume"], window=14)
    df["TRIX"] = ta.trend.trix(df["Close"], window=15)
    df["ROC"] = ta.momentum.roc(df["Close"], window=12)
    df["AO"] = ta.momentum.awesome_oscillator(df["High"], df["Low"], window1=5, window2=34)
    df["KAMA"] = ta.momentum.kama(df["Close"], window=10, pow1=2, pow2=30)
    
    # --- Ichimoku Cloud ---
    df["Ichimoku_A"] = ta.trend.ichimoku_a(df["High"], df["Low"], window1=9, window2=26)
    df["Ichimoku_B"] = ta.trend.ichimoku_b(df["High"], df["Low"], window2=26, window3=52)
    
    # --- Parabolic SAR ---
    psar_up = ta.trend.psar_up(df["High"], df["Low"], df["Close"])
    psar_down = ta.trend.psar_down(df["High"], df["Low"], df["Close"])
    df["Parabolic_SAR"] = psar_up.fillna(psar_down)
    
    # --- Volume Analysis ---
    df["Vol_SMA"] = df["Volume"].rolling(window=20).mean()
    df["Base_Line"] = (df["High"].rolling(window=26).max() + df["Low"].rolling(window=26).min()) / 2
    
    return df

def get_weighted_signal(df):
    """
    Menghitung sinyal teknikal berbasis weighted scoring.
    
    Menggunakan 4 indikator utama:
    1. RSI (14) - Oversold < 30, Overbought > 70
    2. MACD - Bullish jika MACD > Signal Line
    3. SMA 50 - Bullish jika Price > SMA50
    4. SMA 200 - Bullish jika Price > SMA200
    
    Return: (score, signal, reasons, bullish_count, bearish_count, neutral_count)
    """
    required_cols = ["RSI", "MACD", "Signal_Line", "SMA50", "SMA200"]
    for col in required_cols:
        if col not in df.columns:
            return 0, "WAITING", ["INITIALIZING INDICATORS..."], 0, 0, 100
    
    latest = df.iloc[-1]
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    reasons = []
    
    # 1. RSI Analysis
    rsi_val = latest["RSI"]
    if rsi_val < 30:
        bullish_count += 1
        reasons.append(f"RSI OVERSOLD [{rsi_val:.1f}]")
    elif rsi_val > 70:
        bearish_count += 1
        reasons.append(f"RSI OVERBOUGHT [{rsi_val:.1f}]")
    else:
        neutral_count += 1
        reasons.append(f"RSI NEUTRAL [{rsi_val:.1f}]")
    
    # 2. MACD Analysis
    if latest["MACD"] > latest["Signal_Line"]:
        bullish_count += 1
        reasons.append("MACD BULLISH CROSS")
    else:
        bearish_count += 1
        reasons.append("MACD BEARISH CROSS")
    
    # 3. SMA 50 Analysis
    if latest["Close"] > latest["SMA50"]:
        bullish_count += 1
        reasons.append("PRICE ABOVE SMA50")
    else:
        bearish_count += 1
        reasons.append("PRICE BELOW SMA50")
    
    # 4. SMA 200 Analysis
    if latest["Close"] > latest["SMA200"]:
        bullish_count += 1
        reasons.append("PRICE ABOVE SMA200")
    else:
        bearish_count += 1
        reasons.append("PRICE BELOW SMA200")
    
    # Calculate Weighted Score
    total = bullish_count + bearish_count + neutral_count
    score = (bullish_count / total) * 100 if total > 0 else 50
    
    # Signal Classification
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

# ##############################################################################
# AI FUNCTIONS
# ##############################################################################

def get_groq_response(question, context=""):
    """
    Chatbot AI menggunakan AeroVulpis Engine.
    
    Model: Large Language Model terbaru via Groq API
    Dilengkapi dengan limit harian berdasarkan tier user.
    
    Parameter:
    - question (str): Pertanyaan dari user
    - context (str): Konteks tambahan (instrumen aktif, harga, dll)
    
    Return: (str) Jawaban dari AI
    """
    if not client:
        return "ERROR: SYSTEM CONFIGURATION REQUIRED"
    
    # Cek limit harian
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_chatbot_count >= user_limits["chatbot_per_day"]:
        return f"LIMIT REACHED [{st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']}] | UPGRADE TIER"
    
    MODEL_NAME = 'llama-3.3-70b-versatile'
    
    system_prompt = f"""AEROVULPIS NEURAL SYSTEM V3.5
TIMESTAMP: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} WIB
LANGUAGE: {st.session_state.lang}
CONTEXT: {context}
PROTOCOL: Provide professional technical trading analysis with specific entry, stop loss, and take profit levels."""
    
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
        return f"SYSTEM ERROR: {str(e)}"

def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    """
    AEROVULPIS SENTINEL PRO - Deep Institutional Analysis.
    
    Menggunakan multiple AI models untuk analisis mendalam:
    - Primary: Model utama untuk analisis institusional
    - Companion: Model pendamping untuk detail teknis tambahan
    - Backup: Model cadangan jika primary/companion sibuk
    
    Hasil analisis di-cache 5 menit untuk menghemat pemakaian.
    
    Parameter:
    - asset_name (str): Nama instrumen
    - market_data (dict): Data harga pasar
    - df (DataFrame): Data historis dengan indikator teknikal
    - signal (str): Sinyal teknikal
    - reasons (list): Alasan teknikal
    
    Return: (str) Laporan analisis lengkap
    """
    openrouter_api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        return "ERROR: SYSTEM CONFIGURATION REQUIRED"
    
    # Check cache (berlaku 5 menit)
    cached = get_cached_ai_analysis(asset_name, "sentinel")
    if cached:
        return cached + "\n\n---\n*[CACHED INTELLIGENCE | < 5 MINUTES]*"
    
    # Check daily limits
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"DAILY LIMIT REACHED [{st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']}] | UPGRADE TIER"
    
    # Model configuration
    PRIMARY_MODEL = 'nousresearch/hermes-3-llama-3.1-405b'
    COMPANION_MODEL = 'qwen/qwen3-next-80b-instruct'
    BACKUP_MODELS = [
        'deepseek/deepseek-chat',
        'liquid/lfm-2.5-1.2b-thinking',
        'minimax/minimax-01'
    ]
    
    # Prepare data
    latest = df.iloc[-1]
    price = market_data['price']
    
    # Get news context
    news_list, _ = get_news_data(asset_name, max_articles=5)
    news_context = "\n".join([f"> {n['title']}" for n in news_list]) if news_list else "NO NEWS DATA AVAILABLE"
    
    # Build analysis prompt
    prompt = f"""AEROVULPIS SENTINEL INTELLIGENCE REPORT

INSTRUMENT: {asset_name}
DATE: {datetime.now().strftime('%Y-%m-%d')}
CURRENT PRICE: {price:,.4f}
SIGNAL: {signal}

TECHNICAL DATA:
- RSI (14): {latest.get('RSI', 0):.2f}
- MACD: {latest.get('MACD', 0):.4f}
- Signal Line: {latest.get('Signal_Line', 0):.4f}
- ATR (14): {latest.get('ATR', 0):.4f}
- ADX (14): {latest.get('ADX', 0):.2f}
- Stochastic K: {latest.get('Stoch_K', 0):.2f}
- Bollinger Upper: {latest.get('BB_Upper', 0):.4f}
- Bollinger Lower: {latest.get('BB_Lower', 0):.4f}

TECHNICAL REASONS:
{', '.join(reasons)}

MARKET NEWS:
{news_context}

REQUIRED OUTPUT STRUCTURE:

[KEY LEVELS]
Support: (2-3 levels with brief reasoning)
Resistance: (2-3 levels with brief reasoning)

[FUNDAMENTAL INSIGHT]
(Brief analysis of key factors affecting this instrument)

[BULLISH SCENARIO]
Entry:
Target:
Stop Loss:
Risk-Reward:

[BEARISH SCENARIO]
Entry:
Target:
Stop Loss:
Risk-Reward:

[FINAL VERDICT]
(Neutral conclusion with key risks to monitor)

RULES:
- Respond in Indonesian language
- Maximum 320 words total
- Balanced analysis between bullish and bearish
- Based on current April 2026 market conditions
"""
    
    def call_openrouter(model_name, system_msg):
        """Make API call to OpenRouter"""
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
    
    # 1. Try Primary Model
    analysis = call_openrouter(PRIMARY_MODEL, "You are AeroVulpis Sentinel Pro Intelligence. Provide institutional-grade trading analysis.")
    
    # 2. Add Companion Insights
    if analysis:
        companion_detail = call_openrouter(COMPANION_MODEL, "Provide additional technical details to supplement the trading analysis.")
        if companion_detail:
            analysis += "\n\n---\nSENTINEL COMPANION ANALYSIS:\n" + companion_detail
    
    # 3. Fallback to Backup Models
    if not analysis:
        backup_names = ["LING-2.6-FLASH", "LFM2.5-THINKING", "MINIMAX M2.5"]
        for i, model in enumerate(BACKUP_MODELS):
            analysis = call_openrouter(model, "You are AeroVulpis Backup Intelligence System. Provide trading analysis.")
            if analysis:
                analysis = f"[BACKUP SYSTEM ACTIVE: {backup_names[i]}]\n\n" + analysis
                break
    
    if not analysis:
        return "ALL NEURAL SYSTEMS AT CAPACITY | PLEASE RETRY IN A FEW MINUTES"
    
    # Update counters and cache
    st.session_state.daily_analysis_count += 1
    cache_ai_analysis(asset_name, "sentinel", analysis)
    
    return analysis

def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    """
    AEROVULPIS ENGINE - Deep Technical Analysis.
    
    Memberikan analisis teknikal mendalam dengan level entry,
    stop loss, dan take profit spesifik.
    
    Parameter:
    - asset_name (str): Nama instrumen
    - market_data (dict): Data harga pasar
    - df (DataFrame): Data historis dengan indikator
    - signal (str): Sinyal teknikal
    - reasons (list): Alasan teknikal
    
    Return: (str) Analisis teknikal lengkap
    """
    if not client:
        return "ERROR: SYSTEM CONFIGURATION REQUIRED"
    
    # Check cache
    cached = get_cached_ai_analysis(asset_name, "deep")
    if cached:
        return cached + "\n\n---\n*[CACHED ANALYSIS | < 5 MINUTES]*"
    
    # Check limits
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"DAILY LIMIT REACHED [{st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']}] | UPGRADE TIER"
    
    MODEL_NAME = 'llama-3.3-70b-versatile'
    
    latest = df.iloc[-1]
    price = market_data['price']
    
    # Build technical data context
    technical_data = f"""
INSTRUMENT: {asset_name}
CURRENT PRICE: {price:,.4f}
SIGNAL: {signal}

TECHNICAL INDICATORS:
- RSI (14): {latest.get('RSI',0):.2f}
- MACD: {latest.get('MACD',0):.4f}
- Signal Line: {latest.get('Signal_Line',0):.4f}
- SMA 50: {latest.get('SMA50',0):.4f}
- SMA 200: {latest.get('SMA200',0):.4f}
- ATR (14): {latest.get('ATR',0):.4f}
- ADX (14): {latest.get('ADX',0):.2f}
- Bollinger Bands: [{latest.get('BB_Lower',0):.4f} - {latest.get('BB_Upper',0):.4f}]
- Stochastic K: {latest.get('Stoch_K',0):.2f}
- Volume: {df['Volume'].iloc[-1]:,.0f}

TECHNICAL REASONS:
{', '.join(reasons)}
"""
    
    system_prompt = """AEROVULPIS DEEP ANALYSIS ENGINE V3.5
You are an expert technical analyst. Provide comprehensive analysis with specific entry, stop loss, and take profit levels.
Use markdown formatting with emojis. Maximum 2000 characters. Focus on actionable insights."""

    user_prompt = f"""DEEP ANALYSIS REQUEST:

{technical_data}

PLEASE INCLUDE:
1. RSI (14) Interpretation: {latest.get('RSI',0):.2f}
2. Price vs SMA 200 Position: {latest.get('SMA200',0):.4f}
3. Entry Levels (2-3 specific price levels with reasoning)
4. Stop Loss based on ATR: {latest.get('ATR',0):.4f}
5. Take Profit levels with minimum 1:2 risk-reward ratio
6. Position sizing and risk management recommendations
7. Bullish and Bearish scenarios with probability assessment"""
    
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
        
        # Update counters and cache
        st.session_state.daily_analysis_count += 1
        cache_ai_analysis(asset_name, "deep", analysis)
        
        return analysis
    except Exception as e:
        return f"SYSTEM ERROR: {str(e)}"