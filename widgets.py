import streamlit as st
import requests
import os
from supabase import create_client, Client
from datetime import datetime, timedelta
import pytz
import yfinance as yf
import json

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
    """Economic Radar Widget - RAPIH dengan format Actual/Forecast/Previous"""
    
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&family=Share+Tech+Mono&display=swap');
        
        .econ-radar-container {
            border: 1px solid rgba(0, 212, 255, 0.3);
            border-radius: 8px;
            padding: 28px;
            background: rgba(0, 20, 40, 0.5);
            box-shadow: 0 0 25px rgba(0, 212, 255, 0.08);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        
        .radar-header-stack {
            display: flex;
            flex-direction: column;
            align-items: center;
            margin-bottom: 20px;
            width: 100%;
            gap: 6px;
        }
        
        .radar-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 26px;
            font-weight: 700;
            color: #00d4ff;
            text-shadow: 0 0 12px rgba(0, 212, 255, 0.6);
            margin: 0;
            padding: 0 10px;
            text-transform: uppercase;
            letter-spacing: 3px;
            text-align: center;
            line-height: 1;
        }
        
        .radar-subtitle-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .radar-logo {
            width: 14px;
            height: 14px;
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        
        .radar-circle {
            position: absolute;
            width: 100%;
            height: 100%;
            border: 1px solid #00d4ff;
            border-radius: 50%;
            opacity: 0.5;
            animation: rdp 2s infinite;
        }
        
        .radar-sweep {
            position: absolute;
            width: 50%;
            height: 1px;
            background: linear-gradient(to right, transparent, #00d4ff);
            top: 50%;
            left: 50%;
            transform-origin: left center;
            animation: rsw 2s linear infinite;
        }
        
        @keyframes rdp {
            0%, 100% { transform: scale(1); opacity: 0.4; }
            50% { transform: scale(1.2); opacity: 0.8; }
        }
        
        @keyframes rsw {
            from { transform: rotate(0deg); }
            to { transform: rotate(360deg); }
        }
        
        .status-indicator {
            font-family: 'Share Tech Mono', monospace;
            font-size: 10px;
            color: #00ff88;
            letter-spacing: 1px;
            background: rgba(0, 255, 136, 0.05);
            padding: 2px 8px;
            border-radius: 3px;
            border: 1px solid rgba(0, 255, 136, 0.2);
            display: flex;
            align-items: center;
        }
        
        .status-dot {
            height: 5px;
            width: 5px;
            background: #00ff88;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
            box-shadow: 0 0 5px #00ff88;
            animation: pg 2s infinite;
        }
        
        @keyframes pg {
            0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.6); }
            70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }
        
        .econ-table {
            width: 100%;
            border-collapse: collapse;
            font-family: 'Share Tech Mono', monospace;
            font-size: 11px;
        }
        
        .econ-table th {
            background: rgba(0, 212, 255, 0.08);
            color: #00d4ff;
            padding: 10px 8px;
            text-align: center;
            font-family: 'Orbitron', sans-serif;
            font-size: 9px;
            letter-spacing: 2px;
            border-bottom: 1px solid rgba(0, 212, 255, 0.3);
        }
        
        .econ-table td {
            padding: 10px 8px;
            text-align: center;
            border-bottom: 1px solid rgba(0, 212, 255, 0.06);
            color: #8899bb;
        }
        
        .econ-table tr:hover td {
            background: rgba(0, 212, 255, 0.03);
            color: #c0d0e0;
        }
        
        .impact-high {
            color: #ff2a6d;
            text-shadow: 0 0 4px rgba(255, 42, 109, 0.4);
            font-weight: 700;
        }
        
        .impact-med {
            color: #ffcc00;
        }
        
        .impact-low {
            color: #00ff88;
        }
        
        .actual-val {
            color: #00ff88;
            font-weight: 700;
        }
        
        .forecast-val {
            color: #557799;
        }
        
        .previous-val {
            color: #445566;
        }
        
        .impact-legend {
            display: flex;
            justify-content: center;
            gap: 18px;
            margin-top: 14px;
            font-family: 'Share Tech Mono', monospace;
            font-size: 10px;
            flex-wrap: wrap;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            color: #8899bb;
        }
        
        .star-icon {
            font-size: 11px;
        }
        
        .high-impact { color: #ff2a6d; text-shadow: 0 0 4px rgba(255, 42, 109, 0.4); }
        .med-impact { color: #ffcc00; }
        .low-impact { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.markdown("""
    <div class="econ-radar-container">
        <div class="radar-header-stack">
            <h2 class="radar-title">ECONOMIC RADAR</h2>
            <div class="radar-subtitle-row">
                <div class="radar-logo"><div class="radar-circle"></div><div class="radar-sweep"></div></div>
                <div class="status-indicator"><span class="status-dot"></span>LIVE CONNECTION</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Ambil data economic calendar dari API (fallback: data statis)
    events = []
    
    # Coba ambil dari free API
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
                    actual = item.get('actual', '')
                    forecast = item.get('forecast', '')
                    previous = item.get('previous', '')
                    
                    # Format angka
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
                            else:
                                return str(v)
                        except:
                            return str(v)
                    
                    events.append({
                        'time': item.get('date', '')[-8:-3] if item.get('date') else '—',
                        'currency': item.get('currency', '—'),
                        'event': item.get('title', 'Unknown'),
                        'actual': fmt_val(actual),
                        'forecast': fmt_val(forecast),
                        'previous': fmt_val(previous),
                        'impact': item.get('importance', 1)
                    })
    except Exception:
        pass

    # Jika API gagal, tampilkan data default
    if not events:
        events = [
            {'time': '—', 'currency': 'USD', 'event': 'WAITING FOR DATA...', 'actual': '—', 'forecast': '—', 'previous': '—', 'impact': 1},
            {'time': '—', 'currency': 'USD', 'event': 'REFRESH TO LOAD ECONOMIC CALENDAR', 'actual': '—', 'forecast': '—', 'previous': '—', 'impact': 2},
        ]
    
    # Render table
    table_html = """
    <table class="econ-table">
        <thead>
            <tr>
                <th>TIME</th>
                <th>CUR</th>
                <th>EVENT</th>
                <th>ACTUAL</th>
                <th>FORECAST</th>
                <th>PREVIOUS</th>
            </tr>
        </thead>
        <tbody>
    """
    
    for ev in events:
        impact_class = 'impact-high' if ev['impact'] >= 3 else ('impact-med' if ev['impact'] == 2 else 'impact-low')
        impact_stars = '★★★' if ev['impact'] >= 3 else ('★★☆' if ev['impact'] == 2 else '★☆☆')
        
        table_html += f"""
            <tr>
                <td style="color:#00d4ff;">{ev['time']}</td>
                <td><span class="{impact_class}">{ev['currency']} {impact_stars}</span></td>
                <td style="text-align:left;">{ev['event']}</td>
                <td class="actual-val">{ev['actual']}</td>
                <td class="forecast-val">{ev['forecast']}</td>
                <td class="previous-val">{ev['previous']}</td>
            </tr>
        """
    
    table_html += """
        </tbody>
    </table>
    """
    
    st.markdown(table_html, unsafe_allow_html=True)
    
    # Legend
    st.markdown("""
        <div class="impact-legend">
            <div class="legend-item"><span class="star-icon high-impact">★★★</span> High Impact</div>
            <div class="legend-item"><span class="star-icon med-impact">★★☆</span> Medium</div>
            <div class="legend-item"><span class="star-icon low-impact">★☆☆</span> Low</div>
        </div>
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

    # Preview - Cyber Digital Style
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

    # ========== ACTIVATE BUTTON (FIXED - SKIP target_value JIKA TIDAK ADA) ==========
    if st.button("LOCK TARGET & ACTIVATE SENSOR", key="alert_activate_fix", type="primary", use_container_width=True):
        if price_target > 0 and telegram_chat_id:
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")
            formatted_target_display = f"{price_target:,.{decimal_places}f}"
            target_value_float = round(price_target, decimal_places)

            if "active_alerts" not in st.session_state:
                st.session_state.active_alerts = []
            
            # Insert tanpa target_value dulu (hindari error kolom tidak ada)
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
                
                # Simpan target_value ke session state untuk monitoring lokal
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