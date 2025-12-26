def show_admin_page():
    """
    Адмін-панель (CRM).
    ВЕРСІЯ: PROJECT NAME / BRAND NAME.
    Відображення: "Назва проекту / Назва бренду" у списку.
    """
    import pandas as pd
    import streamlit as st
    import numpy as np
    import time
    import plotly.express as px

    # --- 0. ПІДКЛЮЧЕННЯ ---
    if 'supabase' not in globals():
        if 'supabase' in st.session_state:
            supabase = st.session_state['supabase']
        else:
            st.error("🚨 Помилка: Змінна 'supabase' не знайдена.")
            return
    else:
        supabase = globals()['supabase']

    # --- ХЕЛПЕРИ ---
    def clean_data_for_json(data):
        if isinstance(data, dict): return {k: clean_data_for_json(v) for k, v in data.items()}
        elif isinstance(data, list): return [clean_data_for_json(v) for v in data]
        elif isinstance(data, (np.int64, np.int32, np.integer)): return int(data)
        elif isinstance(data, (np.float64, np.float32, np.floating)): return float(data)
        elif isinstance(data, (np.bool_, bool)): return bool(data)
        elif pd.isna(data): return None
        return data

    def update_project_field(proj_id, field, value):
        try:
            val = clean_data_for_json(value)
            supabase.table("projects").update({field: val}).eq("id", proj_id).execute()
            
            if "my_projects" in st.session_state: del st.session_state["my_projects"]
            if "all_projects_admin" in st.session_state: del st.session_state["all_projects_admin"]
            
            st.toast(f"✅ Оновлено: {field} -> {value}")
            time.sleep(0.5)
        except Exception as e:
            st.error(f"Помилка оновлення: {e}")

    st.title("🛡️ Admin Panel (CRM)")

    # --- 1. ОТРИМАННЯ ДАНИХ ---
    try:
        # Отримуємо проекти
        projects_resp = supabase.table("projects").select("*").execute()
        projects_data = projects_resp.data if projects_resp.data else []

        # Отримуємо кількість запитів для статистики
        kws_resp = supabase.table("keywords").select("project_id").execute()
        kws_df = pd.DataFrame(kws_resp.data) if kws_resp.data else pd.DataFrame()
        kw_counts = kws_df['project_id'].value_counts().to_dict() if not kws_df.empty else {}

        # Отримуємо користувачів
        users_resp = supabase.table("profiles").select("*").execute()
        users_data = users_resp.data if users_resp.data else []
        
        # Мапа користувачів для швидкого пошуку
        user_map = {}
        for u in users_data:
            f_name = u.get('first_name', '') or ''
            l_name = u.get('last_name', '') or ''
            full_name = f"{f_name} {l_name}".strip() or u.get('email', 'Unknown')
            user_map[u['id']] = {
                "full_name": full_name,
                "role": u.get('role', 'user'),
                "email": u.get('email', '-'),
                "created_at": u.get('created_at', '')
            }

    except Exception as e:
        st.error(f"Помилка завантаження даних: {e}")
        return

    # --- 2. KPI ---
    if projects_data:
        df_stats = pd.DataFrame(projects_data)
        total = len(df_stats)
        active = len(df_stats[df_stats['status'] == 'active'])
        blocked = len(df_stats[df_stats['status'] == 'blocked'])
        trial = len(df_stats[df_stats['status'] == 'trial'])
        
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Всього проектів", total)
        k2.metric("Active", active)
        k3.metric("Trial", trial)
        k4.metric("Blocked", blocked)

    st.write("")

    # --- 3. ВКЛАДКИ ---
    tab_list, tab_users = st.tabs(["📂 Список проектів", "👥 Користувачі & Права"])

    # ========================================================
    # TAB 1: СПИСОК ПРОЕКТІВ
    # ========================================================
    with tab_list:
        st.markdown("##### 🔍 Фільтрація та Пошук")
        
        fc1, fc2, fc3 = st.columns([2, 1.5, 1])
        with fc1:
            search_query = st.text_input("Пошук", placeholder="Назва, ID, домен, email власника", key="adm_search")
        with fc2:
            status_filter = st.multiselect("Статус", ["active", "trial", "blocked"], default=[], key="adm_status_filter", placeholder="Всі статуси")
        with fc3:
            sort_order = st.selectbox("Сортування", ["Найновіші", "Найстаріші"], key="adm_sort")

        st.divider()
        
        filtered_projects = []
        if projects_data:
            for p in projects_data:
                u_id = p.get('user_id')
                owner = user_map.get(u_id, {"full_name": "", "email": ""})
                
                p_int = p.get('project_name') or ""
                p_brand = p.get('brand_name') or ""
                p_domain = p.get('domain') or ""
                p_id_str = str(p.get('id', ''))
                
                # Пошук по всіх полях
                search_text = f"{p_int} {p_brand} {p_domain} {p_id_str} {owner['full_name']} {owner['email']}".lower()
                
                if search_query and search_query.lower() not in search_text: continue
                if status_filter and p.get('status', 'trial') not in status_filter: continue
                
                filtered_projects.append(p)

            reverse_sort = True if sort_order == "Найновіші" else False
            filtered_projects.sort(key=lambda x: x.get('created_at', ''), reverse=reverse_sort)

        # Header
        h0, h1, h_dash, h2, h3, h_cnt, h4, h5 = st.columns([0.3, 2.5, 0.4, 1.3, 1.2, 0.7, 0.9, 0.5])
        h0.markdown("**#**")
        h1.markdown("**Проект / Користувач**")
        h_dash.markdown("") 
        h2.markdown("**Статус**")
        h3.markdown("**Автосканування**")
        h_cnt.markdown("**Запитів**")
        h4.markdown("**Дата**")
        h5.markdown("**Дії**")
        st.markdown("<hr style='margin: 5px 0'>", unsafe_allow_html=True)

        if not filtered_projects: st.info("Проектів не знайдено.")

        for idx, p in enumerate(filtered_projects, 1):
            p_id = p['id']
            u_id = p.get('user_id')
            owner_info = user_map.get(u_id, {"full_name": "Невідомий", "role": "user", "email": "-"})
            
            # 🔥 ФОРМУВАННЯ НАЗВИ: "Project Name / Brand Name"
            p_internal = p.get('project_name')
            p_brand = p.get('brand_name')
            domain = p.get('domain', '')
            
            if p_internal and p_brand:
                # Якщо вони однакові, показуємо один раз
                if p_internal.strip() == p_brand.strip():
                    clean_name = p_internal
                else:
                    clean_name = f"{p_internal} / {p_brand}"
            elif p_internal:
                clean_name = p_internal
            elif p_brand:
                clean_name = p_brand
            else:
                # Якщо назв немає взагалі, беремо домен або заглушку
                clean_name = domain.replace('https://', '').replace('www.', '').split('/')[0] if domain else "Без назви"

            # ЛОГОТИП
            logo_url = None
            backup_logo_url = None
            if domain:
                clean_d = domain.lower().replace('https://', '').replace('http://', '').replace('www.', '')
                if '/' in clean_d: clean_d = clean_d.split('/')[0]
                logo_url = f"https://cdn.brandfetch.io/{clean_d}"
                backup_logo_url = f"https://www.google.com/s2/favicons?domain={clean_d}&sz=64"

            k_count = kw_counts.get(p_id, 0)

            with st.container():
                c0, c1, c_dash, c2, c3, c_cnt, c4, c5 = st.columns([0.3, 2.5, 0.4, 1.3, 1.2, 0.7, 0.9, 0.5])

                with c0: st.caption(f"{idx}")

                with c1:
                    if logo_url:
                        sub_c1, sub_c2 = st.columns([0.15, 0.85])
                        with sub_c1:
                            img_html = f'<img src="{logo_url}" style="width: 30px; border-radius: 4px; pointer-events: none;" onerror="this.onerror=null; this.src=\'{backup_logo_url}\';">'
                            st.markdown(img_html, unsafe_allow_html=True)
                        with sub_c2:
                            st.markdown(f"**{clean_name}**")
                    else:
                        st.markdown(f"**{clean_name}**")
                    
                    st.caption(f"ID: `{p_id}`")
                    if domain: st.caption(f"🌐 {domain}")
                    st.caption(f"👤 {owner_info['full_name']} | {owner_info['email']}")

                with c_dash:
                    if st.button("↗️", key=f"goto_{p_id}", help="Відкрити дашборд"):
                        st.session_state["current_project"] = p
                        st.session_state["force_redirect_to"] = "Дашборд"
                        st.session_state["menu_id_counter"] = st.session_state.get("menu_id_counter", 0) + 1
                        st.session_state["focus_keyword_id"] = None
                        st.rerun()
                        
                with c2:
                    curr_status = p.get('status', 'trial')
                    opts = ["trial", "active", "blocked"]
                    try: idx_s = opts.index(curr_status)
                    except: idx_s = 0
                    
                    new_status = st.selectbox("St", opts, index=idx_s, key=f"st_{p_id}", label_visibility="collapsed")
                    if new_status != curr_status:
                        update_project_field(p_id, "status", new_status)

                with c3:
                    allow_cron = p.get('allow_cron', False)
                    new_cron = st.checkbox("Дозволити", value=allow_cron, key=f"cr_{p_id}")
                    if new_cron != allow_cron:
                        update_project_field(p_id, "allow_cron", new_cron)

                with c_cnt:
                    st.markdown(f"**{k_count}**")

                with c4:
                    raw_date = p.get('created_at', '')
                    if raw_date: st.caption(raw_date[:10])

                with c5:
                    confirm_key = f"confirm_del_{p_id}"
                    if not st.session_state.get(confirm_key, False):
                        if st.button("🗑", key=f"del_btn_{p_id}"):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        if st.button("✅", key=f"yes_{p_id}"):
                            try:
                                supabase.table("projects").delete().eq("id", p_id).execute()
                                st.success("Видалено!")
                                time.sleep(0.5)
                                st.rerun()
                            except Exception as e:
                                st.error(str(e))
                        if st.button("❌", key=f"no_{p_id}"):
                            st.session_state[confirm_key] = False
                            st.rerun()
                
                st.markdown("<hr style='margin: 5px 0; border-top: 1px solid #eee;'>", unsafe_allow_html=True)

    # ========================================================
    # TAB 2: КОРИСТУВАЧІ ТА ПРАВА
    # ========================================================
    with tab_users:
        
        # --- БЛОК 1: ТАБЛИЦЯ КОРИСТУВАЧІВ ---
        st.markdown("##### 👥 База користувачів")

        uf1, uf2 = st.columns(2)
        with uf1:
            u_search = st.text_input("🔍 Пошук користувача", placeholder="Ім'я або email")
        with uf2:
            role_filter = st.multiselect("Роль", ["user", "admin", "super_admin"], default=[])

        if users_data:
            proj_df = pd.DataFrame(projects_data)
            
            user_table_data = []
            for u in users_data:
                full_name = f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                email = u.get('email', '')
                
                search_target = f"{full_name} {email}".lower()
                if u_search and u_search.lower() not in search_target: continue
                if role_filter and u.get('role', 'user') not in role_filter: continue

                user_projs = []
                if not proj_df.empty and 'user_id' in proj_df.columns:
                    my_projs = proj_df[proj_df['user_id'] == u['id']]
                    for _, p_row in my_projs.iterrows():
                        p_nm = p_row.get('brand_name') or p_row.get('project_name') or 'NoName'
                        p_dt = p_row.get('created_at', '')[:10]
                        user_projs.append(f"{p_nm} ({p_dt})")
                
                projs_str = "\n".join(user_projs) if user_projs else "-"

                user_table_data.append({
                    "id": u['id'],
                    "Ім'я": full_name,
                    "Email": email,
                    "Роль": u.get('role', 'user'),
                    "Проекти": projs_str, 
                    "Зареєстрований": u.get('created_at', '')[:10]
                })
            
            df_users_view = pd.DataFrame(user_table_data)
            
            if not df_users_view.empty:
                df_users_view.index = np.arange(1, len(df_users_view) + 1)
                
                edited_users = st.data_editor(
                    df_users_view,
                    column_config={
                        "id": st.column_config.TextColumn("User ID", disabled=True, width="small"),
                        "Email": st.column_config.TextColumn("Email", disabled=True),
                        "Ім'я": st.column_config.TextColumn("Ім'я", disabled=True),
                        "Проекти": st.column_config.TextColumn("Проекти (Дата)", disabled=True, width="large"),
                        "Зареєстрований": st.column_config.TextColumn("Дата реєстрації", disabled=True),
                        "Роль": st.column_config.SelectboxColumn("Роль", options=["user", "admin", "super_admin"], required=True)
                    },
                    use_container_width=True,
                    key="admin_users_final_v4"
                )

                if st.button("💾 Зберегти зміни прав"):
                    try:
                        changes_count = 0
                        updated_rows = edited_users.to_dict('index') 
                        
                        for idx, row in updated_rows.items():
                            uid = row['id']
                            new_role = row['Роль']
                            
                            old_user = next((u for u in users_data if u['id'] == uid), None)
                            if old_user and old_user.get('role') != new_role:
                                supabase.table("profiles").update({"role": new_role}).eq("id", uid).execute()
                                changes_count += 1
                        
                        if changes_count > 0:
                            st.success(f"Успішно оновлено {changes_count} користувачів!")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.info("Змін не виявлено.")
                            
                    except Exception as e:
                        st.error(f"Помилка збереження: {e}")
            else:
                st.warning("Користувачів не знайдено.")
        else:
            st.warning("База користувачів пуста.")

        st.divider()

        # --- БЛОК 2: ПРИЗНАЧЕННЯ ПРОЕКТІВ ---
        with st.expander("🛠️ Призначити проект користувачу (зміна власника)", expanded=False):
            st.info("Тут ви можете передати існуючий проект іншому користувачу.")
            
            c_asn_1, c_asn_2, c_asn_3 = st.columns([1.5, 1.5, 1])
            
            # 1. Вибір користувача
            user_options = {f"{u['email']} ({u.get('first_name','')} {u.get('last_name','')})": u['id'] for u in users_data}
            
            with c_asn_1:
                selected_user_key = st.selectbox("1. Оберіть нового власника", options=list(user_options.keys()))
            
            # 2. Вибір проекту
            proj_options = {}
            for p in projects_data:
                owner_id = p.get('user_id')
                owner_email = user_map.get(owner_id, {}).get('email', 'Unknown')
                label = f"{p.get('brand_name', 'No Name')} (Власник: {owner_email})"
                proj_options[label] = p['id']
                
            with c_asn_2:
                selected_proj_key = st.selectbox("2. Оберіть проект для передачі", options=list(proj_options.keys()))
            
            with c_asn_3:
                st.write("")
                st.write("")
                if st.button("🔄 Призначити", type="primary", use_container_width=True):
                    if selected_user_key and selected_proj_key:
                        target_user_id = user_options[selected_user_key]
                        target_proj_id = proj_options[selected_proj_key]
                        
                        try:
                            supabase.table("projects").update({"user_id": target_user_id}).eq("id", target_proj_id).execute()
                            st.success(f"Проект успішно передано користувачу {selected_user_key}!")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Помилка при передачі: {e}")
                    else:
                        st.warning("Оберіть користувача та проект.")

        st.divider()
        st.markdown("##### 📈 Динаміка реєстрацій")
        
        df_chart = pd.DataFrame(users_data)
        if 'created_at' in df_chart.columns:
            df_chart['date'] = pd.to_datetime(df_chart['created_at']).dt.date
            from datetime import timedelta
            time_filter = st.selectbox("Період", ["Останні 7 днів", "Останні 30 днів", "Останні 90 днів", "Весь час"], index=1)
            
            today = pd.to_datetime("today").date()
            if "7" in time_filter: start_date = today - timedelta(days=7)
            elif "30" in time_filter: start_date = today - timedelta(days=30)
            elif "90" in time_filter: start_date = today - timedelta(days=90)
            else: start_date = df_chart['date'].min()
            
            df_chart_filtered = df_chart[df_chart['date'] >= start_date]
            reg_counts = df_chart_filtered.groupby('date').size().reset_index(name='count')
            
            if not reg_counts.empty:
                fig = px.bar(reg_counts, x='date', y='count', labels={'date': 'Дата', 'count': 'Нових користувачів'})
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Немає реєстрацій за цей період.")
