import streamlit as st
from supabase import create_client, Client

# Використовуємо кешування, щоб не перепідключатися при кожному кліку
@st.cache_resource
def init_supabase() -> Client:
    try:
        # Отримуємо ключі з st.secrets (налаштовані у .streamlit/secrets.toml або в хмарі)
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"CRITICAL ERROR: Database Connection Failed. {e}")
        st.stop()

# Створюємо глобальний об'єкт, який імпортують інші файли
supabase = init_supabase()
