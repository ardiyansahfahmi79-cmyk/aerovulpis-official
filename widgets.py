import streamlit as st
import requests
import os
from supabase import create_client, Client

url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]

def economic_calendar_widget():
    """Economic Radar Widget - Cyber Tech Style"""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');
        .economic-radar-container {
            border: 1px solid rgba(0, 212, 255, 0.3); border-radius: 8px; padding: 28px;
            background: rgba(0, 20, 40, 0.5); box-shadow: 0 0 25px rgba(0, 212, 255, 0.08);
            margin-bottom: 10px; position: relative; overflow: hidden;
        }
        .radar-header-stack { display: flex; flex-direction: column; align-items: center; margin-bottom: 14px; width: 100%; gap: 6px; }
        .radar-title { font-family: 'Orbitron', sans-serif; font-size: 26px; font-weight: 700; color: #00d4ff; text-shadow: 0 0 12px rgba(0, 212, 255, 0.6); margin: 0; padding: 0 10px; text-transform: uppercase; letter-spacing: 3px; text-align: center; line-height: 1; }
        .radar-subtitle-row { display: flex; align-items: center; justify-content: center; gap: 8px; }
        .radar-logo { width: 14px; height: 14px; position: relative; display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
        .radar-circle { position: absolute; width: 100%; height: 100%; border: 1px solid #00d4ff; border-radius: 50%; opacity: 0.5; animation: radarDiscPulse 2s infinite; }
        .radar-sweep { position: absolute; width: 50%; height: 1px; background: linear-gradient(to right, transparent, #00d4ff); top: 50%; left: 50%; transform-origin: left center; animation: radarSweepWidget 2s linear infinite; }
        @keyframes radarDiscPulse { 0%, 100% { transform: scale(1); opacity: 0.4; } 50% { transform: scale(1.2); opacity: 0.8; } }
        @keyframes radarSweepWidget { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .status-indicator { font-family: 'Share Tech Mono', monospace; font-size: 10px; color: #00ff88; letter-spacing: 1px; background: rgba(0, 255, 136, 0.05); padding: 2px 8px; border-radius: 3px; border: 1px solid rgba(0, 255, 136, 0.2); display: flex; align-items: center; }
        .status-dot { height: 5px; width: 5px; background-color: #00ff88; border-radius: 50%; display: inline-block; margin-right: 6px; box-shadow: 0 0 5px #00ff88; animation: pulse-green 2s infinite; }
        @keyframes pulse-green { 0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.6); } 70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(0, 255, 136, 0); } 100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); } }
        .tradingview-widget-container iframe { border-radius: 6px !important; filter: brightness(0.9) contrast(1.05); }
        .impact-legend { display: flex; justify-content: center; gap: 18px; margin-top: 14px; font-family: 'Share Tech Mono', monospace; font-size: 10px; flex-wrap: wrap; }
        .legend-item { display: flex; align-items: center; gap: 6px; color: #8899bb; }
        .star-icon { font-size: 11px; }
        .high-impact { color: #ff2a6d; text-shadow: 0 0 4px rgba(255, 42, 109, 0.4); }
        .med-impact { color: #ffcc00; }
        .low-impact { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="economic-radar-container">
        <div class="radar-header-stack">
            <h2 class="radar-title">ECONOMIC RADAR</h2>
            <div class="radar-subtitle-row">
                <div class="radar-logo"><div class="radar-circle"></div><div class="radar-sweep"></div></div>
                <div class="status-indicator"><span class="status-dot"></span>LIVE CONNECTION</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    tradingview_html = """
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
      {"colorTheme":"dark","isTransparent":true,"width":"100%","height":"450","locale":"en","importanceFilter":"-1,0,1","currencyFilter":"USD,EUR,GBP,JPY,AUD,CAD,CHF,NZD"}
      </script>
    </div>
    """
    try:
        st.components.v1.html(tradingview_html, height=450)
    except Exception as e:
        st.error(f"ECONOMIC RADAR LOAD ERROR: {str(e)}")

    st.markdown("""
        <div class="impact-legend">
            <div class="legend-item"><span class="star-icon high-impact">★★★</span> High Impact</div>
            <div class="legend-item"><span class="star-icon med-impact">★★☆</span> Medium</div>
            <div class="legend-item"><span class="star-icon low-impact">★☆☆</span> Low</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def smart_alert_widget():
    """
    SMART ALERT CENTER - MURNI WIDGET INPUT
    TIDAK ADA LOGO, TIDAK ADA HEADER, TIDAK ADA JUDUL AEROVULPIS
    Logo dan judul dihandle oleh streamlit_app.py
    """
    
    instruments_list = [
        "XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD",
        "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF",
        "WTI", "US100", "Palladium", "Platinum",
        "GOOGL", "AAPL", "BBCA.JK", "TLKM.JK"
    ]
    
    selected_instrument = st.selectbox("INSTRUMENT SELECTOR", instruments_list, key="alert_instrument_v2")

    # ====================== CURRENT PRICE (100% SAMA DENGAN LIVE DASHBOARD) ======================
    current_price = 0.0
    price_display = "0.00"
    data_source = "NO DATA"
    
    try:
        from streamlit_app import get_cached_market_price_full, get_market_data, instruments
        
        # 1. AMBIL DARI SUPABASE CACHE (FUNGSI SAMA DENGAN LIVE DASHBOARD)
        cached = get_cached_market_price_full(selected_instrument)
        
        if cached and cached.get("price") and cached["price"] > 0:
            current_price = cached["price"]
            data_source = "SUPABASE"
        else:
            # 2. FALLBACK: AMBIL LIVE SEPERTI LIVE DASHBOARD
            ticker_to_fetch = None
            for cat in instruments.values():
                if selected_instrument in cat:
                    ticker_to_fetch = cat[selected_instrument]
                    break
            if ticker_to_fetch:
                m_data = get_market_data(ticker_to_fetch)
                if m_data and m_data.get("price"):
                    current_price = m_data["price"]
                    data_source = m_data.get("source", "LIVE")
        
        # 3. FORMAT HARGA (100% SAMA DENGAN format_price_display DI STREAMLIT_APP)
        if selected_instrument in ["XAUUSD", "XAGUSD"]:
            price_display = f"{current_price:,.2f}"
        elif selected_instrument in ["BTCUSD", "ETHUSD"]:
            price_display = f"{current_price:,.2f}"
        elif selected_instrument in ["SOLUSD"]:
            price_display = f"{current_price:,.2f}"
        elif selected_instrument in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]:
            price_display = f"{current_price:,.4f}".rstrip('0').rstrip('.')
        elif selected_instrument in ["WTI", "US100"]:
            price_display = f"{current_price:,.2f}"
        else:
            price_display = f"{current_price:,.2f}"
            
    except Exception as e:
        price_display = "ERROR"
        data_source = "ERROR"
    
    st.markdown(f"""
    <div style="background:rgba(0,212,255,0.04);border:1px solid rgba(0,212,255,0.2);padding:14px;border-radius:4px;margin-bottom:16px;text-align:center;">
        <span style="font-family:'Share Tech Mono',monospace;font-size:10px;color:#557799;letter-spacing:2px;">CURRENT PRICE</span><br>
        <span style="font-family:'Orbitron',sans-serif;font-size:22px;color:#00ff88;text-shadow:0 0 12px rgba(0,255,136,0.5);letter-spacing:2px;">{price_display}</span>
        <br><span style="font-family:'Share Tech Mono',monospace;font-size:8px;color:#445566;">SOURCE: {data_source}</span>
    </div>
    """, unsafe_allow_html=True)

    # Digital Price Target
    st.markdown('<p style="font-family:Orbitron;font-size:9px;color:#8899bb;letter-spacing:2px;text-transform:uppercase;margin:0 0 4px 0;">DIGITAL PRICE TARGET</p>', unsafe_allow_html=True)
    price_target = st.number_input("TARGET", min_value=0.0, format="%.4f", step=0.0001, key="alert_target_v2", label_visibility="collapsed")

    # Telegram Chat ID
    st.markdown('<p style="font-family:Orbitron;font-size:9px;color:#8899bb;letter-spacing:2px;text-transform:uppercase;margin:16px 0 4px 0;">TELEGRAM CHAT ID</p>', unsafe_allow_html=True)
    telegram_chat_id = st.text_input("CHAT ID", value="", placeholder="Enter Telegram Chat ID...", key="alert_chatid_v2", label_visibility="collapsed")

    # Condition Trigger
    st.markdown('<p style="font-family:Orbitron;font-size:9px;color:#8899bb;letter-spacing:2px;text-transform:uppercase;margin:16px 0 4px 0;">CONDITION TRIGGER</p>', unsafe_allow_html=True)
    condition_label = st.radio("CONDITION", ["BREAKOUT ABOVE [BULLISH]", "BREAKDOWN BELOW [BEARISH]"], key="alert_cond_v2", label_visibility="collapsed")
    condition_value = "bullish" if "ABOVE" in condition_label else "bearish"

    # ACTIVATE BUTTON
    if st.button("LOCK TARGET & ACTIVATE SENSOR", key="alert_activate_v2", type="primary", use_container_width=True):
        if price_target > 0 and telegram_chat_id:
            from datetime import datetime
            import pytz
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")

            if "active_alerts" not in st.session_state:
                st.session_state.active_alerts = []
            
            alert_data = {
                "instrument": selected_instrument,
                "target": price_target,
                "condition": condition_value,
                "chat_id": telegram_chat_id,
                "time_created": now_wib,
                "triggered": False
            }
            st.session_state.active_alerts.append(alert_data)
            
            try:
                supabase: Client = create_client(url, key)
                supabase.table("active_alerts").insert(alert_data).execute()
                
                st.markdown(f"""
                <div style="background:rgba(0,212,255,0.06);border-left:3px solid #00d4ff;padding:16px;border-radius:3px;margin-top:18px;box-shadow:0 0 15px rgba(0,212,255,0.1);">
                    <p style="font-family:Orbitron;font-size:12px;color:#00d4ff;margin:0 0 8px;letter-spacing:2px;">SENSOR ACTIVATED</p>
                    <p style="font-family:Rajdhani;font-size:13px;color:#00d4ff;opacity:0.9;margin:2px 0;">INSTRUMENT: {selected_instrument}</p>
                    <p style="font-family:Rajdhani;font-size:13px;color:#00d4ff;opacity:0.9;margin:2px 0;">TARGET: {price_display}</p>
                    <p style="font-family:Rajdhani;font-size:13px;color:#00d4ff;opacity:0.9;margin:2px 0;">STATUS: MONITORING 24/7</p>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"DATABASE SYNC ERROR: {str(e)}")
        else:
            st.warning("ENTER VALID TARGET PRICE AND TELEGRAM CHAT ID")
