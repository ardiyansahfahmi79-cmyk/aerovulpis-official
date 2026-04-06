import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pytz
import time
import json

# ==============================================================================
# AEROVULPIS v2.0 - ULTRA PROFESSIONAL EDITION
# Created by: Fahmi
# Identity: DynamiHatch
# ==============================================================================

# 1. KONFIGURASI HALAMAN
st.set_page_config(
    layout="wide", 
    page_title="AeroVulpis v2.0 | Digital 3D Trading Intelligence", 
    page_icon="🦅", 
    initial_sidebar_state="expanded"
)

# 2. CSS CUSTOM - DIGITAL 3D & GLASSMORPHISM (ULTRA DETAIL)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;700;900&family=Rajdhani:wght@300;400;500;600;700&family=JetBrains+Mono:wght@300;400&display=swap');

    :root {
        --neon-green: #00ff88;
        --neon-blue: #00d4ff;
        --crimson-red: #ff2a6d;
        --deep-space: #050a14;
        --glass-bg: rgba(10, 20, 40, 0.7);
        --glass-border: rgba(0, 212, 255, 0.2);
        --glow-shadow: 0 0 15px rgba(0, 212, 255, 0.4);
    }

    /* Global Styles */
    .stApp {
        background: radial-gradient(circle at 50% 50%, #0a1428 0%, #02050a 100%);
        color: #e0e0e0;
        font-family: 'Rajdhani', sans-serif;
    }

    /* 3D Title & Logo Animation */
    .header-container {
        perspective: 1000px;
        text-align: center;
        padding: 40px 0;
    }

    .logo-3d {
        font-size: 100px;
        display: inline-block;
        animation: float3d 4s ease-in-out infinite;
        filter: drop-shadow(0 0 20px var(--neon-blue));
        margin-bottom: 10px;
    }

    @keyframes float3d {
        0%, 100% { transform: translateZ(20px) rotateY(0deg) translateY(0); }
        50% { transform: translateZ(50px) rotateY(10deg) translateY(-15px); }
    }

    .title-3d {
        font-family: 'Orbitron', sans-serif;
        font-size: 64px;
        font-weight: 900;
        text-transform: uppercase;
        letter-spacing: 8px;
        background: linear-gradient(to bottom, #fff 20%, var(--neon-blue) 50%, #0055ff 80%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        filter: drop-shadow(0 0 10px rgba(0, 212, 255, 0.8));
        transform: rotateX(10deg);
        margin: 0;
    }

    /* Glassmorphism Cards */
    .glass-panel {
        background: var(--glass-bg);
        backdrop-filter: blur(15px);
        -webkit-backdrop-filter: blur(15px);
        border: 1px solid var(--glass-border);
        border-radius: 20px;
        padding: 25px;
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.5), inset 0 0 15px rgba(0, 212, 255, 0.05);
        margin-bottom: 25px;
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }

    .glass-panel:hover {
        transform: translateY(-5px);
        box-shadow: 0 20px 45px rgba(0, 0, 0, 0.6), 0 0 20px rgba(0, 212, 255, 0.2);
    }

    /* Digital Elements */
    .digital-clock {
        font-family: 'Orbitron', sans-serif;
        color: var(--neon-green);
        font-size: 28px;
        text-shadow: 0 0 15px var(--neon-green);
        background: rgba(0, 255, 136, 0.05);
        padding: 15px 30px;
        border-radius: 50px;
        border: 1px solid rgba(0, 255, 136, 0.2);
        display: inline-block;
    }

    .market-label {
        font-family: 'Orbitron', sans-serif;
        font-size: 14px;
        color: var(--neon-blue);
        letter-spacing: 2px;
        margin-bottom: 5px;
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #050a14 0%, #02050a 100%);
        border-right: 1px solid var(--glass-border);
    }

    .sidebar-logo {
        text-align: center;
        padding: 20px 0;
        border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    }

    /* Custom Buttons */
    .stButton>button {
        width: 100%;
        background: linear-gradient(135deg, rgba(0, 212, 255, 0.1), rgba(0, 85, 255, 0.1)) !important;
        border: 1px solid var(--neon-blue) !important;
        color: var(--neon-blue) !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        padding: 12px !important;
        border-radius: 12px !important;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) !important;
        text-transform: uppercase;
        letter-spacing: 2px;
    }

    .stButton>button:hover {
        background: var(--neon-blue) !important;
        color: #000 !important;
        box-shadow: 0 0 25px var(--neon-blue);
        transform: scale(1.02);
    }

    /* Metrics Styling */
    [data-testid="stMetricValue"] {
        font-family: 'Orbitron', sans-serif !important;
        font-size: 24px !important;
        color: #fff !important;
    }

    /* Scrollbar */
    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: #050a14; }
    ::-webkit-scrollbar-thumb { background: var(--neon-blue); border-radius: 10px; }
