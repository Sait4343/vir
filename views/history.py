import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import pytz
import math

# 🔥 Імпорт підключення до БД (замість globals)
from utils.db import supabase

def show_history_page():
    """
    Сторінка історії сканувань.
    ВЕРСІЯ: MODULAR + PROFILES MAPPING.
    1. Бере user_email з scan_results.
    2. Шукає власника в таблиці 'profiles'.
    3. Формує ПІБ (first_name + last_name).
    """

    # Налаштування часового поясу
    KYIV_TZ = pytz.timezone('Europe/Kiev')

    # Функція для скидання сторінки
    def reset_page():
        st.session_state.history_page_number = 1

    if 'history_page_number' not in st.session_state:
        st.session_state.history_page_number = 1

    # --- ПЕРЕВІРКА ПРОЕКТУ ---
    proj = st.session_state.get("current_project")
    if not proj:
        st.info("Спочатку оберіть проект.")
        return

    st.title("📜 Історія сканувань")

    # --- 2. ОТРИМАННЯ ДАНИХ ---
    with st.spinner("Завантаження історії..."):
        try:
            # 1. Keywords
            kw_resp = supabase.table("keywords").select("id, keyword_text").eq("project_id", proj["id"]).execute()
            kw_map = {k['id']: k['keyword_text'] for k in kw_resp.data} if kw_resp.data else {}

            # 2. Scans (Беремо user_email)
            scans_resp = supabase.table("scan_results")\
                .select("id, created_at, provider, keyword_id, user_email")\
                .eq("project_id", proj["id"])\
                .order("created_at", desc=True)\
                .limit(1000)\
                .execute()
            
            scans_data = scans_resp.data if scans_resp.data else []
            
            if not scans_data:
                st.info("Історія сканувань порожня.")
                return

            scan_ids = [s['id'] for s in scans_data]

            # 🔥 3. ОТРИМАННЯ ПІБ З ТАБЛИЦІ PROFILES
            unique_emails = list(set([s['user_email'] for s in scans_data if s.get('user_email')]))
            email_to_name_map = {}

            if unique_emails:
                try:
                    # ⚠️ Змінено таблицю на 'profiles'
                    p_resp = supabase.table("profiles")\
                        .select("email, first_name, last_name")\
                        .in_("email", unique_emails)\
                        .execute()
                    
                    if p_resp.data:
                        for p in p_resp.data:
                            f_n = p.get('first_name', '') or ''
                            l_n = p.get('last_name', '') or ''
                            full_n = f"{f_n} {l_n}".strip()
                            
                            # Якщо ім'я знайдене, записуємо його в мапу
                            if full_n and p.get('email'):
                                email_to_name_map[p['email']] = full_n
                except Exception:
                    # Якщо таблиці profiles немає або помилка доступу
                    pass

            # 4. Mentions
            # Розбиваємо на чанки, якщо ID дуже багато
            chunk_size = 200
            all_mentions = []
            all_sources = []
            
            for i in range(0, len(scan_ids), chunk_size):
                chunk = scan_ids[i:i + chunk_size]
                m_resp = supabase.table("brand_mentions").select("scan_result_id, is_my_brand, mention_count").in_("scan_result_id", chunk).execute()
                if m_resp.data: all_mentions.extend(m_resp.data)
                
                s_resp = supabase.table("extracted_sources").select("scan_result_id, is_official").in_("scan_result_id", chunk).execute()
                if s_resp.data: all_sources.extend(s_resp.data)

            mentions_df = pd.DataFrame(all_mentions)
            sources_df = pd.DataFrame(all_sources)

        except Exception as e:
            if "column scan_results.user_email does not exist" in str(e):
                st.error("⚠️ Відсутня колонка `user_email` у таблиці scan_results.")
            else:
                st.error(f"Помилка завантаження даних: {e}")
            return

    # --- 3. ОБРОБКА ДАНИХ ---
    df_scans = pd.DataFrame(scans_data)

    # 🔥 ЛОГІКА ІНІЦІАТОРА
    def resolve_initiator(email_val):
        # 1. Якщо емейл пустий -> Авто
        if pd.isna(email_val) or str(email_val).strip() == "" or str(email_val).lower() == "none":
            return "🤖 Автосканування"
        
        # 2. Якщо ми знайшли ім'я у profiles -> Виводимо ПІБ
        if email_val in email_to_name_map:
            return f"👤 {email_to_name_map[email_val]}"
        
        # 3. Якщо імені не знайшли (профіль не заповнений) -> Виводимо Email
        return f"👤 {email_val}"
    
    # Застосовуємо, якщо колонка є
    if 'user_email' in df_scans.columns:
        df_scans['initiator'] = df_scans['user_email'].apply(resolve_initiator)
    else:
        df_scans['initiator'] = "🤖 Автосканування"

    # Провайдери
    PROVIDER_MAP = {"gpt-4o": "OpenAI", "gpt-4-turbo": "OpenAI", "gemini-1.5-pro": "Gemini", "perplexity": "Perplexity"}
    df_scans['provider'] = df_scans['provider'].replace(PROVIDER_MAP)
    
    # Ключові слова
    df_scans['keyword'] = df_scans['keyword_id'].map(kw_map).fillna("Видалений запит")
    
    # Timezone Fix
    df_scans['created_at_dt'] = pd.to_datetime(df_scans['created_at'])
    if df_scans['created_at_dt'].dt.tz is None:
        df_scans['created_at_dt'] = df_scans['created_at_dt'].dt.tz_localize('UTC')
    df_scans['created_at_dt'] = df_scans['created_at_dt'].dt.tz_convert(KYIV_TZ)
    
    # Merge (Безпечне злиття)
    if not mentions_df.empty:
        brands_count = mentions_df.groupby('scan_result_id').size().reset_index(name='total_brands')
        my_mentions = mentions_df[mentions_df['is_my_brand'] == True].groupby('scan_result_id')['mention_count'].sum().reset_index(name='my_mentions_count')
        
        df_scans = df_scans.merge(brands_count, left_on='id', right_on='scan_result_id', how='left')
        if 'scan_result_id' in df_scans.columns: df_scans = df_scans.drop(columns=['scan_result_id'])
        
        df_scans = df_scans.merge(my_mentions, left_on='id', right_on='scan_result_id', how='left')
        if 'scan_result_id' in df_scans.columns: df_scans = df_scans.drop(columns=['scan_result_id'])
    else:
        df_scans['total_brands'] = 0
        df_scans['my_mentions_count'] = 0

    if not sources_df.empty:
        links_count = sources_df.groupby('scan_result_id').size().reset_index(name='total_links')
        off_count = sources_df[sources_df['is_official'] == True].groupby('scan_result_id').size().reset_index(name='official_links')
        
        df_scans = df_scans.merge(links_count, left_on='id', right_on='scan_result_id', how='left')
        if 'scan_result_id' in df_scans.columns: df_scans = df_scans.drop(columns=['scan_result_id'])
        
        df_scans = df_scans.merge(off_count, left_on='id', right_on='scan_result_id', how='left')
        if 'scan_result_id' in df_scans.columns: df_scans = df_scans.drop(columns=['scan_result_id'])
    else:
        df_scans['total_links'] = 0
        df_scans['official_links'] = 0

    df_scans = df_scans.fillna(0)

    # --- 4. ФІЛЬТРИ ---
    st.markdown("### 🔍 Фільтрація")
    
    now_kyiv = datetime.now(KYIV_TZ).date()
    
    if not df_scans.empty:
        min_date_avail = df_scans['created_at_dt'].min().date()
        max_date_avail = max(df_scans['created_at_dt'].max().date(), now_kyiv) + timedelta(days=1)
    else:
        min_date_avail = now_kyiv
        max_date_avail = now_kyiv + timedelta(days=1)

    c1, c2, c3, c4 = st.columns([1, 1.2, 1, 0.8])
    
    with c1:
        all_providers = df_scans['provider'].unique().tolist()
        sel_providers = st.multiselect("Модель", all_providers, default=all_providers, on_change=reset_page)
    
    with c2:
        default_start = now_kyiv - timedelta(days=30)
        sel_dates = st.date_input(
            "Період",
            value=(default_start, now_kyiv),
            min_value=min_date_avail - timedelta(days=365),
            max_value=max_date_avail
        )
        
    with c3:
        sort_opts = ["Найновіші", "Найстаріші", "Більше згадок", "Офіц. джерела"]
        sel_sort = st.selectbox("Сортування", sort_opts, on_change=reset_page)

    with c4:
        rows_per_page = st.selectbox("Рядків на стор.", [10, 20, 50, 100, 200], index=0, on_change=reset_page)

    # --- ЗАСТОСУВАННЯ ФІЛЬТРІВ ---
    mask = df_scans['provider'].isin(sel_providers)
    
    if isinstance(sel_dates, tuple):
        if len(sel_dates) == 2:
            start_d, end_d = sel_dates
            mask &= (df_scans['created_at_dt'].dt.date >= start_d)
            mask &= (df_scans['created_at_dt'].dt.date <= end_d)
        elif len(sel_dates) == 1:
            mask &= (df_scans['created_at_dt'].dt.date == sel_dates[0])
        
    df_filtered = df_scans[mask].copy()

    # Сортування
    if sel_sort == "Найновіші": df_filtered = df_filtered.sort_values('created_at_dt', ascending=False)
    elif sel_sort == "Найстаріші": df_filtered = df_filtered.sort_values('created_at_dt', ascending=True)
    elif sel_sort == "Більше згадок": df_filtered = df_filtered.sort_values('my_mentions_count', ascending=False)
    elif sel_sort == "Офіц. джерела": df_filtered = df_filtered.sort_values('official_links', ascending=False)

    # --- 5. ПАГІНАЦІЯ ---
    total_rows = len(df_filtered)
    total_pages = math.ceil(total_rows / rows_per_page)
    
    if st.session_state.history_page_number > total_pages:
        st.session_state.history_page_number = max(1, total_pages)
    
    current_page = st.session_state.history_page_number
    start_idx = (current_page - 1) * rows_per_page
    end_idx = start_idx + rows_per_page
    
    df_display_page = df_filtered.iloc[start_idx:end_idx].copy()

    # --- 6. ВІДОБРАЖЕННЯ (AUTO HEIGHT) ---
    st.divider()
    
    p_col1, p_col2, p_col3 = st.columns([1, 2, 1])
    with p_col1:
        if current_page > 1:
            if st.button("⬅️ Попередня", key="hist_prev_top"):
                st.session_state.history_page_number -= 1
                st.rerun()
    with p_col2:
        st.markdown(f"<div style='text-align: center; padding-top: 5px;'>Сторінка <b>{current_page}</b> з <b>{total_pages}</b> (Всього: {total_rows})</div>", unsafe_allow_html=True)
    with p_col3:
        if current_page < total_pages:
            if st.button("Наступна ➡️", key="hist_next_top"):
                st.session_state.history_page_number += 1
                st.rerun()

    if 'created_at_dt' in df_display_page.columns:
        df_display_page['created_at_dt'] = df_display_page['created_at_dt'].dt.strftime('%d.%m.%Y %H:%M')

    cols_to_show = ['created_at_dt', 'keyword', 'provider', 'total_brands', 'total_links', 'my_mentions_count', 'official_links', 'initiator']
    df_show = df_display_page[[c for c in cols_to_show if c in df_display_page.columns]]

    # Авто-висота
    dynamic_height = (len(df_show) * 35) + 38

    st.dataframe(
        df_show,
        use_container_width=True,
        hide_index=True,
        height=dynamic_height,
        column_config={
            "created_at_dt": "Дата (Kyiv)",
            "keyword": st.column_config.TextColumn("Запит", width="medium"),
            "provider": "LLM",
            "total_brands": st.column_config.NumberColumn("Бренди", help="Кількість знайдених конкурентів"),
            "total_links": st.column_config.NumberColumn("Посил.", help="Всього джерел"),
            "my_mentions_count": st.column_config.NumberColumn("Згадки", help="Згадки нашого бренду"),
            "official_links": st.column_config.NumberColumn("Офіц.", help="Офіційні джерела"),
            "initiator": st.column_config.TextColumn("Ініціатор", help="Хто запустив", width="medium")
        }
    )

    if total_rows > 10:
        st.write("")
        b_col1, b_col2, b_col3 = st.columns([1, 2, 1])
        with b_col1:
            if current_page > 1:
                if st.button("⬅️ Попередня", key="hist_prev_btm"):
                    st.session_state.history_page_number -= 1
                    st.rerun()
        with b_col3:
            if current_page < total_pages:
                if st.button("Наступна ➡️", key="hist_next_btm"):
                    st.session_state.history_page_number += 1
                    st.rerun()
