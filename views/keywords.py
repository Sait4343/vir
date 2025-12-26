import pandas as pd
import streamlit as st
from datetime import datetime
import time
import io
import re
import uuid

# 🔥 Імпорт залежностей з утиліт
from utils.db import supabase
from utils.n8n import n8n_trigger_analysis

# Щоб уникнути Circular Import, імпорт show_keyword_details робимо всередині функції або
# якщо це можливо, переносимо його в окремий файл. Але для простоти зробимо Lazy Import.

def show_keywords_page():
    """
    Сторінка списку запитів.
    ВЕРСІЯ: MODULAR & STABLE.
    """
    
    # Ініціалізація лічильника
    if "bulk_update_counter" not in st.session_state:
        st.session_state["bulk_update_counter"] = 0

    # CSS Стилізація
    st.markdown("""
    <style>
        .green-number { 
            background-color: #00C896; 
            color: white; 
            width: 28px; 
            height: 28px; 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            font-weight: bold; 
            font-size: 14px; 
            margin-top: 5px; 
        }
        div[data-testid="stColumn"]:nth-of-type(3) button[kind="secondary"] {
            border: none;
            background: transparent;
            text-align: left;
            padding-left: 0;
            font-weight: 600;
            color: #31333F;
            box-shadow: none;
        }
        div[data-testid="stColumn"]:nth-of-type(3) button[kind="secondary"]:hover {
            color: #00C896;
            background: transparent;
            border: none;
            box-shadow: none;
        }
        div[data-testid="stColumn"]:nth-of-type(3) button[kind="secondary"]:active {
            color: #00C896;
            background: transparent;
            box-shadow: none;
        }
    </style>
    """, unsafe_allow_html=True)

    try:
        import pytz
        kyiv_tz = pytz.timezone('Europe/Kiev')
    except ImportError:
        kyiv_tz = None

    MODEL_MAPPING = {
        "Perplexity": "perplexity",
        "OpenAI GPT": "gpt-4o",
        "Google Gemini": "gemini-1.5-pro"
    }

    if "kw_input_count" not in st.session_state:
        st.session_state["kw_input_count"] = 1

    # --- СИНХРОНІЗАЦІЯ З БД ---
    if "current_project" in st.session_state and st.session_state["current_project"]:
        try:
            curr_id = st.session_state["current_project"]["id"]
            refresh_resp = supabase.table("projects").select("*").eq("id", curr_id).execute()
            if refresh_resp.data:
                st.session_state["current_project"] = refresh_resp.data[0]
        except Exception:
            pass 

    proj = st.session_state.get("current_project")
    if not proj:
        st.info("Спочатку створіть проект в онбордингу.")
        return

    # Якщо вибрано детальний перегляд
    if st.session_state.get("focus_keyword_id"):
        # 🔥 Lazy Import для уникнення циклічної залежності
        from views.dashboard import show_keyword_details
        show_keyword_details(st.session_state["focus_keyword_id"])
        return

    st.markdown("<h3 style='padding-top:0;'>📋 Перелік запитів</h3>", unsafe_allow_html=True)

    def format_kyiv_time(iso_str):
        if not iso_str or iso_str == "1970-01-01T00:00:00+00:00":
            return "—"
        try:
            dt_utc = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            if kyiv_tz:
                dt_kyiv = dt_utc.astimezone(kyiv_tz)
                return dt_kyiv.strftime("%d.%m %H:%M")
            else:
                return dt_utc.strftime("%d.%m %H:%M UTC")
        except:
            return iso_str

    def update_kw_field(kw_id, field, value):
        try:
            supabase.table("keywords").update({field: value}).eq("id", kw_id).execute()
        except Exception as e:
            st.error(f"Помилка оновлення: {e}")

    # ========================================================
    # 2. БЛОК РЕДАГУВАННЯ
    # ========================================================
    with st.expander("✏️ Редагування запитів", expanded=False): 
        
        tab_manual, tab_paste, tab_import, tab_export, tab_auto = st.tabs(["✍️ Ввести вручну", "📋 Вставити списком", "📥 Імпорт (Excel / URL)", "📤 Експорт (Excel)", "⚙️ Автозапуск"])

        # --- TAB 1: ВРУЧНУ ---
        with tab_manual:
            with st.container(border=True):
                st.markdown("##### 📝 Введіть нові запити")
                for i in range(st.session_state["kw_input_count"]):
                    st.text_input(f"Запит #{i+1}", key=f"new_kw_input_{i}", placeholder="Наприклад: Купити квитки...")

                col_plus, col_minus, _ = st.columns([1, 1, 5])
                with col_plus:
                    if st.button("➕ Ще рядок"):
                        st.session_state["kw_input_count"] += 1
                        st.rerun()
                with col_minus:
                    if st.session_state["kw_input_count"] > 1:
                        if st.button("➖ Прибрати"):
                            st.session_state["kw_input_count"] -= 1
                            st.rerun()

            st.divider()
            c_models, c_submit = st.columns([3, 1])
            with c_models:
                selected_models_manual = st.multiselect("LLM для першого скану:", list(MODEL_MAPPING.keys()), default=["Perplexity"], key="manual_multiselect")
            
            with c_submit:
                st.write("")
                st.write("")
                if st.button("🚀 Додати", use_container_width=True, type="primary", key="btn_add_manual"):
                    new_keywords_list = []
                    for i in range(st.session_state["kw_input_count"]):
                        val = st.session_state.get(f"new_kw_input_{i}", "").strip()
                        if val: new_keywords_list.append(val)
                    
                    if new_keywords_list:
                        try:
                            insert_data = [{
                                "project_id": proj["id"], "keyword_text": kw, "is_active": True, 
                                "is_auto_scan": False, "frequency": "daily"
                            } for kw in new_keywords_list]
                            
                            res = supabase.table("keywords").insert(insert_data).execute()
                            if res.data:
                                with st.spinner(f"Зберігаємо та запускаємо аналіз..."):
                                    for new_kw in new_keywords_list:
                                        n8n_trigger_analysis(proj["id"], [new_kw], proj.get("brand_name"), models=selected_models_manual)
                                        time.sleep(0.5) 
                                    st.success(f"Додано {len(new_keywords_list)} запитів!")
                                    st.session_state["kw_input_count"] = 1
                                    for key in list(st.session_state.keys()):
                                        if key.startswith("new_kw_input_"): del st.session_state[key]
                                    time.sleep(1)
                                    st.rerun()
                        except Exception as e:
                            st.error(f"Помилка: {e}")
                    else:
                        st.warning("Введіть хоча б один запит.")

        # --- TAB 2: ВСТАВИТИ СПИСКОМ ---
        with tab_paste:
            st.info("💡 Вставте список запитів. Кожен новий запит — з нового рядка.")
            paste_text = st.text_area("Список запитів", height=150, key="kw_paste_area", placeholder="купити квитки\nвідгуки про бренд\nнайкращі ціни")
            
            st.write("---")
            c_paste_models, c_paste_btn1, c_paste_btn2 = st.columns([2, 1.5, 1.5])
            
            with c_paste_models:
                selected_models_paste = st.multiselect("LLM для запуску:", list(MODEL_MAPPING.keys()), default=["Perplexity"], key="paste_multiselect")
            
            with c_paste_btn1:
                st.write("")
                st.write("")
                if st.button("📥 Тільки зберегти", use_container_width=True, key="btn_paste_save"):
                    if paste_text:
                        lines = [line.strip() for line in paste_text.split('\n') if line.strip()]
                        if lines:
                            try:
                                insert_data = [{
                                    "project_id": proj["id"], "keyword_text": kw, "is_active": True, 
                                    "is_auto_scan": False, "frequency": "daily"
                                } for kw in lines]
                                
                                supabase.table("keywords").insert(insert_data).execute()
                                st.success(f"Успішно збережено {len(lines)} запитів!")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Помилка збереження: {e}")
                        else:
                            st.warning("Список пустий.")
                    else:
                        st.warning("Поле пусте.")

            with c_paste_btn2:
                st.write("")
                st.write("")
                if st.button("🚀 Зберегти та Аналізувати", type="primary", use_container_width=True, key="btn_paste_run"):
                    if paste_text:
                        lines = [line.strip() for line in paste_text.split('\n') if line.strip()]
                        if lines:
                            try:
                                insert_data = [{
                                    "project_id": proj["id"], "keyword_text": kw, "is_active": True, 
                                    "is_auto_scan": False, "frequency": "daily"
                                } for kw in lines]
                                
                                res = supabase.table("keywords").insert(insert_data).execute()
                                if res.data:
                                    with st.spinner(f"Обробка {len(lines)} запитів..."):
                                        my_bar = st.progress(0, text="Запуск...")
                                        total = len(lines)
                                        for i, kw in enumerate(lines):
                                            n8n_trigger_analysis(proj["id"], [kw], proj.get("brand_name"), models=selected_models_paste)
                                            my_bar.progress((i + 1) / total)
                                            time.sleep(0.3)
                                        st.success("Успішно збережено та запущено!")
                                        time.sleep(2)
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Помилка процесу: {e}")
                        else:
                            st.warning("Список пустий.")
                    else:
                        st.warning("Поле пусте.")

        # --- TAB 3: ІМПОРТ EXCEL / URL ---
        with tab_import:
            st.info("💡 Завантажте файл .xlsx або вставте посилання на Google Sheet. **Важливо:** Для Google Sheet має бути відкрито доступ (Anyone with the link). Перша колонка має називатися **Keyword**.")
            
            import_source = st.radio("Джерело:", ["Файл (.xlsx)", "Посилання (URL)"], horizontal=True)
            df_upload = None
            
            if import_source == "Файл (.xlsx)":
                uploaded_file = st.file_uploader("Оберіть файл Excel", type=["xlsx"])
                if uploaded_file:
                    try:
                        df_upload = pd.read_excel(uploaded_file)
                    except ImportError:
                        st.error("🚨 Відсутня бібліотека `openpyxl`.")
                    except Exception as e:
                        st.error(f"Не вдалося прочитати файл: {e}")
            else: # URL
                import_url = st.text_input("Вставте посилання (Google Sheets або CSV):")
                if import_url:
                    try:
                        if "docs.google.com" in import_url:
                            match = re.search(r'/d/([a-zA-Z0-9-_]+)', import_url)
                            if match:
                                sheet_id = match.group(1)
                                csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
                                df_upload = pd.read_csv(csv_url)
                            else:
                                st.error("Не вдалося розпізнати ID Google таблиці. Перевірте посилання.")
                        elif import_url.endswith(".csv"):
                            df_upload = pd.read_csv(import_url)
                        elif import_url.endswith(".xlsx"):
                            df_upload = pd.read_excel(import_url)
                        else:
                            st.warning("Спробуємо прочитати як CSV...")
                            df_upload = pd.read_csv(import_url)
                    except Exception as e:
                        if "400" in str(e) or "403" in str(e):
                            st.error("🔒 Помилка доступу (HTTP 400/403).")
                        else:
                            st.error(f"Не вдалося завантажити: {e}")

            if df_upload is not None:
                target_col = None
                cols_lower = [str(c).lower().strip() for c in df_upload.columns]
                
                if "keyword" in cols_lower:
                    target_col = df_upload.columns[cols_lower.index("keyword")]
                elif "запит" in cols_lower:
                    target_col = df_upload.columns[cols_lower.index("запит")]
                else:
                    target_col = df_upload.columns[0] 
                
                preview_kws = df_upload[target_col].dropna().astype(str).tolist()
                st.write(f"✅ Знайдено **{len(preview_kws)}** запитів. Приклад: {preview_kws[:3]}")
                
                st.write("---")
                st.write("Оберіть дію:")
                
                c_imp_models, c_imp_btn1, c_imp_btn2 = st.columns([2, 1.5, 1.5])
                
                with c_imp_models:
                    selected_models_import = st.multiselect("LLM (тільки для кнопки аналізу):", list(MODEL_MAPPING.keys()), default=["Perplexity"], key="import_multiselect")
                
                with c_imp_btn1:
                    st.write("")
                    st.write("")
                    if st.button("📥 Тільки зберегти", use_container_width=True):
                        if preview_kws:
                            try:
                                insert_data = [{
                                    "project_id": proj["id"], "keyword_text": kw, "is_active": True, 
                                    "is_auto_scan": False, "frequency": "daily"
                                } for kw in preview_kws]
                                
                                supabase.table("keywords").insert(insert_data).execute()
                                st.success(f"Успішно збережено {len(preview_kws)} запитів!")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Помилка збереження: {e}")

                with c_imp_btn2:
                    st.write("")
                    st.write("")
                    if st.button("🚀 Зберегти та Аналізувати", type="primary", use_container_width=True):
                        if preview_kws:
                            try:
                                insert_data = [{
                                    "project_id": proj["id"], "keyword_text": kw, "is_active": True, 
                                    "is_auto_scan": False, "frequency": "daily"
                                } for kw in preview_kws]
                                
                                res = supabase.table("keywords").insert(insert_data).execute()
                                if res.data:
                                    with st.spinner(f"Обробка {len(preview_kws)} запитів..."):
                                        my_bar = st.progress(0, text="Запуск...")
                                        total = len(preview_kws)
                                        for i, kw in enumerate(preview_kws):
                                            n8n_trigger_analysis(proj["id"], [kw], proj.get("brand_name"), models=selected_models_import)
                                            my_bar.progress((i + 1) / total)
                                            time.sleep(0.3)
                                        st.success("Успішно збережено та запущено!")
                                        time.sleep(2)
                                        st.rerun()
                            except Exception as e:
                                st.error(f"Помилка процесу: {e}")

        # --- TAB 4: ЕКСПОРТ EXCEL ---
        with tab_export:
            st.write("Натисніть кнопку нижче, щоб завантажити всі запити цього проекту в Excel.")
            try:
                kws_resp = supabase.table("keywords").select("id, keyword_text, created_at").eq("project_id", proj["id"]).execute()
                if kws_resp.data:
                    df_export = pd.DataFrame(kws_resp.data)
                    scan_resp = supabase.table("scan_results").select("keyword_id, created_at").eq("project_id", proj["id"]).order("created_at", desc=True).execute()
                    
                    last_scan_map = {}
                    if scan_resp.data:
                        for s in scan_resp.data:
                            if s['keyword_id'] not in last_scan_map:
                                last_scan_map[s['keyword_id']] = s['created_at']
                    
                    df_export['last_scan_date'] = df_export['id'].map(lambda x: last_scan_map.get(x, "-"))
                    df_export['created_at'] = pd.to_datetime(df_export['created_at']).dt.strftime('%Y-%m-%d %H:%M')
                    df_export['last_scan_date'] = df_export['last_scan_date'].apply(lambda x: pd.to_datetime(x).strftime('%Y-%m-%d %H:%M') if x != "-" else "-")
                    
                    df_final = df_export[["keyword_text", "created_at", "last_scan_date"]].rename(columns={"keyword_text": "Keyword", "created_at": "Date Added", "last_scan_date": "Last Scan Date"})
                    
                    buffer = io.BytesIO()
                    try:
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            df_final.to_excel(writer, index=False, sheet_name='Keywords')
                    except:
                         try:
                             with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                                 df_final.to_excel(writer, index=False, sheet_name='Keywords')
                         except ImportError:
                             st.error("Для експорту потрібна бібліотека `xlsxwriter` або `openpyxl`.")
                             buffer = None

                    if buffer:
                        st.download_button(label="📥 Завантажити Excel", data=buffer.getvalue(), file_name=f"keywords_{proj.get('brand_name')}.xlsx", mime="application/vnd.ms-excel", type="primary")
                else:
                    st.warning("У проекті ще немає запитів для експорту.")
            except Exception as e:
                st.error(f"Помилка підготовки експорту: {e}")

        # --- TAB 5: АВТОЗАПУСК (МАСОВЕ НАЛАШТУВАННЯ) ---
        with tab_auto:
            st.markdown("##### ⚙️ Масове налаштування автозапуску")
            
            allow_cron_global = proj.get('allow_cron', False)
            if not allow_cron_global:
                st.error("🔒 Автозапуск недоступний для цього проекту. Зверніться до адміністратора.")
            else:
                st.info("Тут ви можете керувати автоскануванням для **всіх** запитів одночасно.")

                c_freq, c_btn = st.columns([2, 1.5])
                
                with c_freq:
                    freq_map = {"Щодня": "daily", "Щотижня": "weekly", "Щомісяця": "monthly"}
                    selected_freq_ui = st.selectbox("Оберіть частоту для всіх запитів:", list(freq_map.keys()))
                    selected_freq_db = freq_map[selected_freq_ui]

                with c_btn:
                    st.write("") 
                    st.write("")
                    
                    if st.button("✅ Застосувати частоту та Увімкнути", type="primary", use_container_width=True):
                        try:
                            supabase.table("keywords").update({
                                "is_auto_scan": True,
                                "frequency": selected_freq_db
                            }).eq("project_id", proj["id"]).execute()
                            
                            st.session_state["bulk_update_counter"] += 1
                            
                            st.success(f"Оновлено! Всі запити будуть скануватися: {selected_freq_ui}")
                            time.sleep(1)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Помилка оновлення: {e}")

                if st.button("⛔ Вимкнути автосканування для всіх", use_container_width=True):
                      try:
                        supabase.table("keywords").update({
                            "is_auto_scan": False
                        }).eq("project_id", proj["id"]).execute()

                        st.session_state["bulk_update_counter"] += 1
                        
                        st.warning("Автосканування вимкнено для всіх запитів.")
                        time.sleep(1)
                        st.rerun()
                      except Exception as e:
                        st.error(f"Помилка: {e}")
                
                st.markdown("---")
                st.markdown("""
                **ℹ️ Як це працює:**
                1. **✅ Застосувати:** Активує автозапуск (`ON`) і встановлює обрану частоту для **всіх** запитів.
                2. **⛔ Вимкнути всі:** Деактивує автозапуск (`OFF`) для всіх запитів.
                """)

    st.divider()
    
    # ========================================================
    # 3. ОТРИМАННЯ ДАНИХ (ДЛЯ ТАБЛИЦІ НИЖЧЕ)
    # ========================================================
    try:
        keywords = supabase.table("keywords").select("*").eq("project_id", proj["id"]).order("created_at", desc=True).execute().data
        last_scans_resp = supabase.table("scan_results").select("keyword_id, created_at").eq("project_id", proj["id"]).order("created_at", desc=True).execute()
        
        last_scan_map = {}
        if last_scans_resp.data:
            for s in last_scans_resp.data:
                if s['keyword_id'] not in last_scan_map:
                    last_scan_map[s['keyword_id']] = s['created_at']
        
        for k in keywords:
            k['last_scan_date'] = last_scan_map.get(k['id'], "1970-01-01T00:00:00+00:00")

    except Exception as e:
        st.error(f"Помилка завантаження: {e}")
        keywords = []

    if not keywords:
        st.info("Список порожній.")
        return

    update_suffix = st.session_state.get("bulk_update_counter", 0)

    # Функція-фрагмент (оновлюється незалежно)
    @st.fragment(run_every=5)
    def render_live_dashboard(keywords_data, proj_data, suffix_val):
        
        # --- LIVE DATA FETCH ---
        try:
            fresh_scans = supabase.table("scan_results").select("keyword_id, created_at").eq("project_id", proj_data["id"]).order("created_at", desc=True).execute()
            fresh_map = {}
            if fresh_scans.data:
                for s in fresh_scans.data:
                    if s['keyword_id'] not in fresh_map:
                        fresh_map[s['keyword_id']] = s['created_at']
            
            for k in keywords_data:
                k['last_scan_date'] = fresh_map.get(k['id'], "1970-01-01T00:00:00+00:00")
        except Exception:
            pass

        # --- SORTING ---
        c_sort, _ = st.columns([2, 4])
        with c_sort:
            sort_option = st.selectbox("Сортувати за:", 
                                     ["Найновіші (Додані)", "Найстаріші (Додані)", "Нещодавно проскановані", "Давно не скановані"], 
                                     label_visibility="collapsed")

        sorted_kws = keywords_data.copy()
        if sort_option == "Найновіші (Додані)": sorted_kws.sort(key=lambda x: x['created_at'], reverse=True)
        elif sort_option == "Найстаріші (Додані)": sorted_kws.sort(key=lambda x: x['created_at'], reverse=False)
        elif sort_option == "Нещодавно проскановані": sorted_kws.sort(key=lambda x: x['last_scan_date'], reverse=True)
        elif sort_option == "Давно не скановані": sorted_kws.sort(key=lambda x: x['last_scan_date'], reverse=False)

        current_page_ids = [str(k['id']) for k in sorted_kws]

        # --- STATE CALLBACKS ---
        def master_checkbox_change():
            new_state = st.session_state.select_all_master_key
            for kid in current_page_ids:
                st.session_state[f"chk_{kid}"] = new_state

        def child_checkbox_change():
            all_selected = True
            for kid in current_page_ids:
                if not st.session_state.get(f"chk_{kid}", False):
                    all_selected = False
                    break
            st.session_state.select_all_master_key = all_selected

        for kid in current_page_ids:
            key = f"chk_{kid}"
            if key not in st.session_state:
                st.session_state[key] = False

        if "select_all_master_key" not in st.session_state:
            st.session_state.select_all_master_key = False

        # --- ПАНЕЛЬ ДІЙ ---
        with st.container(border=True):
            c_check, c_models, c_btn = st.columns([0.5, 3, 1.5])
            
            with c_check:
                st.write("") 
                st.checkbox("Всі", key="select_all_master_key", on_change=master_checkbox_change)
            
            with c_models:
                all_models = list(MODEL_MAPPING.keys())
                bulk_models = st.multiselect(
                    "ЛЛМ для запуску:", 
                    all_models, 
                    default=all_models, 
                    label_visibility="collapsed", 
                    key="bulk_models_selector_v6"
                )
            
            with c_btn:
                if st.button("🚀 Аналізувати обрані", use_container_width=True, type="primary"):
                    selected_texts = []
                    for k in sorted_kws:
                        if st.session_state.get(f"chk_{k['id']}", False):
                            selected_texts.append(k['keyword_text'])
                    
                    if selected_texts:
                        try:
                            if 'n8n_trigger_analysis' in globals():
                                my_bar = st.progress(0, text="Ініціалізація...")
                                total = len(selected_texts)
                                for i, txt in enumerate(selected_texts):
                                    my_bar.progress((i / total), text=f"Відправка: {txt}...")
                                    n8n_trigger_analysis(proj_data["id"], [txt], proj_data.get("brand_name"), models=bulk_models)
                                    time.sleep(0.2)
                                my_bar.progress(1.0, text="Готово!")
                                st.success(f"Запущено {total} завдань.")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Функція запуску не знайдена.")
                        except Exception as e:
                            st.error(f"Помилка: {e}")
                    else:
                        st.warning("Оберіть хоча б один запит.")

        # --- ТАБЛИЦЯ ---
        h_chk, h_num, h_txt, h_cron, h_date, h_act = st.columns([0.4, 0.5, 3.2, 2, 1.2, 1.3])
        h_txt.markdown("**Запит**")
        h_cron.markdown("**Автозапуск**")
        h_date.markdown("**Останній аналіз**")
        h_act.markdown("**Видалити**")

        allow_cron_global = proj_data.get('allow_cron', False)

        for idx, k in enumerate(sorted_kws, start=1):
            k_id_str = str(k['id'])
            
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([0.4, 0.5, 3.2, 2, 1.2, 1.3])
                
                with c1:
                    st.write("") 
                    st.checkbox("", key=f"chk_{k_id_str}", on_change=child_checkbox_change)
                
                with c2:
                    st.markdown(f"<div class='green-number'>{idx}</div>", unsafe_allow_html=True)
                
                with c3:
                    if st.button(k['keyword_text'], key=f"lnk_{k_id_str}", help="Деталі"):
                        st.session_state["focus_keyword_id"] = k["id"]
                        st.rerun()
                
                with c4:
                    cron_c1, cron_c2 = st.columns([0.8, 1.2])
                    is_auto_db = k.get('is_auto_scan', False)
                    
                    with cron_c1:
                        if allow_cron_global:
                            toggle_key = f"auto_{k_id_str}_{suffix_val}"
                            new_auto = st.toggle("Авто", value=is_auto_db, key=toggle_key, label_visibility="collapsed")
                            if new_auto != is_auto_db:
                                update_kw_field(k['id'], "is_auto_scan", new_auto)
                        else:
                            st.toggle("Авто", value=False, key=f"auto_dis_{k_id_str}", disabled=True, label_visibility="collapsed")
                            st.caption("🔒")

                    with cron_c2:
                        if allow_cron_global and (is_auto_db or new_auto): 
                            current_freq = k.get('frequency', 'daily')
                            freq_options = ["daily", "weekly", "monthly"]
                            try: idx_f = freq_options.index(current_freq)
                            except: idx_f = 0
                            
                            freq_key = f"freq_{k_id_str}_{suffix_val}"
                            new_freq = st.selectbox("Freq", freq_options, index=idx_f, key=freq_key, label_visibility="collapsed")
                            if new_freq != current_freq:
                                update_kw_field(k['id'], "frequency", new_freq)

                with c5:
                    st.write("")
                    date_iso = k.get('last_scan_date')
                    formatted_date = format_kyiv_time(date_iso)
                    st.caption(f"{formatted_date}")

                with c6:
                    st.write("")
                    del_confirm_key = f"del_confirm_{k_id_str}"
                    if del_confirm_key not in st.session_state: st.session_state[del_confirm_key] = False

                    if not st.session_state[del_confirm_key]:
                        if st.button("🗑️", key=f"pre_del_{k_id_str}"):
                            st.session_state[del_confirm_key] = True
                            st.rerun()
                    else:
                        dc1, dc2 = st.columns(2)
                        if dc1.button("✅", key=f"yes_del_{k_id_str}", type="primary"):
                            try:
                                supabase.table("scan_results").delete().eq("keyword_id", k["id"]).execute()
                                supabase.table("keywords").delete().eq("id", k["id"]).execute()
                                st.success("OK")
                                st.session_state[del_confirm_key] = False
                                time.sleep(0.5)
                                st.rerun()
                            except:
                                st.error("Error")
                        if dc2.button("❌", key=f"no_del_{k_id_str}"):
                            st.session_state[del_confirm_key] = False
                            st.rerun()

    # Запускаємо фрагмент
    render_live_dashboard(keywords, proj, update_suffix)
