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
# ##############################################################################
# MARKET SESSIONS MONITOR
# ##############################################################################

def market_session_status():
    """
    Real-time global market session tracker.
    
    Menampilkan status 3 sesi pasar utama:
    - Asian Session (Tokyo): 06:00 - 15:00 WIB
    - European Session (London): 14:00 - 23:00 WIB
    - American Session (New York): 19:00 - 04:00 WIB
    
    Fitur:
    - Progress bar real-time untuk setiap sesi
    - Golden Hour detection (London + New York overlap)
    - SMC (Smart Money Concept) strategy recommendations
    """
    tz = pytz.timezone('Asia/Jakarta')
    now = datetime.now(tz)
    current_time = now.time()
    
    sessions = [
        {
            "name": "ASIAN SESSION",
            "market": "TOKYO",
            "start": dt_time(6, 0),
            "end": dt_time(15, 0),
            "color": "#00ff88"
        },
        {
            "name": "EUROPEAN SESSION",
            "market": "LONDON",
            "start": dt_time(14, 0),
            "end": dt_time(23, 0),
            "color": "#00d4ff"
        },
        {
            "name": "AMERICAN SESSION",
            "market": "NEW YORK",
            "start": dt_time(19, 0),
            "end": dt_time(4, 0),
            "color": "#ff2a6d"
        }
    ]
    
    st.markdown('<div class="session-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="cyber-glow-text" style="text-align:center; font-size:22px; margin-bottom:25px; letter-spacing:5px;">GLOBAL MARKET SESSIONS</h2>', unsafe_allow_html=True)
    
    active_sessions = []
    
    for sess in sessions:
        # Determine if session is currently active
        is_active = False
        if sess["start"] < sess["end"]:
            # Normal session (start < end)
            is_active = sess["start"] <= current_time <= sess["end"]
        else:
            # Session crosses midnight (start > end)
            is_active = current_time >= sess["start"] or current_time <= sess["end"]
        
        # Status badge dengan neon effect
        if is_active:
            status_html = f'<span style="padding:4px 14px; border-radius:2px; background:rgba(0,255,136,0.07); border:1px solid rgba(0,255,136,0.35); color:#00ff88; font-size:9px; font-family:Orbitron; letter-spacing:2px;">ACTIVE</span>'
        else:
            status_html = f'<span style="padding:4px 14px; border-radius:2px; background:rgba(255,42,109,0.04); border:1px solid rgba(255,42,109,0.18); color:#556680; font-size:9px; font-family:Orbitron; letter-spacing:2px; opacity:0.6;">CLOSED</span>'
        
        if is_active:
            active_sessions.append(sess["name"])
        
        # Calculate progress percentage for active sessions
        progress = 0
        if is_active:
            now_minutes = now.hour * 60 + now.minute
            start_minutes = sess["start"].hour * 60 + sess["start"].minute
            end_minutes = sess["end"].hour * 60 + sess["end"].minute
            
            # Adjust for sessions crossing midnight
            if end_minutes < start_minutes:
                end_minutes += 24 * 60
            if now_minutes < start_minutes and sess["start"] > sess["end"]:
                now_minutes += 24 * 60
            
            total_duration = end_minutes - start_minutes
            elapsed = now_minutes - start_minutes
            progress = min(100, max(0, int((elapsed / total_duration) * 100)))
        
        # Render session card with progress bar
        st.markdown(f"""
        <div style="background:rgba(0,18,36,0.5); border:1px solid rgba(0,212,255,0.08); border-radius:4px; padding:18px; margin-bottom:10px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                <div>
                    <span style="font-family:Orbitron; font-weight:700; color:{sess['color']}; font-size:14px; letter-spacing:2px;">{sess['name']}</span>
                    <span style="font-family:Share Tech Mono; font-size:10px; color:#557799; margin-left:8px;">{sess['market']}</span>
                </div>
                {status_html}
            </div>
            <div style="font-family:Share Tech Mono; font-size:11px; color:#6688aa; margin-bottom:10px;">
                {sess['start'].strftime('%H:%M')} - {sess['end'].strftime('%H:%M')} WIB
            </div>
            <div style="background:rgba(255,255,255,0.03); height:4px; border-radius:2px; overflow:hidden;">
                <div style="background:{sess['color'] if is_active else '#333'}; width:{progress if is_active else 0}%; height:100%; border-radius:2px; transition:width 0.5s ease; box-shadow:0 0 12px {sess['color'] if is_active else 'transparent'};"></div>
            </div>
            <div style="font-family:Share Tech Mono; font-size:9px; color:{sess['color'] if is_active else '#445566'}; text-align:right; margin-top:4px;">
                {f'PROGRESS: {progress}%' if is_active else 'STANDBY'}
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    # Golden Hour Detection (London + New York overlap: 19:00 - 23:00 WIB)
    is_golden = (dt_time(19, 0) <= current_time <= dt_time(23, 0))
    if is_golden:
        st.markdown("""
        <div style="text-align:center; padding:16px; background:rgba(0,212,255,0.04); border:1px solid rgba(0,212,255,0.28); border-radius:4px; margin-top:12px;">
            <p class="cyber-glow-text" style="margin:0; font-size:18px; letter-spacing:3px;">GOLDEN HOUR ACTIVE</p>
            <p style="font-family:Share Tech Mono; color:#8899bb; margin:4px 0 0 0; font-size:10px;">LONDON + NEW YORK OVERLAP | MAXIMUM LIQUIDITY | HIGH VOLATILITY</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Strategy Recommendation based on active sessions
    strategy_text = "AWAITING MARKET OPEN"
    strategy_detail = "System on standby for next active session"
    
    if "ASIAN SESSION" in active_sessions and len(active_sessions) == 1:
        strategy_text = "RANGE TRADING PROTOCOL"
        strategy_detail = "Focus on liquidity sweeps and Asian range breakout patterns"
    elif is_golden:
        strategy_text = "HIGH VOLATILITY PROTOCOL"
        strategy_detail = "Order block mitigations and FVG entries. Tight spreads, maximum momentum"
    elif "EUROPEAN SESSION" in active_sessions:
        strategy_text = "TREND FOLLOWING PROTOCOL"
        strategy_detail = "London breakout patterns. Monitor displacement moves for entry confirmation"
    elif "AMERICAN SESSION" in active_sessions:
        strategy_text = "REVERSAL PROTOCOL"
        strategy_detail = "NY open manipulation watch. Late session reversals probability elevated"
    
    st.markdown(f"""
    <div style="margin-top:20px; padding:18px; border:1px solid rgba(0,212,255,0.2); border-radius:4px; background:rgba(0,212,255,0.03); text-align:center;">
        <p class="cyber-glow-text" style="font-size:12px; margin-bottom:6px; letter-spacing:2px;">ACTIVE STRATEGY [SMC FRAMEWORK]</p>
        <p style="font-family:Orbitron; font-size:16px; color:#e0e6f0; margin:0; letter-spacing:2px;">{strategy_text}</p>
        <p style="font-family:Share Tech Mono; font-size:10px; color:#6688aa; margin:6px 0 0 0;">{strategy_detail}</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown('</div>', unsafe_allow_html=True)

# ##############################################################################
# INSTRUMENTS DATABASE
# ##############################################################################

instruments = {
    "FOREX": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CHF": "USDCHF=X"
    },
    "CRYPTO": {
        "BITCOIN": "BTC-USD",
        "ETHEREUM": "ETH-USD",
        "SOLANA": "SOL-USD",
        "BNB": "BNB-USD",
        "XRP": "XRP-USD"
    },
    "INDICES": {
        "NASDAQ-100": "^IXIC",
        "S&P 500": "^GSPC",
        "DOW JONES": "^DJI",
        "DAX 40": "^GDAXI",
        "IHSG": "^JKSE"
    },
    "US STOCKS": {
        "NVIDIA": "NVDA",
        "APPLE": "AAPL",
        "TESLA": "TSLA",
        "MICROSOFT": "MSFT",
        "AMAZON": "AMZN"
    },
    "ID STOCKS": {
        "BBRI": "BBRI.JK",
        "BBCA": "BBCA.JK",
        "TLKM": "TLKM.JK",
        "ASII": "ASII.JK",
        "BMRI": "BMRI.JK"
    },
    "COMMODITIES": {
        "GOLD (XAUUSD)": "GC=F",
        "SILVER (XAGUSD)": "SI=F",
        "CRUDE OIL (WTI)": "CL=F",
        "NATURAL GAS": "NG=F",
        "COPPER": "HG=F",
        "PALLADIUM": "PA=F",
        "PLATINUM": "PL=F"
    }
}

# ##############################################################################
# NEWS AGGREGATOR (DENGAN CURRENTS API)
# ##############################################################################

def get_news_data(category="General", max_articles=10):
    """
    Mengambil berita finansial dari multiple sources.
    
    Sumber berita (berdasarkan prioritas):
    1. Currents API (berita finansial terkini)
    2. Marketaux API (berita global)
    3. Tiingo API (berita saham & forex)
    4. NewsAPI (fallback)
    
    Cache berlaku 5 menit. Berita difilter 6 jam terakhir.
    """
    from news_cache_manager import initialize_news_cache, should_update_news, get_cached_news, update_news_cache
    
    # Initialize cache system
    initialize_news_cache()
    
    # Force refresh mechanism
    force_refresh = False
    if "last_news_fetch" not in st.session_state:
        st.session_state.last_news_fetch = {}
    
    last_fetch = st.session_state.last_news_fetch.get(category)
    if last_fetch is None or (datetime.now() - last_fetch).total_seconds() > 300:
        force_refresh = True
        st.session_state.last_news_fetch[category] = datetime.now()
    
    # Return cache if valid
    if not force_refresh and not should_update_news(category):
        cached_news = get_cached_news(category)
        if cached_news:
            return cached_news, None

    berita_final = []
    urls_terpakai = set()
    
    # Category mapping
    category_map = {
        "Stock": "stocks,equities,earnings",
        "Konflik": "geopolitics,war,conflict,sanctions",
        "Gold & Silver": "gold,silver,precious metals,commodities",
        "Forex": "forex,currency,central banks,interest rates",
        "General": "finance,economy,market"
    }
    api_query = category_map.get(category, "finance")

    # 1. Currents API (prioritas utama)
    if currents_api_key:
        try:
            url_c = f"https://api.currentsapi.services/v1/latest-news?apiKey={currents_api_key}&language=en&category={category.lower()}&limit=15"
            res_c = requests.get(url_c, timeout=10).json()
            if res_c.get('news'):
                for item in res_c.get('news', []):
                    if item.get('url') and item['url'] not in urls_terpakai:
                        berita_final.append({
                            'publishedAt': item.get('published', datetime.now().isoformat()),
                            'title': item.get('title', 'NO TITLE'),
                            'description': item.get('description', ''),
                            'source': 'CURRENTS FINANCIAL',
                            'url': item['url']
                        })
                        urls_terpakai.add(item['url'])
        except Exception:
            pass

    # 2. Marketaux API
    if marketaux_key:
        try:
            since_date = (datetime.now() - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M')
            url_m = f"https://api.marketaux.com/v1/news/all?api_token={marketaux_key}&language=en&search={api_query}&limit=15&published_after={since_date}"
            res_m = requests.get(url_m, timeout=10).json()
            if res_m.get('data'):
                for item in res_m.get('data', []):
                    if item.get('url') and item['url'] not in urls_terpakai:
                        berita_final.append({
                            'publishedAt': item.get('published_at', datetime.now().isoformat()),
                            'title': item.get('title', 'NO TITLE'),
                            'description': item.get('description', ''),
                            'source': 'GLOBAL FINANCIAL NETWORK',
                            'url': item['url']
                        })
                        urls_terpakai.add(item['url'])
        except Exception:
            pass

    # 3. Tiingo API
    tiingo_key = st.secrets.get("TIINGO_KEY") or os.getenv("TIINGO_KEY")
    if tiingo_key:
        try:
            start_date = (datetime.now() - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S')
            url_t = f"https://api.tiingo.com/tiingo/news?token={tiingo_key}&limit=15&startDate={start_date}"
            if category == "Stock":
                url_t += "&tags=stocks"
            elif category == "Forex":
                url_t += "&tags=forex"
            res_t = requests.get(url_t, timeout=10).json()
            if isinstance(res_t, list):
                for item in res_t:
                    if item.get('url') and item['url'] not in urls_terpakai:
                        berita_final.append({
                            'publishedAt': item.get('publishedDate', datetime.now().isoformat()),
                            'title': item.get('title', 'NO TITLE'),
                            'description': item.get('description', item.get('title', '')),
                            'source': 'FINANCIAL NEWS NETWORK',
                            'url': item['url']
                        })
                        urls_terpakai.add(item['url'])
        except Exception:
            pass

    # 4. NewsAPI (fallback)
    newsapi_key = st.secrets.get("NEWSAPI_KEY") or os.getenv("NEWSAPI_KEY")
    if newsapi_key and len(berita_final) < 5:
        try:
            url_n = f"https://newsapi.org/v2/everything?q={api_query}&language=en&pageSize=10&sortBy=publishedAt&apiKey={newsapi_key}"
            res_n = requests.get(url_n, timeout=10).json()
            if res_n.get('articles'):
                for item in res_n.get('articles', []):
                    if item.get('url') and item['url'] not in urls_terpakai:
                        berita_final.append({
                            'publishedAt': item.get('publishedAt', datetime.now().isoformat()),
                            'title': item.get('title', 'NO TITLE'),
                            'description': item.get('description', ''),
                            'source': item.get('source', {}).get('name', 'NEWS NETWORK'),
                            'url': item['url']
                        })
                        urls_terpakai.add(item['url'])
        except Exception:
            pass

    # Return cache if all APIs fail
    if not berita_final:
        cached_news = get_cached_news(category)
        if cached_news:
            return cached_news, "DISPLAYING CACHED DATA | LIVE FEED UNAVAILABLE"
        return [], "NO NEWS AVAILABLE"

    # Sort by newest first
    try:
        berita_final = sorted(berita_final, key=lambda x: str(x.get('publishedAt', '')), reverse=True)
    except Exception:
        pass
    
    # Limit results
    berita_final = berita_final[:max_articles]
    
    # Convert to WIB timezone
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
    
    # Update cache
    update_news_cache(category, berita_final)
    return berita_final, None

# ##############################################################################
# SMART ALERT MONITORING SYSTEM (REVISED - target_value SUPPORT)
# ##############################################################################

def check_smart_alerts():
    """
    Continuous monitoring of active price alerts.
    
    Flow:
    1. Ambil semua alert yang belum triggered
    2. Cek harga terkini dari database cache
    3. Bandingkan dengan target harga (dukung target_value FLOAT)
    4. Jika tercapai, kirim notifikasi Telegram
    5. Tandai alert sebagai triggered
    """
    if "active_alerts" not in st.session_state or not st.session_state.active_alerts:
        return

    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or st.secrets.get("TELEGRAM_BOT_TOKEN")
    if not telegram_bot_token:
        return

    # Collect unique instruments
    unique_instruments = list(set([
        a["instrument"] for a in st.session_state.active_alerts
        if not a.get("triggered", False)
    ]))
    
    if not unique_instruments:
        return

    # Map instruments to tickers
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

    # Get current prices
    current_prices = {}
    for inst in unique_instruments:
        # Try database cache first
        cached_data = get_cached_market_price_full(inst)
        if cached_data and cached_data.get("price"):
            current_prices[inst] = cached_data["price"]
        else:
            # Fallback to live data
            ticker = instrument_to_ticker.get(inst)
            if ticker:
                m_data = get_market_data(ticker)
                if m_data:
                    current_prices[inst] = m_data.get("price")

    # Check each alert
    for alert in st.session_state.active_alerts:
        if not alert.get("triggered", False):
            inst_name = alert.get("instrument")
            current_price = current_prices.get(inst_name)
            
            if current_price is None:
                continue
            
            # ✅ AMBIL target_raw DAN target_value
            target_raw = alert.get("target")           # TEXT: "2,650.00" atau FLOAT lama
            target_value = alert.get("target_value")   # FLOAT: 2650.0 (dari widget baru)
            condition = alert.get("condition")
            
            # ✅ TENTUKAN target_num (numerik) untuk perbandingan
            if target_value is not None and isinstance(target_value, (int, float)) and target_value > 0:
                target_num = float(target_value)
            else:
                # Fallback: parse dari target_raw
                try:
                    target_num = float(str(target_raw).replace(",", ""))
                except (ValueError, AttributeError):
                    target_num = 0.0
            
            triggered = False

            if condition == "bullish" and current_price >= target_num:
                triggered = True
            elif condition == "bearish" and current_price <= target_num:
                triggered = True

            if triggered:
                alert["triggered"] = True
                now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%Y-%m-%d %H:%M:%S WIB")
                
                # Format prices
                formatted_price = format_price_display(current_price, inst_name)
                # ✅ Gunakan target_raw untuk tampilan, atau format dari target_num
                if target_raw and isinstance(target_raw, str) and "," in str(target_raw):
                    formatted_target = str(target_raw)
                else:
                    formatted_target = format_price_display(target_num, inst_name)
                
                # Build notification
                alert_message = (
                    f"/// AEROVULPIS TARGET ACQUIRED ///\n"
                    f"INSTR: {inst_name}\n"
                    f"PRICE: {formatted_price}\n"
                    f"TARGET: {formatted_target}\n"
                    f"TIME: {now_wib}\n"
                    f"/// MONITORING COMPLETE ///"
                )
                
                # Send via Telegram
                url = f"https://api.telegram.org/bot{telegram_bot_token}/sendMessage"
                payload = {
                    'chat_id': alert.get("chat_id"),
                    'text': alert_message
                }
                try:
                    requests.post(url, json=payload, timeout=10)
                    st.toast(f"TARGET ACQUIRED: {inst_name} @ {formatted_target}", icon="!")
                except Exception:
                    pass
# ##############################################################################
# UI HEADER
# ##############################################################################

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
# SIDEBAR CONTROL CENTER
# ##############################################################################

with st.sidebar:
    # Sidebar logo
    st.markdown("""
    <div style='text-align:center; margin-bottom:-10px;'>
        <img src='https://files.manuscdn.com/user_upload_by_module/session_file/310519663520709901/oOIKIIkSvIdagiSw.png' style='width:48px; filter:drop-shadow(0 0 12px rgba(0,212,255,0.5));'>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"<h2 style='font-family:Orbitron; text-align:center; font-size:16px; color:#00d4ff; letter-spacing:4px; margin-bottom:0;'>{t['control_center']}</h2>", unsafe_allow_html=True)
    
    # Tier colors
    tier_colors = {
        "free": "#556680",
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
        "six_months": "6M PRO",
        "yearly": "ULTIMATE"
    }
    
    # ====================== AUTHENTICATION SECTION ======================
    if st.session_state.auth_session and st.session_state.user_name:
        # User is logged in
        tier_color = tier_colors.get(st.session_state.user_tier, "#556680")
        tier_name = tier_names.get(st.session_state.user_tier, "FREE")
        avatar_url = st.session_state.get('user_avatar', '')
        
        # User info card
        st.markdown(f"""
        <div style="background:rgba(0,15,30,0.7); border:1px solid {tier_color}40; border-radius:4px; padding:16px; margin:8px 0; text-align:center;">
            {f'<img src="{avatar_url}" style="width:40px;height:40px;border-radius:2px;margin-bottom:10px;border:1px solid {tier_color};">' if avatar_url else '<div style="width:40px;height:40px;border-radius:2px;margin:0 auto 10px;background:linear-gradient(160deg,#001a33,#003060);display:flex;align-items:center;justify-content:center;font-size:18px;">V</div>'}
            <p style="font-family:Rajdhani;font-size:10px;color:#6688aa;margin:0;letter-spacing:1px;">{t['welcome']}</p>
            <p style="font-family:Orbitron;font-size:12px;color:#e0e6f0;margin:3px 0;letter-spacing:1px;">{st.session_state.user_name.upper()}</p>
            <p style="font-family:Share Tech Mono;font-size:8px;color:#557799;margin:2px 0;">{t['user_id_label']}: {st.session_state.user_id[:16]}...</p>
            <p style="font-family:Share Tech Mono;font-size:8px;color:#557799;margin:2px 0;">{t['tier_label']}: <span style="color:{tier_color};">{tier_name}</span></p>
        </div>
        """, unsafe_allow_html=True)
        
        # Logout & Activation buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button(t['logout'], use_container_width=True, key="google_logout"):
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
            if st.button(t['activate_key'], use_container_width=True, key="show_activation_btn"):
                st.session_state.show_activation = not st.session_state.show_activation
        
        # License Activation Form
        if st.session_state.show_activation:
            st.markdown(f"""
            <div style="background:rgba(0,10,25,0.8);border:1px solid rgba(0,212,255,0.2);border-radius:4px;padding:18px;margin:12px 0;text-align:center;position:relative;">
                <div style="position:absolute;top:0;left:0;width:100%;height:1px;background:linear-gradient(90deg,transparent,#00d4ff,transparent);animation:scanHorizontal 3s infinite;"></div>
                <p style="font-family:Orbitron;font-size:11px;color:#00d4ff;margin:0 0 4px;letter-spacing:2px;">{t['license_activation']}</p>
                <p style="font-family:Share Tech Mono;font-size:8px;color:#557799;margin:0 0 12px;">{t['enter_license_key']}</p>
            """, unsafe_allow_html=True)
            
            key_input = st.text_input(
                t['enter_key'],
                value="",
                key="activation_key_input",
                placeholder=t['license_placeholder'],
                label_visibility="collapsed"
            )
            st.markdown('<style>div[data-testid="stTextInput"] input{background:rgba(0,0,0,0.6)!important;border:1px solid rgba(0,212,255,0.3)!important;color:#00ff88!important;font-family:Share Tech Mono!important;letter-spacing:3px!important;text-align:center!important;font-size:14px!important;padding:10px!important;}</style>', unsafe_allow_html=True)
            
            if st.button(t['key_activate_button'], use_container_width=True, key="activate_btn_main", type="primary"):
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
    else:
        # User not logged in - Google Sign-In
        st.markdown(f"""
        <div style="text-align:center;padding:18px;margin:8px 0;background:rgba(0,15,30,0.5);border:1px solid rgba(0,212,255,0.1);border-radius:4px;">
            <p style="font-family:Orbitron;font-size:10px;color:#00d4ff;margin-bottom:6px;letter-spacing:2px;">{t['sign_in_prompt']}</p>
            <p style="font-family:Share Tech Mono;font-size:9px;color:#557799;margin-bottom:14px;">{t['sign_in_desc']}</p>
        """, unsafe_allow_html=True)
        
        try:
            supabase_auth = get_supabase_client()
            redirect_url = st.secrets.get("REDIRECT_URL", "https://aerovulpis.streamlit.app")
            auth_response = supabase_auth.auth.sign_in_with_oauth({
                "provider": "google",
                "options": {
                    "redirect_to": redirect_url,
                    "query_params": {"prompt": "select_account"}
                }
            })
            google_auth_link = auth_response.url if auth_response else "#"
            st.markdown(f"""
            <a href="{google_auth_link}" target="_self" style="text-decoration:none;">
                <div class="google-login-btn">
                    <svg width="20" height="20" viewBox="0 0 24 24"><path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" fill="#4285F4"/><path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/><path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05"/><path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"/></svg>
                    {t['login_google']}
                </div>
            </a>
            """, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"AUTH SYSTEM ERROR: {str(e)}")
        st.markdown("</div>", unsafe_allow_html=True)
    
    # Sidebar footer
    st.markdown("<p style='font-family:Share Tech Mono;font-size:9px;color:#445566;text-align:center;margin:8px 0;'>AEROVULPIS V3.5 | DYNAMIHATCH</p>", unsafe_allow_html=True)
    st.caption("2026 | SYSTEM ACTIVE")
    
    # Category & Asset selectors
    category = st.selectbox(t['category'], list(instruments.keys()))
    asset_name = st.selectbox(t['asset'], list(instruments[category].keys()))
    ticker_input = instruments[category][asset_name]
    ticker_display = f"{asset_name} [{ticker_input}]"
    
    st.markdown("---")
    
    # Timeframe selector
    tf_options = {
        "15M": {"period": "5d", "interval": "15m"},
        "30M": {"period": "5d", "interval": "30m"},
        "1H": {"period": "1mo", "interval": "1h"},
        "3H": {"period": "1mo", "interval": "1h"},
        "4H": {"period": "1mo", "interval": "1h"},
        "1D": {"period": "1y", "interval": "1d"},
        "1W": {"period": "2y", "interval": "1wk"}
    }
    selected_tf_display = st.selectbox(t['timeframe'], list(tf_options.keys()), index=0)
    period = tf_options[selected_tf_display]["period"]
    interval = tf_options[selected_tf_display]["interval"]
    
    # Navigation menu
    menu_selection = option_menu(
        menu_title=t['navigation'],
        options=[
            "Live Dashboard",
            "AeroVulpis Sentinel",
            "Signal Analysis",
            "Market Sessions",
            "Market News",
            "Economic Radar",
            "Smart Alert Center",
            "Chatbot AI",
            "Risk Management",
            "Settings",
            "Help & Support"
        ],
        icons=[
            "activity",
            "shield-shaded",
            "graph-up-arrow",
            "globe",
            "newspaper",
            "calendar-event",
            "bell-fill",
            "chat-dots",
            "shield-fill",
            "gear",
            "question-circle"
        ],
        menu_icon="cast",
        default_index=0,
        styles={
            "container": {"padding": "5!important", "background-color": "transparent"},
            "icon": {"color": "#00d4ff", "font-size": "13px"},
            "nav-link": {
                "font-size": "11px",
                "text-align": "left",
                "margin": "2px 0",
                "padding": "10px 12px",
                "border-radius": "3px",
                "font-family": "Rajdhani",
                "font-weight": "500",
                "letter-spacing": "1px",
                "background": "rgba(0,212,255,0.015)",
                "border": "1px solid rgba(0,212,255,0.06)",
                "transition": "all 0.25s ease"
            },
            "nav-link-selected": {
                "background": "linear-gradient(160deg,rgba(0,48,96,0.4),rgba(0,28,64,0.6))",
                "border": "1px solid #00d4ff",
                "color": "#00d4ff",
                "box-shadow": "0 0 18px rgba(0,212,255,0.12)",
                "font-weight": "700"
            },
        }
    )
    
    # Daily usage indicator
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

# ##############################################################################
# MAIN APPLICATION LOGIC
# ##############################################################################

# Run smart alert checker
check_smart_alerts()

# ==============================================================================
# 1. AEROVULPIS SENTINEL PRO
# ==============================================================================
if menu_selection == "AeroVulpis Sentinel":
    st.markdown(f"""
    <div class="sentinel-container">
        <div class="sentinel-header" style="flex-direction:column;align-items:flex-start;">
            <h2 class="sentinel-title">{t['sentinel_title']}</h2>
            <div style="display:flex;gap:10px;margin-top:10px;">
                <span class="status-badge status-open">{t['market_status']}</span>
                <span class="status-badge status-ai">{t['sentinel_ai_status']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    col_chart, col_intel = st.columns([2, 1])
    
    with col_chart:
        # Convert ticker for TradingView
        tv_symbol = ticker_input.replace("-USD", "USD").replace("=X", "").replace(".JK", "")
        if "GC=F" in ticker_input:
            tv_symbol = "COMEX:GC1!"
        elif "SI=F" in ticker_input:
            tv_symbol = "COMEX:SI1!"
        elif "CL=F" in ticker_input:
            tv_symbol = "NYMEX:CL1!"
        
        # TradingView chart
        tv_html = f"""
        <div class="tradingview-widget-container" style="height:500px;width:100%;">
          <div id="tv_sentinel" style="height:500px;"></div>
          <script src="https://s3.tradingview.com/tv.js"></script>
          <script>
          new TradingView.widget({{"autosize":true,"symbol":"{tv_symbol}","interval":"D","timezone":"Asia/Jakarta","theme":"dark","style":"1","locale":"en","enable_publishing":false,"allow_symbol_change":true,"container_id":"tv_sentinel","studies":["RSI@tv-basicstudies","MACD@tv-basicstudies"]}});
          </script>
        </div>
        """
        st.components.v1.html(tv_html, height=500)
        
        st.markdown("<br>", unsafe_allow_html=True)
        loading_placeholder = st.empty()
        
        # Generate Deep Analysis PRO button
        if st.button(t['sentinel_btn'], key="sentinel_pro_btn", use_container_width=True):
            market = get_market_data(ticker_input)
            df = get_historical_data(ticker_input, period, interval)
            
            if market and not df.empty:
                df = add_technical_indicators(df)
                score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
                
                # Show 3D loading animation
                loading_placeholder.markdown("""
                <div class="loading-3d-pro-container">
                    <div class="loading-3d-pro-scene">
                        <div class="loading-3d-pro-core">
                            <div class="loading-3d-pro-ring"></div>
                            <div class="loading-3d-pro-ring"></div>
                            <div class="loading-3d-pro-ring"></div>
                            <div class="loading-3d-pro-ring"></div>
                        </div>
                        <div class="loading-3d-pro-center"></div>
                        <div class="loading-3d-pro-particles">
                            <div class="loading-3d-pro-particle"></div>
                            <div class="loading-3d-pro-particle"></div>
                            <div class="loading-3d-pro-particle"></div>
                            <div class="loading-3d-pro-particle"></div>
                            <div class="loading-3d-pro-particle"></div>
                            <div class="loading-3d-pro-particle"></div>
                        </div>
                    </div>
                    <p class="loading-3d-pro-text">SENTINEL PROCESSING</p>
                    <p class="loading-3d-pro-sub">AEROVULPIS SENTINEL CORE | MARKET MICROSTRUCTURE ANALYSIS</p>
                </div>
                """, unsafe_allow_html=True)
                
                # Progress bar
                progress_bar = st.progress(0)
                for i in range(100):
                    time.sleep(0.03)
                    progress_bar.progress(i + 1)
                
                # Call Sentinel Analysis
                analysis = get_sentinel_analysis(asset_name, market, df, signal, reasons)
                st.session_state.sentinel_analysis = analysis
                
                # Clean up
                loading_placeholder.empty()
                progress_bar.empty()
            else:
                st.error("DATA ACQUISITION FAILED | CHECK CONNECTION")
    
    with col_intel:
        st.markdown(f"""
        <div class="intelligence-panel">
            <div class="intel-header">{t['sentinel_intel']}</div>
            <div class="intel-content">
        """, unsafe_allow_html=True)
        
        if st.session_state.sentinel_analysis:
            st.markdown(st.session_state.sentinel_analysis)
        else:
            st.info(t['sentinel_placeholder'])
        
        st.markdown("</div></div>", unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# 2. LIVE DASHBOARD
# ==============================================================================
elif menu_selection == "Live Dashboard":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    
    if market and not df.empty:
        # Resample for 3H/4H timeframes
        if selected_tf_display in ["3H", "4H"]:
            rule = "3h" if selected_tf_display == "3H" else "4h"
            df = df.resample(rule).agg({
                'Open': 'first',
                'High': 'max',
                'Low': 'min',
                'Close': 'last',
                'Volume': 'sum'
            }).dropna()
        
        df = add_technical_indicators(df)
        score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
        
        # 4 Glass Cards
        c1, c2, c3, c4 = st.columns(4)
        formatted_price = format_price_display(market['price'], asset_name)
        data_source = market.get('source', 'LIVE')
        
        with c1:
            st.markdown(f'<div class="glass-card"><p style="color:#557799;margin:0;font-size:9px;letter-spacing:2px;">{t["live_price"]} [{data_source}]</p><p style="font-family:Share Tech Mono;color:#00ff88;font-size:24px;margin:0;text-shadow:0 0 10px rgba(0,255,136,0.4);">{formatted_price}</p></div>', unsafe_allow_html=True)
        
        with c2:
            color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
            st.markdown(f'<div class="glass-card"><p style="color:#557799;margin:0;font-size:9px;letter-spacing:2px;">{t["signal"]}</p><p style="font-family:Orbitron;font-size:20px;margin:0;color:{color};text-shadow:0 0 15px {color};">{signal}</p></div>', unsafe_allow_html=True)
        
        with c3:
            rsi_val = df["RSI"].iloc[-1] if "RSI" in df.columns else 0.0
            st.markdown(f'<div class="glass-card"><p style="color:#557799;margin:0;font-size:9px;letter-spacing:2px;">{t["rsi"]}</p><p style="font-family:Share Tech Mono;color:#00d4ff;font-size:24px;margin:0;">{rsi_val:.1f}</p></div>', unsafe_allow_html=True)
        
        with c4:
            atr_val = df["ATR"].iloc[-1] if "ATR" in df.columns else 0.0
            st.markdown(f'<div class="glass-card"><p style="color:#557799;margin:0;font-size:9px;letter-spacing:2px;">{t["atr"]}</p><p style="font-family:Share Tech Mono;color:#8899bb;font-size:24px;margin:0;">{atr_val:.4f}</p></div>', unsafe_allow_html=True)
        
        # Price Chart
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], mode='lines', name='PRICE', line=dict(color='#00ff88', width=1.5)))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA50"], line=dict(color='#00d4ff', width=1, dash='dot'), name='SMA50'))
        fig.add_trace(go.Scatter(x=df.index, y=df["SMA200"], line=dict(color='#bc13fe', width=1, dash='dash'), name='SMA200'))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10, r=10, t=10, b=10),
            height=380,
            legend=dict(orientation="h", y=-0.15, font=dict(size=10)),
            xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.03)')
        )
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
        
        # Gauge & Analysis
        col_g, col_a = st.columns([1, 1])
        
        with col_g:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            
            gauge_color = color
            
            # Cyber Gauge
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=score,
                number={"font": {"family": "Orbitron", "color": "#00d4ff", "size": 42}, "suffix": "%"},
                title={"text": "TECHNICAL STRENGTH", "font": {"family": "Orbitron", "color": "#00d4ff", "size": 15}},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "#00d4ff", "tickfont": {"color": "#8899bb", "size": 10}},
                    "bar": {"color": gauge_color, "thickness": 0.25},
                    "bgcolor": "rgba(0,0,0,0)",
                    "borderwidth": 1,
                    "bordercolor": "rgba(0,212,255,0.3)",
                    "steps": [
                        {"range": [0, 30], "color": "rgba(255,42,109,0.15)"},
                        {"range": [30, 45], "color": "rgba(255,42,109,0.08)"},
                        {"range": [45, 55], "color": "rgba(255,204,0,0.08)"},
                        {"range": [55, 70], "color": "rgba(0,255,136,0.08)"},
                        {"range": [70, 100], "color": "rgba(0,255,136,0.15)"}
                    ],
                    "threshold": {
                        "line": {"color": gauge_color, "width": 3},
                        "thickness": 0.8,
                        "value": score
                    }
                },
                delta={"reference": 50, "increasing": {"color": "#00ff88"}, "decreasing": {"color": "#ff2a6d"}, "font": {"size": 12}}
            ))
            fig_gauge.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font={"color": "#8899bb"},
                height=300,
                margin=dict(l=20, r=20, t=60, b=20)
            )
            
            st.markdown('<div class="cyber-gauge-container">', unsafe_allow_html=True)
            st.plotly_chart(fig_gauge, use_container_width=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
            if st.button(t['refresh'], use_container_width=True):
                st.cache_data.clear()
                st.rerun()
            
            st.markdown("</div>", unsafe_allow_html=True)
        
        with col_a:
            st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-family:Orbitron;font-size:13px;color:#00d4ff;letter-spacing:2px;margin-bottom:10px;'>{t['ai_analysis']}</p>", unsafe_allow_html=True)
            
            for r in reasons:
                st.markdown(f"<p style='font-family:Share Tech Mono;font-size:10px;color:#8899bb;margin:3px 0;'>[ {r} ]</p>", unsafe_allow_html=True)
            
            if st.button(t['generate_ai'], use_container_width=True):
                with st.spinner("AEROVULPIS ENGINE PROCESSING..."):
                    ai_anal = get_deep_analysis(asset_name, market, df, signal, reasons)
                    st.info(ai_anal)
            
            st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# 3. SIGNAL ANALYSIS
# ==============================================================================
elif menu_selection == "Signal Analysis":
    market = get_market_data(ticker_input)
    df = get_historical_data(ticker_input, period, interval)
    
    if not df.empty:
        if selected_tf_display in ["3H", "4H"]:
            rule = "3h" if selected_tf_display == "3H" else "4h"
            df = df.resample(rule).agg({
                'Open': 'first', 'High': 'max', 'Low': 'min',
                'Close': 'last', 'Volume': 'sum'
            }).dropna()
        
        df = add_technical_indicators(df)
        latest = df.iloc[-1]
        score, signal, reasons, bull, bear, neut = get_weighted_signal(df)
        
        st.markdown("<div class='glass-card'>", unsafe_allow_html=True)
        sig_color = "#00ff88" if "BUY" in signal else "#ff2a6d" if "SELL" in signal else "#ffcc00"
        st.markdown(f"<p style='font-family:Orbitron;font-size:16px;color:#8899bb;letter-spacing:2px;'>{t['recommendation']}: <span style='color:{sig_color};'>{signal}</span></p>", unsafe_allow_html=True)
        
        # Bull/Bear/Neutral
        c1, c2, c3 = st.columns(3)
        c1.markdown(f'<div style="text-align:center;background:rgba(0,255,136,0.04);padding:12px;border-radius:4px;border:1px solid rgba(0,255,136,0.15);"><p style="color:#00ff88;font-size:10px;margin:0;letter-spacing:2px;">BULLISH</p><p style="font-family:Orbitron;font-size:26px;margin:0;color:#00ff88;">{bull}</p></div>', unsafe_allow_html=True)
        c2.markdown(f'<div style="text-align:center;background:rgba(255,42,109,0.04);padding:12px;border-radius:4px;border:1px solid rgba(255,42,109,0.15);"><p style="color:#ff2a6d;font-size:10px;margin:0;letter-spacing:2px;">BEARISH</p><p style="font-family:Orbitron;font-size:26px;margin:0;color:#ff2a6d;">{bear}</p></div>', unsafe_allow_html=True)
        c3.markdown(f'<div style="text-align:center;background:rgba(255,204,0,0.04);padding:12px;border-radius:4px;border:1px solid rgba(255,204,0,0.15);"><p style="color:#ffcc00;font-size:10px;margin:0;letter-spacing:2px;">NEUTRAL</p><p style="font-family:Orbitron;font-size:26px;margin:0;color:#ffcc00;">{neut}</p></div>', unsafe_allow_html=True)
        
        # 20 Indicators Grid
        st.markdown('<div class="indicator-grid">', unsafe_allow_html=True)
        indicators_data = [
            ("RSI (14)", f"{latest.get('RSI',0):.2f}", "BULLISH" if latest.get('RSI',0)<30 else "BEARISH" if latest.get('RSI',0)>70 else "NEUTRAL"),
            ("MACD", f"{latest.get('MACD',0):.4f}", "BULLISH" if latest.get('MACD',0)>latest.get('Signal_Line',0) else "BEARISH"),
            ("SMA 50", f"{latest.get('SMA50',0):.4f}".rstrip('0').rstrip('.'), "BULLISH" if latest.get('Close',0)>latest.get('SMA50',0) else "BEARISH"),
            ("SMA 200", f"{latest.get('SMA200',0):.4f}".rstrip('0').rstrip('.'), "BULLISH" if latest.get('Close',0)>latest.get('SMA200',0) else "BEARISH"),
            ("CCI (20)", f"{latest.get('CCI',0):.2f}", "BULLISH" if latest.get('CCI',0)<-100 else "BEARISH" if latest.get('CCI',0)>100 else "NEUTRAL"),
            ("WILLIAMS %R", f"{latest.get('WPR',0):.2f}", "BULLISH" if latest.get('WPR',0)<-80 else "BEARISH" if latest.get('WPR',0)>-20 else "NEUTRAL"),
            ("MFI (14)", f"{latest.get('MFI',0):.2f}", "BULLISH" if latest.get('MFI',0)<20 else "BEARISH" if latest.get('MFI',0)>80 else "NEUTRAL"),
            ("EMA 9/21", "CROSS", "BULLISH" if latest.get('EMA9',0)>latest.get('EMA21',0) else "BEARISH"),
            ("ADX (14)", f"{latest.get('ADX',0):.2f}", "STRONG" if latest.get('ADX',0)>25 else "WEAK"),
            ("STOCH K", f"{latest.get('Stoch_K',0):.2f}", "BULLISH" if latest.get('Stoch_K',0)<20 else "BEARISH" if latest.get('Stoch_K',0)>80 else "NEUTRAL"),
            ("ATR (14)", f"{latest.get('ATR',0):.4f}", "HIGH" if latest.get('ATR',0)>df['ATR'].mean() else "LOW"),
            ("ROC (12)", f"{latest.get('ROC',0):.2f}", "BULLISH" if latest.get('ROC',0)>0 else "BEARISH"),
            ("TRIX (15)", f"{latest.get('TRIX',0):.4f}", "BULLISH" if latest.get('TRIX',0)>0 else "BEARISH"),
            ("AO (5/34)", f"{latest.get('AO',0):.4f}", "BULLISH" if latest.get('AO',0)>0 else "BEARISH"),
            ("KAMA (10)", f"{latest.get('KAMA',0):.2f}", "BULLISH" if latest.get('Close',0)>latest.get('KAMA',0) else "BEARISH"),
            ("ICHIMOKU A", f"{latest.get('Ichimoku_A',0):.2f}", "BULLISH" if latest.get('Close',0)>latest.get('Ichimoku_A',0) else "BEARISH"),
            ("ICHIMOKU B", f"{latest.get('Ichimoku_B',0):.2f}", "BULLISH" if latest.get('Close',0)>latest.get('Ichimoku_B',0) else "BEARISH"),
            ("PARABOLIC SAR", f"{latest.get('Parabolic_SAR',0):.2f}", "BULLISH" if latest.get('Close',0)>latest.get('Parabolic_SAR',0) else "BEARISH"),
            ("BB UPPER", f"{latest.get('BB_Upper',0):.2f}", "OVERBOUGHT" if latest.get('Close',0)>latest.get('BB_Upper',0) else "NORMAL"),
            ("BB LOWER", f"{latest.get('BB_Lower',0):.2f}", "OVERSOLD" if latest.get('Close',0)<latest.get('BB_Lower',0) else "NORMAL")
        ]
        
        for name, val, sig in indicators_data:
            if "BULLISH" in sig or "STRONG" in sig or "OVERSOLD" in sig:
                sig_col = "#00ff88"
            elif "BEARISH" in sig or "OVERBOUGHT" in sig:
                sig_col = "#ff2a6d"
            else:
                sig_col = "#ffcc00"
            
            st.markdown(f'<div class="indicator-box"><div class="indicator-name">{name}</div><div class="indicator-value">{val}</div><div class="indicator-signal" style="color:{sig_col};">{sig}</div></div>', unsafe_allow_html=True)
        
        st.markdown('</div></div>', unsafe_allow_html=True)

# ==============================================================================
# 4. MARKET SESSIONS
# ==============================================================================
elif menu_selection == "Market Sessions":
    market_session_status()

# ==============================================================================
# 5. MARKET NEWS
# ==============================================================================
elif menu_selection == "Market News":
    st.markdown(f'<h2 style="font-family:Orbitron;font-size:22px;color:#00d4ff;letter-spacing:3px;margin-bottom:5px;">{t["market_news"]}</h2>', unsafe_allow_html=True)
    st.markdown(f'<p style="font-family:Share Tech Mono;font-size:9px;color:#557799;margin-bottom:15px;">{t["news_updated"]}</p>', unsafe_allow_html=True)
    
    news_categories = ["General", "Stock", "Konflik", "Gold & Silver", "Forex"]
    selected_news_cat = st.segmented_control(t['news_filter'], news_categories, default="General")
    
    # Force refresh button
    col_refresh, col_empty = st.columns([1, 3])
    with col_refresh:
        if st.button(t['force_refresh'], use_container_width=True, key="force_news_refresh"):
            if "last_news_fetch" in st.session_state:
                st.session_state.last_news_fetch = {}
            st.cache_data.clear()
            st.rerun()
    
    articles, error = get_news_data(selected_news_cat, 10)
    
    if error and not articles:
        st.error(error)
    elif articles:
        for a in articles:
            st.markdown(f"""
            <div class="news-card">
                <p style="font-family:Orbitron;font-size:13px;color:#00d4ff;margin:0 0 5px;letter-spacing:1px;">{a.get('title','NO TITLE')}</p>
                <p style="font-family:Share Tech Mono;font-size:9px;color:#557799;margin:0 0 8px;">{a.get('source','')} | {a.get('publishedAt','')}</p>
                <p style="font-family:Rajdhani;font-size:11px;color:#8899bb;line-height:1.5;">{a.get('description','')[:300]}{'...' if len(a.get('description',''))>300 else ''}</p>
                <a href="{a.get('url','#')}" target="_blank" style="font-family:Share Tech Mono;font-size:9px;color:#00ff88;text-decoration:none;letter-spacing:1px;">[ ACCESS SOURCE ]</a>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info(t['no_news'])

# ==============================================================================
# 6. ECONOMIC RADAR
# ==============================================================================
elif menu_selection == "Economic Radar":
    economic_calendar_widget()
    st.markdown(f"""
    <div style="text-align:center;padding:12px;margin-top:8px;background:rgba(0,20,40,0.5);border:1px solid rgba(0,212,255,0.15);border-radius:4px;">
        <p class="cyber-glow-text" style="font-size:13px;margin:0;letter-spacing:3px;">{t['economic_title']}</p>
        <p style="font-family:Share Tech Mono;font-size:9px;color:#557799;margin:4px 0 0;">{t['economic_subtitle']}</p>
    </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# 7. SMART ALERT CENTER (NO DUPLICATE)
# ==============================================================================
elif menu_selection == "Smart Alert Center":
    st.markdown(f"""
    <div style="border:1px solid rgba(0,212,255,0.25);border-radius:6px;padding:28px;background:rgba(0,15,30,0.5);box-shadow:0 0 30px rgba(0,212,255,0.06);margin-bottom:20px;">
        <div style="text-align:center;margin-bottom:22px;">
            <p class="cyber-glow-text" style="font-size:24px;margin:0;letter-spacing:4px;">{t['alert_title']}</p>
            <p class="cyber-glow-text" style="font-size:15px;margin:6px 0;letter-spacing:3px;">{t['alert_subtitle']}</p>
            <div style="display:flex;justify-content:center;gap:24px;margin-top:12px;">
                <span style="font-family:Share Tech Mono;font-size:10px;color:#00ff88;text-shadow:0 0 8px rgba(0,255,136,0.5);">{t['alert_online']}</span>
                <span style="font-family:Share Tech Mono;font-size:10px;color:#00d4ff;text-shadow:0 0 8px rgba(0,212,255,0.5);">{t['alert_sync']}</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    # Only call widget - no duplicate content
    smart_alert_widget()
    
    st.markdown("</div>", unsafe_allow_html=True)

# ==============================================================================
# 8. CHATBOT AI
# ==============================================================================
elif menu_selection == "Chatbot AI":
    st.markdown(f'<h2 style="font-family:Orbitron;font-size:20px;color:#00d4ff;letter-spacing:3px;">{t["chatbot_title"]}</h2>', unsafe_allow_html=True)
    st.caption(f"AEROVULPIS ENGINE | {tier_names.get(st.session_state.user_tier,'FREE')} | {st.session_state.daily_chatbot_count}/{user_limits['chatbot_per_day']}")
    
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    if prompt := st.chat_input("INPUT QUERY..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            m_data = get_market_data(ticker_input)
            context_str = f"INSTR: {ticker_display} | PRICE: {format_price_display(m_data['price'], asset_name) if m_data else 'N/A'}"
            if st.session_state.get("active_alerts"):
                context_str += f" | ALERTS: {len(st.session_state.active_alerts)}"
            response = get_groq_response(prompt, context_str)
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# ==============================================================================
# 9. RISK MANAGEMENT
# ==============================================================================
elif menu_selection == "Risk Management":
    st.markdown(f'<h2 style="font-family:Orbitron;text-align:center;font-size:24px;color:#00d4ff;letter-spacing:3px;margin-bottom:5px;">{t["risk_title"]}</h2>', unsafe_allow_html=True)
    st.markdown('<p style="text-align:center;font-family:Share Tech Mono;font-size:9px;color:#557799;margin-top:-5px;">RETURN SIMULATOR | POSITION SIZING</p>', unsafe_allow_html=True)
    
    # Four Pillars
    st.markdown("""
    <div class="pillar-container">
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/lxtUFfqAGtqmckoG.png" class="pillar-icon"><p class="pillar-title">TRADING RULES</p><p class="pillar-desc">SL DEFINITION</p></div>
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/IrMPKUKVGNWfJYiT.png" class="pillar-icon"><p class="pillar-title">POSITION SIZE</p><p class="pillar-desc">SCALE LOGIC</p></div>
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/KvlBOIcTGsUXIlxi.png" class="pillar-icon"><p class="pillar-title">CONFIDENCE</p><p class="pillar-desc">REAL-TIME</p></div>
        <div class="pillar-item"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663558138123/XagmGYTISfZpBVMv.png" class="pillar-icon"><p class="pillar-title">RISK MGMT</p><p class="pillar-desc">STRATEGY</p></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Account Balance
    st.markdown(f'<p class="section-title">{t["funding_details"]}</p>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card"><p style="font-family:Share Tech Mono;font-size:10px;color:#557799;margin-bottom:6px;">{t["account_balance"]}</p>', unsafe_allow_html=True)
    balance = st.number_input("", value=1000.0, step=100.0, min_value=100.0, key="sim_balance", label_visibility="collapsed")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # R:R Ratio
    st.markdown(f'<p class="section-title">{t["rr_simulator"]}</p>', unsafe_allow_html=True)
    rr_ratios = {"1:2": 2.0, "1:3": 3.0, "1:4": 4.0, "2:3": 1.5, "2:4": 2.0, "2:5": 2.5, "3:4": 1.33, "3:5": 1.67, "3:6": 2.0}
    selected_rr = st.radio("R:R", list(rr_ratios.keys()), horizontal=True, key="rr_radio")
    
    # Win/Loss
    st.markdown(f'<p style="font-family:Share Tech Mono;font-size:10px;color:#8899bb;margin-top:12px;">WEEKLY SIMULATION</p>', unsafe_allow_html=True)
    wc, lc = st.columns(2)
    with wc:
        wins = st.number_input(t['wins'], min_value=0, value=3, step=1, key="wins")
    with lc:
        losses = st.number_input(t['losses'], min_value=0, value=2, step=1, key="losses")
    
    risk_pct = 1.0
    
    # Daily Risk
    st.markdown(f'<p class="section-title">{t["daily_risk"]}</p>', unsafe_allow_html=True)
    d1, d2 = st.columns(2)
    with d1:
        max_loss = st.number_input("MAX LOSS %", 1.0, 100.0, 5.0, 1.0, key="maxl")
    with d2:
        max_profit = st.number_input("MAX PROFIT %", 1.0, 200.0, 10.0, 1.0, key="maxp")
    
    # Simulate
    if st.button(t['risk_simulate'], use_container_width=True, type="primary"):
        ra = balance * (risk_pct / 100)
        rw = ra * rr_ratios[selected_rr]
        wn = (wins * rw) - (losses * ra)
        wr = (wn / balance) * 100 if balance > 0 else 0
        mr = wr * 4
        yr = wr * 52
        fbw = balance + wn
        fbm = balance + (wn * 4)
        fby = balance + (wn * 52)
        mla = balance * (max_loss / 100)
        mpa = balance * (max_profit / 100)
        
        # Projected Performance
        st.markdown(f'<p style="font-family:Orbitron;font-size:14px;margin-top:20px;color:#00d4ff;text-align:center;letter-spacing:3px;">{t["projection_title"]}</p>', unsafe_allow_html=True)
        
        for pn, net, ret, fbal in [
            (t['risk_weekly'], wn, wr, fbw),
            (t['risk_monthly'], wn * 4, mr, fbm),
            (t['risk_yearly'], wn * 52, yr, fby)
        ]:
            st.markdown(f"""
            <div class="fintech-result-card">
                <p style="font-family:Orbitron;font-size:11px;color:#00d4ff;margin:0 0 8px;letter-spacing:2px;">{pn}</p>
                <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;">
                    <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_net']}</p><p class="risk-metric" style="color:{'#00ff88' if net>=0 else '#ff2a6d'};">{net:+,.2f}</p></div>
                    <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_return']}</p><p class="risk-metric" style="color:{'#00ff88' if ret>=0 else '#ff2a6d'};">{ret:+.1f}%</p></div>
                    <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_balance']}</p><p class="risk-metric" style="color:#00d4ff;">{fbal:,.2f}</p></div>
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Risk Parameters
        st.markdown(f'<p style="font-family:Orbitron;font-size:14px;margin-top:20px;color:#ff2a6d;text-align:center;letter-spacing:3px;">{t["risk_params"]}</p>', unsafe_allow_html=True)
        st.markdown(f"""
        <div class="fintech-result-card" style="border-color:rgba(255,42,109,0.2);">
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;">
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_per_trade']}</p><p class="risk-metric" style="color:#ff2a6d;">{ra:,.2f}</p></div>
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_reward_trade']}</p><p class="risk-metric" style="color:#00ff88;">{rw:,.2f}</p></div>
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_max_loss']}</p><p class="risk-metric" style="color:#ff2a6d;">-{mla:,.2f}</p></div>
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_max_profit']}</p><p class="risk-metric" style="color:#00ff88;">+{mpa:,.2f}</p></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Balance Summary
        st.markdown(f"""
        <div class="fintech-result-card" style="border:1px solid #00d4ff;background:linear-gradient(160deg,rgba(0,30,60,0.8),rgba(0,15,40,0.9));">
            <p style="font-family:Orbitron;font-size:11px;color:#00d4ff;margin:0 0 8px;text-align:center;letter-spacing:2px;">{t['risk_summary']}</p>
            <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;">
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_initial']}</p><p class="risk-metric">{balance:,.2f}</p></div>
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_after']} 1W</p><p class="risk-metric" style="color:{'#00ff88' if fbw>=balance else '#ff2a6d'};">{fbw:,.2f}</p></div>
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_after']} 1M</p><p class="risk-metric" style="color:{'#00ff88' if fbm>=balance else '#ff2a6d'};">{fbm:,.2f}</p></div>
                <div style="text-align:center;"><p style="font-size:8px;color:#557799;margin:0;">{t['risk_after']} 1Y</p><p class="risk-metric" style="color:{'#00ff88' if fby>=balance else '#ff2a6d'};">{fby:,.2f}</p></div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.info("CONFIGURE PARAMETERS | EXECUTE SIMULATION")

# ==============================================================================
# 10. SETTINGS
# ==============================================================================
elif menu_selection == "Settings":
    st.markdown(f'<h2 style="font-family:Orbitron;font-size:20px;color:#00d4ff;letter-spacing:3px;">{t["settings_title"]}</h2>', unsafe_allow_html=True)
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    
    new_lang = st.selectbox(t['lang_select'], ["ID", "EN"], index=0 if st.session_state.lang == "ID" else 1)
    if new_lang != st.session_state.lang:
        st.session_state.lang = new_lang
        st.rerun()
    
    if st.button(t['clear_cache'], use_container_width=True):
        st.cache_data.clear()
        st.session_state.cached_analysis = {}
        st.session_state.last_news_fetch = {}
        st.success("SYSTEM CACHE CLEARED")
        time.sleep(1)
        st.rerun()
    
    st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# 11. HELP & SUPPORT (BAHASA INDONESIA, TIDAK SEBUT TEKNOLOGI)
# ==============================================================================
elif menu_selection == "Help & Support":
    st.markdown(f'<h2 style="font-family:Orbitron;text-align:center;font-size:24px;color:#00d4ff;letter-spacing:4px;margin-bottom:24px;">{t["help_title"]}</h2>', unsafe_allow_html=True)
    
    with st.expander("SENTINEL PRO INTELLIGENCE", expanded=True):
        st.markdown("""
        **Sentinel Pro** adalah dashboard analisis profesional yang didukung oleh sistem kecerdasan buatan AeroVulpis Sentinel Core.

        **Kemampuan Utama:**
        - Grafik real-time dengan berbagai pilihan jangka waktu
        - Deep Analysis Pro menghasilkan laporan lengkap mencakup Level Support/Resistance, Wawasan Fundamental, dan Skenario Trading Bullish/Bearish
        - Analisis struktur pasar untuk timing entry dan exit yang presisi
        - Penyimpanan hasil analisis sementara untuk menghemat kuota

        **Sumber Data:** Data harga diambil langsung dari broker untuk akurasi tinggi pada Gold, Silver, Forex, dan Crypto.

        **Cara Penggunaan:** Pilih instrumen dan jangka waktu dari sidebar, buka halaman Sentinel, klik "INITIATE DEEP ANALYSIS PRO".
        """)
    
    with st.expander("LIVE DASHBOARD"):
        st.markdown("""
        **Live Dashboard** menyediakan pemantauan pasar real-time.

        **Fitur:**
        - Harga live dengan indikator sumber data
        - Cyber Gauge yang menunjukkan kekuatan teknikal dengan animasi
        - Grafik harga interaktif dengan indikator moving average
        - Analisis cepat dengan satu klik

        **Format Harga:**
        - XAUUSD: 4,756.00 | XAGUSD: 34.50
        - Forex: 1.0850 | Crypto: 67,250.00
        - Indeks: 18,250.50 | Saham: 150.25
        """)
    
    with st.expander("SIGNAL ANALYSIS"):
        st.markdown("""
        **Signal Analysis Matrix** menampilkan 20 indikator teknikal dalam format grid.

        **Kategori Indikator:**
        - **Trend:** SMA 50, SMA 200, EMA 9/21, Ichimoku, Parabolic SAR
        - **Momentum:** RSI, MACD, Stochastic, CCI, Williams %R, MFI, ROC, TRIX, Awesome Oscillator
        - **Volatilitas:** ATR, Bollinger Bands
        - **Volume:** Volume SMA, Base Line

        **Warna Sinyal:** Hijau = Bullish | Merah = Bearish | Kuning = Netral
        """)
    
    with st.expander("MARKET SESSIONS & BERITA"):
        st.markdown("""
        **Monitor Sesi Pasar Global:**
        - Tracking real-time sesi Asia (Tokyo), Eropa (London), dan Amerika (New York)
        - Progress bar menunjukkan persentase sesi berjalan
        - Deteksi Golden Hour (tumpang tindih London-New York)
        - Rekomendasi strategi berdasarkan sesi aktif

        **Agregator Berita:**
        - Berita dari berbagai jaringan finansial global
        - Filter kategori: Umum, Saham, Geopolitik, Gold & Silver, Forex
        - Penyimpanan sementara dengan tombol refresh
        - Tautan langsung ke sumber berita
        """)
    
    with st.expander("SMART ALERT CENTER"):
        st.markdown("""
        **Sistem Pemantauan Harga Otomatis** dengan notifikasi Telegram.

        **Cara Setup:**
        1. Pilih instrumen dari dropdown
        2. Tentukan harga target
        3. Masukkan Chat ID Telegram (dapatkan dari @userinfobot)
        4. Pilih kondisi: Bullish (harga naik) atau Bearish (harga turun)
        5. Aktifkan sensor untuk pemantauan 24/7

        **Fitur:**
        - Pemantauan latar belakang untuk semua alert aktif
        - Notifikasi Telegram instan saat target tercapai
        - Format harga otomatis menyesuaikan jenis instrumen
        """)
    
    with st.expander("CHATBOT AI"):
        st.markdown("""
        **Asisten Cerdas** yang memahami konteks instrumen yang dipilih dan harga live.

        **Kemampuan:**
        - Analisis teknikal dan interpretasi indikator
        - Rekomendasi level Entry, Stop Loss, dan Take Profit
        - Diskusi strategi trading

        **Batas Harian per Level:**
        - GRATIS: 20 pesan/hari
        - TRIAL: 50 pesan/hari
        - MINGGUAN: 100 pesan/hari
        - BULANAN: 200 pesan/hari
        - 6 BULAN: 500 pesan/hari
        - TAHUNAN: Tidak Terbatas
        """)
    
    with st.expander("ECONOMIC RADAR"):
        st.markdown("""
        **Pemindai Ekonomi Global** memantau peristiwa ekonomi berdampak tinggi.

        **Fitur:**
        - Kalender ekonomi live dengan cakupan global
        - Deteksi peristiwa berdampak tinggi
        - Filter berdasarkan mata uang: USD, EUR, GBP, JPY, AUD, CAD, CHF, NZD

        **Peristiwa yang Dimonitor:** Suku Bunga Bank Sentral, NFP, CPI, GDP, PMI, Consumer Confidence
        """)
    
    with st.expander("RISK MANAGEMENT"):
        st.markdown("""
        **Sistem Manajemen Risiko Empat Pilar:**
        1. **Aturan Trading** - Tentukan stop loss dan parameter entry
        2. **Ukuran Posisi** - Hitung ukuran posisi optimal berdasarkan saldo
        3. **Skor Keyakinan** - Penilaian kekuatan teknikal real-time
        4. **Strategi Risiko** - Batas kerugian harian dan target profit

        **Simulator Return:** Rasio Risk-Reward, simulasi mingguan, proyeksi Bulanan/Tahunan.
        """)
    
    with st.expander("AKTIVASI LISENSI & LEVEL"):
        st.markdown("""
        **Sistem Manajemen Lisensi**

        **Cara Masuk:** Klik "AUTHENTICATE WITH GOOGLE" di sidebar, pilih akun Google Anda.

        **Aktivasi Lisensi:**
        1. Setelah masuk, klik "ACTIVATE LICENSE KEY"
        2. Masukkan kunci lisensi (format: XXXX-XXXX-XXXX-XXXX)
        3. Klik "VALIDATE & ACTIVATE"

        **Level & Batas Harian:**
        - **GRATIS:** 5 analisis AI/hari, 20 chat/hari
        - **TRIAL (1 hari):** 10 analisis/hari, 50 chat/hari
        - **MINGGUAN:** 20 analisis/hari, 100 chat/hari
        - **BULANAN:** 50 analisis/hari, 200 chat/hari
        - **6 BULAN:** 100 analisis/hari, 500 chat/hari
        - **TAHUNAN:** Tak terbatas
        """)
    
    st.info("PENGATURAN: Ganti bahasa (ID/EN) di halaman Settings. Gunakan tombol Clear Cache jika data terasa lambat.")

# ##############################################################################
# FOOTER
# ##############################################################################
st.markdown("---")
st.markdown("""
<div style="text-align:center;padding:25px;opacity:0.55;">
    <p style="font-family:Share Tech Mono;font-size:14px;color:#556680;margin:0;letter-spacing:2px;">
        "DISCIPLINE IS THE KEY | EMOTION IS THE ENEMY | TRUST THE SYSTEM"
    </p>
    <p style="font-family:Orbitron;font-size:11px;color:#00ff88;margin:8px 0;letter-spacing:3px;">
        FAHMI — AEROVULPIS ARCHITECT
    </p>
    <p style="font-family:Share Tech Mono;font-size:8px;color:#334455;letter-spacing:2px;margin-top:6px;">
        DYNAMIHATCH IDENTITY | V3.5 ULTIMATE | 2026
    </p>
</div>
""", unsafe_allow_html=True)