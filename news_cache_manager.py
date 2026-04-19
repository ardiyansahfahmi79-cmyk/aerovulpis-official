import streamlit as st
from datetime import datetime, timedelta
import pytz

def initialize_news_cache():
    """Inisialisasi cache untuk rotasi berita setiap 20 menit"""
    if "news_cache" not in st.session_state:
        st.session_state.news_cache = {
            "articles": [],
            "last_update": None,
            "update_interval": 1200  # 20 menit dalam detik
        }

def should_update_news():
    """Cek apakah berita perlu diperbarui (setiap 20 menit)"""
    initialize_news_cache()
    
    if st.session_state.news_cache["last_update"] is None:
        return True
    
    now = datetime.now(pytz.timezone('Asia/Jakarta'))
    last_update = st.session_state.news_cache["last_update"]
    
    # Jika perbedaan waktu lebih dari 20 menit, update
    if (now - last_update).total_seconds() >= st.session_state.news_cache["update_interval"]:
        return True
    
    return False

def rotate_news_articles(articles, max_articles=10):
    """
    Rotasi berita: hapus 1 berita lama, tambah 1 berita baru
    Menjaga total 10 berita
    """
    initialize_news_cache()
    
    if should_update_news():
        # Hapus 1 berita paling lama (dari belakang)
        if len(st.session_state.news_cache["articles"]) >= max_articles:
            st.session_state.news_cache["articles"].pop()
        
        # Tambah berita baru di depan
        if articles:
            st.session_state.news_cache["articles"].insert(0, articles[0])
        
        # Update waktu terakhir
        st.session_state.news_cache["last_update"] = datetime.now(pytz.timezone('Asia/Jakarta'))
    
    return st.session_state.news_cache["articles"][:max_articles]
