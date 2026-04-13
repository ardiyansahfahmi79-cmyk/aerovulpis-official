import streamlit as st

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
            border: 2px solid #00d4ff;
            border-radius: 15px;
            padding: 10px;
            background: rgba(0, 212, 255, 0.02);
            box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        
        .radar-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
            flex-wrap: nowrap;
            gap: 5px;
        }
        
        .radar-title-wrapper {
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .radar-logo {
            width: 18px;
            height: 18px;
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
            border: 1.2px solid #00d4ff;
            border-radius: 50%;
            opacity: 0.6;
        }

        .radar-sweep {
            position: absolute;
            width: 50%;
            height: 1.2px;
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
        
        .radar-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 14px; /* Dikecilkan lagi agar pas di HP */
            font-weight: 700;
            color: #00d4ff;
            text-shadow: 0 0 8px rgba(0, 212, 255, 0.8);
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }
        
        .status-indicator {
            font-family: 'Rajdhani', sans-serif;
            font-size: 8px;
            color: #00ff88;
            letter-spacing: 0.5px;
            background: rgba(0, 255, 136, 0.1);
            padding: 2px 5px;
            border-radius: 3px;
            border: 1px solid rgba(0, 255, 136, 0.3);
            display: flex;
            align-items: center;
            white-space: nowrap;
            flex-shrink: 0;
        }
        
        .status-dot {
            height: 4px;
            width: 4px;
            background-color: #00ff88;
            border-radius: 50%;
            display: inline-block;
            margin-right: 4px;
            box-shadow: 0 0 5px #00ff88;
            animation: pulse-green 2s infinite;
        }
        
        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 4px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }

        .tradingview-widget-container iframe {
            border-radius: 10px !important;
            filter: hue-rotate(180deg) brightness(0.95) contrast(1.1); 
        }
        
        .radar-info-bar {
            display: flex;
            justify-content: space-around;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(0, 212, 255, 0.1);
            border-radius: 8px;
            padding: 5px;
            margin-bottom: 10px;
            font-family: 'Rajdhani', sans-serif;
        }

        .info-item {
            text-align: center;
        }

        .info-label {
            font-size: 7px;
            color: #888;
            text-transform: uppercase;
            display: block;
        }

        .info-value {
            font-size: 10px;
            color: #00d4ff;
            font-weight: 700;
        }
        
        .impact-legend {
            display: flex;
            justify-content: center;
            gap: 12px;
            margin-top: 10px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 9px;
            flex-wrap: wrap;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 3px;
            color: #aaa;
        }
        
        .star-icon {
            font-size: 9px;
        }
        
        .high-impact { color: #ff2a6d; text-shadow: 0 0 5px rgba(255, 42, 109, 0.5); }
        .med-impact { color: #ffcc00; }
        .low-impact { color: #00ff88; }

        @media (max-width: 480px) {
            .radar-title {
                font-size: 13px;
            }
            .status-indicator {
                font-size: 7px;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # Container Utama (DIBUNGKUS DALAM SATU st.markdown)
    st.markdown("""
    <div class="economic-radar-container">
        <div class="radar-header">
            <div class="radar-title-wrapper">
                <div class="radar-logo">
                    <div class="radar-circle"></div>
                    <div class="radar-sweep"></div>
                </div>
                <h2 class="radar-title">ECONOMIC RADAR</h2>
            </div>
            <div class="status-indicator">
                <span class="status-dot"></span>
                LIVE CONNECTION
            </div>
        </div>
        
        <div class="radar-info-bar">
            <div class="info-item">
                <span class="info-label">Actual</span>
                <span class="info-value">REAL-TIME</span>
            </div>
            <div class="info-item">
                <span class="info-label">Forecast</span>
                <span class="info-value">ESTIMATED</span>
            </div>
            <div class="info-item">
                <span class="info-label">Previous</span>
                <span class="info-value">HISTORICAL</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # TradingView Economic Calendar Widget (Iframe)
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
