import streamlit as st
from supabase import create_client, Client

# Ініціалізація клієнта Supabase
# Використовуємо st.cache_resource, щоб не перепідключатися при кожному перезавантаженні
@st.cache_resource
def init_supabase() -> Client:
    try:
        # Тут ми беремо ключі за ІМЕНЕМ змінної у файлі secrets.toml
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"CRITICAL ERROR: Database Connection Failed. {e}")
        st.stop()

# Створюємо глобальний екземпляр клієнта
supabase = init_supabase()
