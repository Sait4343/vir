import streamlit as st
from supabase import create_client, Client

# Use st.cache_resource to initialize the client once
@st.cache_resource
def init_supabase() -> Client:
    try:
        # Access secrets using dictionary syntax as in your working code
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"CRITICAL ERROR: Database Connection Failed. {e}")
        st.stop()

# Create the global supabase object
supabase = init_supabase()
