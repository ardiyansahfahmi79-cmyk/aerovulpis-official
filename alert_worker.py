import os
import requests
import yfinance as yf
from supabase import create_client, Client
from datetime import datetime
import pytz
import sys

# Konfigurasi
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

print("--- AEROVULPIS DEBUG START ---")
print(f"Time: {datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')}")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: SUPABASE_URL or SUPABASE_KEY is missing!")
    sys.exit(1)

if not TELEGRAM_BOT_TOKEN:
    print("ERROR: TELEGRAM_BOT_TOKEN is missing!")
    sys.exit(1)

# Inisialisasi Supabase
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("SUCCESS: Connected to Supabase.")
except Exception as e:
    print(f"ERROR: Failed to connect to Supabase: {e}")
    sys.exit(1)

def get_price(ticker):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            price = data['Close'].iloc[-1]
            print(f"DEBUG: Price for {ticker} is {price}")
            return price
        else:
            print(f"DEBUG: No data found for {ticker}")
    except Exception as e:
        print(f"DEBUG: Error fetching {ticker}: {e}")
    return None

def send_telegram(chat_id, message):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'}
    try:
        res = requests.post(url, json=payload, timeout=10)
        print(f"DEBUG: Telegram response: {res.status_code}")
        return res.status_code == 200
    except Exception as e:
        print(f"DEBUG: Telegram error: {e}")
        return False

def run_worker():
    try:
        print("DEBUG: Fetching alerts from 'active_alerts' table...")
        res = supabase.table("active_alerts").select("*").eq("triggered", False).execute()
        alerts = res.data
        print(f"DEBUG: Found {len(alerts)} active alerts.")
    except Exception as e:
        print(f"ERROR: Failed to fetch alerts: {e}")
        return

    if not alerts:
        print("INFO: No active alerts to process.")
        return

    ticker_map = {
        "XAUUSD": "GC=F", "XAGUSD": "SI=F", "BTCUSD": "BTC-USD",
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
        "WTI": "CL=F", "US100": "NQ=F", "Palladium": "PA=F", "Platinum": "PL=F",
        "GOOGL": "GOOGL", "AAPL": "AAPL", "BBCA.JK": "BBCA.JK", "TLKM.JK": "TLKM.JK"
    }

    for alert in alerts:
        inst = alert.get('instrument')
        target = alert.get('target')
        condition = alert.get('condition')
        chat_id = alert.get('chat_id')
        alert_id = alert.get('id')

        print(f"\n--- Processing Alert ID: {alert_id} ---")
        print(f"Instrument: {inst}, Target: {target}, Condition: {condition}")

        ticker = ticker_map.get(inst)
        if not ticker:
            print(f"WARNING: No ticker mapping for {inst}")
            continue

        current_price = get_price(ticker)
        if current_price is None:
            continue

        triggered = False
        if condition == "bullish" and current_price >= target:
            triggered = True
        elif condition == "bearish" and current_price <= target:
            triggered = True

        if triggered:
            print(f"ACTION: Triggering alert for {inst}!")
            # Update status
            try:
                supabase.table("active_alerts").update({"triggered": True}).eq("id", alert_id).execute()
                print("DEBUG: Supabase status updated to triggered=True")
            except Exception as e:
                print(f"ERROR: Failed to update Supabase: {e}")

            # Kirim Telegram
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")
            msg = (
                f"<b>🦅 AEROVULPIS SENTINEL ALERT</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>INSTRUMENT:</b> {inst}\n"
                f"<b>TARGET:</b> {target:.4f}\n"
                f"<b>CURRENT:</b> {current_price:.4f}\n"
                f"<b>TIME:</b> {now_wib}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<i>[STATUS]: TARGET REACHED</i>"
            )
            if send_telegram(chat_id, msg):
                print("SUCCESS: Telegram message sent.")
            else:
                print("FAILED: Could not send Telegram message.")
        else:
            print(f"INFO: Target not reached yet.")

if __name__ == "__main__":
    run_worker()
    print("\n--- AEROVULPIS DEBUG END ---")
