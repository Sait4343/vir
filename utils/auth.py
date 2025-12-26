import streamlit as st
import extra_streamlit_components as stx
from datetime import datetime, timedelta
import time
from utils.db import supabase  # Імпорт клієнта бази даних

# Ініціалізація менеджера кукі
# Важливо: це має бути викликано один раз на початку роботи додатка, 
# але cookie_manager часто потребує бути в контексті рендерингу.
# Ми будемо використовувати його тут.
def get_cookie_manager():
    return stx.CookieManager(key="auth_cookie_manager")

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

def load_user_project(user_id: str) -> bool:
    try:
        res = supabase.table("projects").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            st.session_state["current_project"] = res.data[0]
            return True
    except Exception:
        pass
    return False

def check_session():
    cookie_manager = get_cookie_manager()
    
    if st.session_state.get("user") is None:
        time.sleep(0.1)
        token = cookie_manager.get("virshi_auth_token")

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
                cookie_manager.delete("virshi_auth_token")

def login_user(email: str, password: str):
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

def register_user(email: str, password: str, first: str, last: str) -> bool:
    """
    Реєстрація нового користувача + запис first_name / last_name в таблицю profiles.
    """
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
            # явне створення профілю
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
    """
    Надійний вихід із системи.
    """
    cookie_manager = get_cookie_manager()
    # 1. Видаляємо куку (Token)
    try:
        cookie_manager.delete("virshi_auth_token")
    except Exception:
        pass

    # 2. Виходимо з Supabase (на стороні сервера)
    try:
        supabase.auth.sign_out()
    except Exception:
        pass

    # 3. 🔥 ПОВНЕ очищення Session State
    st.session_state.clear()

    # 4. Ініціалізуємо критичні змінні
    st.session_state["user"] = None
    
    # 5. Пауза
    time.sleep(1)

    # 6. Перезавантаження сторінки
    st.rerun()

def show_auth_page():
    """
    Сторінка входу/реєстрації з дизайном.
    """
    # Стилізація сторінки
    st.markdown("""
    <style>
        .stApp { background-color: #F4F7F6; }
        [data-testid="stForm"] {
            background-color: #ffffff;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
            border: 1px solid #EAEAEA;
        }
        .stTextInput > div > div > input {
            border-radius: 8px;
            border: 1px solid #e0e0e0;
            padding: 10px;
        }
        .stButton > button {
            width: 100%;
            background-color: #00C896 !important;
            color: white !important;
            border: none;
            border-radius: 8px;
            padding: 12px;
            font-weight: 600;
            margin-top: 10px;
        }
        .stButton > button:hover {
            background-color: #00a87e !important;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 20px;
            justify-content: center;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            border-radius: 4px 4px 0 0;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
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

        tab_login, tab_register = st.tabs(["🔑 Вхід", "📝 Реєстрація"])

        # --- ВКЛАДКА ВХОДУ ---
        with tab_login:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="name@company.com")
                password = st.text_input("Пароль", type="password", placeholder="••••••••")
                st.write("") 
                submit = st.form_submit_button("Увійти", use_container_width=True)
                
                if submit:
                    if not email or not password:
                        st.warning("Будь ласка, заповніть всі поля.")
                    else:
                        login_user(email, password)

        # --- ВКЛАДКА РЕЄСТРАЦІЇ ---
        with tab_register:
            with st.form("register_form"):
                c1, c2 = st.columns(2)
                with c1:
                    first_name = st.text_input("Ім'я", placeholder="Іван")
                with c2:
                    last_name = st.text_input("Прізвище", placeholder="Петренко")
                
                new_email = st.text_input("Email", placeholder="name@company.com")
                new_password = st.text_input("Пароль", type="password", placeholder="••••••••", help="Мін. 6 символів")
                
                st.write("") 
                submit_reg = st.form_submit_button("Створити акаунт", use_container_width=True)
                
                if submit_reg:
                    if not new_email or not new_password or not first_name:
                        st.warning("Будь ласка, заповніть обов'язкові поля.")
                    elif len(new_password) < 6:
                        st.warning("Пароль має містити щонайменше 6 символів.")
                    else:
                        register_user(new_email, new_password, first_name, last_name)
