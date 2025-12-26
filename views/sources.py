import pandas as pd
import plotly.express as px
import streamlit as st
import time
from urllib.parse import urlparse

# 🔥 Імпорт підключення до БД (важливо!)
from utils.db import supabase

def show_sources_page():
    """
    Сторінка джерел.
    ВЕРСІЯ: MODULAR & STABLE.
    """

    # --- ПЕРЕВІРКА ПРОЕКТУ ---
    proj = st.session_state.get("current_project")
    if not proj:
        st.info("Спочатку оберіть проект.")
        return

    # --- CSS ---
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
    </style>
    """, unsafe_allow_html=True)

    st.title("🔗 Джерела")

    # --- MAPPING ТИПІВ (UI -> DB) ---
    TYPE_UI_TO_DB = {
        "Веб-сайт": "website",
        "Соціальні мережі": "social",
        "Стаття": "article",
        "Інше": "other"
    }
    # Зворотній мапінг (DB -> UI)
    TYPE_DB_TO_UI = {v: k for k, v in TYPE_UI_TO_DB.items()}

    # ==============================================================================
    # 1. ОТРИМАННЯ ДАНИХ (Скан результати)
    # ==============================================================================
    try:
        # Keywords
        kw_resp = supabase.table("keywords").select("id, keyword_text").eq("project_id", proj["id"]).execute()
        kw_map = {k['id']: k['keyword_text'] for k in kw_resp.data} if kw_resp.data else {}

        # Scan Results
        scan_resp = supabase.table("scan_results")\
            .select("id, provider, created_at, keyword_id")\
            .eq("project_id", proj["id"])\
            .execute()
        
        scan_meta = {} 
        scan_ids = []
        
        PROVIDER_MAP = {
            "perplexity": "Perplexity",
            "gpt-4o": "OpenAI GPT", "gpt-4": "OpenAI GPT",
            "gemini-1.5-pro": "Google Gemini", "gemini": "Google Gemini"
        }

        if scan_resp.data:
            for s in scan_resp.data:
                scan_ids.append(s['id'])
                raw_p = s.get('provider', '').lower()
                clean_p = "Інше"
                for k, v in PROVIDER_MAP.items():
                    if k in raw_p:
                        clean_p = v
                        break
                
                scan_meta[s['id']] = {
                    'provider': clean_p,
                    'date': s['created_at'],
                    'keyword_text': kw_map.get(s['keyword_id'], "Невідомий запит")
                }
        
        # Extracted Sources
        df_master = pd.DataFrame()
        if scan_ids:
            # Читаємо батчами, якщо ID багато, але для простоти тут один запит (можна оптимізувати пізніше)
            sources_resp = supabase.table("extracted_sources").select("*").in_("scan_result_id", scan_ids).execute()
            if sources_resp.data:
                df_master = pd.DataFrame(sources_resp.data)
                df_master['provider'] = df_master['scan_result_id'].map(lambda x: scan_meta.get(x, {}).get('provider', 'Інше'))
                df_master['keyword_text'] = df_master['scan_result_id'].map(lambda x: scan_meta.get(x, {}).get('keyword_text', ''))
                df_master['scan_date'] = df_master['scan_result_id'].map(lambda x: scan_meta.get(x, {}).get('date'))
                
                if 'domain' not in df_master.columns:
                    df_master['domain'] = df_master['url'].apply(lambda x: urlparse(x).netloc if x else "unknown")

    except Exception as e:
        st.error(f"Помилка завантаження даних: {e}")
        df_master = pd.DataFrame()

    # ==============================================================================
    # 2. WHITELIST LOGIC (ПРАВИЛЬНЕ ЧИТАННЯ)
    # ==============================================================================
    try:
        # 🔥 FIX: Читаємо з таблиці official_assets
        oa_resp = supabase.table("official_assets").select("domain_or_url, type").eq("project_id", proj["id"]).execute()
        raw_assets = oa_resp.data if oa_resp.data else []
    except Exception as e:
        raw_assets = []

    # Формуємо список для логіки (для підрахунку)
    assets_list_dicts = []
    for item in raw_assets:
        # Конвертуємо тип з БД в UI (english -> ukrainian)
        db_type = item.get("type", "website")
        ui_type = TYPE_DB_TO_UI.get(db_type, "Веб-сайт")
        
        assets_list_dicts.append({
            "Домен": item.get("domain_or_url", ""), 
            "Мітка": ui_type
        })
    
    OFFICIAL_DOMAINS = [d["Домен"].lower().strip() for d in assets_list_dicts if d["Домен"]]

    # Функція перевірки
    def check_is_official(url):
        if not url: return False
        u_str = str(url).lower()
        for od in OFFICIAL_DOMAINS:
            if od in u_str: return True
        return False

    if not df_master.empty:
        df_master['is_official_dynamic'] = df_master['url'].apply(check_is_official)

    # ==============================================================================
    # 3. ВКЛАДКИ
    # ==============================================================================
    tab1, tab2, tab3 = st.tabs(["📊 Офіційні ресурси бренду", "🌐 Ренкінг доменів", "🔗 Посилання"])

    # --- TAB 1: АНАЛІЗ ОХОПЛЕННЯ ---
    with tab1:
        st.markdown("#### 📊 Аналіз охоплення офіційних ресурсів")
        
        if not df_master.empty:
            total_rows = len(df_master)
            off_rows = df_master[df_master['is_official_dynamic'] == True]
            ext_rows = df_master[df_master['is_official_dynamic'] == False]
            
            def get_counts(df_sub):
                cnt = len(df_sub)
                if cnt == 0: return 0, 0, 0, 0
                p_c = len(df_sub[df_sub['provider'] == 'Perplexity'])
                g_c = len(df_sub[df_sub['provider'] == 'OpenAI GPT'])
                gem_c = len(df_sub[df_sub['provider'] == 'Google Gemini'])
                return cnt, p_c, g_c, gem_c

            tot_all, tot_p, tot_g, tot_gem = get_counts(df_master)
            off_all, off_p, off_g, off_gem = get_counts(off_rows)
            
            c_chart, c_stats = st.columns([2.5, 1.5], vertical_alignment="center")
            
            with c_chart:
                if total_rows > 0:
                    fig = px.pie(
                        names=["Офіційні", "Зовнішні"], 
                        values=[off_all, len(ext_rows)],
                        hole=0.55, 
                        color_discrete_sequence=["#00C896", "#E0E0E0"]
                    )
                    fig.update_layout(margin=dict(t=10, b=10, l=10, r=10), height=350, showlegend=True)
                    fig.update_traces(textposition='inside', textinfo='percent+label')
                    st.plotly_chart(fig, use_container_width=True, key="unique_chart_key_sources_1")
                else:
                    st.info("Немає даних.")

            with c_stats:
                st.markdown(f"""
                <div style="margin-bottom: 20px; padding:20px; border:1px solid #eee; border-radius:12px; background:white; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                    <div style="color:#888; font-size:13px; font-weight:700; text-transform:uppercase; margin-bottom:5px;">Всього посилань</div>
                    <div style="font-size:32px; font-weight:800; color:#333; line-height:1;">{tot_all}</div>
                    <div style="margin-top:10px; font-size:12px; color:#555; display:flex; flex-direction:column; gap:3px;">
                        <div>🔹 Perplexity: <b>{tot_p}</b></div>
                        <div>🔸 OpenAI GPT: <b>{tot_g}</b></div>
                        <div>✨ Google Gemini: <b>{tot_gem}</b></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                st.markdown(f"""
                <div style="padding:20px; border:1px solid #00C896; border-radius:12px; background:#f0fdf9; box-shadow: 0 2px 5px rgba(0,200,150,0.1);">
                    <div style="color:#007a5c; font-size:13px; font-weight:700; text-transform:uppercase; margin-bottom:5px;">З них офіційні</div>
                    <div style="font-size:32px; font-weight:800; color:#00C896; line-height:1;">{off_all}</div>
                    <div style="margin-top:10px; font-size:12px; color:#005c45; display:flex; flex-direction:column; gap:3px;">
                        <div>🔹 Perplexity: <b>{off_p}</b></div>
                        <div>🔸 OpenAI GPT: <b>{off_g}</b></div>
                        <div>✨ Google Gemini: <b>{off_gem}</b></div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

        else:
            st.info("Дані сканування відсутні.")

        st.divider()

        # --- РЕДАКТОР WHITELIST ---
        st.subheader("⚙️ Керування списком (Whitelist)")
        
        if "edit_whitelist_mode" not in st.session_state:
            st.session_state["edit_whitelist_mode"] = False
        
        # Ініціалізація змінної для редагування
        if "temp_assets" not in st.session_state:
            st.session_state["temp_assets"] = []

        # --- ВІДОБРАЖЕННЯ ТАБЛИЦІ (View Mode) ---
        if not st.session_state["edit_whitelist_mode"]:
            # Готуємо DataFrame для перегляду
            if assets_list_dicts:
                df_assets = pd.DataFrame(assets_list_dicts)
            else:
                df_assets = pd.DataFrame(columns=["Домен", "Мітка"])

            # Рахуємо статистику
            if not df_master.empty:
                def get_stat_whitelist(dom):
                    matches = df_master[df_master['url'].astype(str).str.contains(dom.lower(), case=False, na=False)]
                    return len(matches)
                df_assets['Згадок'] = df_assets['Домен'].apply(get_stat_whitelist)
            else:
                df_assets['Згадок'] = 0

            st.dataframe(
                df_assets,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Домен": st.column_config.TextColumn("Домен / URL", width="medium"),
                    "Мітка": st.column_config.TextColumn("Тип ресурсу", width="small"),
                    "Згадок": st.column_config.NumberColumn("Знайдено разів", format="%d")
                }
            )
            
            if st.button("✏️ Редагувати список"):
                st.session_state["edit_whitelist_mode"] = True
                # Завантажуємо поточні дані в temp_assets для редагування
                st.session_state["temp_assets"] = assets_list_dicts.copy()
                st.rerun()
        
        # --- РЕЖИМ РЕДАГУВАННЯ ---
        else:
            st.info("Додайте або видаліть домени. Натисніть 'Зберегти' для застосування змін.")
            
            # Якщо список пустий, додаємо один порожній рядок
            if not st.session_state["temp_assets"]:
                st.session_state["temp_assets"].append({"Домен": "", "Мітка": "Веб-сайт"})

            # Відображаємо список карток
            for i, asset in enumerate(st.session_state["temp_assets"]):
                with st.container(border=True):
                    c_num, c_dom, c_type, c_del = st.columns([0.5, 5, 3, 1])
                    
                    with c_num:
                        st.markdown(f"<div class='green-number'>{i+1}</div>", unsafe_allow_html=True)
                    
                    with c_dom:
                        new_domain = st.text_input(
                            "Домен", 
                            value=asset["Домен"], 
                            key=f"asset_dom_{i}", 
                            label_visibility="collapsed",
                            placeholder="example.com"
                        )
                        st.session_state["temp_assets"][i]["Домен"] = new_domain
                    
                    with c_type:
                        new_type = st.selectbox(
                            "Тип", 
                            options=list(TYPE_UI_TO_DB.keys()), 
                            index=list(TYPE_UI_TO_DB.keys()).index(asset["Мітка"]) if asset["Мітка"] in TYPE_UI_TO_DB else 0,
                            key=f"asset_type_{i}", 
                            label_visibility="collapsed"
                        )
                        st.session_state["temp_assets"][i]["Мітка"] = new_type

                    with c_del:
                        if st.button("🗑️", key=f"del_asset_{i}"):
                            st.session_state["temp_assets"].pop(i)
                            st.rerun()

            # Кнопка додавання
            if st.button("➕ Додати джерело"):
                st.session_state["temp_assets"].append({"Домен": "", "Мітка": "Веб-сайт"})
                st.rerun()

            st.divider()

            # Кнопки дії
            c1, c2 = st.columns([1, 4])
            with c1:
                if st.button("💾 Зберегти", type="primary"):
                    try:
                        # 1. Видаляємо старі записи
                        supabase.table("official_assets").delete().eq("project_id", proj["id"]).execute()
                        
                        # 2. Формуємо нові дані (конвертуємо UI -> DB)
                        insert_data = []
                        for item in st.session_state["temp_assets"]:
                            d_val = str(item["Домен"]).strip()
                            if d_val:
                                db_type_val = TYPE_UI_TO_DB.get(item["Мітка"], "website")
                                
                                insert_data.append({
                                    "project_id": proj["id"],
                                    "domain_or_url": d_val,
                                    "type": db_type_val
                                })
                        
                        # 3. Вставляємо
                        if insert_data:
                            supabase.table("official_assets").insert(insert_data).execute()
                            
                        st.success("Список оновлено!")
                        st.session_state["edit_whitelist_mode"] = False
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Помилка збереження: {e}")
            with c2:
                if st.button("❌ Скасувати"):
                    st.session_state["edit_whitelist_mode"] = False
                    st.rerun()

    # --- TAB 2: РЕНКІНГ ---
    with tab2:
        st.markdown("#### 🏆 Ренкінг доменів")
        if not df_master.empty:
            all_kws = sorted(df_master['keyword_text'].unique())
            sel_kws_rank = st.multiselect("🔍 Фільтр по запитах:", all_kws, key="rank_kw_filter")
            
            df_rank_view = df_master.copy()
            if sel_kws_rank:
                df_rank_view = df_rank_view[df_rank_view['keyword_text'].isin(sel_kws_rank)]
            
            if not df_rank_view.empty:
                pivot_df = df_rank_view.pivot_table(
                    index='domain', columns='provider', values='mention_count', aggfunc='sum', fill_value=0
                ).reset_index()
                
                pivot_df['Всього'] = pivot_df.sum(axis=1, numeric_only=True)
                for col in ["Perplexity", "OpenAI GPT", "Google Gemini"]:
                    if col not in pivot_df.columns: pivot_df[col] = 0
                
                def get_meta(dom):
                    is_off = "Зовнішній"
                    for od in OFFICIAL_DOMAINS:
                        if od in dom.lower():
                            is_off = "Офіційний"
                            break
                    dates = df_rank_view[df_rank_view['domain'] == dom]['scan_date']
                    first = dates.min() if not dates.empty else None
                    first_str = pd.to_datetime(first).strftime("%Y-%m-%d") if first else "-"
                    return is_off, first_str

                pivot_df[['Тип', 'Вперше знайдено']] = pivot_df['domain'].apply(lambda x: pd.Series(get_meta(x)))
                pivot_df = pivot_df.sort_values("Всього", ascending=False).reset_index(drop=True)
                
                cols_order = ["domain", "Тип", "Всього", "Perplexity", "OpenAI GPT", "Google Gemini", "Вперше знайдено"]
                final_cols = [c for c in cols_order if c in pivot_df.columns]
                
                st.dataframe(
                    pivot_df[final_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "domain": "Домен",
                        "Всього": st.column_config.NumberColumn(format="%d"),
                        "Perplexity": st.column_config.NumberColumn(format="%d"),
                        "OpenAI GPT": st.column_config.NumberColumn(format="%d"),
                        "Google Gemini": st.column_config.NumberColumn(format="%d"),
                    }
                )
            else:
                st.warning("Даних немає.")
        else:
            st.info("Дані відсутні.")

    # --- TAB 3: ПОСИЛАННЯ ---
    with tab3:
        st.markdown("#### 🔗 Детальний список посилань")
        if not df_master.empty:
            c_f1, c_f2 = st.columns([1, 1])
            with c_f1: sel_kws_links = st.multiselect("🔍 Фільтр по запитах:", all_kws, key="links_kw_filter")
            with c_f2: search_url = st.text_input("🔎 Пошук URL:", key="links_search")
            
            c_f3, c_f4 = st.columns(2)
            with c_f3: type_filter = st.selectbox("Тип ресурсу:", ["Всі", "Офіційні", "Зовнішні"], key="links_type_filter")
            
            df_links_view = df_master.copy()
            if sel_kws_links: df_links_view = df_links_view[df_links_view['keyword_text'].isin(sel_kws_links)]
            if search_url: df_links_view = df_links_view[df_links_view['url'].astype(str).str.contains(search_url, case=False)]
            if type_filter == "Офіційні": df_links_view = df_links_view[df_links_view['is_official_dynamic'] == True]
            elif type_filter == "Зовнішні": df_links_view = df_links_view[df_links_view['is_official_dynamic'] == False]

            if not df_links_view.empty:
                pivot_links = df_links_view.pivot_table(
                    index=['url', 'domain', 'is_official_dynamic'],
                    columns='provider', values='mention_count', aggfunc='sum', fill_value=0
                ).reset_index()
                
                pivot_links['Всього'] = pivot_links.sum(axis=1, numeric_only=True)
                for col in ["Perplexity", "OpenAI GPT", "Google Gemini"]:
                    if col not in pivot_links.columns: pivot_links[col] = 0
                
                pivot_links['Тип'] = pivot_links['is_official_dynamic'].apply(lambda x: "Офіційні" if x else "Зовнішні")
                pivot_links = pivot_links.sort_values("Всього", ascending=False).reset_index(drop=True)
                
                cols_order = ["url", "domain", "Тип", "Всього", "Perplexity", "OpenAI GPT", "Google Gemini"]
                final_cols = [c for c in cols_order if c in pivot_links.columns]
                
                st.dataframe(
                    pivot_links[final_cols],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "url": st.column_config.LinkColumn("Посилання", width="large"),
                        "Всього": st.column_config.NumberColumn(format="%d"),
                        "Perplexity": st.column_config.NumberColumn(format="%d"),
                        "OpenAI GPT": st.column_config.NumberColumn(format="%d"),
                        "Google Gemini": st.column_config.NumberColumn(format="%d"),
                    }
                )
            else:
                st.warning("Нічого не знайдено.")
        else:
            st.info("Дані відсутні.")