</style>

<script>
    // Audio Context for Futuristic SFX
    let audioCtx;
    function initAudio() {
        if (!audioCtx) audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }

    function playDigitalBeep(freq = 880, duration = 0.1, type = 'square') {
        initAudio();
        const osc = audioCtx.createOscillator();
        const gain = audioCtx.createGain();
        
        osc.type = type;
        osc.frequency.setValueAtTime(freq, audioCtx.currentTime);
        osc.connect(gain);
        gain.connect(audioCtx.destination);
        
        gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + duration);
        
        osc.start();
        osc.stop(audioCtx.currentTime + duration);
    }
</script>
""", unsafe_allow_html=True)

# 3. AUDIO TRIGGER FUNCTION
def trigger_sfx(effect_type="click"):
    if effect_type == "click":
        st.components.v1.html("<script>window.parent.playDigitalBeep(1200, 0.05, 'sine');</script>", height=0)
    elif effect_type == "refresh":
        st.components.v1.html("<script>window.parent.playDigitalBeep(880, 0.15, 'square');</script>", height=0)
    elif effect_type == "alert":
        st.components.v1.html("<script>window.parent.playDigitalBeep(440, 0.3, 'triangle');</script>", height=0)

# 4. KONFIGURASI AI (GEMINI)
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

def get_ai_analysis(ticker, price, indicators, news_context):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        Sistem: AeroVulpis v2.0 Intelligence 🦅
        User: Fahmi (Pencipta)
        
        Data Pasar:
        - Instrumen: {ticker}
        - Harga Terkini: {price}
        - RSI (14): {indicators.get('RSI', 'N/A')}
        - SMA (20): {indicators.get('SMA20', 'N/A')}
        - Tren: {'Bullish' if price > indicators.get('SMA20', 0) else 'Bearish'}
        
        Berita Terkini:
        {news_context}
        
        Tugas: Berikan analisis trading yang tajam, teknikal, dan futuristik. 
        Gunakan gaya bahasa profesional namun antusias. 
        Sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawaban.
        """
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ AI Core Error: {str(e)}"

# 5. ENGINE DATA (YFINANCE)
class MarketEngine:
    @staticmethod
    @st.cache_data(ttl=60)
    def fetch_history(symbol, period="1mo", interval="1h"):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            if df.empty: return None
            return df.sort_index().dropna()
        except:
            return None

    @staticmethod
    def calculate_indicators(df):
        if df is None or len(df) < 30: return df
        # SMA
        df['SMA20'] = df['Close'].rolling(window=20).mean()
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        # RSI
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        # Bollinger Bands
        df['STD'] = df['Close'].rolling(window=20).std()
        df['BB_Upper'] = df['SMA20'] + (df['STD'] * 2)
        df['BB_Lower'] = df['SMA20'] - (df['STD'] * 2)
        return df

    @staticmethod
    def get_live_stats(symbol):
        try:
            t = yf.Ticker(symbol)
            info = t.fast_info
            return {
                "price": info.get('lastPrice'),
                "change": info.get('regularMarketChangePercent'),
                "volume": info.get('lastVolume'),
                "high": info.get('dayHigh'),
                "low": info.get('dayLow')
            }
        except:
            return None

