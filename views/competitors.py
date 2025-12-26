def show_keyword_details(kw_id):
    """
    Сторінка детальної аналітики одного запиту.
    ВЕРСІЯ: ADDED MODEL OVERVIEW BLOCK.
    1. Додано блок "Огляд по моделях" перед графіком динаміки.
    2. Виводиться SOV, Rank та Тональність (100% distribution) для кожної LLM окремо.
    """
    import pandas as pd
    import plotly.express as px
    import plotly.graph_objects as go
    import streamlit as st
    from datetime import datetime, timedelta
    import numpy as np
    import time
    import re
    import uuid
    
    # 0. ПІДКЛЮЧЕННЯ
    if 'supabase' not in globals():
        if 'supabase' in st.session_state:
            supabase = st.session_state['supabase']
        else:
            st.error("🚨 Помилка: Змінна 'supabase' не знайдена.")
            return
    else:
        supabase = globals()['supabase']

    # --- CSS Styles for Cards & Sentiment ---
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
        .sent-container {
            background-color: #f8f9fa;
            border-radius: 8px;
            padding: 10px;
            margin-top: 10px;
        }
        .sent-title {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            color: #555;
            margin-bottom: 8px;
            text-align: center;
        }
        .sent-row {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            font-weight: 600;
            margin-bottom: 4px;
        }
        .text-pos { color: #00C896; }
        .text-neu { color: #B0BEC5; }
        .text-neg { color: #FF4B4B; }
    </style>
    """, unsafe_allow_html=True)

    # --- MAPPING ---
    MODEL_CONFIG = {
        "Perplexity": "perplexity",
        "OpenAI GPT": "gpt-4o",
        "Google Gemini": "gemini-1.5-pro"
    }
    ALL_MODELS_UI = list(MODEL_CONFIG.keys())
    
    # Функція нормалізації назв з бази
    def get_ui_model_name(db_name):
        for ui, db in MODEL_CONFIG.items():
            if db == db_name: return ui
        lower = str(db_name).lower()
        if "perplexity" in lower: return "Perplexity"
        if "gpt" in lower or "openai" in lower: return "OpenAI GPT"
        if "gemini" in lower or "google" in lower: return "Google Gemini"
        return db_name 

    def tooltip(text):
        return f'<span title="{text}" style="cursor:help; font-size:14px; color:#333; margin-left:4px;">ℹ️</span>'

    def normalize_url(u):
        u = str(u).strip()
        u = re.split(r'[)\]]', u)[0] 
        if not u.startswith(('http://', 'https://')): return f"https://{u}"
        return u

    # 1. ОТРИМАННЯ ДАНИХ ЗАПИТУ (СТАТИЧНА ЧАСТИНА)
    try:
        kw_resp = supabase.table("keywords").select("*").eq("id", kw_id).execute()
        if not kw_resp.data:
            st.error("Запит не знайдено.")
            st.session_state["focus_keyword_id"] = None
            st.rerun()
            return
        
        keyword_record = kw_resp.data[0]
        keyword_text = keyword_record["keyword_text"]
        project_id = keyword_record["project_id"]
        
        proj = st.session_state.get("current_project", {})
        target_brand_name = proj.get("brand_name", "").strip()
        target_brand_lower = target_brand_name.lower()
        
    except Exception as e:
        st.error(f"Помилка БД: {e}")
        return

    # HEADER
    col_back, col_title = st.columns([1, 15])
    with col_back:
        if st.button("⬅", key="back_from_details", help="Назад до списку"):
            st.session_state["focus_keyword_id"] = None
            st.rerun()
    
    with col_title:
        st.markdown(f"<h3 style='margin-top: -5px;'>🔍 {keyword_text}</h3>", unsafe_allow_html=True)

    # ⚙️ БЛОК НАЛАШТУВАНЬ
    with st.expander("⚙️ Налаштування та Нове сканування", expanded=False):
        c1, c2 = st.columns(2)
        
        # ЛІВА: РЕДАГУВАННЯ
        with c1:
            edit_key = f"edit_mode_{kw_id}"
            if edit_key not in st.session_state: st.session_state[edit_key] = False
            
            new_text = st.text_input(
                "Текст запиту", 
                value=keyword_text, 
                key="edit_kw_input",
                disabled=not st.session_state[edit_key]
            )
            
            if not st.session_state[edit_key]:
                if st.button("✏️ Редагувати", key="enable_edit_btn"):
                    st.session_state[edit_key] = True
                    st.rerun()
            else:
                if st.button("💾 Зберегти", key="save_kw_btn"):
                    if new_text and new_text != keyword_text:
                        supabase.table("keywords").update({"keyword_text": new_text}).eq("id", kw_id).execute()
                        st.success("Збережено!")
                    st.session_state[edit_key] = False
                    st.rerun()

        # ПРАВА: ЗАПУСК
        with c2:
            selected_models_to_run = st.multiselect(
                "Оберіть моделі для сканування:", 
                options=ALL_MODELS_UI, 
                default=ALL_MODELS_UI, 
                key="rescan_models_select"
            )
            
            confirm_run_key = f"confirm_run_{kw_id}"
            if confirm_run_key not in st.session_state: st.session_state[confirm_run_key] = False

            if not st.session_state[confirm_run_key]:
                if st.button("🚀 Запустити сканування", key="pre_run_btn"):
                    st.session_state[confirm_run_key] = True
                    st.rerun()
            else:
                c_conf1, c_conf2 = st.columns(2)
                with c_conf1:
                    if st.button("✅ Підтвердити", type="primary", key="real_run_btn"):
                        proj = st.session_state.get("current_project", {})
                        if 'n8n_trigger_analysis' in globals():
                            n8n_trigger_analysis(
                                project_id, 
                                [new_text], 
                                proj.get("brand_name"), 
                                models=selected_models_to_run
                            )
                            st.success("Задачу відправлено! Оновлення даних...")
                            time.sleep(2)
                            st.session_state[confirm_run_key] = False
                            st.rerun()
                        else:
                            st.error("Функція запуску не знайдена.")
                with c_conf2:
                    if st.button("❌ Скасувати", key="cancel_run_btn"):
                        st.session_state[confirm_run_key] = False
                        st.rerun()

    # =================================================================================
    # 🔥 LIVE SECTION: АВТО-ОНОВЛЕННЯ ДАНИХ (KPI, Charts, Tabs)
    # =================================================================================
    @st.fragment(run_every=5)
    def render_live_analytics():
        # 2. ОТРИМАННЯ ДАНИХ (Всередині фрагмента)
        try:
            scans_resp = supabase.table("scan_results")\
                .select("id, created_at, provider, raw_response")\
                .eq("keyword_id", kw_id)\
                .order("created_at", desc=False)\
                .execute()
            
            scans_data = scans_resp.data if scans_resp.data else []
            df_scans = pd.DataFrame(scans_data)
            
            if not df_scans.empty:
                df_scans.rename(columns={'id': 'scan_id'}, inplace=True)
                
                # --- TIMEZONE FIX ---
                df_scans['created_at'] = pd.to_datetime(df_scans['created_at'])
                if df_scans['created_at'].dt.tz is None:
                    df_scans['created_at'] = df_scans['created_at'].dt.tz_localize('UTC')
                # df_scans['created_at'] = df_scans['created_at'].dt.tz_convert('Europe/Kiev') # Optional
                df_scans['date_str'] = df_scans['created_at'].dt.strftime('%Y-%m-%d %H:%M')
                
                df_scans['provider_ui'] = df_scans['provider'].apply(get_ui_model_name)
            else:
                df_scans = pd.DataFrame(columns=['scan_id', 'created_at', 'provider', 'raw_response', 'date_str', 'provider_ui'])

            # B. Mentions
            if not df_scans.empty:
                scan_ids = df_scans['scan_id'].tolist()
                if scan_ids:
                    mentions_resp = supabase.table("brand_mentions")\
                        .select("*")\
                        .in_("scan_result_id", scan_ids)\
                        .execute()
                    mentions_data = mentions_resp.data if mentions_resp.data else []
                    df_mentions = pd.DataFrame(mentions_data)
                else:
                    df_mentions = pd.DataFrame()
            else:
                df_mentions = pd.DataFrame()

            # SMART MERGE / CHECK TARGET
            if not df_mentions.empty:
                # Нормалізація тональності
                def normalize_sentiment(s):
                    s_lower = str(s).lower()
                    if 'поз' in s_lower or 'pos' in s_lower: return 'Позитивна'
                    if 'нег' in s_lower or 'neg' in s_lower: return 'Негативна'
                    if 'ней' in s_lower or 'neu' in s_lower: return 'Нейтральна'
                    return 'Нейтральна'
                df_mentions['sentiment_score'] = df_mentions['sentiment_score'].apply(normalize_sentiment)

                # Перевірка is_target
                def check_is_target(row):
                    flag_val = str(row.get('is_my_brand', '')).lower()
                    if flag_val in ['true', '1', 't', 'yes', 'on']: return True
                    
                    mention_name = str(row.get('brand_name', '')).strip().lower()
                    if target_brand_lower and mention_name:
                        if target_brand_lower in mention_name: return True
                        if mention_name in target_brand_lower: return True
                    return False

                df_mentions['is_real_target'] = df_mentions.apply(check_is_target, axis=1)

            # C. Merge
            if not df_mentions.empty:
                df_full = pd.merge(df_scans, df_mentions, left_on='scan_id', right_on='scan_result_id', how='left')
            else:
                df_full = df_scans.copy()
                df_full['mention_count'] = 0
                df_full['is_real_target'] = False
                df_full['scan_result_id'] = df_full['scan_id'] if not df_full.empty else None
                df_full['sentiment_score'] = None
                df_full['rank_position'] = None
                df_full['brand_name'] = None

        except Exception as e:
            st.error(f"Помилка обробки даних: {e}")
            return

        # ==============================================================================
        # 🔥 НОВИЙ БЛОК: ОГЛЯД ПО МОДЕЛЯХ (ДЛЯ ЦЬОГО ЗАПИТУ)
        # ==============================================================================
        st.markdown("### 🌐 Огляд по моделях")

        # Helper to get stats for the latest scan of a model
        def get_model_stats_for_keyword(model_name):
            if df_scans.empty: return 0, 0, (0,0,0)
            
            # Filter scans for this model
            model_rows = df_scans[df_scans['provider_ui'] == model_name]
            if model_rows.empty: return 0, 0, (0,0,0)
            
            # Get latest scan
            last_scan = model_rows.sort_values('created_at', ascending=False).iloc[0]
            scan_id = last_scan['scan_id']
            
            if df_mentions.empty: return 0, 0, (0,0,0)
            
            current_mentions = df_mentions[df_mentions['scan_result_id'] == scan_id]
            if current_mentions.empty: return 0, 0, (0,0,0)
            
            total_mentions = current_mentions['mention_count'].sum()
            
            # Target Brand Mentions
            my_mentions = current_mentions[current_mentions['is_real_target'] == True]
            my_count = my_mentions['mention_count'].sum()
            
            # SOV
            sov = (my_count / total_mentions * 100) if total_mentions > 0 else 0
            
            # Rank
            valid_ranks = my_mentions[my_mentions['rank_position'] > 0]
            rank = valid_ranks['rank_position'].mean() if not valid_ranks.empty else 0
            
            # Sentiment (100% distribution of MY brand mentions)
            pos_p, neu_p, neg_p = 0, 0, 0
            if not my_mentions.empty:
                counts = my_mentions['sentiment_score'].value_counts()
                raw_pos = counts.get('Позитивна', 0)
                raw_neu = counts.get('Нейтральна', 0)
                raw_neg = counts.get('Негативна', 0)
                
                total_brand = raw_pos + raw_neu + raw_neg
                
                if total_brand > 0:
                    pos_p = (raw_pos / total_brand * 100)
                    neu_p = (raw_neu / total_brand * 100)
                    neg_p = (raw_neg / total_brand * 100)
            
            return sov, rank, (pos_p, neu_p, neg_p)

        # Render Cards
        cols = st.columns(3)
        models_order = ['OpenAI GPT', 'Google Gemini', 'Perplexity']
        
        for i, model in enumerate(models_order):
            with cols[i]:
                sov, rank, (pos, neu, neg) = get_model_stats_for_keyword(model)
                
                with st.container(border=True):
                    st.markdown(f"**{model}**")
                    c1, c2 = st.columns(2)
                    c1.metric("SOV", f"{sov:.1f}%")
                    c2.metric("Rank", f"#{rank:.1f}" if rank > 0 else "-")
                    
                    # Sentiment Chart
                    has_data = (pos + neu + neg) > 0.1
                    pie_values = [pos, neu, neg] if has_data else [1]
                    pie_colors = ['#00C896', '#B0BEC5', '#FF4B4B'] if has_data else ['#E0E0E0']
                    labels = ['Pos', 'Neu', 'Neg'] if has_data else ['No Data']

                    # Legend
                    st.markdown(f"""
                    <div class="sent-container">
                        <div class="sent-title">Загальна тональність</div>
                        <div class="sent-row text-pos"><span>Позитивна</span><span>{pos:.0f}%</span></div>
                        <div class="sent-row text-neu"><span>Нейтральна</span><span>{neu:.0f}%</span></div>
                        <div class="sent-row text-neg"><span>Негативна</span><span>{neg:.0f}%</span></div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Chart
                    fig_donut = go.Figure(data=[go.Pie(
                        labels=labels,
                        values=pie_values,
                        hole=.6,
                        marker=dict(colors=pie_colors),
                        textinfo='none',
                        hoverinfo='label+percent' if has_data else 'none'
                    )])
                    fig_donut.update_layout(
                        showlegend=False, 
                        margin=dict(t=5, b=5, l=5, r=5), 
                        height=100,
                        paper_bgcolor='rgba(0,0,0,0)',
                        plot_bgcolor='rgba(0,0,0,0)'
                    )
                    st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False}, key=f"kw_detail_donut_{model}_{i}")

        st.markdown("---")

        # 4. ГРАФІК ДИНАМІКИ
        st.markdown("##### 📈 Динаміка показників")

        if not df_full.empty and 'scan_id' in df_full.columns:
            totals = df_full.groupby('scan_id')['mention_count'].sum().reset_index()
            totals.rename(columns={'mention_count': 'scan_total'}, inplace=True)
            df_plot_base = pd.merge(df_full, totals, on='scan_id', how='left')
            df_plot_base['sov'] = (df_plot_base['mention_count'] / df_plot_base['scan_total'] * 100).fillna(0)
        else:
            df_plot_base = pd.DataFrame()

        with st.container(border=True):
            f_col1, f_col2, f_col3 = st.columns([1.2, 1.2, 2.5])
            with f_col1:
                metric_choice = st.selectbox("Метрика:", ["Частка голосу (SOV)", "Згадки бренду", "Позиція у списку"])
            with f_col2:
                if not df_plot_base.empty:
                    min_d = df_plot_base['created_at'].min().date()
                    max_d = df_plot_base['created_at'].max().date()
                    date_range = st.date_input("Діапазон дат:", value=(min_d, max_d), min_value=min_d, max_value=max_d)
                else:
                    date_range = None
                    st.date_input("Діапазон дат:", disabled=True)
            with f_col3:
                col_llm, col_brand = st.columns(2)
                with col_llm:
                    selected_llm_ui = st.multiselect("Фільтр по LLM:", options=ALL_MODELS_UI, default=ALL_MODELS_UI)
                with col_brand:
                    if not df_plot_base.empty:
                        all_found_brands = sorted([str(b) for b in df_plot_base['brand_name'].unique() if pd.notna(b)])
                        my_brand_name = proj.get("brand_name", "")
                        default_sel = [my_brand_name] if my_brand_name in all_found_brands else ([all_found_brands[0]] if all_found_brands else [])
                        selected_brands = st.multiselect("Фільтр по Брендах:", options=all_found_brands, default=default_sel)
                    else:
                        st.multiselect("Фільтр по Брендах:", options=[], disabled=True)

        if not df_plot_base.empty and date_range:
            if isinstance(date_range, tuple):
                if len(date_range) == 2:
                    start_d, end_d = date_range
                    mask_date = (df_plot_base['created_at'].dt.date >= start_d) & (df_plot_base['created_at'].dt.date <= end_d)
                    df_plot_base = df_plot_base[mask_date]
                elif len(date_range) == 1:
                    start_d = date_range[0]
                    mask_date = (df_plot_base['created_at'].dt.date == start_d)
                    df_plot_base = df_plot_base[mask_date]

            df_plot_base = df_plot_base[df_plot_base['provider_ui'].isin(selected_llm_ui)]
            if 'selected_brands' in locals() and selected_brands:
                df_plot_base = df_plot_base[df_plot_base['brand_name'].isin(selected_brands)]
            
            df_plot_base = df_plot_base.sort_values('created_at')

            if not df_plot_base.empty:
                if metric_choice == "Частка голосу (SOV)":
                    y_col = "sov"
                    y_title = "SOV (%)"
                    y_range = [0, 100]
                elif metric_choice == "Згадки бренду":
                    y_col = "mention_count"
                    y_title = "Кількість згадок"
                    y_range = None
                else:
                    y_col = "rank_position"
                    y_title = "Позиція"
                    y_range = None

                df_plot_base['legend_label'] = df_plot_base['brand_name'] + " (" + df_plot_base['provider_ui'] + ")"

                fig = px.line(
                    df_plot_base, 
                    x="created_at", 
                    y=y_col, 
                    color="legend_label",
                    markers=True,
                    labels={"created_at": "Час", "legend_label": "Легенда", y_col: y_title}
                )
                
                if y_range: fig.update_yaxes(range=y_range)
                if metric_choice == "Позиція у списку": fig.update_yaxes(autorange="reversed")

                fig.update_xaxes(showgrid=True, showticklabels=True, tickformat="%d.%m\n%H:%M", title_text="Час")
                fig.update_layout(height=350, hovermode="x unified", margin=dict(l=0, r=0, t=10, b=0), legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
            else:
                st.info("Немає даних за обраними критеріями.")
        else:
            st.info("Історія сканувань порожня або не обрано дати.")

        st.markdown("---")

        # 5. ДЕТАЛІЗАЦІЯ (TABS)
        st.markdown("##### 📝 Детальний аналіз відповідей")
        
        tabs = st.tabs(ALL_MODELS_UI)
        
        for tab, ui_model_name in zip(tabs, ALL_MODELS_UI):
            with tab:
                if not df_scans.empty:
                    model_scans = df_scans[df_scans['provider_ui'] == ui_model_name].sort_values('created_at', ascending=False)
                else:
                    model_scans = pd.DataFrame()
                
                if model_scans.empty:
                    st.write(f"📉 Даних від **{ui_model_name}** ще немає.")
                    continue

                with st.container(border=True):
                    scan_options = {row['date_str']: row['scan_id'] for _, row in model_scans.iterrows()}
                    
                    c_sel, c_del = st.columns([3, 1])
                    with c_sel:
                        selected_date = st.selectbox(
                            f"Оберіть дату аналізу ({ui_model_name}):", 
                            list(scan_options.keys()), 
                            key=f"sel_date_{ui_model_name}" 
                        )
                    
                    selected_scan_id = scan_options[selected_date]
                    
                    with c_del:
                        st.write("") 
                        st.write("")
                        confirm_key = f"del_scan_{selected_scan_id}"
                        if confirm_key not in st.session_state: st.session_state[confirm_key] = False

                        if not st.session_state[confirm_key]:
                            if st.button("🗑️ Видалити", key=f"btn_del_{selected_scan_id}"):
                                st.session_state[confirm_key] = True
                                st.rerun()
                        else:
                            c_y, c_n = st.columns(2)
                            if c_y.button("✅", key=f"yes_{selected_scan_id}"):
                                try:
                                    supabase.table("scan_results").delete().eq("id", selected_scan_id).execute()
                                    st.success("Видалено!")
                                    st.session_state[confirm_key] = False
                                    time.sleep(1)
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Помилка: {e}")
                            
                            if c_n.button("❌", key=f"no_{selected_scan_id}"):
                                st.session_state[confirm_key] = False
                                st.rerun()

                current_scan_row = model_scans[model_scans['scan_id'] == selected_scan_id].iloc[0]
                
                # --- LOCAL METRICS ---
                loc_sov = 0
                loc_mentions = 0
                loc_sent = "Не згадано"
                loc_rank_str = "-"
                
                current_scan_mentions = pd.DataFrame()
                if not df_mentions.empty:
                    current_scan_mentions = df_mentions[df_mentions['scan_result_id'] == selected_scan_id]
                
                if not current_scan_mentions.empty:
                    total_in_scan = current_scan_mentions['mention_count'].sum()
                    my_brand_rows = current_scan_mentions[current_scan_mentions['is_real_target'] == True]

                    if not my_brand_rows.empty:
                        val_my_mentions = my_brand_rows['mention_count'].sum()
                        valid_ranks = my_brand_rows[my_brand_rows['rank_position'] > 0]['rank_position']
                        val_rank = valid_ranks.min() if not valid_ranks.empty else None
                        
                        if val_my_mentions > 0:
                            main_row = my_brand_rows.sort_values('mention_count', ascending=False).iloc[0]
                            loc_sent = main_row['sentiment_score']
                        
                        loc_mentions = int(val_my_mentions)
                        loc_sov = (val_my_mentions / total_in_scan * 100) if total_in_scan > 0 else 0
                        loc_rank_str = f"#{val_rank:.0f}" if pd.notna(val_rank) else "-"
                
                sent_color = "#333"
                if loc_sent == "Позитивна": sent_color = "#00C896"
                elif loc_sent == "Негативна": sent_color = "#FF4B4B"
                elif loc_sent == "Не знайдено": sent_color = "#999"

                st.markdown(f"""
                <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin-bottom: 20px;">
                    <div style="background:#fff; border:1px solid #E0E0E0; border-top:4px solid #00C896; border-radius:8px; padding:15px; text-align:center;">
                        <div style="font-size:11px; color:#888; font-weight:600;">ЧАСТКА ГОЛОСУ (SOV) {tooltip('Відсоток згадок вашого бренду в цій конкретній відповіді.')}</div>
                        <div style="font-size:24px; font-weight:700; color:#333;">{loc_sov:.1f}%</div>
                    </div>
                    <div style="background:#fff; border:1px solid #E0E0E0; border-top:4px solid #00C896; border-radius:8px; padding:15px; text-align:center;">
                        <div style="font-size:11px; color:#888; font-weight:600;">ЗГАДОК БРЕНДУ {tooltip('Кількість разів, коли бренд був згаданий.')}</div>
                        <div style="font-size:24px; font-weight:700; color:#333;">{loc_mentions}</div>
                    </div>
                    <div style="background:#fff; border:1px solid #E0E0E0; border-top:4px solid #00C896; border-radius:8px; padding:15px; text-align:center;">
                        <div style="font-size:11px; color:#888; font-weight:600;">ТОНАЛЬНІСТЬ {tooltip('Емоційне забарвлення згадки в цій відповіді.')}</div>
                        <div style="font-size:18px; font-weight:600; color:{sent_color}; margin-top:5px;">{loc_sent}</div>
                    </div>
                    <div style="background:#fff; border:1px solid #E0E0E0; border-top:4px solid #00C896; border-radius:8px; padding:15px; text-align:center;">
                        <div style="font-size:11px; color:#888; font-weight:600;">ПОЗИЦІЯ У СПИСКУ {tooltip('Порядковий номер першої згадки бренду.')}</div>
                        <div style="font-size:24px; font-weight:700; color:#333;">{loc_rank_str}</div>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                raw_text = current_scan_row.get('raw_response', '')
                st.markdown("##### Відповідь від LLM")
                proj = st.session_state.get("current_project", {})
                brand_name = proj.get("brand_name", "")
                
                if raw_text:
                    final_html = raw_text
                    if brand_name:
                        highlight_span = f"<span style='background-color:#dcfce7; color:#166534; font-weight:bold; padding:0 4px; border-radius:4px;'>{brand_name}</span>"
                        final_html = final_html.replace(brand_name, highlight_span)
                    st.markdown(f"""<div style="background-color: #f9fffb; border: 1px solid #bbf7d0; border-radius: 8px; padding: 20px; font-size: 16px; line-height: 1.6; color: #374151;">{final_html}</div>""", unsafe_allow_html=True)
                else:
                    st.info("Текст відповіді не збережено.")

                st.markdown("<br>", unsafe_allow_html=True)

                # --- БРЕНДИ ---
                st.markdown(f"**Знайдені бренди:** {tooltip('Бренди, які AI згадав у цій відповіді.')}", unsafe_allow_html=True)
                
                if not current_scan_mentions.empty:
                    scan_mentions_plot = current_scan_mentions[current_scan_mentions['mention_count'] > 0].copy()
                    scan_mentions_plot = scan_mentions_plot.sort_values('mention_count', ascending=False)

                    if not scan_mentions_plot.empty:
                        c_chart, c_table = st.columns([1.3, 2], vertical_alignment="center")
                        with c_chart:
                            fig_brands = px.pie(
                                scan_mentions_plot, values='mention_count', names='brand_name', hole=0.5,
                                color_discrete_sequence=px.colors.qualitative.Pastel,
                                labels={'brand_name': 'Бренд', 'mention_count': 'Згадок'}
                            )
                            fig_brands.update_traces(textposition='inside', textinfo='percent+label', hovertemplate='<b>%{label}</b><br>Згадок: %{value}')
                            fig_brands.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=250)
                            st.plotly_chart(
                                fig_brands, 
                                use_container_width=True, 
                                config={'displayModeBar': False},
                                key=f"brands_chart_{selected_scan_id}_{str(uuid.uuid4())[:8]}" # унікальний ключ
                            )
                        with c_table:
                            st.dataframe(
                                scan_mentions_plot[['brand_name', 'mention_count', 'rank_position', 'sentiment_score']],
                                column_config={
                                    "brand_name": "Бренд",
                                    "mention_count": st.column_config.NumberColumn("Згадок"),
                                    "rank_position": st.column_config.NumberColumn("Позиція"),
                                    "sentiment_score": st.column_config.TextColumn("Тональність")
                                },
                                use_container_width=True, hide_index=True
                            )
                    else:
                        st.info("Брендів не знайдено.")
                else:
                    st.info("Брендів не знайдено.")
                
                st.markdown("<br>", unsafe_allow_html=True)

                # --- ДЖЕРЕЛА ---
                st.markdown(f"#### 🔗 Цитовані джерела {tooltip('Посилання, які надала модель.')}", unsafe_allow_html=True)
                try:
                    sources_resp = supabase.table("extracted_sources").select("*").eq("scan_result_id", selected_scan_id).execute()
                    sources_data = sources_resp.data
                    if sources_data:
                        df_src = pd.DataFrame(sources_data)
                        
                        if 'url' in df_src.columns:
                            if 'domain' not in df_src.columns:
                                df_src['domain'] = df_src['url'].apply(lambda x: str(x).split('/')[2] if x and '//' in str(x) else 'unknown')
                            
                            df_src['url'] = df_src['url'].apply(normalize_url)
                            if 'is_official' in df_src.columns:
                                df_src['status_text'] = df_src['is_official'].apply(lambda x: "✅ Офіційне" if x is True else "🔗 Зовнішнє")
                            else:
                                df_src['status_text'] = "🔗 Зовнішнє"

                            df_grouped_src = df_src.groupby(['url', 'domain', 'status_text'], as_index=False).size()
                            df_grouped_src = df_grouped_src.rename(columns={'size': 'count'})
                            df_grouped_src = df_grouped_src.sort_values(by='count', ascending=False)

                            c_src_chart, c_src_table = st.columns([1.3, 2], vertical_alignment="center")
                            
                            with c_src_chart:
                                domain_counts = df_grouped_src.groupby('domain')['count'].sum().reset_index()
                                fig_src = px.pie(
                                    domain_counts.head(10), values='count', names='domain', hole=0.5,
                                    labels={'domain': 'Домен', 'count': 'Кількість'}
                                )
                                fig_src.update_traces(textposition='inside', textinfo='percent', hovertemplate='<b>%{label}</b><br>Кількість: %{value}')
                                fig_src.update_layout(showlegend=False, margin=dict(t=0, b=0, l=0, r=0), height=200)
                                st.plotly_chart(
                                    fig_src, 
                                    use_container_width=True, 
                                    config={'displayModeBar': False},
                                    key=f"src_chart_{selected_scan_id}_{str(uuid.uuid4())[:8]}"
                                )

                            with c_src_table:
                                st.dataframe(
                                    df_grouped_src[['url', 'count']],
                                    use_container_width=True, hide_index=True,
                                    column_config={
                                        "url": st.column_config.LinkColumn("Посилання", width="large", validate="^https?://"),
                                        "count": st.column_config.NumberColumn("К-сть", width="small")
                                    }
                                )
                        else:
                            st.info("URL не знайдено.")
                    else:
                        st.info("ℹ️ Джерел не знайдено.")
                except Exception as e:
                    st.error(f"Помилка завантаження джерел: {e}")

    # Запускаємо фрагмент
    render_live_analytics()
