import streamlit as st
import pandas as pd
from datetime import datetime
import requests
import re
import time
import uuid

# 🔥 ВАЖЛИВО: Імпортуємо supabase напряму з утиліт
# Це гарантує стабільне підключення незалежно від того, як викликається сторінка
from utils.db import supabase

def show_my_projects_page():
    """
    Сторінка 'Мої проекти'.
    ВЕРСІЯ: STABLE MODULAR.
    Додано можливість редагувати назву проекту (олівець -> інпут -> зберегти).
    """

    # --- КОНСТАНТИ ---
    N8N_GEN_URL = "https://virshi.app.n8n.cloud/webhook/webhook/generate-prompts"

    # --- CSS ---
    st.markdown("""
    <style>
        .green-number { 
            background-color: #00C896; 
            color: white; 
            width: 24px; 
            height: 24px; 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-weight: bold; 
            font-size: 12px; 
        }
        .stTabs [data-baseweb="tab-list"] { gap: 10px; }
        
        /* Стиль для кнопки редагування, щоб вона була компактною */
        button[kind="secondary"] {
            padding: 0px 10px !important;
            border: none !important;
        }
    </style>
    """, unsafe_allow_html=True)

    # --- ПЕРЕВІРКА АВТОРИЗАЦІЇ ---
    user = st.session_state.get("user")
    if not user:
        st.error("Потрібна авторизація.")
        return
        
    # Ім'я автора
    user_details = st.session_state.get("user_details", {})
    author_name = f"{user_details.get('first_name', '')} {user_details.get('last_name', '')}".strip()
    if not author_name: author_name = user.email

    # --- ХЕЛПЕР: ГЕНЕРАЦІЯ ---
    def trigger_keyword_generation(brand, domain, industry, products):
        payload = { "brand": brand, "domain": domain, "industry": industry, "products": products }
        headers = {"virshi-auth": "hi@virshi.ai2025"}
        try:
            response = requests.post(N8N_GEN_URL, json=payload, headers=headers, timeout=60)
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        if "prompts" in data: return data["prompts"]
                        if "keywords" in data: return data["keywords"]
                        return list(data.values()) if data else []
                    elif isinstance(data, list):
                        return data
                    return []
                except ValueError: return []
            else:
                st.error(f"Error: {response.status_code}")
                return []
        except Exception as e:
            st.error(f"Connection error: {e}")
            return []

    # --- STATE ---
    if "new_proj_keywords" not in st.session_state:
        st.session_state["new_proj_keywords"] = [] 
    if "my_proj_reset_id" not in st.session_state:
        st.session_state["my_proj_reset_id"] = 0
    if "edit_proj_id" not in st.session_state:
        st.session_state["edit_proj_id"] = None

    for item in st.session_state["new_proj_keywords"]:
        if "id" not in item: item["id"] = str(uuid.uuid4())

    st.title("📂 Мої проекти")
    
    tab1, tab2 = st.tabs(["📋 Активні проекти", "➕ Створити проект"])

    # ========================================================
    # ТАБ 1: СПИСОК ПРОЕКТІВ
    # ========================================================
    with tab1:
        try:
            # Використовуємо імпортований supabase
            projs_resp = supabase.table("projects").select("*").eq("user_id", user.id).order("created_at", desc=True).execute()
            projects = projs_resp.data if projs_resp.data else []

            if not projects:
                st.info("У вас поки немає створених проектів.")
            else:
                for p in projects:
                    with st.container(border=True):
                        col_left, col_center, col_right = st.columns([1.3, 2, 2])

                        # --- 1. Лого + Назва (Editable) ---
                        with col_left:
                            # Логіка отримання чистого домену
                            clean_d = None
                            if p.get('domain'):
                                # Очищаємо домен від зайвого
                                clean_d = p['domain'].lower().replace('https://', '').replace('http://', '').replace('www.', '').split('/')[0]

                            # Формування основного URL логотипу
                            logo_url_src = None
                            if p.get('logo_url'):
                                logo_url_src = p['logo_url']
                            elif clean_d:
                                logo_url_src = f"https://cdn.brandfetch.io/{clean_d}"
                            
                            # Резервний логотип (Google Favicon)
                            backup_logo = f"https://www.google.com/s2/favicons?domain={clean_d}&sz=128" if clean_d else ""

                            # Відображення через HTML
                            if logo_url_src:
                                img_html = f'<img src="{logo_url_src}" style="width: 80px; height: 80px; object-fit: contain; border-radius: 8px; border: 1px solid #eee; padding: 5px;" onerror="this.onerror=null; this.src=\'{backup_logo}\';">'
                                st.markdown(img_html, unsafe_allow_html=True)
                            else:
                                st.markdown("🖼️ *No Logo*")
                            
                            st.write("")
                            
                            # 🔥 ЛОГІКА РЕДАГУВАННЯ НАЗВИ
                            current_name = p.get('project_name') or p.get('brand_name') or 'Без назви'
                            
                            if st.session_state["edit_proj_id"] == p['id']:
                                # Режим редагування
                                new_p_name = st.text_input("Назва", value=current_name, key=f"edit_inp_{p['id']}", label_visibility="collapsed")
                                
                                c_save, c_canc = st.columns([1, 1])
                                if c_save.button("💾", key=f"save_{p['id']}", help="Зберегти"):
                                    if new_p_name and new_p_name != current_name:
                                        try:
                                            supabase.table("projects").update({"project_name": new_p_name}).eq("id", p['id']).execute()
                                            st.toast("Назву успішно змінено!", icon="✅")
                                            st.session_state["edit_proj_id"] = None
                                            time.sleep(0.5)
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Помилка: {e}")
                                    else:
                                        st.session_state["edit_proj_id"] = None
                                        st.rerun()
                                    
                                if c_canc.button("❌", key=f"cncl_{p['id']}", help="Скасувати"):
                                    st.session_state["edit_proj_id"] = None
                                    st.rerun()
                            else:
                                # Режим перегляду (Текст + Олівець)
                                c_txt, c_btn = st.columns([0.8, 0.2])
                                with c_txt:
                                    st.markdown(f"**{current_name}**")
                                with c_btn:
                                    if st.button("✏️", key=f"edit_{p['id']}", help="Редагувати назву"):
                                        st.session_state["edit_proj_id"] = p['id']
                                        st.rerun()
                            
                            created_dt = p.get('created_at', '')[:10]
                            st.caption(f"📅 {created_dt}")
                            st.caption(f"👤 {author_name}")

                        # --- 2. Деталі ---
                        with col_center:
                            st.markdown(f"**Бренд:** {p.get('brand_name', '-')}")
                            st.markdown(f"**Домен:** `{p.get('domain', '-')}`")
                            st.markdown(f"**Галузь:** {p.get('industry', '-')}")
                            
                            prods = p.get('products') or p.get('description') or '-'
                            if len(prods) > 100: prods_display = prods[:100] + "..."
                            else: prods_display = prods
                            st.markdown(f"**Послуги:** {prods_display}")
                            
                            status_p = p.get('status', 'trial').upper()
                            color_s = "orange" if status_p == "TRIAL" else "green"
                            st.markdown(f"Статус: **:{color_s}[{status_p}]**")

                        # --- 3. Дії ---
                        with col_right:
                            try:
                                assets_resp = supabase.table("official_assets").select("domain_or_url").eq("project_id", p['id']).execute()
                                sources = [a['domain_or_url'] for a in assets_resp.data] if assets_resp.data else []
                            except: sources = []
                            
                            with st.expander(f"🔗 Джерела ({len(sources)})"):
                                for s in sources: st.markdown(f"- `{s}`")

                            try:
                                kw_resp = supabase.table("keywords").select("id", count="exact").eq("project_id", p['id']).execute()
                                kw_count = kw_resp.count if kw_resp.count is not None else len(kw_resp.data)
                            except: kw_count = 0
                            
                            st.markdown(f"**Кількість запитів:** `{kw_count}`")

                            st.write("")
                            if st.button(f"➡️ Відкрити проект", key=f"open_proj_{p['id']}", type="primary", use_container_width=True):
                                st.toast(f"🔄 Перемикання на проект: **{current_name}**...", icon="✅")
                                
                                keys_to_clear = ["focus_keyword_id", "new_proj_keywords", "analysis_results"]
                                for key in keys_to_clear:
                                    if key in st.session_state: del st.session_state[key]

                                st.session_state["current_project"] = p
                                if "menu_id_counter" not in st.session_state: st.session_state["menu_id_counter"] = 0
                                st.session_state["menu_id_counter"] += 1

                                time.sleep(0.7)
                                st.rerun()

        except Exception as e:
            st.error(f"Помилка завантаження проектів: {e}")

    # ========================================================
    # ТАБ 2: СТВОРЕННЯ ПРОЕКТУ
    # ========================================================
    with tab2:
        st.markdown("##### 🚀 Створення нового проекту")
        
        rk = st.session_state["my_proj_reset_id"]
        
        c1, c2 = st.columns(2)
        new_brand_val = c1.text_input("Назва бренду (для AI) *", key=f"mp_brand_{rk}", placeholder="Наприклад: Nova Poshta")
        new_domain_val = c2.text_input("Домен *", key=f"mp_domain_{rk}", placeholder="novaposhta.ua")
        
        c3, c4 = st.columns(2)
        def_proj_name = f"{new_brand_val} Audit" if new_brand_val else ""
        new_proj_name_val = c3.text_input("Назва проекту (Внутрішня) *", value=def_proj_name, key=f"mp_pname_{rk}")
        new_industry_val = c4.text_input("Галузь *", key=f"mp_ind_{rk}", placeholder="напр. Логістика")

        c5, c6 = st.columns([1, 2])
        new_region_val = c5.selectbox("Регіон", ["Ukraine", "USA", "Europe", "Global"], key=f"mp_region_{rk}")
        new_products_val = c6.text_area("Продукти/Послуги (Опис) *", placeholder="Основні послуги для AI...", height=68, key=f"mp_prod_{rk}")
        
        st.divider()
        st.markdown("###### 📝 Наповнення семантичного ядра (Keywords)")
        
        kw_tabs = st.tabs(["✨ AI Генерація", "📥 Імпорт (Excel/URL)", "📋 Вставити списком", "✍️ Додати вручну"])
        
        # --- TAB A: AI ---
        with kw_tabs[0]:
            st.caption("Автоматичне створення запитів на основі опису продуктів.")
            if st.button("✨ Згенерувати запити", key=f"mp_btn_gen_{rk}"):
                if new_domain_val and new_industry_val and new_products_val and new_brand_val: 
                    with st.spinner("AI аналізує бренд..."):
                        generated_kws = trigger_keyword_generation(new_brand_val, new_domain_val, new_industry_val, new_products_val)
                    if generated_kws:
                        for kw in generated_kws:
                            st.session_state["new_proj_keywords"].append({"id": str(uuid.uuid4()), "keyword": kw})
                        st.success(f"Додано {len(generated_kws)} запитів!")
                    else: st.warning("AI не повернув запитів.")
                else: st.warning("⚠️ Заповніть всі поля вище.")

        # --- TAB B: ІМПОРТ ---
        with kw_tabs[1]:
            st.caption("Завантажте файл або посилання.")
            import_source = st.radio("Джерело:", ["Файл (.xlsx)", "Посилання (URL)"], horizontal=True, key=f"mp_imp_src_{rk}")
            df_upload = None
            if import_source == "Файл (.xlsx)":
                uploaded_file = st.file_uploader("Оберіть файл", type=["xlsx", "csv"], key=f"mp_file_{rk}")
                if uploaded_file:
                    try: 
                        if uploaded_file.name.endswith('.csv'): df_upload = pd.read_csv(uploaded_file)
                        else: df_upload = pd.read_excel(uploaded_file)
                    except Exception as e: st.error(f"Помилка файлу: {e}")
            else:
                import_url = st.text_input("Посилання (CSV/Google Sheet):", key=f"mp_url_{rk}")
                if import_url:
                    try:
                        if "docs.google.com" in import_url:
                            match = re.search(r'/d/([a-zA-Z0-9-_]+)', import_url)
                            if match:
                                sheet_id = match.group(1)
                                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                                df_upload = pd.read_csv(csv_url)
                        elif import_url.endswith(".csv"): df_upload = pd.read_csv(import_url)
                        elif import_url.endswith(".xlsx"): df_upload = pd.read_excel(import_url)
                    except: st.error("Помилка URL")

            if df_upload is not None:
                target_col = df_upload.columns[0]
                cols_lower = [str(c).lower().strip() for c in df_upload.columns]
                if "keyword" in cols_lower: target_col = df_upload.columns[cols_lower.index("keyword")]
                imp_kws = df_upload[target_col].dropna().astype(str).tolist()
                if st.button(f"📥 Імпортувати {len(imp_kws)} запитів", key=f"mp_add_imp_{rk}"):
                    for kw in imp_kws:
                        st.session_state["new_proj_keywords"].append({"id": str(uuid.uuid4()), "keyword": kw})
                    st.success("Імпортовано!")
                    st.rerun()

        # --- TAB C: СПИСОК ---
        with kw_tabs[2]:
            paste_text = st.text_area("Вставте список (кожен з нового рядка)", height=150, key=f"mp_paste_{rk}")
            if st.button("📋 Додати список", key=f"mp_btn_paste_{rk}"):
                if paste_text:
                    lines = [line.strip() for line in paste_text.split('\n') if line.strip()]
                    for line in lines:
                        st.session_state["new_proj_keywords"].append({"id": str(uuid.uuid4()), "keyword": line})
                    st.success(f"Додано {len(lines)} запитів!")
                    st.rerun()

        # --- TAB D: ВРУЧНУ ---
        with kw_tabs[3]:
            c_man1, c_man2 = st.columns([4, 1])
            manual_kw = c_man1.text_input("Запит", key=f"mp_man_kw_{rk}", placeholder="Введіть запит...")
            c_man2.write("") 
            c_man2.write("") 
            if c_man2.button("➕", key=f"mp_btn_man_{rk}"):
                if manual_kw:
                    st.session_state["new_proj_keywords"].append({"id": str(uuid.uuid4()), "keyword": manual_kw})
                    st.rerun()

        # --- СПИСОК ---
        st.write("")
        st.markdown("###### 📋 Ваш список для збереження:")
        
        keywords_list = st.session_state["new_proj_keywords"]
        if not keywords_list:
            st.info("Список порожній.")
        else:
            for i, item in enumerate(keywords_list):
                unique_key = item['id']
                with st.container(border=True):
                    c_num, c_txt, c_act = st.columns([0.5, 8, 1])
                    with c_num: st.markdown(f"<div class='green-number'>{i+1}</div>", unsafe_allow_html=True)
                    with c_txt:
                        new_val = st.text_input("kw", value=item['keyword'], key=f"kw_input_{unique_key}", label_visibility="collapsed")
                        if new_val != item['keyword']:
                            for k in st.session_state["new_proj_keywords"]:
                                if k['id'] == unique_key: k['keyword'] = new_val
                    with c_act:
                        if st.button("🗑️", key=f"del_btn_{unique_key}"):
                            st.session_state["new_proj_keywords"] = [k for k in st.session_state["new_proj_keywords"] if k['id'] != unique_key]
                            st.rerun()
            
            if st.button("🗑️ Очистити весь список", key=f"mp_clear_all_{rk}", type="secondary"):
                st.session_state["new_proj_keywords"] = []
                st.rerun()

        st.divider()
        
        # --- ДІЇ ---
        col_llm, col_act = st.columns(2)
        with col_llm:
            ui_llm_options = ["OpenAI GPT", "Google Gemini", "Perplexity"]
            selected_llms = st.multiselect("Активувати LLM", ui_llm_options, default=["OpenAI GPT", "Google Gemini"], key=f"mp_llms_{rk}")
        
        with col_act:
            st.caption("Дія:")
            b1, b2 = st.columns(2)
            save_only = b1.button("💾 Зберегти проект", use_container_width=True)
            save_run = b2.button("🚀 Зберегти та Запустити", type="primary", use_container_width=True)

        if save_only or save_run:
            final_project_name = new_proj_name_val if new_proj_name_val else new_brand_val
            
            if new_domain_val and new_industry_val and new_brand_val:
                try:
                    uid = st.session_state.user.id
                    
                    # 1. Створюємо проект
                    new_proj_data = {
                        "user_id": uid, "brand_name": new_brand_val, "project_name": final_project_name,
                        "domain": new_domain_val, "industry": new_industry_val, "products": new_products_val,
                        "status": "trial", "allow_cron": True if save_run else False, "region": new_region_val,
                        "created_at": datetime.now().isoformat()
                    }
                    res_proj = supabase.table("projects").insert(new_proj_data).execute()
                    
                    if res_proj.data:
                        new_proj_id = res_proj.data[0]['id']
                        
                        # 2. Whitelist
                        try:
                            clean_d = new_domain_val.replace("https://", "").replace("http://", "").replace("www.", "").strip().rstrip("/")
                            supabase.table("official_assets").insert({"project_id": new_proj_id, "domain_or_url": clean_d, "type": "website"}).execute()
                        except: pass
                        
                        # 3. Keywords
                        final_kws_clean = [k['keyword'].strip() for k in keywords_list if k['keyword'].strip()]
                        if final_kws_clean:
                            kws_data = [{"project_id": new_proj_id, "keyword_text": kw, "is_active": True} for kw in final_kws_clean]
                            supabase.table("keywords").insert(kws_data).execute()

                        # 4. Встановлюємо проект в сесію
                        st.session_state["current_project"] = res_proj.data[0]

                        # 5. ЗАПУСК АНАЛІЗУ (ПОШТУЧНО)
                        if save_run:
                            from utils.n8n import n8n_trigger_analysis
                            
                            my_bar = st.progress(0, text="Ініціалізація...")
                            
                            total_ops = len(final_kws_clean) * len(selected_llms)
                            if total_ops == 0: total_ops = 1 
                            current_op = 0
                            
                            for kw_item in final_kws_clean:
                                for model_item in selected_llms:
                                    current_op += 1
                                    prog_val = min(current_op / total_ops, 1.0)
                                    my_bar.progress(prog_val, text=f"Аналіз: {kw_item} ({model_item})...")
                                    
                                    n8n_trigger_analysis(
                                        project_id=new_proj_id, 
                                        keywords=[kw_item], 
                                        brand_name=new_brand_val, 
                                        models=[model_item]
                                    )
                                    time.sleep(0.2) 
                            
                            my_bar.progress(1.0, text="Готово!")
                            st.toast(f"✅ Проект '{new_brand_val}' створено! Аналіз запущено.", icon="🚀")
                        else:
                            st.toast(f"✅ Проект '{new_brand_val}' успішно збережено!", icon="💾")

                        # 6. Очищення та перенаправлення
                        st.session_state["new_proj_keywords"] = []
                        st.session_state["my_proj_reset_id"] += 1
                        
                        # Примусово перекидаємо на вкладку "Мої проекти" (список)
                        st.session_state["force_redirect_to"] = "Мої проекти"
                        
                        time.sleep(1.5)
                        st.rerun()
                except Exception as e: 
                    st.error(f"Помилка створення: {e}")
            else: 
                st.warning("Заповніть обов'язкові поля.")
