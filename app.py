import streamlit as st

# 1. Config (First line)
st.set_page_config(
    page_title="AI Visibility by Virshi",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Imports
from utils.auth import check_session, show_auth_page, logout
from utils.ui import render_sidebar, load_custom_css
from utils.db import supabase

# Import Pages
from views.dashboard import show_dashboard
from views.projects import show_my_projects_page
from views.keywords import show_keywords_page
from views.sources import show_sources_page
from views.competitors import show_competitors_page
from views.recommendations import show_recommendations_page
from views.history import show_history_page
from views.reports import show_reports_page
from views.faq import show_faq_page
from views.chat import show_chat_page
from views.admin import show_admin_page

# 3. Styles & Session
load_custom_css()
check_session()

# ==========================================
# ГОЛОВНА ЛОГІКА (Як у вашому робочому коді)
# ==========================================

def main():
    # 1. АВТОРИЗАЦІЯ
    if not st.session_state.get("user"):
        show_auth_page()
        return

    # 2. ОТРИМАННЯ ДАНИХ ПРОЕКТУ (Якщо ще немає в сесії)
    if not st.session_state.get("current_project"):
        try:
            # Отримуємо ID коректно (об'єкт або dict)
            usr = st.session_state["user"]
            uid = usr.id if hasattr(usr, 'id') else usr.get('id')
            
            resp = supabase.table("projects").select("*").eq("user_id", uid).execute()
            if resp.data:
                st.session_state["current_project"] = resp.data[0]
                st.rerun()
        except Exception:
            pass

    user_role = st.session_state.get("role", "user")

    # 3. ЛОГІКА ДЛЯ НОВИХ КОРИСТУВАЧІВ (НЕМАЄ ПРОЕКТУ)
    if st.session_state.get("current_project") is None and user_role not in ["admin", "super_admin"]:
        
        # Малюємо спрощений сайдбар (тільки лого і вихід), як у вашому коді
        with st.sidebar:
            st.image("https://raw.githubusercontent.com/virshi-ai/image/refs/heads/main/logo-removebg-preview.png", width=150)
            st.markdown("---")
            if st.button("🚪 Вийти з акаунту", use_container_width=True):
                logout()
        
        # Примусово показуємо сторінку проектів
        show_my_projects_page()
        return 

    # 4. ОСНОВНИЙ ДОДАТОК (Є Юзер і Проект)
    # Малюємо повне меню з utils/ui.py
    page = render_sidebar()

    # Роутинг
    if page == "Дашборд":
        show_dashboard()
    elif page == "Мої проекти":
        show_my_projects_page()
    elif page == "Перелік запитів":
        show_keywords_page()
    elif page == "Джерела":
        show_sources_page()
    elif page == "Конкуренти":
        show_competitors_page()
    elif page == "Рекомендації":
        show_recommendations_page()
    elif page == "Історія сканувань":
        show_history_page()
    elif page == "Звіти":
        show_reports_page()
    elif page == "FAQ":
        show_faq_page()
    elif page == "GPT-Visibility":
        show_chat_page()
    elif page == "Адмін":
        if user_role in ["admin", "super_admin"]:
            show_admin_page()
        else:
            st.error("Доступ заборонено.")

if __name__ == "__main__":
    main()