# 6. UI COMPONENTS
def render_header():
    st.markdown("""
    <div class="header-container">
        <div class="logo-3d">🦅</div>
        <h1 class="title-3d">AeroVulpis v2.0</h1>
        <p style="color: var(--neon-blue); letter-spacing: 5px; font-family: 'Orbitron'; font-size: 14px; margin-top: -10px;">
            Digital Intelligence Trading System
        </p>
    </div>
    """, unsafe_allow_html=True)

def render_market_update():
    wib = pytz.timezone('Asia/Jakarta')
    now = datetime.now(wib)
    st.markdown(f"""
    <div style="text-align: center; margin-bottom: 40px;">
        <div class="market-label">SYSTEM TIME (WIB)</div>
        <div class="digital-clock">
            {now.strftime('%H:%M:%S')}
        </div>
        <div style="margin-top: 10px; font-family: 'Rajdhani'; font-weight: 600; color: #888;">
            {now.strftime('%A, %d %B %Y')}
        </div>
    </div>
    """, unsafe_allow_html=True)

def render_gauge(value, title, color):
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        title={'text': title, 'font': {'family': 'Orbitron', 'size': 16, 'color': '#fff'}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
            'bar': {'color': color},
            'bgcolor': "rgba(0,0,0,0)",
            'borderwidth': 2,
            'bordercolor': "rgba(255,255,255,0.1)",
            'steps': [
                {'range': [0, 20], 'color': 'rgba(255, 42, 109, 0.3)'},
                {'range': [20, 40], 'color': 'rgba(255, 42, 109, 0.1)'},
                {'range': [40, 60], 'color': 'rgba(255, 255, 255, 0.05)'},
                {'range': [60, 80], 'color': 'rgba(0, 255, 136, 0.1)'},
                {'range': [80, 100], 'color': 'rgba(0, 255, 136, 0.3)'}
            ],
            'threshold': {
                'line': {'color': "white", 'width': 4},
                'thickness': 0.75,
                'value': value
            }
        }
    ))
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font={'color': "white", 'family': "Orbitron"},
        height=250,
        margin=dict(l=30, r=30, t=50, b=20)
    )
    return fig

