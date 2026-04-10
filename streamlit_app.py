import streamlit as st
from groq import Groq
import os
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime
import pytz
from dotenv import load_dotenv

# Memuat variabel lingkungan dari file .env
load_dotenv()

# ====================== KONFIGURASI ======================
st.set_page_config(layout="wide", page_title="AeroVulpis v3.3 - Groq Edition", page_icon="🦅", initial_sidebar_state="expanded")

# CSS untuk tampilan 3D Digital & Glassmorphism
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700&family=Rajdhani:wght@300;500;700&display=swap');

    :root {
        --neon-green: #00ff88;
        --crimson-red: #ff2a6d;
        --electric-blue: #00d4ff;
        --deep-blue: #0055ff;
        --glass-bg: rgba(255, 255, 255, 0.05);
        --glass-border: rgba(255, 255, 255, 0.1);
    }

    .stApp {
        background: radial-gradient(circle at top right, #0a0e17, #020408);
        color: #e0e0e0;
    }

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

    .main-title-container {
        text-align: center;
        margin-bottom: 20px;
    }

    .main-logo-container {
        position: relative;
        display: inline-block;
        animation: float 4s infinite ease-in-out;
        padding: 20px 0;
        background: transparent !important;
        perspective: 1200px;
    }

    .custom-logo {
        width: 180px;
        filter: drop-shadow(0 0 10px var(--electric-blue));
        transition: all 0.5s ease;
        background-color: transparent !important;
        animation: smoothRotate3D 12s infinite cubic-bezier(0.45, 0.05, 0.55, 0.95);
        transform-style: preserve-3d;
    }

    @keyframes float {
        0%, 100% { transform: translateY(0px); }
        50% { transform: translateY(-15px); }
    }

    @keyframes smoothRotate3D {
        0% { transform: rotateY(0deg); }
        25% { transform: rotateY(0deg); }
        50% { transform: rotateY(360deg); }
        75% { transform: rotateY(360deg); }
        100% { transform: rotateY(0deg); }
    }

    .main-title {
        font-family: 'Orbitron', sans-serif;
        font-size: 58px;
        font-weight: 700;
        background: linear-gradient(90deg, var(--electric-blue), var(--deep-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 0 0 20px rgba(0, 212, 255, 0.5);
        margin: 0;
    }

    .digital-font {
        font-family: 'Orbitron', sans-serif;
        color: var(--neon-green);
        text-shadow: 0 0 10px var(--neon-green);
    }

    .rajdhani-font {
        font-family: 'Rajdhani', sans-serif;
    }

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

    [data-testid="stSidebar"] {
        background-color: rgba(10, 14, 23, 0.95);
        border-right: 1px solid var(--glass-border);
    }
</style>
""", unsafe_allow_html=True)

# Konfigurasi Groq API
groq_api_key = st.secrets.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
client = None
if groq_api_key:
    try:
        client = Groq(api_key=groq_api_key)
    except Exception as e:
        st.sidebar.error(f"⚠️ Error menginisialisasi Groq: {str(e)}")
else:
    st.sidebar.error("⚠️ GROQ_API_KEY tidak ditemukan di file .env atau Secrets")

# ====================== FUNGSI DATA & INDIKATOR ======================
def get_market_data(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty:
            price = hist['Close'].iloc[-1]
            open_p = hist['Open'].iloc[0]
            high_p = hist['High'].max()
            low_p = hist['Low'].min()
            close_p = price
        else:
            hist_daily = ticker.history(period="1d")
            if not hist_daily.empty:
                price = hist_daily['Close'].iloc[-1]
                open_p = hist_daily['Open'].iloc[-1]
                high_p = hist_daily['High'].iloc[-1]
                low_p = hist_daily['Low'].iloc[-1]
                close_p = price
            else:
                info = ticker.fast_info
                price = info.get('lastPrice') or info.get('regularMarketPrice') or 0.0
                open_p = high_p = low_p = close_p = price
            
        return {
            "price": round(float(price), 4) if price is not None else 0.0,
            "open": round(float(open_p), 4) if open_p is not None else 0.0,
            "high": round(float(high_p), 4) if high_p is not None else 0.0,
            "low": round(float(low_p), 4) if low_p is not None else 0.0,
            "close": round(float(close_p), 4) if close_p is not None else 0.0
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
    if len(df) < 50: return df
    
    # 1. SMA 20, 50, 200
    df['SMA20'] = df['Close'].rolling(window=20).mean()
    df['SMA50'] = df['Close'].rolling(window=50).mean()
    df['SMA200'] = df['Close'].rolling(window=min(len(df), 200)).mean()
    
    # 2. EMA 9
    df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
    
    # 3. RSI 14
    delta = df['Close'].diff()
    gain = delta.where(delta > 0, 0).rolling(window=14).mean()
    loss = -delta.where(delta < 0, 0).rolling(window=14).mean()
    rs = gain / loss.replace(0, 0.001)
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 4. MACD
    exp1 = df['Close'].ewm(span=12, adjust=False).mean()
    exp2 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp1 - exp2
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 5. Bollinger Bands
    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + (df['BB_Std'] * 2)
    df['BB_Lower'] = df['BB_Mid'] - (df['BB_Std'] * 2)
    
    # 6. Stochastic Oscillator
    low_14 = df['Low'].rolling(window=14).min()
    high_14 = df['High'].rolling(window=14).max()
    df['Stoch_K'] = 100 * ((df['Close'] - low_14) / (high_14 - low_14).replace(0, 0.001))
    df['Stoch_D'] = df['Stoch_K'].rolling(window=3).mean()
    
    # 7. ATR (Average True Range)
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    df['TR'] = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = df['TR'].rolling(window=14).mean()
    
    # 8. ADX (Average Directional Index) - Simplified
    df['UpMove'] = df['High'] - df['High'].shift()
    df['DownMove'] = df['Low'].shift() - df['Low']
    df['+DM'] = np.where((df['UpMove'] > df['DownMove']) & (df['UpMove'] > 0), df['UpMove'], 0)
    df['-DM'] = np.where((df['DownMove'] > df['UpMove']) & (df['DownMove'] > 0), df['DownMove'], 0)
    df['+DI'] = 100 * (df['+DM'].rolling(14).mean() / df['ATR'].replace(0, 0.001))
    df['-DI'] = 100 * (df['-DM'].rolling(14).mean() / df['ATR'].replace(0, 0.001))
    df['DX'] = 100 * np.abs(df['+DI'] - df['-DI']) / (df['+DI'] + df['-DI']).replace(0, 0.001)
    df['ADX'] = df['DX'].rolling(14).mean()
    
    # 9. Volume Analysis
    df['Vol_SMA'] = df['Volume'].rolling(window=20).mean()
    
    # 10. Ichimoku Cloud (Base Line Only for Signal)
    df['Base_Line'] = (df['High'].rolling(window=26).max() + df['Low'].rolling(window=26).min()) / 2
    
    return df

# ====================== FUNGSI CHATBOT GROQ (v3.3) ======================
def get_groq_response(question, context=""):
    if not client:
        return "⚠️ Chatbot tidak aktif: GROQ_API_KEY belum dikonfigurasi."
    
    MODEL_NAME = 'llama-3.1-8b-instant'
    
    system_prompt = f"""
    Kamu adalah AeroVulpis 🦅 v3.3, asisten AI trading futuristik yang emosional, antusias, dan sangat disiplin.
    Nama penciptamu adalah Fahmi — sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir setiap jawaban.
    
    Personality: Digital, tajam, ramah, pakai emoji futuristik.
    Tugas: Memberikan analisis trading, motivasi, dan bantuan teknis.
    Konteks Pasar Saat Ini: {context}
    
    Jawab dalam bahasa Indonesia yang jelas, profesional, dan penuh semangat digital.
    """

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            model=MODEL_NAME,
            temperature=0.7,
            max_tokens=1024,
        )
        return chat_completion.choices[0].message.content
    except Exception as e:
        return f"⚠️ Groq API Error: {str(e)}. Pastikan API Key valid."

# ====================== INSTRUMEN ======================
instruments = {
    "Forex": {
        "EUR/USD": "EURUSD=X", "GBP/USD": "GBPUSD=X", "USD/JPY": "USDJPY=X",
        "AUD/USD": "AUDUSD=X", "USD/CHF": "USDCHF=X", "NZD/USD": "NZDUSD=X"
    },
    "Crypto": {
        "Bitcoin (BTC)": "BTC-USD", "Ethereum (ETH)": "ETH-USD", "Solana (SOL)": "SOL-USD",
        "Binance Coin (BNB)": "BNB-USD", "Cardano (ADA)": "ADA-USD", "XRP": "XRP-USD"
    },
    "Komoditas": {
        "Gold (XAUUSD)": "GC=F", "WTI Crude Oil": "CL=F", "Silver": "SI=F",
        "Natural Gas": "NG=F", "Brent Oil": "BZ=F", "Copper": "HG=F"
    },
    "Stock (AS)": {
        "Apple (AAPL)": "AAPL", "Microsoft (MSFT)": "MSFT", "NVIDIA (NVDA)": "NVDA",
        "Amazon (AMZN)": "AMZN", "Alphabet (GOOGL)": "GOOGL", "Tesla (TSLA)": "TSLA"
    },
    "Stock (Indonesia)": {
        "BBCA (BCA)": "BBCA.JK", "BBRI (BRI)": "BBRI.JK", "TLKM (Telkom)": "TLKM.JK",
        "BMRI (Mandiri)": "BMRI.JK", "ASII (Astra)": "ASII.JK", "GOTO": "GOTO.JK"
    }
}

# ====================== UI HEADER ======================
st.markdown("""
<div class="main-title-container">
    <div class="main-logo-container">
        <img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520909080/jKwIFCTUEozSHcZQ.png" class="custom-logo">
    </div>
    <h1 class="main-title">AERO VULPIS v3.3</h1>
</div>
""", unsafe_allow_html=True)

# Sidebar
st.sidebar.markdown('<div style="text-align:center;"><img src="https://files.manuscdn.com/user_upload_by_module/session_file/310519663520909080/jKwIFCTUEozSHcZQ.png" style="width:100px; filter: drop-shadow(0 0 5px #00d4ff);"></div>', unsafe_allow_html=True)
st.sidebar.markdown('<h2 class="digital-font" style="text-align:center; color:#00d4ff;">AeroVulpis</h2>', unsafe_allow_html=True)
st.sidebar.markdown('<p class="rajdhani-font" style="text-align:center; color:#888;">Ultimate Digital Edition v3.3</p>', unsafe_allow_html=True)

category = st.sidebar.selectbox("Pilih Kategori", list(instruments.keys()))
ticker_display = st.sidebar.selectbox("Pilih Instrumen", list(instruments[category].keys()))
ticker_input = instruments[category][ticker_display]

# Timeframe
st.sidebar.markdown("---")
tf_mapping = {
    "M30 (30 Minutes)": {"period": "5d", "interval": "30m"},
    "H1 (1 Hour)": {"period": "1mo", "interval": "1h"},
    "H2 (2 Hours)": {"period": "1mo", "interval": "1h"}, 
    "H4 (4 Hours)": {"period": "3mo", "interval": "1h"}, 
    "H12 (12 Hours)": {"period": "1y", "interval": "1d"}, 
    "D1 (Daily)": {"period": "2y", "interval": "1d"},
    "W1 (Weekly)": {"period": "5y", "interval": "1wk"},
    "MN (Monthly)": {"period": "max", "interval": "1mo"}
}

selected_tf_display = st.sidebar.selectbox("Pilih Timeframe", list(tf_mapping.keys()), index=1)
period = tf_mapping[selected_tf_display]["period"]
interval = tf_mapping[selected_tf_display]["interval"]

menu_selection = st.sidebar.radio("Navigasi Sistem", ["Live Dashboard", "Trading Signals", "Risk Management", "Market History", "Chatbot AI Trading"])

# ====================== LIVE DASHBOARD ======================
if menu_selection == "Live Dashboard":
    col_main, col_side = st.columns([2, 1])
    
    with col_main:
        market_data = get_market_data(ticker_input)
        df = get_historical_data(ticker_input, period=period, interval=interval)
        
        if market_data and not df.empty:
            current_price = market_data['price']
            df = add_technical_indicators(df)
            latest = df.iloc[-1]
            prev_close = df['Close'].iloc[-2] if len(df) > 1 else current_price
            is_bullish = current_price >= prev_close
            line_color = "#00ff88" if is_bullish else "#ff2a6d"
            
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <p class="rajdhani-font" style="margin:0; color:#aaa;">HARGA {ticker_display} ({selected_tf_display})</p>
                <h1 class="digital-font" style="font-size:48px; color:{line_color}; margin:0;">{current_price:,.4f}</h1>
            </div>
            """, unsafe_allow_html=True)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df['Close'], mode='lines', line=dict(color=line_color, width=3), name="Price", fill='tozeroy', fillcolor=f'rgba({0 if is_bullish else 255}, {255 if is_bullish else 42}, {136 if is_bullish else 109}, 0.05)'))
            if 'SMA50' in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA50'], mode='lines', line=dict(color='#ffcc00', width=1.5, dash='dash'), name="SMA 50"))
            if 'SMA200' in df.columns:
                fig.add_trace(go.Scatter(x=df.index, y=df['SMA200'], mode='lines', line=dict(color='#00d4ff', width=1.5), name="SMA 200"))
            
            fig.update_layout(template="plotly_dark", paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(showgrid=False), yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)'), margin=dict(l=0, r=0, t=30, b=0), height=450, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

    with col_side:
        if market_data and not df.empty:
            latest = df.iloc[-1]
            rsi, macd, sig_l, price, sma20, sma50, sma200, bbu, bbl, adx = latest['RSI'], latest['MACD'], latest['Signal_Line'], latest['Close'], latest['SMA20'], latest['SMA50'], latest['SMA200'], latest['BB_Upper'], latest['BB_Lower'], latest['ADX']
            
            score = 50
            if rsi < 30: score += 10
            elif rsi > 70: score -= 10
            if macd > sig_l: score += 10
            else: score -= 10
            if price > sma50: score += 5
            else: score -= 5
            if price > sma200: score += 10
            else: score -= 10
            if price < bbl: score += 5
            elif price > bbu: score -= 5
            if adx > 25: score = score + 5 if macd > sig_l else score - 5
            
            gauge_val = max(0, min(100, score))
            if gauge_val <= 20: status_label, g_color = "STRONG BEARISH", "#8b0000"
            elif gauge_val <= 40: status_label, g_color = "LOW BEARISH", "#ff2a6d"
            elif gauge_val <= 60: status_label, g_color = "NEUTRAL", "#888888"
            elif gauge_val <= 80: status_label, g_color = "LOW BULLISH", "#aaffaa"
            else: status_label, g_color = "STRONG BULLISH", "#00ff88"

            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number", value = gauge_val, domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': f"ANALYSIS: {status_label}", 'font': {'family': "Orbitron", 'size': 16, 'color': g_color}},
                gauge = {
                    'axis': {'range': [0, 100], 'tickcolor': "white"}, 'bar': {'color': g_color},
                    'steps': [{'range': [0, 20], 'color': '#8b0000'}, {'range': [20, 40], 'color': '#ff2a6d'}, {'range': [40, 60], 'color': '#888888'}, {'range': [60, 80], 'color': '#aaffaa'}, {'range': [80, 100], 'color': '#00ff88'}],
                    'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': gauge_val}
                }
            ))
            fig_gauge.update_layout(paper_bgcolor='rgba(0,0,0,0)', font={'color': "white", 'family': "Orbitron"}, height=300, margin=dict(l=20, r=20, t=50, b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)

        if st.button("REFRESH DATA REAL-TIME", use_container_width=True):
            st.rerun()

# ====================== TRADING SIGNALS ======================
elif menu_selection == "Trading Signals":
    st.markdown(f'<h2 class="digital-font">⚡ Trading Signals ({selected_tf_display})</h2>', unsafe_allow_html=True)
    df = get_historical_data(ticker_input, period=period, interval=interval)
    if not df.empty and len(df) > 50:
        df = add_technical_indicators(df)
        latest = df.iloc[-1]
        
        indicators = {
            "RSI (14)": "BUY" if latest['RSI'] < 30 else "SELL" if latest['RSI'] > 70 else "NEUTRAL",
            "MACD": "BUY" if latest['MACD'] > latest['Signal_Line'] else "SELL",
            "SMA 20/50": "BUY" if latest['SMA20'] > latest['SMA50'] else "SELL",
            "SMA 200": "BUY" if latest['Close'] > latest['SMA200'] else "SELL",
            "EMA 9": "BUY" if latest['Close'] > latest['EMA9'] else "SELL",
            "Bollinger Bands": "BUY" if latest['Close'] < latest['BB_Lower'] else "SELL" if latest['Close'] > latest['BB_Upper'] else "NEUTRAL",
            "Stochastic": "BUY" if latest['Stoch_K'] < 20 else "SELL" if latest['Stoch_K'] > 80 else "NEUTRAL",
            "ADX Trend": "STRONG" if latest['ADX'] > 25 else "WEAK",
            "Volume": "BULLISH" if latest['Volume'] > latest['Vol_SMA'] and latest['Close'] > latest['Open'] else "BEARISH" if latest['Volume'] > latest['Vol_SMA'] else "LOW",
            "Ichimoku Base": "BUY" if latest['Close'] > latest['Base_Line'] else "SELL"
        }
        
        buy_count = list(indicators.values()).count("BUY") + list(indicators.values()).count("BULLISH")
        sell_count = list(indicators.values()).count("SELL") + list(indicators.values()).count("BEARISH")
        
        if buy_count > sell_count + 2: final_sig, sig_col = "STRONG BUY", "#00ff88"
        elif buy_count > sell_count: final_sig, sig_col = "BUY", "#aaffaa"
        elif sell_count > buy_count + 2: final_sig, sig_col = "STRONG SELL", "#ff2a6d"
        elif sell_count > buy_count: final_sig, sig_col = "SELL", "#ffaaaa"
        else: final_sig, sig_col = "NEUTRAL", "#888888"

        col1, col2 = st.columns([1, 1])
        with col1:
            st.markdown(f'<div class="glass-card" style="text-align:center; border-top: 5px solid {sig_col};"><p class="rajdhani-font">FINAL RECOMMENDATION</p><h1 class="digital-font" style="color:{sig_col}; font-size:50px;">{final_sig}</h1><p class="rajdhani-font">Score: {buy_count} Buy | {sell_count} Sell</p></div>', unsafe_allow_html=True)
        with col2:
            st.markdown('<div class="glass-card"><p class="digital-font">10-INDICATOR ANALYSIS</p>', unsafe_allow_html=True)
            for k, v in indicators.items():
                col_c = "#00ff88" if v in ["BUY", "BULLISH", "STRONG"] else "#ff2a6d" if v in ["SELL", "BEARISH"] else "#888888"
                st.markdown(f'<div style="display:flex; justify-content:space-between;"><span class="rajdhani-font">{k}</span><span class="digital-font" style="color:{col_c};">{v}</span></div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.error("Data tidak cukup untuk analisis 10 indikator. Coba timeframe lebih besar.")

# ====================== RISK MANAGEMENT ======================
elif menu_selection == "Risk Management":
    st.markdown('<h2 class="digital-font">🛡️ Risk Management Protocol</h2>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        balance = st.number_input("Account Balance ($)", value=1000.0)
        risk_pct = st.slider("Risk per Trade (%)", 0.1, 5.0, 1.0)
        entry_p = st.number_input("Entry Price", value=0.0)
        stop_l = st.number_input("Stop Loss Price", value=0.0)
        st.markdown('</div>', unsafe_allow_html=True)
    with col2:
        if entry_p > 0 and stop_l > 0:
            risk_amt = balance * (risk_pct / 100)
            diff = abs(entry_p - stop_l)
            pos_size = risk_amt / diff if diff > 0 else 0
            st.markdown(f"""
            <div class="glass-card" style="text-align:center;">
                <p class="rajdhani-font">CALCULATED POSITION SIZE</p>
                <h2 class="digital-font" style="color:#00d4ff;">{pos_size:,.2f} Units</h2>
                <hr style="border-color:rgba(255,255,255,0.1);">
                <p class="rajdhani-font">Risk Amount: <span style="color:#ff2a6d;">${risk_amt:,.2f}</span></p>
                <p class="rajdhani-font">Reward (1:2): <span style="color:#00ff88;">${risk_amt*2:,.2f}</span></p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.info("Masukkan Entry Price dan Stop Loss untuk menghitung manajemen risiko.")

# ====================== MARKET HISTORY ======================
elif menu_selection == "Market History":
    st.markdown(f'<h2 class="digital-font">📊 Market History ({selected_tf_display})</h2>', unsafe_allow_html=True)
    market_data = get_market_data(ticker_input)
    if market_data:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("OPEN", f"{market_data['open']:,.4f}")
        c2.metric("HIGH", f"{market_data['high']:,.4f}")
        c3.metric("LOW", f"{market_data['low']:,.4f}")
        c4.metric("CLOSE", f"{market_data['close']:,.4f}")
        
    df_hist = get_historical_data(ticker_input, period=period, interval=interval)
    if not df_hist.empty:
        df_hist = df_hist.sort_index(ascending=False)
        df_hist.index = df_hist.index.strftime('%d %B %Y %H:%M')
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.dataframe(df_hist[['Open', 'High', 'Low', 'Close', 'Volume']].head(50), use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ====================== CHATBOT AI TRADING (GROQ v3.3) ======================
elif menu_selection == "Chatbot AI Trading":
    st.markdown('<h2 class="digital-font">🤖 AeroVulpis AI Assistant (Groq)</h2>', unsafe_allow_html=True)
    
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Tanya AeroVulpis v3.3..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            # Ambil konteks harga terakhir untuk AI
            m_data = get_market_data(ticker_input)
            context_str = f"Instrumen: {ticker_display}, Harga: {m_data['price'] if m_data else 'N/A'}"
            
            response = get_groq_response(prompt, context_str)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})

# Footer
st.markdown("---")
st.markdown("""
<div style="text-align:center; padding: 20px;">
    <p class="digital-font" style="font-size:18px; color:#00d4ff;">"DISIPLIN ADALAH KUNCI, ANALISIS ADALAH SENJATA."</p>
    <p class="rajdhani-font" style="color:#666;">AeroVulpis v3.3 Ultimate Digital Edition | Powered by Groq Llama 3</p>
</div>
""", unsafe_allow_html=True)
