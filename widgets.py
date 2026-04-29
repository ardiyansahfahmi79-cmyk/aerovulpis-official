import streamlit as st
import requests
import os
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import yfinance as yf

url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]

def format_price_display(price, instrument_name):
    """Format harga - XAUUSD: 4,756.00 | Forex: 1.0850"""
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
        return f"{price:,.4f}".rstrip('0').rstrip('.')
    elif any(idx in name_upper for idx in ["NASDAQ", "S&P", "DOW", "DAX", "IHSG"]):
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

def get_cached_price(instrument_name):
    """Ambil harga dari Supabase cache, fallback ke yfinance"""
    try:
        supabase = create_client(url, key)
        res = supabase.table("market_prices").select("*").eq("instrument", instrument_name).execute()
        
        if res.data and res.data[0].get("price") and res.data[0]["price"] > 0:
            return {"price": res.data[0]["price"], "source": "SUPABASE"}
        
        # Fallback yfinance
        ticker_map = {
            "XAUUSD": "GC=F", "XAGUSD": "SI=F",
            "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
            "AUDUSD": "AUDUSD=X", "USDCHF": "USDCHF=X",
            "BTCUSD": "BTC-USD", "ETHUSD": "ETH-USD", "SOLUSD": "SOL-USD",
            "WTI": "CL=F", "US100": "^IXIC",
            "Palladium": "PA=F", "Platinum": "PL=F",
            "GOOGL": "GOOGL", "AAPL": "AAPL",
            "BBCA.JK": "BBCA.JK", "TLKM.JK": "TLKM.JK"
        }
        
        ticker = ticker_map.get(instrument_name)
        if ticker:
            yt = yf.Ticker(ticker)
            hist = yt.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
                if instrument_name in ["XAUUSD", "XAGUSD"]:
                    price = round(price, 2)
                return {"price": price, "source": "LIVE"}
    except Exception:
        pass
    
    return {"price": 0.0, "source": "UNAVAILABLE"}


