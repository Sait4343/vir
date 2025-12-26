import streamlit as st
from supabase import create_client, Client

# Ініціалізація клієнта Supabase
# Використовуємо st.cache_resource, щоб не перепідключатися при кожному перезавантаженні
@st.cache_resource
def init_supabase() -> Client:
    try:
        SUPABASE_URL = st.secrets["https://honujwuyjppukqotmfiv.supabase.co"]
        SUPABASE_KEY = st.secrets["eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhvbnVqd3V5anBwdWtxb3RtZml2Iiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2NTEwNzc0MiwiZXhwIjoyMDgwNjgzNzQyfQ.yEw3GShJml2OjtuvivrJufe634vk9YVXceOul21wIiw"]
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        st.error(f"CRITICAL ERROR: Database Connection Failed. {e}")
        st.stop()

# Створюємо глобальний екземпляр клієнта
supabase = init_supabase()
