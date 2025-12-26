import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from datetime import datetime, timedelta
import re

# 🔥 Імпорт підключення до БД (замість globals)
from utils.db import supabase

def show_dashboard():
    """
    Сторінка Дашборд.
    ВЕРСІЯ: FINAL FIXED MATH & NAMES.
    1. Тональність: 100% від суми згадок саме вашого бренду (total_brand).
    2. Назви: Chat GPT, Gemini, Perplexity.
    3. Імпорти: Використовується utils.db.
    """

    proj = st.session_state.get("current_project")
    if not proj:
        st.info("Спочатку створіть проект.")
        return

    # --- CSS ---
    st.markdown("""
    <style>
        h3 { font-size: 1.15rem !important; font-weight: 600 !important; padding-top: 20px !important; }
        .green-number { background-color: #00C896; color: white; width: 24px; height: 24px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: bold; font-size: 12px; }
        
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
        
        .competitor-highlight {
            color: #FF4B4B; 
            font-size: 14px; 
            font-weight: 700;
        }
    </style>
    """, unsafe_allow_html=True)

    st.title(f"📊 Дашборд: {proj.get('brand_name')}")

    # ==============================================================================
    # 2. ОТРИМАННЯ ДАНИХ
    # ==============================================================================
    with st.spinner("Аналіз даних..."):
        try:
            # Ключові слова
            kw_resp = supabase.table("keywords").select("id, keyword_text").eq("project_id", proj["id"]).execute()
            keywords_df = pd.DataFrame(kw_resp.data) if kw_resp.data else pd.DataFrame()
            
            # Результати сканування
            scan_resp = supabase.table("scan_results")\
                .select("id, provider, created_at, keyword_id")\
                .eq("project_id", proj["id"])\
                .order("created_at", desc=True)\
                .execute()
            scans_df = pd.DataFrame(scan_resp.data) if scan_resp.data else pd.DataFrame()
            
            mentions_df = pd.DataFrame()
            sources_df = pd.DataFrame()
            
            if not scans_df.empty:
                scan_ids = scans_df['id'].tolist()
                
                # Завантаження згадок (порціями по 200)
                chunk_size = 200
                all_mentions = []
                all_sources = []
                
                for i in range(0, len(scan_ids), chunk_size):
                    chunk = scan_ids[i:i + chunk_size]
                    m_resp = supabase.table("brand_mentions").select("*").in_("scan_result_id", chunk).execute()
                    if m_resp.data: all_mentions.extend(m_resp.data)
                    
                    s_resp = supabase.table("extracted_sources").select("*").in_("scan_result_id", chunk).execute()
                    if s_resp.data: all_sources.extend(s_resp.data)
                
                if all_mentions: mentions_df = pd.DataFrame(all_mentions)
                if all_sources: sources_df = pd.DataFrame(all_sources)

        except Exception as e:
            st.error(f"Помилка завантаження даних: {e}")
            return

    if scans_df.empty:
        st.info("Даних ще немає. Запустіть сканування.")
        return

    # ==============================================================================
    # 3. ОБРОБКА ДАНИХ
    # ==============================================================================
    def norm_provider(p):
        p = str(p).lower()
        if 'gpt' in p or 'openai' in p: return 'Chat GPT'    # Renamed
        if 'gemini' in p or 'google' in p: return 'Gemini'      # Renamed
        if 'perplexity' in p: return 'Perplexity'
        return 'Other'

    scans_df['provider_ui'] = scans_df['provider'].apply(norm_provider)
    scans_df['created_at'] = pd.to_datetime(scans_df['created_at'])

    # Назва бренду з налаштувань проекту (Original)
    target_brand_raw = proj.get('brand_name', '').strip()
    target_brand_lower = target_brand_raw.lower()
    
    if not mentions_df.empty:
        mentions_df['mention_count'] = pd.to_numeric(mentions_df['mention_count'], errors='coerce').fillna(0)
        mentions_df['rank_position'] = pd.to_numeric(mentions_df['rank_position'], errors='coerce').fillna(0)
        
        # Нормалізація тональності
        def normalize_sentiment(s):
            s_lower = str(s).lower()
            if 'поз' in s_lower or 'pos' in s_lower: return 'Позитивна'
            if 'нег' in s_lower or 'neg' in s_lower: return 'Негативна'
            if 'ней' in s_lower or 'neu' in s_lower: return 'Нейтральна'
            return 'Нейтральна'
            
        mentions_df['sentiment_score'] = mentions_df['sentiment_score'].apply(normalize_sentiment)

        df_full = pd.merge(mentions_df, scans_df, left_on='scan_result_id', right_on='id', suffixes=('_m', '_s'))
        
        # 🔥 ВИЗНАЧЕННЯ ЦІЛЬОВОГО БРЕНДУ (ПРОСТА ЛОГІКА)
        def check_is_target(row):
            # 1. Пріоритет: чи стоїть прапорець в базі (від n8n)
            flag_val = str(row.get('is_my_brand', '')).lower()
            if flag_val in ['true', '1', 't', 'yes', 'on']:
                return True
            
            # 2. Якщо прапорця немає - перевіряємо по назві (case-insensitive)
            mention_name = str(row.get('brand_name', '')).strip().lower()
            
            if target_brand_lower and mention_name:
                # Перевірка: чи входить одна назва в іншу
                if target_brand_lower in mention_name: return True
                if mention_name in target_brand_lower: return True
            
            return False

        df_full['is_target'] = df_full.apply(check_is_target, axis=1)
    else:
        df_full = pd.DataFrame()

    # ==============================================================================
    # 4. МЕТРИКИ ПО МОДЕЛЯХ
    # ==============================================================================
    st.markdown("### 🌐 Огляд по моделях")
    
    def get_llm_stats(model_name):
        model_scans = scans_df[scans_df['provider_ui'] == model_name]
        if model_scans.empty: return 0, 0, (0,0,0)
        
        # Беремо останній скан для кожного кейворда (snapshot)
        latest_scans = model_scans.sort_values('created_at', ascending=False).drop_duplicates('keyword_id')
        target_scan_ids = latest_scans['id'].tolist()
        
        if not target_scan_ids or df_full.empty: return 0, 0, (0,0,0)

        # Беремо всі згадки для цих сканів
        current_mentions = df_full[df_full['scan_result_id'].isin(target_scan_ids)]
        if current_mentions.empty: return 0, 0, (0,0,0)

        total_mentions = current_mentions['mention_count'].sum()
        
        # Наш бренд (фільтрація за is_target)
        my_mentions = current_mentions[current_mentions['is_target'] == True]
        my_count = my_mentions['mention_count'].sum()
        
        sov = (my_count / total_mentions * 100) if total_mentions > 0 else 0
        
        valid_ranks = my_mentions[my_mentions['rank_position'] > 0]
        rank = valid_ranks['rank_position'].mean() if not valid_ranks.empty else 0
        
        # 🔥 FIX: Тональність (100% сума від total_brand)
        pos_p, neu_p, neg_p = 0, 0, 0
        if not my_mentions.empty:
            counts = my_mentions['sentiment_score'].value_counts()
            
            raw_pos = counts.get('Позитивна', 0)
            raw_neu = counts.get('Нейтральна', 0)
            raw_neg = counts.get('Негативна', 0)
            
            # ТУТ ГОЛОВНЕ: Сума по ЗГАДКАХ бренду (а не по сканах)
            total_brand = raw_pos + raw_neu + raw_neg
            
            if total_brand > 0:
                pos_p = (raw_pos / total_brand * 100)
                neu_p = (raw_neu / total_brand * 100)
                neg_p = (raw_neg / total_brand * 100)
            
        return sov, rank, (pos_p, neu_p, neg_p)

    cols = st.columns(3)
    models_order = ['Chat GPT', 'Gemini', 'Perplexity']
    
    for i, model in enumerate(models_order):
        with cols[i]:
            sov, rank, (pos, neu, neg) = get_llm_stats(model)
            with st.container(border=True):
                st.markdown(f"**{model}**")
                c1, c2 = st.columns(2)
                
                c1.metric("SOV", f"{sov:.1f}%")
                c2.metric("Rank", f"#{rank:.1f}" if rank > 0 else "-")
                
                # --- SENTIMENT BLOCK ---
                # Дані є, якщо сума відсотків > 0 (або total_brand > 0 у функції вище)
                has_data = (pos + neu + neg) > 0.1 
                
                pie_values = [pos, neu, neg] if has_data else [1]
                pie_colors = ['#00C896', '#B0BEC5', '#FF4B4B'] if has_data else ['#E0E0E0']
                labels = ['Pos', 'Neu', 'Neg'] if has_data else ['No Data']

                # Легенда
                st.markdown(f"""
                <div class="sent-container">
                    <div class="sent-title">Загальна тональність</div>
                    <div class="sent-row text-pos"><span>Позитивна</span><span>{pos:.0f}%</span></div>
                    <div class="sent-row text-neu"><span>Нейтральна</span><span>{neu:.0f}%</span></div>
                    <div class="sent-row text-neg"><span>Негативна</span><span>{neg:.0f}%</span></div>
                </div>
                """, unsafe_allow_html=True)
                
                # Графік
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
                st.plotly_chart(fig_donut, use_container_width=True, config={'displayModeBar': False}, key=f"donut_{model}_{i}")

    # ==============================================================================
    # 5. ГРАФІК ДИНАМІКИ
    # ==============================================================================
    st.write("")
    st.markdown("### 📈 Динаміка бренду (SOV)")
    
    if not df_full.empty:
        df_full['date_day'] = df_full['created_at'].dt.floor('D')
        daily = df_full.groupby(['date_day', 'provider_ui']).apply(
            lambda x: pd.Series({
                'total': x['mention_count'].sum(),
                'my': x[x['is_target'] == True]['mention_count'].sum()
            })
        ).reset_index()
        daily['sov'] = (daily['my'] / daily['total'] * 100).fillna(0)
        
        fig = px.line(daily, x='date_day', y='sov', color='provider_ui', markers=True, 
                      color_discrete_map={'Perplexity':'#00C896', 'Chat GPT':'#FF4B4B', 'Gemini':'#3B82F6'})
        fig.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True, key="sov_main_chart")
    else:
        st.info("Немає даних.")

    # ==============================================================================
    # 6. КОНКУРЕНТНИЙ АНАЛІЗ
    # ==============================================================================
    st.write("")
    st.markdown("### 🏆 Конкурентний аналіз")

    if not df_full.empty:
        total_mentions_all = df_full['mention_count'].sum()
        total_kws_all = df_full['keyword_id'].nunique()

        df_target_raw = df_full[df_full['is_target'] == True]
        df_competitors_raw = df_full[df_full['is_target'] == False]

        def get_dominant_sentiment(series):
            if series.empty: return "-"
            mode = series.mode()
            return mode[0] if not mode.empty else "Нейтральна"

        if not df_target_raw.empty:
            merged_target = pd.Series({
                'brand_name': f"🟢 {target_brand_raw} (Ви)",
                'mentions': df_target_raw['mention_count'].sum(),
                'unique_kws': df_target_raw['keyword_id'].nunique(),
                'sentiment': get_dominant_sentiment(df_target_raw['sentiment_score']),
                'first_seen': df_target_raw['created_at'].min()
            })
            target_df = pd.DataFrame([merged_target])
        else:
            target_df = pd.DataFrame([{
                'brand_name': f"🟢 {target_brand_raw} (Ви)", 'mentions': 0, 'unique_kws': 0, 'sentiment': '-', 'first_seen': None
            }])

        def agg_competitors(x):
            return pd.Series({
                'mentions': x['mention_count'].sum(),
                'unique_kws': x['keyword_id'].nunique(),
                'sentiment': get_dominant_sentiment(x['sentiment_score']),
                'first_seen': x['created_at'].min()
            })
        
        if not df_competitors_raw.empty:
            competitors_agg = df_competitors_raw.groupby('brand_name').apply(agg_competitors).reset_index()
            competitors_top9 = competitors_agg.sort_values('mentions', ascending=False).head(9)
        else:
            competitors_top9 = pd.DataFrame()

        final_df = pd.concat([target_df, competitors_top9])
        final_df = final_df.sort_values('mentions', ascending=False)

        final_df['sov'] = (final_df['mentions'] / total_mentions_all).fillna(0)
        final_df['presence'] = (final_df['unique_kws'] / total_kws_all).fillna(0)

        rows = []
        for _, r in final_df.iterrows():
            d_str = r['first_seen'].strftime("%d.%m.%Y") if pd.notnull(r['first_seen']) else "-"
            rows.append({
                "Бренд": r['brand_name'], 
                "Згадок": r['mentions'],
                "SOV": r['sov'],
                "Присутність": r['presence'],
                "Тональність": r['sentiment'], 
                "Перша згадка": d_str
            })
            
        st.dataframe(
            pd.DataFrame(rows), 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Згадок": st.column_config.NumberColumn(format="%d"),
                "SOV": st.column_config.NumberColumn("Частка голосу (SOV)", format="%.1f%%"),
                "Присутність": st.column_config.NumberColumn("Присутність", format="%.0f%%"),
                "Тональність": st.column_config.TextColumn("Тональність"),
            }
        )
    else:
        st.info("Немає даних для аналізу конкурентів.")

    # ==============================================================================
    # 7. ДЕТАЛЬНА СТАТИСТИКА
    # ==============================================================================
    st.write("")
    st.markdown("### 📋 Детальна статистика по запитах")
    
    cols = st.columns([0.4, 2.5, 1, 1, 1, 1.2, 2])
    cols[1].markdown("**Запит**")
    cols[2].markdown("**Згадок**")
    cols[3].markdown("**SOV**")
    cols[4].markdown("**Позиція**")
    cols[5].markdown("**Тональність**")
    cols[6].markdown("**Топ Конкурент**")
    
    st.markdown("---")

    unique_kws = keywords_df.to_dict('records')
    
    for idx, kw in enumerate(unique_kws, 1):
        kw_id = kw['id']
        kw_text = kw['keyword_text']
        
        cur_sov, cur_rank, my_mentions_count = 0, 0, 0
        cur_sent = "—"
        top_comp_name, top_comp_val = "—", 0
        off_sources_count = 0
        has_data = False

        if not df_full.empty:
            kw_data = df_full[df_full['keyword_id'] == kw_id]
            
            if not kw_data.empty:
                has_data = True
                sorted_scans = kw_data.sort_values('created_at', ascending=False)
                latest_date = sorted_scans['created_at'].max()
                current_slice = sorted_scans[sorted_scans['created_at'] >= (latest_date - timedelta(hours=24))]

                my_rows = current_slice[current_slice['is_target'] == True]
                my_mentions_count = my_rows['mention_count'].sum()
                tot = current_slice['mention_count'].sum()
                cur_sov = (my_mentions_count / tot * 100) if tot > 0 else 0
                
                ranks = my_rows[my_rows['rank_position'] > 0]['rank_position']
                cur_rank = ranks.mean() if not ranks.empty else 0
                
                if not my_rows.empty:
                    cur_sent = my_rows['sentiment_score'].mode()[0]
                
                competitors = current_slice[current_slice['is_target'] == False]
                if not competitors.empty:
                    top_comp_name = competitors.groupby('brand_name')['mention_count'].sum().idxmax()
                    top_comp_val = competitors.groupby('brand_name')['mention_count'].sum().max()
                
                if not sources_df.empty:
                    scan_ids_kw = current_slice['scan_result_id'].unique()
                    kw_sources = sources_df[sources_df['scan_result_id'].isin(scan_ids_kw)]
                    if 'is_official' in kw_sources.columns:
                        off_sources_count = len(kw_sources[kw_sources['is_official'] == True])

        with st.container():
            c = st.columns([0.4, 2.5, 1, 1, 1, 1.2, 2])
            c[0].markdown(f"<div class='green-number'>{idx}</div>", unsafe_allow_html=True)
            c[1].markdown(f"**{kw_text}**")
            
            if has_data:
                c[2].markdown(f"**{int(my_mentions_count)}**")
                c[3].markdown(f"{cur_sov:.1f}%")
                c[4].markdown(f"#{cur_rank:.1f}" if cur_rank > 0 else "-")
                
                st_col = "#333"
                if "Поз" in str(cur_sent): st_col = "#00C896"
                elif "Нег" in str(cur_sent): st_col = "#FF4B4B"
                elif "Ней" in str(cur_sent): st_col = "#FFCE56"
                elif "—" in str(cur_sent): st_col = "#ccc"
                
                c[5].markdown(f"<span style='color:{st_col}; font-weight:bold'>{cur_sent}</span>", unsafe_allow_html=True)
                
                c[6].markdown(f"""
                <span class='competitor-highlight'>VS {top_comp_name} ({top_comp_val})</span><br>
                <span style='font-size:11px; color:#555;'>🔗 Офіц: {off_sources_count}</span>
                """, unsafe_allow_html=True)
            else:
                for i in range(2, 7): c[i].caption("—")
        
        st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)
