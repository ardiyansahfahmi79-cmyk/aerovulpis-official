import streamlit as st import requests import os

=========================

ECONOMIC RADAR (FIXED)

=========================

def economic_calendar_widget(): st.markdown(""" <style> .economic-radar-container { border: 2px solid #00d4ff; border-radius: 12px; padding: 30px; background: rgba(0, 212, 255, 0.02); box-shadow: 0 0 15px rgba(0, 212, 255, 0.2); margin-bottom: 10px; }

.radar-title {
    text-align: center;
    font-size: 28px;
    color: #00d4ff;
    margin-bottom: 10px;
}

.status {
    text-align: center;
    color: #00ff88;
    font-size: 12px;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="economic-radar-container">
    <h2 class="radar-title">ECONOMIC RADAR</h2>
    <div class="status">● LIVE CONNECTION</div>
""", unsafe_allow_html=True)

tradingview_html = """
<div class="tradingview-widget-container">
  <div id="tradingview_widget"></div>
  <script src="https://s3.tradingview.com/external-embedding/embed-widget-events.js"></script>
  <script>
  new TradingView.widget({
    "width": "100%",
    "height": 450,
    "colorTheme": "dark",
    "isTransparent": true,
    "locale": "en",
    "importanceFilter": "-1,0,1",
    "currencyFilter": "USD,EUR,GBP,JPY,AUD,CAD,CHF,NZD"
  });
  </script>
</div>
"""

st.components.v1.html(tradingview_html, height=460)

st.markdown("</div>", unsafe_allow_html=True)

=========================

SMART ALERT (FIXED)

=========================

def smart_alert_widget():

def send_telegram_alert(chat_id, message, bot_token):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message
    }
    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return True
    except Exception as e:
        return False

st.markdown("""
<style>
.alert-box {
    border: 2px solid #00d4ff;
    border-radius: 12px;
    padding: 20px;
    box-shadow: 0 0 20px rgba(0,212,255,0.3);
}
.alert-title {
    font-size: 22px;
    color: #00d4ff;
    text-align: center;
    margin-bottom: 15px;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="alert-box">
    <div class="alert-title">AEROVULPIS SMART ALERT</div>
""", unsafe_allow_html=True)

instruments = ["XAUUSD", "BTCUSD", "EURUSD", "US100"]
instrument = st.selectbox("Instrument", instruments)

price = st.number_input("Target Price", min_value=0.0)

chat_id = st.text_input("Telegram Chat ID")

condition = st.radio("Condition", ["Bullish", "Bearish"])

if st.button("Activate Alert"):
    if price > 0 and chat_id:
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        msg = f"Alert {instrument} {condition} at {price}"

        if token:
            ok = send_telegram_alert(chat_id, msg, token)
            if ok:
                st.success("Alert sent to Telegram")
            else:
                st.error("Failed to send alert")
        else:
            st.error("Token not found")
    else:
        st.warning("Fill all fields")

st.markdown("</div>", unsafe_allow_html=True)

=========================

MAIN (SAFE RENDER)

=========================

economic_calendar_widget()

st.divider()

smart_alert_widget()
