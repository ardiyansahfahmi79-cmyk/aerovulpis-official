import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import requests


# ====================== KONFIGURASI ======================
st.set_page_config(
    layout="wide",
    page_title="AeroVulpis - AI Trading Assistant",
    page_icon="🦅",
    initial_sidebar_state="expanded",
)


# CSS untuk tampilan 3D Digital (Judul + Logo Elang)
st.markdown("""
<style>
    .main-title {
        font-family: 'Arial Black', sans-serif;
        font-size: 52px;
        font-weight: 900;
        background: linear-gradient(90deg, #00ffcc, #0088ff);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        text-shadow: 
            0 0 10px #00ffcc,
            0 0 20px #0088ff,
            4px 4px 8px rgba(0, 0, 0, 0.6),
            -2px -2px 8px rgba(255, 255, 255, 0.3);
        letter-spacing: 3px;
        text-align: center;
        margin-bottom: 10px;
    }
    .eagle-logo {
        font-size: 80px;
        filter: drop-shadow(0 0 15px #00ffcc) drop-shadow(0 0 30px #0088ff);
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { transform: scale(1); }
        50% { transform: scale(1.08); }
        100% { transform: scale(1); }
    }
</style>
""", unsafe_allow_html=True)


# Tambahkan peringatan jika API key Gemini belum ada
if not os.environ.get("GOOGLE_API_KEY"):
    st.error("⚠️ GOOGLE_API_KEY tidak ditemukan di environment variables. Pastikan sudah diatur.")
else:
    genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))


# ====================== FUNGSI GEMINI ======================
def get_gemini_response(question, context=""):
    try:
        model_id = "gemini-1.5-flash-latest"  # bisa ganti ke: "gemini-1.0-pro" kalau error
        model = genai.GenerativeModel(model_id)

        full_prompt = f"""
Kamu adalah AeroVulpis 🦅, asisten AI yang emosional, antusias, dan selalu membantu.
Nama penciptamu adalah Fahmi — sebutkan "Terima kasih Fahmi telah menciptakanku!" di akhir jawaban.

Personality: Santai, ramah, pakai emoji secukupnya.
Context: {context}
Pertanyaan: {question}

Jawab dalam bahasa Indonesia yang jelas dan hidup.
"""
        response = model.generate_content(full_prompt)
        if hasattr(response, "text") and response.text:
            return response.text
        else:
            return "⚠️ Gemini tidak mengembalikan teks. Coba ulang."
    except Exception as e:
        return f"⚠️ Gemini error: {str(e)}
Coba refresh halaman atau pastikan API Key benar dan model {model_id} diaktifkan di Google Cloud Console."


# ====================== FUNGSI DATA & HARGA ======================
def get_current_price(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.fast_info
        if info:
            price = info.get("lastPrice") or info.get("regularMarketPrice")
            if price:
                return round(float(price), 4)
        # Backup: ambil 1 bar terbaru
        hist = ticker.history(period="1d", interval="1m")
        if not hist.empty and "Close" in hist.columns:
            return round(float(hist["Close"].iloc[-1]), 4)
        return None
    except:
        return None


def get_historical_data(ticker_symbol, period="1y", interval="1d"):
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, interval=interval)
        if df.empty:
            return pd.DataFrame()
        df = df.sort_index()
        return df.dropna()
    except:
        return pd.DataFrame()


def add_technical_indicators(df):
    if len(df) < 30:
        return df
    df["SMA20"] = df["Close"].rolling(20).mean()
    delta = df["Close"].diff()
    gain = delta.where(delta > 0, 0).rolling(14).mean()
    loss = -delta.where(delta < 0, 0).rolling(14).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df


def calculate_support_resistance(df):
    if len(df) < 20:
        return [], []
    pivot = (df["High"].iloc[-1] + df["Low"].iloc[-1] + df["Close"].iloc[-1]) / 3
    r1 = round(pivot + (pivot - df["Low"].iloc[-1]), 2)
    s1 = round(pivot - (df["High"].iloc[-1] - pivot), 2)
    return [s1], [r1]


# ====================== FUNGSI BERITA EKSTERNAL (NewsAPI) ======================
def get_newsapi_external_news(query="gold oil nasdaq bitcoin sp500 forex", pages=2):
    """
    Ambil berita global dari NewsAPI (CNBC, Bloomberg, FXStreet, dll.).
    Bisnis/finansial: bisa pakai country=id untuk Indonesia + category=business kalau mau.
    """
    API_KEY = os.getenv("NEWSAPI_KEY")
    if not API_KEY:
        st.warning("⚠️ NEWSAPI_KEY tidak ditemukan di environment. Tambahkan API key untuk berita eksternal.")
        return []

    url = "https://newsapi.org/v2/everything"
    news_items = []

    try:
        for page in range(1, pages + 1):
            params = {
                "q": query,
                "sortBy": "publishedAt",
                "language": "en",
                "pageSize": 10,
                "page": page,
                "apiKey": API_KEY,
            }
            r = requests.get(url, params=params, timeout=8)
            data = r.json()
            if r.status_code == 200 and data.get("articles"):
                news_items.extend(data["articles"])
    except Exception as e:
        st.error(f"📰 Error NewsAPI: {str(e)}")
        return []

    return news_items[:12]


