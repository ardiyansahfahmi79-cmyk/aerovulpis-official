import streamlit as st
import requests
import os

def economic_calendar_widget():
    """
    Menampilkan Economic Radar Real-time menggunakan Iframe TradingView
    dengan gaya visual Cyber Tech Blue yang konsisten dengan AeroVulpis.
    """
    
    # CSS Khusus untuk Widget Economic Radar (sama persis seperti aslimu)
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
            text-shadow: 0 0 4px rgba(0, 212, 255, 0.8);
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
            background: rgba(0, 255, 136, 0.05);
            padding: 4px 8px;
            border-radius: 4px;
            border: 0.5px solid rgba(0, 255, 136, 0.3);
            display: flex;
            align-items: center;
        }
        
        .status-dot {
            height: 8px;
            width: 8px;
            background-color: #00ff88;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
            box-shadow: 0 0 4px #00ff88;
            animation: pulse-green 2s infinite;
        }
        
        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }

        .impact-legend {
            display: flex;
            justify-content: center;
            gap: 15px;
            margin-top: 12px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 13px;
        }
        
        .high-impact { color: #ff2a6d; text-shadow: 0 0 3px rgba(255, 42, 109, 0.5); }
        .med-impact { color: #ffcc00; }
        .low-impact { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

    # Container Utama
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
                    <span class="status-dot"></span>
                    LIVE CONNECTION
                </div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # Economic Calendar menggunakan iframe langsung (lebih stabil di Streamlit)
    try:
        st.components.v1.iframe(
            src="https://www.tradingview.com/economic-calendar/",
            height=520,
            scrolling=True
        )
    except Exception as e:
        st.error(f"Gagal memuat Economic Radar: {str(e)}")

    # Legenda Dampak & Penutup Container
    st.markdown("""
        <div class="impact-legend">
            <div class="legend-item"><span class="high-impact">★★★</span> High Impact</div>
            <div class="legend-item"><span class="med-impact">★★</span> Medium</div>
            <div class="legend-item"><span class="low-impact">★</span> Low</div>
        </div>
    </div>
    """, unsafe_allow_html=True)


def smart_alert_widget():
    """
    Menampilkan AeroVulpis Smart Alert Center V3.3 dengan gaya UI cyber-tech/terminal.
    """

    # Custom CSS for Smart Alert Center (sama persis)
    st.markdown("""
    <style>
        .alert-center-container {
            border: 2px solid #00d4ff;
            border-radius: 15px;
            padding: 25px;
            background: rgba(0, 212, 255, 0.05);
            box-shadow: 0 0 25px rgba(0, 212, 255, 0.4);
            margin-bottom: 20px;
            position: relative;
            overflow: hidden;
        }

        .alert-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            border-bottom: 1px solid rgba(0, 212, 255, 0.3);
            padding-bottom: 10px;
        }

        .alert-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 24px;
            font-weight: 700;
            color: #00d4ff;
            text-shadow: 0 0 15px rgba(0, 212, 255, 0.7);
            margin: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .alert-title-logo {
            height: 28px;
            filter: drop-shadow(0 0 8px rgba(0, 212, 255, 0.8));
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
            text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
        }

        .status-sync {
            color: #00d4ff;
            text-shadow: 0 0 5px rgba(0, 212, 255, 0.5);
        }

        .stSelectbox > div > div > div {
            background-color: rgba(0, 212, 255, 0.1) !important;
            border: 1px solid #00d4ff !important;
            color: #e0e0e0 !important;
            font-family: 'Rajdhani', sans-serif;
        }
        .stSelectbox > label {
            color: #00ff88 !important;
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
        }

        .stNumberInput > label, .stTextInput > label, .stRadio > label {
            color: #00ff88 !important;
            font-family: 'Orbitron', sans-serif;
            font-size: 14px;
            text-shadow: 0 0 5px rgba(0, 255, 136, 0.5);
        }

        .stNumberInput > div > input, .stTextInput > div > input {
            background-color: rgba(0, 212, 255, 0.1) !important;
            border: 1px solid #00d4ff !important;
            color: #e0e0e0 !important;
            font-family: 'Rajdhani', sans-serif;
            padding: 10px;
            border-radius: 8px;
        }

        .stRadio > div {
            background-color: rgba(0, 212, 255, 0.05);
            border: 1px solid rgba(0, 212, 255, 0.2);
            border-radius: 10px;
            padding: 10px;
        }
        .stRadio > div > label {
            color: #e0e0e0 !important;
            font-family: 'Rajdhani', sans-serif;
        }
        .stRadio > div > label > div > div:first-child {
            border: 2px solid #00d4ff !important;
        }
        .stRadio > div > label > div > div:first-child > div {
            background-color: #00ff88 !important;
        }

        .stButton.alert-button > button {
            background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
            border: 2px solid #00d4ff !important;
            color: white !important;
            font-family: 'Orbitron', sans-serif !important;
            font-weight: 700 !important;
            padding: 15px 30px !important;
            border-radius: 12px !important;
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.6), inset 0 0 10px rgba(255, 255, 255, 0.2) !important;
            transition: all 0.3s ease !important;
            text-transform: uppercase;
            letter-spacing: 2px;
            width: 100%;
            margin-top: 20px;
        }
        .stButton.alert-button > button:hover {
            transform: translateY(-3px) scale(1.02);
            box-shadow: 0 0 30px rgba(0, 212, 255, 0.9), inset 0 0 15px rgba(255, 255, 255, 0.3) !important;
            filter: brightness(1.3);
        }
    </style>
    """, unsafe_allow_html=True)

    # Fungsi untuk mengirim alert Telegram
    def send_telegram_alert(chat_id, message, bot_token):
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'MarkdownV2'
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return True, response.json()
        except requests.exceptions.RequestException as e:
            return False, str(e)

    with st.container():
        st.markdown("<div class='alert-center-container'>", unsafe_allow_html=True)

        # Header (sudah diperbaiki)
        st.markdown("""
        <div class='alert-header'>
            <h2 class='alert-title'>
                <img src='https://i.imgur.com/12345.png' class='alert-title-logo' alt="AeroVulpis Logo">
                AEROVULPIS TERMINAL
            </h2>
            <div class='status-indicators'>
                <span class='status-online'>SYSTEM STATUS: ONLINE</span>
                <span class='status-sync'>SATELLITE SYNC ACTIVE</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h3 class='alert-title' style='text-align: center; font-size: 20px; margin-bottom: 20px;'>SMART ALERT CENTER V3.3</h3>", unsafe_allow_html=True)

        # Instrument Selector
        instruments = ["XAUUSD", "WTI", "BTCUSD", "EURUSD", "US100", "Silver", "GOOGL", "AAPL", "BBCA.JK", "TLKM.JK"]
        selected_instrument = st.selectbox("**INSTRUMENT SELECTOR**", instruments, key="alert_instrument")

        # Digital Price Target
        price_target = st.number_input("**DIGITAL PRICE TARGET**", min_value=0.00, format="%.2f", key="alert_price_target")

        # Telegram Chat ID
        default_chat_id = os.getenv("TELEGRAM_CHAT_ID") or st.secrets.get("TELEGRAM_CHAT_ID", "")
        telegram_chat_id = st.text_input("**TELEGRAM CHAT ID**", value=default_chat_id, key="alert_chat_id")

        # Condition Trigger
        condition_options = {
            "MELAMPAUI KE ATAS [BULLISH] ↑": "bullish",
            "TURUN DI BAWAH [BEARISH] ↓": "bearish"
        }
        selected_condition_label = st.radio("**CONDITION TRIGGER**", list(condition_options.keys()), key="alert_condition")
        selected_condition_value = condition_options[selected_condition_label]

        # Main Button
        if st.button("**LOCK TARGET & ACTIVATE SENSOR**", key="activate_sensor_button", help="Click to set the alert and activate the sensor.", type="primary"):
            if price_target > 0 and telegram_chat_id:
                alert_message = f"*AeroVulpis Alert Activated!*\n\n" \
                                f"```\n" \
                                f"╔═══════════════════════════════════╗\n" \
                                f"║   🚨 TERMINAL MESSAGE - ALERT 🚨  ║\n" \
                                f"╠═══════════════════════════════════╣\n" \
                                f"║ INSTRUMENT: {selected_instrument:<20}║\n" \
                                f"║ TARGET PRICE: ${price_target:.2f:<17}║\n" \
                                f"║ CONDITION: {selected_condition_label:<20}║\n" \
                                f"╚═══════════════════════════════════╝\n" \
                                f"```\n\n" \
                                f"🔒 Monitoring {selected_instrument} for price {selected_condition_label.split(' ')[0].lower()} ${price_target:.2f}.\n" \
                                f"_By DynamiHatch Company_"

                telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN") or st.secrets.get("TELEGRAM_BOT_TOKEN")

                if telegram_bot_token:
                    success, result = send_telegram_alert(telegram_chat_id, alert_message, telegram_bot_token)
                    if success:
                        st.success("✅ Alert berhasil diaktifkan! Notifikasi akan dikirim ke Telegram.")
                        st.json(result)
                    else:
                        st.error(f"❌ Gagal mengirim notifikasi Telegram: {result}")
                else:
                    st.error("⚠️ TELEGRAM_BOT_TOKEN tidak ditemukan.")
            else:
                st.warning("⚠️ Harap masukkan Target Harga dan Telegram Chat ID yang valid.")

        st.markdown("</div>", unsafe_allow_html=True)
