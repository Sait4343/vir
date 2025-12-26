import streamlit as st
import extra_streamlit_components as stx
from datetime import datetime, timedelta
import time
from utils.db import supabase

cookie_manager = stx.CookieManager()

def get_user_role_and_details(user_id):
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

def load_user_project(user_id):
    try:
        res = supabase.table("projects").select("*").eq("user_id", user_id).execute()
        if res.data:
            st.session_state["current_project"] = res.data[0]
            return True
    except Exception:
        pass
    return False

def check_session():
    if "user" not in st.session_state:
        st.session_state["user"] = None
    
    if st.session_state["user"] is None:
        time.sleep(0.1)
        token = cookie_manager.get("virshi_auth_token")
        if token:
            try:
                res = supabase.auth.get_user(token)
                if res.user:
                    st.session_state["user"] = res.user
                    role, details = get_user_role_and_details(res.user.id)
                    st.session_state["role"] = role
                    st.session_state["user_details"] = details
                    load_user_project(res.user.id)
                else:
                    cookie_manager.delete("virshi_auth_token")
            except:
                cookie_manager.delete("virshi_auth_token")

def login_user(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if res.user:
            st.session_state["user"] = res.user
            cookie_manager.set("virshi_auth_token", res.session.access_token, expires_at=datetime.now() + timedelta(days=7))
            role, details = get_user_role_and_details(res.user.id)
            st.session_state["role"] = role
            st.session_state["user_details"] = details
            load_user_project(res.user.id)
            st.success("Вхід успішний!")
            st.rerun()
    except Exception as e:
        st.error(f"Помилка входу: {e}")

def logout():
    cookie_manager.delete("virshi_auth_token")
    supabase.auth.sign_out()
    st.session_state.clear()
    st.rerun()
