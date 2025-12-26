import streamlit as st
from streamlit_option_menu import option_menu
from utils.auth import logout
from utils.db import supabase

def load_custom_css():
    st.markdown(
    """
    <style>
    /* 1. ЗАГАЛЬНІ НАЛАШТУВАННЯ */
    .stApp { background-color: #F4F6F9; }
    
    /* Приховування якірних посилань */
    [data-testid="stMarkdownContainer"] h1 > a,
    [data-testid="stMarkdownContainer"] h2 > a,
    [data-testid="stMarkdownContainer"] h3 > a,
    [data-testid="stMarkdownContainer"] h4 > a,
    [data-testid="stMarkdownContainer"] h5 > a,
    [data-testid="stMarkdownContainer"] h6 > a {
        display: none !important;
    }
    a.anchor-link { display: none !important; }

    /* 2. САЙДБАР */
    section[data-testid="stSidebar"] { 
        background-color: #FFFFFF; 
        border-right: 1px solid #E0E0E0; 
    }
    .sidebar-logo-container { display: flex; justify-content: center; margin-bottom: 10px; }
    .sidebar-logo-container img { width: 140px; }
    .sidebar-name { font-size: 14px; font-weight: 600; color: #333; margin-top: 5px;}
    .sidebar-label { font-size: 11px; color: #999; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 15px;}

    /* 3. КОНТЕЙНЕРИ І ФОРМИ */
    .css-1r6slb0, .css-12oz5g7, div[data-testid="stForm"] {
        background-color: white; padding: 20px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #EAEAEA;
    }

    /* 4. МЕТРИКИ */
    div[data-testid="stMetric"] {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px;
        border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .metric-card-small {
        background-color: #F0F2F6;
        border-radius: 6px;
        padding: 10px;
        text-align: center;
    }
    .metric-value {
        font-size: 18px; font-weight: bold; color: #8041F6;
    }
    .metric-label {
        font-size: 12px; color: #666;
    }

    /* 5. КНОПКИ */
    .stButton>button { 
        background-color: #8041F6; color: white; border-radius: 8px; border: none; font-weight: 600; 
        transition: background-color 0.3s;
    }
    .stButton>button:hover { background-color: #6a35cc; }
    
    .upgrade-btn {
        display: block; width: 100%; background-color: #FFC107; color: #000000;
        text-align: center; padding: 8px; border-radius: 8px;
        text-decoration: none; font-weight: bold; margin-top: 10px; border: 1px solid #e0a800;
    }

    /* 6. БЕЙДЖІ ТА СТАТУСИ */
    .badge-trial { background-color: #FFECB3; color: #856404; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.7em; }
    .badge-active { background-color: #D4EDDA; color: #155724; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.7em; }

    /* 7. ВІДПОВІДЬ ШІ */
    .ai-response-box {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 8px;
        padding: 20px;
        font-family: 'Source Sans Pro', sans-serif;
        line-height: 1.6;
        color: #31333F;
        box-shadow: 0 1px 2px rgba(0,0,0,0.05);
        max-height: 600px;
        overflow-y: auto;
    }
    </style>
    """,
    unsafe_allow_html=True,
    )

def render_sidebar():
    with st.sidebar:
        # --- ЛОГОТИП ---
        st.image("https://raw.githubusercontent.com/virshi-ai/image/39ba460ec649893b9495427aa102420beb1fa48d/virshi-op_logo-main.png", width=150)
        
        st.markdown("---")
        
        # --- ІНФО ПРО КОРИСТУВАЧА ---
        user_email = st.session_state.get("user", {}).get("email", "User")
        user_role = st.session_state.get("role", "user")
        
        st.caption(f"Ви авторизовані як:\n**{user_role.capitalize()}**")
        st.caption(user_email)
        
        st.markdown("---")

        # --- ВИБІР ПРОЕКТУ ---
        if "projects" not in st.session_state or not st.session_state["projects"]:
            try:
                response = supabase.table("projects").select("*").execute()
                st.session_state["projects"] = response.data
            except:
                st.session_state["projects"] = []

        projects = st.session_state["projects"]
        
        if not projects:
            st.warning("Проекти не знайдені")
        else:
            project_names = [p['brand_name'] for p in projects]
            current_p = st.session_state.get("current_project", {})
            default_index = 0
            
            if current_p:
                try:
                    default_index = project_names.index(current_p['brand_name'])
                except ValueError:
                    default_index = 0

            selected_project_name = st.selectbox(
                "Оберіть проект:", 
                project_names, 
                index=default_index,
                key="sidebar_project_select"
            )
            
            new_project = next((p for p in projects if p['brand_name'] == selected_project_name), None)
            if new_project and (not current_p or current_p['id'] != new_project['id']):
                st.session_state["current_project"] = new_project
                st.rerun()

        st.markdown("### 🖥 Меню")
        
        # --- НАВІГАЦІЯ ---
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

        if st.session_state.get("role") in ["admin", "super_admin"]:
            options.append("Адмін")
            icons.append("shield-lock")

        default_idx = 0
        redirect_target = st.session_state.get("force_redirect_to")
        
        if redirect_target and redirect_target in options:
            default_idx = options.index(redirect_target)
            del st.session_state["force_redirect_to"]
        
        menu_refresh_id = st.session_state.get("menu_id_counter", 0)

        selected = option_menu(
            "Меню",
            options,
            icons=icons,
            menu_icon="cast",
            default_index=default_idx,
            key=f"main_menu_nav_{menu_refresh_id}", 
            styles={
                "container": {"padding": "0!important", "background-color": "transparent"},
                "icon": {"color": "grey", "font-size": "16px"}, 
                "nav-link": {"font-size": "14px", "text-align": "left", "margin":"0px", "--hover-color": "#eee"},
                "nav-link-selected": {"background-color": "#00C896"},
            }
        )
        
        st.divider()

        st.caption("Потрібна допомога?")
        st.markdown("📧 [hi@virshi.ai](mailto:hi@virshi.ai)")
        
        if st.button("🚪 Вийти з акаунту"):
            logout()
    
    return selected
