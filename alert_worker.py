import os
import sys
import time
import requests
import yfinance as yf
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz

# ============================================================
# KONFIGURASI
# ============================================================
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

print("=" * 60)
print("🦅 AEROVULPIS SENTINEL WORKER V3.0")
print(f"Start Time: {datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 60)

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ ERROR: SUPABASE_URL or SUPABASE_KEY is missing!")
    sys.exit(1)

if not TELEGRAM_BOT_TOKEN:
    print("❌ ERROR: TELEGRAM_BOT_TOKEN is missing!")
    sys.exit(1)

# ============================================================
# INISIALISASI SUPABASE
# ============================================================
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    print("✅ SUCCESS: Connected to Supabase.")
except Exception as e:
    print(f"❌ ERROR: Failed to connect to Supabase: {e}")
    sys.exit(1)

# ============================================================
# FUNGSI HELPER
# ============================================================

def get_price(ticker):
    """
    Mengambil harga terbaru dari yfinance.
    Return: (float) price atau None jika gagal.
    """
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if not data.empty:
            price = data['Close'].iloc[-1]
            return price
        else:
            print(f"DEBUG: No data found for {ticker}")
    except Exception as e:
        print(f"DEBUG: Error fetching {ticker}: {e}")
    return None


def get_cached_price(instrument):
    """
    Mengambil harga dari market_prices cache di Supabase.
    Return: (float) price atau None jika tidak ada.
    """
    try:
        res = supabase.table("market_prices").select("price")\
            .eq("instrument", instrument)\
            .order("updated_at", desc=True)\
            .limit(1)\
            .execute()
        if res.data and res.data[0].get("price"):
            return float(res.data[0]["price"])
    except Exception as e:
        print(f"DEBUG: Cache lookup failed for {instrument}: {e}")
    return None


def send_telegram(chat_id, message):
    """
    Kirim notifikasi via Telegram Bot API.
    Return: True jika berhasil, False jika gagal.
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        res = requests.post(url, json=payload, timeout=10)
        if res.status_code == 200:
            print(f"✅ Telegram sent to {chat_id}")
            return True
        else:
            print(f"DEBUG: Telegram response: {res.status_code} - {res.text[:200]}")
            return False
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
    
    if isinstance(target_raw, (int, float)):
        return float(target_raw)
    
    try:
        cleaned = str(target_raw).replace(",", "").strip()
        return float(cleaned)
    except (ValueError, AttributeError):
        return 0.0


def format_price_display(price, instrument_name):
    """
    Format harga sesuai jenis instrumen untuk tampilan.
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
    
    # Default
    else:
        if price >= 1000:
            return f"{price:,.2f}"
        elif price >= 1:
            return f"{price:,.2f}"
        else:
            return f"{price:,.4f}".rstrip('0').rstrip('.')


def is_alert_expired(created_at_str):
    """
    Cek apakah alert sudah lebih dari 7 hari.
    Return: True jika expired.
    """
    if not created_at_str:
        return False
    
    try:
        created_at_str = str(created_at_str).replace('Z', '+00:00')
        alert_date = datetime.fromisoformat(created_at_str)
        now = datetime.now(pytz.UTC)
        return (now - alert_date) > timedelta(days=7)
    except Exception:
        return False


# ============================================================
# TICKER MAPPING
# ============================================================
TICKER_MAP = {
    # Forex
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "EURUSD": "EURUSD=X",
    "GBPUSD": "GBPUSD=X",
    "USDJPY": "USDJPY=X",
    "AUDUSD": "AUDUSD=X",
    "USDCHF": "USDCHF=X",
    
    # Crypto
    "BTCUSD": "BTC-USD",
    "ETHUSD": "ETH-USD",
    "SOLUSD": "SOL-USD",
    "XRPUSD": "XRP-USD",
    "BNBUSD": "BNB-USD",
    
    # Commodities
    "WTI": "CL=F",
    "NATURAL GAS": "NG=F",
    "COPPER": "HG=F",
    "PALLADIUM": "PA=F",
    "PLATINUM": "PL=F",
    
    # Indices
    "US100": "NQ=F",
    "NASDAQ-100": "^IXIC",
    "S&P 500": "^GSPC",
    "DOW JONES": "^DJI",
    
    # US Stocks
    "GOOGL": "GOOGL",
    "AAPL": "AAPL",
    "NVDA": "NVDA",
    "TSLA": "TSLA",
    "MSFT": "MSFT",
    "AMZN": "AMZN",
    
    # ID Stocks
    "BBCA.JK": "BBCA.JK",
    "BBRI.JK": "BBRI.JK",
    "TLKM.JK": "TLKM.JK",
}


# ============================================================
# MAIN WORKER FUNCTION
# ============================================================

def run_worker():
    """
    Fungsi utama worker:
    1. Ambil semua alert yang belum triggered dari Supabase
    2. Cek harga dari market_prices cache (prioritas) atau yfinance (fallback)
    3. Bandingkan dengan target
    4. Kirim Telegram + update status kalo triggered
    5. Hapus alert expired (>7 hari)
    """
    print(f"\n{'─' * 50}")
    print(f"🔍 Checking alerts... [{datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%H:%M:%S')}]")
    
    # 1. Ambil alert dari Supabase
    try:
        res = supabase.table("active_alerts").select("*").eq("triggered", False).execute()
        alerts = res.data
    except Exception as e:
        print(f"❌ ERROR: Failed to fetch alerts: {e}")
        return
    
    if not alerts:
        print("ℹ️  No active alerts to process.")
        return
    
    print(f"📋 Found {len(alerts)} active alert(s)")
    
    # Statistik
    triggered_count = 0
    expired_count = 0
    skipped_count = 0
    
    # 2. Proses setiap alert
    for alert in alerts:
        inst = alert.get('instrument')
        target_raw = alert.get('target')
        target_value = alert.get('target_value')
        condition = alert.get('condition')
        chat_id = alert.get('chat_id')
        alert_id = alert.get('id')
        created_at = alert.get('created_at', '')
        
        print(f"\n{'─' * 40}")
        print(f"📌 Alert ID: {alert_id} | {inst}")
        
        # Cek expired
        if is_alert_expired(created_at):
            print(f"⏰ Alert expired (>7 days), marking as triggered")
            try:
                supabase.table("active_alerts").update({"triggered": True}).eq("id", alert_id).execute()
                expired_count += 1
            except Exception as e:
                print(f"ERROR: Failed to expire alert: {e}")
            continue
        
        # Tentukan target numerik
        if target_value is not None and isinstance(target_value, (int, float)) and target_value > 0:
            target_num = float(target_value)
            target_display = str(target_raw) if target_raw else format_price_display(target_num, inst)
        else:
            target_num = parse_target_value(target_raw)
            target_display = str(target_raw) if target_raw else format_price_display(target_num, inst)
        
        print(f"Target: {target_display} | Condition: {condition}")
        
        # 3. Ambil harga: CACHE DULU, baru fallback ke yfinance
        current_price = get_cached_price(inst)
        
        if current_price:
            print(f"📦 Using CACHED price: {current_price}")
        else:
            ticker = TICKER_MAP.get(inst)
            if ticker:
                current_price = get_price(ticker)
                if current_price:
                    print(f"📡 Using YFINANCE price: {current_price}")
            
            if current_price is None:
                # Coba tanpa mapping (mungkin inst langsung ticker)
                current_price = get_price(inst)
                if current_price:
                    print(f"📡 Using YFINANCE direct: {current_price}")
        
        if current_price is None:
            print(f"⚠️  Could not fetch price for {inst}, skipping...")
            skipped_count += 1
            continue
        
        # Format untuk display
        formatted_price = format_price_display(current_price, inst)
        formatted_target = format_price_display(target_num, inst)
        
        print(f"Current: {formatted_price} | Target: {formatted_target}")
        
        # 4. Cek kondisi trigger
        triggered = False
        if condition == "bullish" and current_price >= target_num:
            triggered = True
            print(f"🚀 BULLISH triggered! {formatted_price} >= {formatted_target}")
        elif condition == "bearish" and current_price <= target_num:
            triggered = True
            print(f"🔻 BEARISH triggered! {formatted_price} <= {formatted_target}")
        
        # 5. Kirim notifikasi + update Supabase
        if triggered:
            # Update status di Supabase
            try:
                supabase.table("active_alerts").update({
                    "triggered": True,
                    "triggered_at": datetime.now(pytz.UTC).isoformat(),
                    "triggered_price": current_price
                }).eq("id", alert_id).execute()
                print("✅ Supabase updated: triggered=True")
            except Exception as e:
                print(f"❌ ERROR: Failed to update Supabase: {e}")
            
            # Buat pesan Telegram
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")
            
            msg = (
                f"<b>🦅 AEROVULPIS SENTINEL ALERT</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<b>INSTRUMENT:</b> {inst}\n"
                f"<b>TARGET:</b> {formatted_target}\n"
                f"<b>CURRENT:</b> {formatted_price}\n"
                f"<b>TIME:</b> {now_wib} WIB\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"<i>[STATUS]: TARGET REACHED ✅</i>"
            )
            
            # Kirim Telegram
            if send_telegram(chat_id, msg):
                triggered_count += 1
            else:
                print("❌ Failed to send Telegram notification!")
        else:
            diff_pct = ((current_price - target_num) / target_num) * 100
            print(f"⏳ Not triggered yet. Diff: {diff_pct:+.2f}%")
    
    # Ringkasan
    print(f"\n{'═' * 50}")
    print(f"📊 SUMMARY:")
    print(f"   Total alerts: {len(alerts)}")
    print(f"   Triggered: {triggered_count}")
    print(f"   Expired: {expired_count}")
    print(f"   Skipped: {skipped_count}")
    print(f"   Remaining: {len(alerts) - triggered_count - expired_count - skipped_count}")
    print(f"{'═' * 50}")


# ============================================================
# MAIN LOOP - JALAN TERUS 24/7
# ============================================================

if __name__ == "__main__":
    CHECK_INTERVAL = 60  # Detik (bisa diubah: 30, 45, 60, 120)
    
    print(f"Mode: Continuous Monitoring ({CHECK_INTERVAL}s interval)")
    print("Press Ctrl+C to stop\n")
    
    while True:
        try:
            run_worker()
        except Exception as e:
            print(f"💥 CRITICAL ERROR: {e}")
            print("Worker will retry in 60 seconds...")
        
        print(f"\n⏳ Sleeping {CHECK_INTERVAL}s... [{datetime.now(pytz.timezone('Asia/Jakarta')).strftime('%H:%M:%S')}]")
        time.sleep(CHECK_INTERVAL)
