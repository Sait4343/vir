import streamlit as st
from streamlit_option_menu import option_menu
from utils.auth import logout
from utils.db import supabase

def load_custom_css():
    st.markdown("""
    <style>
    /* 1. GENERAL SETTINGS */
    .stApp { background-color: #F4F6F9; }
    
    /* Hide anchor links */
    [data-testid="stMarkdownContainer"] h1 > a,
    [data-testid="stMarkdownContainer"] h2 > a,
    [data-testid="stMarkdownContainer"] h3 > a,
    [data-testid="stMarkdownContainer"] h4 > a,
    [data-testid="stMarkdownContainer"] h5 > a,
    [data-testid="stMarkdownContainer"] h6 > a {
        display: none !important;
    }
    a.anchor-link { display: none !important; }

    /* 2. SIDEBAR */
    section[data-testid="stSidebar"] { 
        background-color: #FFFFFF; 
        border-right: 1px solid #E0E0E0; 
    }
    
    /* Hide default sidebar header/close button */
    [data-testid="stSidebarHeader"] {
        padding-top: 0rem !important;
        height: 0rem !important;
        visibility: hidden;
    }

    /* 3. CONTAINERS AND FORMS */
    .css-1r6slb0, .css-12oz5g7, div[data-testid="stForm"] {
        background-color: white; padding: 20px; border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #EAEAEA;
    }

    /* 4. METRICS */
    div[data-testid="stMetric"] {
        background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px;
        border-radius: 10px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }

    /* 5. BUTTONS */
    .stButton>button { 
        background-color: #8041F6; color: white; border-radius: 8px; border: none; font-weight: 600; 
        transition: background-color 0.3s;
    }
    .stButton>button:hover { background-color: #6a35cc; }

    /* 6. BADGES */
    .badge-trial { background-color: #FFECB3; color: #856404; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.7em; }
    .badge-active { background-color: #D4EDDA; color: #155724; padding: 2px 6px; border-radius: 4px; font-weight: bold; font-size: 0.7em; }
    </style>
    """, unsafe_allow_html=True)

