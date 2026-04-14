import streamlit as st
import requests
import os

# --- 1. WIDGET ECONOMIC RADAR (FULL STYLE) ---
def economic_calendar_widget():
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');
        .economic-radar-container {
            border: 2px solid #00d4ff;
            border-radius: 12px;
            padding: 30px;
            background: rgba(0, 212, 255, 0.02);
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        .radar-header-stack { display: flex; flex-direction: column; align-items: center; margin-bottom: 12px; width: 100%; gap: 6px; }
        .radar-title { font-family: 'Orbitron', sans-serif; font-size: 28px; font-weight: 700; color: #00d4ff; text-shadow: 0 0 4px rgba(0, 212, 255, 0.8); margin: 0; text-transform: uppercase; text-align: center; }
        .status-indicator { font-family: 'Rajdhani', sans-serif; font-size: 12px; color: #00ff88; background: rgba(0, 255, 136, 0.05); padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(0, 255, 136, 0.2); display: flex; align-items: center; justify-content: center; }
        .status-dot { height: 6px; width: 6px; background-color: #00ff88; border-radius: 50%; margin-right: 5px; box-shadow: 0 0 5px #00ff88; animation: pulse-green 2s infinite; }
        @keyframes pulse-green { 0% { transform: scale(0.95); } 70% { transform: scale(1); } 100% { transform: scale(0.95); } }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="economic-radar-container">
        <div class="radar-header-stack">
            <h2 class="radar-title">ECONOMIC RADAR</h2>
            <div class="status-indicator"><span class="status-dot"></span> LIVE CONNECTION</div>
        </div>
    """, unsafe_allow_html=True)

    tradingview_html = """
    <div class="tradingview-widget-container">
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
      {"colorTheme": "dark", "isTransparent": true, "width": "100%", "height": "450", "locale": "en", "importanceFilter": "-1,0,1", "currencyFilter": "USD,EUR,GBP,JPY,AUD,CAD,CHF,NZD"}
      </script>
    </div>
    """
    st.components.v1.html(tradingview_html, height=450)
    st.markdown("</div>", unsafe_allow_html=True)

# --- 2. WIDGET SMART ALERT CENTER (FULL STYLE) ---
def smart_alert_widget():
    st.markdown("""
    <style>
        .alert-center-container { border: 2px solid #00d4ff; border-radius: 15px; padding: 25px; background: rgba(0, 212, 255, 0.05); box-shadow: 0 0 25px rgba(0, 212, 255, 0.4); margin-bottom: 20px; }
        .alert-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid rgba(0, 212, 255, 0.3); padding-bottom: 10px; }
        .alert-title { font-family: 'Orbitron', sans-serif; font-size: 22px; color: #00d4ff; text-shadow: 0 0 15px rgba(0, 212, 255, 0.7); }
        .status-online { color: #00ff88; font-family: 'Rajdhani', sans-serif; font-size: 12px; }
        .stButton > button { background: linear-gradient(145deg, #00d4ff, #0055ff) !important; border: 2px solid #00d4ff !important; color: white !important; font-family: 'Orbitron', sans-serif !important; width: 100%; border-radius: 12px !important; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class='alert-center-container'>
        <div class='alert-header'>
            <h2 class='alert-title'>AEROVULPIS TERMINAL</h2>
            <span class='status-online'>SYSTEM STATUS: ONLINE</span>
        </div>
    """, unsafe_allow_html=True)

    instruments = ["XAUUSD", "BTCUSD", "EURUSD", "BBCA.JK", "TLKM.JK"]
    selected_instrument = st.selectbox("INSTRUMENT SELECTOR", instruments, key="alert_inst")
    price_target = st.number_input("DIGITAL PRICE TARGET", min_value=0.0, format="%.2f", key="alert_price")
    telegram_chat_id = st.text_input("TELEGRAM CHAT ID", value=st.secrets.get("TELEGRAM_CHAT_ID", ""), key="alert_id")
    condition = st.radio("CONDITION TRIGGER", ["MELAMPAUI KE ATAS [BULLISH] ↑", "TURUN DI BAWAH [BEARISH] ↓"], key="alert_cond")

    if st.button("LOCK TARGET & ACTIVATE SENSOR"):
        token = st.secrets.get("TELEGRAM_BOT_TOKEN")
        if token and price_target > 0:
            msg = f"⚠️ *AEROVULPIS ALERT*\nAsset: {selected_instrument}\nTarget: {price_target}\n_By DynamiHatch_"
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            requests.post(url, json={'chat_id': telegram_chat_id, 'text': msg, 'parse_mode': 'Markdown'})
            st.success("Target Locked!")
    
    st.markdown("</div>", unsafe_allow_html=True)

# --- 3. EKSEKUSI (WAJIB ADA) ---
st.title("🦅 AeroVulpis Dashboard")
economic_calendar_widget()
st.markdown("---")
smart_alert_widget()
