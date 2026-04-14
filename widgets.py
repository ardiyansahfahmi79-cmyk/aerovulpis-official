import streamlit as st
import requests
import os

def inject_css(css_content):
    """Injeksi CSS modular."""
    st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)

def render_tradingview_iframe():
    """Render TradingView Economic Calendar iframe."""
    tradingview_html = """
    <div class="tradingview-widget-container">
        <div class="tradingview-widget-container__widget"></div>
        <div class="tradingview-widget-copyright">
            <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
                <span class="blue-text">Track all markets on TradingView</span>
            </a>
        </div>
        <script type="text/javascript" src="https://s3.tradingview.com/external-embedding/embed-widget-events.js" async>
        {
            "colorTheme": "dark",
            "isTransparent": true,
            "width": "100%",
            "height": 450,
            "locale": "en",
            "importanceFilter": "-1,0,1",
            "currencyFilter": "USD,EUR,GBP,JPY,AUD,CAD,CHF,NZD"
        }
        </script>
    </div>
    """
    st.markdown(tradingview_html, unsafe_allow_html=True)

def economiccalendarwidget():
    """Economic Radar Widget - Fixed & Complete."""
    css_economic = """
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');
    
    .economic-radar-container {
        border: 2px solid #00d4ff;
        border-radius: 12px;
        padding: 30px;
        background: rgba(0,212,255,0.02);
        box-shadow: 0 0 15px rgba(0,212,255,0.2);
        margin-bottom: 10px;
        position: relative;
        overflow: hidden;
    }
    .radar-header-stack {
        display: flex;
        flex-direction: column;
        align-items: center;
        margin-bottom: 12px;
        width: 100%;
        gap: 6px;
    }
    .radar-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 28px;
        font-weight: 700;
        color: #00d4ff;
        text-shadow: 0 0 4px rgba(0,212,255,0.8);
        margin: 0;
        padding: 0 10px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        text-align: center;
        line-height: 1;
    }
    .radar-subtitle-row {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 6px;
    }
    .radar-logo {
        width: 16px;
        height: 16px;
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
        border: 0.8px solid #00d4ff;
        border-radius: 50%;
        opacity: 0.6;
    }
    .radar-sweep {
        position: absolute;
        width: 50%;
        height: 0.8px;
        background: linear-gradient(to right, transparent, #00d4ff);
        top: 50%;
        left: 50%;
        transform-origin: left center;
        animation: radar-spin 2s linear infinite;
    }
    @keyframes radar-spin {
        from { transform: rotate(0deg); }
        to { transform: rotate(360deg); }
    }
    .status-indicator {
        font-family: 'Rajdhani', sans-serif;
        font-size: 12px;
        color: #00ff88;
        letter-spacing: 0.3px;
        background: rgba(0,255,136,0.05);
        padding: 2px 6px;
        border-radius: 4px;
        border: 1px solid rgba(0,255,136,0.2);
        display: flex;
        align-items: center;
    }
    .status-dot {
        height: 6px;
        width: 6px;
        background: #00ff88;
        border-radius: 50%;
        display: inline-block;
        margin-right: 5px;
        box-shadow: 0 0 5px #00ff88;
        animation: pulse-green 2s infinite;
    }
    @keyframes pulse-green {
        0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0,255,136,0.7); }
        70% { transform: scale(1); box-shadow: 0 0 0 5px rgba(0,255,136,0); }
        100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0,255,136,0); }
    }
    .tradingview-widget-container iframe {
        border-radius: 8px !important;
        filter: hue-rotate(180deg) brightness(0.95) contrast(1.1);
    }
    .impact-legend {
        display: flex;
        justify-content: center;
        gap: 15px;
        margin-top: 15px;
        font-family: 'Rajdhani', sans-serif;
        font-size: 12px;
        flex-wrap: wrap;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 5px;
        color: #aaa;
    }
    .high-impact { color: #ff2a6d; text-shadow: 0 0 3px rgba(255,42,109,0.5); }
    .med-impact { color: #ffcc00; }
    .low-impact { color: #00ff88; }
    """
    
    inject_css(css_economic)
    
    st.markdown("""
    <div class="economic-radar-container">
        <div class="radar-header-stack">
            <h2 class="radar-title">ECONOMIC RADAR</h2>
            <div class="radar-subtitle-row">
                <div class="radar-logo">
                    <div class="radar-circle"></div>
                    <div class="radar-sweep"></div>
                </div>
                <div class="status-indicator">
                    <span class="status-dot"></span><span>LIVE CONNECTION</span>
                </div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    render_tradingview_iframe()
    
    st.markdown("""
    <div class="impact-legend">
        <div class="legend-item"><span class="high-impact">★★★</span>High Impact</div>
        <div class="legend-item"><span class="med-impact">★★</span>Medium</div>
        <div class="legend-item"><span class="low-impact">★</span>Low</div>
    </div>
    """, unsafe_allow_html=True)

def send_telegram_alert(chat_id, message, bot_token):
    """Kirim Telegram alert dengan error handling."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": message, 
        "parse_mode": "MarkdownV2"
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return True, response.json()
    except requests.exceptions.RequestException as e:
        return False, str(e)

def smartalertwidget():
    """Smart Alert Center V3.3 - Fixed & Complete."""
    css_alert = """
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');
    
    .alert-center-container {
        border: 2px solid #00d4ff;
        border-radius: 15px;
        padding: 25px;
        background: rgba(0,212,255,0.05);
        box-shadow: 0 0 25px rgba(0,212,255,0.4);
        margin-bottom: 20px;
        position: relative;
        overflow: hidden;
    }
    .alert-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 20px;
        border-bottom: 1px solid rgba(0,212,255,0.3);
        padding-bottom: 10px;
    }
    .alert-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 24px;
        font-weight: 700;
        color: #00d4ff;
        text-shadow: 0 0 15px rgba(0,212,255,0.7);
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .alert-title-logo {
        height: 28px;
        filter: drop-shadow(0 0 8px rgba(0,212,255,0.8));
    }
    .status-indicators {
        display: flex;
        flex-direction: column;
        align-items: flex-end;
        font-family: 'Rajdhani', sans-serif;
        font-size: 12px;
        gap: 3px;
    }
    .status-online {
        color: #00ff88;
        text-shadow: 0 0 5px rgba(0,255,136,0.5);
    }
    .status-sync {
        color: #00d4ff;
        text-shadow: 0 0 5px rgba(0,212,255,0.5);
    }
    .alert-title-sub {
        text-align: center;
        font-size: 20px;
        margin-bottom: 20px;
        color: #00d4ff;
        font-family: 'Orbitron', sans-serif;
    }
    .stSelectbox > div > div > div {
        background-color: rgba(0,212,255,0.1) !important;
        border: 1px solid #00d4ff !important;
        color: #e0e0e0 !important;
    }
    .stButton > button {
        background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
        border: 2px solid #00d4ff !important;
        color: white !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        padding: 15px 30px !important;
        border-radius: 12px !important;
        box-shadow: 0 0 20px rgba(0,212,255,0.6) !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        width: 100% !important;
        margin-top: 20px;
    }
    .stButton > button:hover {
        box-shadow: 0 0 30px rgba(0,212,255,0.8) !important;
        transform: translateY(-2px);
    }
    """
    
    inject_css(css_alert)
    
    # Header Container
    st.markdown("""
    <div class="alert-center-container">
        <div class="alert-header">
            <h2 class="alert-title">
                <img src="https://files.manuscdn.com/useruploadbymodulesessionfile310519663520709901oOIKIIkSvIdagiSw.png" class="alert-title-logo" alt="AeroVulpis Logo">
                AEROVULPIS TERMINAL
            </h2>
            <div class="status-indicators">
                <span class="status-online">SYSTEM STATUS: ONLINE</span>
                <span class="status-sync">SATELLITE SYNC: ACTIVE</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Subtitle
    st.markdown('<h3 class="alert-title-sub">SMART ALERT CENTER V3.3</h3>', unsafe_allow_html=True)
    
    # Form Inputs - EXACT dari file asli
    instruments = ["XAUUSD", "WTI", "BTCUSD", "EURUSD", "US100", "Silver", "GOOGL", "AAPL", "BBCA.JK", "TLKM.JK"]
    selected_instrument = st.selectbox("📈 INSTRUMENT SELECTOR", instruments, key="alert_instrument")
    
    price_target = st.number_input("💰 DIGITAL PRICE TARGET", min_value=0.0, format="%.2f", key="alert_price_target")
    
    default_chatid = os.getenv("TELEGRAM_CHATID") or st.secrets.get("TELEGRAM_CHATID", "")
    telegram_chatid = st.text_input("📱 TELEGRAM CHAT ID", value=default_chatid, key="alert_chatid")
    
    condition_options = {
        "MELAMPAUI KE ATAS (BULLISH)": "bullish",
        "TURUN DI BAWAH (BEARISH)": "bearish"
    }
    selected_condition_label = st.radio("🎯 CONDITION TRIGGER", list(condition_options.keys()), key="alert_condition")
    
    # Activate Button & Logic - EXACT dari asli
    if st.button("🔒 LOCK TARGET & ACTIVATE SENSOR", key="activate_sensor_button"):
        if price_target > 0 and telegram_chatid:
            alert_message = f"""🔔 *AeroVulpis Alert Activated!*

*TERMINAL MESSAGE - ALERT*
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
*INSTRUMENT*: {selected_instrument:<20}
*TARGET PRICE*: {price_target:>17.2f}
*CONDITION*: {selected_condition_label:<20}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Monitoring {selected_instrument} for price movement.

*By DynamiHatch Company*"""
            
            telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or st.secrets.get("TELEGRAM_BOT_TOKEN", "")
            if telegram_bot_token:
                success, result = send_telegram_alert(telegram_chatid, alert_message, telegram_bot_token)
                if success:
                    st.success("✅ Alert berhasil diaktifkan! Notifikasi Telegram terkirim.")
                    st.balloons()
                else:
                    st.error(f"❌ Gagal kirim Telegram: {result}")
            else:
                st.error("❌ TELEGRAM_BOT_TOKEN tidak ditemukan di env/secrets.")
        else:
            st.warning("⚠️ Isi TARGET PRICE & CHAT ID dulu!")

# ===== COMPATIBILITY FIX untuk streamlit_app.py =====
economic_calendar_widget = economiccalendarwidget
smart_alert_widget = smartalertwidget

# EOF - widgets.py FIXED VERSION