def economic_calendar_widget():
    """Economic Radar Widget"""
    
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&family=Share+Tech+Mono&display=swap');
        .radar-header-stack {
            display: flex; flex-direction: column; align-items: center; margin-bottom: 20px; width: 100%; gap: 6px;
        }
        .radar-title {
            font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 700;
            color: #00d4ff; text-shadow: 0 0 12px rgba(0, 212, 255, 0.6);
            margin: 0; text-transform: uppercase; letter-spacing: 3px; text-align: center;
        }
        .radar-subtitle-row { display: flex; align-items: center; justify-content: center; gap: 8px; }
        .status-indicator {
            font-family: 'Share Tech Mono', monospace; font-size: 10px; color: #00ff88;
            letter-spacing: 1px; background: rgba(0, 255, 136, 0.05); padding: 4px 12px;
            border-radius: 3px; border: 1px solid rgba(0, 255, 136, 0.2);
            display: flex; align-items: center;
        }
        .status-dot {
            height: 6px; width: 6px; background: #00ff88; border-radius: 50%;
            display: inline-block; margin-right: 8px;
            box-shadow: 0 0 8px #00ff88; animation: pg 2s infinite;
        }
        @keyframes pg {
            0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.6); }
            70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }
        .econ-event-row {
            background: rgba(0, 18, 36, 0.5);
            border: 1px solid rgba(0, 212, 255, 0.08);
            border-radius: 3px;
            padding: 12px 14px;
            margin-bottom: 4px;
            transition: all 0.3s ease;
        }
        .econ-event-row:hover {
            background: rgba(0, 212, 255, 0.03);
            border-color: rgba(0, 212, 255, 0.25);
        }
        .impact-high { color: #ff2a6d; text-shadow: 0 0 4px rgba(255, 42, 109, 0.4); }
        .impact-med { color: #ffcc00; }
        .impact-low { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="radar-header-stack">
        <h2 class="radar-title">ECONOMIC RADAR</h2>
        <div class="radar-subtitle-row">
            <div class="status-indicator"><span class="status-dot"></span>LIVE CONNECTION</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Ambil data
    events = []
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        end_date = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d')
        resp = requests.get(
            f"https://economic-calendar.tradingview.com/events?from={today}T00:00:00Z&to={end_date}T23:59:59Z&countries=US,EU,GB,JP,AU,CA,CH,NZ",
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get('result'):
                for item in data['result'][:15]:
                    def fmt_val(v):
                        if v is None or v == '' or v == 'N/A':
                            return '—'
                        try:
                            num = float(v)
                            if abs(num) >= 1000:
                                return f"{num:,.1f}"
                            elif abs(num) >= 1:
                                return f"{num:.2f}"
                            elif abs(num) > 0:
                                return f"{num:.4f}"
                            return str(v)
                        except:
                            return str(v)
                    
                    events.append({
                        'time': item.get('date', '')[-8:-3] if item.get('date') else '—',
                        'currency': item.get('currency', '—'),
                        'event': item.get('title', 'Unknown'),
                        'actual': fmt_val(item.get('actual', '')),
                        'forecast': fmt_val(item.get('forecast', '')),
                        'previous': fmt_val(item.get('previous', '')),
                        'impact': item.get('importance', 1)
                    })
    except Exception:
        pass

    if not events:
        events = [
            {'time': '—', 'currency': 'USD', 'event': 'WAITING FOR DATA...', 'actual': '—', 'forecast': '—', 'previous': '—', 'impact': 1},
            {'time': '—', 'currency': 'USD', 'event': 'REFRESH TO LOAD ECONOMIC CALENDAR', 'actual': '—', 'forecast': '—', 'previous': '—', 'impact': 2},
        ]

    # Render event
    for ev in events:
        stars = '★★★' if ev['impact'] >= 3 else ('★★☆' if ev['impact'] == 2 else '★☆☆')
        impact_css = 'impact-high' if ev['impact'] >= 3 else ('impact-med' if ev['impact'] == 2 else 'impact-low')
        
        st.markdown(f"""
        <div class="econ-event-row" style="display:flex;align-items:center;gap:10px;font-family:'Share Tech Mono',monospace;">
            <span style="color:#00d4ff;min-width:45px;font-size:11px;">{ev['time']}</span>
            <span class="{impact_css}" style="min-width:60px;font-size:10px;letter-spacing:1px;">{ev['currency']} {stars}</span>
            <span style="color:#8899bb;flex:1;font-size:11px;text-align:left;">{ev['event']}</span>
        </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3, c4 = st.columns([0.8, 0.8, 0.8, 3.6])
        with c1:
            st.markdown(f"<p style='font-size:8px;color:#557799;margin:0;letter-spacing:1px;'>ACT</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-family:Share Tech Mono;font-size:13px;color:#00ff88;margin:0;font-weight:700;'>{ev['actual']}</p>", unsafe_allow_html=True)
        with c2:
            st.markdown(f"<p style='font-size:8px;color:#557799;margin:0;letter-spacing:1px;'>FCT</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-family:Share Tech Mono;font-size:13px;color:#557799;margin:0;'>{ev['forecast']}</p>", unsafe_allow_html=True)
        with c3:
            st.markdown(f"<p style='font-size:8px;color:#557799;margin:0;letter-spacing:1px;'>PRV</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-family:Share Tech Mono;font-size:13px;color:#445566;margin:0;'>{ev['previous']}</p>", unsafe_allow_html=True)
        with c4:
            st.markdown("")
        
        st.markdown("<hr style='border-color:rgba(0,212,255,0.05);margin:2px 0;'>", unsafe_allow_html=True)

    # Legend
    st.markdown("""
    <div style="display:flex;justify-content:center;gap:18px;margin-top:14px;font-family:'Share Tech Mono',monospace;font-size:10px;">
        <span class="impact-high">★★★ High Impact</span>
        <span class="impact-med">★★☆ Medium</span>
        <span class="impact-low">★☆☆ Low</span>
    </div>
    """, unsafe_allow_html=True)


def smart_alert_widget():
    """SMART ALERT CENTER - Current price dari Supabase cache"""
    
    instruments_list = [
        "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD",
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
        "WTI", "US100", "Palladium", "Platinum",
        "GOOGL", "AAPL", "BBCA.JK", "TLKM.JK"
    ]
    
    selected_instrument = st.selectbox(
        "INSTRUMENT SELECTOR",
        instruments_list,
        key="alert_instrument_fix"
    )

    # ========== CURRENT PRICE ==========
    price_data = get_cached_price(selected_instrument)
    current_price = price_data["price"]
    data_source = price_data["source"]
    price_display = format_price_display(current_price, selected_instrument)
    
    st.markdown(f"""
    <div style="background:rgba(0,212,255,0.04);border:1px solid rgba(0,212,255,0.2);padding:14px;border-radius:4px;margin-bottom:16px;text-align:center;">
        <span style="font-family:'Share Tech Mono',monospace;font-size:10px;color:#557799;letter-spacing:2px;">CURRENT PRICE</span><br>
        <span style="font-family:'Orbitron',sans-serif;font-size:22px;color:#00ff88;text-shadow:0 0 12px rgba(0,255,136,0.5);letter-spacing:2px;">{price_display}</span>
        <br><span style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#445566;">SOURCE: {data_source}</span>
    </div>
    """, unsafe_allow_html=True)

    # ========== DIGITAL PRICE TARGET ==========
    if selected_instrument in ["XAUUSD", "XAGUSD"]:
        decimal_places = 2
        default_display = "0"
    elif selected_instrument in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]:
        decimal_places = 4
        default_display = "0"
    else:
        decimal_places = 2
        default_display = "0"
    
    st.markdown('<p style="font-family:Orbitron;font-size:9px;color:#8899bb;letter-spacing:2px;text-transform:uppercase;margin:0 0 4px 0;">DIGITAL PRICE TARGET</p>', unsafe_allow_html=True)
    
    raw_target_input = st.text_input(
        "TARGET",
        value=default_display,
        key="alert_target_fix_text",
        label_visibility="collapsed",
        placeholder="Contoh: 2,650"
    )

    def parse_localized_number(input_str):
        if not input_str or not input_str.strip():
            return 0.0
        cleaned = input_str.strip()
        has_dot = "." in cleaned
        has_comma = "," in cleaned
        if has_comma and not has_dot:
            parts = cleaned.split(",")
            after_last_comma = parts[-1]
            if len(parts) == 2 and len(after_last_comma) <= 2:
                return float(cleaned.replace(",", "."))
            else:
                return float(cleaned.replace(",", ""))
        elif has_comma and has_dot:
            cleaned = cleaned.replace(",", "")
            return float(cleaned)
        else:
            return float(cleaned)

    try:
        price_target = parse_localized_number(raw_target_input)
    except ValueError:
        price_target = 0.0
        st.caption("Format tidak valid. Gunakan koma untuk ribuan (contoh: 2,650)")

    # Preview - Cyber Digital
    if price_target > 0:
        formatted_preview = f"{price_target:,.{decimal_places}f}"
        st.markdown(f"""
        <div style="background:rgba(0,255,136,0.03);border:1px solid rgba(0,255,136,0.15);padding:10px;border-radius:3px;margin-top:8px;text-align:center;">
            <span style="font-family:'Share Tech Mono',monospace;font-size:9px;color:#557799;letter-spacing:2px;">[ TARGET LOCKED ]</span><br>
            <span style="font-family:'Orbitron',sans-serif;font-size:16px;color:#00ff88;text-shadow:0 0 8px rgba(0,255,136,0.4);letter-spacing:2px;">{formatted_preview}</span>
        </div>
        """, unsafe_allow_html=True)

    # Telegram Chat ID
    st.markdown('<p style="font-family:Orbitron;font-size:9px;color:#8899bb;letter-spacing:2px;text-transform:uppercase;margin:16px 0 4px 0;">TELEGRAM CHAT ID</p>', unsafe_allow_html=True)
    telegram_chat_id = st.text_input("CHAT ID", value="", placeholder="Enter Telegram Chat ID...", key="alert_chatid_fix", label_visibility="collapsed")

    # Condition Trigger
    st.markdown('<p style="font-family:Orbitron;font-size:9px;color:#8899bb;letter-spacing:2px;text-transform:uppercase;margin:16px 0 4px 0;">CONDITION TRIGGER</p>', unsafe_allow_html=True)
    condition_label = st.radio("CONDITION", ["BREAKOUT ABOVE [BULLISH]", "BREAKDOWN BELOW [BEARISH]"], key="alert_cond_fix", label_visibility="collapsed")
    condition_value = "bullish" if "ABOVE" in condition_label else "bearish"

    # ========== ACTIVATE BUTTON ==========
    if st.button("LOCK TARGET & ACTIVATE SENSOR", key="alert_activate_fix", type="primary", use_container_width=True):
        if price_target > 0 and telegram_chat_id:
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")
            formatted_target_display = f"{price_target:,.{decimal_places}f}"
            target_value_float = round(price_target, decimal_places)

            if "active_alerts" not in st.session_state:
                st.session_state.active_alerts = []
            
            alert_data = {
                "instrument": selected_instrument,
                "target": formatted_target_display,
                "condition": condition_value,
                "chat_id": telegram_chat_id,
                "time_created": now_wib,
                "triggered": False
            }
            
            try:
                supabase = create_client(url, key)
                supabase.table("active_alerts").insert(alert_data).execute()
                
                alert_data["target_value"] = target_value_float
                st.session_state.active_alerts.append(alert_data)
                
                st.markdown(f"""
                <div style="background:rgba(0,212,255,0.06);border-left:3px solid #00d4ff;padding:16px;border-radius:3px;margin-top:18px;box-shadow:0 0 15px rgba(0,212,255,0.1);">
                    <p style="font-family:Orbitron;font-size:12px;color:#00d4ff;margin:0 0 8px;letter-spacing:2px;">/// SENSOR ACTIVATED ///</p>
                    <p style="font-family:Rajdhani;font-size:13px;color:#00d4ff;opacity:0.9;margin:2px 0;">INSTRUMENT: {selected_instrument}</p>
                    <p style="font-family:Rajdhani;font-size:13px;color:#00d4ff;opacity:0.9;margin:2px 0;">TARGET: {formatted_target_display}</p>
                    <p style="font-family:Share Tech Mono;font-size:9px;color:#00ff88;margin:6px 0 0 0;letter-spacing:1px;">[STATUS]: MONITORING_24/7 | TELEGRAM_LINKED</p>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"DATABASE ERROR: {str(e)}")
        else:
            st.warning("ENTER VALID TARGET PRICE AND TELEGRAM CHAT ID")