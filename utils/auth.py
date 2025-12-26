import streamlit as st
import extra_streamlit_components as stx
import time
from datetime import datetime, timedelta
from utils.db import supabase

# --- COOKIE MANAGER (FIX: SINGLETON) ---
def get_cookie_manager():
    """Створює менеджер кукі лише один раз за сесію."""
    if "cookie_manager_instance" not in st.session_state:
        st.session_state["cookie_manager_instance"] = stx.CookieManager(key="auth_cookie_manager")
    return st.session_state["cookie_manager_instance"]

# --- HELPER: ЗАВАНТАЖЕННЯ ПРОЕКТУ ---
def load_user_project(user_id: str) -> bool:
    """Знаходить перший активний проект користувача і зберігає в сесію."""
    try:
        res = supabase.table("projects").select("*").eq("user_id", user_id).execute()
        if res.data and len(res.data) > 0:
            st.session_state["current_project"] = res.data[0]
            return True
    except Exception:
        pass
    return False

# --- HELPER: ОТРИМАННЯ ДЕТАЛЕЙ ЮЗЕРА ---
def get_user_role_and_details(user_id: str):
    try:
        data = supabase.table("profiles").select("*").eq("id", user_id).execute()
        if data.data:
            p = data.data[0]
            return p.get("role", "user"), {
                "first_name": p.get("first_name", ""),
                "last_name": p.get("last_name", ""),
            }
    except Exception:
        pass
    return "user", {}

# --- ПЕРЕВІРКА СЕСІЇ ---
def check_session():
    # Ініціалізуємо менеджер кукі (рендерить iframe, має бути на початку)
    cookie_manager = get_cookie_manager()
    
    # Якщо юзер вже є в пам'яті - виходимо
    if st.session_state.get("user"):
        return

    # Чекаємо кукі
    time.sleep(0.1)
    cookies = cookie_manager.get_all()
    token = cookies.get("virshi_auth_token")

    if token:
        try:
            # Відновлення сесії через Supabase
            res = supabase.auth.get_user(token)
            if res and res.user:
                st.session_state["user"] = res.user
                role, details = get_user_role_and_details(res.user.id)
                st.session_state["role"] = role
                st.session_state["user_details"] = details
                load_user_project(res.user.id)
            else:
                cookie_manager.delete("virshi_auth_token")
        except Exception:
            # Якщо токен невалідний
            pass

# --- ВХІД ---
def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            st.session_state["user"] = res.user
            
            # Зберігаємо куку
            cm = get_cookie_manager()
            cm.set("virshi_auth_token", res.session.access_token, expires_at=datetime.now() + timedelta(days=7))
            
            # Завантажуємо дані
            role, details = get_user_role_and_details(res.user.id)
            st.session_state["role"] = role
            st.session_state["user_details"] = details
            
            # 🔥 Завантажуємо проект одразу!
            has_project = load_user_project(res.user.id)
            
            st.success("Вхід успішний!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Невірний логін або пароль.")
    except Exception as e:
        st.error(f"Помилка входу: {e}")

# --- РЕЄСТРАЦІЯ ---
def register_user(email, password, first, last):
    try:
        res = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"first_name": first, "last_name": last}}
        })

        if res.user:
            # Створюємо запис в profiles
            try:
                supabase.table("profiles").insert({
                    "id": res.user.id,
                    "email": email,
                    "first_name": first,
                    "last_name": last,
                    "role": "user"
                }).execute()
            except:
                pass # Можливо, вже існує

            st.success("Реєстрація успішна! Увійдіть у систему.")
        else:
            st.error("Не вдалося створити користувача.")
    except Exception as e:
        st.error(f"Помилка реєстрації: {e}")

# --- ВИХІД ---
def logout():
    cm = get_cookie_manager()
    try:
        cm.delete("virshi_auth_token")
        supabase.auth.sign_out()
    except:
        pass
    st.session_state.clear()
    st.rerun()

# --- UI СТОРІНКИ ВХОДУ ---
def show_auth_page():
    st.markdown("<h2 style='text-align: center;'>👋 Вітаємо у Virshi.ai</h2>", unsafe_allow_html=True)
    t1, t2 = st.tabs(["Вхід", "Реєстрація"])
    
    with t1:
        email = st.text_input("Email", key="l_email")
        password = st.text_input("Пароль", type="password", key="l_pass")
        if st.button("Увійти", type="primary", use_container_width=True):
            login_user(email, password)
            
    with t2:
        re = st.text_input("Email", key="r_email")
        rp = st.text_input("Пароль", type="password", key="r_pass")
        c1, c2 = st.columns(2)
        fn = c1.text_input("Ім'я")
        ln = c2.text_input("Прізвище")
        if st.button("Зареєструватися", type="primary", use_container_width=True):
            register_user(re, rp, fn, ln)
