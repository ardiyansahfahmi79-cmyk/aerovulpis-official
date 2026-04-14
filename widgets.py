import streamlit as st
import requests
import os

# --- 1. WIDGET ECONOMIC RADAR ---
def economic_calendar_widget():
    """
    Menampilkan Economic Radar Real-time menggunakan Iframe TradingView
    dengan gaya visual Cyber Tech Blue.
    """
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');
        .economic-radar-container {
            border: 2px solid #00d4ff;
            border-radius: 12px;
            padding: 30px;
            background: rgba(0, 212, 255, 0.02);
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
            margin-bottom: 20px;
            position: relative;
        }
        .radar-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 28px;
            color: #00d4ff;
            text-shadow: 0 0 4px rgba(0, 212, 255, 0.8);
            text-align: center;
            text-transform: uppercase;
        }
        .status-indicator {
            font-family: 'Rajdhani', sans-serif;
            color: #00ff88;
            text-align: center;
            font-size: 14px;
            margin-bottom: 10px;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="economic-radar-container">
        <h2 class="radar-title">ECONOMIC RADAR</h2>
        <div class="status-indicator">● LIVE CONNECTION ACTIVE</div>
    """, unsafe_allow_html=True)

    tradingview_html = """
    <div class="tradingview-widget-container">
      <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
      {
      "colorTheme": "dark",
      "isTransparent": true,
      "width": "100%",
      "height": "450",
      "locale": "en",
      "importanceFilter": "-1,0,1",
      "currencyFilter": "USD,EUR,GBP,JPY,AUD,CAD,CHF,NZD"
      }
      </script>
    </div>
    """
    st.components.v1.html(tradingview_html, height=450)
    st.markdown("</div>", unsafe_allow_html=True)

# --- 2. WIDGET SMART ALERT CENTER ---
def smart_alert_widget():
    """
    Menampilkan AeroVulpis Smart Alert Center V3.3
    """
    st.markdown("""
    <style>
        .alert-center-container {
            border: 2px solid #00d4ff;
            border-radius: 15px;
            padding: 25px;
            background: rgba(0, 212, 255, 0.05);
            box-shadow: 0 0 25px rgba(0, 212, 255, 0.4);
            margin-bottom: 20px;
        }
        .stButton > button {
            background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
            color: white !important;
            font-weight: bold !important;
            width: 100%;
            border-radius: 10px !important;
        }
    </style>
    """, unsafe_allow_html=True)

    def send_telegram_alert(chat_id, message, bot_token):
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {'chat_id': chat_id, 'text': message, 'parse_mode': 'Markdown'}
        try:
            r = requests.post(url, json=payload)
            return r.status_code == 200, r.text
        except:
            return False, "Connection Error"

    st.markdown("<div class='alert-center-container'>", unsafe_allow_html=True)
    st.markdown("<h2 style='text-align: center; color: #00d4ff; font-family: Orbitron;'>SMART ALERT CENTER V3.3</h2>", unsafe_allow_html=True)

    # Inputs
    instruments = ["XAUUSD", "BTCUSD", "EURUSD", "BBCA.JK", "TLKM.JK"]
    selected_instrument = st.selectbox("INSTRUMENT SELECTOR", instruments)
    price_target = st.number_input("DIGITAL PRICE TARGET", min_value=0.0, format="%.2f")
    
    # Ambil data dari Secrets
    default_chat_id = st.secrets.get("TELEGRAM_CHAT_ID", "")
    telegram_chat_id = st.text_input("TELEGRAM CHAT ID", value=default_chat_id)

    condition = st.radio("CONDITION TRIGGER", ["MELAMPAUI KE ATAS [BULLISH] ↑", "TURUN DI BAWAH [BEARISH] ↓"])

    if st.button("LOCK TARGET & ACTIVATE SENSOR"):
        bot_token = st.secrets.get("TELEGRAM_BOT_TOKEN")
        if not bot_token:
            st.error("Gagal: TELEGRAM_BOT_TOKEN tidak ada di Secrets!")
        elif price_target > 0 and telegram_chat_id:
            msg = f"*AeroVulpis Alert Locked!*\nAsset: {selected_instrument}\nTarget: {price_target}\nStatus: Monitoring...\n_By DynamiHatch_"
            success, res = send_telegram_alert(telegram_chat_id, msg, bot_token)
            if success:
                st.success("Target Locked! Sensor aktif di Telegram.")
            else:
                st.error(f"Error: {res}")
        else:
            st.warning("Data belum lengkap.")
    
    st.markdown("</div>", unsafe_allow_html=True)

# --- 3. EKSEKUSI / PEMANGGILAN ---
# Bagian ini yang membuat fitur muncul di website
st.title("🦅 AeroVulpis Terminal Control")

# Panggil Radar Ekonomi
economic_calendar_widget()

st.markdown("---")

# Panggil Fitur Alert
smart_alert_widget()
