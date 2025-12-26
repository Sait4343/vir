import requests
import streamlit as st
import time
from utils.db import supabase # Імпортуємо підключення до БД

def show_chat_page():
    """
    Сторінка AI-асистента (GPT-Visibility).
    Дизайн: Картковий стиль (Card UI) з кастомними бульбашками повідомлень.
    Логіка: Webhook n8n + Context (Sources, Brand, User).
    """

    # --- 1. КОНФІГУРАЦІЯ ---
    # Отримуємо URL вебхука (краще винести в secrets або utils/n8n.py)
    # Якщо він не заданий в secrets, можна використати дефолтний
    try:
        N8N_CHAT_WEBHOOK = st.secrets.get("N8N_CHAT_WEBHOOK", "https://virshi.app.n8n.cloud/webhook/webhook/chat-bot")
    except:
        N8N_CHAT_WEBHOOK = "https://virshi.app.n8n.cloud/webhook/webhook/chat-bot"
        
    target_url = N8N_CHAT_WEBHOOK

    headers = {
        "virshi-auth": "hi@virshi.ai2025" 
    }

    # --- 2. CSS СТИЛІЗАЦІЯ (ДИЗАЙН ЗІ СКРІНШОТУ) ---
    st.markdown("""
    <style>
        /* Основний контейнер (Картка) */
        .chat-card-container {
            background-color: white;
            border: 1px solid #e0e0e0;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.05);
            margin-bottom: 100px; /* Місце для інпуту знизу */
        }
        
        /* Заголовок картки */
        .chat-card-header {
            font-family: 'Montserrat', sans-serif;
            font-size: 16px;
            font-weight: 700;
            color: #111;
            padding-bottom: 15px;
            border-bottom: 1px solid #f0f0f0;
            margin-bottom: 20px;
        }

        /* Повідомлення AI (Ліворуч, біле з рамкою) */
        .msg-container-ai {
            display: flex;
            justify-content: flex-start;
            margin-bottom: 15px;
            align-items: flex-start;
        }
        .avatar-ai {
            width: 35px;
            height: 35px;
            background-color: #F3F4F6;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-right: 10px;
            font-size: 20px;
            flex-shrink: 0;
        }
        .bubble-ai {
            background-color: #ffffff;
            border: 1px solid #6c5ce7; /* Фіолетова рамка як на скріншоті */
            color: #333;
            padding: 12px 16px;
            border-radius: 12px;
            border-top-left-radius: 2px; /* Гострий кут до аватара */
            max-width: 80%;
            font-size: 14px;
            line-height: 1.5;
            box-shadow: 0 2px 4px rgba(0,0,0,0.03);
        }
        .ai-label {
            font-size: 11px;
            font-weight: 700;
            color: #333;
            margin-bottom: 4px;
            display: block;
        }

        /* Повідомлення Користувача (Праворуч, фіолетове) */
        .msg-container-user {
            display: flex;
            justify-content: flex-end;
            margin-bottom: 15px;
        }
        .bubble-user {
            background-color: #6c5ce7; /* Primary Purple */
            color: white;
            padding: 12px 16px;
            border-radius: 12px;
            border-bottom-right-radius: 2px;
            max-width: 80%;
            font-size: 14px;
            line-height: 1.5;
            box-shadow: 0 2px 5px rgba(108, 92, 231, 0.2);
            text-align: left;
        }
        
        /* Приховати стандартні елементи Streamlit, що заважають дизайну */
        .stChatMessage { display: none !important; } 
    </style>
    """, unsafe_allow_html=True)

    # --- 3. ЛОГІКА ДАНИХ ---
    user = st.session_state.get("user")
    role = st.session_state.get("role", "user") 
    proj = st.session_state.get("current_project", {})
    
    if not proj:
        st.info("⚠️ Спочатку оберіть проект у меню зліва.")
        return

    # Ім'я користувача
    user_name = "Користувач"
    if user:
        meta = getattr(user, "user_metadata", {})
        user_name = meta.get("full_name") or meta.get("name") or user.email.split("@")[0]

    # Офіційні джерела (Whitelist)
    official_sources_list = []
    try:
        assets_resp = supabase.table("official_assets")\
            .select("domain_or_url")\
            .eq("project_id", proj.get("id"))\
            .execute()
        if assets_resp.data:
            official_sources_list = [item["domain_or_url"] for item in assets_resp.data]
    except Exception:
        official_sources_list = []

    # Ініціалізація історії
    if "chat_messages" not in st.session_state:
        brand_name = proj.get('brand_name', 'Brand')
        welcome_text = f"Based on the latest analysis, **{brand_name}**'s presence has improved. I'm ready to help you with visibility insights."
        st.session_state["chat_messages"] = [
            {"role": "assistant", "content": welcome_text}
        ]

    # --- 4. ВІДОБРАЖЕННЯ ІНТЕРФЕЙСУ (КАРТКА) ---
    
    # Заголовок сторінки (як в дизайні)
    st.markdown("### 🤖 AI Visibility Assistant")

    # Контейнер-картка
    chat_container = st.container()
    
    with chat_container:
        # Відкриваємо div картки
        st.markdown(f"""
        <div class="chat-card-container">
            <div class="chat-card-header">
                Project: {proj.get('brand_name', 'Unknown')} - AI Chat Assistant (GPT-Visibility)
            </div>
        """, unsafe_allow_html=True)

        # Рендеринг повідомлень (HTML Loop)
        for msg in st.session_state["chat_messages"]:
            content = msg["content"]
            
            if msg["role"] == "assistant":
                st.markdown(f"""
                <div class="msg-container-ai">
                    <div class="avatar-ai">🤖</div>
                    <div class="bubble-ai">
                        <span class="ai-label">AI Assistant</span>
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="msg-container-user">
                    <div class="bubble-user">
                        {content}
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # Закриваємо div картки
        st.markdown("</div>", unsafe_allow_html=True)

    # --- 5. ВВЕДЕННЯ ТА ОБРОБКА ---
    
    if prompt := st.chat_input("Ask GPT-Visibility about your brand's AI presence..."):
        
        # 1. Додаємо питання користувача в історію
        st.session_state["chat_messages"].append({"role": "user", "content": prompt})
        st.rerun() # Оновлюємо, щоб показати повідомлення користувача одразу

    # Логіка відповіді (спрацьовує після rerun, якщо останнє повідомлення - від user)
    if st.session_state["chat_messages"] and st.session_state["chat_messages"][-1]["role"] == "user":
        
        last_user_msg = st.session_state["chat_messages"][-1]["content"]
        
        # Показуємо спінер над інпутом (або під карткою)
        with st.spinner("AI Assistant is typing..."):
            try:
                # Payload
                payload = {
                    "query": last_user_msg,
                    "user_id": user.id if user else "guest",
                    "user_email": user.email if user else None,
                    "user_name": user_name,
                    "role": role,
                    "project_id": proj.get("id"),
                    "project_name": proj.get("brand_name"),
                    "target_brand": proj.get("brand_name"),
                    "domain": proj.get("domain"),
                    "status": proj.get("status"),
                    "official_sources": official_sources_list
                }

                response = requests.post(
                    target_url, 
                    json=payload, 
                    headers=headers, 
                    timeout=240
                )

                if response.status_code == 200:
                    data = response.json()
                    bot_reply = data.get("output") or data.get("answer") or data.get("text")
                    
                    if isinstance(bot_reply, dict):
                        bot_reply = str(bot_reply)
                    
                    if not bot_reply:
                        bot_reply = "⚠️ I received an empty response from the AI."
                        
                elif response.status_code == 403:
                    bot_reply = "⛔ Error 403: Access denied. Check API keys."
                elif response.status_code == 404:
                    bot_reply = "⚠️ Error 404: Endpoint not found."
                else:
                    bot_reply = f"⚠️ Server Error: {response.status_code}"

            except Exception as e:
                bot_reply = f"⚠️ Connection Error: {e}"

            # Додаємо відповідь бота в історію
            st.session_state["chat_messages"].append({"role": "assistant", "content": bot_reply})
            st.rerun()
