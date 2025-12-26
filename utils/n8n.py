import requests
import streamlit as st
from utils.db import supabase # Потрібно для перевірки лімітів

# 🔴 ПРОДАКШН N8N ВЕБХУКИ
N8N_GEN_URL = "https://virshi.app.n8n.cloud/webhook/webhook/generate-prompts"
N8N_ANALYZE_URL = "https://virshi.app.n8n.cloud/webhook/webhook/run-analysis_prod"
N8N_RECO_URL = "https://virshi.app.n8n.cloud/webhook/recommendations"  
N8N_CHAT_WEBHOOK = "https://virshi.app.n8n.cloud/webhook/webhook/chat-bot" 

def n8n_generate_prompts(brand: str, domain: str, industry: str, products: str):
    """
    Викликає n8n вебхук для генерації промптів.
    """
    try:
        payload = {
            "brand": brand,
            "domain": domain,
            "industry": industry,
            "products": products,
        }
        headers = {
            "virshi-auth": "hi@virshi.ai2025"
        }
        response = requests.post(N8N_GEN_URL, json=payload, headers=headers, timeout=60)

        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                return data
            return data.get("prompts", [])
        else:
            st.error(f"N8N Error: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        st.error(f"Помилка з'єднання з N8N: {e}")
        return []

def n8n_trigger_analysis(project_id, keywords, brand_name, models=None):
    """
    Відправляє запит на n8n для аналізу.
    ВЕРСІЯ: TRIAL LOGIC UPDATE.
    """
    # URL для аналізу (може бути перезаписаний з secrets)
    target_url = st.secrets.get("N8N_ANALYZE_URL", N8N_ANALYZE_URL)

    MODEL_MAPPING = {
        "Perplexity": "perplexity",
        "OpenAI GPT": "gpt-4o",
        "Google Gemini": "gemini-1.5-pro"
    }

    # Отримання статусу проекту
    current_proj = st.session_state.get("current_project")
    status = "trial"
    if current_proj and current_proj.get("id") == project_id:
        status = current_proj.get("status", "trial")
    
    if status == "blocked":
        st.error("⛔ Проект заблоковано. Зверніться до адміністратора.")
        return False

    if not models:
        models = ["Perplexity"] # Default

    if isinstance(keywords, str):
        keywords_list = [keywords]
    else:
        keywords_list = keywords

    # 🔥 ЛОГІКА ТРІАЛУ
    if status == "trial":
        try:
            # 1. Знаходимо ID для слів
            kw_resp = supabase.table("keywords")\
                .select("id, keyword_text")\
                .eq("project_id", project_id)\
                .in_("keyword_text", keywords_list)\
                .execute()
            
            kw_map = {item['keyword_text']: item['id'] for item in kw_resp.data} if kw_resp.data else {}
            
            allowed_keywords = []
            blocked_keywords = []

            for kw_text in keywords_list:
                kw_id = kw_map.get(kw_text)
                if kw_id:
                    # 2. Перевірка наявності сканів
                    existing_scan = supabase.table("scan_results")\
                        .select("id", count="exact")\
                        .eq("keyword_id", kw_id)\
                        .limit(1)\
                        .execute()
                    
                    if existing_scan.count and existing_scan.count > 0:
                        blocked_keywords.append(kw_text)
                    else:
                        allowed_keywords.append(kw_text)
                else:
                    allowed_keywords.append(kw_text)

            if blocked_keywords:
                st.warning(f"🔒 Наступні запити вже були проскановані (Trial ліміт 1 раз): {', '.join(blocked_keywords[:3])}...")
            
            if not allowed_keywords:
                st.error("⛔ Всі обрані запити вже були проскановані. У статусі Trial повторне сканування заборонено.")
                return False
            
            keywords_list = allowed_keywords

        except Exception as e:
            print(f"Trial check error: {e}")
            st.warning("⚠️ Не вдалося перевірити ліміти Trial. Спробуйте пізніше.")
            return False

    try:
        user = st.session_state.get("user")
        user_email = user.email if user else "no-reply@virshi.ai"
        
        success_count = 0

        # Отримання Whitelist
        clean_assets = []
        try:
            assets_resp = supabase.table("official_assets")\
                .select("domain_or_url")\
                .eq("project_id", project_id)\
                .execute()
            
            if assets_resp.data:
                for item in assets_resp.data:
                    raw_url = item.get("domain_or_url", "").lower().strip()
                    clean = raw_url.replace("https://", "").replace("http://", "").replace("www.", "").rstrip("/")
                    if clean:
                        clean_assets.append(clean)
        except Exception as e:
            print(f"Error fetching assets: {e}")
            clean_assets = []

        headers = {"virshi-auth": "hi@virshi.ai2025"}

        if not keywords_list:
             return False

        for ui_model_name in models:
            tech_model_id = MODEL_MAPPING.get(ui_model_name, ui_model_name)

            payload = {
                "project_id": project_id,
                "keywords": keywords_list,
                "brand_name": brand_name,
                "user_email": user_email,
                "provider": tech_model_id,
                "models": [tech_model_id],
                "official_assets": clean_assets 
            }
            
            try:
                response = requests.post(
                    target_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=60
                )
                
                if response.status_code == 200:
                    success_count += 1
                else:
                    st.error(f"Помилка n8n ({ui_model_name}): {response.text}")
                    
            except Exception as inner_e:
                st.error(f"Не вдалося запустити {ui_model_name}: {inner_e}")

        return success_count > 0
            
    except Exception as e:
        st.error(f"Критична помилка запуску: {e}")
        return False

def trigger_ai_recommendation(user, project, category, context_text):
    """
    Відправляє запит на AI для генерації HTML-звіту.
    """
    from datetime import datetime
    
    headers = {
        "virshi-auth": "hi@virshi.ai2025"
    }
    
    payload = {
        "timestamp": datetime.now().isoformat(),
        "user_id": user.id if user else "unknown",
        "user_email": user.email if user else "unknown",
        "project_id": project.get("id"),
        "brand_name": project.get("brand_name"),
        "domain": project.get("domain"),
        "category": category, 
        "request_context": context_text,
        "request_type": "html_report"
    }
    
    try:
        response = requests.post(N8N_RECO_URL, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            try:
                data = response.json()
                return data.get("html") or data.get("output") or data.get("report") or str(data)
            except:
                return response.text
        else:
            return f"<p style='color:red; font-weight:bold;'>Error from AI Provider: {response.status_code}</p>"
            
    except Exception as e:
        return f"<p style='color:red; font-weight:bold;'>Connection Error: {e}</p>"
