# ##############################################################################
# PART 1: SETUP, CSS, SIDEBAR, FUNCTIONS (FINAL)
# ##############################################################################

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
import finnhub
import base64
from io import BytesIO
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
    return create_client(url, key)

def get_supabase_admin():
    return create_client(url, service_role_key)

# ##############################################################################
# SYSTEM LOGGING & MAINTENANCE
# ##############################################################################

def send_log(pesan):
    try:
        supabase = get_supabase_client()
        supabase.table("logs_aktivitas").insert({"keterangan": pesan}).execute()
    except Exception:
        pass

def cleanup_logs():
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        supabase.table("logs_aktivitas").delete().lt("created_at", cutoff).execute()
    except Exception:
        pass

def cleanup_ai_cache():
    try:
        supabase = get_supabase_client()
        supabase.rpc("cleanup_ai_cache").execute()
    except Exception:
        try:
            cutoff = (datetime.now(pytz.UTC) - timedelta(minutes=30)).isoformat()
            supabase.table("ai_cache_sentinel").delete().lt("created_at", cutoff).execute()
            supabase.table("ai_cache_deep").delete().lt("created_at", cutoff).execute()
        except Exception:
            pass

def cache_market_price(symbol, price, change_pct=0.0):
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
    try:
        supabase = get_supabase_client()
        res = supabase.table("market_prices").select("price").eq("instrument", symbol).execute()
        if res.data:
            return res.data[0]["price"]
    except Exception:
        pass
    return None

def get_cached_market_price_full(symbol):
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
                        get_supabase_admin().table("user_tiers").update({"tier": "free"}).eq("user_id", user_id).execute()
                        return "free", None
                except Exception:
                    pass
            return tier, expired_at
    except Exception:
        pass
    return "free", None

def activate_key(user_id, key_code):
    if not user_id or not key_code:
        return False, "IDENTITY VERIFICATION REQUIRED"
    try:
        supabase = get_supabase_client()
        res = supabase.table("activation_keys").select("*").eq("key_code", key_code.upper().strip()).eq("is_used", False).execute()
        if not res.data:
            return False, "INVALID OR EXPIRED LICENSE KEY"
        key_data = res.data[0]
        tier = key_data.get("tier", "monthly")
        duration_days = key_data.get("duration_days", 30)
        expired_at = (datetime.now(pytz.UTC) + timedelta(days=duration_days)).isoformat()

        # Pastikan user ada di tabel users sebelum insert user_tiers
        sync_user_to_supabase(user_id, st.session_state.get("user_email", ""), st.session_state.get("user_name", ""))

        supabase_admin = get_supabase_admin()
        supabase_admin.table("user_tiers").upsert({
            "user_id": user_id,
            "tier": tier,
            "expired_at": expired_at,
            "activated_at": datetime.now(pytz.UTC).isoformat()
        }).execute()
        supabase.table("activation_keys").update({
            "is_used": True,
            "used_by": user_id,
            "used_at": datetime.now(pytz.UTC).isoformat()
        }).eq("key_code", key_code.upper().strip()).execute()
        return True, f"ACCESS GRANTED | TIER: {tier.upper()} | VALID UNTIL: {expired_at[:10]}"
    except Exception as e:
        return False, f"SYSTEM ERROR: {str(e)}"

def sync_user_to_supabase(user_id, email, name, avatar=""):
    try:
        supabase = get_supabase_client()
        existing = supabase.table("users").select("id").eq("id", user_id).execute()
        if existing.data:
            supabase.table("users").update({
                "email": email,
                "name": name,
                "avatar": avatar,
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).eq("id", user_id).execute()
        else:
            supabase.table("users").insert({
                "id": user_id,
                "email": email,
                "name": name,
                "avatar": avatar,
                "created_at": datetime.now(pytz.UTC).isoformat(),
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).execute()
            try:
                supabase_admin = get_supabase_admin()
                supabase_admin.table("user_tiers").upsert({
                    "user_id": user_id,
                    "tier": "free",
                    "activated_at": datetime.now(pytz.UTC).isoformat()
                }).execute()
            except Exception:
                try:
                    supabase.table("user_tiers").upsert({
                        "user_id": user_id,
                        "tier": "free",
                        "activated_at": datetime.now(pytz.UTC).isoformat()
                    }).execute()
                except Exception:
                    pass
    except Exception:
        pass

# ##############################################################################
# DELETE USER BY EMAIL (MENGGUNAKAN SERVICE_ROLE, TANPA LOGIN)
# ##############################################################################

def delete_user_by_email(email):
    """
    Mencari user ID berdasarkan email dari auth.users menggunakan admin client,
    lalu menghapus user dari auth.users dan tabel kustom.
    """
    try:
        supabase_admin = get_supabase_admin()
        # Cari user di auth.users berdasarkan email (menggunakan admin API)
        # Supabase Python client tidak memiliki method list_users secara langsung,
        # kita bisa gunakan REST API via requests.
        admin_url = url.replace(".co", ".co")  # pastikan format
        # Gunakan service_role key untuk mendapatkan list user by email
        headers = {
            "Authorization": f"Bearer {service_role_key}",
            "apikey": service_role_key
        }
        # Endpoint untuk list users (perlu Supabase > 2.1.0)
        # Kita gunakan supabase_admin.auth.admin.list_users() jika ada
        # Cek versi supabase client, namun lebih mudah kita gunakan REST langsung.
        # Saya akan gunakan pendekatan lebih sederhana: dapatkan user_id dari tabel users kita,
        # tapi itu tidak ada relasi langsung. Lebih baik gunakan fitur admin list_users.
        
        # Kita akan menggunakan API Supabase Auth Admin: GET /auth/v1/admin/users
        response = requests.get(
            f"{url}/auth/v1/admin/users",
            headers=headers,
            params={"email": email}
        )
        if response.status_code == 200:
            users_list = response.json().get("users", [])
            if users_list:
                user_id = users_list[0]["id"]
                # Hapus dari auth.users
                supabase_admin.auth.admin.delete_user(user_id)
                # Hapus dari tabel kustom
                supabase = get_supabase_client()
                supabase.table("users").delete().eq("id", user_id).execute()
                supabase.table("user_tiers").delete().eq("user_id", user_id).execute()
                return True, "User berhasil dihapus dari sistem."
            else:
                return False, "User dengan email tersebut tidak ditemukan."
        else:
            return False, f"Gagal mengakses daftar user: {response.text}"
    except Exception as e:
        return False, f"Gagal menghapus user: {str(e)}"

# ##############################################################################
# AI ANALYSIS CACHE SYSTEM
# ##############################################################################

def get_cached_ai_analysis(asset_name, cache_type="sentinel"):
    table_name = "ai_cache_sentinel" if cache_type == "sentinel" else "ai_cache_deep"
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now(pytz.UTC) - timedelta(minutes=15)).isoformat()
        res = supabase.table(table_name).select("*").eq("asset_name", asset_name)\
            .gte("created_at", cutoff)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data:
            return res.data[0]["analysis"]
    except Exception:
        pass
    return None

def cache_ai_analysis(asset_name, analysis, cache_type="sentinel"):
    table_name = "ai_cache_sentinel" if cache_type == "sentinel" else "ai_cache_deep"
    try:
        supabase = get_supabase_client()
        supabase.table(table_name).insert({
            "asset_name": asset_name,
            "analysis": analysis,
            "created_at": datetime.now(pytz.UTC).isoformat()
        }).execute()
    except Exception:
        pass

# ##############################################################################
# AUTH SESSION RESTORE
# ##############################################################################

def restore_session():
    if not st.session_state.get("auth_session"):
        try:
            supabase = get_supabase_client()
            session = supabase.auth.get_session()
            if session and session.user:
                user = session.user
                st.session_state.auth_session = session.access_token
                st.session_state.user_id = user.id
                st.session_state.user_name = user.user_metadata.get("full_name") or \
                    user.user_metadata.get("name") or \
                    (user.email.split("@")[0] if user.email else "USER")
                st.session_state.user_email = user.email or ""
                st.session_state.user_avatar = user.user_metadata.get("avatar_url") or \
                    user.user_metadata.get("picture") or ""
                st.session_state.user_tier, _ = get_user_tier(user.id)
                sync_user_to_supabase(user.id, user.email or "", st.session_state.user_name, st.session_state.user_avatar)
                send_log(f"AUTH: {st.session_state.user_name} ({st.session_state.user_email}) - Session Restored")
                return True
        except Exception as e:
            print(f"DEBUG: No existing session - {str(e)[:100]}")
    return False

# ##############################################################################
# FINNHUB PRICE FETCHER (REAL-TIME)
# ##############################################################################

def fetch_finnhub_price(symbol):
    finnhub_key = st.secrets.get("FINNHUB_KEY") or os.getenv("FINNHUB_KEY")
    if not finnhub_key:
        return None

    finnhub_map = {
        "XAUUSD": "XAUUSD", "XAGUSD": "XAGUSD",
        "EURUSD": "EURUSD", "GBPUSD": "GBPUSD",
        "USDJPY": "USDJPY", "AUDUSD": "AUDUSD",
        "USDCHF": "USDCHF", "USDCAD": "USDCAD",
        "NZDUSD": "NZDUSD", "BTCUSD": "BTCUSD",
        "ETHUSD": "ETHUSD", "SOLUSD": "SOLUSD",
        "XRPUSD": "XRPUSD", "BNBUSD": "BNBUSD",
    }

    finn_symbol = finnhub_map.get(symbol)
    if not finn_symbol:
        return None

    try:
        finnhub_client = finnhub.Client(api_key=finnhub_key)
        if finn_symbol in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD", "XRPUSD", "BNBUSD"]:
            res = finnhub_client.crypto_candles(finn_symbol, '1', int(time.time()) - 120, int(time.time()))
            if res and res.get('c') and len(res['c']) > 0:
                return {"price": float(res['c'][-1]), "source": "FINNHUB"}
        else:
            base_currency = finn_symbol[:3]
            res = finnhub_client.forex_rates(base=base_currency)
            if res and res.get('quote'):
                quote_currency = finn_symbol[3:]
                price = res['quote'].get(quote_currency)
                if price:
                    return {"price": float(price), "source": "FINNHUB"}
    except Exception:
        pass
    return None

# ##############################################################################
# PRICE FORMATTER
# ##############################################################################

def format_price_display(price, instrument_name):
    name_upper = str(instrument_name).upper() if instrument_name else ""
    if "XAU" in name_upper or "GOLD" in name_upper:
        return f"{price:,.2f}"
    elif "XAG" in name_upper or "SILVER" in name_upper:
        return f"{price:,.2f}"
    elif "BTC" in name_upper or "BITCOIN" in name_upper:
        return f"{price:,.2f}"
    elif "ETH" in name_upper or "ETHEREUM" in name_upper:
        return f"{price:,.2f}"
    elif any(c in name_upper for c in ["SOL", "BNB", "XRP"]):
        return f"{price:,.2f}"
    elif any(fx in name_upper for fx in ["EUR", "GBP", "CHF", "JPY", "AUD", "NZD", "CAD"]):
        return f"{price:,.4f}"
    elif any(idx in name_upper for idx in ["NASDAQ", "S&P", "DOW", "DAX", "IHSG", "SP500"]):
        return f"{price:,.2f}"
    elif any(cmd in name_upper for cmd in ["OIL", "WTI", "CRUDE", "GAS", "COPPER", "PALLADIUM", "PLATINUM"]):
        return f"{price:,.2f}"
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
    page_icon="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png",
    initial_sidebar_state="expanded"
)

