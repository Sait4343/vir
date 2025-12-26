import streamlit as st
import time

# 1. КОНФІГУРАЦІЯ СТОРІНКИ (Має бути першою командою)
st.set_page_config(
    page_title="AI Visibility by Virshi",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. ІМПОРТИ (Після конфігурації)
from utils.auth import check_session, show_auth_page, logout
from utils.ui import render_sidebar, load_custom_css
from utils.db import supabase

# Імпорт сторінок (Views)
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

# 3. ЗАВАНТАЖЕННЯ СТИЛІВ
load_custom_css()

# 4. ПЕРЕВІРКА СЕСІЇ
check_session()

# ==========================================
# ГОЛОВНА ЛОГІКА
# ==========================================

def main():
    # А. Якщо користувач НЕ авторизований -> Показуємо вхід
    if not st.session_state.get("user"):
        show_auth_page()
        return

    # Б. Якщо користувач авторизований:
    
    # 1. Рендеримо сайдбар і отримуємо обрану сторінку
    # Ця функція малює лого, інфо про юзера і меню
    selected_page = render_sidebar()

    # 2. Логіка примусового створення проекту для нових юзерів
    # Якщо проекту немає, і це не адмін - перекидаємо на сторінку проектів
    user_role = st.session_state.get("role", "user")
    current_proj = st.session_state.get("current_project")

    if not current_proj and user_role not in ["admin", "super_admin"]:
        if selected_page != "Мої проекти":
            st.warning("⚠️ Будь ласка, створіть або оберіть проект, щоб продовжити.")
            show_my_projects_page()
            return # Зупиняємо виконання, щоб не показувати іншу сторінку

    # 3. Роутинг (Перемикання сторінок)
    if selected_page == "Дашборд":
        show_dashboard()
        
    elif selected_page == "Мої проекти":
        show_my_projects_page()
        
    elif selected_page == "Перелік запитів":
        show_keywords_page()
        
    elif selected_page == "Джерела":
        show_sources_page()
        
    elif selected_page == "Конкуренти":
        show_competitors_page()
            
    elif selected_page == "Рекомендації":
        show_recommendations_page()

    elif selected_page == "Історія сканувань":
        show_history_page()
        
    elif selected_page == "Звіти":
        show_reports_page()
        
    elif selected_page == "FAQ":
        show_faq_page()

    elif selected_page == "GPT-Visibility":
        show_chat_page()
        
    elif selected_page == "Адмін":
        if user_role in ["admin", "super_admin"]:
            show_admin_page()
        else:
            st.error("⛔ Доступ заборонено.")

if __name__ == "__main__":
    main()
