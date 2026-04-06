import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.1 - Ultimate Trading Edition", page_icon="🦅", initial_sidebar_state="expanded")

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
Kamu adalah AeroVulpis 🦅 v3.1, asisten AI trading futuristik yang emosional, antusias, dan sangat disiplin.
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
        info = ticker.fast_info
        price = info.get('lastPrice') or info.get('regularMarketPrice')
        
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
    # SMA
    df['SMA20'] = df['Close'].rolling(20).mean()
    df['SMA50'] = df['Close'].rolling(50).mean()
    # RSI
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    # MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    return df

# ====================== INSTRUMEN ======================
instruments = {
    "Forex": {
        "EUR/USD": "EURUSD=X",
        "GBP/USD": "GBPUSD=X",
        "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X",
        "USD/CHF": "USDCHF=X"
    },
    "Crypto": {
        "Bitcoin (BTC)": "BTC-USD",
        "Ethereum (ETH)": "ETH-USD",
        "Solana (SOL)": "SOL-USD",
        "Binance Coin (BNB)": "BNB-USD",
        "Ripple (XRP)": "XRP-USD"
    },
    "Komoditas": {
        "Gold (XAUUSD)": "GC=F",
        "WTI Crude Oil": "CL=F",
        "Silver": "SI=F",
        "Natural Gas": "NG=F",
        "Brent Oil": "BZ=F"
    },
    "Stock (AS)": {
        "Apple (AAPL)": "AAPL",
        "Microsoft (MSFT)": "MSFT",
        "NVIDIA (NVDA)": "NVDA",
        "Amazon (AMZN)": "AMZN",
        "Alphabet (GOOGL)": "GOOGL"
    },
    "Stock (Indonesia)": {
        "BBCA (BCA)": "BBCA.JK",
        "BBRI (BRI)": "BBRI.JK",
        "TLKM (Telkom)": "TLKM.JK",
        "BMRI (Mandiri)": "BMRI.JK",
        "ASII (Astra)": "ASII.JK"
    }
}

# ====================== UI HEADER ======================
st.markdown('<h1 class="main-title">🦅 AERO VULPIS v3.1</h1>', unsafe_allow_html=True)

# Session State
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Sistem AeroVulpis v3.1 Aktif. Semua kategori instrumen telah diperbarui. Siap beraksi, Fahmi!"}]

# Sidebar
st.sidebar.markdown('<div style="text-align:center;"><span style="font-size:60px;">🦅</span></div>', unsafe_allow_html=True)
st.sidebar.markdown('<h2 class="digital-font" style="text-align:center;">AeroVulpis</h2>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="rajdhani-font" style="text-align:center; color:#888;">Ultimate Trading Edition</p>', unsafe_allow_html=True)

category = st.sidebar.selectbox("Pilih Kategori", list(instruments.keys()))
ticker_display = st.sidebar.selectbox("Pilih Instrumen", list(instruments[category].keys()))
ticker_input = instruments[category][ticker_display]

menu_selection = st.sidebar.radio("Navigasi Sistem", ["Live Dashboard", "Trading Signals", "Market History", "Chatbot AI Trading"])

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
            
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <p class="rajdhani-font" style="margin:0; color:#aaa;">HARGA {ticker_display} SAAT INI</p>
                <h1 class="digital-font" style="font-size:48px; color:{line_color}; margin:0;">{current_price:,.4f if "USD" in ticker_display or "/" in ticker_display else current_price:,.2f}</h1>
            </div>
            """, unsafe_allow_html=True)
            
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

    with col_side:
        # Gauge Chart (5 Zona)
        if not df.empty:
            rsi = latest.get('RSI', 50)
            sma20 = latest.get('SMA20', current_price)
            
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
                        {'range': [40, 60], 'color': '#888888', 'name': 'Neutral'},
                        {'range': [60, 80], 'color': '#aaffaa', 'name': 'Low Bullish'},
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

        # Benchmark Widget
        st.markdown('<div class="glass-card" style="text-align:center;">', unsafe_allow_html=True)
        st.markdown('<p class="rajdhani-font" style="color:#888; font-size:12px;">S&P 500 Benchmark</p>', unsafe_allow_html=True)
        st.markdown('<h3 class="digital-font" style="color:#00d4ff; margin:0;">6,611.21</h3>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ====================== TRADING SIGNALS ======================
elif menu_selection == "Trading Signals":
    st.markdown('<h2 class="digital-font">⚡ Trading Signals</h2>', unsafe_allow_html=True)
    
    df = get_historical_data(ticker_input, period="1mo", interval="1h")
    if not df.empty:
        df = add_technical_indicators(df)
        latest = df.iloc[-1]
        rsi = latest['RSI']
        macd = latest['MACD']
        sig_line = latest['Signal_Line']
        price = latest['Close']
        sma20 = latest['SMA20']
        sma50 = latest['SMA50']
        
        # Logika Sinyal
        score = 0
        reasons = []
        
        if rsi < 30: 
            score += 2
            reasons.append("RSI Oversold (Bullish)")
        elif rsi > 70: 
            score -= 2
            reasons.append("RSI Overbought (Bearish)")
            
        if macd > sig_line: 
            score += 1
            reasons.append("MACD Crossover Up (Bullish)")
        else: 
            score -= 1
            reasons.append("MACD Crossover Down (Bearish)")
            
        if price > sma20: 
            score += 1
            reasons.append("Price above SMA20 (Bullish)")
        else: 
            score -= 1
            reasons.append("Price below SMA20 (Bearish)")

        if sma20 > sma50:
            score += 1
            reasons.append("Golden Cross Tendency (Bullish)")
        else:
            score -= 1
            reasons.append("Death Cross Tendency (Bearish)")

        # Penentuan Sinyal Akhir
        if score >= 2:
            final_signal = "STRONG BUY"
            sig_color = "#00ff88"
        elif score == 1:
            final_signal = "BUY"
            sig_color = "#aaffaa"
        elif score == -1:
            final_signal = "SELL"
            sig_color = "#ffaaaa"
        elif score <= -2:
            final_signal = "STRONG SELL"
            sig_color = "#ff2a6d"
        else:
            final_signal = "NEUTRAL / WAIT"
            sig_color = "#888888"

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f"""
            <div class="glass-card" style="text-align:center; border-top: 5px solid {sig_color};">
                <p class="rajdhani-font" style="color:#aaa; margin:0;">REKOMENDASI</p>
                <h1 class="digital-font" style="color:{sig_color}; font-size:50px; margin:10px 0;">{final_signal}</h1>
                <p class="rajdhani-font">Confidence Score: {abs(score)}/5</p>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown('<p class="digital-font">SIGNAL ANALYSIS</p>', unsafe_allow_html=True)
            for r in reasons:
                color = "#00ff88" if "Bullish" in r else "#ff2a6d"
                st.markdown(f'<p class="rajdhani-font" style="color:{color};">● {r}</p>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        st.info(f"Strategi: Sinyal ini dihasilkan berdasarkan kombinasi RSI, MACD, dan Moving Averages pada timeframe 1 Jam. Selalu gunakan Stop Loss!")
    else:
        st.error("Data tidak cukup untuk menghasilkan sinyal.")

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
                market_data = get_market_data(ticker_input)
                context = f"Harga {ticker_display} saat ini adalah {market_data['price'] if market_data else 'N/A'}. S&P 500 berada di 6,611.21."
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
    <p style="font-size: 10px; color: #444; letter-spacing: 2px;">DYNAMIHATCH IDENTITY • v3.1 ULTIMATE • 2026</p>
</div>
""", unsafe_allow_html=True)