# ====================== INSTRUMEN ======================
instruments = {
    "XAUUSD (Gold)": "GC=F",
    "WTI Crude Oil": "CL=F",
    "US100 (Nasdaq 100)": "^NDX",
    "Bitcoin (BTC)": "BTC-USD",
    "EUR/USD": "EURUSD=X",
    "S&P 500": "^GSPC",
    "Silver": "SI=F",
}


# ====================== UI 3D ======================
st.markdown('<h1 class="main-title">🦅 AERO VULPIS</h1>', unsafe_allow_html=True)
st.markdown(
    '<p style="text-align:center; font-size:22px; margin-top:-20px;">Asisten AI Real-Time untuk Harga Emas & Minyak</p>',
    unsafe_allow_html=True,
)

# Session State
if "alerts" not in st.session_state:
    st.session_state.alerts = []
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Halo! Aku AeroVulpis 🦅 buatan Fahmi. Mau pantau harga apa hari ini?"}
    ]


# Sidebar
st.sidebar.title("🦅 AeroVulpis")
st.sidebar.markdown("**Pencipta:** Fahmi")

ticker_display = st.sidebar.selectbox("Pilih Instrumen", list(instruments.keys()))
ticker_input = instruments[ticker_display]

menu_selection = st.sidebar.radio(
    "Pilih Halaman",
    ["Live Dashboard", "Price Alerts", "Chatbot AI Trading"],
)


