import streamlit as st
import requests
import os
from supabase import create_client, Client

# Konfigurasi Supabase dari Secrets
url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]

def economic_calendar_widget():
    """
    Menampilkan Economic Radar Real-time menggunakan Iframe TradingView
    dengan gaya visual Cyber Tech Blue yang konsisten dengan AeroVulpis.
    """
    
    # CSS Khusus untuk Widget Economic Radar
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

        .economic-radar-container {
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
            margin-bottom: 14px;
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
            animation: radarDiscPulse 2s infinite;
        }

        .radar-sweep {
            position: absolute;
            width: 50%;
            height: 1px;
            background: linear-gradient(to right, transparent, #00d4ff);
            top: 50%;
            left: 50%;
            transform-origin: left center;
            animation: radarSweepWidget 2s linear infinite;
        }

        @keyframes radarDiscPulse {
            0%, 100% { transform: scale(1); opacity: 0.4; }
            50% { transform: scale(1.2); opacity: 0.8; }
        }

        @keyframes radarSweepWidget {
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
            background-color: #00ff88;
            border-radius: 50%;
            display: inline-block;
            margin-right: 6px;
            box-shadow: 0 0 5px #00ff88;
            animation: pulse-green 2s infinite;
        }
        
        @keyframes pulse-green {
            0% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.6); }
            70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.9); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }

        .tradingview-widget-container iframe {
            border-radius: 6px !important;
            filter: brightness(0.9) contrast(1.05); 
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

    # TradingView Economic Calendar Widget
    tradingview_html = """
    <div class="tradingview-widget-container">
      <div class="tradingview-widget-container__widget"></div>
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
    
    try:
        st.components.v1.html(tradingview_html, height=450)
    except Exception as e:
        st.error(f"Gagal memuat radar ekonomi: {str(e)}")

    # Legenda Dampak & Penutup Container
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
    Menampilkan Smart Alert Center V3.5 dengan gaya UI cyber-tech/terminal.
    TANPA logo AeroVulpis (logo ada di streamlit_app.py header).
    Current price mengikuti format dari Live Dashboard.
    """

    # Custom CSS for Smart Alert Center
    st.markdown("""
    <style>
        .alert-widget-container {
            position: relative;
        }

        .alert-widget-selector label {
            color: #00d4ff !important;
            font-family: 'Orbitron', sans-serif !important;
            font-size: 10px !important;
            letter-spacing: 2px !important;
        }
        
        .alert-widget-selector > div > div {
            background: rgba(0, 28, 56, 0.6) !important;
            border: 1px solid rgba(0, 212, 255, 0.3) !important;
            border-radius: 3px !important;
            color: #c0d0e0 !important;
            font-family: 'Rajdhani', sans-serif !important;
        }

        .alert-price-display {
            background: rgba(0, 212, 255, 0.04);
            border: 1px solid rgba(0, 212, 255, 0.2);
            padding: 14px;
            border-radius: 4px;
            margin-bottom: 16px;
            text-align: center;
        }
        
        .alert-price-label {
            font-family: 'Share Tech Mono', monospace;
            font-size: 10px;
            color: #557799;
            letter-spacing: 2px;
        }
        
        .alert-price-value {
            font-family: 'Orbitron', sans-serif;
            font-size: 22px;
            color: #00ff88;
            text-shadow: 0 0 12px rgba(0, 255, 136, 0.5);
            letter-spacing: 2px;
            margin: 4px 0;
        }
        
        .alert-price-source {
            font-family: 'Share Tech Mono', monospace;
            font-size: 8px;
            color: #445566;
        }

        .alert-input-label {
            font-family: 'Orbitron', sans-serif !important;
            font-size: 9px !important;
            color: #8899bb !important;
            letter-spacing: 2px !important;
            text-transform: uppercase;
        }

        .stButton.alert-activate-btn > button {
            background: linear-gradient(160deg, #001a33, #002850) !important;
            border: 1px solid rgba(0, 212, 255, 0.4) !important;
            color: #00d4ff !important;
            font-family: 'Orbitron', sans-serif !important;
            font-weight: 700 !important;
            font-size: 12px !important;
            padding: 14px 28px !important;
            border-radius: 3px !important;
            letter-spacing: 2px !important;
            transition: all 0.3s ease !important;
            text-transform: uppercase;
            width: 100%;
            margin-top: 18px;
        }
        
        .stButton.alert-activate-btn > button:hover {
            background: linear-gradient(160deg, #002850, #003870) !important;
            border-color: #00d4ff !important;
            box-shadow: 0 0 28px rgba(0, 212, 255, 0.3) !important;
            color: #ffffff !important;
            transform: translateY(-1px);
        }

        .alert-success-box {
            background: rgba(0, 212, 255, 0.06);
            border-left: 3px solid #00d4ff;
            padding: 16px;
            border-radius: 3px;
            font-family: 'Rajdhani', sans-serif;
            color: #00d4ff;
            margin-top: 18px;
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.1);
        }
    </style>
    """, unsafe_allow_html=True)

    def send_telegram_alert(chat_id, message, bot_token):
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            'chat_id': chat_id,
            'text': message,
            'parse_mode': 'HTML'
        }
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return True, response.json()
        except requests.exceptions.RequestException as e:
            return False, str(e)

    st.markdown("<div class='alert-widget-container'>", unsafe_allow_html=True)

    # Instrument Selector
    instruments_list = ["XAUUSD", "XAGUSD", "BTCUSD", "ETHUSD", "SOLUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF", "WTI", "US100", "Palladium", "Platinum", "GOOGL", "AAPL", "BBCA.JK", "TLKM.JK"]
    selected_instrument = st.selectbox("INSTRUMENT SELECTOR", instruments_list, key="alert_instrument")

    # ====================== CURRENT PRICE DARI SUPABASE CACHE ======================
    try:
        supabase: Client = create_client(url, key)
        res = supabase.table("market_prices").select("*").eq("instrument", selected_instrument).execute()
        
        if res.data:
            current_price = res.data[0].get("price", 0.0)
            data_source = "SUPABASE"
        else:
            current_price = 0.0
            data_source = "NO DATA"
        
        # Format harga sesuai instrumen (SAMA DENGAN LIVE DASHBOARD)
        if selected_instrument in ["XAUUSD", "XAGUSD"]:
            price_display = f"{current_price:,.2f}"
        elif selected_instrument in ["BTCUSD", "ETHUSD"]:
            price_display = f"{current_price:,.2f}"
        elif selected_instrument in ["SOLUSD", "XRPUSD", "BNBUSD"]:
            price_display = f"{current_price:,.2f}"
        elif selected_instrument in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]:
            price_display = f"{current_price:,.4f}".rstrip('0').rstrip('.')
        elif selected_instrument in ["WTI", "US100"]:
            price_display = f"{current_price:,.2f}"
        else:
            price_display = f"{current_price:,.2f}"
        
        # Jika harga 0, coba ambil dari streamlit_app cache
        if current_price == 0:
            try:
                from streamlit_app import get_market_data, instruments
                ticker_to_fetch = None
                for cat in instruments.values():
                    if selected_instrument in cat:
                        ticker_to_fetch = cat[selected_instrument]
                        break
                if ticker_to_fetch:
                    m_data = get_market_data(ticker_to_fetch)
                    if m_data:
                        current_price = m_data["price"]
                        data_source = m_data.get("source", "LIVE")
                        # Re-format
                        if selected_instrument in ["XAUUSD", "XAGUSD"]:
                            price_display = f"{current_price:,.2f}"
                        elif selected_instrument in ["EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCHF"]:
                            price_display = f"{current_price:,.4f}".rstrip('0').rstrip('.')
                        else:
                            price_display = f"{current_price:,.2f}"
            except Exception:
                pass
        
        st.markdown(f"""
        <div class="alert-price-display">
            <span class="alert-price-label">CURRENT PRICE</span><br>
            <span class="alert-price-value">{price_display}</span>
            <br><span class="alert-price-source">DATA SOURCE: {data_source}</span>
        </div>
        """, unsafe_allow_html=True)
        
    except Exception:
        st.markdown("""
        <div class="alert-price-display">
            <span class="alert-price-label">CURRENT PRICE</span><br>
            <span style="font-family:Orbitron;font-size:16px;color:#ff2a6d;">PRICE UNAVAILABLE</span>
        </div>
        """, unsafe_allow_html=True)

    # Digital Price Target
    st.markdown('<p class="alert-input-label">DIGITAL PRICE TARGET</p>', unsafe_allow_html=True)
    price_target = st.number_input(
        "DIGITAL PRICE TARGET",
        min_value=0.0,
        format="%.4f",
        step=0.0001,
        key="alert_price_target",
        label_visibility="collapsed"
    )

    # Telegram Chat ID
    st.markdown('<p class="alert-input-label">TELEGRAM CHAT ID</p>', unsafe_allow_html=True)
    telegram_chat_id = st.text_input(
        "TELEGRAM CHAT ID",
        value="",
        placeholder="Enter your Telegram Chat ID...",
        key="alert_chat_id",
        label_visibility="collapsed"
    )

    # Condition Trigger
    st.markdown('<p class="alert-input-label">CONDITION TRIGGER</p>', unsafe_allow_html=True)
    condition_options = {
        "BREAKOUT ABOVE [BULLISH]": "bullish",
        "BREAKDOWN BELOW [BEARISH]": "bearish"
    }
    selected_condition_label = st.radio(
        "CONDITION TRIGGER",
        list(condition_options.keys()),
        key="alert_condition",
        label_visibility="collapsed"
    )

    # Main Button
    if st.button("LOCK TARGET & ACTIVATE SENSOR", key="activate_sensor_button", type="primary"):
        if price_target > 0 and telegram_chat_id:
            from datetime import datetime
            import pytz
            now_wib = datetime.now(pytz.timezone('Asia/Jakarta')).strftime("%d/%m/%Y %H:%M:%S")

            # Simpan ke Session State
            if "active_alerts" not in st.session_state:
                st.session_state.active_alerts = []
            
            alert_data = {
                "instrument": selected_instrument,
                "target": price_target,
                "condition": condition_options[selected_condition_label],
                "chat_id": telegram_chat_id,
                "time_created": now_wib,
                "triggered": False
            }
            st.session_state.active_alerts.append(alert_data)
            
            # Simpan ke Supabase
            try:
                supabase: Client = create_client(url, key)
                supabase.table("active_alerts").insert(alert_data).execute()
                
                # Tampilan Sukses
                st.markdown(f"""
                <div class="alert-success-box">
                    <p style="font-family:Orbitron;font-size:12px;margin:0 0 8px;letter-spacing:2px;">SENSOR ACTIVATED</p>
                    <p style="font-size:13px;opacity:0.9;margin:2px 0;">INSTRUMENT: {selected_instrument}</p>
                    <p style="font-size:13px;opacity:0.9;margin:2px 0;">TARGET: {price_display}</p>
                    <p style="font-size:13px;opacity:0.9;margin:2px 0;">STATUS: MONITORING 24/7</p>
                </div>
                """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"SYSTEM ERROR: DATABASE SYNC FAILED")
                st.caption(f"Details: {str(e)}")
        else:
            st.warning("Please enter both Target Price and Telegram Chat ID.")

    st.markdown("</div>", unsafe_allow_html=True)
