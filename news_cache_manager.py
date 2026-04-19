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
    Rotasi berita: Memastikan selalu ada 10 berita.
    Jika cache kosong atau perlu update, isi dengan berita terbaru.
    """
    initialize_news_cache()
    
    # Jika cache kosong, isi pertama kali dengan berita yang tersedia (hingga max_articles)
    if not st.session_state.news_cache["articles"] and articles:
        st.session_state.news_cache["articles"] = articles[:max_articles]
        st.session_state.news_cache["last_update"] = datetime.now(pytz.timezone('Asia/Jakarta'))
    
    # Jika sudah waktunya update (20 menit)
    elif should_update_news() and articles:
        # Ambil berita yang belum ada di cache untuk rotasi
        existing_urls = {a['url'] for a in st.session_state.news_cache["articles"]}
        new_articles = [a for a in articles if a['url'] not in existing_urls]
        
        if new_articles:
            # Hapus 1 berita paling lama (dari belakang)
            if len(st.session_state.news_cache["articles"]) >= max_articles:
                st.session_state.news_cache["articles"].pop()
            
            # Tambah 1 berita terbaru di depan
            st.session_state.news_cache["articles"].insert(0, new_articles[0])
        
        # Jika tidak ada berita baru yang benar-benar unik, 
        # kita tetap update listnya dari data terbaru untuk menjaga kesegaran
        elif len(articles) >= max_articles:
            st.session_state.news_cache["articles"] = articles[:max_articles]
            
        # Update waktu terakhir
        st.session_state.news_cache["last_update"] = datetime.now(pytz.timezone('Asia/Jakarta'))
    
    # Selalu pastikan kita mengembalikan tepat max_articles jika tersedia cukup banyak berita
    return st.session_state.news_cache["articles"][:max_articles]
