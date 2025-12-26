import streamlit as st
from streamlit_option_menu import option_menu
from utils.auth import logout
from utils.db import supabase

def load_custom_css():
    st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    [data-testid="stMarkdownContainer"] h1 > a { display: none !important; }
    section[data-testid="stSidebar"] { background-color: #FFFFFF; border-right: 1px solid #E0E0E0; }
    
    /* Приховування хедера сайдбару (хрестика) */
    [data-testid="stSidebarHeader"] {
        padding-top: 0rem !important; height: 0rem !important;
        visibility: hidden;
    }
    
    .stButton>button { 
        background-color: #8041F6; color: white; border-radius: 8px; border: none; font-weight: 600; 
        transition: background-color 0.3s;
    }
    .stButton>button:hover { background-color: #6a35cc; }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    """
    Малює сайдбар і повертає обрану сторінку.
    """
    # Отримуємо юзера (безпечно)
    user = st.session_state.get("user")
    user_email = "Guest"
    user_id = None

    if user:
        # Якщо це об'єкт Supabase User
        if hasattr(user, "email"):
            user_email = user.email
            user_id = user.id
        # Якщо це словник (fallback)
        elif isinstance(user, dict):
            user_email = user.get("email", "Guest")
            user_id = user.get("id")

    # Отримуємо деталі
    details = st.session_state.get("user_details", {})
    full_name = f"{details.get('first_name', '')} {details.get('last_name', '')}".strip() or "Користувач"
    role = st.session_state.get("role", "user")

    # Отримуємо проекти
    if "projects" not in st.session_state or not st.session_state["projects"]:
        try:
            if user_id:
                resp = supabase.table("projects").select("*").eq("user_id", user_id).execute()
                st.session_state["projects"] = resp.data or []
            else:
                st.session_state["projects"] = []
        except:
            st.session_state["projects"] = []
    
    projects = st.session_state["projects"]
    current_p = st.session_state.get("current_project")

    with st.sidebar:
        # 1. Лого
        st.image("https://raw.githubusercontent.com/virshi-ai/image/refs/heads/main/logo-removebg-preview.png", width=150)
        st.markdown("---")

        # 2. Інфо про юзера
        st.markdown(f"**{full_name}**")
        st.caption(f"{user_email} ({role})")
        st.markdown("---")

        # 3. Вибір проекту
        if projects:
            p_names = [p['brand_name'] for p in projects]
            curr_idx = 0
            if current_p:
                try:
                    curr_idx = p_names.index(current_p['brand_name'])
                except:
                    curr_idx = 0
            
            selected_name = st.selectbox("Проект:", p_names, index=curr_idx, key="sb_proj_sel")
            
            # Оновлюємо поточний проект
            new_p = next((p for p in projects if p['brand_name'] == selected_name), None)
            if new_p and (not current_p or current_p['id'] != new_p['id']):
                st.session_state["current_project"] = new_p
                st.rerun()
                
            # Лого бренду (якщо є)
            clean_d = None
            if current_p and current_p.get('domain'):
                 clean_d = current_p['domain'].replace('https://','').replace('www.','').split('/')[0]
                 st.image(f"https://cdn.brandfetch.io/{clean_d}", width=40)

        else:
            st.warning("Немає активних проектів")

        st.markdown("---")

        # 4. МЕНЮ (Малюємо ЗАВЖДИ)
        options = [
            "Мої проекти",      
            "Дашборд", 
            "Перелік запитів", 
            "Джерела", 
            "Конкуренти", 
            "Рекомендації", 
            "Історія сканувань", 
            "Звіти",              
            "FAQ",                
            "GPT-Visibility"
        ]
        
        icons = [
            "folder",           
            "speedometer2", 
            "list-task", 
            "router", 
            "people", 
            "lightbulb", 
            "clock-history", 
            "file-earmark-text", 
            "question-circle",    
            "robot"
        ]

        if role in ["admin", "super_admin"]:
            options.append("Адмін")
            icons.append("shield-lock")

        # Визначаємо дефолтний індекс
        default_idx = 0
        redirect = st.session_state.get("force_redirect_to")
        if redirect and redirect in options:
            default_idx = options.index(redirect)
            del st.session_state["force_redirect_to"]

        # Рендер меню
        selected = option_menu(
            menu_title=None,
            options=options,
            icons=icons,
            default_index=default_idx,
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "nav-link": {"font-size": "14px", "text-align": "left", "margin":"0px"},
                "nav-link-selected": {"background-color": "#00C896"},
            },
            key=f"menu_{st.session_state.get('menu_id_counter', 0)}"
        )
        
        st.markdown("---")
        if st.button("🚪 Вихід"):
            logout()
            
    return selected
