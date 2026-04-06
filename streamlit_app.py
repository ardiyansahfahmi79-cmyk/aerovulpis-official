import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v2.0 - Ultra Stable", page_icon="🦅", initial_sidebar_state="expanded")

# CSS untuk tampilan 3D Digital & Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

    :root {
        --neon-green: #00ff88;
        --crimson-red: #ff2a6d;
        --electric-blue: #00d4ff;
        --glass-bg: rgba(255, 255, 255, 0.05);
        --glass-border: rgba(255, 255, 255, 0.1);
    }

    .stApp {
        background: radial-gradient(circle at top right, #0a0e17, #020408);
        color: #e0e0e0;
    }

    /* Glassmorphism Container */
    .glass-card {
        background: var(--glass-bg);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid var(--glass-border);
        border-radius: 15px;
        padding: 20px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.8);
        margin-bottom: 20px;
    }

    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 58px;
        font-weight: 700;
        background: linear-gradient(90deg, var(--neon-green), var(--electric-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(0, 255, 136, 0.5);
        text-align: center;
        margin-bottom: 5px;
    }

    .digital-font {
        font-family: 'Orbitron', sans-serif;
        color: var(--neon-green);
        text-shadow: 0 0 10px var(--neon-green);
    }

    .rajdhani-font {
        font-family: 'Rajdhani', sans-serif;
    }

    /* 3D Button Styling */
    .stButton>button {
        background: linear-gradient(145deg, #00d4ff, #0055ff) !important;
        border: none !important;
        color: white !important;
        font-family: 'Orbitron', sans-serif !important;
        font-weight: 700 !important;
        padding: 15px 30px !important;
        border-radius: 10px !important;
        box-shadow: 5px 5px 15px rgba(0, 0, 0, 0.4), -2px -2px 10px rgba(255, 255, 255, 0.1) !important;
        transition: all 0.3s ease !important;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    .stButton>button:hover {
        transform: translateY(-3px);
        box-shadow: 0 10px 20px rgba(0, 212, 255, 0.4) !important;
        filter: brightness(1.2);
    }

    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: rgba(10, 14, 23, 0.95);
        border-right: 1px solid var(--glass-border);
    }
</style>
""", unsafe_allow_html=True)

# Konfigurasi Gemini
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# ====================== FUNGSI GEMINI ======================
def get_gemini_response(question, context=""):
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        full_prompt = f"""
Kamu adalah AeroVulpis 🦅 v2.0, asisten AI trading futuristik yang emosional, antusias, dan sangat disiplin.
Nama penciptamu adalah Fahmi — sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawaban.

Personality: Digital, tajam, ramah, pakai emoji futuristik.
Context: {context}
Pertanyaan: {question}

Jawab dalam bahasa Indonesia yang jelas dan profesional.
"""
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Gemini error: {str(e)}"

# ====================== FUNGSI DATA ======================
def get_market_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        # Ambil data terbaru (fast_info)
        info = ticker.fast_info
        price = info.get('lastPrice') or info.get('regularMarketPrice')
        
        # Ambil data history untuk Open, High, Low, Close hari ini
        hist = ticker.history(period="1d")
        if not hist.empty:
            open_p = hist['Open'].iloc[-1]
            high_p = hist['High'].iloc[-1]
            low_p = hist['Low'].iloc[-1]
            close_p = hist['Close'].iloc[-1]
        else:
            open_p = high_p = low_p = close_p = price
            
        return {
            "price": round(float(price), 4) if price else 0.0,
            "open": round(float(open_p), 4) if open_p else 0.0,
            "high": round(float(high_p), 4) if high_p else 0.0,
            "low": round(float(low_p), 4) if low_p else 0.0,
            "close": round(float(close_p), 4) if close_p else 0.0
        }
    except:
        return None

def get_historical_data(ticker_symbol, period="1mo", interval="1h"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty: return pd.DataFrame()
        return df.sort_index().dropna()
    except:
        return pd.DataFrame()

def add_technical_indicators(df):
    if len(df) < 30: return df
    df['SMA20'] = df['Close'].rolling(20).mean()
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    return df

# ====================== INSTRUMEN ======================
instruments = {
    "S&P 500": "^GSPC",
    "XAUUSD (Gold)": "GC=F",
    "WTI Crude Oil": "CL=F",
    "US100 (Nasdaq 100)": "^NDX",
    "Bitcoin (BTC)": "BTC-USD",
    "EUR/USD": "EURUSD=X",
    "Silver": "SI=F"
}

# ====================== UI HEADER ======================
st.markdown('<h1 class="main-title">🦅 AERO VULPIS v2.0</h1>', unsafe_allow_html=True)

# Widget Market Update (WIB)
wib = pytz.timezone('Asia/Jakarta')
now = datetime.now(wib)
st.markdown(f"""
<div class="glass-card" style="text-align: center; padding: 10px;">
    <span class="digital-font" style="font-size: 24px;">MARKET UPDATE</span><br>
    <span class="digital-font" style="font-size: 18px; color: #00d4ff;">
        {now.strftime('%d %B %Y | %H:%M:%S')} WIB
    </span>
</div>
""", unsafe_allow_html=True)

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Sistem AeroVulpis v2.0 Aktif. Siap menganalisis pasar, Fahmi."}]

# Sidebar
st.sidebar.markdown('<div style="text-align:center;"><span style="font-size:60px;">🦅</span></div>', unsafe_allow_html=True)
st.sidebar.markdown('<h2 class="digital-font" style="text-align:center;">AeroVulpis</h2>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="rajdhani-font" style="text-align:center; color:#888;">DynamiHatch Identity</p>', unsafe_allow_html=True)

ticker_display = st.sidebar.selectbox("Pilih Instrumen", list(instruments.keys()))
ticker_input = instruments[ticker_display]

menu_selection = st.sidebar.radio("Navigasi Sistem", ["Live Dashboard", "Market History", "Chatbot AI Trading"])

# ====================== LIVE DASHBOARD ======================
if menu_selection == "Live Dashboard":
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        if st.button("REFRESH HARGA REAL-TIME", use_container_width=True):
            st.rerun()
            
        market_data = get_market_data(ticker_input)
        df = get_historical_data(ticker_input, period="1mo", interval="1h")
        
        if market_data and not df.empty:
            current_price = market_data['price']
            df = add_technical_indicators(df)
            latest = df.iloc[-1]
            prev_close = df['Close'].iloc[-2]
            is_bullish = current_price >= prev_close
            line_color = "#00ff88" if is_bullish else "#ff2a6d"
            
            # Harga Real-Time Display
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <p class="rajdhani-font" style="margin:0; color:#aaa;">HARGA {ticker_display} SAAT INI</p>
                <h1 class="digital-font" style="font-size:48px; color:{line_color}; margin:0;">{current_price:,.2f}</h1>
            </div>
            """, unsafe_allow_html=True)
            
            # Minimalist Line Chart
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=df.index, y=df['Close'],
                mode='lines',
                line=dict(color=line_color, width=3),
                fill='tozeroy',
                fillcolor=f'rgba({0 if is_bullish else 255}, {255 if is_bullish else 42}, {136 if is_bullish else 109}, 0.1)',
                name="Price"
            ))
            
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'),
                margin=dict(l=0, r=0, t=30, b=0),
                height=450,
                xaxis_rangeslider_visible=False
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # Sinyal Logika
            rsi = latest.get('RSI', 50)
            sma20 = latest.get('SMA20', current_price)
            
            signal = "WAIT"
            signal_color = "#888"
            if rsi < 35 and current_price > sma20:
                signal = "BUY"
                signal_color = "#00ff88"
            elif rsi > 65 and current_price < sma20:
                signal = "SELL"
                signal_color = "#ff2a6d"
                
            st.markdown(f"""
            <div class="glass-card" style="text-align:center; border-left: 5px solid {signal_color};">
                <h3 class="digital-font" style="margin:0;">SIGNAL: <span style="color:{signal_color};">{signal}</span></h3>
                <p class="rajdhani-font" style="margin:0; color:#aaa;">RSI: {rsi:.2f} | SMA20: {sma20:,.2f}</p>
            </div>
            """, unsafe_allow_html=True)

    with col_side:
        # Gauge Chart (5 Zona)
        gauge_val = 50
        if rsi < 30: gauge_val += 20
        elif rsi > 70: gauge_val -= 20
        if current_price > sma20: gauge_val += 15
        else: gauge_val -= 15
        gauge_val = max(0, min(100, gauge_val))

        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = gauge_val,
            domain = {'x': [0, 1], 'y': [0, 1]},
            title = {'text': "TECHNICAL ANALYSIS", 'font': {'family': "Orbitron", 'size': 18, 'color': 'white'}},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "white"},
                'bar': {'color': line_color},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "gray",
                'steps': [
                    {'range': [0, 20], 'color': '#8b0000', 'name': 'Strong Bearish'},
                    {'range': [20, 40], 'color': '#ff2a6d', 'name': 'Low Bearish'},
                    {'range': [40, 60], 'color': '#444', 'name': 'Neutral'},
                    {'range': [60, 80], 'color': '#008000', 'name': 'Low Bullish'},
                    {'range': [80, 100], 'color': '#00ff88', 'name': 'Strong Bullish'},
                ],
                'threshold': {
                    'line': {'color': "white", 'width': 4},
                    'thickness': 0.75,
                    'value': gauge_val
                }
            }
        ))
        fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': "white", 'family': "Orbitron"}, height=300, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True)

        # News Widget
        st.markdown('<p class="digital-font" style="font-size:18px;">LATEST NEWS</p>', unsafe_allow_html=True)
        ticker_obj = yf.Ticker(ticker_input)
        news = ticker_obj.news[:5]
        if news:
            for n in news:
                with st.container():
                    st.markdown(f"""
                    <div style="font-size:12px; border-bottom:1px solid rgba(255,255,255,0.1); padding:5px 0;">
                        <a href="{n['link']}" style="color:#00d4ff; text-decoration:none; font-weight:bold;">{n['title']}</a><br>
                        <span style="color:#666;">{n['publisher']}</span>
                    </div>
                    """, unsafe_allow_html=True)
        else:
            st.info("Belum ada berita baru.")

