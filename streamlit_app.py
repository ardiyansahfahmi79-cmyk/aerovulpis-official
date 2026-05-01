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
        supabase_admin = get_supabase_admin()
        supabase_admin.table("user_tiers").upsert({
            "user_id": user_id, "tier": tier,
            "expired_at": expired_at,
            "activated_at": datetime.now(pytz.UTC).isoformat()
        }).execute()
        supabase.table("activation_keys").update({
            "is_used": True, "used_by": user_id,
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
                "email": email, "name": name, "avatar": avatar,
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).eq("id", user_id).execute()
        else:
            supabase.table("users").insert({
                "id": user_id, "email": email, "name": name, "avatar": avatar,
                "created_at": datetime.now(pytz.UTC).isoformat(),
                "last_login": datetime.now(pytz.UTC).isoformat()
            }).execute()
            try:
                supabase_admin = get_supabase_admin()
                supabase_admin.table("user_tiers").insert({
                    "user_id": user_id, "tier": "free",
                    "activated_at": datetime.now(pytz.UTC).isoformat()
                }).execute()
            except Exception:
                try:
                    supabase.table("user_tiers").insert({
                        "user_id": user_id, "tier": "free",
                        "activated_at": datetime.now(pytz.UTC).isoformat()
                    }).execute()
                except Exception:
                    pass
    except Exception:
        pass

# ##############################################################################
# AI ANALYSIS CACHE SYSTEM
# ##############################################################################

def get_cached_ai_analysis(asset_name, cache_type="sentinel"):
    table_name = "ai_cache_sentinel" if cache_type == "sentinel" else "ai_cache_deep"
    try:
        supabase = get_supabase_client()
        cutoff = (datetime.now(pytz.UTC) - timedelta(minutes=15)).isoformat()
        res = supabase.table(table_name).select("*").eq("asset_name", asset_name).gte("created_at", cutoff).order("created_at", desc=True).limit(1).execute()
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
            "asset_name": asset_name, "analysis": analysis,
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
                st.session_state.user_name = user.user_metadata.get("full_name") or user.user_metadata.get("name") or (user.email.split("@")[0] if user.email else "USER")
                st.session_state.user_email = user.email or ""
                st.session_state.user_avatar = user.user_metadata.get("avatar_url") or user.user_metadata.get("picture") or ""
                st.session_state.user_tier, _ = get_user_tier(user.id)
                sync_user_to_supabase(user.id, user.email or "", st.session_state.user_name, st.session_state.user_avatar)
                send_log(f"AUTH: {st.session_state.user_name} ({st.session_state.user_email}) - Session Restored")
                return True
        except Exception as e:
            print(f"DEBUG: No existing session - {str(e)[:100]}")
    return False

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

if "lang" not in st.session_state:
    st.session_state.lang = "ID"
if "cached_analysis" not in st.session_state:
    st.session_state.cached_analysis = {}
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
if "show_signup" not in st.session_state:
    st.session_state.show_signup = False
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
if "messages" not in st.session_state:
    st.session_state.messages = []
if "active_alerts" not in st.session_state:
    st.session_state.active_alerts = []
if "last_news_fetch" not in st.session_state:
    st.session_state.last_news_fetch = {}

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
# LANGUAGE DICTIONARY (ID & EN)
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
        "login_password": "PASSWORD", "login_btn": "ACCESS TERMINAL",
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
        "or_continue_with": "OR CONTINUE WITH", "login_google": "AUTHENTICATE WITH GOOGLE"
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
        "login_password": "PASSWORD", "login_btn": "ACCESS TERMINAL",
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
        "or_continue_with": "OR CONTINUE WITH", "login_google": "AUTHENTICATE WITH GOOGLE"
    }
}

t = translations[st.session_state.lang]

# ##############################################################################
# CYBER-TECH CSS
# ##############################################################################

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
    
    /* RISK MANAGEMENT COMPACT CYBER-TECH */
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
</style>
""", unsafe_allow_html=True)
