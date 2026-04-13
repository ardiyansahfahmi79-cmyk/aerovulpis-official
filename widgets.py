import streamlit as st

def economic_calendar_widget():
    """
    Menampilkan Economic Radar Real-time menggunakan Iframe TradingView
    dengan gaya visual Cyber Tech Blue yang konsisten dengan AeroVulpis.
    
    PERBAIKAN TATA LETAK:
    - Judul "ECONOMIC RADAR" berukuran 6px di paling atas.
    - Logo Radar dan Status "LIVE CONNECTION" diletakkan di bawah judul secara rapi.
    - Menghapus radar-info-bar (Actual/Forecast/Previous).
    """
    
    # CSS Khusus untuk Widget Economic Radar
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

        .economic-radar-container {
            border: 2px solid #00d4ff;
            border-radius: 12px;
            padding: 8px;
            background: rgba(0, 212, 255, 0.02);
            box-shadow: 0 0 15px rgba(0, 212, 255, 0.2);
            margin-bottom: 10px;
            position: relative;
            overflow: hidden;
        }
        
        /* Layout Vertikal: Judul di atas, Logo & Status di bawahnya */
        .radar-header-stack {
            display: flex;
            flex-direction: column;
            align-items: center; /* Rata tengah */
            margin-bottom: 8px;
            width: 100%;
            gap: 4px;
        }
        
        .radar-title {
            font-family: 'Orbitron', sans-serif;
            font-size: 6px; /* Sesuai permintaan: 6px */
            font-weight: 700;
            color: #00d4ff;
            text-shadow: 0 0 4px rgba(0, 212, 255, 0.8);
            margin: 0;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            white-space: nowrap;
            text-align: center;
        }
        
        .radar-subtitle-row {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 5px;
        }

        .radar-logo {
            width: 10px;
            height: 10px;
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
            font-size: 5.5px; /* Sedikit lebih kecil agar proporsional */
            color: #00ff88;
            letter-spacing: 0.3px;
            background: rgba(0, 255, 136, 0.05);
            padding: 1px 3px;
            border-radius: 2px;
            border: 0.5px solid rgba(0, 255, 136, 0.2);
            display: flex;
            align-items: center;
            white-space: nowrap;
        }
        
        .status-dot {
            height: 2.5px;
            width: 2.5px;
            background-color: #00ff88;
            border-radius: 50%;
            display: inline-block;
            margin-right: 2px;
            box-shadow: 0 0 2px #00ff88;
            animation: pulse-green 2s infinite;
        }
        
        @keyframes pulse-green {
            0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0.7); }
            70% { transform: scale(1); box-shadow: 0 0 0 2px rgba(0, 255, 136, 0); }
            100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(0, 255, 136, 0); }
        }

        .tradingview-widget-container iframe {
            border-radius: 8px !important;
            filter: hue-rotate(180deg) brightness(0.95) contrast(1.1); 
        }
        
        .impact-legend {
            display: flex;
            justify-content: center;
            gap: 6px;
            margin-top: 6px;
            font-family: 'Rajdhani', sans-serif;
            font-size: 6px;
            flex-wrap: wrap;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            gap: 2px;
            color: #aaa;
        }
        
        .star-icon {
            font-size: 6px;
        }
        
        .high-impact { color: #ff2a6d; text-shadow: 0 0 3px rgba(255, 42, 109, 0.5); }
        .med-impact { color: #ffcc00; }
        .low-impact { color: #00ff88; }
    </style>
    """, unsafe_allow_html=True)

    # Container Utama dengan Tata Letak Baru
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