cleanup_logs()
cleanup_old_data()
cleanup_ai_cache()
send_log("AEROVULPIS V3.5 SYSTEM ONLINE")

# ##############################################################################
# SESSION STATE INITIALIZATION
# ##############################################################################

if "lang" not in st.session_state: st.session_state.lang = "ID"
if "cached_analysis" not in st.session_state: st.session_state.cached_analysis = {}
if "user_tier" not in st.session_state: st.session_state.user_tier = "free"
if "user_id" not in st.session_state: st.session_state.user_id = None
if "user_name" not in st.session_state: st.session_state.user_name = None
if "user_email" not in st.session_state: st.session_state.user_email = None
if "user_avatar" not in st.session_state: st.session_state.user_avatar = None
if "auth_session" not in st.session_state: st.session_state.auth_session = None
if "show_signup" not in st.session_state: st.session_state.show_signup = False
if "daily_analysis_count" not in st.session_state: st.session_state.daily_analysis_count = 0
if "daily_chatbot_count" not in st.session_state: st.session_state.daily_chatbot_count = 0
if "last_reset_date" not in st.session_state: st.session_state.last_reset_date = datetime.now().date()
if "show_activation" not in st.session_state: st.session_state.show_activation = False
if "activation_result" not in st.session_state: st.session_state.activation_result = None
if "sentinel_analysis" not in st.session_state: st.session_state.sentinel_analysis = None
if "messages" not in st.session_state: st.session_state.messages = []
if "active_alerts" not in st.session_state: st.session_state.active_alerts = []
if "last_news_fetch" not in st.session_state: st.session_state.last_news_fetch = {}
if "show_payment_modal" not in st.session_state: st.session_state.show_payment_modal = False
if "selected_package" not in st.session_state: st.session_state.selected_package = None
if "selected_price" not in st.session_state: st.session_state.selected_price = ""
if "selected_duration" not in st.session_state: st.session_state.selected_duration = ""
if "payment_proof_uploaded" not in st.session_state: st.session_state.payment_proof_uploaded = False
if "show_forgot_password" not in st.session_state: st.session_state.show_forgot_password = False
if "show_delete_account" not in st.session_state: st.session_state.show_delete_account = False

if st.session_state.last_reset_date < datetime.now().date():
    st.session_state.daily_analysis_count = 0
    st.session_state.daily_chatbot_count = 0
    st.session_state.last_reset_date = datetime.now().date()

restore_session()

# ##############################################################################
# TIER LIMITS CONFIGURATION
# ##############################################################################
LIMITS = {
    "free": {"analysis_per_day": 5, "chatbot_per_day": 20},
    "trial": {"analysis_per_day": 10, "chatbot_per_day": 50},
    "weekly": {"analysis_per_day": 20, "chatbot_per_day": 100},
    "monthly": {"analysis_per_day": 50, "chatbot_per_day": 200},
    "six_months": {"analysis_per_day": 100, "chatbot_per_day": 500},
    "yearly": {"analysis_per_day": 999999, "chatbot_per_day": 999999}
}

# ##############################################################################
# LANGUAGE DICTIONARY (ID & EN LENGKAP)
# ##############################################################################
translations = {
    "ID": {
        "control_center": "CONTROL CENTER", "category": "KATEGORI ASET", "asset": "PILIH INSTRUMEN",
        "timeframe": "TIMEFRAME", "navigation": "NAVIGATION SYSTEM", "live_price": "LIVE PRICE",
        "signal": "SIGNAL", "rsi": "RSI", "atr": "ATR", "refresh": "REFRESH DATA",
        "ai_analysis": "AI ANALYSIS", "generate_ai": "GENERATE DEEP ANALYSIS",
        "market_sessions": "MARKET SESSIONS", "market_news": "MARKET NEWS",
        "risk_mgmt": "RISK MANAGEMENT", "settings": "SETTINGS", "clear_cache": "CLEAR SYSTEM CACHE",
        "lang_select": "LANGUAGE", "recommendation": "CURRENT RECOMMENDATION",
        "no_news": "NO NEWS AVAILABLE", "limit_reached": "DAILY LIMIT REACHED",
        "daily_limit": "DAILY USAGE", "upgrade_premium": "UPGRADE TIER",
        "login_title": "AUTHENTICATION SYSTEM", "login_email": "EMAIL",
        "login_password": "PASSWORD", "login_btn": "LOGIN",
        "signup_btn": "REGISTER NEW IDENTITY", "logout": "TERMINATE SESSION",
        "activate_key": "ACTIVATE LICENSE KEY", "enter_key": "ENTER ACTIVATION KEY",
        "activate_btn": "VALIDATE & ACTIVATE", "welcome": "WELCOME", "tier_free": "FREE TIER",
        "processing": "PROCESSING AUTHENTICATION", "activation_success": "ACTIVATION SUCCESSFUL",
        "activation_failed": "ACTIVATION FAILED", "sign_in_prompt": "IDENTITY VERIFICATION REQUIRED",
        "sign_in_desc": "Enter credentials to access the terminal",
        "sentinel_btn": "INITIATE DEEP ANALYSIS PRO", "risk_simulate": "EXECUTE SIMULATION",
        "risk_weekly": "WEEKLY", "risk_monthly": "MONTHLY", "risk_yearly": "YEARLY",
        "risk_net": "NET P/L", "risk_return": "RETURN %", "risk_balance": "FINAL BALANCE",
        "risk_initial": "INITIAL", "risk_after": "AFTER", "risk_params": "RISK PARAMETERS",
        "risk_per_trade": "RISK PER TRADE", "risk_reward_trade": "REWARD PER TRADE",
        "risk_max_loss": "MAX DAILY LOSS", "risk_max_profit": "MAX DAILY PROFIT",
        "risk_summary": "BALANCE PROJECTION", "funding_details": "ACCOUNT CONFIGURATION",
        "account_balance": "ACCOUNT BALANCE", "rr_simulator": "RISK-REWARD MATRIX",
        "wins": "WINNING TRADES", "losses": "LOSING TRADES", "daily_risk": "DAILY RISK LIMITS",
        "help_support": "SYSTEM DOCUMENTATION", "sentinel_title": "SENTINEL PRO INTELLIGENCE",
        "sentinel_ai_status": "AEROVULPIS SENTINEL CORE ACTIVE", "market_status": "MARKET STATUS: ACTIVE",
        "sentinel_intel": "INTELLIGENCE REPORT",
        "sentinel_placeholder": "Initialize Deep Analysis Pro to generate intelligence report",
        "news_filter": "CATEGORY FILTER",
        "news_updated": "Live feed from global financial networks | Updated hourly",
        "economic_title": "GLOBAL ECONOMIC SCANNER",
        "economic_subtitle": "Real-Time High Impact Event Detection Active",
        "alert_title": "SMART ALERT CENTER", "alert_subtitle": "AEROVULPIS TERMINAL V3.5",
        "alert_online": "SYSTEM ONLINE", "alert_sync": "MONITORING ACTIVE",
        "dashboard_title": "LIVE DASHBOARD", "signal_title": "TECHNICAL SIGNAL MATRIX",
        "chatbot_title": "NEURAL ASSISTANT", "risk_title": "RISK FRAMEWORK",
        "settings_title": "SYSTEM SETTINGS", "help_title": "SYSTEM DOCUMENTATION",
        "projection_title": "PROJECTED PERFORMANCE", "tier_label": "LICENSE TIER",
        "daily_usage_label": "DAILY USAGE MONITOR", "user_id_label": "USER ID",
        "user_email_label": "EMAIL", "license_activation": "LICENSE ACTIVATION",
        "enter_license_key": "ENTER LICENSE KEY", "license_placeholder": "XXXX-XXXX-XXXX-XXXX",
        "key_activate_button": "VALIDATE & ACTIVATE LICENSE", "force_refresh": "FORCE REFRESH",
        "or_continue_with": "OR CONTINUE WITH", "login_google": "AUTHENTICATE WITH GOOGLE",
        "upgrade_level": "UPGRADE LEVEL",
        "premium_lock": "PREMIUM ACCESS ONLY",
        "premium_msg": "This feature is available for premium users. Upgrade your access to unlock."
    },
    "EN": {
        "control_center": "CONTROL CENTER", "category": "ASSET CATEGORY", "asset": "SELECT INSTRUMENT",
        "timeframe": "TIMEFRAME", "navigation": "NAVIGATION SYSTEM", "live_price": "LIVE PRICE",
        "signal": "SIGNAL", "rsi": "RSI", "atr": "ATR", "refresh": "REFRESH DATA",
        "ai_analysis": "AI ANALYSIS", "generate_ai": "GENERATE DEEP ANALYSIS",
        "market_sessions": "MARKET SESSIONS", "market_news": "MARKET NEWS",
        "risk_mgmt": "RISK MANAGEMENT", "settings": "SETTINGS", "clear_cache": "CLEAR SYSTEM CACHE",
        "lang_select": "LANGUAGE", "recommendation": "CURRENT RECOMMENDATION",
        "no_news": "NO NEWS AVAILABLE", "limit_reached": "DAILY LIMIT REACHED",
        "daily_limit": "DAILY USAGE", "upgrade_premium": "UPGRADE TIER",
        "login_title": "AUTHENTICATION SYSTEM", "login_email": "EMAIL",
        "login_password": "PASSWORD", "login_btn": "LOGIN",
        "signup_btn": "REGISTER NEW IDENTITY", "logout": "TERMINATE SESSION",
        "activate_key": "ACTIVATE LICENSE KEY", "enter_key": "ENTER ACTIVATION KEY",
        "activate_btn": "VALIDATE & ACTIVATE", "welcome": "WELCOME", "tier_free": "FREE TIER",
        "processing": "PROCESSING AUTHENTICATION", "activation_success": "ACTIVATION SUCCESSFUL",
        "activation_failed": "ACTIVATION FAILED", "sign_in_prompt": "IDENTITY VERIFICATION REQUIRED",
        "sign_in_desc": "Enter credentials to access the terminal",
        "sentinel_btn": "INITIATE DEEP ANALYSIS PRO", "risk_simulate": "EXECUTE SIMULATION",
        "risk_weekly": "WEEKLY", "risk_monthly": "MONTHLY", "risk_yearly": "YEARLY",
        "risk_net": "NET P/L", "risk_return": "RETURN %", "risk_balance": "FINAL BALANCE",
        "risk_initial": "INITIAL", "risk_after": "AFTER", "risk_params": "RISK PARAMETERS",
        "risk_per_trade": "RISK PER TRADE", "risk_reward_trade": "REWARD PER TRADE",
        "risk_max_loss": "MAX DAILY LOSS", "risk_max_profit": "MAX DAILY PROFIT",
        "risk_summary": "BALANCE PROJECTION", "funding_details": "ACCOUNT CONFIGURATION",
        "account_balance": "ACCOUNT BALANCE", "rr_simulator": "RISK-REWARD MATRIX",
        "wins": "WINNING TRADES", "losses": "LOSING TRADES", "daily_risk": "DAILY RISK LIMITS",
        "help_support": "SYSTEM DOCUMENTATION", "sentinel_title": "SENTINEL PRO INTELLIGENCE",
        "sentinel_ai_status": "AEROVULPIS SENTINEL CORE ACTIVE", "market_status": "MARKET STATUS: ACTIVE",
        "sentinel_intel": "INTELLIGENCE REPORT",
        "sentinel_placeholder": "Initialize Deep Analysis Pro to generate intelligence report",
        "news_filter": "CATEGORY FILTER",
        "news_updated": "Live feed from global financial networks | Updated hourly",
        "economic_title": "GLOBAL ECONOMIC SCANNER",
        "economic_subtitle": "Real-Time High Impact Event Detection Active",
        "alert_title": "SMART ALERT CENTER", "alert_subtitle": "AEROVULPIS TERMINAL V3.5",
        "alert_online": "SYSTEM ONLINE", "alert_sync": "MONITORING ACTIVE",
        "dashboard_title": "LIVE DASHBOARD", "signal_title": "TECHNICAL SIGNAL MATRIX",
        "chatbot_title": "NEURAL ASSISTANT", "risk_title": "RISK FRAMEWORK",
        "settings_title": "SYSTEM SETTINGS", "help_title": "SYSTEM DOCUMENTATION",
        "projection_title": "PROJECTED PERFORMANCE", "tier_label": "LICENSE TIER",
        "daily_usage_label": "DAILY USAGE MONITOR", "user_id_label": "USER ID",
        "user_email_label": "EMAIL", "license_activation": "LICENSE ACTIVATION",
        "enter_license_key": "ENTER LICENSE KEY", "license_placeholder": "XXXX-XXXX-XXXX-XXXX",
        "key_activate_button": "VALIDATE & ACTIVATE LICENSE", "force_refresh": "FORCE REFRESH",
        "or_continue_with": "OR CONTINUE WITH", "login_google": "AUTHENTICATE WITH GOOGLE",
        "upgrade_level": "UPGRADE LEVEL",
        "premium_lock": "PREMIUM ACCESS ONLY",
        "premium_msg": "This feature is available for premium users. Upgrade your access to unlock."
    }
}

