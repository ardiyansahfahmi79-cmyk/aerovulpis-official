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
# GOOGLE OAUTH AUTHENTICATION (REVISED - MULTI FALLBACK)
# ##############################################################################

def handle_google_oauth():
    """
    Menangani autentikasi Google OAuth via Supabase Auth.
    
    Alur:
    1. Cek existing session dari Supabase (user sudah login)
    2. Handle callback dari Google (ada 'code' di URL)
    3. Fallback: cek session lagi setelah callback
    4. Fallback 2: panggil REST API Supabase langsung
    
    KONFIGURASI YANG DIPERLUKAN:
    - Google Cloud Console:
      Authorized JavaScript origins: https://bqdugkmmnbxlftuxqtdg.supabase.co
      Authorized redirect URIs: https://bqdugkmmnbxlftuxqtdg.supabase.co/auth/v1/callback
    - Supabase Dashboard → Authentication → Providers → Google:
      Enable = ON, isi Client ID & Secret, Skip nonce checks = OFF
    - Supabase Dashboard → Authentication → URL Configuration:
      Site URL = https://[app].streamlit.app
    """
    
    # ========== STEP 1: Cek existing session ==========
    if not st.session_state.get("auth_session"):
        try:
            supabase = get_supabase_client()
            session = supabase.auth.get_session()
            
            if session and session.user:
                user = session.user
                print(f"DEBUG: Existing session found for {user.email}")
                
                st.session_state.auth_session = session.access_token
                st.session_state.user_id = user.id
                st.session_state.user_name = user.user_metadata.get("full_name") or \
                                           user.user_metadata.get("name") or \
                                           (user.email.split("@")[0] if user.email else "USER")
                st.session_state.user_email = user.email or ""
                st.session_state.user_avatar = user.user_metadata.get("avatar_url") or \
                                              user.user_metadata.get("picture") or ""
                st.session_state.user_tier, _ = get_user_tier(user.id)
                
                # Sync ke database
                sync_user_to_supabase(
                    user.id, 
                    user.email or "", 
                    st.session_state.user_name, 
                    st.session_state.user_avatar
                )
                send_log(f"AUTH: {st.session_state.user_name} ({st.session_state.user_email}) - Session Restored")
                return True
        except Exception as e:
            print(f"DEBUG: No existing session - {str(e)[:100]}")
    
    # ========== STEP 2: Handle OAuth Callback ==========
    query_params = st.query_params
    
    if "code" in query_params:
        code = query_params["code"]
        print(f"DEBUG: OAuth callback detected, code length: {len(code)}")
        
        # --- METODE A: exchange_code_for_session (standar) ---
        try:
            supabase = get_supabase_client()
            
            auth_response = supabase.auth.exchange_code_for_session({
                "auth_code": code
            })
            
            if auth_response and auth_response.user:
                user = auth_response.user
                print(f"DEBUG: Method A success - {user.email}")
                
                st.session_state.auth_session = auth_response.session.access_token if auth_response.session else "active"
                st.session_state.user_id = user.id
                st.session_state.user_name = user.user_metadata.get("full_name") or \
                                           user.user_metadata.get("name") or \
                                           (user.email.split("@")[0] if user.email else "USER")
                st.session_state.user_email = user.email or ""
                st.session_state.user_avatar = user.user_metadata.get("avatar_url") or \
                                              user.user_metadata.get("picture") or ""
                st.session_state.user_tier, _ = get_user_tier(user.id)
                
                sync_user_to_supabase(user.id, user.email or "", st.session_state.user_name, st.session_state.user_avatar)
                send_log(f"AUTH: {st.session_state.user_name} ({st.session_state.user_email}) - Method A")
                
                st.query_params.clear()
                st.rerun()
                
        except Exception as e1:
            print(f"DEBUG: Method A failed - {str(e1)[:100]}")
            
            # --- METODE B: get_session setelah callback ---
            try:
                time.sleep(1)  # Tunggu 1 detik untuk session tersimpan
                supabase = get_supabase_client()
                session = supabase.auth.get_session()
                
                if session and session.user:
                    user = session.user
                    print(f"DEBUG: Method B success - {user.email}")
                    
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
                    send_log(f"AUTH: {st.session_state.user_name} ({st.session_state.user_email}) - Method B")
                    
                    st.query_params.clear()
                    st.rerun()
                    
            except Exception as e2:
                print(f"DEBUG: Method B failed - {str(e2)[:100]}")
                
                # --- METODE C: Manual token exchange via REST API ---
                try:
                    supabase_url = st.secrets["supabase_url"]
                    supabase_key = st.secrets["supabase_key"]
                    
                    # Panggil Supabase Auth REST API langsung
                    response = requests.post(
                        f"{supabase_url}/auth/v1/token?grant_type=pkce",
                        headers={
                            "apikey": supabase_key,
                            "Content-Type": "application/json"
                        },
                        json={
                            "auth_code": code,
                            "code_verifier": ""
                        },
                        timeout=10
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        print(f"DEBUG: Method C success")
                        
                        # Simpan token
                        st.session_state.auth_session = data.get("access_token", "active")
                        
                        # Ambil user info
                        user_response = requests.get(
                            f"{supabase_url}/auth/v1/user",
                            headers={
                                "apikey": supabase_key,
                                "Authorization": f"Bearer {data.get('access_token')}"
                            },
                            timeout=10
                        )
                        
                        if user_response.status_code == 200:
                            user_data = user_response.json()
                            user_id = user_data.get("id")
                            user_email = user_data.get("email", "")
                            user_name = user_data.get("user_metadata", {}).get("full_name") or \
                                       user_data.get("user_metadata", {}).get("name") or \
                                       (user_email.split("@")[0] if user_email else "USER")
                            user_avatar = user_data.get("user_metadata", {}).get("avatar_url") or \
                                         user_data.get("user_metadata", {}).get("picture") or ""
                            
                            st.session_state.user_id = user_id
                            st.session_state.user_name = user_name
                            st.session_state.user_email = user_email
                            st.session_state.user_avatar = user_avatar
                            st.session_state.user_tier, _ = get_user_tier(user_id)
                            
                            sync_user_to_supabase(user_id, user_email, user_name, user_avatar)
                            send_log(f"AUTH: {user_name} ({user_email}) - Method C")
                            
                            st.query_params.clear()
                            st.rerun()
                            
                except Exception as e3:
                    error_msg = f"AUTH FAILED: A={str(e1)[:50]}, B={str(e2)[:50]}, C={str(e3)[:50]}"
                    print(f"DEBUG: {error_msg}")
                    st.sidebar.error(f"AUTHENTICATION ERROR: {str(e1)}")
                    send_log(error_msg)
    
    return False

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
</style>
""", unsafe_allow_html=True)