def render_sidebar():
    """
    Renders the sidebar and returns the selected menu option.
    Uses the logic from the working monolithic code.
    """
    
    # Data from session state
    proj = st.session_state.get("current_project")
    user = st.session_state.get("user")
    user_details = st.session_state.get("user_details", {})
    
    # Safe User Email Access
    user_email = "guest@virshi.ai"
    if user:
        if hasattr(user, "email"):
            user_email = user.email
        elif isinstance(user, dict):
            user_email = user.get("email", "guest@virshi.ai")

    first_name = user_details.get("first_name", "")
    last_name = user_details.get("last_name", "")
    full_name = f"{first_name} {last_name}".strip()
    if not full_name: full_name = "Користувач"

    proj_name = proj.get("brand_name", "No Project") if proj else "Оберіть проект"
    proj_id = proj.get("id", "") if proj else ""
    proj_domain = proj.get("domain", "") if proj else ""

    with st.sidebar:
        # LOGO
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 5px;">
                <img src="https://raw.githubusercontent.com/virshi-ai/image/refs/heads/main/logo-removebg-preview.png" width="160" style="display: inline-block;">
                <div style="margin-top: 5px; font-size: 18px; font-weight: bold; color: #333; letter-spacing: 0.5px;">AI Visibility</div>
            </div>
            <div style="margin-top: 20px; border-top: 1px solid #E0E0E0;"></div>
            <div style="margin-top: 15px;"></div>
        """, unsafe_allow_html=True)

        # PROFILE
        st.markdown(f"""
        <div style='line-height: 1.2; margin-bottom: 10px; padding-right: 40px;'>
            <div style='font-size: 12px; color: rgba(49, 51, 63, 0.6); margin-bottom: 2px;'>Ви авторизовані як:</div>
            <div style='font-weight: 600; font-size: 16px; color: #31333F;'>{full_name}</div>
            <div style='font-size: 12px; color: rgba(49, 51, 63, 0.6);'>{user_email}</div>
        </div>
        """, unsafe_allow_html=True)
        
        st.write("") 

        # PROJECT SELECTION LOGIC
        # 1. Load projects if not already in session
        if "projects" not in st.session_state or not st.session_state["projects"]:
            try:
                # Safe access to user ID
                uid = user.id if hasattr(user, 'id') else user.get('id') if user else None
                if uid:
                    response = supabase.table("projects").select("*").eq("user_id", uid).execute()
                    st.session_state["projects"] = response.data
                else:
                    st.session_state["projects"] = []
            except:
                st.session_state["projects"] = []

        projects = st.session_state["projects"]
        
        # 2. Render Project Selector or Warning
        if not projects:
            st.warning("Проекти не знайдені")
            # Even if no projects, we still want to show the menu so user can go to "My Projects"
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
            
            # Update current project if selection changed
            new_project = next((p for p in projects if p['brand_name'] == selected_project_name), None)
            if new_project and (not current_p or current_p['id'] != new_project['id']):
                st.session_state["current_project"] = new_project
                st.rerun()

        # 3. Project Details (Logo + Name)
        logo_url = None
        backup_logo_url = None
        clean_d = None

        if proj and proj_domain:
            clean_d = proj_domain.lower().replace('https://', '').replace('http://', '').replace('www.', '')
            if '/' in clean_d: clean_d = clean_d.split('/')[0]
            logo_url = f"https://cdn.brandfetch.io/{clean_d}"
            backup_logo_url = f"https://www.google.com/s2/favicons?domain={clean_d}&sz=128"

        if proj and proj_name != "Оберіть проект":
            if logo_url:
                col_brand_img, col_brand_txt = st.columns([0.25, 0.75])
                with col_brand_img:
                    img_html = f'<img src="{logo_url}" style="width: 45px; height: 45px; object-fit: contain; border-radius: 5px; pointer-events: none;" onerror="this.onerror=null; this.src=\'{backup_logo_url}\';">'
                    st.markdown(img_html, unsafe_allow_html=True)
                
                with col_brand_txt:
                    html_content = f"""
                    <div style='line-height: 1.1; display: flex; flex-direction: column; justify-content: center; height: 48px;'>
                        <div style='font-weight: bold; font-size: 20px; color: #31333F; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;'>{proj_name}</div>
                        <div style='font-size: 12px; color: #888;'>{clean_d if clean_d else ''}</div>
                    </div>
                    """
                    st.markdown(html_content, unsafe_allow_html=True)
            else:
                st.markdown(f"### 📁 {proj_name}")
                if clean_d: st.caption(clean_d)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)

        # --- MENU ---
        st.markdown("### 🖥 Меню")
        
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

        # Admin check
        if st.session_state.get("role") in ["admin", "super_admin"]:
            options.append("Адмін")
            icons.append("shield-lock")

        # Redirect logic
        default_idx = 0
        redirect_target = st.session_state.get("force_redirect_to")
        if redirect_target and redirect_target in options:
            default_idx = options.index(redirect_target)
            del st.session_state["force_redirect_to"]
        
        # Unique key for menu to force refresh if needed
        menu_refresh_id = st.session_state.get("menu_id_counter", 0)

        # Render option_menu
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

        # FOOTER
        st.caption("Потрібна допомога?")
        st.markdown("📧 [hi@virshi.ai](mailto:hi@virshi.ai)")
        
        # Project status if exists
        if proj:
            st.write("")
            status = proj.get("status", "trial").upper()
            color = "orange" if status == "TRIAL" else "green" if status == "ACTIVE" else "red"
            st.markdown(f"Статус: **:{color}[{status}]**")
            st.caption(f"ID: `{proj_id}`")

        st.write("")
        if st.button("🚪 Вийти з акаунту", use_container_width=True):
            logout()
            
    return selected
