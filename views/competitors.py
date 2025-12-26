import pandas as pd
import plotly.express as px
import streamlit as st

# 🔥 Імпорт підключення до БД (важливо!)
from utils.db import supabase

def show_competitors_page():
    """
    Сторінка глибокого конкурентного аналізу.
    ВЕРСІЯ: MODULAR & STABLE.
    1. Тональність: Графік Stacked Bar (🔴/⚪/🟢) для кожного бренду.
    2. Середня позиція: Топ-10 + Цільовий.
    3. Ліміт рядків: Мінімум 20.
    """

    # --- ПЕРЕВІРКА ПРОЕКТУ ---
    proj = st.session_state.get("current_project")
    if not proj:
        st.info("Спочатку створіть проект.")
        return
    
    OFFICIAL_BRAND_NAME = proj.get("brand_name", "My Brand")

    MODEL_MAPPING = {
        "Perplexity": "perplexity",
        "OpenAI GPT": "gpt-4o",
        "Google Gemini": "gemini-1.5-pro"
    }

    # --- Ініціалізація станів пагінації ---
    if 'cp_page_list' not in st.session_state: st.session_state.cp_page_list = 1
    if 'cp_page_freq' not in st.session_state: st.session_state.cp_page_freq = 1
    if 'cp_page_sent' not in st.session_state: st.session_state.cp_page_sent = 1
    if 'cp_page_rank' not in st.session_state: st.session_state.cp_page_rank = 1

    # Callbacks для скидання сторінок при зміні фільтрів
    def reset_p_list(): st.session_state.cp_page_list = 1
    def reset_p_freq(): st.session_state.cp_page_freq = 1
    def reset_p_sent(): st.session_state.cp_page_sent = 1
    def reset_p_rank(): st.session_state.cp_page_rank = 1

    st.title("👥 Аналіз Конкурентів")

    # --- 1. ЗАВАНТАЖЕННЯ ДАНИХ ---
    try:
        # Отримуємо результати сканування для проекту
        scans_resp = supabase.table("scan_results")\
            .select("id, provider, keyword_id, created_at")\
            .eq("project_id", proj["id"])\
            .execute()
        
        if not scans_resp.data:
            st.info("Даних немає. Запустіть сканування.")
            return
            
        df_scans = pd.DataFrame(scans_resp.data)
        
        # Отримуємо слова для мапінгу
        kw_resp = supabase.table("keywords").select("id, keyword_text").eq("project_id", proj["id"]).execute()
        kw_map = {k['id']: k['keyword_text'] for k in kw_resp.data}
        df_scans['keyword_text'] = df_scans['keyword_id'].map(kw_map)

        scan_ids = df_scans['id'].tolist()
        
        # Завантажуємо згадки (можна додати батчінг, якщо багато даних)
        # Тут для простоти один запит
        mentions_resp = supabase.table("brand_mentions")\
            .select("*")\
            .in_("scan_result_id", scan_ids)\
            .execute()
        
        if not mentions_resp.data:
            st.info("Брендів не знайдено.")
            return

        df_mentions = pd.DataFrame(mentions_resp.data)
        
        # Об'єднуємо таблиці
        df_full = pd.merge(df_mentions, df_scans, left_on='scan_result_id', right_on='id', how='left')

    except Exception as e:
        st.error(f"Помилка обробки даних: {e}")
        return

    # --- 2. ФІЛЬТРИ ---
    with st.container(border=True):
        c1, c2 = st.columns(2)
        with c1:
            all_models = list(MODEL_MAPPING.keys())
            sel_models = st.multiselect("🤖 Фільтр по LLM:", all_models, default=all_models)
            sel_tech_models = [MODEL_MAPPING[m] for m in sel_models]

        with c2:
            all_kws = df_full['keyword_text'].dropna().unique().tolist()
            sel_kws = st.multiselect("🔎 Фільтр по Запитах:", all_kws, default=all_kws)

    # Застосування фільтрів
    if sel_tech_models:
        mask_model = df_full['provider'].apply(lambda x: any(t in str(x) for t in sel_tech_models))
    else:
        mask_model = df_full['provider'].apply(lambda x: False)

    if sel_kws:
        mask_kw = df_full['keyword_text'].isin(sel_kws)
    else:
        mask_kw = df_full['keyword_text'].apply(lambda x: False)

    df_filtered = df_full[mask_model & mask_kw].copy()

    if df_filtered.empty:
        st.warning("За обраними фільтрами даних немає.")
        return

    # --- 3. АГРЕГАЦІЯ ---
    # Уніфікація назви нашого бренду
    mask_target = df_filtered['is_my_brand'] == True
    if mask_target.any():
        df_filtered.loc[mask_target, 'brand_name'] = OFFICIAL_BRAND_NAME

    # Числова оцінка тональності для середнього
    def sentiment_to_score(s):
        if s == 'Позитивна': return 100
        if s == 'Негативна': return 0
        return 50
    
    df_filtered['sent_score_num'] = df_filtered['sentiment_score'].apply(sentiment_to_score)

    # Основна статистика по брендах
    stats = df_filtered.groupby('brand_name').agg(
        Mentions=('id_x', 'count'), # id_x - це id згадки
        Avg_Rank=('rank_position', 'mean'),
        Avg_Sentiment_Num=('sent_score_num', 'mean'),
        Is_My_Brand=('is_my_brand', 'max')
    ).reset_index()

    # Детальна тональність (Pivot)
    sent_counts = df_filtered.groupby(['brand_name', 'sentiment_score']).size().unstack(fill_value=0)
    for col in ['Негативна', 'Нейтральна', 'Позитивна']:
        if col not in sent_counts.columns: sent_counts[col] = 0
            
    sent_counts['Total'] = sent_counts.sum(axis=1)
    
    # Відсотки
    import math # Для floor/ceil якщо треба, тут int
    sent_counts['Neg_Pct'] = (sent_counts['Негативна'] / sent_counts['Total'] * 100).fillna(0).astype(int)
    sent_counts['Neu_Pct'] = (sent_counts['Нейтральна'] / sent_counts['Total'] * 100).fillna(0).astype(int)
    sent_counts['Pos_Pct'] = (sent_counts['Позитивна'] / sent_counts['Total'] * 100).fillna(0).astype(int)

    # Строка для таблиці
    sent_counts['Тональність_Str'] = sent_counts.apply(
        lambda x: f"🔴 {x['Neg_Pct']}%   ⚪ {x['Neu_Pct']}%   🟢 {x['Pos_Pct']}%", axis=1
    )

    # Зливаємо все разом
    stats = stats.merge(sent_counts[['Тональність_Str', 'Neg_Pct', 'Neu_Pct', 'Pos_Pct']], on='brand_name', how='left')
    stats['Тональність_Str'] = stats['Тональність_Str'].fillna("🔴 0% ⚪ 0% 🟢 0%")
    stats[['Neg_Pct', 'Neu_Pct', 'Pos_Pct']] = stats[['Neg_Pct', 'Neu_Pct', 'Pos_Pct']].fillna(0)

    # --- ЛОГІКА TOP-N (Helper Function) ---
    def set_top_n_flag(df, sort_col, n=15, ascending=False):
        """
        Встановлює 'Show' = True для Top N брендів.
        Гарантовано включає цільовий бренд, навіть якщо він не в топі.
        """
        df = df.sort_values(sort_col, ascending=ascending).reset_index(drop=True)
        df['Show'] = False
        
        top_indices = df.index[:n].tolist()
        target_idx = df[df['brand_name'] == OFFICIAL_BRAND_NAME].index
        
        if not target_idx.empty:
            t_idx = target_idx[0]
            if t_idx not in top_indices:
                # Якщо наш бренд не в топі, замінюємо останнього, щоб показати наш
                if len(top_indices) == n:
                    top_indices.pop()
                top_indices.append(t_idx)
        
        df.loc[top_indices, 'Show'] = True
        return df

    # --- 4. ВІДОБРАЖЕННЯ (ВКЛАДКИ) ---
    st.write("") 
    
    tab_list, tab_freq, tab_sent, tab_rank = st.tabs([
        "📋 Детальний рейтинг", 
        "📊 Частота згадки", 
        "⭐ Тональність", 
        "🏆 Середня позиція"
    ])

    # === TAB 1: ДЕТАЛЬНИЙ РЕЙТИНГ (Таблиця) ===
    with tab_list:
        c_head, c_search, c_rows = st.columns([2, 2, 1])
        with c_head: st.markdown("##### 📋 Зведена таблиця")
        with c_search: search_list = st.text_input("🔍 Пошук бренду", key="s_list", on_change=reset_p_list)
        # Мінімум 20 рядків
        with c_rows: rows_list = st.selectbox("Рядків", [20, 50, 100, 200], key="r_list", on_change=reset_p_list)
        
        display_df = stats.copy().sort_values('Mentions', ascending=False).reset_index(drop=True)
        display_df.index = display_df.index + 1
        display_df.index.name = '#'
        display_df['Сер. Позиція'] = display_df['Avg_Rank'].apply(lambda x: f"#{x:.1f}")

        if search_list:
            display_df = display_df[display_df['brand_name'].astype(str).str.contains(search_list, case=False, na=False)]

        # Пагінація
        total_rows = len(display_df)
        total_pages = math.ceil(total_rows / rows_list)
        
        if st.session_state.cp_page_list > total_pages: st.session_state.cp_page_list = max(1, total_pages)
        curr_p = st.session_state.cp_page_list
        
        start_idx = (curr_p - 1) * rows_list
        end_idx = start_idx + rows_list
        df_page = display_df.iloc[start_idx:end_idx].copy()

        nc1, nc2, nc3 = st.columns([1, 2, 1])
        with nc1:
            if curr_p > 1: 
                if st.button("⬅️ Попередня", key="prev_list_t"): st.session_state.cp_page_list -= 1; st.rerun()
        with nc2: st.caption(f"Стор. {curr_p} з {total_pages} (Всього: {total_rows})")
        with nc3:
            if curr_p < total_pages:
                if st.button("Наступна ➡️", key="next_list_t"): st.session_state.cp_page_list += 1; st.rerun()

        def highlight_target_row(row):
            if row['brand_name'] == OFFICIAL_BRAND_NAME:
                return ['background-color: #d4edda; color: #155724; font-weight: bold'] * len(row)
            return [''] * len(row)

        cols_to_show = ['brand_name', 'Mentions', 'Сер. Позиція', 'Тональність_Str']
        
        # Стилізація таблиці (Pandas Styler)
        styled_df = df_page[cols_to_show].style.apply(highlight_target_row, axis=1)

        dynamic_h = (len(df_page) * 35) + 38
        st.dataframe(
            styled_df,
            use_container_width=True,
            height=dynamic_h,
            column_config={
                "brand_name": "Бренд",
                "Mentions": st.column_config.ProgressColumn("Згадок", format="%d", min_value=0, max_value=int(stats['Mentions'].max())),
                "Сер. Позиція": st.column_config.TextColumn("Сер. Позиція", width="small"),
                "Тональність_Str": st.column_config.TextColumn("Тональність", width="medium")
            }
        )

        if total_rows > 20:
            bc1, bc2, bc3 = st.columns([1, 2, 1])
            with bc1:
                if curr_p > 1: 
                    if st.button("⬅️ Попередня", key="prev_list_b"): st.session_state.cp_page_list -= 1; st.rerun()
            with bc3:
                if curr_p < total_pages:
                    if st.button("Наступна ➡️", key="next_list_b"): st.session_state.cp_page_list += 1; st.rerun()

    # === TAB 2: ЧАСТОТА ЗГАДКИ ===
    with tab_freq:
        c_head, c_search, c_rows = st.columns([2, 2, 1])
        with c_head: st.markdown("##### 📊 Частота згадки (Топ-15)")
        with c_search: search_freq = st.text_input("🔍 Пошук бренду", key="s_freq", on_change=reset_p_freq)
        with c_rows: rows_freq = st.selectbox("Рядків", [20, 50, 100, 200], key="r_freq", on_change=reset_p_freq)
        
        df_for_freq = stats.copy()
        df_for_freq['Display_Name'] = df_for_freq.apply(
            lambda x: f"🟢 {x['brand_name']}" if x['brand_name'] == OFFICIAL_BRAND_NAME else x['brand_name'], axis=1
        )
        # Топ-15
        df_for_freq = set_top_n_flag(df_for_freq, 'Mentions', n=15, ascending=False)
        
        if search_freq:
            df_for_freq = df_for_freq[df_for_freq['brand_name'].astype(str).str.contains(search_freq, case=False, na=False)]

        col_table, col_chart = st.columns([1.8, 2.2])

        with col_table:
            total_rows = len(df_for_freq)
            total_pages = math.ceil(total_rows / rows_freq)
            if st.session_state.cp_page_freq > total_pages: st.session_state.cp_page_freq = max(1, total_pages)
            curr_p = st.session_state.cp_page_freq
            start_idx = (curr_p - 1) * rows_freq
            end_idx = start_idx + rows_freq
            df_page = df_for_freq.iloc[start_idx:end_idx]

            nc1, nc2, nc3 = st.columns([1, 2, 1])
            with nc1:
                if curr_p > 1: 
                    if st.button("⬅️", key="p_freq_t"): st.session_state.cp_page_freq -= 1; st.rerun()
            with nc2: st.caption(f"Стор. {curr_p}/{total_pages}")
            with nc3:
                if curr_p < total_pages: 
                    if st.button("➡️", key="n_freq_t"): st.session_state.cp_page_freq += 1; st.rerun()

            dynamic_h = (len(df_page) * 35) + 38
            # Редактор, щоб користувач міг ховати/показувати бренди на графіку
            edited_freq_df = st.data_editor(
                df_page[['Show', 'Display_Name', 'Mentions']],
                column_config={
                    "Show": st.column_config.CheckboxColumn("Відобразити", width="small"),
                    "Display_Name": st.column_config.TextColumn("Бренд", disabled=True),
                    "Mentions": st.column_config.ProgressColumn("Згадок", format="%d", min_value=0, max_value=int(stats['Mentions'].max())),
                },
                hide_index=True,
                use_container_width=True,
                height=dynamic_h,
                key=f"editor_freq_{curr_p}"
            )
            
            if total_rows > 20:
                bc1, bc2, bc3 = st.columns([1, 2, 1])
                with bc1:
                    if curr_p > 1: 
                        if st.button("⬅️", key="p_freq_b"): st.session_state.cp_page_freq -= 1; st.rerun()
                with bc3:
                    if curr_p < total_pages: 
                        if st.button("➡️", key="n_freq_b"): st.session_state.cp_page_freq += 1; st.rerun()

        with col_chart:
            chart_data = edited_freq_df[edited_freq_df['Show'] == True].copy()
            chart_data['Original_Name'] = chart_data['Display_Name'].apply(lambda x: x.replace("🟢 ", ""))
            
            if not chart_data.empty:
                # Додаємо колір: Зелений для нашого, Сірий/Тіл для інших
                chart_data['Color'] = chart_data['Original_Name'].apply(lambda x: '#00C896' if x == OFFICIAL_BRAND_NAME else '#90A4AE')
                
                fig = px.bar(
                    chart_data, 
                    x='Original_Name', 
                    y='Mentions',
                    text='Mentions'
                )
                fig.update_traces(marker_color=chart_data['Color'])
                fig.update_layout(xaxis_title="", yaxis_title="Кількість згадок", showlegend=False)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Оберіть бренди.")

    # === TAB 3: ТОНАЛЬНІСТЬ (STACKED BAR CHART) ===
    with tab_sent:
        c_head, c_search, c_rows = st.columns([2, 2, 1])
        with c_head: st.markdown("##### ⭐ Тональність (Топ-15)")
        with c_search: search_sent = st.text_input("🔍 Пошук бренду", key="s_sent", on_change=reset_p_sent)
        with c_rows: rows_sent = st.selectbox("Рядків", [20, 50, 100, 200], key="r_sent", on_change=reset_p_sent)
        
        df_for_sent = stats.copy()
        df_for_sent['Display_Name'] = df_for_sent.apply(
            lambda x: f"🟢 {x['brand_name']}" if x['brand_name'] == OFFICIAL_BRAND_NAME else x['brand_name'], axis=1
        )
        df_for_sent = set_top_n_flag(df_for_sent, 'Mentions', n=15, ascending=False)

        if search_sent:
            df_for_sent = df_for_sent[df_for_sent['brand_name'].astype(str).str.contains(search_sent, case=False, na=False)]

        col_table, col_chart = st.columns([1.8, 2.2])

        with col_table:
            total_rows = len(df_for_sent)
            total_pages = math.ceil(total_rows / rows_sent)
            if st.session_state.cp_page_sent > total_pages: st.session_state.cp_page_sent = max(1, total_pages)
            curr_p = st.session_state.cp_page_sent
            start_idx = (curr_p - 1) * rows_sent
            end_idx = start_idx + rows_sent
            df_page = df_for_sent.iloc[start_idx:end_idx]

            nc1, nc2, nc3 = st.columns([1, 2, 1])
            with nc1:
                if curr_p > 1: 
                    if st.button("⬅️", key="p_sent_t"): st.session_state.cp_page_sent -= 1; st.rerun()
            with nc2: st.caption(f"Стор. {curr_p}/{total_pages}")
            with nc3:
                if curr_p < total_pages: 
                    if st.button("➡️", key="n_sent_t"): st.session_state.cp_page_sent += 1; st.rerun()

            dynamic_h = (len(df_page) * 35) + 38
            edited_sent_df = st.data_editor(
                df_page[['Show', 'Display_Name', 'Тональність_Str']],
                column_config={
                    "Show": st.column_config.CheckboxColumn("Відобразити", width="small"),
                    "Display_Name": st.column_config.TextColumn("Бренд", disabled=True),
                    "Тональність_Str": st.column_config.TextColumn("Розподіл", disabled=True, width="medium"),
                },
                hide_index=True,
                use_container_width=True,
                height=dynamic_h,
                key=f"editor_sent_{curr_p}"
            )
            
            if total_rows > 20:
                bc1, bc2, bc3 = st.columns([1, 2, 1])
                with bc1:
                    if curr_p > 1: 
                        if st.button("⬅️", key="p_sent_b"): st.session_state.cp_page_sent -= 1; st.rerun()
                with bc3:
                    if curr_p < total_pages: 
                        if st.button("➡️", key="n_sent_b"): st.session_state.cp_page_sent += 1; st.rerun()

        with col_chart:
            # 🔥 БУДУЄМО ГРАФІК З НАКОПИЧЕННЯМ (STACKED)
            selected_rows = edited_sent_df[edited_sent_df['Show'] == True]
            selected_rows['Original_Name'] = selected_rows['Display_Name'].apply(lambda x: x.replace("🟢 ", ""))
            
            target_brands = selected_rows['Original_Name'].tolist()
            chart_data_src = stats[stats['brand_name'].isin(target_brands)].copy()
            
            if not chart_data_src.empty:
                df_melted = chart_data_src.melt(
                    id_vars=['brand_name'], 
                    value_vars=['Neg_Pct', 'Neu_Pct', 'Pos_Pct'], 
                    var_name='Sentiment_Type', 
                    value_name='Percentage'
                )
                
                df_melted['Sentiment'] = df_melted['Sentiment_Type'].map({
                    'Neg_Pct': 'Негативна',
                    'Neu_Pct': 'Нейтральна',
                    'Pos_Pct': 'Позитивна'
                })
                
                color_map = {
                    "Негативна": "#FF5252",
                    "Нейтральна": "#CFD8DC",
                    "Позитивна": "#00C896"
                }
                
                fig = px.bar(
                    df_melted,
                    x="brand_name",
                    y="Percentage",
                    color="Sentiment",
                    text="Percentage",
                    color_discrete_map=color_map,
                    category_orders={"Sentiment": ["Негативна", "Нейтральна", "Позитивна"]},
                    height=500
                )
                
                fig.update_traces(texttemplate='%{text}%', textposition='inside')
                fig.update_layout(
                    barmode='stack',
                    xaxis_title="", 
                    yaxis_title="Частка (%)", 
                    legend_title="",
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Оберіть бренди.")

    # === TAB 4: СЕРЕДНЯ ПОЗИЦІЯ (TOP-10) ===
    with tab_rank:
        c_head, c_search, c_rows = st.columns([2, 2, 1])
        with c_head: st.markdown("##### 🏆 Середня позиція (Топ-10)")
        with c_search: search_rank = st.text_input("🔍 Пошук бренду", key="s_rank", on_change=reset_p_rank)
        with c_rows: rows_rank = st.selectbox("Рядків", [20, 50, 100, 200], key="r_rank", on_change=reset_p_rank)

        col_table, col_chart = st.columns([1.8, 2.2])

        with col_table:
            df_for_rank = stats.copy()
            df_for_rank['Display_Name'] = df_for_rank.apply(
                lambda x: f"🟢 {x['brand_name']}" if x['brand_name'] == OFFICIAL_BRAND_NAME else x['brand_name'], axis=1
            )
            df_for_rank = set_top_n_flag(df_for_rank, 'Avg_Rank', n=10, ascending=True)

            if search_rank:
                df_for_rank = df_for_rank[df_for_rank['brand_name'].astype(str).str.contains(search_rank, case=False, na=False)]

            total_rows = len(df_for_rank)
            total_pages = math.ceil(total_rows / rows_rank)
            if st.session_state.cp_page_rank > total_pages: st.session_state.cp_page_rank = max(1, total_pages)
            curr_p = st.session_state.cp_page_rank
            start_idx = (curr_p - 1) * rows_rank
            end_idx = start_idx + rows_rank
            df_page = df_for_rank.iloc[start_idx:end_idx]

            nc1, nc2, nc3 = st.columns([1, 2, 1])
            with nc1:
                if curr_p > 1: 
                    if st.button("⬅️", key="p_rank_t"): st.session_state.cp_page_rank -= 1; st.rerun()
            with nc2: st.caption(f"Стор. {curr_p}/{total_pages}")
            with nc3:
                if curr_p < total_pages: 
                    if st.button("➡️", key="n_rank_t"): st.session_state.cp_page_rank += 1; st.rerun()

            dynamic_h = (len(df_page) * 35) + 38
            edited_rank_df = st.data_editor(
                df_page[['Show', 'Display_Name', 'Avg_Rank']],
                column_config={
                    "Show": st.column_config.CheckboxColumn("Відобразити", width="small"),
                    "Display_Name": st.column_config.TextColumn("Бренд", disabled=True),
                    "Avg_Rank": st.column_config.NumberColumn("Сер. Позиція", format="%.1f"),
                },
                hide_index=True,
                use_container_width=True,
                height=dynamic_h,
                key=f"editor_rank_{curr_p}"
            )
            
            if total_rows > 20:
                bc1, bc2, bc3 = st.columns([1, 2, 1])
                with bc1:
                    if curr_p > 1: 
                        if st.button("⬅️", key="p_rank_b"): st.session_state.cp_page_rank -= 1; st.rerun()
                with bc3:
                    if curr_p < total_pages: 
                        if st.button("➡️", key="n_rank_b"): st.session_state.cp_page_rank += 1; st.rerun()

        with col_chart:
            chart_data = edited_rank_df[edited_rank_df['Show'] == True].copy()
            chart_data['Original_Name'] = chart_data['Display_Name'].apply(lambda x: x.replace("🟢 ", ""))
            
            chart_data['Color'] = chart_data['Original_Name'].apply(
                lambda x: '#00C896' if x == OFFICIAL_BRAND_NAME else '#B0BEC5'
            )

            if not chart_data.empty:
                fig = px.bar(
                    chart_data, 
                    x='Original_Name', 
                    y='Avg_Rank',
                    text='Avg_Rank'
                )
                
                fig.update_traces(
                    marker_color=chart_data['Color'],
                    texttemplate='%{text:.1f}', 
                    textposition='outside'
                )
                
                fig.update_layout(
                    xaxis_title="", 
                    yaxis_title="Середня позиція (менше = краще)", 
                    showlegend=False
                )
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Оберіть бренди.")