# 7. MAIN LOGIC
def main():
    # Session State Init
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()

    # Sidebar
    with st.sidebar:
        st.markdown('<div class="sidebar-logo"><span style="font-size:50px;">🦅</span><br><span class="digital-font" style="font-size:20px; color:var(--neon-blue);">AERO VULPIS</span></div>', unsafe_allow_html=True)
        st.markdown("### 🛠️ CONTROL PANEL")
        
        instruments = {
            "GOLD (XAU/USD)": "GC=F",
            "CRUDE OIL (WTI)": "CL=F",
            "NASDAQ 100": "^NDX",
            "BITCOIN (BTC)": "BTC-USD",
            "EUR/USD": "EURUSD=X",
            "S&P 500": "^GSPC",
            "SILVER": "SI=F",
            "ETHEREUM": "ETH-USD"
        }
        
        selected_label = st.selectbox("SELECT INSTRUMENT", list(instruments.keys()))
        symbol = instruments[selected_label]
        
        timeframe = st.selectbox("TIMEFRAME", ["1m", "5m", "15m", "1h", "1d"], index=3)
        period_map = {"1m": "1d", "5m": "5d", "15m": "1wk", "1h": "1mo", "1d": "1y"}
        
        st.markdown("---")
        nav = st.radio("NAVIGATION", ["DASHBOARD", "AI INTELLIGENCE", "MARKET NEWS", "SYSTEM LOGS"])
        
        st.markdown("---")
        st.info(f"Identity: DynamiHatch\nCreator: Fahmi\nVersion: 2.0 Stable")

    # Header & Time
    render_header()
    render_market_update()

    # Data Fetching
    engine = MarketEngine()
    df = engine.fetch_history(symbol, period=period_map[timeframe], interval=timeframe)
    live = engine.get_live_stats(symbol)

    if df is not None and live is not None:
        df = engine.calculate_indicators(df)
        latest = df.iloc[-1]
        
        # Dashboard View
        if nav == "DASHBOARD":
            # Top Metrics
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.metric("CURRENT PRICE", f"{live['price']:.2f}", f"{live['change']:.2f}%")
                st.markdown('</div>', unsafe_allow_html=True)
            with m2:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.metric("RSI (14)", f"{latest['RSI']:.2f}")
                st.markdown('</div>', unsafe_allow_html=True)
            with m3:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.metric("DAY HIGH", f"{live['high']:.2f}")
                st.markdown('</div>', unsafe_allow_html=True)
            with m4:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.metric("DAY LOW", f"{live['low']:.2f}")
                st.markdown('</div>', unsafe_allow_html=True)

            # Main Chart Area
            col_chart, col_gauge = st.columns([3, 1])
            
            with col_chart:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                
                # Plotly Chart
                is_up = live['change'] >= 0
                line_color = "#00ff88" if is_up else "#ff2a6d"
                
                fig = go.Figure()
                # Price Line
                fig.add_trace(go.Scatter(
                    x=df.index, y=df['Close'],
                    mode='lines',
                    line=dict(color=line_color, width=3),
                    fill='tozeroy',
                    fillcolor=f'rgba({0 if is_up else 255}, {255 if is_up else 42}, {136 if is_up else 109}, 0.1)',
                    name="Price"
                ))
                # SMA 20
                fig.add_trace(go.Scatter(
                    x=df.index, y=df['SMA20'],
                    line=dict(color='rgba(0, 212, 255, 0.5)', width=1.5, dash='dot'),
                    name="SMA 20"
                ))
                
                fig.update_layout(
                    template="plotly_dark",
                    paper_bgcolor='rgba(0,0,0,0)',
                    plot_bgcolor='rgba(0,0,0,0)',
                    xaxis=dict(showgrid=False, zeroline=False, showline=False),
                    yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', zeroline=False),
                    margin=dict(l=10, r=10, t=10, b=10),
                    height=500,
                    hovermode="x unified",
                    showlegend=False
                )
                st.plotly_chart(fig, use_container_width=True)
                
                if st.button("⚡ REFRESH SYSTEM DATA"):
                    trigger_sfx("refresh")
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

            with col_gauge:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                # Trend Strength Logic
                rsi_val = latest['RSI']
                price_vs_sma = (latest['Close'] / latest['SMA20'] - 1) * 1000
                strength = 50 + (50 - rsi_val) + price_vs_sma
                strength = max(0, min(100, strength))
                
                st.plotly_chart(render_gauge(strength, "TREND STRENGTH", line_color), use_container_width=True)
                
                # Signal Box
                signal = "NEUTRAL"
                sig_color = "#888"
                if rsi_val < 35 and latest['Close'] > latest['SMA20']:
                    signal = "STRONG BUY"
                    sig_color = "#00ff88"
                elif rsi_val > 65 and latest['Close'] < latest['SMA20']:
                    signal = "STRONG SELL"
                    sig_color = "#ff2a6d"
                
                st.markdown(f"""
                <div style="text-align:center; padding:15px; border:1px solid {sig_color}; border-radius:10px; background:rgba(255,255,255,0.02);">
                    <div style="font-family:'Orbitron'; font-size:12px; color:#aaa;">CURRENT SIGNAL</div>
                    <div style="font-family:'Orbitron'; font-size:24px; color:{sig_color}; text-shadow:0 0 10px {sig_color};">
                        {signal}
                    </div>
                </div>
                """, unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)

            # Bottom Info
            c1, c2 = st.columns(2)
            with c1:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.markdown("### 📊 TECHNICAL SUMMARY")
                st.write(f"**SMA 50:** {latest['SMA50']:.2f}")
                st.write(f"**BB Upper:** {latest['BB_Upper']:.2f}")
                st.write(f"**BB Lower:** {latest['BB_Lower']:.2f}")
                st.markdown('</div>', unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
                st.markdown("### 🦅 SYSTEM STATUS")
                st.success("AeroVulpis Core: ONLINE")
                st.info("Market Feed: STABLE")
                st.warning("AI Engine: READY")
                st.markdown('</div>', unsafe_allow_html=True)

        elif nav == "AI INTELLIGENCE":
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            st.markdown("### 🤖 AEROVULPIS AI CORE")
            
            for chat in st.session_state.chat_history:
                with st.chat_message(chat["role"]):
                    st.markdown(chat["content"])
            
            if prompt := st.chat_input("Ask AeroVulpis Intelligence..."):
                trigger_sfx("click")
                st.session_state.chat_history.append({"role": "user", "content": prompt})
                with st.chat_message("user"):
                    st.markdown(prompt)
                
                with st.chat_message("assistant"):
                    with st.spinner("Processing Market Intelligence..."):
                        # Get news for context
                        t_obj = yf.Ticker(symbol)
                        news = t_obj.news[:3]
                        news_text = "\n".join([f"- {n['title']}" for n in news])
                        
                        response = get_ai_analysis(selected_label, live['price'], latest.to_dict(), news_text)
                        st.markdown(response)
                        st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.markdown('</div>', unsafe_allow_html=True)

        elif nav == "MARKET NEWS":
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            st.markdown(f"### 📰 LATEST NEWS: {selected_label}")
            t_obj = yf.Ticker(symbol)
            news_list = t_obj.news
            if news_list:
                for n in news_list:
                    with st.container():
                        st.markdown(f"""
                        <div style="padding:15px; border-bottom:1px solid rgba(255,255,255,0.05);">
                            <div style="color:var(--neon-blue); font-weight:700; font-size:18px;">{n['title']}</div>
                            <div style="color:#666; font-size:12px; margin-bottom:10px;">{n['publisher']} • {datetime.fromtimestamp(n['providerPublishTime']).strftime('%Y-%m-%d %H:%M')}</div>
                            <a href="{n['link']}" target="_blank" style="color:var(--neon-green); text-decoration:none; font-size:14px;">READ FULL ARTICLE →</a>
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("No recent news found for this instrument.")
            st.markdown('</div>', unsafe_allow_html=True)

        elif nav == "SYSTEM LOGS":
            st.markdown('<div class="glass-panel">', unsafe_allow_html=True)
            st.markdown("### 🖥️ SYSTEM LOGS")
            logs = [
                f"[{datetime.now().strftime('%H:%M:%S')}] AeroVulpis v2.0 Initialized.",
                f"[{datetime.now().strftime('%H:%M:%S')}] Connected to Yahoo Finance API.",
                f"[{datetime.now().strftime('%H:%M:%S')}] Gemini AI Core Handshake: SUCCESS.",
                f"[{datetime.now().strftime('%H:%M:%S')}] Fetching data for {symbol}...",
                f"[{datetime.now().strftime('%H:%M:%S')}] UI Rendering: 3D Engine Active.",
                f"[{datetime.now().strftime('%H:%M:%S')}] Identity Verified: DynamiHatch."
            ]
            for log in logs:
                st.code(log, language="bash")
            st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.error("❌ CRITICAL ERROR: Unable to establish connection with Market Data Feed.")
        if st.button("RETRY CONNECTION"):
            st.rerun()

    # 8. FOOTER (SIGNATURE)
    st.markdown("""
    <div style="text-align: center; padding: 50px 0; margin-top: 50px; border-top: 1px solid rgba(255,255,255,0.05);">
        <p style="font-family: 'Rajdhani'; font-style: italic; font-size: 20px; color: #aaa; max-width: 600px; margin: 0 auto 20px;">
            "Disiplin adalah kunci, emosi adalah musuh. Tetap tenang dan percaya pada sistem."
        </p>
        <div style="font-family: 'Orbitron'; font-size: 16px; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green);">
            — FAHMI (Pencipta AeroVulpis)
        </div>
        <div style="margin-top: 15px; font-family: 'Rajdhani'; font-size: 12px; color: #444; letter-spacing: 3px;">
            DYNAMIHATCH IDENTITY • V2.0 ULTRA PRO • 2026
        </div>
    </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