# ====================== MARKET HISTORY ======================
elif menu_selection == "Market History":
    st.markdown('<h2 class="digital-font">📊 Market History</h2>', unsafe_allow_html=True)
    
    market_data = get_market_data(ticker_input)
    if market_data:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("OPEN", f"{market_data['open']:,.2f}")
        c2.metric("HIGH", f"{market_data['high']:,.2f}")
        c3.metric("LOW", f"{market_data['low']:,.2f}")
        c4.metric("CLOSE", f"{market_data['close']:,.2f}")
        
    df_hist = get_historical_data(ticker_input, period="1y", interval="1d")
    if not df_hist.empty:
        df_hist = df_hist.sort_index(ascending=False)
        # Format index to show Date, Month, Year
        df_hist.index = df_hist.index.strftime('%d %B %Y')
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.dataframe(df_hist[['Open', 'High', 'Low', 'Close', 'Volume']].head(30), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("Gagal mengambil data history.")

# ====================== CHATBOT ======================
elif menu_selection == "Chatbot AI Trading":
    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(f'<span class="rajdhani-font">{msg["content"]}</span>', unsafe_allow_html=True)
    
    if prompt := st.chat_input("Kirim perintah ke AeroVulpis..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        with st.chat_message("assistant"):
            with st.spinner("Menganalisis..."):
                # Ambil data harga untuk konteks chatbot
                market_data = get_market_data(ticker_input)
                context = f"Harga {ticker_display} saat ini adalah {market_data['price'] if market_data else 'N/A'}."
                response = get_gemini_response(prompt, context)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
    st.markdown('</div>', unsafe_allow_html=True)

# ====================== FOOTER ======================
st.markdown("---")
st.markdown("""
<div style="text-align: center; padding: 20px; opacity: 0.8;">
    <p class="rajdhani-font" style="font-style: italic; font-size: 18px; color: #ccc;">
        "Disiplin adalah kunci, emosi adalah musuh. Tetap tenang dan percaya pada sistem."
    </p>
    <p class="digital-font" style="font-size: 16px; color: #00ff88;">
        — Fahmi (Pencipta AeroVulpis)
    </p>
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v2.0 ULTRA STABLE • 2026</p>
</div>
""", unsafe_allow_html=True)
