import streamlit as st
from supabase import create_client, Client

def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Database connection error: {e}")
        st.stop()

# Ініціалізація глобального клієнта, якщо треба
supabase = init_supabase()
