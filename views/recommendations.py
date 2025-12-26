import streamlit as st
import pandas as pd
import streamlit.components.v1 as components
from datetime import datetime, timedelta

# 🔥 Імпорт залежностей з утиліт (важливо для модульності)
from utils.db import supabase
from utils.n8n import trigger_ai_recommendation

def show_recommendations_page():
    """
    Сторінка рекомендацій.
    ВЕРСІЯ: MODULAR & STABLE.
    File prefix: "Recommendations_"
    Button label: "Завантажити Рекомендації"
    """

    # --- ПЕРЕВІРКА ПРОЕКТУ ---
    proj = st.session_state.get("current_project")
    user = st.session_state.get("user")
    
    if not proj:
        st.info("Спочатку оберіть проект.")
        return

    st.title(f"💡 Центр рекомендацій: {proj.get('brand_name')}")

    # --- 2. КАТЕГОРІЇ ---
    CATEGORIES = {
        "Digital": {
            "title": "Digital & Technical GEO",
            "desc": "Технічна оптимізація екосистеми бренду для алгоритмів AI.",
            "value": "LLM (ChatGPT, Gemini) — це програми. Якщо сайт технічно складний для них, вони його ігнорують. Ми аналізуємо код, розмітку Schema.org та доступність для ботів.",
            "prompt_context": "Analyze technical SEO, Schema markup, site structure, and data accessibility for LLM crawling. Focus on Technical GEO factors."
        },
        "Content": {
            "title": "Content Strategy",
            "desc": "Створення контенту, який AI захоче цитувати.",
            "value": "AI любить факти і структуру. Ми дамо план: які статті писати і як їх оформлювати, щоб стати 'джерелом істини' для нейромереж.",
            "prompt_context": "Generate content strategy optimized for Generative Search. Focus on answer structure, NLP-friendly formats, and topical authority."
        },
        "PR": {
            "title": "PR & Brand Authority",
            "desc": "Побудова авторитету через зовнішні джерела.",
            "value": "AI довіряє тому, про що пишуть авторитетні медіа. Ми визначимо, де вам треба з'явитися (Wiki, ЗМІ), щоб алгоритми вважали вас лідером.",
            "prompt_context": "Analyze brand authority signals, mentions in tier-1 media, and external trust factors influencing LLM perception."
        },
        "Social": {
            "title": "Social Media & UGC",
            "desc": "Вплив соціальних сигналів на видачу.",
            "value": "Gemini та Perplexity читають Reddit, LinkedIn та X у реальному часі. Ми покажемо, як керувати дискусією там, щоб AI бачив позитив.",
            "prompt_context": "Analyze social signals, User Generated Content (Reddit, LinkedIn, Reviews), and their impact on real-time AI answers."
        }
    }

    main_tab, history_tab = st.tabs(["🚀 Замовити рекомендацію", "📚 Історія рекомендацій"])

    # Підготовка безпечної назви бренду для файлів
    safe_brand_name = proj.get('brand_name', 'Brand').replace(" ", "_")

    # ========================================================
    # TAB 1: ЗАМОВЛЕННЯ
    # ========================================================
    with main_tab:
        st.markdown("Оберіть напрямок, щоб отримати стратегію **Generative Engine Optimization**.")
        
        cat_names = list(CATEGORIES.keys())
        cat_tabs = st.tabs([CATEGORIES[c]["title"] for c in cat_names])

        for idx, cat_key in enumerate(cat_names):
            info = CATEGORIES[cat_key]
            with cat_tabs[idx]:
                with st.container(border=True):
                    st.subheader(info["title"])
                    st.markdown(f"**Що це:** {info['desc']}")
                    st.info(f"💎 **Навіщо це вам:**\n\n{info['value']}")
                    st.write("") 
                    
                    # Кнопка генерації
                    btn_label = f"✨ Отримати рекомендації ({info['title']})"
                    
                    if st.button(btn_label, key=f"btn_rec_{cat_key}", type="primary", use_container_width=True):
                        
                        if proj.get('status') == 'blocked':
                            st.error("Проект заблоковано.")
                        else:
                            st.warning("⏳ Розпочато формування рекомендацій. Будь ласка, не закривайте сторінку і дочекайтеся завершення (це може зайняти до 60 секунд).")
                            
                            with st.spinner("Аналіз даних та генерація звіту..."):
                                # Виклик функції з utils/n8n.py
                                html_res = trigger_ai_recommendation(
                                    user=user, project=proj, category=info["title"], context_text=info["prompt_context"]
                                )
                                try:
                                    supabase.table("strategy_reports").insert({
                                        "project_id": proj["id"], 
                                        "category": cat_key, 
                                        "html_content": html_res, 
                                        "created_at": datetime.now().isoformat()
                                    }).execute()
                                    
                                    st.success("✅ Рекомендації успішно сформовано!")
                                    st.markdown(f"""
                                    <div style="padding:15px; border:1px solid #00C896; border-radius:5px; background-color:#f0fff4;">
                                        <p>Ваш звіт збережено. Перейдіть у вкладку <b>"Історія рекомендацій"</b>, щоб переглянути його.</p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                    
                                except Exception as e:
                                    st.error(f"Помилка збереження в БД: {e}")
                                    with st.expander("Резервний перегляд", expanded=True):
                                        components.html(html_res, height=600, scrolling=True)
                                        # Кнопка скачування (Резервна)
                                        st.download_button(
                                            "📥 Завантажити Рекомендації", 
                                            html_res, 
                                            file_name=f"Recommendations_{cat_key}_{safe_brand_name}.html", 
                                            mime="text/html"
                                        )

    # ========================================================
    # TAB 2: ІСТОРІЯ
    # ========================================================
    with history_tab:
        c_h1, c_h2 = st.columns(2)
        with c_h1:
            sel_cat_hist = st.multiselect("Фільтр по категорії", list(CATEGORIES.keys()), default=[])
        with c_h2:
            date_filter_options = ["Весь час", "Сьогодні", "Останні 7 днів", "Останні 30 днів"]
            sel_date_range = st.selectbox("Період", date_filter_options)

        try:
            query = supabase.table("strategy_reports").select("*").eq("project_id", proj["id"]).order("created_at", desc=True)
            hist_resp = query.execute()
            reports = hist_resp.data if hist_resp.data else []
            
            if reports:
                df_rep = pd.DataFrame(reports)
                df_rep['created_at_dt'] = pd.to_datetime(df_rep['created_at'])
                
                # Фільтри
                if sel_cat_hist:
                    df_rep = df_rep[df_rep['category'].isin(sel_cat_hist)]
                
                # Обробка часових поясів для коректного порівняння
                if not df_rep.empty and df_rep['created_at_dt'].dt.tz is None:
                     # Припускаємо UTC, якщо таймзона не задана
                     df_rep['created_at_dt'] = df_rep['created_at_dt'].dt.tz_localize('UTC')
                
                now = datetime.now(df_rep['created_at_dt'].dt.tz if not df_rep.empty else None)
                
                if sel_date_range == "Сьогодні":
                    df_rep = df_rep[df_rep['created_at_dt'].dt.date == now.date()]
                elif sel_date_range == "Останні 7 днів":
                    df_rep = df_rep[df_rep['created_at_dt'] >= (now - timedelta(days=7))]
                elif sel_date_range == "Останні 30 днів":
                    df_rep = df_rep[df_rep['created_at_dt'] >= (now - timedelta(days=30))]
                
                if df_rep.empty:
                    st.info("За обраними критеріями звітів не знайдено.")
                else:
                    for _, row in df_rep.iterrows():
                        cat_nice = CATEGORIES.get(row['category'], {}).get('title', row['category'])
                        try: date_str = row['created_at'][:16].replace('T', ' ')
                        except: date_str = "-"
                        
                        # Формуємо красиву дату для файлу
                        date_file = date_str.replace(" ", "_").replace(":", "-")

                        with st.expander(f"📑 {cat_nice} | {date_str}"):
                            c_dl, c_del = st.columns([4, 1])
                            
                            with c_dl:
                                file_n = f"Recommendations_{row['category']}_{safe_brand_name}_{date_file}.html"
                                
                                st.download_button(
                                    label="📥 Завантажити Рекомендації", 
                                    data=row['html_content'], 
                                    file_name=file_n, 
                                    mime="text/html",
                                    key=f"dl_hist_{row['id']}"
                                )
                            
                            with c_del:
                                del_key = f"confirm_del_{row['id']}"
                                if del_key not in st.session_state:
                                    st.session_state[del_key] = False

                                if not st.session_state[del_key]:
                                    if st.button("🗑️", key=f"pre_del_{row['id']}", help="Видалити звіт"):
                                        st.session_state[del_key] = True
                                        st.rerun()
                                else:
                                    col_yes, col_no = st.columns(2)
                                    if col_yes.button("✅", key=f"yes_{row['id']}"):
                                        supabase.table("strategy_reports").delete().eq("id", row['id']).execute()
                                        st.session_state[del_key] = False
                                        st.rerun()
                                    if col_no.button("❌", key=f"no_{row['id']}"):
                                        st.session_state[del_key] = False
                                        st.rerun()
                            
                            st.divider()
                            components.html(row['html_content'], height=500, scrolling=True)
            else:
                st.info("Історія рекомендацій порожня. Згенеруйте першу стратегію.")
                
        except Exception as e:
            st.warning(f"Неможливо завантажити історію: {e}")
