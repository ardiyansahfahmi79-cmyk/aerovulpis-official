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
import threading
import ssl
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
    - user_id (str): ID unik user
    
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
    Sinkronisasi data user ke tabel users.
    
    - Jika user sudah terdaftar: update email, nama, avatar, dan last_login
    - Jika user baru: insert data user + beri tier free
    
    Parameter:
    - user_id (str): ID unik user
    - email (str): Email user
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
# AUTH SESSION RESTORE (EMAIL + PASSWORD)
# ##############################################################################

def restore_session():
    """
    Memulihkan sesi user yang sudah login sebelumnya.
    Email + Password tidak memerlukan callback khusus -
    Supabase SDK menyimpan sesi secara otomatis.
    """
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
    return False

# ##############################################################################
# CTRADER WEBSOCKET REAL-TIME PRICE (XAUUSD, XAGUSD, FOREX, CRYPTO)
# ##############################################################################

if "ctrader_prices" not in st.session_state:
    st.session_state.ctrader_prices = {}
if "ctrader_ws_connected" not in st.session_state:
    st.session_state.ctrader_ws_connected = False

def start_ctrader_websocket():
    """
    Memulai koneksi WebSocket ke cTrader API untuk harga real-time.
    Menggunakan thread terpisah agar tidak blocking Streamlit.
    
    Fitur:
    - Heartbeat setiap 10 detik (mencegah disconnect)
    - Subscribe ke XAUUSD, XAGUSD, EURUSD, GBPUSD, BTCUSD
    - Auto-reconnect jika koneksi terputus
    - Harga disimpan ke st.session_state.ctrader_prices
    - Update cache Supabase setiap harga berubah
    """
    ctrader_client_id = st.secrets.get("CTRADER_CLIENT_ID") or os.getenv("CTRADER_CLIENT_ID")
    ctrader_client_secret = st.secrets.get("CTRADER_CLIENT_SECRET") or os.getenv("CTRADER_CLIENT_SECRET")
    
    if not ctrader_client_id or not ctrader_client_secret:
        return
    
    def run_websocket():
        import websocket
        import time as ws_time
        
        def get_ctrader_token():
            """
            Mendapatkan access token dari cTrader Open API.
            Endpoint: https://openapi.ctrader.com/apps/token
            Grant type: client_credentials
            """
            try:
                resp = requests.post(
                    "https://openapi.ctrader.com/apps/token",
                    headers={"Content-Type": "application/json"},
                    json={
                        "client_id": ctrader_client_id,
                        "client_secret": ctrader_client_secret,
                        "grant_type": "client_credentials"
                    },
                    timeout=10
                )
                if resp.status_code == 200:
                    return resp.json().get("access_token")
                else:
                    print(f"CTRADER TOKEN ERROR: {resp.status_code} - {resp.text[:200]}")
            except Exception as e:
                print(f"CTRADER TOKEN EXCEPTION: {e}")
            return None
        
        token = get_ctrader_token()
        if not token:
            print("CTRADER: Failed to obtain token, retrying in 30s...")
            ws_time.sleep(30)
            run_websocket()
            return
        
        subscribe_symbols = ["1", "2", "3", "4", "100"]  # XAUUSD, XAGUSD, EURUSD, GBPUSD, BTCUSD
        symbol_names = {"1": "XAUUSD", "2": "XAGUSD", "3": "EURUSD", "4": "GBPUSD", "100": "BTCUSD"}
        
        def on_message(ws, message):
            """
            Callback saat menerima pesan dari WebSocket.
            Parse harga bid/ask dari SpotEvent.
            """
            try:
                data = json.loads(message)
                if "symbolId" in data and "bid" in data:
                    symbol_id = str(data["symbolId"])
                    symbol_name = symbol_names.get(symbol_id, symbol_id)
                    bid = float(data.get("bid", 0))
                    ask = float(data.get("ask", 0))
                    mid_price = (bid + ask) / 2
                    
                    if symbol_name in ["XAUUSD", "XAGUSD", "BTCUSD"]:
                        mid_price = round(mid_price, 2)
                    else:
                        mid_price = round(mid_price, 4)
                    
                    st.session_state.ctrader_prices[symbol_name] = {
                        "price": mid_price,
                        "bid": bid,
                        "ask": ask,
                        "spread": round(ask - bid, 5),
                        "updated_at": datetime.now(pytz.timezone('Asia/Jakarta')).isoformat()
                    }
                    
                    cache_market_price(symbol_name, mid_price, 0)
                    
            except Exception as e:
                print(f"CTRADER WS MESSAGE ERROR: {e}")
        
        def on_error(ws, error):
            print(f"CTRADER WS ERROR: {error}")
        
        def on_close(ws, close_status_code, close_msg):
            print(f"CTRADER WS CLOSED: {close_status_code} - {close_msg}")
            st.session_state.ctrader_ws_connected = False
            ws_time.sleep(5)
            run_websocket()
        
        def on_open(ws):
            print("CTRADER WS CONNECTED!")
            st.session_state.ctrader_ws_connected = True
            
            sub_msg = {
                "type": "subscribe",
                "symbols": subscribe_symbols,
                "access_token": token
            }
            ws.send(json.dumps(sub_msg))
            print(f"CTRADER: Subscribed to {len(subscribe_symbols)} symbols")
            
            def heartbeat():
                while st.session_state.ctrader_ws_connected:
                    try:
                        ws.send(json.dumps({"type": "heartbeat"}))
                    except Exception:
                        break
                    ws_time.sleep(10)
            
            threading.Thread(target=heartbeat, daemon=True).start()
        
        try:
            ws = websocket.WebSocketApp(
                "wss://ctraderapi.com/ws",
                on_open=on_open,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close
            )
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        except Exception as e:
            print(f"CTRADER WS FATAL: {e}")
            st.session_state.ctrader_ws_connected = False
            ws_time.sleep(10)
            run_websocket()
    
    if not st.session_state.ctrader_ws_connected:
        print("CTRADER: Starting WebSocket thread...")
        thread = threading.Thread(target=run_websocket, daemon=True)
        thread.start()