t = translations[st.session_state.lang]

# CSS (tidak berubah dari sebelumnya)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;800;900&family=Rajdhani:wght@300;400;500;600;700&family=Share+Tech+Mono&display=swap');
    :root {
        --neon-cyan: #00d4ff; --neon-green: #00ff88; --neon-red: #ff2a6d;
        --deep-blue: #0055ff; --dark-bg: #020408; --card-bg: rgba(10, 14, 23, 0.85);
        --glass-border: rgba(0, 212, 255, 0.12); --text-primary: #dce4f0;
        --text-secondary: #8899bb; --text-muted: #556680;
    }
    * { font-family: 'Rajdhani', sans-serif; }
    .stApp { background: radial-gradient(ellipse at 15% 45%, #0a1a30 0%, #030810 35%, #010408 100%); color: var(--text-primary); }
    .glass-card { background: var(--card-bg); backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px); border: 1px solid var(--glass-border); border-radius: 6px; padding: 20px; box-shadow: 0 4px 32px rgba(0,0,0,0.6), inset 0 1px 0 rgba(255,255,255,0.02); margin-bottom: 6px; transition: all 0.3s cubic-bezier(0.4,0,0.2,1); }
    .glass-card:hover { border-color: rgba(0,212,255,0.25); box-shadow: 0 6px 36px rgba(0,0,0,0.7), 0 0 16px rgba(0,212,255,0.04); }
    .session-container { border: 1px solid rgba(0,212,255,0.2); border-radius: 6px; padding: 28px; background: rgba(0,18,36,0.55); box-shadow: 0 0 48px rgba(0,212,255,0.05); margin-bottom: 24px; }
    .news-card { background: rgba(0,212,255,0.015); border: 1px solid rgba(0,212,255,0.06); padding: 20px; border-radius: 4px; margin-bottom: 10px; transition: all 0.35s cubic-bezier(0.4,0,0.2,1); position: relative; overflow: hidden; }
    .news-card::before { content: ''; position: absolute; top: 0; left: 0; width: 2px; height: 100%; background: linear-gradient(180deg, var(--neon-cyan) 0%, transparent 100%); opacity: 0.4; }
    .news-card:hover { background: rgba(0,212,255,0.03); border-color: rgba(0,212,255,0.2); box-shadow: 0 0 20px rgba(0,212,255,0.04); transform: translateX(2px); }
    .main-title-container { text-align: center; margin-bottom: 0; padding-bottom: 0; display: flex; flex-direction: column; align-items: center; justify-content: center; }
    .main-logo-container { position: relative; display: inline-block; animation: floatLogo 5s infinite ease-in-out; padding: 6px 0; margin-bottom: -16px; background: transparent !important; perspective: 1200px; overflow: visible !important; }
    .custom-logo { width: 88px; filter: drop-shadow(0 0 22px rgba(0,212,255,0.45)); background-color: transparent !important; animation: rotateLogo3D 15s infinite linear; transform-style: preserve-3d; position: relative; z-index: 2; }
    @keyframes floatLogo { 0%,100% { transform: translateY(0px); } 50% { transform: translateY(-7px); } }
    @keyframes rotateLogo3D { 0% { transform: rotateY(0deg) rotateX(0deg); } 25% { transform: rotateY(90deg) rotateX(4deg); } 50% { transform: rotateY(180deg) rotateX(0deg); } 75% { transform: rotateY(270deg) rotateX(-4deg); } 100% { transform: rotateY(360deg) rotateX(0deg); } }
    .main-title { font-family: 'Orbitron', sans-serif; font-size: 38px; font-weight: 800; background: linear-gradient(135deg, #00d4ff 0%, #00ff88 30%, #00d4ff 60%, #0055ff 100%); background-size: 300% 300%; -webkit-background-clip: text; -webkit-text-fill-color: transparent; animation: titleShimmer 6s ease infinite; margin: 0; padding: 0; letter-spacing: 10px; text-align: center; }
    @keyframes titleShimmer { 0%,100% { background-position: 0% 50%; } 50% { background-position: 100% 50%; } }
    .subtitle-text { text-align: center; color: #556680; font-family: 'Share Tech Mono', monospace; margin-top: -6px; padding: 0; font-size: 11px; letter-spacing: 5px; }
    .stButton > button { background: linear-gradient(160deg, #001a33, #002850) !important; border: 1px solid rgba(0,212,255,0.35) !important; color: #00d4ff !important; font-family: 'Orbitron', sans-serif !important; font-weight: 600 !important; font-size: 11px !important; padding: 10px 20px !important; border-radius: 3px !important; letter-spacing: 2px !important; transition: all 0.3s ease !important; text-transform: uppercase; }
    .stButton > button:hover { background: linear-gradient(160deg, #002850, #003870) !important; border-color: #00d4ff !important; box-shadow: 0 0 28px rgba(0,212,255,0.25), 0 0 56px rgba(0,212,255,0.08) !important; color: #ffffff !important; transform: translateY(-1px); }
    [data-testid="stSidebar"] { background: linear-gradient(180deg, rgba(6,10,18,0.99) 0%, rgba(2,5,10,0.99) 100%) !important; border-right: 1px solid rgba(0,212,255,0.1) !important; }
    .sentinel-container { border: 1px solid rgba(0,212,255,0.25); border-radius: 6px; padding: 24px; background: rgba(0,12,28,0.6); box-shadow: 0 0 48px rgba(0,212,255,0.06); margin-bottom: 20px; }
    .sentinel-title { font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 700; color: #00d4ff; text-shadow: 0 0 20px rgba(0,212,255,0.35); letter-spacing: 4px; margin: 0; }
    .intelligence-panel { background: rgba(0,8,22,0.7); border: 1px solid rgba(0,212,255,0.1); border-radius: 4px; padding: 18px; height: 100%; }
    .intel-header { font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: 600; color: #00d4ff; margin-bottom: 12px; border-left: 2px solid #00d4ff; padding-left: 12px; letter-spacing: 3px; }
    .status-badge { padding: 4px 14px; border-radius: 2px; font-size: 9px; font-family: 'Orbitron', sans-serif; text-transform: uppercase; letter-spacing: 2px; }
    .status-open { background: rgba(0,255,136,0.07); color: #00ff88; border: 1px solid rgba(0,255,136,0.25); }
    .status-ai { background: rgba(0,212,255,0.07); color: #00d4ff; border: 1px solid rgba(0,212,255,0.25); }
    .cyber-glow-text { font-family: 'Orbitron', sans-serif; color: #00d4ff; text-shadow: 0 0 10px rgba(0,212,255,0.55), 0 0 30px rgba(0,212,255,0.18); letter-spacing: 2px; }
    .section-title { font-family: 'Orbitron', sans-serif; font-size: 12px; font-weight: 600; color: #7788aa; letter-spacing: 3px; text-transform: uppercase; margin: 22px 0 8px 0; }
    .sentinel-cyber-report { background: rgba(0,8,22,0.8); border-left: 3px solid #00d4ff; padding: 18px 20px; border-radius: 3px; margin: 12px 0; font-family: 'Share Tech Mono', monospace; font-size: 11px; color: #8899bb; line-height: 1.7; box-shadow: 0 0 20px rgba(0,212,255,0.06); position: relative; overflow: hidden; }
    .indicator-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(155px, 1fr)); gap: 7px; margin-top: 14px; }
    .indicator-box { background: rgba(0,28,56,0.35); border: 1px solid rgba(0,212,255,0.08); border-radius: 3px; padding: 14px; text-align: center; transition: all 0.3s ease; }
    .indicator-name { font-family: 'Share Tech Mono', monospace; font-size: 9px; color: #6688aa; margin-bottom: 6px; letter-spacing: 1px; }
    .indicator-value { font-family: 'Orbitron', sans-serif; font-size: 15px; color: #e0e6f0; font-weight: 600; }
    .indicator-signal { font-family: 'Rajdhani', sans-serif; font-size: 10px; font-weight: 700; margin-top: 4px; letter-spacing: 1.5px; }
    .digital-auth-container { background: rgba(0,15,30,0.7); border: 1px solid rgba(0,212,255,0.2); border-radius: 6px; padding: 20px; margin: 8px 0; text-align: center; position: relative; overflow: hidden; box-shadow: 0 0 24px rgba(0,212,255,0.05); }
    .help-center-container { max-width: 700px; margin: 0 auto 24px auto; display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
    .fintech-result-card { background: linear-gradient(160deg, rgba(0,18,38,0.9), rgba(0,8,24,0.95)); border: 1px solid rgba(0,212,255,0.18); border-radius: 4px; padding: 22px; margin: 10px 0; position: relative; overflow: hidden; }
    .risk-metric { font-family: 'Orbitron', sans-serif; font-size: 14px; color: #00d4ff; text-align: center; letter-spacing: 1px; }
    ::-webkit-scrollbar { width: 3px; } ::-webkit-scrollbar-track { background: #010408; } ::-webkit-scrollbar-thumb { background: #1a3350; border-radius: 2px; } ::-webkit-scrollbar-thumb:hover { background: #00d4ff; }
    .risk-cyber-container { border: 1px solid rgba(0,212,255,0.25); border-radius: 8px; padding: 24px 20px; background: linear-gradient(160deg, rgba(0,12,32,0.95), rgba(0,4,16,0.98)); box-shadow: 0 0 60px rgba(0,212,255,0.06), inset 0 1px 0 rgba(0,212,255,0.04); margin-bottom: 20px; position: relative; overflow: hidden; }
    .risk-cyber-container::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, #00d4ff, #00ff88, #bc13fe, transparent); animation: scanHorizontal 4s infinite; }
    @keyframes scanHorizontal { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }
    .risk-hud-title { font-family: 'Orbitron', sans-serif; font-size: 22px; font-weight: 800; color: #00d4ff; text-align: center; letter-spacing: 6px; text-shadow: 0 0 35px rgba(0,212,255,0.5), 0 0 70px rgba(0,212,255,0.15); margin-bottom: 2px; }
    .risk-hud-subtitle { font-family: 'Share Tech Mono', monospace; font-size: 8px; color: #556680; text-align: center; letter-spacing: 4px; margin-bottom: 20px; text-transform: uppercase; }
    .risk-neon-divider { height: 1px; background: linear-gradient(90deg, transparent, rgba(0,212,255,0.2), transparent); margin: 16px 0; }
    .risk-input-card { background: rgba(0,22,55,0.6); border: 1px solid rgba(0,212,255,0.1); border-radius: 4px; padding: 12px; margin-bottom: 8px; backdrop-filter: blur(8px); }
    .risk-matrix-item { background: rgba(0,25,60,0.5); border: 1px solid rgba(0,212,255,0.08); border-radius: 4px; padding: 10px 6px; text-align: center; transition: all 0.3s ease; }
    .risk-matrix-item:hover { border-color: #00d4ff; box-shadow: 0 0 14px rgba(0,212,255,0.1); }
    .risk-matrix-label { font-family: 'Orbitron', sans-serif; font-size: 6px; color: #557799; letter-spacing: 1.5px; margin-bottom: 4px; }
    .risk-matrix-value { font-family: 'Share Tech Mono', monospace; font-size: 13px; color: #00d4ff; text-shadow: 0 0 8px rgba(0,212,255,0.3); }
    .risk-simulate-btn button { background: linear-gradient(160deg, #002850, #004080) !important; border: 1px solid #00d4ff !important; color: #00d4ff !important; font-family: 'Orbitron', sans-serif !important; font-weight: 700 !important; font-size: 12px !important; letter-spacing: 4px !important; padding: 14px 24px !important; border-radius: 4px !important; text-shadow: 0 0 20px rgba(0,212,255,0.5) !important; animation: btnPulse 2s infinite; width: 100% !important; }
    .risk-simulate-btn button:hover { background: linear-gradient(160deg, #003870, #0050a0) !important; box-shadow: 0 0 40px rgba(0,212,255,0.4), 0 0 80px rgba(0,212,255,0.1) !important; color: #ffffff !important; transform: scale(1.02); }
    @keyframes btnPulse { 0%,100% { box-shadow: 0 0 20px rgba(0,212,255,0.2); } 50% { box-shadow: 0 0 40px rgba(0,212,255,0.4); } }
    .risk-projection-card { background: linear-gradient(160deg, rgba(0,28,65,0.8), rgba(0,8,35,0.9)); border: 1px solid rgba(0,212,255,0.2); border-radius: 4px; padding: 14px; margin: 6px 0; position: relative; overflow: hidden; }
    .risk-projection-card::after { content: ''; position: absolute; bottom: 0; left: 0; width: 100%; height: 2px; background: linear-gradient(90deg, transparent, #00ff88, transparent); }
    .risk-projection-card.warning::after { background: linear-gradient(90deg, transparent, #ff2a6d, transparent); }
    .risk-data-stream { font-family: 'Share Tech Mono', monospace; font-size: 7px; color: #3a5068; text-align: center; letter-spacing: 2px; margin-top: 14px; animation: dataStream 3s infinite; }
    @keyframes dataStream { 0%,100% { opacity: 0.3; } 50% { opacity: 0.7; } }
    .upgrade-container { max-width: 1000px; margin: 0 auto; padding: 20px 10px; }
    .upgrade-title { font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 800; text-align: center; color: #00d4ff; text-shadow: 0 0 35px rgba(0,212,255,0.55), 0 0 70px rgba(0,212,255,0.15); letter-spacing: 6px; margin-bottom: 5px; }
    .upgrade-subtitle { font-family: 'Share Tech Mono', monospace; font-size: 9px; text-align: center; color: #557799; letter-spacing: 4px; margin-bottom: 30px; text-transform: uppercase; }
    .pricing-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 20px; }
    @media (max-width: 900px) { .pricing-grid { grid-template-columns: repeat(2, 1fr); } }
    .pricing-card { background: linear-gradient(160deg, rgba(0,15,38,0.9), rgba(0,4,12,0.97)); border: 1px solid rgba(0,212,255,0.15); border-radius: 6px; padding: 22px 12px; text-align: center; transition: all 0.35s cubic-bezier(0.175, 0.885, 0.32, 1.275); position: relative; overflow: hidden; }
    .pricing-card:hover { border-color: #00d4ff; box-shadow: 0 0 35px rgba(0,212,255,0.25), 0 0 70px rgba(0,212,255,0.08); transform: translateY(-4px); }
    .pricing-card::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 1.5px; background: linear-gradient(90deg, transparent, rgba(0,212,255,0.5), transparent); animation: scanHorizontal 3s infinite; }
    .pricing-card.featured { border-color: rgba(0,255,136,0.35); box-shadow: 0 0 30px rgba(0,255,136,0.1); }
    .pricing-card.featured::before { background: linear-gradient(90deg, transparent, #00ff88, transparent); }
    .pricing-badge { position: absolute; top: 10px; right: -28px; background: #00ff88; color: #000; font-family: 'Orbitron', sans-serif; font-size: 7px; font-weight: 800; letter-spacing: 2px; padding: 3px 30px; transform: rotate(45deg); text-transform: uppercase; }
    .pricing-name { font-family: 'Orbitron', sans-serif; font-size: 13px; font-weight: 700; color: #00d4ff; letter-spacing: 3px; margin-bottom: 4px; text-transform: uppercase; }
    .pricing-duration { font-family: 'Share Tech Mono', monospace; font-size: 9px; color: #557799; letter-spacing: 2px; margin-bottom: 14px; }
    .pricing-price { font-family: 'Share Tech Mono', monospace; font-size: 26px; font-weight: 700; color: #ffffff; text-shadow: 0 0 20px rgba(0,212,255,0.3); margin-bottom: 14px; }
    .pricing-price .currency { font-size: 13px; color: #6688aa; font-weight: 400; }
    .pricing-features { list-style: none; padding: 0; margin: 0 0 16px 0; text-align: left; font-family: 'Rajdhani', sans-serif; font-size: 10px; color: #8899bb; }
    .pricing-features li { padding: 3px 0; border-bottom: 1px solid rgba(255,255,255,0.02); }
    .pricing-features li::before { content: "// "; color: #00d4ff; font-family: 'Share Tech Mono', monospace; font-size: 7px; }
    .payment-modal-overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.85); z-index: 9999; display: flex; align-items: center; justify-content: center; backdrop-filter: blur(12px); }
    .payment-modal { background: linear-gradient(160deg, rgba(0,15,38,0.98), rgba(0,5,18,0.99)); border: 2px solid rgba(0,212,255,0.3); border-radius: 10px; padding: 20px 15px; max-width: 300px; width: 90%; text-align: center; position: relative; box-shadow: 0 0 100px rgba(0,212,255,0.15), 0 0 200px rgba(0,212,255,0.05); }
    .payment-modal::before { content: ''; position: absolute; top: 0; left: 0; width: 100%; height: 3px; background: linear-gradient(90deg, transparent, #00d4ff, #00ff88, #bc13fe, transparent); animation: scanHorizontal 4s infinite; }
    .payment-modal-title { font-family: 'Orbitron', sans-serif; font-size: 16px; font-weight: 800; color: #00d4ff; letter-spacing: 4px; margin-bottom: 5px; }
    .payment-modal-subtitle { font-family: 'Share Tech Mono', monospace; font-size: 7px; color: #557799; letter-spacing: 3px; margin-bottom: 15px; }
    .close-modal-btn { position: absolute; top: 8px; right: 10px; background: none; border: none; font-size: 20px; color: #00d4ff; cursor: pointer; font-family: 'Orbitron', sans-serif; z-index: 10000; }
    .close-modal-btn:hover { color: #ff2a6d; }
    .qr-container { background: #ffffff; padding: 8px; border-radius: 6px; display: inline-block; margin-bottom: 12px; border: 2px solid rgba(0,212,255,0.3); box-shadow: 0 0 30px rgba(0,212,255,0.2); }
    .payment-info-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin: 10px 0; text-align: left; }
    .payment-info-item { background: rgba(0,20,50,0.5); border: 1px solid rgba(0,212,255,0.1); border-radius: 3px; padding: 6px 8px; }
    .payment-info-label { font-family: 'Orbitron', sans-serif; font-size: 5px; color: #557799; letter-spacing: 1.5px; text-transform: uppercase; }
    .payment-info-value { font-family: 'Share Tech Mono', monospace; font-size: 9px; color: #00ff88; }
    .trust-badge-container { display: flex; justify-content: center; gap: 8px; margin: 10px 0; flex-wrap: wrap; }
    .trust-badge { background: rgba(0,212,255,0.04); border: 1px solid rgba(0,212,255,0.12); border-radius: 3px; padding: 4px 10px; font-family: 'Share Tech Mono', monospace; font-size: 6px; color: #6688aa; letter-spacing: 1px; }
    .trust-badge .highlight { color: #00d4ff; font-weight: 700; }
    .payment-steps { text-align: left; font-family: 'Rajdhani', sans-serif; font-size: 9px; color: #8899bb; margin: 8px 0; line-height: 1.6; }
    .payment-steps span { color: #00d4ff; font-family: 'Orbitron', sans-serif; font-size: 7px; margin-right: 4px; }
    .dynamihatch-watermark { font-family: 'Orbitron', sans-serif; font-size: 7px; color: rgba(255,255,255,0.03); position: absolute; bottom: 6px; right: 12px; letter-spacing: 2px; }
</style>
""", unsafe_allow_html=True)

# API Key Configuration
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

# Market data functions
def get_market_data(ticker_symbol):
    try:
        inst_name = ticker_symbol
        for cat in instruments.values():
            for name, tick in cat.items():
                if tick == ticker_symbol:
                    inst_name = name
                    break
        finnhub_result = fetch_finnhub_price(inst_name)
        if finnhub_result and finnhub_result.get("price", 0) > 0:
            cache_market_price(inst_name, finnhub_result["price"], 0)
            return {"price": finnhub_result["price"], "change": 0, "change_pct": 0, "source": finnhub_result.get("source", "FINNHUB"), "spread": 0}
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
            now = datetime.now(pytz.UTC)
            if (now - updated_at).total_seconds() < 5:
                return {"price": cached.get('price', 0), "change": cached.get('price', 0) * (cached.get('change_pct', 0) / 100), "change_pct": cached.get('change_pct', 0), "source": "CACHE"}
        fetch_ticker = ticker_symbol
        ticker = yf.Ticker(fetch_ticker)
        hist = ticker.history(period="2d")
        if not hist.empty:
            price = float(hist["Close"].iloc[-1])
            if ticker_symbol in ["GC=F", "SI=F"]:
                price = round(price, 2)
            prev_close = float(hist["Close"].iloc[-2]) if len(hist) > 1 else float(hist["Open"].iloc[-1])
            change_pct = ((price - prev_close) / prev_close) * 100 if prev_close > 0 else 0
            cache_market_price(inst_name, price, change_pct)
            return {"price": price, "change": price - prev_close, "change_pct": change_pct, "source": "LIVE"}
        return None
    except Exception:
        return None

def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        return df.sort_index().dropna()
    except:
        return pd.DataFrame()

def add_technical_indicators(df):
    if len(df) < 50:
        return df
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
    psar_up = ta.trend.psar_up(df["High"], df["Low"], df["Close"])
    psar_down = ta.trend.psar_down(df["High"], df["Low"], df["Close"])
    df["Parabolic_SAR"] = psar_up.fillna(psar_down)
    df["Vol_SMA"] = df["Volume"].rolling(window=20).mean()
    df["Base_Line"] = (df["High"].rolling(window=26).max() + df["Low"].rolling(window=26).min()) / 2
    return df

def get_weighted_signal(df):
    required_cols = ["RSI", "MACD", "Signal_Line", "SMA50", "SMA200"]
    for col in required_cols:
        if col not in df.columns:
            return 0, "WAITING", ["INITIALIZING INDICATORS..."], 0, 0, 100
    latest = df.iloc[-1]
    bullish_count = 0
    bearish_count = 0
    neutral_count = 0
    reasons = []
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
    if latest["MACD"] > latest["Signal_Line"]:
        bullish_count += 1
        reasons.append("MACD BULLISH CROSS")
    else:
        bearish_count += 1
        reasons.append("MACD BEARISH CROSS")
    if latest["Close"] > latest["SMA50"]:
        bullish_count += 1
        reasons.append("PRICE ABOVE SMA50")
    else:
        bearish_count += 1
        reasons.append("PRICE BELOW SMA50")
    if latest["Close"] > latest["SMA200"]:
        bullish_count += 1
        reasons.append("PRICE ABOVE SMA200")
    else:
        bearish_count += 1
        reasons.append("PRICE BELOW SMA200")
    total = bullish_count + bearish_count + neutral_count
    score = (bullish_count / total) * 100 if total > 0 else 50
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

def get_groq_response(question, context=""):
    if not client:
        return "ERROR: SYSTEM CONFIGURATION REQUIRED"
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
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": question}],
            model=MODEL_NAME, temperature=0.7, max_tokens=1024,
        )
        st.session_state.daily_chatbot_count += 1
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"SYSTEM ERROR: {str(e)}"

def get_sentinel_analysis(asset_name, market_data, df, signal, reasons):
    openrouter_api_key = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
    if not openrouter_api_key:
        return "ERROR: SYSTEM CONFIGURATION REQUIRED"
    cached = get_cached_ai_analysis(asset_name, "sentinel")
    if cached:
        return cached + "\n\n---\n*[CACHED INTELLIGENCE | < 15 MINUTES]*"
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"DAILY LIMIT REACHED | UPGRADE TIER"
    PRIMARY_MODEL = 'nousresearch/hermes-3-llama-3.1-405b'
    COMPANION_MODEL = 'qwen/qwen3-next-80b-instruct'
    BACKUP_MODELS = ['deepseek/deepseek-chat', 'liquid/lfm-2.5-1.2b-thinking', 'minimax/minimax-01']
    latest = df.iloc[-1]
    price = market_data['price']
    news_list, _ = get_news_data(asset_name, max_articles=5)
    news_context = "\n".join([f"> {n['title']}" for n in news_list]) if news_list else "NO NEWS DATA AVAILABLE"
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
TECHNICAL REASONS: {', '.join(reasons)}
MARKET NEWS: {news_context}
REQUIRED OUTPUT STRUCTURE:
[KEY LEVELS] Support: (2-3 levels) Resistance: (2-3 levels)
[FUNDAMENTAL INSIGHT] (Brief analysis)
[BULLISH SCENARIO] Entry/Target/Stop Loss/Risk-Reward
[BEARISH SCENARIO] Entry/Target/Stop Loss/Risk-Reward
[FINAL VERDICT] (Neutral conclusion)
RULES: Respond in Indonesian, max 320 words, balanced analysis, April 2026 market conditions."""
    def call_openrouter(model_name, system_msg):
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {openrouter_api_key}", "Content-Type": "application/json"},
                data=json.dumps({"model": model_name, "messages": [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}]}),
                timeout=45
            )
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            return None
        except:
            return None
    analysis = call_openrouter(PRIMARY_MODEL, "You are AeroVulpis Sentinel Pro Intelligence. Provide institutional-grade trading analysis.")
    if analysis:
        companion_detail = call_openrouter(COMPANION_MODEL, "Provide additional technical details.")
        if companion_detail:
            analysis += "\n\n---\nSENTINEL COMPANION ANALYSIS:\n" + companion_detail
    if not analysis:
        backup_names = ["LING-2.6-FLASH", "LFM2.5-THINKING", "MINIMAX M2.5"]
        for i, model in enumerate(BACKUP_MODELS):
            analysis = call_openrouter(model, "You are AeroVulpis Backup Intelligence System.")
            if analysis:
                analysis = f"[BACKUP SYSTEM ACTIVE: {backup_names[i]}]\n\n" + analysis
                break
    if not analysis:
        return "ALL NEURAL SYSTEMS AT CAPACITY | PLEASE RETRY IN A FEW MINUTES"
    st.session_state.daily_analysis_count += 1
    cache_ai_analysis(asset_name, analysis, "sentinel")
    return f"""<div class="sentinel-cyber-report">{analysis}</div>"""

def get_deep_analysis(asset_name, market_data, df, signal, reasons):
    if not client:
        return "ERROR: SYSTEM CONFIGURATION REQUIRED"
    cached = get_cached_ai_analysis(asset_name, "deep")
    if cached:
        return cached + "\n\n---\n*[CACHED ANALYSIS | < 15 MINUTES]*"
    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    if st.session_state.daily_analysis_count >= user_limits["analysis_per_day"]:
        return f"DAILY LIMIT REACHED | UPGRADE TIER"
    MODEL_NAME = 'llama-3.3-70b-versatile'
    latest = df.iloc[-1]
    price = market_data['price']
    technical_data = f"""INSTRUMENT: {asset_name} | CURRENT PRICE: {price:,.4f} | SIGNAL: {signal}
RSI (14): {latest.get('RSI',0):.2f} | MACD: {latest.get('MACD',0):.4f} | Signal Line: {latest.get('Signal_Line',0):.4f}
SMA 50: {latest.get('SMA50',0):.4f} | SMA 200: {latest.get('SMA200',0):.4f} | ATR (14): {latest.get('ATR',0):.4f}
ADX (14): {latest.get('ADX',0):.2f} | BB: [{latest.get('BB_Lower',0):.4f} - {latest.get('BB_Upper',0):.4f}]
Stochastic K: {latest.get('Stoch_K',0):.2f} | Volume: {df['Volume'].iloc[-1]:,.0f}
TECHNICAL REASONS: {', '.join(reasons)}"""
    system_prompt = """AEROVULPIS DEEP ANALYSIS ENGINE V3.5. You are an expert technical analyst. Provide comprehensive analysis with specific entry, stop loss, and take profit levels. Max 2000 chars."""
    user_prompt = f"""DEEP ANALYSIS REQUEST: {technical_data}
INCLUDE: RSI Interpretation, Price vs SMA 200, Entry Levels (2-3), Stop Loss based on ATR, Take Profit (min 1:2 RR), Position sizing, Bullish/Bearish scenarios with probability."""
    try:
        chat_completion = client.chat.completions.create(
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            model=MODEL_NAME, temperature=0.6, max_tokens=2000,
        )
        analysis = chat_completion.choices[0].message.content
        st.session_state.daily_analysis_count += 1
        cache_ai_analysis(asset_name, analysis, "deep")
        return analysis
    except Exception as e:
        return f"SYSTEM ERROR: {str(e)}"

def market_session_status():
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    current_time = now.time()
    sessions = [
        {"name": "ASIAN SESSION", "market": "TOKYO", "start": dt_time(6, 0), "end": dt_time(15, 0), "color": "#00ff88"},
        {"name": "EUROPEAN SESSION", "market": "LONDON", "start": dt_time(14, 0), "end": dt_time(23, 0), "color": "#00d4ff"},
        {"name": "AMERICAN SESSION", "market": "NEW YORK", "start": dt_time(19, 0), "end": dt_time(4, 0), "color": "#ff2a6d"}
    ]
    st.markdown('<div class="session-container">', unsafe_allow_html=True)
    st.markdown('<h2 style="font-family:Orbitron;color:#00d4ff;text-align:center;font-size:22px;margin-bottom:25px;letter-spacing:5px;text-shadow:0 0 12px rgba(0,212,255,0.5);">GLOBAL MARKET SESSIONS</h2>', unsafe_allow_html=True)
    active_sessions = []
    for sess in sessions:
        is_active = (sess["start"] <= current_time <= sess["end"]) if sess["start"] < sess["end"] else (current_time >= sess["start"] or current_time <= sess["end"])
        status_html = f'<span style="padding:4px 14px;border-radius:2px;background:rgba(0,255,136,0.07);border:1px solid rgba(0,255,136,0.35);color:#00ff88;font-size:9px;font-family:Orbitron;letter-spacing:2px;">ACTIVE</span>' if is_active else f'<span style="padding:4px 14px;border-radius:2px;background:rgba(255,42,109,0.04);border:1px solid rgba(255,42,109,0.18);color:#556680;font-size:9px;font-family:Orbitron;letter-spacing:2px;opacity:0.6;">CLOSED</span>'
        if is_active:
            active_sessions.append(sess["name"])
        progress = 0
        if is_active:
            now_minutes = now.hour * 60 + now.minute
            start_minutes = sess["start"].hour * 60 + sess["start"].minute
            end_minutes = sess["end"].hour * 60 + sess["end"].minute
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            if now_minutes < start_minutes and sess["start"] > sess["end"]:
                now_minutes += 24 * 60
            total_duration = end_minutes - start_minutes
            elapsed = now_minutes - start_minutes
            progress = min(100, max(0, int((elapsed / total_duration) * 100)))
        st.markdown(f"""<div style="background:rgba(0,18,36,0.5);border:1px solid rgba(0,212,255,0.08);border-radius:4px;padding:18px;margin-bottom:10px;">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
                <div><span style="font-family:Orbitron;font-weight:700;color:{sess['color']};font-size:14px;letter-spacing:2px;">{sess['name']}</span><span style="font-family:Share Tech Mono;font-size:10px;color:#557799;margin-left:8px;">{sess['market']}</span></div>
                {status_html}</div>
            <div style="font-family:Share Tech Mono;font-size:11px;color:#6688aa;margin-bottom:10px;">{sess['start'].strftime('%H:%M')} - {sess['end'].strftime('%H:%M')} WIB</div>
            <div style="background:rgba(255,255,255,0.03);height:4px;border-radius:2px;overflow:hidden;">
                <div style="background:{sess['color'] if is_active else '#333'};width:{progress if is_active else 0}%;height:100%;border-radius:2px;transition:width 0.5s ease;box-shadow:0 0 12px {sess['color'] if is_active else 'transparent'};"></div>
            </div>
            <div style="font-family:Share Tech Mono;font-size:9px;color:{sess['color'] if is_active else '#445566'};text-align:right;margin-top:4px;">{f'PROGRESS: {progress}%' if is_active else 'STANDBY'}</div>
        </div>""", unsafe_allow_html=True)
    is_golden = (dt_time(19, 0) <= current_time <= dt_time(23, 0))
    if is_golden:
        st.markdown("""<div style="text-align:center;padding:16px;background:rgba(0,212,255,0.04);border:1px solid rgba(0,212,255,0.28);border-radius:4px;margin-top:12px;"><p style="font-family:Orbitron;color:#00d4ff;text-shadow:0 0 12px rgba(0,212,255,0.5);margin:0;font-size:18px;letter-spacing:3px;">GOLDEN HOUR ACTIVE</p><p style="font-family:Share Tech Mono;color:#8899bb;margin:4px 0 0 0;font-size:10px;">LONDON + NEW YORK OVERLAP | MAXIMUM LIQUIDITY | HIGH VOLATILITY</p></div>""", unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

instruments = {
    "FOREX": {"EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X", "AUD/USD": "AUDUSD=X", "USD/CHF": "USDCHF=X"},
    "CRYPTO": {"BITCOIN": "BTC-USD", "ETHEREUM": "ETH-USD", "SOLANA": "SOL-USD", "BNB": "BNB-USD", "XRP": "XRP-USD"},
    "INDICES": {"NASDAQ-100": "^IXIC", "S&P 500": "^GSPC", "DOW JONES": "^DJI", "DAX 40": "^GDAXI", "IHSG": "^JKSE"},
    "US STOCKS": {"NVIDIA": "NVDA", "APPLE": "AAPL", "TESLA": "TSLA", "MICROSOFT": "MSFT", "AMAZON": "AMZN"},
    "ID STOCKS": {"BBRI": "BBRI.JK", "BBCA": "BBCA.JK", "TLKM": "TLKM.JK", "ASII": "ASII.JK", "BMRI": "BMRI.JK"},
    "COMMODITIES": {"GOLD (XAUUSD)": "GC=F", "SILVER (XAGUSD)": "SI=F", "CRUDE OIL (WTI)": "CL=F", "NATURAL GAS": "NG=F", "COPPER": "HG=F", "PALLADIUM": "PA=F", "PLATINUM": "PL=F"}
}

def get_news_data(category="General", max_articles=10):
    from news_cache_manager import initialize_news_cache, should_update_news, get_cached_news, update_news_cache
    initialize_news_cache()
    force_refresh = False
    if "last_news_fetch" not in st.session_state:
        st.session_state.last_news_fetch = {}
    last_fetch = st.session_state.last_news_fetch.get(category)
    if last_fetch is None or (datetime.now() - last_fetch).total_seconds() > 300:
        force_refresh = True
        st.session_state.last_news_fetch[category] = datetime.now()
    if not force_refresh and not should_update_news(category):
        cached_news = get_cached_news(category)
        if cached_news:
            return cached_news, None
    berita_final = []
    urls_terpakai = set()
    category_map = {
        "Stock": "stocks, equities, earnings, wall street",
        "Geopolitics": "geopolitics, war, conflict, sanctions, central banks, tariffs, trade war",
        "Gold & Silver": "gold, silver, precious metals, commodities, XAUUSD",
        "Forex": "forex, currency, EURUSD, GBPUSD, USDJPY, central banks, interest rates, federal reserve, ECB, BOJ, BOE",
        "General": "finance, economy, market, breaking news"
    }
    api_query = category_map.get(category, "finance,economy,market")
    forex_keywords = ["EURUSD", "GBPUSD", "USDJPY", "forex", "currency", "central bank", "interest rate", "federal reserve", "ECB", "BOJ", "BOE"]
    if marketaux_key:
        try:
            since_date = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M')
            if category == "Forex":
                search_terms = ["forex", "currency markets", "central banks", "interest rates", "EURUSD", "GBPUSD"]
                for term in search_terms[:3]:
                    try:
                        url_m = f"https://api.marketaux.com/v1/news/all?api_token={marketaux_key}&language=en&search={term}&limit=10&published_after={since_date}"
                        res_m = requests.get(url_m, timeout=10).json()
                        if res_m.get('data'):
                            for item in res_m.get('data', []):
                                if item.get('url') and item['url'] not in urls_terpakai:
                                    berita_final.append({'publishedAt': item.get('published_at', datetime.now().isoformat()), 'title': item.get('title', 'NO TITLE'), 'description': item.get('description', ''), 'source': item.get('source', 'GLOBAL FINANCIAL NETWORK'), 'url': item['url']})
                                    urls_terpakai.add(item['url'])
                    except Exception:
                        pass
            else:
                url_m = f"https://api.marketaux.com/v1/news/all?api_token={marketaux_key}&language=en&search={api_query}&limit=20&published_after={since_date}"
                res_m = requests.get(url_m, timeout=10).json()
                if res_m.get('data'):
                    for item in res_m.get('data', []):
                        if item.get('url') and item['url'] not in urls_terpakai:
                            berita_final.append({'publishedAt': item.get('published_at', datetime.now().isoformat()), 'title': item.get('title', 'NO TITLE'), 'description': item.get('description', ''), 'source': item.get('source', 'GLOBAL FINANCIAL NETWORK'), 'url': item['url']})
                            urls_terpakai.add(item['url'])
        except Exception:
            pass
    if currents_api_key:
        try:
            currents_cat = category.lower()
            if category == "Geopolitics": currents_cat = "world"
            elif category == "Gold & Silver": currents_cat = "commodities"
            elif category == "Forex": currents_cat = "finance"
            url_c = f"https://api.currentsapi.services/v1/latest-news?apiKey={currents_api_key}&language=en&category={currents_cat}&limit=15"
            res_c = requests.get(url_c, timeout=10).json()
            if res_c.get('news'):
                for item in res_c.get('news', []):
                    if item.get('url') and item['url'] not in urls_terpakai:
                        if category == "Forex":
                            title_lower = item.get('title', '').lower()
                            if not any(kw.lower() in title_lower for kw in forex_keywords):
                                continue
                        berita_final.append({'publishedAt': item.get('published', datetime.now().isoformat()), 'title': item.get('title', 'NO TITLE'), 'description': item.get('description', ''), 'source': 'CURRENTS FINANCIAL', 'url': item['url']})
                        urls_terpakai.add(item['url'])
        except Exception:
            pass
    tiingo_key = st.secrets.get("TIINGO_KEY") or os.getenv("TIINGO_KEY")
    if tiingo_key:
        try:
            start_date = (datetime.now() - timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%S')
            url_t = f"https://api.tiingo.com/tiingo/news?token={tiingo_key}&limit=15&startDate={start_date}"
            if category == "Stock": url_t += "&tags=stocks"
            elif category == "Forex": url_t += "&tags=forex,currencies"
            elif category == "Gold & Silver": url_t += "&tags=commodities"
            res_t = requests.get(url_t, timeout=10).json()
            if isinstance(res_t, list):
                for item in res_t:
                    if item.get('url') and item['url'] not in urls_terpakai:
                        berita_final.append({'publishedAt': item.get('publishedDate', datetime.now().isoformat()), 'title': item.get('title', 'NO TITLE'), 'description': item.get('description', item.get('title', '')), 'source': 'FINANCIAL NEWS NETWORK', 'url': item['url']})
                        urls_terpakai.add(item['url'])
        except Exception:
            pass
    if not berita_final:
        cached_news = get_cached_news(category)
        if cached_news:
            return cached_news, "DISPLAYING CACHED DATA | LIVE FEED UNAVAILABLE"
        return [], "NO NEWS AVAILABLE"
    try:
        berita_final = sorted(berita_final, key=lambda x: str(x.get('publishedAt', '')), reverse=True)
    except Exception:
        pass
    berita_final = berita_final[:max_articles]
    tz_wib = pytz.timezone('Asia/Jakarta')
    for b in berita_final:
        try:
            raw_date = str(b.get('publishedAt', ''))
            if raw_date:
                raw_date = raw_date.replace('Z', '+00:00')
                try:
                    dt_utc = datetime.fromisoformat(raw_date)
                except Exception:
                    dt_utc = datetime.strptime(raw_date[:19], "%Y-%m-%dT%H:%M:%S")
                    dt_utc = dt_utc.replace(tzinfo=pytz.UTC)
                dt_wib = dt_utc.astimezone(tz_wib)
                b['publishedAt'] = dt_wib.strftime("%Y-%m-%d %H:%M WIB")
            else:
                b['publishedAt'] = 'N/A'
        except Exception:
            b['publishedAt'] = 'N/A'
    update_news_cache(category, berita_final)
    return berita_final, None

def check_smart_alerts():
    if "active_alerts" not in st.session_state or not st.session_state.active_alerts:
        return
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or st.secrets.get("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        return
    unique_instruments = list(set([a["instrument"] for a in st.session_state.active_alerts if not a.get("triggered", False)]))
    if not unique_instruments:
        return
    instrument_to_ticker = {"XAUUSD": "GC=F", "BTCUSD": "BTC-USD", "XAGUSD": "SI=F", "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X"}
    for cat in instruments.values():
        for name, ticker in cat.items():
            instrument_to_ticker[name] = ticker
    current_prices = {}
    for inst in unique_instruments:
        cached_data = get_cached_market_price_full(inst)
        if cached_data and cached_data.get("price"):
            current_prices[inst] = cached_data["price"]
        else:
            ticker = instrument_to_ticker.get(inst)
            if ticker:
                m_data = get_market_data(ticker)
                if m_data:
                    current_prices[inst] = m_data.get("price")
    for alert in st.session_state.active_alerts:
        if not alert.get("triggered", False):
            inst_name = alert.get("instrument")
            current_price = current_prices.get(inst_name)
            if current_price is None:
                continue
            target_raw = alert.get("target")
            target_value = alert.get("target_value")
            condition = alert.get("condition")
            if target_value is not None and isinstance(target_value, (int, float)) and target_value > 0:
                target_num = float(target_value)
            elif isinstance(target_raw, (int, float)):
                target_num = float(target_raw)
            else:
                try:
                    target_num = float(str(target_raw).replace(",", ""))
                except:
                    target_num = 0.0
            triggered = False
            if condition == "bullish" and current_price >= target_num:
                triggered = True
            elif condition == "bearish" and current_price <= target_num:
                triggered = True
            if triggered:
                alert["triggered"] = True
                now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d %H:%M:%S WIB")
                formatted_price = format_price_display(current_price, inst_name)
                formatted_target = format_price_display(target_num, inst_name)
                alert_message = f"/// AEROVULPIS TARGET ACQUIRED ///\nINSTR: {inst_name}\nPRICE: {formatted_price}\nTARGET: {formatted_target}\nTIME: {now_wib}\n/// MONITORING COMPLETE ///"
                url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
                payload = {'chat_id': alert.get("chat_id"), 'text': alert_message}
                try:
                    requests.post(url, json=payload, timeout=10)
                    st.toast(f"TARGET ACQUIRED: {inst_name} @ {formatted_target}", icon="!")
                except Exception:
                    pass

st.markdown(f"""
<div class="main-title-container">
    <div class="main-logo-container">
        <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png" alt="AEROVULPIS" class="custom-logo">
    </div>
    <h1 class="main-title">AEROVULPIS</h1>
    <p class="subtitle-text">V3.5 ULTIMATE</p>
</div>
""", unsafe_allow_html=True)

# ##############################################################################
# SIDEBAR CONTROL CENTER (FINAL)
# ##############################################################################

with st.sidebar:
    st.markdown("""
    <div style='text-align:center;margin-bottom:-10px;'>
        <img src='https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png' style='width:48px;filter:drop-shadow(0 0 12px rgba(0,212,255,0.5));'>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<h2 style='font-family:Orbitron;text-align:center;font-size:16px;color:#00d4ff;letter-spacing:4px;margin-bottom:0;'>{t['control_center']}</h2>", unsafe_allow_html=True)

    tier_colors = {"free": "#556680", "trial": "#00d4ff", "weekly": "#00ff88", "monthly": "#ffcc00", "six_months": "#ff8800", "yearly": "#ff2a6d"}
    tier_names = {"free": "FREE", "trial": "TRIAL", "weekly": "WEEKLY", "monthly": "MONTHLY", "six_months": "6M PRO", "yearly": "ULTIMATE"}

    if not st.session_state.auth_session:
        st.markdown(f"""
        <div style="text-align:center;padding:14px;margin:8px 0;background:rgba(0,15,30,0.5);border:1px solid rgba(0,212,255,0.1);border-radius:4px;">
            <p style="font-family:Orbitron;font-size:10px;color:#00d4ff;margin-bottom:0;letter-spacing:2px;">{t['sign_in_prompt']}</p>
            <p style="font-family:Share Tech Mono;font-size:9px;color:#557799;margin:2px 0 0 0;">{t['sign_in_desc']}</p>
        </div>
        """, unsafe_allow_html=True)

        st.markdown('<div class="digital-auth-container">', unsafe_allow_html=True)
        with st.form("email_password_login_form"):
            st.markdown(f"""<p style="font-family:Orbitron;font-size:9px;color:#557799;letter-spacing:3px;margin:0 0 8px;">{t.get('login_title', 'AUTHENTICATION SYSTEM')}</p>""", unsafe_allow_html=True)

            email_input = st.text_input(t.get('login_email', 'EMAIL'), placeholder="ENTER EMAIL ADDRESS", key="login_email", label_visibility="collapsed")
            password_input = st.text_input(t.get('login_password', 'PASSWORD'), type="password", placeholder="ENTER PASSWORD", key="login_password", label_visibility="collapsed")

            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                login_submitted = st.form_submit_button(t.get('login_btn', 'LOGIN'), width='stretch', type="primary")
            with col_btn2:
                signup_submitted = st.form_submit_button(t.get('signup_btn', 'REGISTER'), width='stretch', type="primary")

            if login_submitted and email_input and password_input:
                try:
                    supabase_auth = get_supabase_client()
                    resp = supabase_auth.auth.sign_in_with_password({"email": email_input.strip(), "password": password_input})
                    if resp and resp.user:
                        user = resp.user
                        st.session_state.auth_session = resp.session.access_token if resp.session else "active"
                        st.session_state.user_id = user.id
                        st.session_state.user_name = user.user_metadata.get("full_name") or (user.email.split("@")[0] if user.email else "USER")
                        st.session_state.user_email = user.email or ""
                        st.session_state.user_avatar = user.user_metadata.get("avatar_url", "")
                        st.session_state.user_tier, _ = get_user_tier(user.id)
                        sync_user_to_supabase(user.id, user.email or "", st.session_state.user_name, st.session_state.user_avatar)
                        send_log(f"LOGIN: {st.session_state.user_name} ({st.session_state.user_email})")
                        st.rerun()
                    else:
                        st.error("INVALID EMAIL OR PASSWORD")
                except Exception as e:
                    error_msg = str(e)
                    if "Email not confirmed" in error_msg:
                        st.error("Email belum dikonfirmasi. Silakan cek inbox/spam Anda dan klik link konfirmasi sebelum login.")
                    elif "Invalid login credentials" in error_msg:
                        st.error("Email atau password salah. Gunakan LUPA PASSWORD jika Anda yakin email sudah benar, atau REGISTER untuk membuat akun baru.")
                    else:
                        st.error(f"AUTH FAILED: {error_msg}")

            if signup_submitted and email_input and password_input:
                if len(password_input) < 6:
                    st.error("PASSWORD MUST BE AT LEAST 6 CHARACTERS")
                else:
                    try:
                        supabase_auth = get_supabase_client()
                        resp = supabase_auth.auth.sign_up({
                            "email": email_input.strip(),
                            "password": password_input
                        })
                        # Cek apakah session ada - jika tidak, user sudah terdaftar
                        if resp and resp.user:
                            if resp.session:
                                # User baru berhasil dibuat
                                st.session_state.auth_session = resp.session.access_token
                                st.session_state.user_id = resp.user.id
                                st.session_state.user_name = resp.user.user_metadata.get("full_name") or (email_input.split("@")[0] if email_input else "USER")
                                st.session_state.user_email = resp.user.email or ""
                                st.session_state.user_avatar = ""
                                st.session_state.user_tier, _ = get_user_tier(resp.user.id)
                                sync_user_to_supabase(resp.user.id, resp.user.email or "", st.session_state.user_name, "")
                                send_log(f"REGISTER: {st.session_state.user_name} ({st.session_state.user_email})")
                                st.rerun()
                            else:
                                # User sudah terdaftar (tidak ada session)
                                st.warning("Email sudah terdaftar. Silakan LOGIN atau gunakan LUPA PASSWORD. Jika ingin mendaftar ulang, gunakan fitur DELETE ACCOUNT di bawah.")
                        else:
                            st.error("Registrasi gagal. Silakan coba lagi.")
                    except Exception as e:
                        err = str(e)
                        if "already registered" in err.lower() or "already exists" in err.lower():
                            st.warning("Email sudah terdaftar. Silakan LOGIN atau gunakan fitur LUPA PASSWORD / DELETE ACCOUNT di bawah.")
                        else:
                            st.error(f"REGISTRATION FAILED: {err}")
        st.markdown('</div>', unsafe_allow_html=True)

        # LUPA PASSWORD & DELETE ACCOUNT di luar form
        st.markdown("---")
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button("LUPA PASSWORD", key="forgot_password_btn", width='stretch'):
                st.session_state.show_forgot_password = True
        with col_f2:
            if st.button("DELETE ACCOUNT", key="show_delete_account_btn", width='stretch'):
                st.session_state.show_delete_account = True

        # Form Lupa Password
        if st.session_state.get("show_forgot_password", False):
            with st.container():
                reset_email = st.text_input("Email untuk reset password", key="reset_email", placeholder="Masukkan email terdaftar")
                col_r1, col_r2 = st.columns(2)
                with col_r1:
                    if st.button("Kirim Link Reset", key="send_reset_btn", width='stretch'):
                        if reset_email:
                            try:
                                supabase_auth = get_supabase_client()
                                supabase_auth.auth.reset_password_email(reset_email.strip())
                                st.success(f"Link reset password telah dikirim ke {reset_email}. Silakan cek inbox/spam Anda. Setelah klik link, Anda akan diarahkan ke halaman utama untuk mengatur password baru.")
                                st.session_state.show_forgot_password = False
                            except Exception as e:
                                st.error(f"Gagal: {str(e)}")
                        else:
                            st.warning("Masukkan email terlebih dahulu.")
                with col_r2:
                    if st.button("Batal", key="cancel_reset_btn", width='stretch'):
                        st.session_state.show_forgot_password = False
                        st.rerun()

        # Form Delete Account (HAPUS DARI AUTH.USERS HANYA DENGAN EMAIL)
        if st.session_state.get("show_delete_account", False):
            with st.container():
                st.warning("PERHATIAN: Ini akan menghapus akun Anda secara permanen dari sistem. Semua data (tier, aktivitas, cache) akan hilang.")
                del_email = st.text_input("Email akun yang akan dihapus", key="del_email", placeholder="Masukkan email")
                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    if st.button("HAPUS AKUN", key="confirm_delete_btn", width='stretch', type="primary"):
                        if del_email:
                            success, msg = delete_user_by_email(del_email.strip())
                            if success:
                                st.success(msg)
                                st.session_state.show_delete_account = False
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error(msg)
                        else:
                            st.warning("Masukkan email yang terdaftar.")
                with col_d2:
                    if st.button("Batal", key="cancel_delete_btn", width='stretch'):
                        st.session_state.show_delete_account = False
                        st.rerun()
        st.stop()

    # --- SUDAH LOGIN ---
    tier_color = tier_colors.get(st.session_state.user_tier, "#556680")
    tier_name = tier_names.get(st.session_state.user_tier, "FREE")
    avatar_url = st.session_state.get('user_avatar', '')

    st.markdown(f"""
    <div style="background:rgba(0,15,30,0.7);border:1px solid {tier_color}40;border-radius:4px;padding:16px;margin:8px 0;text-align:center;">
        {f'<img src="{avatar_url}" style="width:40px;height:40px;border-radius:2px;margin-bottom:10px;border:1px solid {tier_color};">' if avatar_url else '<div style="width:40px;height:40px;border-radius:2px;margin:0 auto 10px;background:linear-gradient(160deg,#001a33,#003060);display:flex;align-items:center;justify-content:center;font-size:18px;">V</div>'}
        <p style="font-family:Rajdhani;font-size:10px;color:#6688aa;margin:0;letter-spacing:1px;">{t['welcome']}</p>
        <p style="font-family:Orbitron;font-size:12px;color:#e0e6f0;margin:3px 0;letter-spacing:1px;">{st.session_state.user_name.upper()}</p>
        <p style="font-family:Share Tech Mono;font-size:8px;color:#557799;margin:2px 0;">{t['user_id_label']}: {st.session_state.user_id[:16]}...</p>
        <p style="font-family:Share Tech Mono;font-size:8px;color:#557799;margin:2px 0;">{t['tier_label']}: <span style="color:{tier_color};">{tier_name}</span></p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button(t['logout'], width='stretch', key="logout_btn"):
            try:
                get_supabase_client().auth.sign_out()
            except Exception:
                pass
            for key in ['auth_session', 'user_id', 'user_name', 'user_email', 'user_avatar']:
                st.session_state[key] = None
            st.session_state.user_tier = "free"
            st.session_state.show_activation = False
            st.rerun()
    with col2:
        if st.button(t['activate_key'], width='stretch', key="show_activation_btn"):
            st.session_state.show_activation = not st.session_state.show_activation

    if st.session_state.show_activation:
        st.markdown(f"""
        <div style="background:rgba(0,10,25,0.8);border:1px solid rgba(0,212,255,0.2);border-radius:4px;padding:18px;margin:12px 0;text-align:center;position:relative;">
            <div style="position:absolute;top:0;left:0;width:100%;height:1px;background:linear-gradient(90deg,transparent,#00d4ff,transparent);animation:scanHorizontal 3s infinite;"></div>
            <p style="font-family:Orbitron;font-size:11px;color:#00d4ff;margin:0 0 4px;letter-spacing:2px;">{t['license_activation']}</p>
            <p style="font-family:Share Tech Mono;font-size:8px;color:#557799;margin:0 0 12px;">{t['enter_license_key']}</p>
        """, unsafe_allow_html=True)
        key_input = st.text_input(t['enter_key'], value="", key="activation_key_input", placeholder=t['license_placeholder'], label_visibility="collapsed")
        if st.button(t['key_activate_button'], width='stretch', key="activate_btn_main", type="primary"):
            if key_input and st.session_state.user_id:
                with st.spinner(t['processing']):
                    time.sleep(2)
                    success, message = activate_key(st.session_state.user_id, key_input.strip().upper())
                if success:
                    st.session_state.user_tier, _ = get_user_tier(st.session_state.user_id)
                    st.success(f"{t['activation_success']}")
                    st.info(message)
                    st.balloons()
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(f"{t['activation_failed']}: {message}")
            else:
                st.warning("ENTER VALID LICENSE KEY")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<p style='font-family:Share Tech Mono;font-size:9px;color:#445566;text-align:center;margin:8px 0;'>AEROVULPIS V3.5 | DYNAMIHATCH</p>", unsafe_allow_html=True)
    st.caption("2026 | SYSTEM ACTIVE")

    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    ticker_display = f"{asset_name} [{ticker_input}]"

    st.markdown("---")

    tf_options = {"15M": {"period": "5d", "interval": "15m"}, "30M": {"period": "5d", "interval": "30m"}, "1H": {"period": "1mo", "interval": "1h"}, "3H": {"period": "1mo", "interval": "1h"}, "4H": {"period": "1mo", "interval": "1h"}, "1D": {"period": "1y", "interval": "1d"}, "1W": {"period": "2y", "interval": "1wk"}}
    selected_tf_display = st.selectbox(t['timeframe'], list(tf_options.keys()), index=0)
    period = tf_options[selected_tf_display]["period"]
    interval = tf_options[selected_tf_display]["interval"]

    user_is_premium = st.session_state.user_tier != "free"

    menu_options = ["Live Dashboard"]
    menu_icons = ["activity"]

    if user_is_premium:
        menu_options += ["AeroVulpis Sentinel", "Signal Analysis", "Market Sessions", "Market News", "Smart Alert Center", "Risk Management"]
        menu_icons += ["shield-shaded", "graph-up-arrow", "globe", "newspaper", "bell-fill", "shield-fill"]
    else:
        menu_options += ["AeroVulpis Sentinel (Premium)", "Signal Analysis (Premium)", "Market Sessions (Premium)", "Market News (Premium)", "Smart Alert Center (Premium)", "Risk Management (Premium)"]
        menu_icons += ["lock-fill"] * 6

    menu_options += ["Economic Radar", "Chatbot AI", "Tingkatkan Level", "Settings", "Help & Support"]
    menu_icons += ["calendar-event", "chat-dots", "rocket-takeoff", "gear", "question-circle"]

    menu_selection = option_menu(
        menu_title=t['navigation'],
        options=menu_options,
        icons=menu_icons,
        menu_icon="cast", default_index=0,
        styles={
            "container": {"padding": "5!important", "background-color": "transparent"},
            "icon": {"color": "#00d4ff", "font-size": "13px"},
            "nav-link": {"font-size": "11px", "text-align": "left", "margin": "2px 0", "padding": "10px 12px", "border-radius": "3px", "font-family": "Rajdhani", "font-weight": "500", "letter-spacing": "1px", "background": "rgba(0,212,255,0.015)", "border": "1px solid rgba(0,212,255,0.06)", "transition": "all 0.25s ease"},
            "nav-link-selected": {"background": "linear-gradient(160deg,rgba(0,48,96,0.4),rgba(0,28,64,0.6))", "border": "1px solid #00d4ff", "color": "#00d4ff", "box-shadow": "0 0 18px rgba(0,212,255,0.12)", "font-weight": "700"},
        }
    )

    if "(Premium)" in menu_selection and not user_is_premium:
        st.error(f"**{t['premium_lock']}**")
        st.info(t['premium_msg'])
        st.markdown("[UPGRADE NOW](/Tingkatkan%20Level)")
        st.stop()

    user_limits = LIMITS.get(st.session_state.user_tier, LIMITS["free"])
    st.markdown("---")
    st.markdown(f"""
    <div style="background:rgba(0,15,30,0.5);border:1px solid rgba(0,212,255,0.1);border-radius:4px;padding:12px;margin-top:8px;">
        <p style="font-family:Orbitron;font-size:8px;color:#557799;margin:0 0 8px;letter-spacing:2px;">{t['daily_usage_label']}</p>
        <div style="margin-bottom:6px;">
            <p style="font-family:Share Tech Mono;font-size:10px;color:#00d4ff;margin:2px 0;display:flex;justify-content:space-between;">
                <span>AI ANALYSIS</span><span>{st.session_state.daily_analysis_count}/{user_limits['analysis_per_day']}</span>
            </p>
            <div style="background:rgba(255,255,255,0.05);height:3px;border-radius:1px;overflow:hidden;">
                <div style="background:#00d4ff;width:{min(100,(st.session_state.daily_analysis_count/user_limits['analysis_per_day'])*100)}%;height:100%;border-radius:1px;"></div>
            </div>
        </div>
        <div>
            <p style="font-family:Share Tech Mono;font-size:10px;color:#00ff88;margin:2px 0;display:flex;justify-content:space-between;">
                <span>CHATBOT</span><span>{st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']}</span>
            </p>
            <div style="background:rgba(255,255,255,0.05);height:3px;border-radius:1px;overflow:hidden;">
                <div style="background:#00ff88;width:{min(100,(st.session_state.daily_chatbot_count/user_limits['chatbot_per_day'])*100)}%;height:100%;border-radius:1px;"></div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)