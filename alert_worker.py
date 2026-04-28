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

def parse_target_value(target_raw):
    """
    Parse target dari berbagai format:
    - "2,650.00" (TEXT baru) → 2650.0
    - "2650.0" (FLOAT lama) → 2650.0
    - 2650.0 (sudah FLOAT) → 2650.0
    """
    if target_raw is None:
        return 0.0
    
    # Kalau sudah float, return langsung
    if isinstance(target_raw, (int, float)):
        return float(target_raw)
    
    # Kalau string, bersihkan
    try:
        cleaned = str(target_raw).replace(",", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0

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
        target_raw = alert.get('target')
        target_value = alert.get('target_value')  # Coba ambil target_value dulu
        condition = alert.get('condition')
        chat_id = alert.get('chat_id')
        alert_id = alert.get('id')

        print(f"\n--- Processing Alert ID: {alert_id} ---")
        
        # Tentukan target numerik untuk perbandingan
        if target_value is not None and isinstance(target_value, (int, float)) and target_value > 0:
            target_num = float(target_value)
            target_display = str(target_raw) if target_raw else str(target_num)
            print(f"DEBUG: Using target_value field: {target_num}")
        else:
            target_num = parse_target_value(target_raw)
            target_display = str(target_raw) if target_raw else f"{target_num:,.2f}"
            print(f"DEBUG: Parsed target from 'target' field: {target_num}")
        
        print(f"Instrument: {inst}, Target Num: {target_num}, Target Display: {target_display}, Condition: {condition}")

        ticker = ticker_map.get(inst)
        if not ticker:
            print(f"WARNING: No ticker mapping for {inst}")
            continue

        current_price = get_price(ticker)
        if current_price is None:
            print(f"DEBUG: Could not fetch price for {ticker}, skipping...")
            continue

        print(f"DEBUG: Current price of {inst} = {current_price}, Target = {target_num}")

        triggered = False
        if condition == "bullish" and current_price >= target_num:
            triggered = True
            print(f"DEBUG: BULLISH condition met! {current_price} >= {target_num}")
        elif condition == "bearish" and current_price <= target_num:
            triggered = True
            print(f"DEBUG: BEARISH condition met! {current_price} <= {target_num}")

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
            
            # Format current_price untuk tampilan
            if inst in ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD"]:
                current_fmt = f"{current_price:,.2f}"
            else:
                current_fmt = f"{current_price:,.4f}"
            
            msg = (
                f"<b>🦅 AEROVULPIS SENTINEL ALERT</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>INSTRUMENT:</b> {inst}\n"
                f"<b>TARGET:</b> {target_display}\n"
                f"<b>CURRENT:</b> {current_fmt}\n"
                f"<b>TIME:</b> {now_wib}\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<i>[STATUS]: TARGET REACHED</i>"
            )
            if send_telegram(chat_id, msg):
                print("SUCCESS: Telegram message sent.")
            else:
                print("FAILED: Could not send Telegram message.")
        else:
            print(f"INFO: Target not reached. Current={current_price}, Target={target_num}, Condition={condition}")

if __name__ == "__main__":
    run_worker()
    print("\n--- AEROVULPIS DEBUG END ---")
