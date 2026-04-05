
import streamlit as st
import google.generativeai as genai
import os
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Konfigurasi API Gemini
# Pastikan GOOGLE_API_KEY telah diatur sebagai environment variable
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

# Fungsi untuk berinteraksi dengan Gemini AI
def get_gemini_response(question):
    model = genai.GenerativeModel('gemini-pro')
    response = model.generate_content(question)
    return response.text

# Fungsi untuk mendapatkan data harga XAUUSD
def get_xauusd_data(period="1y"):
    ticker = yf.Ticker("GC=F") # GC=F adalah simbol ticker untuk Gold Futures
    hist = ticker.history(period=period)
    return hist

# Fungsi untuk membuat candlestick chart
def create_candlestick_chart(df):
    fig = go.Figure(data=[
        go.Candlestick(
            x=df.index,
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close']
        )
    ])
    fig.update_layout(
        title='Grafik Harga XAUUSD (Gold Futures)',
        xaxis_title='Tanggal',
        yaxis_title='Harga (USD)',
        xaxis_rangeslider_visible=False
    )
    return fig

# Tampilan aplikasi Streamlit
st.set_page_config(layout="wide", page_title="AeroVulpis - AI Trading Assistant")

st.title("🦅 AeroVulpis - AI Trading Assistant")

# Sidebar untuk navigasi
st.sidebar.title("Navigasi")
menu_selection = st.sidebar.radio("Pilih Halaman", ["Dashboard XAUUSD", "Chatbot AI Trading"])

if menu_selection == "Dashboard XAUUSD":
    st.header("Dashboard Pemantau Harga XAUUSD")

    # Pilihan periode data
    period_option = st.selectbox(
        "Pilih Periode Data",
        ["1 hari", "5 hari", "1 bulan", "3 bulan", "6 bulan", "1 tahun", "5 tahun", "Max"],
        index=5 # Default 1 tahun
    )

    period_map = {
        "1 hari": "1d",
        "5 hari": "5d",
        "1 bulan": "1mo",
        "3 bulan": "3mo",
        "6 bulan": "6mo",
        "1 tahun": "1y",
        "5 tahun": "5y",
        "Max": "max"
    }
    
    data_period = period_map[period_option]

    # Mendapatkan dan menampilkan data
    xauusd_data = get_xauusd_data(period=data_period)

    if not xauusd_data.empty:
        st.subheader(f"Data Historis XAUUSD ({period_option})")
        st.dataframe(xauusd_data.tail())

        st.subheader("Grafik Candlestick XAUUSD")
        st.plotly_chart(create_candlestick_chart(xauusd_data), use_container_width=True)

        # Informasi harga terbaru
        latest_price = xauusd_data['Close'].iloc[-1]
        previous_close = xauusd_data['Close'].iloc[-2] if len(xauusd_data) > 1 else latest_price
        change = latest_price - previous_close
        change_percent = (change / previous_close) * 100 if previous_close != 0 else 0

        st.markdown(f"### Harga Penutupan Terbaru: **{latest_price:.2f} USD**")
        if change >= 0:
            st.markdown(f"Perubahan dari penutupan sebelumnya: <span style='color:green;'>+{change:.2f} ({change_percent:.2f}%)</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"Perubahan dari penutupan sebelumnya: <span style='color:red;'>{change:.2f} ({change_percent:.2f}%)</span>", unsafe_allow_html=True)

    else:
        st.warning("Tidak dapat mengambil data XAUUSD. Silakan coba lagi nanti.")

elif menu_selection == "Chatbot AI Trading":
    st.header("Chatbot AI Trading (Didukung Gemini AI)")
    st.write("Ajukan pertanyaan seputar trading, analisis pasar, atau informasi XAUUSD.")

    # Inisialisasi riwayat chat
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Tampilkan riwayat chat
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Input chat dari pengguna
    if prompt := st.chat_input("Ketik pertanyaan Anda di sini..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Memikirkan jawaban..."):
                response = get_gemini_response(prompt)
                st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})
