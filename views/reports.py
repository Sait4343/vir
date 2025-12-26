import streamlit as st
import pandas as pd
from datetime import datetime
import streamlit.components.v1 as components
import pytz 
import re
from urllib.parse import urlparse

# 🔥 Імпорт залежностей з утиліт (для стабільної роботи)
from utils.db import supabase

# --- ФУНКЦІЯ ГЕНЕРАЦІЇ HTML ЗВІТУ (Вбудована сюди для надійності) ---
def generate_html_report_content(project_name, scans_data, whitelist_domains):
    """
    Генерує HTML-звіт.
    ВЕРСІЯ: FINAL CORRECTED MATH + UI.
    """
    current_date = datetime.now().strftime('%d.%m.%Y')

    # --- Helpers ---
    def safe_int(val):
        try: return int(float(val))
        except: return 0

    def get_domain(url):
        try: return urlparse(str(url)).netloc.replace('www.', '').lower()
        except: return ""

    def is_url_official(url, domains_list):
        if not url or not domains_list: return False
        try:
            url_lower = str(url).lower()
            for domain in domains_list:
                clean_d = str(domain).lower().replace('https://', '').replace('http://', '').replace('www.', '').strip()
                if clean_d and clean_d in url_lower: return True
            return False
        except: return False

    def format_llm_text(text):
        if not text: return "Текст відповіді відсутній."
        txt = str(text)
        txt = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', txt)
        txt = txt.replace('* ', '<br>• ')
        txt = txt.replace('\n', '<br>')
        return txt

    # --- 0. PRE-CALCULATE GLOBAL SORT ORDER ---
    query_time_map = {}
    for s in scans_data:
        kw = s.get('keyword_text', '')
        t = s.get('created_at', '')
        if kw and (kw not in query_time_map or t > query_time_map[kw]):
            query_time_map[kw] = t

    # --- UI Mapping ---
    PROVIDER_MAPPING = {
        "perplexity": "Perplexity",
        "gpt-4o": "Chat GPT",         
        "gpt-4": "Chat GPT",          
        "gemini-1.5-pro": "Gemini",   
        "gemini": "Gemini"            
    }
    
    def get_ui_provider(p):
        p_str = str(p).lower()
        for k, v in PROVIDER_MAPPING.items():
            if k in p_str: return v
        return str(p).capitalize()

    # --- Group Data ---
    data_by_provider = {}
    target_norm = str(project_name).lower().strip().split(' ')[0] if project_name else ""

    for scan in scans_data:
        prov_ui = get_ui_provider(scan.get('provider', 'Other'))
        if prov_ui not in data_by_provider:
            data_by_provider[prov_ui] = []
        
        # Mentions Processing
        mentions = scan.get('brand_mentions', [])
        processed_mentions = []
        for m in mentions:
            b_name = str(m.get('brand_name', '')).lower().strip()
            is_db_flag = str(m.get('is_my_brand', '')).lower() in ['true', '1', 't', 'yes', 'on']
            is_text_match = (target_norm in b_name) if target_norm else False
            
            m['is_real_target'] = is_db_flag or is_text_match
            m['mention_count'] = safe_int(m.get('mention_count', 0))
            m['rank_position'] = safe_int(m.get('rank_position', 0))
            
            raw_sent = str(m.get('sentiment_score', '')).lower()
            if 'поз' in raw_sent or 'pos' in raw_sent: m['sentiment_score'] = 'Позитивна'
            elif 'нег' in raw_sent or 'neg' in raw_sent: m['sentiment_score'] = 'Негативна'
            elif 'ней' in raw_sent or 'neu' in raw_sent: m['sentiment_score'] = 'Нейтральна'
            else: m['sentiment_score'] = 'Не визначено'

            processed_mentions.append(m)
        scan['brand_mentions'] = processed_mentions

        # Sources Processing
        sources = scan.get('extracted_sources', [])
        processed_sources = []
        for s in sources:
            url = s.get('url', '')
            s['is_official_calc'] = is_url_official(url, whitelist_domains)
            s['domain_clean'] = get_domain(url)
            processed_sources.append(s)
        scan['extracted_sources'] = processed_sources
        
        data_by_provider[prov_ui].append(scan)

    providers_ui = sorted(data_by_provider.keys())

    # --- CSS ---
    css_styles = '''
    @font-face { font-family: 'Golca'; src: url('') format('woff2'); font-weight: normal; font-style: normal; }
    * { box-sizing: border-box; }
    body { margin: 0; padding: 20px; background-color: #00d18f; font-family: 'Golca', 'Montserrat', sans-serif; color: #333; line-height: 1.6; position: relative; }
    .content-card { background: #ffffff; border-radius: 20px; padding: 40px; max-width: 1000px; margin: 0 auto; box-shadow: 0 10px 40px rgba(0,0,0,0.15); position: relative; z-index: 10; }
    .virshi-logo-container { text-align: center; margin: 0 auto 20px auto; }
    .logo-img-real { max-width: 150px; height: auto; }
    .report-header { text-align: center; border-bottom: 2px solid #eee; padding-bottom: 20px; margin-bottom: 30px; }
    h1 { font-size: 28px; color: #2c3e50; margin: 0; font-weight: 800; }
    .subtitle { color: #888; margin-top: 10px; font-size: 14px; }
    
    .tabs-nav { display: flex; justify-content: center; gap: 10px; margin-bottom: 30px; flex-wrap: wrap; }
    .tab-btn { padding: 12px 25px; border: 2px solid #00d18f; background: #fff; color: #00d18f; border-radius: 30px; cursor: pointer; font-weight: 800; font-size: 14px; transition: all 0.3s ease; text-transform: uppercase; }
    .tab-btn.active, .tab-btn:hover { background: #00d18f; color: #fff; }
    .tab-content { display: none; animation: fadeIn 0.5s; }
    .tab-content.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }

    .nav-side-btn {
        position: fixed; top: 50%; transform: translateY(-50%);
        background-color: #ffffff; border: 2px solid #00d18f; color: #00d18f; 
        padding: 12px 30px; cursor: pointer; z-index: 9999; font-weight: 800; font-size: 14px;
        border-radius: 50px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: all 0.3s ease;
        max-width: 180px; text-align: center; text-transform: uppercase; font-family: 'Montserrat', sans-serif;
    }
    .nav-side-btn:hover { background-color: #00d18f; color: #ffffff; transform: translateY(-50%) scale(1.05); box-shadow: 0 6px 20px rgba(0, 209, 143, 0.3); }
    .nav-left { left: 20px; }
    .nav-right { right: 20px; }
    
    .go-top-btn {
        position: fixed; bottom: 30px; right: 30px; width: 50px; height: 50px;
        background-color: #2c3e50; color: #fff; border-radius: 50%; border: none; cursor: pointer;
        z-index: 10000; font-size: 24px; display: none; align-items: center; justify-content: center;
        box-shadow: 0 4px 10px rgba(0,0,0,0.3); transition: 0.3s;
    }
    .go-top-btn:hover { background-color: #00d18f; transform: translateY(-3px); }

    @media (max-width: 1300px) { .nav-side-btn { display: none; } .content-card { padding: 20px; } }

    .kpi-row { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 15px; margin-bottom: 20px; }
    .kpi-box { flex: 1 1 220px; border: 2px solid #00d18f; border-radius: 15px; padding: 20px; text-align: center; background: #e0f2f1; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; position: relative; min-height: 200px; }
    .kpi-title { font-size: 13px; text-transform: uppercase; font-weight: bold; color: #555; margin-bottom: 10px; height: 30px; display: flex; align-items: center; justify-content: center; width: 100%; }
    .kpi-big-num { font-size: 28px; font-weight: 800; color: #2c3e50; margin-bottom: 10px; }
    .chart-container { position: relative; width: 130px; height: 130px; margin: auto; }
    .kpi-tooltip { visibility: hidden; opacity: 0; width: 220px; background-color: #2c3e50; color: #fff; text-align: center; border-radius: 8px; padding: 10px; position: absolute; z-index: 100; bottom: 105%; left: 50%; transform: translateX(-50%); font-size: 11px; transition: opacity 0.3s; pointer-events: none; }
    .kpi-box:hover .kpi-tooltip { visibility: visible; opacity: 1; }

    .summary-section { margin-top: 40px; margin-bottom: 30px; }
    .summary-header { font-size: 18px; font-weight: 800; color: #2c3e50; border-left: 5px solid #00d18f; padding-left: 15px; margin-bottom: 15px; }
    table.summary-table { width: 100%; border-collapse: collapse; font-size: 13px; border: 1px solid #eee; }
    table.summary-table th { background: #4DD0E1; color: #fff; padding: 10px; text-align: left; font-weight: 700; text-transform: uppercase; }
    table.summary-table td { padding: 10px; border-bottom: 1px solid #eee; color: #333; }
    table.summary-table tr:nth-child(even) { background-color: #f9f9f9; }

    h3 { font-size: 20px; color: #2c3e50; margin-top: 40px; margin-bottom: 20px; padding-left: 15px; border-left: 5px solid #00d18f; font-weight: 800; }

    .item-box { border: 2px solid #4DD0E1; border-radius: 15px; margin-bottom: 20px; overflow: hidden; background: #fff; }
    .accordion-trigger { background: #fff; padding: 15px 20px; display: flex; align-items: center; gap: 15px; cursor: pointer; transition: 0.3s; justify-content: space-between; }
    .accordion-trigger:hover { background-color: #f9f9f9; }
    .accordion-trigger.active { background-color: #f0fdff; border-bottom: 1px solid #eee; }
    .item-number-wrapper { width: 36px; height: 36px; background: #00d18f; border-radius: 50%; display: flex; align-items: center; justify-content: center; color: #fff; font-weight: bold; font-size: 14px; flex-shrink: 0; }
    .item-query { font-size: 15px; font-weight: bold; color: #333; flex-grow: 1; margin-left: 15px;}
    
    .cards-row { display: flex; flex-wrap: wrap; gap: 10px; padding: 20px; background: #fff; border-bottom: 1px solid #eee; }
    .metric-card { flex: 1 1 200px; background: #ffffff; border: 1px solid #e0e0e0; border-top: 4px solid #00d18f; border-radius: 8px; padding: 15px; text-align: center; }
    .mc-label { font-size: 10px; font-weight: 700; text-transform: uppercase; color: #888; margin-bottom: 5px; display:flex; align-items:center; justify-content:center; gap:5px; }
    .mc-val { font-size: 20px; font-weight: 800; color: #333; }
    .info-icon { display:inline-block; width:14px; height:14px; background:#3b82f6; color:white; border-radius:50%; font-size:10px; line-height:14px; text-align:center; cursor:help; }

    .item-response { background-color: #f9fafb; color: #1d192b; padding: 25px; font-size: 14px; text-align: left; line-height: 1.6; }
    .response-label { font-weight: bold; color: #5e35b1; margin-bottom: 15px; display: block; font-size: 16px; border-bottom: 1px dashed #5e35b1; padding-bottom: 5px; width: fit-content; }

    .detail-charts-wrapper { display: flex; flex-wrap: wrap; gap: 20px; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e0e0e0; }
    .detail-chart-block { flex: 1 1 400px; min-width: 0; }
    .detail-title { font-weight: bold; font-size: 14px; margin-bottom: 10px; color: #2c3e50; border-left: 3px solid #00d18f; padding-left: 10px; }
    
    table.inner-table { width: 100%; border-collapse: collapse; font-size: 12px; border: 1px solid #eee; }
    table.inner-table th { background: #f1f3f5; padding: 8px; text-align: left; color: #555; font-weight: 600; border-bottom: 1px solid #ddd; }
    table.inner-table td { padding: 8px; border-bottom: 1px solid #eee; color: #333; }
    
    .cta-block { margin-top: 40px; padding: 20px; background-color: #e0f2f1; border: 2px solid #00d18f; border-radius: 15px; text-align: center; font-size: 12px; }
    
    .sent-kpi-box { flex: 1 1 220px; border: 2px solid #00d18f; border-radius: 15px; padding: 20px; background: #e0f2f1; display: flex; flex-direction: column; align-items: center; justify-content: flex-start; min-height: 220px; }
    .sent-list { width: 100%; margin-bottom: 15px; margin-top: 5px; }
    .sent-row { display: flex; justify-content: space-between; align-items: center; font-size: 13px; font-weight: 700; margin-bottom: 6px; }
    .text-pos { color: #00C896; }
    .text-neu { color: #B0BEC5; }
    .text-neg { color: #FF4B4B; }
    
    @media (min-width: 768px) { .content-card { padding: 50px; } }
    '''

    # JS Code
    js_block = '''
    <script>
    Chart.defaults.font.family = "'Golca', 'Montserrat', sans-serif";
    Chart.defaults.plugins.tooltip.enabled = true;
    const colorMain = "#00d18f"; const colorOfficial = "#4DD0E1"; const colorEmpty = "#ffcdd2";

    function createDoughnut(id, val, activeColor) {
        var ctx = document.getElementById(id);
        if(!ctx) return;
        new Chart(ctx, {
            type: 'doughnut',
            data: { datasets: [{ data: [val, 100 - val], backgroundColor: [activeColor, colorEmpty], borderWidth: 0, hoverOffset: 4 }] },
            options: { layout: { padding: 10 }, responsive: true, maintainAspectRatio: false, cutout: '70%', plugins: { legend: { display: false }, tooltip: { enabled: false } } }
        });
    }

    function createSentimentDoughnut(id, pos, neu, neg) {
        var ctx = document.getElementById(id);
        if(!ctx) return;
        
        let dataValues = [pos, neu, neg];
        let bgColors = ['#00C896', '#B0BEC5', '#FF4B4B']; 
        let labels = ['Позитивна', 'Нейтральна', 'Негативна'];
        
        if (pos + neu + neg === 0) {
             dataValues = [1];
             bgColors = ['#E0E0E0']; 
             labels = ['Немає даних'];
        }

        new Chart(ctx, {
            type: 'doughnut',
            data: { labels: labels, datasets: [{ data: dataValues, backgroundColor: bgColors, borderWidth: 0, hoverOffset: 4 }] },
            options: { layout: { padding: 5 }, responsive: true, maintainAspectRatio: false, cutout: '60%', 
                plugins: { legend: { display: false }, 
                tooltip: { enabled: (pos + neu + neg > 0), 
                    callbacks: { label: function(context) { 
                        let label = context.label || ''; if (label) { label += ': '; }
                        if (context.parsed !== null) { label += Math.round(context.parsed) + '%'; } return label; 
                    }}}} }
        });
    }

    function openTab(evt, tabId) {
        var tabcontent = document.getElementsByClassName("tab-content");
        for (var i = 0; i < tabcontent.length; i++) { tabcontent[i].style.display = "none"; }
        var tablinks = document.getElementsByClassName("tab-btn");
        for (var i = 0; i < tablinks.length; i++) { tablinks[i].className = tablinks[i].className.replace(" active", ""); }
        document.getElementById(tabId).style.display = "block";
        var btn = document.getElementById("btn_" + tabId);
        if(btn) { btn.className += " active"; }
    }
    
    function toggleAcc(el) {
        el.classList.toggle("active");
        var panel = el.nextElementSibling;
        if (panel.style.display === "block") { panel.style.display = "none"; } else { panel.style.display = "block"; }
    }
    
    function topFunction() { window.scrollTo({top: 0, behavior: 'smooth'}); }
    
    window.onscroll = function() {scrollFunction()};
    function scrollFunction() {
        var mybutton = document.getElementById("myBtn");
        if (document.body.scrollTop > 300 || document.documentElement.scrollTop > 300) { mybutton.style.display = "flex"; } else { mybutton.style.display = "none"; }
    }
    
    window.addEventListener('load', function() { __JS_CHARTS_PLACEHOLDER__ });
    </script>
    '''

    html_template = '''<!DOCTYPE html>
<html lang="uk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Звіт AI Visibility</title>
<link rel="icon" type="image/png" href="https://raw.githubusercontent.com/virshi-ai/image/refs/heads/main/faviconV2.png">
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;700;800;900&display=swap" rel="stylesheet">
<style>__CSS_PLACEHOLDER__</style>
</head>
<body>
<button onclick="topFunction()" id="myBtn" class="go-top-btn" title="Наверх">⬆</button>

<div class="content-card">
    <div class="virshi-logo-container"><img src="https://raw.githubusercontent.com/virshi-ai/image/39ba460ec649893b9495427aa102420beb1fa48d/virshi-op_logo-main.png" class="logo-img-real" alt="VIRSHI Logo"></div>
    <div class="report-header"><h1>Звіт AI Visibility: __PROJECT_NAME__</h1><div class="subtitle">Дата формування: __DATE__</div></div>
    <div class="tabs-nav">__TABS_BUTTONS__</div>
    __TABS_CONTENT__
    <div class="cta-block"><p>Повний аудит Al Visibility включає моніторинг згадок вашого бренду в різних LLM.</p><p>Напишіть нам: <a href="mailto:hi@virshi.ai">hi@virshi.ai</a></p></div>
</div>
__JS_BLOCK__
</body>
</html>'''

    # Generate buttons
    tabs_buttons_html = ""
    for i, prov in enumerate(providers_ui):
        active_cls = "active" if i == 0 else ""
        prov_id = str(prov).replace(" ", "_").replace(".", "")
        tabs_buttons_html += f'<button id="btn_{prov_id}" class="tab-btn {active_cls}" onclick="openTab(event, \'{prov_id}\')">{prov}</button>\n'

    tabs_content_html = ""
    js_charts_code = ""

    tt_sov = "Частка видимості вашого бренду у відповідях ШІ порівняно з конкурентами."
    tt_off = "Частка посилань, які ведуть на ваші офіційні ресурси."
    tt_sent = "Тональність, у якій ШІ описує бренд."
    tt_pos = "Середня позиція вашого бренду у списках рекомендацій."
    tt_brand_cov = "Відсоток запитів, де бренд був згаданий."
    tt_domain_cov = "Відсоток запитів з клікабельним посиланням на ваш домен."

    # --- MAIN LOOP ---
    for i, prov_ui in enumerate(providers_ui):
        active_cls = "style='display:block;'" if i == 0 else "style='display:none;'"
        prov_id = str(prov_ui).replace(" ", "_").replace(".", "")
        
        provider_scans = data_by_provider[prov_ui]
        provider_scans.sort(key=lambda x: (query_time_map.get(x.get('keyword_text', ''), ''), x.get('keyword_text', '')), reverse=True)
        
        # Side Nav
        total_providers = len(providers_ui)
        if total_providers > 1:
            idx_prev = (i - 1) % total_providers
            idx_next = (i + 1) % total_providers
            prev_id = str(providers_ui[idx_prev]).replace(" ", "_").replace(".", "")
            next_id = str(providers_ui[idx_next]).replace(" ", "_").replace(".", "")
            
            side_nav_html = f'''
            <button class="nav-side-btn nav-left" onclick="openTab(event, '{prev_id}')">&#10094; {providers_ui[idx_prev]}</button>
            <button class="nav-side-btn nav-right" onclick="openTab(event, '{next_id}')">{providers_ui[idx_next]} &#10095;</button>
            '''
        else:
            side_nav_html = ""

        # Calc
        all_mentions = []
        all_sources = []
        for s in provider_scans:
            all_mentions.extend(s['brand_mentions'])
            all_sources.extend(s['extracted_sources'])
            
        df_m_local = pd.DataFrame(all_mentions)
        df_s_local = pd.DataFrame(all_sources)
        total_queries = len(provider_scans)
        
        sov_pct = 0
        if not df_m_local.empty:
            total_market = df_m_local['mention_count'].sum()
            my_total = df_m_local[df_m_local['is_real_target'] == True]['mention_count'].sum()
            if total_market > 0: sov_pct = (my_total / total_market * 100)
            
        off_pct = 0
        if not df_s_local.empty:
            total_lnk = len(df_s_local)
            off_lnk = len(df_s_local[df_s_local['is_official_calc'] == True])
            if total_lnk > 0: off_pct = (off_lnk / total_lnk * 100)
            
        brand_cov, domain_cov = 0, 0
        scans_present_count, scans_link_count = 0, 0
        for s in provider_scans:
            if any(m['is_real_target'] and m['mention_count'] > 0 for m in s['brand_mentions']): scans_present_count += 1
            if any(src['is_official_calc'] for src in s['extracted_sources']): scans_link_count += 1
        if total_queries > 0:
            brand_cov = (scans_present_count / total_queries * 100)
            domain_cov = (scans_link_count / total_queries * 100)

        avg_pos = 0
        if not df_m_local.empty:
            my_ranks = df_m_local[(df_m_local['is_real_target'] == True) & (df_m_local['rank_position'] > 0)]['rank_position']
            if not my_ranks.empty: avg_pos = my_ranks.mean()
        
        pos_v, neu_v, neg_v = 0, 0, 0
        if not df_m_local.empty:
            my_mentions_df = df_m_local[
                (df_m_local['is_real_target'] == True) & 
                (df_m_local['mention_count'] > 0)
            ]
            if not my_mentions_df.empty:
                counts = my_mentions_df['sentiment_score'].value_counts()
                total_s = counts.sum() 
                if total_s > 0:
                    pos_v = (counts.get('Позитивна', 0) / total_s * 100)
                    neu_v = (counts.get('Нейтральна', 0) / total_s * 100)
                    neg_v = (counts.get('Негативна', 0) / total_s * 100)
        
        # Summary Tables
        summary_competitors_html = ""
        if not df_m_local.empty:
            comp_grp = df_m_local.groupby('brand_name').agg(
                total_mentions=('mention_count', 'sum'),
                avg_pos=('rank_position', lambda x: x[x>0].mean() if not x[x>0].empty else 0),
                sentiment=('sentiment_score', lambda x: x.mode()[0] if not x.empty else 'Не згадано')
            ).reset_index().sort_values('total_mentions', ascending=False)
            comp_grp = comp_grp[comp_grp['total_mentions'] > 0]
            
            rows = ""
            for _, r in comp_grp.iterrows():
                pos_val = f"{r['avg_pos']:.1f}" if r['avg_pos'] > 0 else "-"
                s_txt = str(r['sentiment'])
                if 'Поз' in s_txt: s_txt = 'Позитивна'
                elif 'Нег' in s_txt: s_txt = 'Негативна'
                elif 'Ней' in s_txt: s_txt = 'Нейтральна'
                rows += f"<tr><td>{r['brand_name']}</td><td>{int(r['total_mentions'])}</td><td>{s_txt}</td><td>{pos_val}</td></tr>"
            
            if rows:
                summary_competitors_html = f'<div class="summary-section"><div class="summary-header">🏆 Конкурентний аналіз</div><div class="table-responsive"><table class="summary-table"><thead><tr><th>Бренд</th><th>Згадок</th><th>Тональність</th><th>Поз.</th></tr></thead><tbody>{rows}</tbody></table></div></div>'
            
        summary_links_html = ""
        if not df_s_local.empty:
            off_links = df_s_local[df_s_local['is_official_calc'] == True]
            if not off_links.empty:
                links_grp = off_links.groupby('url').size().reset_index(name='count').sort_values('count', ascending=False)
                rows = ""
                for _, r in links_grp.iterrows():
                    rows += f"<tr><td style='word-break:break-all;'><a href='{r['url']}' target='_blank' style='color:#00d18f; text-decoration:none;'>{r['url']}</a></td><td>{r['count']}</td></tr>"
                summary_links_html = f'<div class="summary-section"><div class="summary-header">✅ Цитовані офіційні посилання</div><div class="table-responsive"><table class="summary-table"><thead><tr><th>URL</th><th>Кількість</th></tr></thead><tbody>{rows}</tbody></table></div></div>'

        summary_domains_html = ""
        if not df_s_local.empty:
            dom_grp = df_s_local.groupby('domain_clean').size().reset_index(name='count').sort_values('count', ascending=False)
            rows = ""
            for _, r in dom_grp.iterrows():
                if r['domain_clean']: rows += f"<tr><td>{r['domain_clean']}</td><td>{r['count']}</td></tr>"
            if rows:
                summary_domains_html = f'<div class="summary-section"><div class="summary-header">🌐 Ренкінг доменів</div><div class="table-responsive"><table class="summary-table"><thead><tr><th>Домен</th><th>Згадок</th></tr></thead><tbody>{rows}</tbody></table></div></div>'

        # Tab Content
        tabs_content_html += f'''
        <div id="{prov_id}" class="tab-content" {active_cls}>
            {side_nav_html}
            <div class="kpi-row">
                <div class="kpi-box"><div class="kpi-tooltip">{tt_sov}</div><div class="kpi-title">Частка голосу (SOV)</div><div class="kpi-big-num">{sov_pct:.2f}%</div><div class="chart-container"><canvas id="chartSOV_{prov_id}"></canvas></div></div>
                <div class="kpi-box"><div class="kpi-tooltip">{tt_off}</div><div class="kpi-title">% Офіційних джерел</div><div class="kpi-big-num">{off_pct:.2f}%</div><div class="chart-container"><canvas id="chartOfficial_{prov_id}"></canvas></div></div>
                <div class="sent-kpi-box">
                    <div class="kpi-title">ЗАГАЛЬНА ТОНАЛЬНІСТЬ</div>
                    <div class="sent-list">
                        <div class="sent-row text-pos"><span>Позитивна</span><span>{pos_v:.0f}%</span></div>
                        <div class="sent-row text-neu"><span>Нейтральна</span><span>{neu_v:.0f}%</span></div>
                        <div class="sent-row text-neg"><span>Негативна</span><span>{neg_v:.0f}%</span></div>
                    </div>
                    <div class="chart-container"><canvas id="chartSent_{prov_id}"></canvas></div>
                </div>
            </div>
            <div class="kpi-row">
                <div class="kpi-box"><div class="kpi-tooltip">{tt_pos}</div><div class="kpi-title">Позиція бренду</div><div class="kpi-big-num">{avg_pos:.1f}</div><div class="chart-container"><canvas id="chartPos_{prov_id}"></canvas></div></div>
                <div class="kpi-box"><div class="kpi-tooltip">{tt_brand_cov}</div><div class="kpi-title">Присутність бренду</div><div class="kpi-big-num">{brand_cov:.1f}%</div><div class="chart-container"><canvas id="chartBrandCov_{prov_id}"></canvas></div></div>
                <div class="kpi-box"><div class="kpi-tooltip">{tt_domain_cov}</div><div class="kpi-title">Згадки домену</div><div class="kpi-big-num">{domain_cov:.1f}%</div><div class="chart-container"><canvas id="chartDomainCov_{prov_id}"></canvas></div></div>
            </div>
            {summary_competitors_html}
            {summary_links_html}
            {summary_domains_html}
            <h3 style="page-break-before: always;">Детальний аналіз запитів</h3>
            <div class="accordion-wrapper">
        '''

        # Details
        for idx, scan_row in enumerate(provider_scans):
            q_text = scan_row.get('keyword_text', 'Запит')
            loc_mentions = pd.DataFrame(scan_row['brand_mentions'])
            loc_sources = pd.DataFrame(scan_row['extracted_sources'])
            
            l_tot = loc_mentions['mention_count'].sum() if not loc_mentions.empty else 0
            my_row = loc_mentions[loc_mentions['is_real_target'] == True] if not loc_mentions.empty else pd.DataFrame()
            l_my = my_row['mention_count'].sum() if not my_row.empty else 0
            
            l_sov = (l_my / l_tot * 100) if l_tot > 0 else 0
            l_count = safe_int(l_my)
            l_sent = "Не знайдено"; l_pos = "0"; l_sent_color = "#333"

            if not my_row.empty and l_my > 0:
                best = my_row.sort_values('mention_count', ascending=False).iloc[0]
                l_sent = best.get('sentiment_score', 'Не знайдено')
                if 'Поз' in l_sent: l_sent = 'Позитивна'
                elif 'Нег' in l_sent: l_sent = 'Негативна'
                elif 'Ней' in l_sent: l_sent = 'Нейтральна'
                vr = my_row[my_row['rank_position'] > 0]['rank_position']
                val = vr.min() if not vr.empty else None
                if pd.notnull(val): l_pos = f"#{safe_int(val)}"
            
            if l_sent == "Позитивна": l_sent_color = "#00C896"
            elif l_sent == "Негативна": l_sent_color = "#FF4B4B"

            details_html = ""
            if not loc_mentions.empty or not loc_sources.empty:
                details_html += '<div class="detail-charts-wrapper">'
                if not loc_mentions.empty:
                    rows_b = ""
                    loc_mentions['sort_rank'] = loc_mentions['rank_position'].replace(0, 9999)
                    sort_b = loc_mentions.sort_values(['sort_rank', 'mention_count'], ascending=[True, False])
                    has_b = False
                    for _, b in sort_b.iterrows():
                        if b['mention_count'] > 0:
                            has_b = True
                            bg = "style='background:#e6fffa; font-weight:bold;'" if b['is_real_target'] else ""
                            s_loc = b['sentiment_score']
                            if 'Поз' in s_loc: s_loc = 'Позитивна'
                            elif 'Нег' in s_loc: s_loc = 'Негативна'
                            elif 'Ней' in s_loc: s_loc = 'Нейтральна'
                            rows_b += f"<tr {bg}><td>{b['brand_name']}</td><td>{safe_int(b['mention_count'])}</td><td>{s_loc}</td><td>{safe_int(b['rank_position'])}</td></tr>"
                    if has_b: details_html += f'<div class="detail-chart-block"><div class="detail-title">Знайдені бренди</div><div class="table-responsive"><table class="inner-table"><thead><tr><th>Бренд</th><th>Кіл.</th><th>Тональність</th><th>Поз.</th></tr></thead><tbody>{rows_b}</tbody></table></div></div>'
                    else: details_html += '<div class="detail-chart-block"><div class="detail-title">Знайдені бренди</div><div style="font-size:12px; color:#999; padding:5px;">Брендів не знайдено</div></div>'

                if not loc_sources.empty:
                    rows_s = ""
                    for _, s in loc_sources.iterrows():
                        icon = "✅" if s['is_official_calc'] else "🔗"
                        url = str(s.get('url', ''))
                        rows_s += f"<tr><td style='word-break:break-all;'><a href='{url}' target='_blank' style='color:#00d18f; text-decoration:none;'>{url}</a></td><td>{icon}</td></tr>"
                    details_html += f'<div class="detail-chart-block"><div class="detail-title">Цитовані джерела</div><div class="table-responsive"><table class="inner-table"><thead><tr><th>URL</th><th>Тип</th></tr></thead><tbody>{rows_s}</tbody></table></div></div>'
                details_html += '</div>'

            raw_t = format_llm_text(scan_row.get('raw_response', ''))
            tabs_content_html += f'<div class="item-box"><div class="item-header accordion-trigger" onclick="toggleAcc(this)"><div class="item-number-wrapper"><span class="item-number">{idx+1}</span></div><div class="item-query">{q_text}</div><div class="accordion-arrow">▼</div></div><div class="accordion-content" style="display: none;"><div class="cards-row"><div class="metric-card"><div class="mc-label">SOV <span class="info-icon" title="Частка">%</span></div><div class="mc-val">{l_sov:.1f}%</div></div><div class="metric-card"><div class="mc-label">ЗГАДОК <span class="info-icon" title="Кількість">#</span></div><div class="mc-val">{l_count}</div></div><div class="metric-card"><div class="mc-label">ТОНАЛЬНІСТЬ <span class="info-icon" title="Настрій">☺</span></div><div class="mc-val" style="font-size:16px; color:{l_sent_color};">{l_sent}</div></div><div class="metric-card"><div class="mc-label">ПОЗИЦІЯ <span class="info-icon" title="Ранг">1</span></div><div class="mc-val">{l_pos}</div></div></div><div class="item-response"><div class="response-label">Відповідь LLM:</div>{raw_t}{details_html}</div></div></div>'
        
        tabs_content_html += "</div></div>"
        
        js_charts_code += f"createDoughnut('chartSOV_{prov_id}', {sov_pct}, '#00d18f');\n"
        js_charts_code += f"createDoughnut('chartOfficial_{prov_id}', {off_pct}, '#4DD0E1');\n"
        js_charts_code += f"createSentimentDoughnut('chartSent_{prov_id}', {pos_v}, {neu_v}, {neg_v});\n"
        js_charts_code += f"createDoughnut('chartBrandCov_{prov_id}', {brand_cov}, '#00d18f');\n"
        js_charts_code += f"createDoughnut('chartDomainCov_{prov_id}', {domain_cov}, '#4DD0E1');\n"
        score_pos = max(0, 11 - avg_pos) if avg_pos > 0 else 0
        js_charts_code += f"createDoughnut('chartPos_{prov_id}', {score_pos * 10}, '#00d18f');\n"

    final_js = js_block.replace("__JS_CHARTS_PLACEHOLDER__", js_charts_code)
    final_html = html_template.replace("__CSS_PLACEHOLDER__", css_styles)\
        .replace("__PROJECT_NAME__", str(project_name))\
        .replace("__DATE__", str(current_date))\
        .replace("__TABS_BUTTONS__", tabs_buttons_html)\
        .replace("__TABS_CONTENT__", tabs_content_html)\
        .replace("__JS_BLOCK__", final_js)

    return final_html

def show_reports_page():
    """
    Сторінка Звітів (Фінальна версія).
    Виправлено:
    - Імпорт supabase з utils.db.
    - Видалено перевірку globals().
    """
    
    # Налаштування часового поясу
    try:
        kyiv_tz = pytz.timezone('Europe/Kiev')
    except:
        kyiv_tz = None

    st.title("📊 Звіти")

    # --- ПЕРЕВІРКА ПРОЕКТУ ---
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
                    html_code = generate_html_report_content(proj.get('brand_name'), final_scans_data, whitelist_domains)
                    
                    # 6. Save
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
                                    if kyiv_tz:
                                        dt_kyiv = dt_utc.astimezone(kyiv_tz)
                                        fmt_time = dt_kyiv.strftime('%d.%m.%Y %H:%M')
                                    else:
                                        fmt_time = dt_utc.strftime('%d.%m.%Y %H:%M UTC')
                                except:
                                    fmt_time = pr['created_at']
                                
                                st.caption(f"📅 {fmt_time}")

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
                                    st.rerun() 
            except Exception as e:
                st.error(f"Помилка адмінки: {e}")
