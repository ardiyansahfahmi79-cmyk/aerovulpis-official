import os
import requests
import yfinance as yf
from supabase import create_client, Client
from datetime import datetime
import pytz

# Konfigurasi
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Inisialisasi Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_price(ticker):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            return data['Close'].iloc[-1]
    except:
        pass
    return None

def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    requests.post(url, json=payload, timeout=10)

def run_worker():
    # Ambil alert aktif dari Supabase (Asumsi Anda menyimpan alert di tabel 'active_alerts')
    # Jika alert hanya di session state Streamlit, maka alert tidak akan jalan saat web ditutup.
    # SOLUSI: Simpan alert ke tabel Supabase 'active_alerts' saat user klik "Lock Target"
    
    try:
        res = supabase.table("active_alerts").select("*").eq("triggered", False).execute()
        alerts = res.data
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return

    if not alerts:
        print("No active alerts.")
        return

    # Mapping Ticker
    ticker_map = {
        "XAUUSD": "GC=F",
        "BTCUSD": "BTC-USD",
        "EURUSD": "EURUSD=X",
        "GBPUSD": "GBPUSD=X",
        "USDJPY": "USDJPY=X"
    }

    for alert in alerts:
        inst = alert['instrument']
        ticker = ticker_map.get(inst)
        if not ticker: continue

        current_price = get_price(ticker)
        if current_price is None: continue

        target = alert['target']
        condition = alert['condition']
        triggered = False

        if condition == "bullish" and current_price >= target:
            triggered = True
        elif condition == "bearish" and current_price <= target:
            triggered = True

        if triggered:
            # Update status di Supabase
            supabase.table("active_alerts").update({"triggered": True}).eq("id", alert['id']).execute()
            
            # Kirim Telegram
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")
            
            msg = (
                f"<b>🚨 AEROVULPIS ALERT: {inst}</b>\n"
                f"Target: {target}\n"
                f"Harga Sekarang: {current_price:.2f}\n"
                f"Waktu: {now_wib}\n"
                f"🦅 <i>AeroVulpis Sentinel System</i>"
            )
            send_telegram(alert['chat_id'], msg)
            print(f"Alert triggered for {inst}")

if __name__ == "__main__":
    run_worker()
