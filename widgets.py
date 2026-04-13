import streamlit as st

def economic_calendar_widget():
    """
    Menampilkan Kalender Ekonomi Real-time menggunakan Iframe TradingView
    dengan gaya visual Cyber Tech Blue yang konsisten dengan AeroVulpis.
    """
    
    # CSS Khusus untuk Widget Kalender Ekonomi
    st.markdown("""
    <style>
        .economic-calendar-container {
            border: 2px solid #00d4ff;
            border-radius: 15px;
            padding: 15px;
            background: rgba(0, 212, 255, 0.02);
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        
        .calendar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        
        .calendar-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 20px;
            font-weight: 700;
            color: #00d4ff;
            text-shadow: 0 0 15px rgba(0, 212, 255, 0.6);
            margin: 0;
            text-transform: uppercase;
        }
        
        .status-indicator {
            font-family: 'Rajdhani', sans-serif;
            font-size: 9px;
            color: #00ff88;
            letter-spacing: 1px;
            background: rgba(0, 255, 136, 0.1);
            padding: 3px 6px;
            border-radius: 5px;
            border: 1px solid rgba(0, 255, 136, 0.3);
            display: flex;
            align-items: center;
        }
        
        .status-dot {
            height: 5px;
            width: 5px;
            background-color: #00ff88;
            border-radius: 50%;
            display: inline-block;
            margin-right: 5px;
            box-shadow: 0 0 8px #00ff88;
            animation: pulse-green 2s infinite;
        }
        
        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 10px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }

        /* Styling Iframe agar lebih menyatu */
        .tradingview-widget-container iframe {
            border-radius: 8px !important;
            /* Filter dikurangi agar data angka (Actual/Forecast) lebih jelas terbaca */
            filter: hue-rotate(180deg) brightness(0.9) contrast(1.1); 
        }
        
        /* Legenda Dampak */
        .impact-legend {
            display: flex;
            gap: 12px;
            margin-top: 10px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 11px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .dot-high { color: #ff2a6d; }
        .dot-med { color: #ffcc00; }
        .dot-low { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

    # Container Utama
    st.markdown("""
    <div class="economic-calendar-container">
        <div class="calendar-header">
            <h2 class="calendar-title">KALENDER EKONOMI</h2>
            <div class="status-indicator">
                <span class="status-dot"></span>
                STATUS: AKTIF • REAL-TIME
            </div>
        </div>
    """, unsafe_allow_html=True)

    # TradingView Economic Calendar Widget (Iframe)
    # Tinggi dikurangi menjadi 450 agar tidak terlalu memakan layar
    # importanceFilter disesuaikan agar menampilkan data yang lebih relevan
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
        # Menggunakan height=450 agar sesuai dengan konfigurasi widget
        st.components.v1.html(tradingview_html, height=450)
    except Exception as e:
        st.error(f"Gagal memuat kalender ekonomi: {str(e)}")

    # Legenda Dampak & Penutup Container
    st.markdown("""
        <div class="impact-legend">
            <div class="legend-item"><span class="dot-high">🔴</span> High</div>
            <div class="legend-item"><span class="dot-med">🟡</span> Medium</div>
            <div class="legend-item"><span class="dot-low">🟢</span> Low</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
