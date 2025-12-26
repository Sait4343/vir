def show_reports_page():
    """
    Сторінка Звітів (Фінальна версія).
    Виправлено:
    - Прибрано запис в неіснуючу колонку 'created_by'.
    - Виправлено логіку підключення до БД.
    - Видалення доступне тільки в Модерації (для адмінів).
    - Оновлено дизайн кнопок та текстів.
    """
    import streamlit as st
    import pandas as pd
    from datetime import datetime
    import streamlit.components.v1 as components
    import pytz 

    kyiv_tz = pytz.timezone('Europe/Kyiv')

    st.title("📊 Звіти")

    # 1. Надійна ініціалізація Supabase
    if 'supabase' in st.session_state:
        supabase = st.session_state['supabase']
    elif 'supabase' in globals():
        supabase = globals()['supabase']
    else:
        st.error("🚨 Помилка: відсутнє підключення до БД (змінна supabase не знайдена).")
        return
    
    proj = st.session_state.get("current_project")
    if not proj:
        st.info("Оберіть проект у сайдбарі.")
        return

    user_role = st.session_state.get("role", "user")
    is_admin = (user_role in ["admin", "super_admin"])
    
    # Вкладки
    tab_names = ["📥 Замовити звіт", "📂 Готові звіти"]
    if is_admin:
        tab_names.append("🛡️ Модерація звітів")
        
    tabs = st.tabs(tab_names)

    # =========================================================
    # ТАБ 1: ЗАМОВЛЕННЯ
    # =========================================================
    with tabs[0]:
        st.markdown("### 🚀 Генерація професійного AI-звіту")
        
        st.info("""
        **Що входить у цей звіт і яка його цінність?**
        
        Цей звіт — це комплексний аудит видимості вашого бренду в генеративних моделях (ChatGPT, Gemini, Perplexity). 
        Ми аналізуємо реальні відповіді ШІ на запити вашої цільової аудиторії.

        **Як формуються метрики:**
        1.  **Share of Voice (SOV):** Частка згадок вашого бренду порівняно з конкурентами.
        2.  **Тональність:** Відсотковий розподіл (Позитив/Нейтраль/Негатив).
        3.  **% Офіційних джерел:** Частка посилань на ваші верифіковані домени (Whitelist).
        4.  **Згадки домену:** Як часто ШІ дає прямі посилання на ваш сайт.
        
        *Звіт формується автоматично на основі останніх актуальних сканувань.*
        """)
        
        rep_name = st.text_input("Назва звіту", value=f"Звіт {proj.get('brand_name')} - {datetime.now().strftime('%d.%m.%Y')}")
        
        if st.button("✨ Сформувати звіт", type="primary"):
            with st.spinner("Аналіз даних, розрахунок метрик та генерація HTML..."):
                try:
                    # 1. Whitelist
                    wl_resp = supabase.table("official_assets").select("domain_or_url").eq("project_id", proj["id"]).execute()
                    whitelist_domains = [w['domain_or_url'] for w in wl_resp.data] if wl_resp.data else []

                    # 2. Keywords
                    kw_resp = supabase.table("keywords").select("id, keyword_text").eq("project_id", proj["id"]).execute()
                    kw_map = {k['id']: k['keyword_text'] for k in kw_resp.data} if kw_resp.data else {}
                    
                    if not kw_map:
                        st.error("У проекті немає ключових слів.")
                        st.stop()

                    # 3. Scans + Data
                    scans_resp = supabase.table("scan_results")\
                        .select("*, brand_mentions(*), extracted_sources(*)")\
                        .eq("project_id", proj["id"])\
                        .order("created_at", desc=True)\
                        .limit(2000)\
                        .execute()
                    
                    raw_scans = scans_resp.data if scans_resp.data else []
                    if not raw_scans:
                        st.error("Історія сканувань пуста.")
                        st.stop()

                    # 4. Snapshot Logic
                    processed_scans = []
                    for s in raw_scans:
                        s['keyword_text'] = kw_map.get(s['keyword_id'], "Unknown Query")
                        processed_scans.append(s)
                    
                    df_raw = pd.DataFrame(processed_scans)
                    if not df_raw.empty:
                        df_raw = df_raw.sort_values('created_at', ascending=False)
                        df_latest = df_raw.drop_duplicates(subset=['keyword_id', 'provider'], keep='first')
                        final_scans_data = df_latest.to_dict('records')
                    else:
                        final_scans_data = []

                    # 5. Generate HTML
                    html_code = generate_html_report_content(
                        proj.get('brand_name'), 
                        final_scans_data, 
                        whitelist_domains
                    )

                    # 6. Save (БЕЗ created_by, бо його немає в схемі)
                    supabase.table("reports").insert({
                        "project_id": proj["id"],
                        "report_name": rep_name,
                        "html_content": html_code,
                        "status": "pending"
                    }).execute()
                    
                    st.balloons()
                    st.success("✅ Звіт успішно сформовано! Очікуйте на модерацію.")
                    
                except Exception as e:
                    st.error(f"Помилка генерації: {e}")

    # =========================================================
    # ТАБ 2: ГОТОВІ ЗВІТИ (Перегляд)
    # =========================================================
    with tabs[1]:
        try:
            pub_resp = supabase.table("reports").select("*").eq("project_id", proj["id"]).eq("status", "published").order("created_at", desc=True).execute()
            reports = pub_resp.data if pub_resp.data else []
            
            if not reports:
                st.info("Поки що немає готових звітів.")
            else:
                for r in reports:
                    with st.expander(f"📄 {r['report_name']}", expanded=False):
                        # Кнопка завантаження (справа)
                        c_info, c_btn = st.columns([4, 1])
                        with c_btn:
                            st.download_button(
                                label="📥 Завантажити",
                                data=r['html_content'],
                                file_name=f"{r['report_name']}.html",
                                mime="text/html",
                                key=f"dl_btn_{r['id']}",
                                use_container_width=True
                            )
                        
                        # Відображення звіту
                        st.markdown("---")
                        components.html(r['html_content'], height=800, scrolling=True)
                        
        except Exception as e:
            st.error(f"Помилка завантаження: {e}")

    # =========================================================
    # ТАБ 3: МОДЕРАЦІЯ (Тільки Адмін)
    # =========================================================
    if is_admin:
        with tabs[2]:
            st.markdown("### 🛡️ Панель модератора")
            try:
                admin_resp = supabase.table("reports").select("*").eq("project_id", proj["id"]).order("created_at", desc=True).execute()
                all_reports = admin_resp.data if admin_resp.data else []
                
                if not all_reports:
                    st.info("Звітів немає.")
                else:
                    for pr in all_reports:
                        status_color = "orange" if pr['status'] == 'pending' else "green"
                        status_text = "ОЧІКУЄ" if pr['status'] == 'pending' else "ОПУБЛІКОВАНО"
                        
                        with st.container(border=True):
                            c_head, c_meta = st.columns([2, 1])
                            with c_head:
                                st.markdown(f"#### {pr['report_name']}")
                                st.markdown(f"Статус: :{status_color}[{status_text}]")
                            
                            with c_meta:
                                # Час
                                try:
                                    dt_utc = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
                                    dt_kyiv = dt_utc.astimezone(kyiv_tz)
                                    fmt_time = dt_kyiv.strftime('%d.%m.%Y %H:%M')
                                except:
                                    fmt_time = pr['created_at']
                                
                                st.caption(f"📅 {fmt_time}")
                                # Автор - прибрано, бо немає колонки created_by

                            # Редактор
                            with st.expander("✏️ Редагувати код"):
                                new_html = st.text_area(
                                    "HTML Code", 
                                    value=pr['html_content'], 
                                    height=300, 
                                    key=f"edit_{pr['id']}"
                                )
                                if st.button("💾 Зберегти зміни", key=f"save_{pr['id']}"):
                                    supabase.table("reports").update({"html_content": new_html}).eq("id", pr['id']).execute()
                                    st.success("Збережено!")
                                    st.rerun()

                            # Прев'ю
                            if st.checkbox("👁️ Прев'ю", key=f"preview_{pr['id']}"):
                                components.html(pr['html_content'], height=500, scrolling=True)

                            st.divider()
                            
                            # Дії
                            ac1, ac2, ac3 = st.columns([1, 1, 3])
                            with ac1:
                                if pr['status'] != 'published':
                                    if st.button("✅ Опублікувати", key=f"pub_{pr['id']}", type="primary"):
                                        supabase.table("reports").update({"status": "published"}).eq("id", pr['id']).execute()
                                        st.success("Готово!")
                                        st.rerun()
                                else:
                                    st.button("Вже опубліковано", disabled=True, key=f"dis_{pr['id']}")
                            
                            with ac3:
                                # Кнопка видалення з унікальним ключем
                                if st.button("🗑️ Видалити", key=f"del_adm_{pr['id']}", type="secondary"):
                                    supabase.table("reports").delete().eq("id", pr['id']).execute()
                                    st.warning("Видалено.")
                                    st.rerun() # Оновлюємо сторінку одразу
            except Exception as e:
                st.error(f"Помилка адмінки: {e}")
