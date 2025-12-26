import streamlit as st
import extra_streamlit_components as stx
import time
from datetime import datetime, timedelta
from utils.db import supabase

# --- 1. COOKIE MANAGER (SINGLETON FIX) ---
def get_cookie_manager():
    """
    Створює менеджер кукі лише один раз за сесію, щоб уникнути DuplicateElementKey.
    """
    # Перевіряємо, чи вже створено менеджер у цій сесії
    if "cookie_manager_instance" in st.session_state:
        return st.session_state["cookie_manager_instance"]

    # Ініціалізація з унікальним ключем
    cookie_manager = stx.CookieManager(key="auth_cookie_manager")
    
    # Зберігаємо інстанс у стані
    st.session_state["cookie_manager_instance"] = cookie_manager
    return cookie_manager

# --- 2. ПЕРЕВІРКА СЕСІЇ ---
def check_session():
    """
    Перевіряє наявність кукі або активної сесії.
    Викликається на початку app.py.
    """
    # Ініціалізуємо менеджер (це рендерить iframe, тому має бути на початку)
    cookie_manager = get_cookie_manager()
    
    # Отримуємо всі кукі
    cookies = cookie_manager.get_all()
    
    # Якщо користувач вже в session_state, нічого не робимо
    if st.session_state.get("user"):
        return

    # Якщо є кукі 'virshi_auth_token', пробуємо відновити сесію
    token = cookies.get("virshi_auth_token")
    if token:
        try:
            # Спробуємо отримати дані користувача з бази за ID (token)
            # Примітка: Це спрощена логіка. Для повної безпеки використовуйте supabase.auth.get_session()
            user_resp = supabase.auth.get_user(token) # Це працюватиме, якщо токен - це JWT
            # Але якщо ми зберегли просто ID як куку (для спрощення):
            if not user_resp:
                 # Якщо токен - це ID, робимо запит до профілю (менш безпечно, але працює для MVP)
                 # Краще: зберігати access_token в кукі
                 pass
        except Exception:
            pass

# --- 3. АВТОРИЗАЦІЯ (LOGIN) ---
def login_user(email, password):
    """
    Логіка входу через Supabase.
    """
    try:
        # Вхід через Supabase Auth
        auth_resp = supabase.auth.sign_in_with_password({"email": email, "password": password})
        
        if auth_resp.user:
            user = auth_resp.user
            
            # Отримуємо додаткові дані профілю
            profile_resp = supabase.table("profiles").select("*").eq("id", user.id).execute()
            user_details = profile_resp.data[0] if profile_resp.data else {}
            
            # Зберігаємо в сесію
            st.session_state["user"] = user
            st.session_state["user_details"] = user_details
            st.session_state["role"] = user_details.get("role", "user")
            
            # Встановлюємо кукі на 7 днів
            cookie_manager = get_cookie_manager()
            cookie_manager.set("virshi_auth_token", auth_resp.session.access_token, expires_at=datetime.now() + timedelta(days=7))
            
            st.success(f"Вітаємо, {user_details.get('first_name', 'Користувач')}!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("Невірний логін або пароль.")

    except Exception as e:
        if "Invalid login credentials" in str(e):
            st.error("Невірний email або пароль.")
        else:
            st.error(f"Помилка входу: {e}")

# --- 4. РЕЄСТРАЦІЯ (REGISTER) ---
def register_user(email, password, first_name, last_name):
    """
    Логіка реєстрації нового користувача.
    """
    try:
        # 1. Реєстрація в Supabase Auth
        auth_resp = supabase.auth.sign_up({
            "email": email,
            "password": password,
            "options": {
                "data": {
                    "first_name": first_name,
                    "last_name": last_name
                }
            }
        })

        if auth_resp.user:
            user = auth_resp.user
            
            # 2. Оновлюємо таблицю profiles (якщо тригер не спрацював або для певності)
            # Перевіряємо, чи створився профіль автоматично (через тригери БД)
            time.sleep(1) # Даємо час базі
            
            # Оновлюємо дані
            try:
                supabase.table("profiles").update({
                    "first_name": first_name,
                    "last_name": last_name
                }).eq("id", user.id).execute()
            except:
                # Якщо запису немає, вставляємо (fallback)
                supabase.table("profiles").insert({
                    "id": user.id,
                    "email": email,
                    "first_name": first_name,
                    "last_name": last_name,
                    "role": "user"
                }).execute()

            # 3. Автоматичний вхід після реєстрації
            st.session_state["user"] = user
            st.session_state["user_details"] = {"first_name": first_name, "last_name": last_name, "role": "user"}
            
            # Кукі (якщо є сесія)
            if auth_resp.session:
                cookie_manager = get_cookie_manager()
                cookie_manager.set("virshi_auth_token", auth_resp.session.access_token, expires_at=datetime.now() + timedelta(days=7))

            st.success("Реєстрація успішна! Ласкаво просимо.")
            time.sleep(1.5)
            st.rerun()
        else:
            st.error("Не вдалося створити користувача. Можливо, email вже зайнятий.")

    except Exception as e:
        st.error(f"Помилка реєстрації: {e}")

# --- 5. ВИХІД ---
def logout():
    """
    Вихід із системи.
    """
    cookie_manager = get_cookie_manager()
    try:
        cookie_manager.delete("virshi_auth_token")
        supabase.auth.sign_out()
    except:
        pass
        
    st.session_state.clear()
    st.rerun()

# --- 6. СТОРІНКА ВХОДУ (UI) ---
def show_auth_page():
    st.markdown("""
    <style>
        .auth-container {
            max-width: 400px;
            margin: 0 auto;
            padding-top: 50px;
            text-align: center;
        }
        .stButton button {
            width: 100%;
            background-color: #00C896;
            color: white;
            font-weight: bold;
            border-radius: 8px;
            height: 45px;
        }
        .stButton button:hover {
            background-color: #00a87e;
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        st.markdown("<div style='text-align: center; margin-bottom: 20px;'><h2>👋 Вітаємо у Virshi.ai</h2></div>", unsafe_allow_html=True)
        
        tab_login, tab_register = st.tabs(["Вхід", "Реєстрація"])
        
        with tab_login:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Пароль", type="password", key="login_pass")
            
            st.write("")
            if st.button("Увійти", key="btn_login"):
                if email and password:
                    login_user(email, password)
                else:
                    st.warning("Заповніть всі поля.")

        with tab_register:
            r_email = st.text_input("Email", key="reg_email")
            r_pass = st.text_input("Пароль", type="password", key="reg_pass")
            r_name = st.text_input("Ім'я", key="reg_name")
            r_surname = st.text_input("Прізвище", key="reg_surname")
            
            st.write("")
            if st.button("Зареєструватися", key="btn_register"):
                if r_email and r_pass and r_name:
                    register_user(r_email, r_pass, r_name, r_surname)
                else:
                    st.warning("Заповніть обов'язкові поля.")