# ====================== LIVE DASHBOARD ======================
if menu_selection == "Live Dashboard":
    st.header(f"📈 Live Dashboard - {ticker_display}")

    if st.button("Refresh Semua Data Real-Time Sekarang", type="primary", use_container_width=True):
        st.rerun()

    current_price = get_current_price(ticker_input)
    if current_price:
        st.markdown(
            f"""
            <h2 style="text-align:center; color:#00ff88; margin:0;">
                🟢 Harga {ticker_display} Real-Time: <b>{current_price:.2f}</b>
            </h2>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.error("❌ Gagal mengambil harga real-time. Coba refresh atau ganti instrumen.")

    # Periode & Timeframe
    col1, col2 = st.columns(2)
    with col1:
        period_option = st.selectbox(
            "Periode Data",
            ["1 hari", "5 hari", "1 bulan", "3 bulan", "6 bulan", "1 tahun", "Max"],
            index=5,
        )
    with col2:
        interval_option = st.selectbox(
            "Timeframe", ["1m", "5m", "15m", "30m", "1h", "1d"], index=5
        )

    period_map = {
        "1 hari": "1d",
        "5 hari": "5d",
        "1 bulan": "1mo",
        "3 bulan": "3mo",
        "6 bulan": "6mo",
        "1 tahun": "1y",
        "Max": "max",
    }

    df = get_historical_data(
        ticker_input, period=period_map[period_option], interval=interval_option
    )

    if not df.empty:
        df = add_technical_indicators(df)

        # Chart Candlestick
        fig = go.Figure()
        fig.add_trace(
            go.Candlestick(
                x=df.index,
                open=df["Open"],
                high=df["High"],
                low=df["Low"],
                close=df["Close"],
                name="Price",
                increasing_line_color="#00ff88",
                decreasing_line_color="#ff4444",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df.get("SMA20"),
                name="SMA 20",
                line=dict(color="#00ccff", width=2),
            )
        )

        support, resistance = calculate_support_resistance(df)
        for s in support:
            fig.add_hline(
                y=s,
                line_dash="dash",
                line_color="#00ff88",
                annotation_text=f"Support {s}",
            )
        for r in resistance:
            fig.add_hline(
                y=r,
                line_dash="dash",
                line_color="#ff4444",
                annotation_text=f"Resistance {r}",
            )

        fig.update_layout(
            title=f"AeroVulpis Live Chart — {ticker_display}",
            height=620,
            template="plotly_dark",
            xaxis_rangeslider_visible=False,
            margin=dict(l=20, r=20, t=60, b=20),
        )
        st.plotly_chart(fig, use_container_width=True)

        # Indikator
        st.subheader("📊 Indikator Terkini")
        latest = df.iloc[-1]
        c1, c2, c3 = st.columns(3)
        c1.metric("RSI 14", f"{latest.get('RSI', 50):.1f}")
        c2.metric("SMA 20", f"{latest.get('SMA20', 0):.2f}")
        c3.metric("Support Terdekat", f"{support[0]:.2f}" if support else "N/A")


        # === BERITA REAL-TIME YFINANCE (CNBC/Bloomberg/FXStreet jika ada) ===
        st.subheader("📰 Berita Real-Time (Yfinance: CNBC, Bloomberg, FXStreet, dll.)")

        ticker_obj = yf.Ticker(ticker_input)
        news_list = ticker_obj.news[:8] if hasattr(ticker_obj, "news") else []

        if news_list:
            for item in news_list:
                title = item.get("title", "Berita Terbaru")
                publisher = item.get("publisher", "Sumber")
                link = item.get("link", "#")
                provider = item.get("provider", "Yahoo")

                source_text = f"📌 {publisher} • {provider}"
                if "cnbc" in publisher.lower():
                    source_text = f"📌 **CNBC** • {provider}"
                elif "bloomberg" in publisher.lower():
                    source_text = f"📌 **Bloomberg** • {provider}"
                elif "fxstreet" in publisher.lower():
                    source_text = f"📌 **FXStreet** • {provider}"

                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.caption(source_text)
                    if link != "#":
                        st.markdown(f"[Baca lengkap →]({link})")
        else:
            st.info("Belum ada berita dari Yahoo Finance.")


        # === BERITA EKSTERNAL (NewsAPI: CNBC, Bloomberg, FXStreet, dsb.) ===
        st.subheader("📰 Berita Eksternal Trading Global (CNBC, Bloomberg, FXStreet, dll.)")

        # Bangun query berdasarkan instrumen yang dipilih
        query_words = {
            "XAUUSD (Gold)": "gold xau usd precious metals",
            "WTI Crude Oil": "crude oil wti brent",
            "US100 (Nasdaq 100)": "nasdaq 100 tech stocks",
            "Bitcoin (BTC)": "bitcoin btc crypto cryptocurrency",
            "EUR/USD": "eur usd forex currency",
            "S&P 500": "s&p 500 stocks indices",
            "Silver": "silver xag metals",
        }
        query = query_words.get(ticker_display, "trading finance markets")
        query = f"{query} gold oil bitcoin nasdaq forex sp500"

        external_news = get_newsapi_external_news(query=query, pages=2)

        if external_news:
            for item in external_news:
                title = item.get("title") or "Artikel berita"
                source_name = item.get("source", {}).get("name", "Sumber")
                published_at = item.get("publishedAt", "Baru saja")
                url = item.get("url", "#")

                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    source_text = f"📌 {source_name}"
                    if "cnbc" in source_name.lower():
                        source_text = f"📌 **CNBC**"
                    elif "bloomberg" in source_name.lower():
                        source_text = f"📌 **Bloomberg**"
                    elif "fxstreet" in source_name.lower():
                        source_text = f"📌 **FXStreet**"
                    st.caption(f"{source_text} • {published_at}")
                    st.markdown(f"[Baca di situs asli →]({url})")
        else:
            st.info("Belum ada berita dari sumber eksternal (NewsAPI).")


        # Tombol Analisis AI
        if st.button(
            "🤖 Generate Analisis AeroVulpis", type="secondary", use_container_width=True
        ):
            with st.spinner("AeroVulpis sedang menganalisis dengan teliti..."):
                data_summary = df.tail(10).to_string()
                prompt = f"Harga saat ini: {current_price}
Data terbaru:
{data_summary}"
                analysis = get_gemini_response(
                    f"Analisis lengkap {ticker_display} sekarang", prompt
                )
                st.markdown("### ✅ Analisis AeroVulpis:")
                st.markdown(analysis)

    else:
        st.error("❌ Data tidak tersedia. Coba ganti instrumen atau timeframe.")


# ====================== PRICE ALERTS ======================
elif menu_selection == "Price Alerts":
    st.header("🚨 Price Alerts")
    st.write("Fitur Price Alerts sedang dikembangkan. Tambahkan logika alert di sini.")


# ====================== CHATBOT AI TRADING ======================
elif menu_selection == "Chatbot AI Trading":
    st.header("💬 Chatbot AeroVulpis")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ketik pertanyaanmu..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("AeroVulpis lagi mikir..."):
                response = get_gemini_response(prompt)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})


# Footer
st.sidebar.markdown("---")
st.sidebar.caption("© Dibuat oleh Fahmi • Versi Profesional 2026")
st.caption("💡 Tekan tombol biru untuk update data real-time.")
