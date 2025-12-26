import requests
import streamlit as st

# Константи URL (можна винести в secrets)
N8N_GEN_URL = "https://virshi.app.n8n.cloud/webhook/webhook/generate-prompts"
N8N_ANALYZE_URL = "https://virshi.app.n8n.cloud/webhook/webhook/run-analysis_prod"
N8N_RECO_URL = "https://virshi.app.n8n.cloud/webhook/recommendations"
N8N_CHAT_WEBHOOK = "https://virshi.app.n8n.cloud/webhook/webhook/chat-bot"

HEADERS = {"virshi-auth": "hi@virshi.ai2025"}

def n8n_generate_prompts(brand, domain, industry, products):
    try:
        payload = {"brand": brand, "domain": domain, "industry": industry, "products": products}
        response = requests.post(N8N_GEN_URL, json=payload, headers=HEADERS, timeout=60)
        if response.status_code == 200:
            data = response.json()
            return data if isinstance(data, list) else data.get("prompts", [])
        return []
    except Exception as e:
        st.error(f"N8N Error: {e}")
        return []

def n8n_trigger_analysis(project_id, keywords, brand_name, models=None, user_email=""):
    # ... (код функції trigger_analysis з вашого файлу)
    pass
