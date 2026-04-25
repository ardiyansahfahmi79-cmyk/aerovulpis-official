import streamlit as st
import requests
import os
import yfinance as yf
from supabase import create_client, Client

# Konfigurasi Supabase dari Secrets
url = st.secrets["supabase_url"]
key = st.secrets["supabase_key"]

def economic_calendar_widget():
    """
    Menampilkan Economic Radar Real-time menggunakan Iframe TradingView
    dengan gaya visual Cyber Tech Blue yang konsisten dengan AeroVulpis.
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
            margin-bottom: 10px;
        }
        .radar-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 28px;
            color: #00d4ff;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="economic-radar-container"><h2 class="radar-title">ECONOMIC RADAR</h2>', unsafe_allow_html=True)
    
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
    st.components.v1.html(tradingview_html, height=450)
    st.markdown('</div>', unsafe_allow_html=True)

def smart_alert_widget():
    """
    Menampilkan AeroVulpis Smart Alert Center V3.4 dengan gaya UI cyber-tech/terminal.
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
        .alert-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 24px;
            color: #00d4ff;
            text-align: center;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<div class='alert-center-container'>", unsafe_allow_html=True)
    st.markdown("<h2 class='alert-title'>AEROVULPIS TERMINAL</h2>", unsafe_allow_html=True)
    
    instruments_list = ["XAUUSD", "XAGUSD", "BTCUSD", "EURUSD", "GBPUSD", "USDJPY", "WTI", "US100", "Palladium", "Platinum", "GOOGL", "AAPL", "BBCA.JK", "TLKM.JK"]
    selected_instrument = st.selectbox("**INSTRUMENT SELECTOR**", instruments_list, key="alert_instrument")

    # Map instrument to yfinance ticker
    ticker_map = {
        "XAUUSD": "GC=F", "XAGUSD": "SI=F", "BTCUSD": "BTC-USD", 
        "EURUSD": "EURUSD=X", "GBPUSD": "GBPUSD=X", "USDJPY": "USDJPY=X",
        "WTI": "CL=F", "US100": "^IXIC", "Palladium": "PA=F", "Platinum": "PL=F"
    }
    
    current_price = 0.0
    try:
        # 1. Coba ambil dari Supabase
        supabase: Client = create_client(url, key)
        res = supabase.table("market_prices").select("price").eq("instrument", selected_instrument).execute()
        if res.data:
            current_price = res.data[0]["price"]
        else:
            # 2. Fallback ke yfinance jika data di Supabase tidak ada
            ticker_sym = ticker_map.get(selected_instrument, selected_instrument)
            ticker = yf.Ticker(ticker_sym)
            hist = ticker.history(period="1d")
            if not hist.empty:
                current_price = hist["Close"].iloc[-1]
    except:
        pass

    price_format = "{:,.2f}" if "USD" in selected_instrument or "XAU" in selected_instrument else "{:,.4f}"
    display_price = price_format.format(current_price)
    
    st.markdown(f"""
    <div style="background: rgba(0, 212, 255, 0.05); border: 1px solid rgba(0, 212, 255, 0.2); padding: 10px; border-radius: 8px; margin-bottom: 15px; text-align: center;">
        <span style="font-family: 'Rajdhani', sans-serif; font-size: 12px; color: #888;">CURRENT PRICE</span><br>
        <span style="font-family: 'Orbitron', sans-serif; font-size: 18px; color: #00ff88; text-shadow: 0 0 10px rgba(0, 255, 136, 0.5);">
            {display_price}
        </span>
    </div>
    """, unsafe_allow_html=True)

    price_target = st.number_input("**DIGITAL PRICE TARGET**", min_value=0.0, format="%.4f", step=0.0001, key="alert_price_target")
    telegram_chat_id = st.text_input("**TELEGRAM CHAT ID**", value="", placeholder="Masukkan Chat ID Anda...", key="alert_chat_id")
    
    condition_options = {"MELAMPAUI KE ATAS [BULLISH] ↑": "bullish", "TURUN DI BAWAH [BEARISH] ↓": "bearish"}
    selected_condition_label = st.radio("**CONDITION TRIGGER**", list(condition_options.keys()), key="alert_condition")

    if st.button("**LOCK TARGET & ACTIVATE SENSOR**", key="activate_sensor_button", type="primary"):
        if price_target > 0 and telegram_chat_id:
            alert_data = {
                "instrument": selected_instrument,
                "target": price_target,
                "condition": condition_options[selected_condition_label],
                "chat_id": telegram_chat_id,
                "triggered": False
            }
            if "active_alerts" not in st.session_state:
                st.session_state.active_alerts = []
            st.session_state.active_alerts.append(alert_data)
            
            try:
                supabase.table("active_alerts").insert(alert_data).execute()
                st.success(f"SENSOR LOCKED: {selected_instrument} @ {price_target}")
            except:
                st.error("DATABASE SYNC FAILED")
    st.markdown("</div>", unsafe_allow_html=True)