start_ctrader_websocket()

def get_icmarket_price(symbol):
    """
    Mendapatkan harga real-time dari IC Market melalui cTrader.
    
    Prioritas:
    1. WebSocket cache (real-time, < 5 detik)
    2. REST API (jika WebSocket belum siap)
    
    Return:
    - dict: {price, bid, ask, spread, source} atau None jika gagal
    """
    if symbol in st.session_state.ctrader_prices:
        data = st.session_state.ctrader_prices[symbol]
        updated_at = data.get("updated_at", "")
        if updated_at:
            try:
                updated_dt = datetime.fromisoformat(updated_at)
                now = datetime.now(pytz.timezone('Asia/Jakarta'))
                if (now - updated_dt).total_seconds() < 5:
                    return {
                        "price": data["price"],
                        "bid": data["bid"],
                        "ask": data["ask"],
                        "spread": data["spread"],
                        "source": "ICMARKET_WS"
                    }
            except Exception:
                pass
    
    ctrader_client_id = st.secrets.get("CTRADER_CLIENT_ID") or os.getenv("CTRADER_CLIENT_ID")
    ctrader_client_secret = st.secrets.get("CTRADER_CLIENT_SECRET") or os.getenv("CTRADER_CLIENT_SECRET")
    
    if not ctrader_client_id or not ctrader_client_secret:
        return None
    
    ctrader_map = {
        "XAUUSD": "1", "XAGUSD": "2",
        "EURUSD": "3", "GBPUSD": "4", "USDJPY": "5",
        "AUDUSD": "6", "USDCHF": "7",
        "BTCUSD": "100", "ETHUSD": "101", "SOLUSD": "102",
        "XRPUSD": "103", "BNBUSD": "104",
    }
    
    symbol_id = ctrader_map.get(symbol)
    if not symbol_id:
        return None
    
    try:
        token_resp = requests.post(
            "https://openapi.ctrader.com/apps/token",
            headers={"Content-Type": "application/json"},
            json={
                "client_id": ctrader_client_id,
                "client_secret": ctrader_client_secret,
                "grant_type": "client_credentials"
            },
            timeout=5
        )
        if token_resp.status_code != 200:
            return None
        
        token = token_resp.json().get("access_token")
        if not token:
            return None
        
        response = requests.get(
            f"https://api.ctrader.com/v1/symbols/{symbol_id}/price",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            bid = float(data.get("bid", 0))
            ask = float(data.get("ask", 0))
            mid_price = (bid + ask) / 2
            
            if symbol in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"]:
                formatted_price = round(mid_price, 2)
            elif symbol in ["SOLUSD", "XRPUSD", "BNBUSD"]:
                formatted_price = round(mid_price, 4)
            else:
                formatted_price = round(mid_price, 4)
            
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
    - XAUUSD (Gold):      4,756.00
    - XAGUSD (Silver):       34.50
    - EURUSD (Forex):      1.0850
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