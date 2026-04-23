import streamlit as st
from datetime import datetime, timedelta
import pytz

def initialize_news_cache():
    """Inisialisasi cache untuk rotasi berita setiap 1 jam"""
    if "news_cache" not in st.session_state:
        st.session_state.news_cache = {
            "articles": {}, # Menggunakan dict untuk kategori: {category: [articles]}
            "last_update": {}, # {category: timestamp}
            "update_interval": 3600  # 1 jam dalam detik
        }

def should_update_news(category="General"):
    """Cek apakah berita kategori tertentu perlu diperbarui (setiap 1 jam)"""
    initialize_news_cache()
    
    last_update = st.session_state.news_cache["last_update"].get(category)
    if last_update is None:
        return True
    
    now = datetime.now(pytz.timezone('Asia/Jakarta'))
    
    # Jika perbedaan waktu lebih dari 1 jam, update
    if (now - last_update).total_seconds() >= st.session_state.news_cache["update_interval"]:
        return True
    
    return False

def get_cached_news(category="General"):
    """Mengambil berita dari cache untuk kategori tertentu"""
    initialize_news_cache()
    return st.session_state.news_cache["articles"].get(category, [])

def update_news_cache(category, articles):
    """Memperbarui cache berita untuk kategori tertentu"""
    initialize_news_cache()
    st.session_state.news_cache["articles"][category] = articles
    st.session_state.news_cache["last_update"][category] = datetime.now(pytz.timezone('Asia/Jakarta'))
