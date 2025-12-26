import streamlit as st
import time

# 🔥 ВИПРАВЛЕНО: Імпортуємо show_auth_page замість login_page
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

# 1. Config
st.set_page_config(
    page_title="AI Visibility by Virshi", 
    page_icon="👁️", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Styles
load_custom_css() 

# 3. Auth Check
check_session()

if not st.session_state.get("user"):
    # 🔥 ВИПРАВЛЕНО: Викликаємо правильну функцію
    show_auth_page()
else:
    # 4. Sidebar & Navigation
    selected_page = render_sidebar() 

    # 5. Routing
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
        show_admin_page()
