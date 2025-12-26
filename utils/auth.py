import streamlit as st
import extra_streamlit_components as stx
import time
from datetime import datetime, timedelta
from utils.db import supabase

# Initialize Cookie Manager (Singleton pattern to avoid DuplicateKeyError)
def get_cookie_manager():
    if "cookie_manager" not in st.session_state:
        st.session_state.cookie_manager = stx.CookieManager(key="auth_cookie_manager")
    return st.session_state.cookie_manager

def load_user_project(user_id: str) -> bool:
    try:
        res = supabase.table("projects").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            st.session_state["current_project"] = res.data[0]
            return True
    except Exception:
        pass
    return False

def get_user_role_and_details(user_id: str):
    try:
        data = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if data.data:
            p = data.data[0]
            return p.get("role", "user"), {
                "first_name": p.get("first_name"),
                "last_name": p.get("last_name"),
            }
    except Exception:
        pass
    return "user", {}

def check_session():
    # Ensure cookie manager is initialized
    cookie_manager = get_cookie_manager()
    
    # Allow cookie manager to load
    # time.sleep(0.1) # removed to avoid flicker, usually not strictly needed if initialized early
    
    if st.session_state.get("user") is None:
        cookies = cookie_manager.get_all()
        token = cookies.get("virshi_auth_token")

        if token:
            try:
                res = supabase.auth.get_user(token)
                if getattr(res, "user", None):
                    st.session_state["user"] = res.user
                    role, details = get_user_role_and_details(res.user.id)
                    st.session_state["role"] = role
                    st.session_state["user_details"] = details
                    load_user_project(res.user.id)
                else:
                    cookie_manager.delete("virshi_auth_token")
            except Exception:
                # If token is invalid or expired
                cookie_manager.delete("virshi_auth_token")

def login_user(email, password):
    cookie_manager = get_cookie_manager()
    try:
        res = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        if not res.user:
            st.error("Не вдалося увійти. Перевірте email та пароль.")
            return

        st.session_state["user"] = res.user
        cookie_manager.set(
            "virshi_auth_token",
            res.session.access_token,
            expires_at=datetime.now() + timedelta(days=7),
        )

        role, details = get_user_role_and_details(res.user.id)
        st.session_state["role"] = role
        st.session_state["user_details"] = details

        if load_user_project(res.user.id):
            st.success("Вхід успішний!")

        st.rerun()
    except Exception:
        st.error(
            "Помилка входу: невірний логін, пароль або налаштування підтвердження email."
        )

def register_user(email, password, first, last):
    cookie_manager = get_cookie_manager()
    try:
        res = supabase.auth.sign_up(
            {
                "email": email,
                "password": password,
                "options": {"data": {"first_name": first, "last_name": last}},
            }
        )

        if res.user:
            # Explicitly create profile
            try:
                supabase.table("profiles").insert(
                    {
                        "id": res.user.id,
                        "email": email,
                        "first_name": first,
                        "last_name": last,
                        "role": "user",
                    }
                ).execute()
            except Exception:
                pass

            if res.session:
                st.success("Реєстрація успішна! Виконуємо вхід...")
                st.session_state["user"] = res.user
                cookie_manager.set(
                    "virshi_auth_token",
                    res.session.access_token,
                    expires_at=datetime.now() + timedelta(days=7),
                )
                role, details = get_user_role_and_details(res.user.id)
                st.session_state["role"] = role
                st.session_state["user_details"] = details
                load_user_project(res.user.id)
                st.rerun()
            else:
                st.success(
                    "Реєстрація успішна! Перевірте пошту, підтвердіть email "
                    "та увійдіть на вкладці «Вхід»."
                )
            return True

        st.error("Не вдалося створити користувача. Перевірте налаштування Auth.")
    except Exception as e:
        if "already registered" in str(e):
            st.warning("Користувач вже існує. Спробуйте увійти.")
        else:
            st.error(f"Помилка реєстрації: {e}")
    return False

def logout():
    cookie_manager = get_cookie_manager()
    try:
        cookie_manager.delete("virshi_auth_token")
    except Exception:
        pass

    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    st.session_state.clear()
    st.rerun()

def show_auth_page():
    # CSS for auth page
    st.markdown("""
    <style>
        .stApp { background-color: #F4F7F6; }
        [data-testid="stForm"] {
            background-color: #ffffff; padding: 40px; border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08); border: 1px solid #EAEAEA;
        }
        .stButton > button {
            width: 100%; background-color: #00C896 !important; color: white !important;
            border: none; border-radius: 8px; padding: 12px; font-weight: 600; margin-top: 10px;
        }
        .stButton > button:hover { background-color: #00a87e !important; }
        .stTabs [data-baseweb="tab-list"] { gap: 20px; justify-content: center; }
    </style>
    """, unsafe_allow_html=True)

    col_l, col_center, col_r = st.columns([1, 1.5, 1])

    with col_center:
        st.markdown(
            '<div style="text-align: center; margin-bottom: 20px;">'
            '<img src="https://raw.githubusercontent.com/virshi-ai/image/refs/heads/main/logo-removebg-preview.png" width="180">'
            '</div>',
            unsafe_allow_html=True,
        )
        
        st.markdown("<h3 style='text-align: center; color: #333; margin-bottom: 5px;'>Welcome to Virshi</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #666; margin-bottom: 30px;'>Sign in to manage your AI visibility</p>", unsafe_allow_html=True)

        t1, t2 = st.tabs(["🔑 Вхід", "📝 Реєстрація"])

        with t1:
            with st.form("login_form"):
                email = st.text_input("Емейл", placeholder="name@company.com")
                password = st.text_input("Пароль", type="password")
                if st.form_submit_button("Увійти"):
                    if email and password:
                        login_user(email, password)
                    else:
                        st.warning("Введіть емейл та пароль.")

        with t2:
            with st.form("register_form"):
                ne = st.text_input("Емейл", placeholder="name@company.com")
                np = st.text_input("Пароль", type="password")
                c1, c2 = st.columns(2)
                fn = c1.text_input("Ім'я")
                ln = c2.text_input("Прізвище")
                if st.form_submit_button("Зареєструватися"):
                    if ne and np and fn:
                        register_user(ne, np, fn, ln)
                    else:
                        st.warning("Всі поля обов'язкові.")
